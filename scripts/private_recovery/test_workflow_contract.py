"""No-network tests of SDK metadata and the boundary around retained results."""
import inspect
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import workflow


def successful_result(mode="synthetic_only"):
    result = {
        "schema": "cashout_private_recovery_v1", "result": "PASS", "mode": mode,
        "mongo_version": "8.0.38", "source_fcv": "8.0", "accounts_exercised": 2,
        "browser_accounts_exercised": 1, "captured_emails": 3, "real_emails_sent": 0,
        "external_app_connections": 0, "record_preservation": "PASS",
        "backup_restore_verified": False,
        "real_member_recovery_verified": mode == "restored_snapshot",
        "production_deployment_verified": False,
    }
    if mode == "restored_snapshot":
        result.update(source_identity="operator_selected_snapshot",
                      archive_checksum="computed_after_https_download",
                      local_snapshot_restore="PASS", logical_copy_verified=True,
                      archive_sha256="a" * 64, source_documents=10, source_collections=3)
    return result


class WorkflowContractTests(unittest.TestCase):
    def test_current_sdk_registers_only_two_bounded_inputless_tasks(self):
        self.assertEqual(set(workflow.app._registry.get_task_names()),
                         {"synthetic_preflight", "rehearse_restored_copy"})
        for name in workflow.app._registry.get_task_names():
            info = workflow.app._registry.get_task(name)
            self.assertEqual(info.parameters, [])
            self.assertEqual(list(inspect.signature(info.func).parameters), ["ctx"])
            self.assertEqual(info.options.plan, "2c-4g")
            self.assertEqual(info.options.timeout_seconds, 1800)
            self.assertEqual(info.options.retry.max_retries, 0)

    def test_tasks_do_not_chain_or_supply_arguments(self):
        with patch.object(workflow, "safe_run", return_value={"result": "PASS"}) as run:
            workflow.synthetic_preflight.func(object())
            run.assert_called_once_with("synthetic_only")
        with patch.object(workflow, "safe_run", return_value={"result": "PASS"}) as run:
            workflow.rehearse_restored_copy.func(object())
            run.assert_called_once_with("restored_snapshot")

    def test_snapshot_and_provider_secrets_are_excluded_from_synthetic_child(self):
        source = {"CASHOUT_SNAPSHOT_URL": "private-snapshot-marker",
                  "CASHOUT_SNAPSHOT_DECLARATION_JSON": "private-declaration-marker",
                  "CASHOUT_REHEARSAL_MODE": "atlas_native_snapshot_v1",
                  "RENDER_API_KEY": "private-render-marker", "MONGO_URL": "private-atlas-marker"}
        with patch.dict(os.environ, source, clear=True):
            environment = workflow.child_environment("synthetic_only", Path("/tmp/private-test"))
        self.assertTrue(set(source).isdisjoint(environment))
        self.assertNotIn("HOME", environment)

    def test_only_snapshot_inputs_are_forwarded_to_restored_child(self):
        source = {name: "private-fixture" for name in workflow.SNAPSHOT_ENV}
        source["CASHOUT_REHEARSAL_MODE"] = "atlas_native_snapshot_v1"
        source["RENDER_API_KEY"] = "private-render-marker"
        with patch.dict(os.environ, source, clear=True):
            environment = workflow.child_environment("restored_snapshot", Path("/tmp/private-test"))
        for name in workflow.SNAPSHOT_ENV:
            self.assertEqual(environment[name], source[name])
        self.assertNotIn("RENDER_API_KEY", environment)

    def test_missing_snapshot_configuration_refuses_before_subprocess(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(workflow.PrivateTaskError, "^missing_snapshot_configuration$"):
                workflow.child_environment("restored_snapshot", Path("/tmp/private-test"))

    def test_successful_fixed_aggregates_are_accepted(self):
        for mode in ("synthetic_only", "restored_snapshot"):
            result = successful_result(mode)
            self.assertEqual(workflow.aggregate_result(result, mode), result)

    def test_free_text_unknown_fields_and_false_success_are_rejected(self):
        mutations = [
            {"email": "private-account-marker"}, {"record_preservation": "failed: private-marker"},
            {"real_emails_sent": 1}, {"external_app_connections": 1},
            {"backup_restore_verified": True}, {"accounts_exercised": True},
            {"captured_emails": "private-marker"}, {"captured_emails": -1},
            {"captured_emails": 0}, {"production_deployment_verified": True},
        ]
        for mutation in mutations:
            with self.subTest(field=next(iter(mutation))):
                result = successful_result()
                result.update(mutation)
                with self.assertRaises(workflow.PrivateTaskError):
                    workflow.aggregate_result(result, "synthetic_only")

    def test_restored_hash_must_be_digest_and_counts_must_exist(self):
        for mutation in ({"archive_sha256": "https://private.invalid/token"},
                         {"source_documents": 0}, {"source_collections": True}):
            result = successful_result("restored_snapshot")
            result.update(mutation)
            with self.assertRaises(workflow.PrivateTaskError):
                workflow.aggregate_result(result, "restored_snapshot")

    def test_unexpected_exceptions_never_forward_sensitive_text(self):
        with patch.object(workflow, "run_private", side_effect=ValueError("private-token-marker")):
            with self.assertRaisesRegex(workflow.PrivateTaskError, "^private_runtime_interrupted$") as caught:
                workflow.safe_run("synthetic_only")
        self.assertNotIn("private-token-marker", str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)


if __name__ == "__main__":
    unittest.main()
