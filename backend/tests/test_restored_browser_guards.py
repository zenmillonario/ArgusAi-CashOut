"""Private browser refusal, output privacy and cleanup tests; no database or browser."""
import argparse
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "private_restored_browser", ROOT / "scripts/private_recovery/test_restored_browser.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class RestoredBrowserGuardsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.selection = {"member_id": "copied-member", "admin_id": "copied-admin"}
        self.selected_file = self.root / "selected.json"
        runner.write_private_json(self.selected_file, self.selection)
        self.build = self.root / "build"
        self.build.mkdir()
        (self.build / "index.html").write_text("<!doctype html>", encoding="utf-8")
        self.args = argparse.Namespace(database="cashout_rehearsal_guard_browser", mongo_port=27217,
                                       http_port=4185, frontend_build=self.build,
                                       selection_file=self.selected_file)

    def test_private_selection_requires_exactly_two_distinct_identifiers(self):
        self.assertEqual(runner.validate_selection(self.selection), self.selection)
        invalid = [None, {}, {**self.selection, "uri": "unused"}, {"member_id": "same", "admin_id": "same"},
                   {"member_id": 12, "admin_id": "admin"}, {"member_id": "", "admin_id": "admin"},
                   {"member_id": " member", "admin_id": "admin"}, {"member_id": "x\ny", "admin_id": "admin"},
                   {"member_id": "x" * 129, "admin_id": "admin"}]
        for value in invalid:
            with self.subTest(case=type(value).__name__), self.assertRaises(runner.BrowserCheckError):
                runner.validate_selection(value)

    def test_private_json_checks_mode_owner_regular_file_and_size(self):
        self.assertEqual(runner.private_json(self.selected_file), self.selection)
        self.selected_file.chmod(0o644)
        with self.assertRaises(runner.BrowserCheckError):
            runner.private_json(self.selected_file)
        self.selected_file.chmod(0o600)
        with mock.patch.object(runner.os, "getuid", return_value=os.getuid() + 1):
            with self.assertRaises(runner.BrowserCheckError):
                runner.private_json(self.selected_file)
        with self.assertRaises((runner.BrowserCheckError, IsADirectoryError)):
            runner.private_json(self.root)
        self.selected_file.write_bytes(b" " * 65536)
        with self.assertRaises(runner.BrowserCheckError):
            runner.private_json(self.selected_file)

    def test_private_json_rejects_relative_paths_and_all_symlink_components(self):
        with self.assertRaises(runner.BrowserCheckError):
            runner.private_json(Path("selected.json"))
        linked_file = self.root / "linked.json"
        linked_file.symlink_to(self.selected_file)
        with self.assertRaises(runner.BrowserCheckError):
            runner.private_json(linked_file)
        linked_directory = self.root / "linked-directory"
        linked_directory.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(runner.BrowserCheckError):
            runner.private_json(linked_directory / self.selected_file.name)

    def test_configuration_refuses_source_database_remote_uri_and_bad_ports(self):
        selection, build = runner.validate_configuration(self.args)
        self.assertEqual(selection, self.selection)
        self.assertEqual(build, self.build)
        for database in ("cashoutai", "mongodb://127.0.0.1/cashoutai", "cashout_rehearsal_X", "cashout_rehearsal_okay\n"):
            with self.subTest(database=database), self.assertRaises(runner.BrowserCheckError):
                runner.validate_configuration(argparse.Namespace(**{**vars(self.args), "database": database}))
        for ports in ((80, 4185), (27217, 65536), (4185, 4185)):
            with self.subTest(ports=ports), self.assertRaises(runner.BrowserCheckError):
                runner.validate_configuration(argparse.Namespace(**{**vars(self.args), "mongo_port": ports[0],
                                                                    "http_port": ports[1]}))

    def test_operator_details_bind_the_selected_preview_origin_and_accounts(self):
        origin = "http://127.0.0.1:4185"
        details = {"origin": origin, "accounts": {
            "member": {"username": "copied_member", "email": "member@example.test"},
            "admin": {"username": "copied_admin", "email": "admin@example.test"}}}
        self.assertEqual(runner.validate_operator_details(details, origin), details["accounts"]["member"])
        with self.assertRaises(runner.BrowserCheckError):
            runner.validate_operator_details(details, "https://example.test")
        details["accounts"]["admin"]["email"] = " MEMBER@EXAMPLE.TEST "
        with self.assertRaises(runner.BrowserCheckError):
            runner.validate_operator_details(details, origin)
        details["accounts"]["admin"]["email"] = "admin@example.test"
        details["accounts"]["member"]["active_session_id"] = "must-not-be-loaded"
        with self.assertRaises(runner.BrowserCheckError):
            runner.validate_operator_details(details, origin)

    def test_capture_wait_handles_async_creation_and_partial_write(self):
        captured = self.root / "captured-links.json"
        link = "http://127.0.0.1:4185/?reset_token=" + "x" * 43
        pauses = []

        def pause(milliseconds):
            pauses.append(milliseconds)
            if len(pauses) == 1:
                captured.write_text("[", encoding="utf-8")
                captured.chmod(0o600)
            else:
                captured.write_text(json.dumps([{"label": "member", "reset_url": link}]), encoding="utf-8")

        self.assertEqual(runner.wait_for_captured_link(self.root, 4185, pause), link)
        self.assertEqual(pauses, [100, 100])

    def test_capture_wait_refuses_remote_ambiguous_or_malformed_links(self):
        token = "x" * 43
        links = [f"https://example.test/?reset_token={token}", f"http://localhost:4185/?reset_token={token}",
                 f"http://127.0.0.1:4186/?reset_token={token}", f"http://user@127.0.0.1:4185/?reset_token={token}",
                 f"http://127.0.0.1:4185/other?reset_token={token}", f"http://127.0.0.1:4185/?reset_token={token}#x",
                 f"http://127.0.0.1:4185/?reset_token={token}&other=x",
                 f"http://127.0.0.1:4185/?reset_token={token}&reset_token={token}",
                 "http://127.0.0.1:4185/?reset_token=short"]
        captured = self.root / "captured-links.json"
        for index, link in enumerate(links):
            captured.write_text(json.dumps([{"label": "member", "reset_url": link}]), encoding="utf-8")
            captured.chmod(0o600)
            with self.subTest(case=index), self.assertRaises(runner.BrowserCheckError):
                runner.wait_for_captured_link(self.root, 4185, lambda _: self.fail("Invalid link waited"))
        captured.write_text(json.dumps([{"label": "member", "reset_url": links[0]}] * 2), encoding="utf-8")
        with self.assertRaises(runner.BrowserCheckError):
            runner.wait_for_captured_link(self.root, 4185, lambda _: self.fail("Duplicate link waited"))

    def test_capture_wait_has_a_fixed_bounded_failure(self):
        with self.assertRaisesRegex(runner.BrowserCheckError, "bounded wait"):
            runner.wait_for_captured_link(self.root, 4185, lambda _: self.fail("No wait permitted"), timeout=0)

    def test_browser_environment_strips_secrets_and_debug_and_restores_parent(self):
        original = {"PATH": "/test/path", "MONGO_URL": "unused-secret", "DEBUG": "pw:api", "PWDEBUG": "1",
                    "RESEND_API_KEY": "unused-secret", "PLAYWRIGHT_BROWSERS_PATH": "/test/browsers"}
        with mock.patch.dict(os.environ, original, clear=True):
            with runner.browser_environment(self.root) as environment:
                self.assertEqual(dict(os.environ), {"PATH": "/test/path", "PLAYWRIGHT_BROWSERS_PATH": "/test/browsers",
                                                   "TMPDIR": str(self.root)})
                self.assertEqual(environment, dict(os.environ))
            self.assertEqual(dict(os.environ), original)

    def test_local_api_disables_redirects_and_refuses_remote_addresses(self):
        with mock.patch.object(runner, "build_opener") as opener:
            for origin, path in (("https://example.test", "/api/users/x/profile"),
                                 ("http://127.0.0.1:4185", "//example.test/x"),
                                 ("http://127.0.0.1:4185", "/login")):
                with self.assertRaises(runner.BrowserCheckError):
                    runner.api_get(origin, 4185, path, {})
            opener.assert_not_called()
        self.assertIsNone(runner.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.test"))

    def test_preview_failure_stops_process_removes_private_state_and_never_seeds(self):
        state = {}

        class Process:
            returncode = None

            def poll(self):
                return self.returncode

            def terminate(self):
                state["terminated"] = True
                self.returncode = 0

            def wait(self, timeout):
                return self.returncode

        def start(command, **kwargs):
            state.update(command=command, environment=kwargs["env"], private_root=Path(kwargs["env"]["TMPDIR"]))
            selection_file = Path(command[command.index("--selection-file") + 1])
            self.assertNotEqual(selection_file, self.selected_file)
            self.assertEqual(runner.private_json(selection_file), self.selection)
            self.assertEqual(selection_file.parent.stat().st_mode & 0o777, 0o700)
            self.assertIs(kwargs["stdout"], kwargs["stderr"])
            self.assertEqual(os.fstat(kwargs["stdout"].fileno()).st_mode & 0o777, 0o600)
            return Process()

        with mock.patch.object(runner.subprocess, "Popen", side_effect=start), \
             mock.patch.object(runner, "wait_until", side_effect=runner.BrowserCheckError("Preview unavailable")), \
             mock.patch.dict(os.environ, {"MONGO_URL": "unused-secret", "RESEND_API_KEY": "unused-secret"}):
            with self.assertRaisesRegex(runner.BrowserCheckError, "Preview unavailable"):
                runner.run(self.args)
        self.assertIn("--restored-copy", state["command"])
        self.assertNotIn("--seed-synthetic", state["command"])
        self.assertEqual(set(state["environment"]), {"PATH", "TMPDIR", "PYTHONUNBUFFERED"})
        self.assertTrue(state["terminated"])
        self.assertFalse(state["private_root"].exists())
        self.assertTrue(self.selected_file.exists())

    def test_argument_errors_and_driver_failures_never_echo_private_values(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(runner.main(["--managed-uri", "private-input-sentinel"]), 1)
        failure = json.loads(output.getvalue())
        self.assertNotIn("private-input-sentinel", output.getvalue())
        self.assertEqual(failure["reason"], "Invalid private browser configuration")
        self.assertFalse(failure["restored_member_recovery_verified"])
        output = io.StringIO()
        argv = ["--database", self.args.database, "--frontend-build", str(self.build),
                "--selection-file", str(self.selected_file)]
        with mock.patch.object(runner.signal, "signal"), \
             mock.patch.object(runner, "run", side_effect=RuntimeError("private-token-session-sentinel")), \
             redirect_stdout(output):
            self.assertEqual(runner.main(argv), 1)
        self.assertNotIn("private-token-session-sentinel", output.getvalue())
        self.assertNotIn(str(self.selected_file), output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["reason"], "Private browser check did not complete")


if __name__ == "__main__":
    unittest.main()
