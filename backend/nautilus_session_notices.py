"""Durable shared notices for newly observed, fresh PAPER runs.

The caller supplies the accepted snapshot and its server-computed live state.
One deterministic shared-chat document is the deduplication record, including
across API restarts. No member fanout, device push, scheduler, or engine control
is performed here. Historical notices describe an observation, not current
run health; room snapshots remain the source of current live/stale status.
"""
from collections import OrderedDict
from datetime import datetime, timezone
import hashlib
import math
import re


ASSETS = frozenset(("BTC", "ETH", "SOL", "XRP", "DOGE"))
NOTICE_TYPE = "bot_session_started"
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$")


def canonical_run_id(value):
    """Never collapse paths/truncated identifiers into another run's identity."""
    return value if isinstance(value, str) and _RUN_ID.fullmatch(value) else None


def notice_id(asset, run_id):
    return "nautilus-run-" + hashlib.sha256((NOTICE_TYPE + "\0" + asset + "\0" + run_id).encode()).hexdigest()


def public_notice(document):
    """Allowlisted public fields; validate the stored asset/run binding."""
    if not isinstance(document, dict) or document.get("kind") != NOTICE_TYPE:
        return None
    asset, run_id = document.get("asset"), canonical_run_id(document.get("sourceRunId"))
    if not isinstance(asset, str) or asset not in ASSETS or run_id is None:
        return None
    expected = notice_id(asset, run_id)
    if document.get("_id") != expected or document.get("id") != expected:
        return None
    try:
        observed = datetime.fromisoformat(document["createdAt"].replace("Z", "+00:00"))
        if observed.tzinfo is None:
            return None
        created = observed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    except (KeyError, AttributeError, ValueError, TypeError, OverflowError):
        return None
    return {
        "id": expected, "type": NOTICE_TYPE, "asset": asset,
        "title": f"{asset} PAPER session detected",
        "message": f"A fresh {asset} PAPER feed was detected. Open the room to check its current status and practice.",
        "createdAt": created, "tab": "bot-" + asset,
    }


class NautilusSessionNotices:
    def __init__(self, db, cache_limit=256):
        self.db = db
        self.cache_limit = max(1, min(1024, int(cache_limit)))
        self.seen = OrderedDict()

    def remember(self, key):
        self.seen[key] = True
        self.seen.move_to_end(key)
        while len(self.seen) > self.cache_limit:
            self.seen.popitem(last=False)

    async def record(self, document, state):
        """Return a new notice once; duplicates and non-live observations return None."""
        if state != "live" or not isinstance(document, dict):
            return None
        packet = document.get("snapshot") or {}
        run = packet.get("run") or {}
        asset = document.get("_id")
        run_id = canonical_run_id(document.get("sessionRunId"))
        status = run.get("status")
        if (not isinstance(asset, str) or asset not in ASSETS or run_id is None or run_id != run.get("run_id")
                or (packet.get("asset") or {}).get("symbol") != asset
                or packet.get("mode") != "PAPER_ONLY" or packet.get("readonly") is not True
                or run.get("fresh") is not True or run.get("stopped") is not False or run.get("review") is not False
                or (status is not None and not isinstance(status, str))
                or (isinstance(status, str) and re.search(r"(?i)(?:^|[^a-z])(replay|recorded|archived|review|stopped|offline|stale|finished|completed)(?:$|[^a-z])", status))):
            return None
        observed = document.get("receivedAt")
        if type(observed) not in (int, float) or not math.isfinite(observed) or observed <= 0:
            return None
        try:
            # Fixed precision keeps the indexed ISO strings chronologically
            # ordered even when one run was observed on an exact second.
            created = datetime.fromtimestamp(observed, timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        except (ValueError, OverflowError, OSError):
            return None
        key = notice_id(asset, run_id)
        # Cache only after durable success or an existing durable record. The
        # bounded cache avoids extra reads on every publisher heartbeat; the
        # unique _id remains the authority after restarts and under concurrency.
        if key in self.seen:
            self.seen.move_to_end(key)
            return None
        if await self.db.nautilus_chat.find_one({"_id": key}):
            self.remember(key)
            return None
        row = {"_id": key, "id": key, "kind": NOTICE_TYPE, "asset": asset,
               "sourceRunId": run_id, "authorId": "cashoutai-system",
               "author": "CashOutAI", "isAdmin": True, "createdAt": created,
               "content": f"A fresh {asset} PAPER feed was detected. Open this room to check its current status and practice."}
        try:
            await self.db.nautilus_chat.insert_one(row)
        except Exception as error:
            if getattr(error, "code", None) == 11000:
                self.remember(key)
                return None
            raise
        self.remember(key)
        return public_notice(row)

    async def recent(self, limit=20):
        # Bounded shared history; normal member chat never enters this feed.
        limit = max(1, min(50, int(limit)))
        rows = await self.db.nautilus_chat.find({"kind": NOTICE_TYPE}).sort("createdAt", -1).limit(limit).to_list(length=limit)
        return [notice for row in rows if (notice := public_notice(row)) is not None]
