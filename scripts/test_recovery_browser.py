"""Exercise the compiled recovery UI against a new, wholly synthetic MongoDB copy.

The existing guarded preview owns the app, email capture and preservation checks.
This runner never accepts an Atlas URI, an existing member selection, or a remote
origin. Browser traffic is restricted to the preview's numeric loopback origin.
Reset links, passwords, sessions, page console, screenshots and traces are never
printed or uploaded. Only aggregate results leave the private temporary folder.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import stat
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import ProxyHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
DATABASE = "cashout_rehearsal_github_browser"
PHASE = "configuration"


class BrowserCheckError(Exception):
    """Fixed, non-sensitive messages suitable for the aggregate test result."""


def require(condition, reason):
    if not condition:
        raise BrowserCheckError(reason)


def private_json(path):
    info = path.stat()
    require(not path.is_symlink() and stat.S_ISREG(info.st_mode)
            and info.st_uid == os.getuid() and not info.st_mode & 0o077,
            "Private preview evidence has unsafe permissions")
    require(info.st_size < 65536, "Private preview evidence is unexpectedly large")
    return json.loads(path.read_text(encoding="utf-8"))


def local_url(url, port, *, websocket=False):
    try:
        parts = urlsplit(url)
        return (parts.scheme == ("ws" if websocket else "http")
                and parts.hostname == "127.0.0.1" and parts.port == port
                and parts.username is None and parts.password is None)
    except ValueError:
        return False


def api_get(origin, path, headers=None):
    require(path.startswith("/api/") and not path.startswith("//"), "Unexpected API path")
    opener = build_opener(ProxyHandler({}))
    request = Request(origin + path, headers=headers or {}, method="GET")
    try:
        with opener.open(request, timeout=5) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, None


def wait_until(check, process, seconds=40):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        require(process.poll() is None, "The guarded preview stopped before the browser check")
        try:
            result = check()
            if result:
                return result
        except (FileNotFoundError, json.JSONDecodeError, URLError, TimeoutError):
            pass
        time.sleep(0.1)
    raise BrowserCheckError("The guarded preview did not become ready in time")


def stop_preview(process):
    if process.poll() is None:
        process.terminate()  # Uvicorn handles SIGTERM and runs preservation checks.
        try:
            process.wait(timeout=25)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise BrowserCheckError("The guarded preview did not stop cleanly")


def wait_for_captured_link(state_dir, port, pause, timeout=10):
    """FastAPI may complete the HTTP response before its email background task."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            captures = private_json(state_dir / "captured-links.json")
        except (FileNotFoundError, json.JSONDecodeError):
            # The capture file is written privately by the existing preview;
            # a first read can also overlap its truncate/write operation.
            captures = []
        require(isinstance(captures, list) and all(isinstance(entry, dict) for entry in captures),
                "The private email capture has an unexpected structure")
        links = [entry["reset_url"] for entry in captures
                 if entry.get("label") == "member" and entry.get("reset_url")]
        require(len(links) <= 1, "The recovery request captured more than one member link")
        if links:
            require(isinstance(links[0], str) and local_url(links[0], port)
                    and urlsplit(links[0]).path == "/"
                    and set(parse_qs(urlsplit(links[0]).query)) == {"reset_token"},
                    "The captured recovery link does not match the isolated frontend")
            return links[0]
        pause(100)
    raise BrowserCheckError("The synthetic recovery email was not captured within the bounded wait")


