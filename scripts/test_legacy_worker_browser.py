#!/usr/bin/env python3
"""Real, loopback-only Chromium lifecycle checks for legacy-worker retirement.

Uses synthetic HTML, storage and worker fixtures. No app backend, credentials,
provider calls, notification sends, screenshots or traces are involved.
"""

import argparse
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import signal
import threading
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
PHASE = "startup"
LEGACY_WORKER = """
const CACHE_NAME = 'cashoutai-v1';
self.addEventListener('install', event => event.waitUntil(
  caches.open(CACHE_NAME).then(cache => cache.add('/'))));
self.addEventListener('activate', event => event.waitUntil(
  caches.keys().then(names => Promise.all(names.filter(name => name !== CACHE_NAME).map(name => caches.delete(name))))));
self.addEventListener('fetch', event => event.respondWith(
  caches.match(event.request).then(response => response || fetch(event.request))));
"""
FIREBASE_FIXTURE = """
self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
"""


def require(condition):
    if not condition:
        raise AssertionError("legacy_worker_browser_check_failed")


@contextmanager
def fixture_server():
    retirement = (ROOT / "frontend/public/sw.js").read_bytes()
    helper = (ROOT / "frontend/src/legacyWorkerMigration.mjs").read_bytes()
    state = {"legacy": True}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/":
                release = "legacy" if state["legacy"] else "current"
                body = ("<!doctype html><html><head><meta charset='utf-8'></head><body>"
                        f"<p id='release'>{release}</p><input id='draft' aria-label='Draft'>"
                        "<script>sessionStorage.setItem('fixture_visits',"
                        "String(Number(sessionStorage.getItem('fixture_visits') || 0) + 1));</script>"
                        "</body></html>").encode()
                content_type = "text/html; charset=utf-8"
            elif path == "/sw.js":
                body = LEGACY_WORKER.encode() if state["legacy"] else retirement
                content_type = "application/javascript; charset=utf-8"
            elif path == "/legacyWorkerMigration.mjs":
                body, content_type = helper, "application/javascript; charset=utf-8"
            elif path == "/firebase-messaging-sw.js":
                body, content_type = FIREBASE_FIXTURE.encode(), "application/javascript; charset=utf-8"
            elif path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            else:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def seed_private_state(page):
    page.locator("#draft").fill("Synthetic unsaved draft")
    return page.evaluate("""async () => {
      localStorage.setItem('cashoutai_user', JSON.stringify({id:'synthetic-member',active_session_id:'synthetic-session'}));
      sessionStorage.setItem('fixture_billing_state', 'synthetic-only');
      const push = await caches.open('cashoutai-stock-push-v1');
      await push.put('/__cashoutai_stock_push_state__', new Response('synthetic-push-context'));
      const unrelated = await caches.open('fixture-unrelated-cache');
      await unrelated.put('/fixture-other', new Response('synthetic-other'));
      return {user:localStorage.getItem('cashoutai_user'),billing:sessionStorage.getItem('fixture_billing_state'),
        permission:(await navigator.permissions.query({name:'notifications'})).state,
        visits:Number(sessionStorage.getItem('fixture_visits'))};
    }""")


def verify_preserved(page, before, *, visits):
    state = page.evaluate("""async () => {
      const push = await (await caches.open('cashoutai-stock-push-v1')).match('/__cashoutai_stock_push_state__');
      const other = await (await caches.open('fixture-unrelated-cache')).match('/fixture-other');
      return {user:localStorage.getItem('cashoutai_user'),billing:sessionStorage.getItem('fixture_billing_state'),
        permission:(await navigator.permissions.query({name:'notifications'})).state,
        visits:Number(sessionStorage.getItem('fixture_visits')),
        push:push && await push.text(),other:other && await other.text()};
    }""")
    require(state == {**before, "visits": visits,
                      "push": "synthetic-push-context", "other": "synthetic-other"})


def seed_legacy(page, origin):
    page.goto(origin + "/", wait_until="load")
    page.evaluate("""async () => {
      await navigator.serviceWorker.register('/sw.js');
      await navigator.serviceWorker.ready;
    }""")
    page.reload(wait_until="load")
    page.wait_for_function("navigator.serviceWorker.controller?.scriptURL === location.origin + '/sw.js'")
    require(page.locator("#release").inner_text() == "legacy")
    require(page.evaluate("caches.has('cashoutai-v1')"))


def wait_retired(page):
    page.wait_for_function("""async () => {
      const registrations = await navigator.serviceWorker.getRegistrations();
      return !registrations.some(registration => [registration.installing, registration.waiting, registration.active]
        .some(worker => worker?.scriptURL === location.origin + '/sw.js')) && !await caches.has('cashoutai-v1');
    }""")


def call_migration(page):
    return page.evaluate("""async () => {
      const module = await import('/legacyWorkerMigration.mjs');
      return await module.retireLegacyServiceWorker();
    }""")


