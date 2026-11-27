#!/usr/bin/env python3
"""Publish five local, read-only PAPER Nautilus snapshots to CashOutAi.

Run on the machine hosting the existing bot engines:
  export NAUTILUS_BACKEND_URL=https://your-backend.example
  export NAUTILUS_PUBLISHER_KEY=<the same secret configured on the backend>
  python scripts/publish_nautilus.py

Use --check-local for a single read-only local identity check with no backend
or key. Use --prompt-key to enter a key privately for this run; that explicit
option overrides an environment key and never saves the entered value.

Generate the secret separately (at least 32 characters). It is never passed to
the local engine or printed. Sources are fixed to 127.0.0.1:8787..8791. This
process has no venue credentials, no order API, and no strategy controls.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import getpass
import json
import os
import sys
import time
import warnings
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

ASSET_PORTS = {"BTC": 8787, "ETH": 8788, "SOL": 8789, "XRP": 8790, "DOGE": 8791}
MAX_PACKET_BYTES = 4 * 1024 * 1024


class LocalIdentityError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "Redirects are disabled for the publisher", headers, fp)


def backend_base(value, allow_local_http=False):
    try:
        parsed = urlsplit(value)
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError
        _ = parsed.port  # Validate malformed port numbers before starting.
        local_http = allow_local_http and parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")
        if parsed.scheme != "https" and not local_http:
            raise ValueError
        if any(char.isspace() or ord(char) < 32 for char in value):
            raise ValueError
    except ValueError:
        raise ValueError("Set an HTTPS backend URL without credentials, query parameters, or fragments.") from None
    path = parsed.path.rstrip("/")
    if path.endswith("/api"):
        path = path[:-4]
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _read_bounded(response):
    raw = response.read(MAX_PACKET_BYTES + 1)
    if len(raw) > MAX_PACKET_BYTES:
        raise ValueError("native packet exceeded the size limit")
    return raw


def read_local_paper(asset):
    """Read one fixed local endpoint; validate only its matching PAPER identity."""
    if asset not in ASSET_PORTS:
        raise ValueError("Unknown bot asset")
    # Proxy environment settings must never send localhost telemetry elsewhere.
    local_opener = build_opener(ProxyHandler({}), NoRedirect())
    # Dashboard cache versions belong to browser tabs. The stable read-only
    # API intentionally accepts an unversioned request from this display bridge.
    source = f"http://127.0.0.1:{ASSET_PORTS[asset]}/api/nautilus"
    with local_opener.open(Request(source, headers={"Accept": "application/json"}), timeout=2) as response:
        raw = _read_bounded(response)
    packet = json.loads(raw)
    if (not isinstance(packet, dict) or packet.get("mode") != "PAPER_ONLY"
            or packet.get("readonly") is not True or not isinstance(packet.get("asset"), dict)
            or packet["asset"].get("symbol") != asset):
        raise LocalIdentityError("local source is not the matching read-only PAPER bot")
    return raw


def check_local_one(asset):
    """Check a local identity once; do not publish or assess quote freshness."""
    try:
        read_local_paper(asset)
        return True, "reachable; matching read-only PAPER identity"
    except LocalIdentityError as error:
        return False, str(error)
    except HTTPError as error:
        return False, f"local HTTP {error.code}; check this bot's local endpoint"
    except (URLError, TimeoutError, OSError):
        return False, "local source unavailable"
    except (ValueError, TypeError, AttributeError, RecursionError):
        return False, "invalid or oversized local PAPER packet"


def check_local_sources():
    print("Checking five fixed local PAPER endpoints; no backend publication.", flush=True)
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {asset: pool.submit(check_local_one, asset) for asset in ASSET_PORTS}
        statuses = {asset: future.result() for asset, future in futures.items()}
    for asset, (_, message) in statuses.items():
        print(f"{asset}: {message}", flush=True)
    print("Identity check only: backend acceptance and source/quote freshness are not checked.", flush=True)
    return 0 if all(ok for ok, _ in statuses.values()) else 1


def prompt_publisher_key():
    """Require hidden terminal input; never fall back to echoed key entry."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            return getpass.getpass("Publisher key (hidden; not saved): ")
    except (getpass.GetPassWarning, EOFError, OSError):
        raise ValueError("Hidden key entry is unavailable. Open a normal terminal and run again.") from None