def browser_exercise(origin, port, state_dir, private_root):
    from playwright.sync_api import sync_playwright

    details = private_json(state_dir / "operator-details.json")
    require(details.get("origin") == origin, "The browser and preview origins differ")
    member = details["accounts"]["member"]
    require(member == {"username": "rehearsal_member", "email": "member@example.test"},
            "The browser runner accepts only its synthetic member")
    counters = {"blocked_external_http": 0, "blocked_external_websocket": 0, "page_errors": 0}
    password = secrets.token_urlsafe(24)

    def http_route(route):
        if local_url(route.request.url, port):
            route.continue_()
        else:
            counters["blocked_external_http"] += 1
            route.abort("blockedbyclient")

    def socket_route(route):
        if local_url(route.url, port, websocket=True):
            route.connect_to_server()
        else:
            counters["blocked_external_websocket"] += 1
            route.close(code=1008, reason="Private rehearsal only")

    def context(browser):
        result = browser.new_context(service_workers="block", reduced_motion="reduce",
                                     accept_downloads=False, viewport={"width": 1280, "height": 960})
        result.set_default_timeout(15000)
        result.route("**/*", http_route)
        result.route_web_socket("**/*", socket_route)
        return result

    def page(context):
        result = context.new_page()
        result.on("dialog", lambda dialog: dialog.accept())
        # Count uncaught errors without retaining error text or browser console.
        result.on("pageerror", lambda _: counters.__setitem__("page_errors", counters["page_errors"] + 1))
        return result

    def posted(path):
        return lambda response: (local_url(response.url, port)
                                 and urlsplit(response.url).path == path
                                 and response.request.method == "POST")

    def save_password(target, link, expected_status):
        target.goto(link, wait_until="domcontentloaded")
        dialog = target.get_by_role("dialog", name="Set a new password", exact=True)
        dialog.wait_for(state="visible")
        require("reset_token" not in parse_qs(urlsplit(target.url).query),
                "The compiled frontend did not remove the recovery token from the address bar")
        dialog.get_by_label("New password", exact=True).fill(password)
        dialog.get_by_label("Confirm new password", exact=True).fill(password)
        with target.expect_response(posted("/api/users/reset-password-confirm")) as received:
            dialog.get_by_role("button", name="Save new password", exact=True).click()
        require(received.value.status == expected_status, "The recovery form returned an unexpected status")
        if expected_status == 200:
            dialog.wait_for(state="hidden")

    def login(target):
        # Use the application's existing account/profile landing. The default
        # bot room creates a practice ledger on GET; that is outside recovery
        # preservation and deliberately remains outside this browser check.
        target.goto(origin + "/?billing=1", wait_until="domcontentloaded")
        submit = target.get_by_role("button", name="Sign in", exact=True)
        submit.wait_for(state="visible")
        form = target.locator("form").filter(has=submit)
        form.locator('input[type="text"]').fill(member["username"])
        form.locator('input[type="password"]').fill(password)
        with target.expect_response(posted("/api/users/login")) as received:
            submit.click()
        require(received.value.status == 200, "Browser sign-in did not succeed")
        session = received.value.json()
        require(session.get("id") == "rehearsal-member" and bool(session.get("active_session_id")),
                "Browser sign-in did not preserve the synthetic account identity")
        target.get_by_test_id("logout-btn").wait_for(state="visible")
        saved = target.evaluate("() => JSON.parse(localStorage.getItem('cashoutai_user'))")
        require(saved and saved.get("id") == session["id"]
                and saved.get("active_session_id") == session["active_session_id"],
                "The compiled frontend did not retain its verified session")
        return {"X-User-ID": session["id"], "X-Session-ID": session["active_session_id"]}

    global PHASE
    # Avoid inherited Playwright debug logging, which can contain token URLs.
    os.environ.pop("DEBUG", None)
    os.environ.pop("PWDEBUG", None)
    with sync_playwright() as driver:
        browser_env = {key: value for key, value in os.environ.items()
                       if key in {"PATH", "LD_LIBRARY_PATH", "PLAYWRIGHT_BROWSERS_PATH"}}
        browser_env["TMPDIR"] = str(private_root)
        browser = driver.chromium.launch(headless=True, env=browser_env, args=[
            "--disable-background-networking", "--disable-component-update",
            "--disable-domain-reliability", "--disable-sync", "--no-first-run",
            "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
        ])
        try:
            first_context = context(browser)
            first_page = page(first_context)
            PHASE = "request_recovery_in_browser"
            first_page.goto(origin + "/", wait_until="domcontentloaded")
            first_page.get_by_role("button", name="Recover existing account", exact=True).click()
            dialog = first_page.get_by_role("dialog", name="Recover your existing account", exact=True)
            dialog.get_by_label("Email address", exact=True).fill(member["email"])
            with first_page.expect_response(posted("/api/users/reset-password-request")) as received:
                dialog.get_by_role("button", name="Email recovery link", exact=True).click()
            require(received.value.status == 200, "The browser recovery request did not succeed")
            link = wait_for_captured_link(state_dir, port, first_page.wait_for_timeout)
            PHASE = "complete_captured_link_in_browser"
            save_password(first_page, link, 200)
            PHASE = "reject_reused_link_in_browser"
            reuse_context = context(browser)
            save_password(page(reuse_context), link, 400)
            reuse_context.close()
            PHASE = "sign_in_and_reload"
            first_headers = login(first_page)
            first_page.reload(wait_until="domcontentloaded")
            first_page.get_by_test_id("logout-btn").wait_for(state="visible")
            saved = first_page.evaluate("() => JSON.parse(localStorage.getItem('cashoutai_user'))")
            require(saved and saved.get("active_session_id") == first_headers["X-Session-ID"],
                    "A page reload lost the valid member session")
            profile = "/api/users/rehearsal-member/profile"
            require(api_get(origin, profile, first_headers)[0] == 200,
                    "The reloaded session cannot read its own profile")
            PHASE = "replace_session_in_second_browser"
            second_context = context(browser)
            second_page = page(second_context)
            second_headers = login(second_page)
            require(second_headers["X-Session-ID"] != first_headers["X-Session-ID"],
                    "The second browser did not receive a new session")
            require(api_get(origin, profile, first_headers)[0] == 401,
                    "The replaced browser session retained access")
            require(api_get(origin, profile, second_headers)[0] == 200,
                    "The newest browser session lost access")
            first_page.wait_for_function("() => localStorage.getItem('cashoutai_user') === null", timeout=25000)
            first_page.get_by_role("button", name="Sign in", exact=True).wait_for(state="visible")
            require(not first_context.service_workers and not second_context.service_workers,
                    "A service worker started during the isolated preview")
            require(counters["page_errors"] == 0, "The compiled frontend raised an uncaught browser error")
        finally:
            browser.close()
    return {"recovery_request_ui": "PASS", "captured_link_ui": "PASS", "token_removed_from_address_bar": "PASS",
            "single_use_link_ui": "PASS", "same_account_login_ui": "PASS", "reload_preserves_session": "PASS",
            "second_browser_replaces_first": "PASS", "stale_browser_returns_to_sign_in": "PASS",
            "external_browser_requests_allowed": 0, "service_workers": "blocked", **counters}


