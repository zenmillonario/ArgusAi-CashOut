"""Data-only Stocks push transport. Acceptance is not proof of delivery.

The existing registration-token scheme is retained as one coherent scheme with
firebase-admin 6.9.0. An FID migration must update client and server together.
"""
import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import firebase_admin
from firebase_admin import credentials, initialize_app, messaging

logger = logging.getLogger(__name__)


class FCMService:
    def __init__(self):
        self.initialized = False
        try:
            try:
                firebase_admin.get_app()
                self.initialized = True
                return
            except ValueError:
                pass
            credential = None
            encoded = os.getenv("FIREBASE_ADMIN_CREDENTIALS")
            if encoded:
                credential = credentials.Certificate(json.loads(encoded))
            elif os.path.exists("/app/backend/firebase-admin.json"):
                credential = credentials.Certificate("/app/backend/firebase-admin.json")
            if credential:
                initialize_app(credential)
                self.initialized = True
            else:
                logger.warning("Firebase credentials are not configured; stock push is unavailable")
        except Exception:
            # Provider exceptions can contain request/credential information.
            logger.warning("Firebase initialization failed; stock push is unavailable")

    async def send_stock_alert(self, token: str, data: Dict[str, str], ttl_seconds: int = 300) -> Dict[str, Any]:
        """One recipient and one context; never include a notification payload.

        Only a pre-send unavailable configuration is retryable automatically.
        Transport timeouts and provider exceptions have an uncertain acceptance
        outcome and are recorded for operator review, not blindly retried.
        """
        if not (data.get("type") == "stock_alert" and data.get("category") == "stocks"
                and re.fullmatch(r"[a-f0-9]{64}", data.get("alert_id", ""))
                and re.fullmatch(r"[a-f0-9]{64}", data.get("notification_context", ""))):
            return {"status": "rejected", "reason": "non_stock_or_invalid_payload"}
        if not self.initialized:
            return {"status": "retryable", "reason": "provider_not_configured"}
        if not token or not isinstance(token, str) or len(token) > 4096:
            return {"status": "rejected", "reason": "invalid_registration"}
        try:
            message = messaging.Message(
                token=token,
                data={str(key): str(value) for key, value in data.items()},
                webpush=messaging.WebpushConfig(headers={"TTL": str(max(1, min(300, ttl_seconds))), "Urgency": "high"}),
            )
        except (TypeError, ValueError):
            return {"status": "rejected", "reason": "invalid_payload"}
        try:
            # The SDK call is synchronous; do not block WebSockets or the API.
            await asyncio.wait_for(asyncio.to_thread(messaging.send, message), timeout=30)
            return {"status": "accepted"}
        except asyncio.CancelledError:
            raise
        except Exception as error:
            # An explicit invalid/unregistered response is a known rejection.
            if type(error).__name__ in {"UnregisteredError", "InvalidArgumentError", "SenderIdMismatchError"}:
                return {"status": "rejected", "reason": "invalid_registration_or_payload"}
            logger.warning("Firebase stock push acceptance is unknown")
            return {"status": "unknown", "reason": "provider_outcome_unknown"}

    async def send_notification(self, token: str, title: str, body: str,
                                data: Optional[Dict[str, str]] = None) -> bool:
        """Legacy callers cannot bypass the Stocks-only allowlist."""
        payload = {**(data or {}), "title": title, "body": body}
        outcome = await self.send_stock_alert(token, payload)
        return outcome["status"] == "accepted"

    async def send_chat_notification(self, token: str, sender_name: str, message_content: str,
                                     sender_id: str, message_type: str = "text") -> bool:
        return False

    async def send_to_multiple(self, tokens: List[str], title: str, body: str,
                               data: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        # Stock jobs must be individualized to the current user's session context.
        # Legacy admin/chat multicast is disabled; no obsolete send_multicast API.
        return {"success_count": 0, "failure_count": len(tokens), "suppressed": True,
                "reason": "individual_verified_stock_jobs_required"}


fcm_service = FCMService()