def publish_one(asset, backend, secret):
    """Return a short status; do not emit response bodies or secret-bearing URLs."""
    if asset not in ASSET_PORTS:
        raise ValueError("Unknown bot asset")
    try:
        raw = read_local_paper(asset)
        remote_opener = build_opener(NoRedirect())
        request = Request(
            backend + "/api/nautilus/ingest/" + asset,
            data=raw,
            headers={"Content-Type": "application/json", "Accept": "application/json", "X-Nautilus-Publisher-Key": secret},
            method="POST",
        )
        with remote_opener.open(request, timeout=5) as response:
            status = response.status
            if not 200 <= status < 300:
                return False, "backend did not accept the packet"
            try:
                acknowledgement = json.loads(_read_bounded(response))
                if (not isinstance(acknowledgement, dict)
                        or acknowledgement.get("asset") != asset
                        or type(acknowledgement.get("accepted")) is not bool
                        or not isinstance(acknowledgement.get("receivedAt"), str)):
                    raise ValueError("invalid acknowledgement")
                received_at = datetime.fromisoformat(acknowledgement["receivedAt"].replace("Z", "+00:00"))
                if received_at.tzinfo is None:
                    raise ValueError("missing receipt timezone")
            except (ValueError, TypeError, UnicodeError, RecursionError):
                return False, "invalid or oversized backend acknowledgement"
        if acknowledgement["accepted"] is not True:
            return False, "source unchanged; no new snapshot accepted"
        return True, "snapshot accepted"
    except LocalIdentityError as error:
        return False, str(error)
    except HTTPError as error:
        return False, f"HTTP {error.code}; check the source, backend URL, and publisher configuration"
    except (URLError, TimeoutError, OSError):
        return False, "source or backend unavailable"
    except (ValueError, TypeError, AttributeError, RecursionError):
        return False, "invalid or oversized local PAPER packet"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default=os.environ.get("NAUTILUS_BACKEND_URL", ""), help="HTTPS backend origin (or NAUTILUS_BACKEND_URL)")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between polling rounds; default 1")
    parser.add_argument("--once", action="store_true", help="Publish one round, then exit")
    parser.add_argument("--allow-local-http", action="store_true", help="Development only: allow an explicit localhost HTTP backend")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-local", action="store_true", help="Read five fixed localhost endpoints once; no backend or key required")
    mode.add_argument("--prompt-key", action="store_true", help="Enter a hidden key for this run, overriding the environment key; never save it")
    args = parser.parse_args(argv)
    if args.check_local:
        try:
            return check_local_sources()
        except KeyboardInterrupt:
            print("Local identity check cancelled.", flush=True)
            return 130
    try:
        backend = backend_base(args.backend, args.allow_local_http)
    except ValueError as error:
        parser.error(str(error))
    if not 0.25 <= args.interval <= 2.0:
        parser.error("Use a polling interval between 0.25 and 2 seconds to preserve short native quote validity.")
    try:
        secret = prompt_publisher_key() if args.prompt_key else os.environ.get("NAUTILUS_PUBLISHER_KEY", "")
    except ValueError as error:
        parser.error(str(error))
    except KeyboardInterrupt:
        print("Publisher start cancelled.", flush=True)
        return 130
    if not 32 <= len(secret) <= 512 or any(ord(c) < 32 or ord(c) > 126 for c in secret):
        parser.error("Publisher key must contain 32–512 printable ASCII characters.")
    print("Nautilus publisher: five fixed local PAPER sources; no venue orders.", flush=True)
    previous, last_report = {}, 0.0
    try:
        with ThreadPoolExecutor(max_workers=5) as pool:
            while True:
                started = time.monotonic()
                futures = {asset: pool.submit(publish_one, asset, backend, secret) for asset in ASSET_PORTS}
                statuses = {asset: future.result() for asset, future in futures.items()}
                report = args.once or time.monotonic() - last_report >= 60
                for asset, result in statuses.items():
                    if report or previous.get(asset) != result:
                        print(f"{asset}: {result[1]}", flush=True)
                previous = statuses
                if report:
                    last_report = time.monotonic()
                if args.once:
                    return 0 if all(ok for ok, _ in statuses.values()) else 1
                time.sleep(max(0.0, args.interval - (time.monotonic() - started)))
    except KeyboardInterrupt:
        print("Nautilus publisher stopped.", flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
