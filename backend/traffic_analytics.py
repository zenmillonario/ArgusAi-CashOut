"""First-party aggregate traffic counts; no visitor identity or tracking cookies."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

try:
    from .membership import utc_datetime
    from .practice_event import CAMPAIGN_ID
except ImportError:
    from membership import utc_datetime
    from practice_event import CAMPAIGN_ID

EASTERN = ZoneInfo("America/New_York")
APP_ORIGINS = frozenset({
    "https://cashoutai.app", "https://www.cashoutai.app",
    "https://cashoutai-static.onrender.com", "https://cashoutai.onrender.com",
})


def eastern_day(value):
    dt = utc_datetime(value)
    return dt.replace(tzinfo=timezone.utc).astimezone(EASTERN).date() if dt else None


def create_traffic_router(db, require_admin, limiter, now=datetime.utcnow):
    router = APIRouter(prefix="/api", tags=["traffic"])

    @router.post("/traffic/open")
    @limiter.limit("30/minute")
    async def record_open(request: Request):
        # A browser origin guard reduces accidental cross-site traffic, not
        # proof of a human visit. Only aggregate day/count fields are persisted.
        if request.headers.get("origin") not in APP_ORIGINS:
            raise HTTPException(403, "App origin required.")
        day = eastern_day(now()).isoformat()
        try:
            await db.app_traffic_daily.update_one(
                {"_id": day}, {"$inc": {"page_opens": 1}}, upsert=True)
        except Exception as error:
            if getattr(error, "code", None) != 11000:
                raise
            await db.app_traffic_daily.update_one(
                {"_id": day}, {"$inc": {"page_opens": 1}})
        return JSONResponse({"recorded": True}, headers={"Cache-Control": "no-store"})

    @router.get("/admin/traffic")
    async def traffic_summary(request: Request):
        await require_admin(request)
        current = utc_datetime(now())
        today = eastern_day(current)
        days = [(today - timedelta(days=offset)).isoformat() for offset in range(6, -1, -1)]
        daily = {day: {"date": day, "page_opens": None, "registrations": 0} for day in days}
        async for doc in db.app_traffic_daily.find({"_id": {"$in": days}}):
            value = doc.get("page_opens")
            if doc.get("_id") in daily and type(value) is int and value >= 0:
                daily[doc["_id"]]["page_opens"] = value
        registered = 0
        recent = 0
        verified_event = 0
        projection = {"_id": 0, "created_at": 1, "last_seen": 1, "status": 1,
                      "disabled": 1, "is_bot": 1, "role": 1,
                      "practice_event_grant.campaign_id": 1,
                      "practice_event_grant.verified_at": 1}
        async for member in db.users.find({}, projection):
            if member.get("is_bot") is True or member.get("role") == "bot":
                continue
            registered += 1
            created = utc_datetime(member.get("created_at"))
            if created and created <= current:
                date = eastern_day(created).isoformat()
                if date in daily:
                    daily[date]["registrations"] += 1
            seen = utc_datetime(member.get("last_seen"))
            if (member.get("disabled") is not True and member.get("status") in ("approved", "trial")
                    and seen and current - timedelta(minutes=15) <= seen <= current):
                recent += 1
            grant = member.get("practice_event_grant")
            if isinstance(grant, dict) and grant.get("campaign_id") == CAMPAIGN_ID:
                verified = utc_datetime(grant.get("verified_at"))
                if verified and verified <= current:
                    verified_event += 1
        recorded_days = [row["page_opens"] for row in daily.values() if row["page_opens"] is not None]
        return JSONResponse({
            "timezone": "America/New_York", "as_of": current.isoformat() + "Z",
            "page_opens_today": daily[days[-1]]["page_opens"],
            "page_opens_7_days": sum(recorded_days) if recorded_days else None,
            "registrations_today": daily[days[-1]]["registrations"],
            "registered_accounts": registered,
            "recent_member_activity": recent,
            "verified_event_accounts": verified_event,
            "days": list(daily.values()),
        }, headers={"Cache-Control": "no-store"})

    return router
