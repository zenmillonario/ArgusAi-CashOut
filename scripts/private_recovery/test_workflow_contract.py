"""No-network tests of SDK metadata and the boundary around retained results."""
from contextlib import redirect_stderr, redirect_stdout
import copy
import inspect
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

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


def failed_result(reason="INSUFFICIENT_PRIVATE_DISK", stage="restored_rehearsal"):
    return {"schema": "cashout_private_recovery_v1", "result": "FAIL",
            "stage": stage, "reason": reason}


def successful_storage_result():
    return {"schema": "cashout_private_storage_v1", "result": "PASS", "mode": "metadata_only",
            "network_attempts": 0, "snapshot_data_accessed": False, "probe_cleanup_verified": True,
            "candidates": [{"label": label, "available": True, "writable": True,
                            "total_bytes": 1024, "free_bytes": 512, "total_inodes": 100, "free_inodes": 50,
                            "same_filesystem_as_default": True, "filesystem_type": "other"}
                           for label in ("default", "tmp", "var_tmp", "home")]}


class WorkflowContractTests(unittest.TestCase):
    def test_current_sdk_registers_only_three_bounded_inputless_tasks(self):
        self.assertEqual(set(workflow.app._registry.get_task_names()),
                         {"synthetic_preflight", "rehearse_restored_copy", "inspect_private_storage"})
        for name in workflow.app._registry.get_task_names():
            info = workflow.app._registry.get_task(name)
            self.assertEqual(info.parameters, [])
            self.assertEqual(list(inspect.signature(info.func).parameters), ["ctx"])
            self.assertEqual(info.options.plan, "2c-4g")
            self.assertEqual(info.options.timeout_seconds, 30 if name == "inspect_private_storage" else 1800)
            self.assertEqual(info.options.retry.max_retries, 0)

    def test_tasks_do_not_chain_or_supply_arguments(self):
        with patch.object(workflow, "safe_run", return_value={"result": "PASS"}) as run:
            workflow.synthetic_preflight.func(object())
            run.assert_called_once_with("synthetic_only")
        with patch.object(workflow, "safe_run", return_value={"result": "PASS"}) as run:
            workflow.rehearse_restored_copy.func(object())
            run.assert_called_once_with("restored_snapshot")
        with patch.object(workflow, "safe_storage_probe", return_value={"result": "PASS"}) as run:
            workflow.inspect_private_storage.func(object())
            run.assert_called_once_with()

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

    def test_reviewed_failure_reasons_preserve_only_known_stage_and_reason(self):
        for stage, reason in (
            ("configuration", "EXACTLY_ONE_SNAPSHOT_IDENTITY_REQUIRED"),
            ("configuration", "INVALID_SNAPSHOT_ARCHIVE_NAME"),
            ("configuration", "SNAPSHOT_ARCHIVE_URL_MISMATCH"),
            ("configuration", "PRIVATE_PARENT_DIRECTORY_REFUSED"),
            ("restored_rehearsal", "INSUFFICIENT_PRIVATE_DISK"),
            ("restored_rehearsal", "INSUFFICIENT_PRIVATE_EXPANSION_DISK"),
            ("restored_rehearsal", "SNAPSHOT_DOWNLOAD_HTTP_FAILED"),
            ("restored_rehearsal", "SOURCE_FCV_REFUSED"),
            ("restored_rehearsal", "ELIGIBLE_RESTORED_ACCOUNTS_UNAVAILABLE"),
        ):
            with self.subTest(stage=stage, reason=reason):
                raw = json.dumps(failed_result(reason, stage)).encode()
                self.assertEqual(workflow.restored_failure_code(raw),
                                 f"private_runner_failed:{stage}:{reason}")

    def test_failure_schema_rejects_unknown_extra_and_leaky_values(self):
        mutations = (
            {"reason": "NEW_UNREVIEWED_REFUSAL"},
            {"reason": "INSUFFICIENT_PRIVATE_DISK https://private.invalid/token"},
            {"reason": ["INSUFFICIENT_PRIVATE_DISK"]},
            {"stage": "download https://private.invalid/token"},
            {"stage": False}, {"result": "PASS"}, {"schema": "other_schema"},
            {"snapshot_url": "https://private.invalid/token"},
            {"details": "private-account-marker"},
        )
        for mutation in mutations:
            value = failed_result()
            value.update(mutation)
            with self.subTest(field=next(iter(mutation))):
                self.assertEqual(workflow.restored_failure_code(json.dumps(value).encode()),
                                 "private_runner_failed")
        for key in failed_result():
            value = failed_result()
            del value[key]
            self.assertEqual(workflow.restored_failure_code(json.dumps(value).encode()),
                             "private_runner_failed")

    def test_failure_bytes_reject_malformed_duplicate_extra_and_oversized_output(self):
        valid = json.dumps(failed_result()).encode()
        duplicate = valid[:-1] + b', "reason": "INSUFFICIENT_PRIVATE_DISK"}'
        for raw in (
            b"", b"\xff", b"[]", b"null", b"true", b"\"private-token-marker\"",
            b"private-token-marker\n" + valid, valid + b"\nprivate-token-marker",
            valid + valid, duplicate,
            valid + b" " * workflow.MAX_FAILURE_BYTES,
        ):
            self.assertEqual(workflow.restored_failure_code(raw), "private_runner_failed")
        self.assertEqual(workflow.restored_failure_code(valid.decode()), "private_runner_failed")

    def test_nonzero_exit_remains_failed_and_never_emits_child_output(self):
        valid = json.dumps(failed_result()).encode()
        for mode, raw, expected in (
            ("restored_snapshot", valid,
             "private_runner_failed:restored_rehearsal:INSUFFICIENT_PRIVATE_DISK"),
            ("restored_snapshot", valid + b"\nprivate-token-marker", "private_runner_failed"),
            ("restored_snapshot", b"private-token-marker" * workflow.MAX_FAILURE_BYTES,
             "private_runner_failed"),
            ("synthetic_only", valid, "private_runner_failed"),
        ):
            process = Mock(returncode=1)
            process.poll.return_value = 1

            def failed_child(*args, **kwargs):
                kwargs["stdout"].write(raw)
                kwargs["stderr"].write(b"private-stderr-marker https://private.invalid/token")
                return process

            public_stdout, public_stderr = io.StringIO(), io.StringIO()
            with self.subTest(mode=mode, expected=expected), \
                    patch.object(workflow, "APP_PYTHON", Path(sys.executable)), \
                    patch.object(workflow, "child_environment", return_value={}), \
                    patch.object(workflow.subprocess, "Popen", side_effect=failed_child) as launch, \
                    redirect_stdout(public_stdout), redirect_stderr(public_stderr):
                with self.assertRaises(workflow.PrivateTaskError) as caught:
                    workflow.safe_run(mode)
                self.assertEqual(str(caught.exception), expected)
                self.assertTrue(caught.exception.__suppress_context__)
                launch.assert_called_once()
            self.assertEqual(public_stdout.getvalue(), "")
            self.assertEqual(public_stderr.getvalue(), "")

    def test_unexpected_exceptions_never_forward_sensitive_text(self):
        with patch.object(workflow, "run_private", side_effect=ValueError("private-token-marker")):
            with self.assertRaisesRegex(workflow.PrivateTaskError, "^private_runtime_interrupted$") as caught:
                workflow.safe_run("synthetic_only")
        self.assertNotIn("private-token-marker", str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)

    def test_storage_child_environment_is_explicit_and_excludes_all_inherited_secrets(self):
        source = {"CASHOUT_SNAPSHOT_URL": "private-marker", "RENDER_API_KEY": "private-marker",
                  "MONGO_URL": "private-marker", "TMPDIR": "/untrusted"}
        with patch.dict(os.environ, source, clear=True):
            result = workflow.storage_environment(Path("/tmp/actual-wrapper-parent"))
        self.assertEqual(set(result), {"PATH", "LANG", "TZ", "PYTHONUNBUFFERED", "PYTHONDONTWRITEBYTECODE", "TMPDIR"})
        self.assertEqual(result["TMPDIR"], "/tmp/actual-wrapper-parent")
        self.assertNotIn("private-marker", repr(result))

    def test_storage_aggregate_rejects_paths_unknown_keys_false_cleanup_and_bad_numbers(self):
        valid = successful_storage_result()
        self.assertEqual(workflow.aggregate_storage_result(valid), valid)
        mutations = []
        for changes in ({"path": "/private/token"}, {"network_attempts": 1},
                        {"snapshot_data_accessed": True}, {"probe_cleanup_verified": False}):
            value = copy.deepcopy(valid)
            value.update(changes)
            mutations.append(value)
        for changes in ({"label": "/private/token"}, {"filesystem_type": "private-token-marker"},
                        {"free_bytes": "private-marker"}, {"free_bytes": True}, {"free_bytes": -1},
                        {"total_bytes": workflow.MAX_STORAGE_NUMBER + 1}, {"free_bytes": 2048},
                        {"free_inodes": 101}, {"writable": 1}, {"available": False}, {"path": "/private/token"}):
            value = copy.deepcopy(valid)
            value["candidates"][0].update(changes)
            mutations.append(value)
        for value in mutations:
            with self.assertRaisesRegex(workflow.PrivateTaskError, "^invalid_storage_result$"):
                workflow.aggregate_storage_result(value)

    def test_storage_parser_rejects_duplicate_keys_extra_text_and_oversized_output(self):
        valid = json.dumps(successful_storage_result()).encode()
        self.assertEqual(workflow.parse_storage_result(valid), successful_storage_result())
        for raw in (b"\xff", b"[]", valid + b"\nprivate-marker", valid + valid,
                    valid[:-1] + b', "result": "PASS"}',
                    valid + b" " * workflow.MAX_STORAGE_OUTPUT_BYTES):
            with self.assertRaisesRegex(workflow.PrivateTaskError, "^invalid_storage_result$"):
                workflow.parse_storage_result(raw)

    def test_storage_wrapper_passes_actual_default_filesystem_and_removes_private_root(self):
        seen = []
        process = Mock(returncode=0)
        process.poll.return_value = 0
        process.wait.return_value = 0
        def completed_child(*args, **kwargs):
            actual = Path(kwargs["env"]["TMPDIR"])
            self.assertEqual(actual.parent, base)
            self.assertTrue(actual.name.startswith("cashout_workflow_storage_"))
            self.assertTrue(actual.is_dir())
            self.assertTrue(set(workflow.SNAPSHOT_ENV).isdisjoint(kwargs["env"]))
            self.assertNotIn("RENDER_API_KEY", kwargs["env"])
            self.assertEqual(len(args[0]), 2)
            seen.append(actual)
            kwargs["stdout"].write(json.dumps(successful_storage_result()).encode())
            kwargs["stdout"].flush()
            return process
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            with patch.object(workflow, "APP_PYTHON", Path(sys.executable)), \
                    patch.object(workflow.tempfile, "tempdir", str(base)), \
                    patch.dict(os.environ, {"CASHOUT_SNAPSHOT_URL": "private-marker", "RENDER_API_KEY": "private-marker"}), \
                    patch.object(workflow.subprocess, "Popen", side_effect=completed_child):
                self.assertEqual(workflow.safe_storage_probe(), successful_storage_result())
            self.assertEqual(len(seen), 1)
            self.assertFalse(seen[0].exists())
            self.assertEqual(list(base.iterdir()), [])
            process.wait.assert_called_once_with(timeout=20)

    def test_storage_nonzero_output_and_stderr_remain_private(self):
        for exit_code, stdout, stderr, expected in (
            (1, b"private-stdout-marker", b"private-stderr-marker", "private_storage_probe_failed"),
            (0, json.dumps(successful_storage_result()).encode(), b"private-stderr-marker", "private_storage_output_refused"),
            (0, b"x" * (workflow.MAX_STORAGE_OUTPUT_BYTES + 1), b"", "private_storage_output_refused"),
        ):
            process = Mock(returncode=exit_code)
            process.poll.return_value = exit_code
            def child(*args, **kwargs):
                kwargs["stdout"].write(stdout)
                kwargs["stderr"].write(stderr)
                kwargs["stdout"].flush()
                kwargs["stderr"].flush()
                return process
            public_stdout, public_stderr = io.StringIO(), io.StringIO()
            with patch.object(workflow, "APP_PYTHON", Path(sys.executable)), \
                    patch.object(workflow.subprocess, "Popen", side_effect=child), \
                    redirect_stdout(public_stdout), redirect_stderr(public_stderr):
                with self.assertRaises(workflow.PrivateTaskError) as caught:
                    workflow.safe_storage_probe()
                self.assertEqual(str(caught.exception), expected)
                self.assertTrue(caught.exception.__suppress_context__)
            self.assertEqual(public_stdout.getvalue(), "")
            self.assertEqual(public_stderr.getvalue(), "")

    def test_storage_timeout_stops_child_and_does_not_expose_exception_text(self):
        process = Mock()
        process.wait.side_effect = workflow.subprocess.TimeoutExpired("private-command-marker", 20)
        with patch.object(workflow, "APP_PYTHON", Path(sys.executable)), \
                patch.object(workflow.subprocess, "Popen", return_value=process), \
                patch.object(workflow, "stop_storage_child") as stop:
            with self.assertRaisesRegex(workflow.PrivateTaskError, "^private_storage_probe_timeout$"):
                workflow.safe_storage_probe()
            stop.assert_called_once_with(process)


if __name__ == "__main__":
    unittest.main()
