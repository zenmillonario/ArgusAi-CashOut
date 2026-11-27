"""Check credential-landing privacy in the actual compiled frontend.

All accounts, tokens, passwords and API responses here are inert fixtures. A
loopback server serves the supplied production build. Every nonlocal browser
request is intercepted: script requests receive an inert observation sentinel,
and other requests are fulfilled locally or blocked. No provider is contacted,
no application database is used, and no browser state or artifacts are retained.

This proves the HTML policy and compiled reset/event UI cooperate. It is not
evidence of backend recovery, real email delivery or production deployment.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import html
import json
import os
from pathlib import Path
import signal
import threading
from urllib.parse import parse_qs, urlsplit


TOKEN = "inert-privacy-fixture-token-" + "x" * 32
PASSWORD = "Inert-privacy-fixture-password-42"
LATE_SCRIPT = "https://privacy-sentinel.invalid/late.js"
PHASE = "configuration"
SENTINEL = """(() => {
  const started = window.__privacySentinels || (window.__privacySentinels = []);
  started.push({ source: document.currentScript.src, href: location.href,
    inputs: Array.from(document.querySelectorAll('input'), input => input.value) });
})();"""


class PrivacyCheckError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise PrivacyCheckError(message)


class QuietBuildHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        # Serve the real index for the legacy recovery route, as the deployed
        # static site's SPA rewrite does. The response sets no privacy headers;
        # the test must depend on the actual HTML policy under review.
        if urlsplit(self.path).path == "/reset-password":
            self.path = "/index.html"
        super().do_GET()

    def log_message(self, *_args):
        pass


def local_url(url, origin):
    try:
        parsed = urlsplit(url)
        expected = urlsplit(origin)
        return (parsed.scheme == "http" and parsed.hostname == "127.0.0.1"
                and parsed.port == expected.port and parsed.username is None and parsed.password is None)
    except ValueError:
        return False


def exercise_case(browser, origin, kind, framed):
    private = kind != "normal"
    query = {"normal": "/", "reset": "/?reset_token=" + TOKEN,
             "legacy_reset": "/reset-password?token=" + TOKEN, "event": "/?event_token=" + TOKEN}[kind]
    counters = {"sentinel_requests": 0, "referrer_headers": 0, "token_referrers": 0,
                "reset_posts": 0, "event_posts": 0, "unexpected_posts": 0, "page_errors": 0}
    now = datetime.now(timezone.utc)
    ends = (now + timedelta(days=1)).isoformat()

    def route_request(route):
        request = route.request
        address = urlsplit(request.url)
        referrer = request.headers.get("referer", "")
        counters["referrer_headers"] += bool(referrer)
        counters["token_referrers"] += TOKEN in referrer
        if local_url(request.url, origin):
            if address.path == "/__privacy_frame__":
                markup = ('<!doctype html><meta name="referrer" content="no-referrer">'
                          '<iframe id="app-frame" style="width:1280px;height:960px" src="'
                          + html.escape(origin + query, quote=True) + '"></iframe>')
                return route.fulfill(status=200, content_type="text/html", body=markup)
            if address.path == "/__privacy_referrer_probe__":
                return route.fulfill(status=200, content_type="text/plain", body="fixture")
            if address.path.startswith("/api/"):
                status, value = 200, {}
                if request.method == "GET" and address.path == "/api/practice-event":
                    value = {"campaign_id": "privacy-fixture", "status": "open", "starts_at": None,
                             "ends_at": ends, "server_now": now.isoformat()}
                elif request.method == "POST" and address.path == "/api/users/reset-password-confirm":
                    valid = request.post_data_json == {"token": TOKEN, "new_password": PASSWORD}
                    counters["reset_posts"] += int(valid)
                    status, value = (200, {"message": "Fixture accepted"}) if valid else (400, {"detail": "Fixture refused"})
                elif request.method == "POST" and address.path == "/api/practice-event/confirm":
                    valid = request.post_data_json == {"token": TOKEN}
                    counters["event_posts"] += int(valid)
                    status, value = (200, {"status": "confirmed", "access": "practice_event",
                                          "sign_in_required": True, "username": "privacy_fixture",
                                          "ends_at": ends}) if valid else (400, {"detail": "Fixture refused"})
                elif request.method not in {"GET", "HEAD", "OPTIONS"}:
                    counters["unexpected_posts"] += 1
                    status, value = 403, {"detail": "Only the inert privacy fixture is available"}
                return route.fulfill(status=status, content_type="application/json", body=json.dumps(value))
            return route.continue_()
        if request.resource_type == "script":
            counters["sentinel_requests"] += 1
            return route.fulfill(status=200, content_type="application/javascript", body=SENTINEL,
                                 headers={"Access-Control-Allow-Origin": "*"})
        if request.resource_type == "stylesheet":
            return route.fulfill(status=200, content_type="text/css", body="/* offline fixture */")
        return route.abort("blockedbyclient")

    context = browser.new_context(service_workers="block", reduced_motion="reduce", accept_downloads=False,
                                  viewport={"width": 1365, "height": 1024})
    context.set_default_timeout(15000)
    context.route("**/*", route_request)
    context.route_web_socket("**/*", lambda route: route.close(code=1008, reason="Offline privacy fixture"))
    page = context.new_page()
    page.on("dialog", lambda dialog: dialog.accept())
    page.on("pageerror", lambda _: counters.__setitem__("page_errors", counters["page_errors"] + 1))
    try:
        page.goto(origin + ("/__privacy_frame__" if framed else query), wait_until="domcontentloaded")
        if framed:
            page.locator("#app-frame").wait_for()
            frame = page.frame_locator("#app-frame")
            frame.locator("html").wait_for()
            target = page.locator("#app-frame").element_handle().content_frame()
            require(target is not None, "The compiled iframe did not load")
        else:
            target = page
        target.wait_for_function("() => typeof window.__CASHOUTAI_PRIVATE_LANDING__ === 'boolean'")
        require(target.evaluate("() => window.__CASHOUTAI_PRIVATE_LANDING__") is private,
                "The initial credential-landing classification was incorrect")

        if kind in {"reset", "legacy_reset"}:
            dialog = target.get_by_role("dialog", name="Set a new password", exact=True)
            dialog.wait_for(state="visible")
            dialog.get_by_label("New password", exact=True).fill(PASSWORD)
            dialog.get_by_label("Confirm new password", exact=True).fill(PASSWORD)
        elif kind == "event":
            target.get_by_role("heading", name="Confirm your practice access.", exact=True).wait_for()
        else:
            submit = target.get_by_role("button", name="Sign in", exact=True)
            submit.wait_for()
            expected = 4 if framed else 2
            target.wait_for_function("minimum => (window.__privacySentinels || []).length >= minimum", arg=expected)
            form = target.locator("form").filter(has=submit)
            form.locator('input[type="text"]').fill("privacy_fixture")
            form.locator('input[type="password"]').fill(PASSWORD)

        if private:
            query_keys = parse_qs(urlsplit(target.url).query, keep_blank_values=True)
            require(not {"reset_token", "event_token", "token"} & query_keys.keys(),
                    "The compiled app did not remove its credential query")
            require(target.evaluate("() => (window.__privacySentinels || []).length") == 0
                    and counters["sentinel_requests"] == 0,
                    "Third-party code initialized on a sensitive landing")
            require(target.evaluate("() => typeof window.posthog === 'undefined'"),
                    "The analytics initializer ran on a sensitive landing")
            require(target.evaluate("""() => {
                const descriptor = Object.getOwnPropertyDescriptor(window, '__CASHOUTAI_PRIVATE_LANDING__');
                return descriptor.value === true && descriptor.writable === false && descriptor.configurable === false;
            }"""), "The private landing flag can change after URL cleanup")

        # Attempt a fresh remote script after the app has cleaned the URL and
        # (for reset) the real password inputs have been filled. The normal
        # controls prove the inert sentinel actually loads when permitted.
        outcome = target.evaluate("""source => new Promise(resolve => {
            const script = document.createElement('script');
            script.onload = () => resolve('loaded');
            script.onerror = () => resolve('blocked');
            script.src = source;
            document.head.appendChild(script);
        })""", LATE_SCRIPT)
        require(outcome == ("blocked" if private else "loaded"),
                "The document-lifetime external script boundary failed")
        if not private:
            require(target.evaluate("value => window.__privacySentinels.at(-1).inputs.includes(value)", PASSWORD),
                    "The normal control did not prove the sentinel could observe filled fixture inputs")
        require(target.evaluate("() => document.querySelector('meta[name=referrer]')?.content === 'no-referrer'"),
                "The document did not retain its no-referrer policy")
        target.evaluate("() => fetch('/__privacy_referrer_probe__', { cache: 'no-store' })")

        if kind in {"reset", "legacy_reset"}:
            dialog.get_by_role("button", name="Save new password", exact=True).click()
            dialog.wait_for(state="hidden")
            target.get_by_role("button", name="Sign in", exact=True).wait_for()
            require(counters["reset_posts"] == 1 and counters["event_posts"] == 0,
                    "The compiled password form did not preserve its original token")
        elif kind == "event":
            target.get_by_role("button", name="Confirm my email", exact=True).click()
            target.get_by_role("heading", name="Your email is verified.", exact=True).wait_for()
            target.get_by_role("button", name="Continue to sign in", exact=True).click()
            target.get_by_role("button", name="Sign in", exact=True).wait_for()
            require(counters["event_posts"] == 1 and counters["reset_posts"] == 0,
                    "The compiled verification flow did not preserve its original token")

        require(counters["referrer_headers"] == 0 and counters["token_referrers"] == 0,
                "A request carried a referrer during the credential privacy check")
        require(counters["unexpected_posts"] == 0 and counters["page_errors"] == 0,
                "The compiled app raised an error or attempted an unexpected write")
        require(target.evaluate("""values => [localStorage, sessionStorage].every(storage =>
            Object.keys(storage).every(key => values.every(value => !storage.getItem(key).includes(value))))
        """, [TOKEN, PASSWORD]), "A credential fixture was retained in browser storage")
        if private:
            require(target.evaluate("() => (window.__privacySentinels || []).length") == 0,
                    "Third-party code started after the sensitive form completed")
        return {"case": kind, "iframe": framed, "result": "PASS"}
    finally:
        context.close()


def run(args):
    from playwright.sync_api import sync_playwright

    build = args.frontend_build.resolve(strict=True)
    require(build.is_dir() and (build / "index.html").is_file()
            and any((build / "static/js").glob("*.js")), "A compiled production frontend is required")
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietBuildHandler, directory=str(build)))
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    environment = {key: value for key, value in os.environ.items()
                   if key in {"PATH", "LD_LIBRARY_PATH", "PLAYWRIGHT_BROWSERS_PATH", "TMPDIR"}}
    os.environ.pop("DEBUG", None)
    os.environ.pop("PWDEBUG", None)
    global PHASE
    try:
        with sync_playwright() as driver:
            options = {"headless": True, "env": environment, "args": [
                "--disable-background-networking", "--disable-component-update", "--disable-domain-reliability",
                "--disable-sync", "--no-first-run", "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1"]}
            if args.browser_executable:
                options["executable_path"] = str(args.browser_executable.resolve(strict=True))
            browser = driver.chromium.launch(**options)
            try:
                cases = []
                for kind in ("reset", "legacy_reset", "event", "normal"):
                    for framed in (False, True):
                        PHASE = kind + ("_iframe" if framed else "_top_level")
                        cases.append(exercise_case(browser, origin, kind, framed))
                return {"result": "PASS", "cases": cases, "compiled_frontend": True,
                        "api": "inert_fixtures_only", "external_network_connections_allowed": 0,
                        "real_accounts_used": 0, "real_emails_sent": 0,
                        "production_deployment_verified": False}
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-build", type=Path, required=True)
    parser.add_argument("--browser-executable", type=Path)
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        print(json.dumps(run(args), sort_keys=True))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        # Driver errors can contain entered values and full URLs. Emit only a
        # fixed phase and reason, never those errors or page/console output.
        print(json.dumps({"result": "FAIL", "phase": PHASE,
                          "reason": str(error) if isinstance(error, PrivacyCheckError) else "Compiled privacy check did not complete",
                          "production_deployment_verified": False}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
