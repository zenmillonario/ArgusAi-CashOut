"""Read the two password-hash fields written by historical CashOutAI versions.

The old bcrypt migration wrote ``hashed_password`` while normal operations used
``password_hash``. A missing canonical field may use that alternate only when it
contains a recognized hash. Plaintext and missing credentials never authenticate.
"""
import re

_LEGACY_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_BCRYPT = re.compile(r"^\$2[ab]\$(?:0[4-9]|[12][0-9]|3[01])\$[./A-Za-z0-9]{53}$")


def password_record(user):
    """Return (field, hash), prioritizing any nonempty canonical credential."""
    if not isinstance(user, dict):
        return None, None
    primary = user.get("password_hash")
    if primary is not None and primary != "":
        # Never fall through an existing canonical credential to a stale alias.
        return ("password_hash", primary) if isinstance(primary, str) else (None, None)
    alternate = user.get("hashed_password")
    if isinstance(alternate, str) and (_LEGACY_SHA256.fullmatch(alternate) or _BCRYPT.fullmatch(alternate)):
        return "hashed_password", alternate
    return None, None
