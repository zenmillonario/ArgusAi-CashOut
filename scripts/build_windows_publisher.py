#!/usr/bin/env python3
"""Build or verify the small, credential-free Windows publisher companion."""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = (
    "scripts/publish_nautilus.py",
    "scripts/windows/01_CHECK_LOCAL_FEEDS.cmd",
    "scripts/windows/02_START_PUBLISHER.cmd",
    "scripts/windows/README.md",
)
PREFIX = "CashOutAI_Publisher_Windows/"
DESTINATION = ROOT / "downloads/CashOutAI_Publisher_Windows.zip"


def archive_bytes():
    # An explicit list prevents local credentials, private engines, and run
    # captures from being accidentally included by a recursive directory glob.
    files = {name: (ROOT / name).read_bytes() for name in PAYLOAD}
    files["SHA256SUMS.txt"] = "".join(
        f"{hashlib.sha256(content).hexdigest()}  {name}\n"
        for name, content in files.items()
    ).encode("utf-8")
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, content in files.items():
            info = zipfile.ZipInfo(PREFIX + name, date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, content)
    result = output.getvalue()
    with zipfile.ZipFile(BytesIO(result)) as archive:
        if archive.testzip() is not None:
            raise ValueError("Companion archive failed its CRC check")
        if archive.namelist() != [PREFIX + name for name in files]:
            raise ValueError("Unexpected companion archive membership")
        for name, content in files.items():
            if archive.read(PREFIX + name) != content:
                raise ValueError("Companion archive differs from its source")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify the existing ZIP without changing it")
    args = parser.parse_args(argv)
    data = archive_bytes()
    if args.check:
        if not DESTINATION.is_file() or DESTINATION.read_bytes() != data:
            print("Companion ZIP is missing or differs from current source; rebuild it.", file=sys.stderr)
            return 1
    else:
        DESTINATION.parent.mkdir(parents=True, exist_ok=True)
        DESTINATION.write_bytes(data)
    print(f"SHA256 {hashlib.sha256(data).hexdigest()}  {DESTINATION.name}")
    print(f"Verified {len(PAYLOAD)} allowlisted source files plus the checksum manifest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