def exercise(browser, origin, state):
    global PHASE
    external_requests = []
    page_errors = []
    expected_origin = urlsplit(origin)

    @contextmanager
    def isolated_page():
        context = browser.new_context(service_workers="allow")
        context.set_default_timeout(15000)

        def is_local(url):
            parsed = urlsplit(url)
            return parsed.scheme == "http" and parsed.hostname == "127.0.0.1" and parsed.port == expected_origin.port

        def route_request(route):
            if is_local(route.request.url):
                route.continue_()
            else:
                external_requests.append(True)
                route.abort()

        def observe_request(request):
            if not is_local(request.url):
                external_requests.append(True)

        context.route("**/*", route_request)
        context.on("request", observe_request)
        page = context.new_page()
        page.on("pageerror", lambda _: page_errors.append(True))
        try:
            yield page
        finally:
            context.close()

    PHASE = "worker_update_lifecycle"
    with isolated_page() as page:
        state["legacy"] = True
        seed_legacy(page, origin)
        before = seed_private_state(page)
        state["legacy"] = False
        # Exercise an already-open old client, where the new app helper has
        # never run. The browser updates the historical worker URL itself.
        page.evaluate("""async () => {
          const registration = await navigator.serviceWorker.getRegistration('/');
          await registration.update();
        }""")
        wait_retired(page)
        require(page.locator("#release").inner_text() == "legacy")
        require(page.locator("#draft").input_value() == "Synthetic unsaved draft")
        verify_preserved(page, before, visits=before["visits"])
        page.reload(wait_until="load")
        require(page.locator("#release").inner_text() == "current")
        verify_preserved(page, before, visits=before["visits"] + 1)

    PHASE = "startup_helper_lifecycle"
    with isolated_page() as page:
        state["legacy"] = True
        seed_legacy(page, origin)
        before = seed_private_state(page)
        state["legacy"] = False
        result = call_migration(page)
        require(result["matched"] == 1 and result["unregistered"] in (0, 1))
        wait_retired(page)
        require(page.locator("#draft").input_value() == "Synthetic unsaved draft")
        verify_preserved(page, before, visits=before["visits"])
        page.reload(wait_until="load")
        require(page.locator("#release").inner_text() == "current")
        require(call_migration(page) == {"matched": 0, "unregistered": 0})
        verify_preserved(page, before, visits=before["visits"] + 1)

    PHASE = "firebase_preservation"
    with isolated_page() as page:
        state["legacy"] = False
        page.goto(origin + "/", wait_until="load")
        page.evaluate("""async () => {
          await navigator.serviceWorker.register('/firebase-messaging-sw.js');
          await navigator.serviceWorker.ready;
        }""")
        page.wait_for_function("navigator.serviceWorker.controller?.scriptURL === location.origin + '/firebase-messaging-sw.js'")
        before = seed_private_state(page)
        require(call_migration(page) == {"matched": 0, "unregistered": 0})
        # A stale client explicitly registering /sw.js must not replace the
        # working Firebase registration on its shared root scope.
        page.evaluate("navigator.serviceWorker.register('/sw.js').catch(() => null)")
        page.wait_for_function("""async () => {
          const registration = await navigator.serviceWorker.getRegistration('/');
          return registration?.active?.scriptURL === location.origin + '/firebase-messaging-sw.js'
            && !registration.installing && !registration.waiting;
        }""")
        require(page.locator("#draft").input_value() == "Synthetic unsaved draft")
        verify_preserved(page, before, visits=before["visits"])
    require(not external_requests and not page_errors)
    return {"result": "PASS", "mode": "synthetic_loopback_only", "lifecycle_cases": 3,
            "cached_root_recovered": True, "firebase_registration_preserved": True,
            "session_storage_preserved": True, "push_cache_preserved": True,
            "notification_permission_preserved": True, "unsaved_draft_preserved": True,
            "automatic_navigations": 0, "external_browser_requests": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chromium-executable", type=Path, help="Optional local Chromium; CI uses Playwright's pinned browser.")
    args = parser.parse_args()
    try:
        def interrupted(*_):
            raise RuntimeError("legacy_worker_browser_deadline")
        signal.signal(signal.SIGALRM, interrupted)
        signal.alarm(180)
        launch = {"headless": True}
        if args.chromium_executable:
            require(args.chromium_executable.is_absolute() and args.chromium_executable.is_file())
            launch["executable_path"] = str(args.chromium_executable)
        with fixture_server() as (origin, state), sync_playwright() as playwright:
            browser = playwright.chromium.launch(**launch)
            try:
                result = exercise(browser, origin, state)
            finally:
                browser.close()
        signal.alarm(0)
    except BaseException:
        print(json.dumps({"result": "FAIL", "mode": "synthetic_loopback_only", "phase": PHASE,
                          "reason": "legacy_worker_browser_check_failed"}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
