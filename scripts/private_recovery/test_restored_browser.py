"""Check the compiled recovery UI against an explicitly selected LOCAL copy.

This separate runner is for a previously verified restored database. It never
accepts a managed MongoDB URI, remote app origin, snapshot URL, or production
credential. The existing guarded preview validates the two selected accounts,
captures email locally, and checks preservation before stopping. This script
does not seed, restore, export, or delete any database.

The selection file must be an absolute, owner-only mode-0600 JSON file with
exactly member_id and admin_id. No account details, URLs containing tokens,
passwords, sessions, browser console, HTML, screenshots, or traces are emitted.
Only aggregate results leave the temporary private directory.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import secrets
import signal
import stat
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.parse import parse_qs, quote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
# Only identity-independent primitives are shared. The synthetic runner's
# account restrictions and exercise entry point remain unchanged and unused.
from test_recovery_browser import BrowserCheckError, local_url, require, stop_preview, wait_until


DATABASE_PATTERN = re.compile(r"cashout_rehearsal_[a-z0-9_]{4,48}\Z")
PHASE = "configuration"


class PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, _message):
        # argparse's normal error can repeat unknown arguments and their values.
        raise BrowserCheckError("Invalid private browser configuration")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def private_json(path):
    """Read a bounded, owner-only regular file without following a symlink."""
    require(path.is_absolute() and not path.is_symlink()
            and path.resolve(strict=True) == path,
            "Private input must use an absolute path without symbolic links")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as handle:
        info = os.fstat(handle.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                and stat.S_IMODE(info.st_mode) == 0o600,
                "Private input must be a regular file owned by this user with mode 0600")
        require(info.st_size < 65536, "Private input is unexpectedly large")
        encoded = handle.read(65536)
        require(len(encoded) < 65536, "Private input is unexpectedly large")
        return json.loads(encoded)


def validate_selection(value):
    require(isinstance(value, dict) and set(value) == {"member_id", "admin_id"},
            "Selection must identify exactly one member and one administrator")
    require(all(isinstance(identity, str) and 0 < len(identity) <= 128
                and identity == identity.strip()
                and all(ord(character) >= 32 and ord(character) != 127 for character in identity)
                for identity in value.values()), "The selected account identifiers are invalid")
    require(value["member_id"] != value["admin_id"], "Select two different restored accounts")
    return dict(value)


def validate_configuration(args):
    require(bool(DATABASE_PATTERN.fullmatch(args.database)), "A rehearsal-prefixed database is required")
    require(1024 <= args.mongo_port <= 65535 and 1024 <= args.http_port <= 65535
            and args.mongo_port != args.http_port, "Use different unprivileged local ports")
    selection = validate_selection(private_json(args.selection_file))
    require(args.frontend_build.is_absolute(), "The compiled frontend must use an absolute path")
    build = args.frontend_build.resolve(strict=True)
    require(build.is_dir() and (build / "index.html").is_file(), "The compiled frontend is unavailable")
    return selection, build


def write_private_json(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        os.fchmod(handle.fileno(), 0o600)
        json.dump(value, handle)


def validate_operator_details(details, origin):
    require(isinstance(details, dict) and details.get("origin") == origin,
            "The browser and preview origins differ")
    accounts = details.get("accounts")
    require(isinstance(accounts, dict) and set(accounts) == {"member", "admin"},
            "The preview must describe only the selected accounts")
    for account in accounts.values():
        require(isinstance(account, dict) and set(account) == {"username", "email"}
                and all(isinstance(item, str) and 0 < len(item) <= 512 for item in account.values()),
                "The private account details are invalid")
    require(accounts["member"]["email"].strip().casefold() != accounts["admin"]["email"].strip().casefold(),
            "The selected accounts must have different recovery addresses")
    return dict(accounts["member"])


def api_get(origin, port, path, headers):
    require(local_url(origin, port) and path.startswith("/api/") and not path.startswith("//"),
            "Unexpected local API address")
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(Request(origin + path, headers=headers, method="GET"), timeout=5) as response:
            return response.status
    except HTTPError as error:
        return error.code


@contextmanager
def browser_environment(private_root):
    original = dict(os.environ)
    permitted = {key: original[key] for key in ("PATH", "LD_LIBRARY_PATH", "PLAYWRIGHT_BROWSERS_PATH")
                 if key in original}
    permitted["TMPDIR"] = str(private_root)
    try:
        # This also removes Playwright debug settings before its driver starts.
        os.environ.clear()
        os.environ.update(permitted)
        yield permitted
    finally:
        os.environ.clear()
        os.environ.update(original)


def wait_for_captured_link(state_dir, port, pause, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            captures = private_json(state_dir / "captured-links.json")
        except (FileNotFoundError, json.JSONDecodeError):
            captures = []
        require(isinstance(captures, list) and all(isinstance(entry, dict) for entry in captures),
                "The private email capture has an unexpected structure")
        links = [entry["reset_url"] for entry in captures
                 if entry.get("label") == "member" and entry.get("reset_url")]
        require(len(links) <= 1, "The recovery request captured more than one member link")
        if links:
            link = links[0]
            require(isinstance(link, str) and local_url(link, port),
                    "The captured recovery link is outside the isolated frontend")
            parts = urlsplit(link)
            parameters = parse_qs(parts.query, keep_blank_values=True)
            require(parts.path == "/" and not parts.fragment and set(parameters) == {"reset_token"}
                    and len(parameters["reset_token"]) == 1
                    and bool(re.fullmatch(r"[A-Za-z0-9_-]{32,128}", parameters["reset_token"][0])),
                    "The captured recovery link has an unexpected format")
            return link
        pause(100)
    raise BrowserCheckError("The selected recovery email was not captured within the bounded wait")


def browser_exercise(origin, port, state_dir, private_root, selection):
    from playwright.sync_api import sync_playwright

    member = validate_operator_details(private_json(state_dir / "operator-details.json"), origin)
    member_id = selection["member_id"]
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

    def page(browser_context):
        result = browser_context.new_page()
        result.on("dialog", lambda dialog: dialog.accept())
        result.on("pageerror", lambda _: counters.__setitem__("page_errors", counters["page_errors"] + 1))
        return result

    def posted(path):
        return lambda response: (local_url(response.url, port) and urlsplit(response.url).path == path
                                 and response.request.method == "POST")

    def save_password(target, link, expected_status):
        target.goto(link, wait_until="domcontentloaded")
        dialog = target.get_by_role("dialog", name="Set a new password", exact=True)
        dialog.wait_for(state="visible")
        require("reset_token" not in parse_qs(urlsplit(target.url).query, keep_blank_values=True),
                "The compiled frontend did not remove the recovery token from the address bar")
        dialog.get_by_label("New password", exact=True).fill(password)
        dialog.get_by_label("Confirm new password", exact=True).fill(password)
        with target.expect_response(posted("/api/users/reset-password-confirm")) as received:
            dialog.get_by_role("button", name="Save new password", exact=True).click()
        require(received.value.status == expected_status, "The recovery form returned an unexpected status")
        if expected_status == 200:
            dialog.wait_for(state="hidden")

    def login(target):
        # The profile landing avoids the bot room's practice-ledger creation.
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
        require(isinstance(session, dict) and session.get("id") == member_id
                and session.get("username") == member["username"] and session.get("email") == member["email"]
                and isinstance(session.get("active_session_id"), str) and 0 < len(session["active_session_id"]) <= 240,
                "Browser sign-in did not preserve the selected account identity")
        target.get_by_test_id("logout-btn").wait_for(state="visible")
        saved = target.evaluate("() => JSON.parse(localStorage.getItem('cashoutai_user'))")
        require(isinstance(saved, dict) and saved.get("id") == member_id
                and saved.get("active_session_id") == session["active_session_id"],
                "The compiled frontend did not retain its verified session")
        return {"X-User-ID": member_id, "X-Session-ID": session["active_session_id"]}

    global PHASE
    with browser_environment(private_root) as environment, sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True, env=environment, args=[
            "--disable-background-networking", "--disable-component-update", "--disable-domain-reliability",
            "--disable-sync", "--no-first-run", "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
        ])
        try:
            first_context = context(browser)
            first_page = page(first_context)
            PHASE = "request_selected_recovery_in_browser"
            first_page.goto(origin + "/", wait_until="domcontentloaded")
            first_page.get_by_role("button", name="Recover existing account", exact=True).click()
            dialog = first_page.get_by_role("dialog", name="Recover your existing account", exact=True)
            dialog.get_by_label("Email address", exact=True).fill(member["email"])
            with first_page.expect_response(posted("/api/users/reset-password-request")) as received:
                dialog.get_by_role("button", name="Email recovery link", exact=True).click()
            require(received.value.status == 200, "The browser recovery request did not succeed")
            link = wait_for_captured_link(state_dir, port, first_page.wait_for_timeout)
            PHASE = "complete_selected_link_in_browser"
            save_password(first_page, link, 200)
            PHASE = "reject_reused_link_in_browser"
            reuse_context = context(browser)
            save_password(page(reuse_context), link, 400)
            reuse_context.close()
            PHASE = "sign_in_and_reload_selected_member"
            first_headers = login(first_page)
            first_page.reload(wait_until="domcontentloaded")
            first_page.get_by_test_id("logout-btn").wait_for(state="visible")
            saved = first_page.evaluate("() => JSON.parse(localStorage.getItem('cashoutai_user'))")
            require(isinstance(saved, dict) and saved.get("id") == member_id
                    and saved.get("active_session_id") == first_headers["X-Session-ID"],
                    "A page reload lost the selected member session")
            profile = "/api/users/" + quote(member_id, safe="") + "/profile"
            require(api_get(origin, port, profile, first_headers) == 200,
                    "The reloaded session cannot read its own profile")
            PHASE = "replace_selected_session_in_second_browser"
            second_context = context(browser)
            second_page = page(second_context)
            second_headers = login(second_page)
            require(second_headers["X-Session-ID"] != first_headers["X-Session-ID"],
                    "The second browser did not receive a new session")
            require(api_get(origin, port, profile, first_headers) == 401,
                    "The replaced browser session retained access")
            require(api_get(origin, port, profile, second_headers) == 200,
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
    selection, build = validate_configuration(args)
    origin = f"http://127.0.0.1:{args.http_port}"
    with tempfile.TemporaryDirectory(prefix="cashout_restored_browser_") as directory:
        private_root = Path(directory).resolve()
        os.chmod(private_root, 0o700)
        # Pin the validated selection for this run. The preview cannot observe
        # a later edit to its parent's original selection file.
        selected_file = private_root / "selected-accounts.json"
        write_private_json(selected_file, selection)
        child_output = private_root / "preview-output.jsonl"
        with child_output.open("x", encoding="utf-8") as output:
            os.chmod(child_output, 0o600)
            process = subprocess.Popen([
                sys.executable, str(ROOT / "backend/tests/rehearse_restored_app_recovery.py"),
                "--mode", "serve", "--restored-copy", "--database", args.database,
                "--selection-file", str(selected_file), "--mongo-port", str(args.mongo_port),
                "--http-port", str(args.http_port), "--frontend-build", str(build),
            ], cwd=ROOT, stdout=output, stderr=output,
                env={"PATH": os.environ.get("PATH", ""), "TMPDIR": str(private_root), "PYTHONUNBUFFERED": "1"})
            try:
                PHASE = "start_guarded_restored_preview"

                def ready():
                    lines = child_output.read_text(encoding="utf-8").splitlines()
                    if not lines:
                        return False
                    metadata = json.loads(lines[0])
                    require(isinstance(metadata, dict), "The preview returned invalid readiness metadata")
                    state = Path(metadata.get("private_state_directory", ""))
                    require(state.is_absolute() and state.parent == private_root and not state.is_symlink(),
                            "The preview state is outside the private test folder")
                    status = private_json(state / "preview-ready.json")
                    require(isinstance(status, dict) and status.get("origin") == origin,
                            "The preview advertised an unexpected origin")
                    with build_opener(ProxyHandler({}), NoRedirect()).open(origin + "/", timeout=1) as response:
                        return state if response.status == 200 else False

                state_dir = wait_until(ready, process)
                checks = browser_exercise(origin, args.http_port, state_dir, private_root, selection)
                PHASE = "verify_shutdown_and_record_preservation"
                stop_preview(process)
                require(process.returncode == 0, "The guarded preview failed its shutdown checks")
                result = private_json(state_dir / "result.json")
                require(isinstance(result, dict) and result.get("result") == "PREVIEW_STOPPED",
                        "Preview preservation did not pass")
                require(result.get("backup_restore_verified") is False,
                        "The browser preview cannot attest to backup verification")
                captures = result.get("captured_emails")
                require(type(captures) is int and captures >= 2, "The preview did not capture its recovery emails")
                return {"result": "PASS", "storage": "real_local_MongoDB_8", "data": "restored_copy_only",
                        "browser": "Chromium", "accounts_exercised": 1, "checks": checks,
                        "record_preservation": "PASS", "captured_emails": captures, "real_emails_sent": 0,
                        "external_app_connections": 0, "browser_reset_completed": True,
                        "backup_restore_verified": False, "restored_member_recovery_verified": True,
                        "live_account_recovery_verified": False, "production_deployment_verified": False}
            finally:
                stop_preview(process)


def main(argv=None):
    global PHASE
    PHASE = "configuration"
    try:
        parser = PrivateArgumentParser(description=__doc__)
        parser.add_argument("--frontend-build", type=Path, required=True)
        parser.add_argument("--database", required=True)
        parser.add_argument("--selection-file", type=Path, required=True)
        parser.add_argument("--mongo-port", type=int, default=27217)
        parser.add_argument("--http-port", type=int, default=4185)
        args = parser.parse_args(argv)
        signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
        result = run(args)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (Exception, KeyboardInterrupt) as error:
        # Driver/server exceptions can contain member details and token URLs.
        print(json.dumps({"result": "FAIL", "phase": PHASE, "error_type": type(error).__name__,
                          "reason": str(error) if isinstance(error, BrowserCheckError) else "Private browser check did not complete",
                          "data": "restored_copy_only", "restored_member_recovery_verified": False,
                          "live_account_recovery_verified": False, "production_deployment_verified": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
