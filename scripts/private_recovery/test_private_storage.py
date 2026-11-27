"""Local metadata-only tests; no provider calls or snapshot inputs."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import mock_open, patch

import inspect_private_storage as probe


def environment(parent):
    return {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "TZ": "UTC", "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1", "TMPDIR": str(parent)}


class PrivateStorageTests(unittest.TestCase):
    def test_parent_directory_must_be_private_owned_resolved_and_explicit(self):
        with tempfile.TemporaryDirectory(prefix="cashout_workflow_storage_") as temporary:
            parent = Path(temporary).resolve()
            self.assertEqual(probe.default_root(environment(parent)), parent)
            for changes in ({"TMPDIR": "/tmp"}, {"TMPDIR": "relative"},
                            {"CASHOUT_SNAPSHOT_URL": "private-token-marker"}):
                with self.assertRaises(probe.ProbeRefusal):
                    probe.default_root({**environment(parent), **changes})
            os.chmod(parent, 0o755)
            with self.assertRaises(probe.ProbeRefusal):
                probe.default_root(environment(parent))
            os.chmod(parent, 0o700)

    def test_mount_metadata_is_bounded_and_types_are_fixed_enums(self):
        raw = (b"1 0 0:1 / / rw - overlay overlay rw\n"
               b"2 1 0:2 / /tmp rw - tmpfs tmpfs rw\n"
               b"3 1 0:3 / /private\\040mount rw - private-token-marker source rw\n")
        opened = mock_open(read_data=raw)
        with patch("builtins.open", opened):
            mounts = probe.read_mount_types()
        opened.assert_called_once_with("/proc/self/mountinfo", "rb")
        opened().read.assert_called_once_with(probe.MAX_MOUNT_BYTES + 1)
        self.assertEqual(probe.filesystem_type(Path("/tmp/child"), mounts), "tmpfs")
        self.assertEqual(probe.filesystem_type(Path("/other/child"), mounts), "overlay")
        self.assertEqual(probe.filesystem_type(Path("/private mount/child"), mounts), "other")
        self.assertNotIn("private-token-marker", repr(mounts))

    def test_missing_or_oversized_mount_metadata_is_unknown(self):
        with patch("builtins.open", side_effect=PermissionError("private-marker")):
            self.assertEqual(probe.read_mount_types(), [])
        with patch("builtins.open", mock_open(read_data=b"x" * (probe.MAX_MOUNT_BYTES + 1))):
            self.assertEqual(probe.read_mount_types(), [])
        self.assertEqual(probe.filesystem_type(Path("/tmp"), []), "unknown")

    def test_candidate_reports_actual_filesystem_metadata_and_removes_empty_probe(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            before = list(parent.iterdir())
            row = probe.candidate("default", parent, parent.stat().st_dev, [(Path("/"), "other")])
            usage = os.statvfs(parent)
            self.assertTrue(row["available"])
            self.assertTrue(row["writable"])
            self.assertTrue(row["same_filesystem_as_default"])
            self.assertEqual(row["total_bytes"], usage.f_blocks * usage.f_frsize)
            self.assertEqual(row["total_inodes"], usage.f_files)
            self.assertEqual(list(parent.iterdir()), before)
            self.assertNotIn(str(parent), json.dumps(row))

    def test_unavailable_candidate_has_only_zero_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            row = probe.candidate("home", Path(temporary) / "absent", -1, [])
        self.assertFalse(row["available"])
        self.assertFalse(row["writable"])
        self.assertFalse(row["same_filesystem_as_default"])
        self.assertEqual(row["filesystem_type"], "unknown")
        for key in ("total_bytes", "free_bytes", "total_inodes", "free_inodes"):
            self.assertEqual(row[key], 0)

    def test_unwritable_candidate_does_not_claim_successful_write(self):
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(probe.tempfile, "mkdtemp", side_effect=PermissionError("private-marker")):
            self.assertFalse(probe.probe_writable(Path(temporary)))
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_interrupted_probe_still_removes_its_empty_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            with patch.object(probe, "require", side_effect=probe.ProbeRefusal):
                with self.assertRaises(probe.ProbeRefusal):
                    probe.probe_writable(parent)
            self.assertEqual(list(parent.iterdir()), [])

    def test_signal_pending_during_creation_runs_after_path_is_recorded_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            def change_mask(operation, signals):
                if operation == probe.signal.SIG_BLOCK:
                    self.assertEqual(signals, {probe.signal.SIGALRM, probe.signal.SIGTERM, probe.signal.SIGINT})
                    self.assertEqual(list(parent.iterdir()), [])
                    return set()
                self.assertEqual(operation, probe.signal.SIG_SETMASK)
                self.assertEqual(len(list(parent.iterdir())), 1)
                raise probe.ProbeRefusal()
            with patch.object(probe.signal, "pthread_sigmask", side_effect=change_mask) as mask:
                with self.assertRaises(probe.ProbeRefusal):
                    probe.probe_writable(parent)
                self.assertEqual(mask.call_count, 2)
            self.assertEqual(list(parent.iterdir()), [])

    def test_cleanup_failure_cannot_return_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(probe.os, "rmdir", side_effect=OSError("private-marker")):
                with self.assertRaises(OSError):
                    probe.probe_writable(Path(temporary))

    def test_network_audit_refuses_socket_and_http_events(self):
        for event in ("socket.__new__", "socket.connect", "socket.getaddrinfo", "urllib.Request", "http.client.connect"):
            with self.assertRaises(probe.ProbeRefusal):
                probe.deny_network(event, ())
        probe.deny_network("os.stat", ())

    def test_main_never_prints_exception_text_or_paths(self):
        with tempfile.TemporaryDirectory(prefix="cashout_workflow_storage_") as temporary:
            parent = Path(temporary).resolve()
            output = io.StringIO()
            with patch.dict(os.environ, environment(parent), clear=True), \
                    patch.object(probe.sys, "argv", ["inspect_private_storage.py"]), \
                    patch.object(probe.sys, "addaudithook"), patch.object(probe.os, "umask"), \
                    patch.object(probe.signal, "signal"), patch.object(probe.signal, "alarm"), \
                    patch.object(probe, "inspect_storage", side_effect=OSError("private-token-marker " + str(parent))), \
                    redirect_stdout(output):
                self.assertEqual(probe.main(), 1)
            self.assertEqual(json.loads(output.getvalue()), {"schema": probe.SCHEMA, "result": "FAIL",
                                                            "reason": "PRIVATE_STORAGE_PROBE_FAILED"})
            self.assertNotIn(str(parent), output.getvalue())
            self.assertNotIn("private-token-marker", output.getvalue())

    def test_secret_environment_or_command_arguments_refuse_before_probe(self):
        for argv, values in ((["probe.py", "untrusted"], {}),
                             (["probe.py"], {"CASHOUT_SNAPSHOT_URL": "private-token-marker"})):
            output = io.StringIO()
            with patch.dict(os.environ, values, clear=True), patch.object(probe.sys, "argv", argv), \
                    patch.object(probe, "inspect_storage") as inspect, redirect_stdout(output):
                self.assertEqual(probe.main(), 1)
                inspect.assert_not_called()
            self.assertNotIn("private-token-marker", output.getvalue())


if __name__ == "__main__":
    unittest.main()