def run(args):
    global PHASE
    require(1024 <= args.mongo_port <= 65535 and 1024 <= args.http_port <= 65535
            and args.mongo_port != args.http_port, "Use different unprivileged local ports")
    build = args.frontend_build.resolve(strict=True)
    require(build.is_dir() and (build / "index.html").is_file(), "The compiled frontend is unavailable")
    origin = f"http://127.0.0.1:{args.http_port}"
    with tempfile.TemporaryDirectory(prefix="cashout_browser_") as directory:
        private_root = Path(directory)
        os.chmod(private_root, 0o700)
        child_output = private_root / "preview-output.jsonl"
        with child_output.open("x", encoding="utf-8") as output:
            os.chmod(child_output, 0o600)
            process = subprocess.Popen([
                sys.executable, str(ROOT / "backend/tests/rehearse_restored_app_recovery.py"),
                "--mode", "serve", "--seed-synthetic", "--database", DATABASE,
                "--mongo-port", str(args.mongo_port), "--http-port", str(args.http_port),
                "--frontend-build", str(build),
            ], cwd=ROOT, stdout=output, stderr=output,
                env={"PATH": os.environ.get("PATH", ""),
                     "TMPDIR": str(private_root), "PYTHONUNBUFFERED": "1"})
            try:
                PHASE = "start_guarded_synthetic_preview"

                def ready():
                    lines = child_output.read_text(encoding="utf-8").splitlines()
                    if not lines:
                        return False
                    metadata = json.loads(lines[0])
                    state = Path(metadata.get("private_state_directory", ""))
                    require(state.is_absolute() and state.parent == private_root and not state.is_symlink(),
                            "The preview state is outside the private test folder")
                    status = private_json(state / "preview-ready.json")
                    require(status.get("origin") == origin, "The preview advertised an unexpected origin")
                    with build_opener(ProxyHandler({})).open(origin + "/", timeout=1) as response:
                        return state if response.status == 200 else False

                state_dir = wait_until(ready, process)
                checks = browser_exercise(origin, args.http_port, state_dir, private_root)
                PHASE = "verify_shutdown_and_preservation"
                stop_preview(process)
                require(process.returncode == 0, "The guarded preview failed its shutdown checks")
                result = private_json(state_dir / "result.json")
                require(result.get("result") == "PREVIEW_STOPPED", "Preview preservation did not pass")
                require(result.get("backup_restore_verified") is False, "Synthetic evidence was mislabeled")
                return {"result": "PASS", "storage": "real_local_MongoDB_8", "data": "synthetic_only",
                        "browser": "Chromium", "checks": checks, "record_preservation": "PASS",
                        "captured_emails": result.get("captured_emails"), "real_emails_sent": 0,
                        "backup_restore_verified": False, "real_member_recovery_verified": False,
                        "production_deployment_verified": False}
            finally:
                stop_preview(process)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-build", type=Path, required=True)
    parser.add_argument("--mongo-port", type=int, default=27217)
    parser.add_argument("--http-port", type=int, default=4185)
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        print(json.dumps(run(args), sort_keys=True))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        # Playwright exceptions may include token URLs and filled passwords.
        # Never print their text, traceback, console, page HTML, or screenshots.
        print(json.dumps({"result": "FAIL", "phase": PHASE, "error_type": type(error).__name__,
                          "reason": str(error) if isinstance(error, BrowserCheckError) else "Private browser check did not complete",
                          "data": "synthetic_only", "real_member_recovery_verified": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
