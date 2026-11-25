"""Shared access decisions. Historical approved accounts are never migrated away.

Once an account has a managed entitlement, an expired or malformed grant must
not fall back to the historical approved-account rule. Payment records and
access are separate: an administrator can still explicitly grant manual access.
"""
from datetime import datetime, timezone


MEMBERSHIP_REQUIRED = {
    "code": "membership_required",
    "message": "An active membership is required. Open billing to review access.",
}


def utc_datetime(value):
    try:
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if not isinstance(value, datetime):
            return None
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    except (ValueError, TypeError, OverflowError):
        return None


def iso_date(value):
    value = utc_datetime(value)
    return value.isoformat(timespec="milliseconds") + "Z" if value else None


def membership_snapshot(user, now=None):
    now = utc_datetime(now) or datetime.utcnow()
    result = {"active": False, "source": "none", "paid_through": None,
              "lifetime": False, "plan_id": None}
    if not isinstance(user, dict) or user.get("disabled") is True:
        return result
    if user.get("status") == "trial":
        end = utc_datetime(user.get("trial_end_date"))
        return {**result, "source": "trial", "active": bool(end and end > now),
                "trial_ends_at": iso_date(end)}
    if user.get("status") != "approved":
        return result
    managed = user.get("billing_entitlement")
    if isinstance(managed, dict) and managed.get("managed_by") in ("square", "manual_payment"):
        end = utc_datetime(managed.get("paid_through"))
        lifetime = managed.get("lifetime") is True
        result.update(source=managed["managed_by"], paid_through=iso_date(end), lifetime=lifetime,
                      plan_id=managed.get("plan_id"), active=bool(lifetime or (end and end > now)))
        if managed.get("legacy_access") is True:
            result.update(source="legacy", active=True)
    elif "billing_entitlement" not in user:
        legacy_lifetime = str(user.get("membership_plan") or "").strip().casefold() == "lifetime"
        result.update(source="legacy", active=True, lifetime=legacy_lifetime,
                      plan_id="lifetime" if legacy_lifetime else None)
    # A manual approval is an explicit admin action, never evidence of payment.
    if user.get("manual_access_granted") is True:
        result.update(source="manual", active=True)
    return result


def active_membership(user, now=None):
    return membership_snapshot(user, now)["active"]
