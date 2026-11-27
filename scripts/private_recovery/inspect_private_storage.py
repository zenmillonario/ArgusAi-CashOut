"""Inputless filesystem metadata probe; no snapshot, app, or network access.

TMPDIR identifies the wrapper's actual newly created private directory. Only
fixed candidate labels and bounded filesystem statistics leave this process.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import stat
import sys
import tempfile


SCHEMA = "cashout_private_storage_v1"
ENVIRONMENT_KEYS = frozenset({"PATH", "LANG", "TZ", "PYTHONUNBUFFERED", "PYTHONDONTWRITEBYTECODE", "TMPDIR"})
FILESYSTEM_TYPES = frozenset({"tmpfs", "overlay", "ext4", "xfs", "btrfs"})
MAX_NUMBER = 2 ** 53 - 1
MAX_MOUNT_BYTES = 256 * 1024


class ProbeRefusal(Exception):
    """Private diagnostic failures never expose exception text."""


def require(condition):
    if not condition:
        raise ProbeRefusal()


def default_root(environment):
    require(set(environment) == ENVIRONMENT_KEYS)
    raw = environment["TMPDIR"]
    require(type(raw) is str and 0 < len(raw) <= 4096)
    path = Path(raw)
    require(path.is_absolute() and path.resolve() == path and not path.is_symlink()
            and path.name.startswith("cashout_workflow_storage_"))
    info = path.stat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077)
    return path


def read_mount_types():
    # Read only this bounded kernel metadata file, never directory contents or
    # member data. Neither mount points nor unrecognized type strings escape.
    try:
        with open("/proc/self/mountinfo", "rb") as stream:
            raw = stream.read(MAX_MOUNT_BYTES + 1)
        if len(raw) > MAX_MOUNT_BYTES:
            return []
        lines = raw.decode("utf-8").splitlines()
    except (OSError, UnicodeError):
        return []
    mounts = []
    for line in lines:
        before, separator, after = line.partition(" - ")
        fields, details = before.split(), after.split()
        if not separator or len(fields) < 5 or not details:
            continue
        point = fields[4]
        for escaped, decoded in ((r"\040", " "), (r"\011", "\t"), (r"\012", "\n"), (r"\134", "\\")):
            point = point.replace(escaped, decoded)
        if not point.startswith("/"):
            continue
        kind = details[0] if details[0] in FILESYSTEM_TYPES else "other"
        mounts.append((Path(point), kind))
    return mounts


def filesystem_type(path, mounts):
    matching = [(len(point.parts), kind) for point, kind in mounts if path.is_relative_to(point)]
    return max(matching, key=lambda item: item[0])[1] if matching else "unknown"


def probe_writable(path):
    created = None
    try:
        # Record the created path before a handled termination signal can run;
        # the fixed candidates can be outside the wrapper's own cleanup root.
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK,
                                               {signal.SIGALRM, signal.SIGTERM, signal.SIGINT})
        try:
            created = Path(tempfile.mkdtemp(prefix="cashout_storage_probe_", dir=path))
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        info = created.stat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077)
        return True
    except OSError:
        return False
    finally:
        if created is not None:
            # Only an empty directory is created. Failure to remove it fails
            # the entire diagnostic instead of claiming successful cleanup.
            os.rmdir(created)
            require(not os.path.lexists(created))


def candidate(label, path, default_device, mounts):
    row = {"label": label, "available": False, "writable": False,
           "total_bytes": 0, "free_bytes": 0, "total_inodes": 0, "free_inodes": 0,
           "same_filesystem_as_default": False, "filesystem_type": "unknown"}
    try:
        resolved = path.resolve(strict=True)
        info = resolved.stat()
        if not stat.S_ISDIR(info.st_mode):
            return row
        usage = os.statvfs(resolved)
    except OSError:
        return row
    counts = {"total_bytes": usage.f_blocks * usage.f_frsize,
              "free_bytes": usage.f_bavail * usage.f_frsize,
              "total_inodes": usage.f_files, "free_inodes": usage.f_favail}
    require(all(type(value) is int and 0 <= value <= MAX_NUMBER for value in counts.values()))
    require(counts["total_bytes"] > 0 and counts["free_bytes"] <= counts["total_bytes"]
            and counts["free_inodes"] <= counts["total_inodes"])
    row.update(counts)
    row.update(available=True, writable=probe_writable(resolved),
               same_filesystem_as_default=info.st_dev == default_device,
               filesystem_type=filesystem_type(resolved, mounts))
    return row


def inspect_storage(parent):
    mounts = read_mount_types()
    device = parent.stat().st_dev
    paths = (("default", parent), ("tmp", Path("/tmp")),
             ("var_tmp", Path("/var/tmp")), ("home", Path("/home/rehearsal")))
    rows = [candidate(label, path, device, mounts) for label, path in paths]
    require(rows[0]["available"] and rows[0]["same_filesystem_as_default"])
    return {"schema": SCHEMA, "result": "PASS", "mode": "metadata_only",
            "network_attempts": 0, "snapshot_data_accessed": False,
            "probe_cleanup_verified": True, "candidates": rows}


def deny_network(event, args):
    if event.startswith("socket.") or event in {"urllib.Request", "http.client.connect"}:
        raise ProbeRefusal()


def main():
    try:
        require(len(sys.argv) == 1)
        parent = default_root(dict(os.environ))
        os.environ.clear()
        os.umask(0o077)
        def interrupted(signum, frame):
            raise ProbeRefusal()
        for signum in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT):
            signal.signal(signum, interrupted)
        signal.alarm(15)
        sys.addaudithook(deny_network)
        result = inspect_storage(parent)
        signal.alarm(0)
    except BaseException:
        print(json.dumps({"schema": SCHEMA, "result": "FAIL",
                          "reason": "PRIVATE_STORAGE_PROBE_FAILED"}, sort_keys=True), flush=True)
        return 1
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
