"""Small no-network checks for the synthetic runner's refusal boundary."""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import run_synthetic_preflight as preflight


class PreflightContractTests(unittest.TestCase):
    def test_existing_pretty_printed_rehearsal_output_is_parsed(self):
        metadata = json.dumps({"private_state_directory": "/private/fixture"})
        result = {"result": "PASS", "real_emails_sent": 0, "backup_restore_verified": False}
        raw = (metadata + "\n" + json.dumps(result, indent=2) + "\n").encode()
        self.assertEqual(preflight.last_json_result(raw), result)

    def test_browser_single_object_is_parsed(self):
        self.assertEqual(preflight.last_json_result(b'{"result":"PASS"}\n'), {"result": "PASS"})

    def test_unexpected_child_logs_fail_without_forwarding_them(self):
        with self.assertRaises(ValueError):
            preflight.last_json_result(b"private-token-marker\n")
        with self.assertRaises(preflight.PreflightError):
            preflight.last_json_result(b"{} {} {}")

    def test_preflight_refuses_snapshot_configuration(self):
        with patch.object(preflight.sys, "argv", ["run_synthetic_preflight.py"]):
            with patch.dict(os.environ, {"CASHOUT_SNAPSHOT_URL": "private-url-marker"}, clear=True):
                with self.assertRaisesRegex(preflight.PreflightError, "^snapshot_configuration_forbidden_in_preflight$"):
                    preflight.run()

    def test_preflight_refuses_arguments(self):
        with patch.object(preflight.sys, "argv", ["run_synthetic_preflight.py", "--remote"]):
            with self.assertRaisesRegex(preflight.PreflightError, "^preflight_arguments_forbidden$"):
                preflight.run()

    def test_child_environment_never_inherits_credentials_or_overrides_home(self):
        with patch.dict(os.environ, {"MONGO_URL": "private-db-marker", "RENDER_API_KEY": "private-key-marker"}):
            result = preflight.child_environment(Path("/tmp/private-test"))
        self.assertFalse({"MONGO_URL", "RENDER_API_KEY", "HOME"} & set(result))


if __name__ == "__main__":
    unittest.main()
