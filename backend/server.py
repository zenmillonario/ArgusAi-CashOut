import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
import uuid
import secrets
from fastapi import File, UploadFile, HTTPException
import shutil

# Configure logging early
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Public profiles, lists and notifications must never carry authentication or
# private billing records. Billing endpoints use their own owner-only projection.
AUTH_PRIVATE_FIELDS = frozenset({
    "password", "password_hash", "hashed_password", "active_session_id",
    "session_created_at", "new_session_id", "reset_token", "reset_token_hash", "reset_expires", "reset_context_hash",
    "billing_entitlement", "billing_token", "credential_fingerprint",
    "manual_access_granted", "manual_access_granted_at", "manual_access_granted_by",
    "practice_event_token_hash", "practice_event_token_expires", "practice_event_token_campaign",
    "practice_event_token_email", "practice_event_token_credential", "practice_event_grant",
    "practice_event_trial", "practice_event_verified_email", "practice_event_verified_at",
    "practice_event_email_status", "registration_email_key", "registration_username_key",
})

def redact_auth_fields(value):
    if isinstance(value, BaseModel):
        value = value.model_dump()
    if isinstance(value, dict):
        return {key: redact_auth_fields(item) for key, item in value.items() if key not in AUTH_PRIVATE_FIELDS}
    if isinstance(value, (list, tuple)):
        return [redact_auth_fields(item) for item in value]
    return value

def public_socket_message(message: str) -> str:
    """Apply the same credential boundary to all structured socket messages."""
    try:
        return json.dumps(redact_auth_fields(json.loads(message)), default=str)
    except (TypeError, ValueError):
        return message

# Import database and app setup early
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Union
import asyncio
import motor.motor_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks, Query, Request, Depends, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import hashlib
import bcrypt

# Database setup
MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017/emergent_db')
DB_NAME = os.getenv('DB_NAME', 'emergent_db')

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# Initialize FastAPI app early (lifespan will be set after lifespan function is defined)
app = FastAPI(title="ArgusAI CashOut API", version="1.0.0")

# Rate limiting - only on registration to prevent abuse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS setup
cors_env = os.getenv("CORS_ORIGINS", "")
if cors_env == "*":
    ALLOWED_ORIGINS = ["*"]
else:
    ALLOWED_ORIGINS = [
        "https://cashoutai.app",
        "https://www.cashoutai.app",
        "https://www.CashOutAi.App",
        "https://cashoutai.onrender.com",
    ]
    if cors_env:
        ALLOWED_ORIGINS.extend([o.strip() for o in cors_env.split(",") if o.strip()])
    preview_url = os.getenv("REACT_APP_BACKEND_URL", "")
    if preview_url:
        ALLOWED_ORIGINS.append(preview_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Nautilus snapshots contain sizeable chart histories. Negotiate compression for
# large HTTP responses; WebSocket connections bypass this HTTP middleware.
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)

# Generate referral code for new users
def generate_referral_code(username: str) -> str:
    """Generate a unique referral code for a user"""
    # Use first 4 chars of username + 4 random chars
    username_part = username[:4].upper()
    random_part = secrets.token_hex(2).upper()
    return f"{username_part}{random_part}"

async def handle_referral_signup(new_user_id: str, referral_code: str):
    """Handle referral when a new user signs up with a referral code"""
    try:
        # Find the referring user
        referring_user = await db.users.find_one({"referral_code": referral_code})
        if not referring_user:
            logger.warning(f"Invalid referral code used: {referral_code}")
            return False
        
        referring_user_id = referring_user["id"]
        
        # Update the new user's referred_by field
        await db.users.update_one(
            {"id": new_user_id},
            {"$set": {"referred_by": referring_user_id}}
        )
        
        # Add new user to referring user's referrals list
        await db.users.update_one(
            {"id": referring_user_id},
            {
                "$push": {"referrals": new_user_id},
                "$inc": {"successful_referrals": 1}
            }
        )
        
        logger.info(f"User {new_user_id} was referred by {referring_user_id} using code {referral_code}")
        
        # Check for referral achievements for the referring user
        await check_achievements(referring_user_id, "referral_success", {"referred_user": new_user_id})
        
        return True
        
    except Exception as e:
        logger.error(f"Error handling referral signup: {e}")
        return False
import hashlib
import json
from enum import Enum
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import aiohttp
import re
import base64
import httpx
import asyncio
import sys
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException, File, UploadFile, BackgroundTasks
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

async def send_registration_confirmation_to_user(email: str, name: str):
    """Send registration confirmation email to user"""
    if not email_service:
        print(f"Email service unavailable. Would send registration confirmation to {email}")
        return
        
    subject = "🎉 Welcome to ArgusAI CashOut - Registration Received"
    
    plain_body = f"""
Hi {name},

Thank you for registering with ArgusAI CashOut!

Your account has been created and is pending admin approval. We'll review your registration and get back to you soon.

You will receive another email once your account is approved and you can start trading with our community.

Thanks for joining us!

--
ArgusAI CashOut Team
"""
    
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f9f9f9; }}
        .welcome-box {{ background: white; padding: 20px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #667eea; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎉 Welcome to ArgusAI CashOut!</h1>
        <p>Registration Received</p>
    </div>
    
    <div class="content">
        <div class="welcome-box">
            <h2>Hi {name},</h2>
            <p>Thank you for registering with ArgusAI CashOut!</p>
            <p>Your account has been created and is pending admin approval.</p>
        </div>
        
        <p>We'll review your registration and get back to you soon. You will receive another email once your account is approved and you can start trading with our community.</p>
        
        <p>Thanks for joining us! 🚀</p>
    </div>
    
    <div class="footer">
        <p>ArgusAI CashOut Team</p>
    </div>
</body>
</html>
"""
    
    await email_service.send_email(email, subject, plain_body, html_body)

async def send_trial_welcome_email(email: str, name: str, trial_end_date: datetime):
    """Send trial welcome email to user"""
    if not email_service:
        print(f"Email service unavailable. Would send trial welcome email to {email}")
        return
        
    await email_service.send_trial_welcome_email(email, name, trial_end_date)

async def send_trial_upgrade_email(email: str, name: str):
    """Send upgrade email to expired trial user"""
    if not email_service:
        print(f"Email service unavailable. Would send trial upgrade email to {email}")
        return
        
    await email_service.send_trial_upgrade_email(email, name)


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Database connection already initialized at top of file
# MongoDB connection moved to top for proper initialization order

# Try to import and initialize email service
try:
    sys.path.append(str(ROOT_DIR))
    from email_service import email_service
    print("Email service initialized successfully")
except Exception as e:
    email_service = None
    print(f"Warning: Email service not available. Email notifications will be disabled. Error: {e}")

# ONLINE USERS FIX: Background task for periodic cleanup
async def periodic_cleanup():
    """Run periodic cleanup of stale sessions every 10 minutes"""
    while True:
        try:
            await asyncio.sleep(600)  # 10 minutes
            await cleanup_stale_sessions()
            await check_expired_trials()  # Check for expired trials
        except Exception as e:
            logger.error(f"Error in periodic cleanup: {e}")

async def check_expired_trials():
    """Check for expired trials and update status"""
    try:
        current_time = datetime.utcnow()
        
        # Find trials that have expired but haven't been processed
        expired_trials = await db.users.find({
            "status": UserStatus.TRIAL,
            "trial_end_date": {"$lt": current_time}
        }).to_list(100)
        
        if expired_trials:
            logger.info(f"🕒 Found {len(expired_trials)} expired trials to process")
            
            for user in expired_trials:
                # Expire only the access state this scan observed. Payment or
                # complimentary approval, an extended trial, or another worker
                # may have changed it while this operation was waiting.
                expected = {
                    "id": user["id"], "status": UserStatus.TRIAL,
                    "trial_end_date": user["trial_end_date"],
                    **{field: user[field] if field in user else {"$exists": False}
                       for field in ("billing_entitlement", "manual_access_granted", "disabled")},
                }
                result = await db.users.update_one(
                    expected,
                    {"$set": {"status": UserStatus.TRIAL_EXPIRED}}
                )
                if result.modified_count != 1:
                    continue
                
                # Send upgrade email if not already sent
                if not user.get("trial_upgrade_email_sent", False):
                    await send_trial_upgrade_email(user["email"], user.get("real_name", user["username"]))
                    await db.users.update_one(
                        {**expected, "status": UserStatus.TRIAL_EXPIRED},
                        {"$set": {"trial_upgrade_email_sent": True}}
                    )
                
                logger.info(f"⏰ TRIAL EXPIRED: {user['username']} - Status updated to trial_expired")
        
    except Exception as e:
        logger.error(f"Error checking expired trials: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create indexes for performance
    try:
        await db.messages.create_index([("timestamp", -1)])
        await db.users.create_index("id", unique=True)
        await db.users.create_index("username")
        await db.users.create_index("email")
        await db.users.create_index("is_online")
        await db.nautilus_chat.create_index(
            [("asset", 1), ("createdAt", -1)], name="nautilus_chat_asset_created_at"
        )
        await db.nautilus_chat.create_index(
            [("kind", 1), ("createdAt", -1)], name="nautilus_chat_kind_created_at"
        )
        logger.info("Ensured messages timestamp index exists")
    except Exception as e:
        logger.warning(f"Could not create index: {e}")

    try:
        await practice_event_service.initialize()
    except Exception:
        # Registration also checks its uniqueness indexes before inserting.
        logger.warning("Practice-event indexes unavailable; verify database readiness before opening enrollment.")
    
    # Administrator provisioning is an operator action. Never seed a public
    # account with a predictable password or elevate the first registration.
    admin_exists = await db.users.find_one({"is_admin": True})
    if not admin_exists:
        logger.warning("No administrator is provisioned; public registration remains pending approval.")
    
    # Start background cleanup task
    cleanup_task = asyncio.create_task(periodic_cleanup())
    stock_push_task = asyncio.create_task(stock_alert_service.run())
    practice_settlement_task = asyncio.create_task(nautilus_settlement_service.run())
    background_tasks = [cleanup_task, stock_push_task, practice_settlement_task]
    if square_billing_service.settings.mode == "automatic":
        background_tasks.append(asyncio.create_task(square_billing_service.run()))
    else:
        # Manual approval uses request background tasks for its single welcome
        # attempt and does not need a continuously running Square worker.
        try:
            await square_billing_service.initialize()
        except Exception:
            logger.warning("Billing indexes unavailable; manual receipts still use unique document IDs.")
    logger.info("Started periodic stale session cleanup (every 10 minutes)")
    try:
        yield
    finally:
        # Stop workers before closing the shared read-only settlement client.
        for task in background_tasks:
            task.cancel()
        await asyncio.gather(*background_tasks, return_exceptions=True)
        await nautilus_settlement_service.shutdown()

# Use the existing app initialized at the top and add lifespan
app.router.lifespan_context = lifespan

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# FCM Token storage model
class FCMToken(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    token: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

async def get_active_fcm_tokens(user_ids):
    """Only devices registered by the member's current login may receive push.

    Store a fingerprint, not a second copy of the session credential. Legacy
    unbound device records are ignored until a current login registers again.
    """
    if not user_ids:
        return []
    selected_ids = list(set(user_ids))
    users = await db.users.find({"id": {"$in": selected_ids}}).to_list(len(selected_ids))
    active_fingerprints = {
        user["id"]: hashlib.sha256(user["active_session_id"].encode()).hexdigest()
        for user in users if isinstance(user.get("active_session_id"), str) and user["active_session_id"]
    }
    if not active_fingerprints:
        return []
    # Query only current-login records. Historical registrations must not consume
    # the result limit and hide a valid device after many prior logins.
    registrations = await db.fcm_tokens.find({"$or": [
        {"user_id": user_id, "session_fingerprint": fingerprint}
        for user_id, fingerprint in active_fingerprints.items()
    ]}).to_list(len(active_fingerprints))
    return [registration for registration in registrations
            if isinstance(registration.get("token"), str) and registration["token"]]


@api_router.post("/fcm/register-token")
async def register_fcm_token(request: Request, token_data: Dict[str, str]):
    """Bind a device registration to the authenticated member's current login."""
    user_id = token_data.get("user_id")
    token = token_data.get("token")
    if not user_id or not token or len(user_id) > 240 or len(token) > 4096:
        raise HTTPException(status_code=400, detail="Valid user_id and token are required")
    user = await require_profile_owner(request, user_id)
    session_id = user["active_session_id"]
    fingerprint = hashlib.sha256(session_id.encode()).hexdigest()
    record_id = f"session:{user_id}:{fingerprint}"
    now = datetime.utcnow()
    update = {
        "$set": {"user_id": user_id, "token": token, "session_fingerprint": fingerprint, "updated_at": now},
        "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now},
    }
    try:
        # A deterministic Mongo _id prevents duplicate current-login records.
        try:
            await db.fcm_tokens.update_one({"_id": record_id}, update, upsert=True)
        except Exception as error:
            if getattr(error, "code", None) != 11000:
                raise
            await db.fcm_tokens.update_one({"_id": record_id}, {"$set": update["$set"]})
        if not await db.users.find_one({"id": user_id, "active_session_id": session_id}):
            raise HTTPException(status_code=401, detail="This session is no longer active. Sign in again.")
        # A browser token can be reused by another account on the same browser.
        # Keep one atomic ownership marker. Capturing `now` before any writes
        # prevents an older delayed request from reclaiming a newer registration.
        owner_id = "token-owner:" + hashlib.sha256(token.encode()).hexdigest()
        try:
            await db.fcm_tokens.update_one(
                {"_id": owner_id, "$or": [{"claimed_at": {"$lte": now}}, {"claimed_at": {"$exists": False}}]},
                {"$set": {"owner_user_id": user_id, "owner_session_fingerprint": fingerprint, "claimed_at": now}},
                upsert=True,
            )
        except Exception as error:
            if getattr(error, "code", None) != 11000:
                raise
            # Existing newer ownership failed the time predicate; preserve it.
        if not await db.users.find_one({"id": user_id, "active_session_id": session_id}):
            raise HTTPException(status_code=401, detail="This session is no longer active. Sign in again.")
        return {"message": "Token registered successfully"}
    except HTTPException:
        raise
    except Exception:
        logger.error("Could not register the current-session notification device")
        raise HTTPException(status_code=500, detail="Could not register this notification device")

@api_router.get("/fcm/status")
async def fcm_status():
    """Check FCM service initialization status"""
    try:
        from fcm_service import fcm_service
        has_creds = bool(os.getenv("FIREBASE_ADMIN_CREDENTIALS"))
        token_count = await db.fcm_tokens.count_documents({"token": {"$exists": True}})
        return {
            "initialized": fcm_service.initialized,
            "credentials_configured": has_creds,
            "registered_tokens": token_count
        }
    except Exception as e:
        return {"initialized": False, "error": str(e)}

@api_router.post("/fcm/test-notification")
async def test_notification(request: Request, test_data: Dict[str, str]):
    """Send test notification"""
    token = test_data.get("token")
    
    if not token:
        raise HTTPException(status_code=400, detail="token is required")
    actor_id = request.headers.get("x-user-id", "")
    await require_profile_owner(request, actor_id)
    current_devices = await get_active_fcm_tokens([actor_id])
    if not any(device["token"] == token for device in current_devices):
        raise HTTPException(status_code=403, detail="Register this device for the current login first.")
    
    return {"success": False, "suppressed": True,
            "message": "Only verified Stocks alerts trigger push. This legacy test does not send a notification."}

async def send_notification_to_admins(title: str, body: str, data: Optional[Dict[str, str]] = None):
    """Administrative activity remains in-app; only verified Stocks alerts push."""
    return {"success_count": 0, "suppressed": True}

async def send_notification_to_user(user_id: str, title: str, body: str, data: Optional[Dict[str, str]] = None):
    """Replies, follows, XP and other social activity remain in-app."""
    return False

async def create_user_notification(user_id: str, notification_type: str, title: str, message: str, data: Dict[str, Any] = None):
    """Create a notification for a user"""
    notification = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": notification_type,
        "title": title,
        "message": message,
        "data": redact_auth_fields(data or {}),
        "read": False,
        "created_at": datetime.utcnow(),
        "expires_at": None
    }
    
    await db.notifications.insert_one(notification)
    
    # Prepare notification for WebSocket (convert datetime to string)
    websocket_notification = notification.copy()
    websocket_notification["created_at"] = notification["created_at"].isoformat()
    
    # Send real-time notification via WebSocket if user is online
    if user_id in manager.user_connections:
        try:
            await manager.send_personal_message(json.dumps({
                "type": "notification",
                "notification": websocket_notification
            }), manager.user_connections[user_id])
        except:
            pass  # Ignore WebSocket errors
    
    # Send FCM notification
    await send_notification_to_user(user_id, title, message, redact_auth_fields(data or {}))
    
    return notification

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.user_connections: Dict[str, WebSocket] = {}
        self.connection_sessions = {}

    async def connect(self, websocket: WebSocket, user_id: str, session_id: str):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.user_connections[user_id] = websocket
        self.connection_sessions[websocket] = (user_id, session_id)

    def disconnect(self, websocket: WebSocket, user_id: str):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.connection_sessions.pop(websocket, None)
        if self.user_connections.get(user_id) is websocket:
            del self.user_connections[user_id]
            for remaining in reversed(self.active_connections):
                if self.connection_sessions.get(remaining, (None,))[0] == user_id:
                    self.user_connections[user_id] = remaining
                    break

    async def revoke_connection(self, connection: WebSocket, user_id: str):
        """Close this particular connection; never close a replacement by user ID."""
        self.disconnect(connection, user_id)
        try:
            await connection.send_text(json.dumps({
                "type": "session_invalidated",
                "message": "Your session has ended. Please sign in again."
            }))
        except Exception:
            pass
        finally:
            try:
                await connection.close(code=4001, reason="Session revoked")
            except Exception:
                pass

    async def validate_connection(self, websocket: WebSocket):
        """Recheck Mongo before private delivery, including across app workers."""
        identity = self.connection_sessions.get(websocket)
        if identity is None:
            return False
        user_id, session_id = identity
        try:
            user = await db.users.find_one({"id": user_id})
            active = (user or {}).get("active_session_id")
            if isinstance(active, str) and active and secrets.compare_digest(active.encode(), session_id.encode()):
                if not active_membership(user, datetime.utcnow()):
                    self.disconnect(websocket, user_id)
                    try:
                        await websocket.close(code=4403, reason="membership_required")
                    except Exception:
                        pass
                    return False
                return True
        except Exception:
            logger.warning("Socket session verification unavailable for user %s", user_id)
        await self.revoke_connection(websocket, user_id)
        return False

    async def send_personal_message(self, message: str, websocket: WebSocket):
        if not await self.validate_connection(websocket):
            return False
        await websocket.send_text(public_socket_message(message))
        return True

    async def broadcast(self, message: str):
        message = public_socket_message(message)
        for connection in tuple(self.active_connections):
            try:
                await self.send_personal_message(message, connection)
            except Exception:
                pass

    async def send_admin_notification(self, message: str):
        """Send notifications to all connected admins"""
        message = public_socket_message(message)
        admin_users = await db.users.find({"is_admin": True}).to_list(1000)
        admin_ids = [user["id"] for user in admin_users]
        
        for user_id in admin_ids:
            if user_id in self.user_connections:
                try:
                    await self.send_personal_message(message, self.user_connections[user_id])
                except Exception:
                    pass

    async def send_session_invalidation(self, user_id: str, revoked_session_id: Optional[str] = None):
        """Revoke only sockets bound to the exact session replaced atomically."""
        if not revoked_session_id:
            return
        for connection in tuple(self.active_connections):
            identity = self.connection_sessions.get(connection)
            # Untracked entries can only be legacy in-process connections.
            legacy_connection = identity is None and self.user_connections.get(user_id) is connection
            if identity == (user_id, revoked_session_id) or legacy_connection:
                await self.revoke_connection(connection, user_id)

manager = ConnectionManager()

# ONLINE USERS FIX: Add automatic stale session cleanup
async def cleanup_stale_sessions():
    """Clean up stale sessions (users marked online but inactive for >30 minutes)"""
    try:
        thirty_minutes_ago = datetime.utcnow() - timedelta(minutes=30)
        
        # Find stale sessions
        stale_sessions = await db.users.find({
            "is_online": True,
            "last_seen": {"$lt": thirty_minutes_ago}
        }).to_list(1000)
        
        for user in stale_sessions:
            # Do not mark a newly active/replaced session offline from an older
            # cleanup snapshot.
            result = await db.users.update_one(
                {"id": user["id"], "active_session_id": user.get("active_session_id"),
                 "last_seen": user.get("last_seen"), "is_online": True},
                {"$set": {"is_online": False}}
            )
            if result.modified_count:
                await manager.broadcast(json.dumps({
                    "type": "user_left",
                    "user_id": user['id']
                }, default=str))
                
    except Exception as e:
        logger.error(f"Error cleaning up stale sessions: {e}")

# Recheck quiet sockets as well as every private outbound delivery.
SESSION_RECHECK_SECONDS = 10

# WebSocket endpoint for real-time chat
@app.websocket("/api/ws/{user_id}/{session_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, session_id: str):
    if not user_id or not session_id or len(user_id) > 240 or len(session_id) > 240:
        await websocket.close(code=1008, reason="Invalid user or session")
        return
    user = await db.users.find_one({"id": user_id})
    active = (user or {}).get("active_session_id")
    if not isinstance(active, str) or not active or not secrets.compare_digest(active.encode(), session_id.encode()):
        await websocket.close(code=1008, reason="Invalid user or session")
        return
    if not active_membership(user, datetime.utcnow()):
        await websocket.accept()
        await websocket.close(code=4403, reason="membership_required")
        return

    await manager.connect(websocket, user_id, session_id)
    try:
        # Login can replace a session while the socket handshake is in flight.
        online_update = await db.users.update_one(
            {"id": user_id, "active_session_id": session_id},
            {"$set": {"is_online": True, "last_seen": datetime.utcnow()}}
        )
        if online_update.matched_count != 1:
            await manager.revoke_connection(websocket, user_id)
            return

        online_users = await db.users.find({"is_online": True}).to_list(1000)
        clean_users = [{
            "id": member["id"], "username": member["username"],
            "real_name": member.get("real_name"), "screen_name": member.get("screen_name"),
            "is_admin": member.get("is_admin", False), "avatar_url": member.get("avatar_url"),
            "last_seen": member.get("last_seen")
        } for member in online_users]
        delivered = await manager.send_personal_message(json.dumps({
            "type": "online_users", "users": clean_users
        }, default=str), websocket)
        if not delivered:
            return

        user_join_data = {
            "id": user["id"], "username": user["username"],
            "real_name": user.get("real_name"), "screen_name": user.get("screen_name"),
            "is_admin": user.get("is_admin", False), "avatar_url": user.get("avatar_url")
        }
        await manager.broadcast(json.dumps({
            "type": "user_joined", "user": user_join_data
        }, default=str))

        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=SESSION_RECHECK_SECONDS)
            except asyncio.TimeoutError:
                data = None
            if not await manager.validate_connection(websocket):
                break
            heartbeat_update = await db.users.update_one(
                {"id": user_id, "active_session_id": session_id},
                {"$set": {"is_online": True, "last_seen": datetime.utcnow()}}
            )
            if heartbeat_update.matched_count != 1:
                await manager.revoke_connection(websocket, user_id)
                break
            if data is not None:
                try:
                    message = json.loads(data)
                except (TypeError, ValueError):
                    continue
                if isinstance(message, dict) and message.get("type") == "heartbeat":
                    await manager.send_personal_message(json.dumps({"type": "heartbeat_ack"}), websocket)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.warning("Chat connection ended for user %s", user_id)
        try:
            await websocket.close(code=1011, reason="Connection unavailable")
        except Exception:
            pass
    finally:
        manager.disconnect(websocket, user_id)
        # Another tab on this same login can remain connected. A replaced login
        # must never change the replacement's presence or send a false user_left.
        if not any(identity == (user_id, session_id) for identity in manager.connection_sessions.values()):
            offline_update = await db.users.update_one(
                {"id": user_id, "active_session_id": session_id, "is_online": True},
                {"$set": {"is_online": False, "last_seen": datetime.utcnow()}}
            )
            if offline_update.modified_count:
                await manager.broadcast(json.dumps({"type": "user_left", "user_id": user_id}))

# Define Enums
class UserStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TRIAL = "trial"
    TRIAL_EXPIRED = "trial_expired"

class UserRole(str, Enum):
    MEMBER = "member"
    MODERATOR = "moderator"
    ADMIN = "admin"
    BOT = "bot"

class NotificationType(str, Enum):
    FOLLOW = "follow"
    REPLY = "reply"
    REACTION = "reaction"
    ACHIEVEMENT = "achievement"
    TRADE_ALERT = "trade_alert"

class Notification(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str  # User who receives the notification
    type: NotificationType
    title: str
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)  # Additional data (user IDs, etc.)
    read: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None  # Optional expiration for temporary notifications

# Define Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: str
    real_name: Optional[str] = None  # NEW: Real name field
    screen_name: Optional[str] = None  # NEW: Screen name field
    membership_plan: Optional[str] = None  # NEW: Membership plan field
    is_admin: bool = False
    role: UserRole = UserRole.MEMBER  # NEW: Role field with enum
    status: UserStatus = UserStatus.PENDING
    avatar_url: Optional[str] = None
    total_profit: float = 0.0
    win_percentage: float = 0.0
    trades_count: int = 0
    average_gain: float = 0.0
    is_online: bool = False  # NEW: Online status
    last_seen: Optional[datetime] = None  # NEW: Last seen timestamp
    active_session_id: Optional[str] = Field(default=None, exclude=True)
    session_created_at: Optional[datetime] = Field(default=None, exclude=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    
    # NEW: Experience Points System
    experience_points: int = 0
    level: int = 1
    daily_login_streak: int = 0
    last_login_date: Optional[str] = None  # YYYY-MM-DD format
    
    # Trial system fields
    trial_start_date: Optional[datetime] = None
    trial_end_date: Optional[datetime] = None
    trial_upgrade_email_sent: Optional[bool] = False
    
    # NEW: Profile Customization
    profile_banner: Optional[str] = None  # URL or base64
    bio: Optional[str] = None
    trading_style_tags: List[str] = Field(default_factory=list)
    
    # NEW: Theme Customization
    custom_theme: Optional[Dict[str, Any]] = None
    active_theme_name: str = "dark"  # default theme
    
    # NEW: Achievements
    achievements: List[str] = Field(default_factory=list)  # Achievement IDs
    achievement_progress: Dict[str, int] = Field(default_factory=dict)  # Progress tracking
    
    # NEW: Location and Social Features
    location: Optional[str] = None  # City, Country or custom location
    show_location: bool = True  # Privacy setting for location display
    
    # NEW: Follow System
    followers: List[str] = Field(default_factory=list)  # List of user IDs following this user
    following: List[str] = Field(default_factory=list)  # List of user IDs this user follows
    follower_count: int = 0  # Cached count for performance
    following_count: int = 0  # Cached count for performance
    
    # NEW: Referral System
    referral_code: Optional[str] = None  # Unique referral code for this user
    referred_by: Optional[str] = None  # User ID who referred this user
    referrals: List[str] = Field(default_factory=list)  # List of user IDs referred by this user
    successful_referrals: int = 0  # Count of successful referrals
    
    # NEW: Cash Prize System
    cash_prizes: List[Dict[str, Any]] = Field(default_factory=list)  # Cash prizes earned
    total_cash_earned: float = 0.0  # Total cash prizes earned
    pending_cash_review: List[Dict[str, Any]] = Field(default_factory=list)  # Pending admin review

class AuthenticatedUser(User):
    """Only a successful password-verified login may return session credentials."""
    active_session_id: str = Field(exclude=False)
    session_created_at: Optional[datetime] = Field(default=None, exclude=False)

class UserCreate(BaseModel):
    username: str
    email: str
    real_name: str  # NEW: Required real name
    membership_plan: str
    is_trial: Optional[bool] = False  # Legacy input retained so trial attempts can be rejected explicitly.
    password: str
    referral_code: Optional[str] = None  # Optional referral code of referring user
    practice_event_id: Optional[str] = Field(default=None, min_length=1, max_length=80)

class CashPrizeReview(BaseModel):
    user_id: str
    achievement_id: str
    amount: float
    status: str  # "approved", "rejected"
    admin_notes: Optional[str] = None

class ReferralInfo(BaseModel):
    referral_code: str
    referred_users: List[Dict[str, Any]]

class UserLogin(BaseModel):
    username: str
    password: str

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)

class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    new_password: str = Field(min_length=8, max_length=72)

class UserApproval(BaseModel):
    user_id: str
    approved: bool
    admin_id: str
    role: Optional[UserRole] = UserRole.MEMBER  # NEW: Role assignment during approval

class UserRoleUpdate(BaseModel):
    # Both historic field names are accepted; the authenticated actor, never a
    # supplied administrator ID, controls authorization.
    user_id: Optional[str] = None
    new_role: Optional[UserRole] = None
    role: Optional[UserRole] = None
    admin_id: Optional[str] = None

# NEW: XP and Achievement Models
class XPAction(BaseModel):
    user_id: str
    action: str  # 'daily_login', 'trade', 'chat_message', etc.
    points: int
    metadata: Optional[Dict[str, Any]] = None

class Achievement(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    points_reward: int
    requirement_type: str  # 'count', 'streak', 'value', 'milestone'
    requirement_value: int
    category: str  # 'trading', 'social', 'platform'

class ProfileUpdate(BaseModel):
    bio: Optional[str] = None
    trading_style_tags: Optional[List[str]] = None
    profile_banner: Optional[str] = None
    avatar_url: Optional[str] = None  # Add profile picture support
    location: Optional[str] = None  # Add location support
    show_location: Optional[bool] = None  # Privacy setting for location

class FollowRequest(BaseModel):
    target_user_id: str

class PublicProfileRequest(BaseModel):
    user_id: str

class ThemeUpdate(BaseModel):
    theme_name: str
    custom_colors: Optional[Dict[str, str]] = None

class ExistingProfileUpdate(BaseModel):
    real_name: Optional[str] = None
    screen_name: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None

class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    username: str
    content: str
    content_type: str = "text"  # NEW: "text", "image", "gif"
    is_admin: bool = False
    avatar_url: Optional[str] = None
    real_name: Optional[str] = None  # NEW: Include real name
    screen_name: Optional[str] = None  # NEW: Include screen name
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    highlighted_tickers: List[str] = []
    reply_to_id: Optional[str] = None  # NEW: ID of message being replied to
    reply_to: Optional[dict] = None  # NEW: Original message data for display
    text_content: Optional[str] = None  # Text accompanying an image message

class MessageCreate(BaseModel):
    content: str
    content_type: str = "text"  # NEW: Support for different content types
    user_id: str
    reply_to_id: Optional[str] = None  # NEW: Support for replies
    text_content: Optional[str] = None  # Text accompanying an image message

class Team(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    admin_ids: List[str] = []
    member_ids: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)

class TeamCreate(BaseModel):
    name: str
    admin_id: str

class StockTicker(BaseModel):
    symbol: str
    price: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[str] = None

class PaperTrade(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    symbol: str
    action: str  # "BUY" or "SELL"
    quantity: int
    price: float
    price_source: str = "legacy_unverified"
    price_verified: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None
    position_id: Optional[str] = None  # Links to open position
    is_closed: bool = False
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

class Position(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    symbol: str
    quantity: int
    avg_price: float
    entry_price: float
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    is_open: bool = True
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    notes: Optional[str] = None
    auto_close_reason: Optional[str] = None  # "STOP_LOSS", "TAKE_PROFIT", "MANUAL"

class PaperTradeCreate(BaseModel):
    symbol: str
    action: str
    quantity: int
    price: float
    notes: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

class PositionAction(BaseModel):
    action: str  # "BUY_MORE", "SELL_PARTIAL", "SELL_ALL"
    quantity: Optional[int] = None
    price: Optional[float] = None

def format_price_display(price):
    """Format price display based on price range for better precision"""
    if price is None:
        return "0.00"
    
    price = float(price)
    
    if price == 0:
        return "0.00"
    elif price < 0.01:
        # For very small prices, show up to 8 decimal places (remove trailing zeros)
        return f"{price:.8f}".rstrip('0').rstrip('.')
    elif price < 1:
        # For prices under $1, show up to 4 decimal places
        return f"{price:.4f}".rstrip('0').rstrip('.')
    else:
        # For regular prices, show 2 decimal places
        return f"{price:.2f}"

# NEW: Achievement System Definitions
ACHIEVEMENTS = {
    "first_blood": {
        "id": "first_blood",
        "name": "First Blood",
        "description": "Make your first profitable trade",
        "icon": "🎯",
        "points_reward": 100,
        "requirement_type": "milestone",
        "requirement_value": 1,
        "category": "trading"
    },
    "diamond_hands": {
        "id": "diamond_hands", 
        "name": "Diamond Hands",
        "description": "Hold a position for 30+ days",
        "icon": "💎",
        "points_reward": 200,
        "requirement_type": "milestone",
        "requirement_value": 30,
        "category": "trading"
    },
    "hot_streak": {
        "id": "hot_streak",
        "name": "Hot Streak", 
        "description": "5 profitable trades in a row",
        "icon": "🔥",
        "points_reward": 150,
        "requirement_type": "streak",
        "requirement_value": 5,
        "category": "trading"
    },
    "chatterbox": {
        "id": "chatterbox",
        "name": "Chatterbox",
        "description": "Send 100 chat messages", 
        "icon": "💬",
        "points_reward": 75,
        "requirement_type": "count",
        "requirement_value": 100,
        "category": "social"
    },
    "heart_giver": {
        "id": "heart_giver",
        "name": "Heart Giver",
        "description": "Give 50 heart reactions",
        "icon": "❤️", 
        "points_reward": 50,
        "requirement_type": "count",
        "requirement_value": 50,
        "category": "social"
    },
    "dedication": {
        "id": "dedication",
        "name": "Dedication",
        "description": "30-day login streak",
        "icon": "🗓️",
        "points_reward": 300,
        "requirement_type": "streak", 
        "requirement_value": 30,
        "category": "platform"
    },
    "profit_1k": {
        "id": "profit_1k",
        "name": "Profit Milestone - $1K",
        "description": "Reach $1,000 in total profit",
        "icon": "💰",
        "points_reward": 250,
        "requirement_type": "value",
        "requirement_value": 1000,
        "category": "trading"
    },
    "profit_2k": {
        "id": "profit_2k",
        "name": "Profit Milestone - $2K",
        "description": "Reach $2,000 in total profit",
        "icon": "💎",
        "points_reward": 400,
        "requirement_type": "value",
        "requirement_value": 2000,
        "category": "trading"
    },
    "profit_3k": {
        "id": "profit_3k",
        "name": "Profit Milestone - $3K",
        "description": "Reach $3,000 in total profit",
        "icon": "🏆",
        "points_reward": 600,
        "requirement_type": "value",
        "requirement_value": 3000,
        "category": "trading"
    },
    "profit_4k": {
        "id": "profit_4k",
        "name": "Profit Milestone - $4K",
        "description": "Reach $4,000 in total profit",
        "icon": "👑",
        "points_reward": 800,
        "requirement_type": "value",
        "requirement_value": 4000,
        "category": "trading"
    },
    "profit_5k": {
        "id": "profit_5k",
        "name": "Profit Milestone - $5K",
        "description": "Reach $5,000 in total profit",
        "icon": "🚀",
        "points_reward": 1000,
        "requirement_type": "value",
        "requirement_value": 5000,
        "category": "trading"
    },
    "diversification_master": {
        "id": "diversification_master",
        "name": "Diversification Master", 
        "description": "Own 10+ different stocks",
        "icon": "🎪",
        "points_reward": 100,
        "requirement_type": "count",
        "requirement_value": 10,
        "category": "trading"
    },
    "team_member_3m": {
        "id": "team_member_3m",
        "name": "Team Player - 3 Months",
        "description": "3 months as a team member",
        "icon": "🥉",
        "points_reward": 150,
        "requirement_type": "duration",
        "requirement_value": 90,  # 90 days
        "category": "membership"
    },
    "team_member_8m": {
        "id": "team_member_8m", 
        "name": "Team Veteran - 8 Months",
        "description": "8 months as a team member",
        "icon": "🥈",
        "points_reward": 400,
        "requirement_type": "duration", 
        "requirement_value": 240,  # 240 days
        "category": "membership"
    },
    "team_member_12m": {
        "id": "team_member_12m",
        "name": "Team Legend - 12 Months", 
        "description": "12 months as a team member",
        "icon": "🥇",
        "points_reward": 600,
        "requirement_type": "duration",
        "requirement_value": 365,  # 365 days
        "category": "membership"
    },
    "referral_master": {
        "id": "referral_master",
        "name": "Referral Master",
        "description": "Welcome a new member to the community.",
        "icon": "🤝",
        "points_reward": 200,
        "requirement_type": "referral",
        "requirement_value": 1,
        "category": "growth",
        "cash_prize_eligible": False
    }
}

# NEW: XP Level System
def get_level_from_xp(xp: int) -> int:
    """Calculate user level based on XP"""
    if xp < 500:
        return 1
    elif xp < 1500:
        return 2
    elif xp < 5000:
        return 3
    elif xp < 15000:
        return 4
    else:
        return 5

def get_xp_for_next_level(current_xp: int) -> int:
    """Get XP needed for next level"""
    level = get_level_from_xp(current_xp)
    level_thresholds = [0, 500, 1500, 5000, 15000, 50000]  # Level 6+ for future
    
    if level >= len(level_thresholds) - 1:
        return 0  # Max level reached
    
    return level_thresholds[level] - current_xp

# NEW: XP System Functions
async def award_xp(user_id: str, action: str, points: int, metadata: dict = None):
    """Award XP to user and check for level ups and achievements"""
    try:
        user = await db.users.find_one({"id": user_id})
        if not user:
            return
        
        old_level = get_level_from_xp(user.get("experience_points", 0))
        new_xp = user.get("experience_points", 0) + points
        new_level = get_level_from_xp(new_xp)
        
        # Update user XP and level
        await db.users.update_one(
            {"id": user_id},
            {
                "$set": {
                    "experience_points": new_xp,
                    "level": new_level
                }
            }
        )
        
        # Check for level up
        if new_level > old_level:
            await handle_level_up(user_id, new_level, old_level)
        
        # Check for achievements (but not for achievement_unlocked to prevent recursion)
        if action != "achievement_unlocked":
            await check_achievements(user_id, action, metadata or {})
        
        logger.info(f"Awarded {points} XP to user {user_id} for action: {action}")
        
    except Exception as e:
        logger.error(f"Error awarding XP: {e}")

async def handle_level_up(user_id: str, new_level: int, old_level: int):
    """Handle level up rewards and notifications"""
    try:
        level_rewards = {
            2: "Unlocked custom themes!",
            3: "Unlocked profile banners!",
            4: "Unlocked trading style tags!",
            5: "Unlocked exclusive themes & badges!"
        }
        
        if new_level in level_rewards:
            # Create level up notification
            await create_user_notification(
                user_id=user_id,
                notification_type="level_up",
                title=f"Level Up! 🎉",
                message=f"Congratulations! You've reached Level {new_level}! {level_rewards[new_level]}",
                data={
                    "new_level": new_level,
                    "old_level": old_level,
                    "reward": level_rewards[new_level],
                    "action": "level_up"
                }
            )
            logger.info(f"User {user_id} leveled up to {new_level}: {level_rewards[new_level]}")
            
    except Exception as e:
        logger.error(f"Error handling level up: {e}")

async def share_achievement_in_chat(user_id: str, achievement: dict):
    """Share achievement in chat when unlocked"""
    try:
        # Get user info
        user = await db.users.find_one({"id": user_id})
        if not user:
            return
            
        # Create achievement message
        message = Message(
            user_id=user_id,
            username=user.get("username", ""),
            content=f"🏆 Achievement Unlocked: {achievement['name']} - {achievement['description']} {achievement['icon']}",
            is_admin=False,
            avatar_url=user.get("avatar_url"),
            real_name=user.get("real_name"),
            screen_name=user.get("screen_name")
        )
        
        # Save message to database
        await db.messages.insert_one(message.dict())
        
        # Broadcast to all connected users
        await manager.broadcast(json.dumps({
            "type": "message",
            "data": message.dict()
        }, default=str))
        
    except Exception as e:
        logger.error(f"Error sharing achievement in chat: {e}")

async def check_achievements(user_id: str, action: str, metadata: dict):
    """Check and award achievements based on user actions - OPTIMIZED VERSION"""
    try:
        logger.info(f"check_achievements called for user {user_id}, action: {action}")
        
        # PERFORMANCE OPTIMIZATION: Skip heavy achievement checking for login actions
        # These are now handled in background via process_login_rewards_async
        if action == "daily_login":
            return
            
        # Use atomic operation to increment counters directly in the database
        if action == "chat_message":
            await db.users.update_one(
                {"id": user_id},
                {"$inc": {"achievement_progress.chatterbox_count": 1}}
            )
        elif action == "heart_reaction":
            await db.users.update_one(
                {"id": user_id},
                {"$inc": {"achievement_progress.heart_giver_count": 1}}
            )
            logger.info(f"🔥 ATOMIC INCREMENT: heart_giver_count +1 for user {user_id}")
        elif action == "profitable_trade":
            await db.users.update_one(
                {"id": user_id},
                {"$inc": {"achievement_progress.profitable_trades": 1}}
            )
        elif action == "referral_success":
            await db.users.update_one(
                {"id": user_id},
                {"$inc": {"achievement_progress.successful_referrals": 1}}
            )
        
        # PERFORMANCE OPTIMIZATION: Only check specific achievements based on action
        # Don't fetch full user data and check ALL achievements every time
        achievements_to_check = []
        
        if action == "chat_message":
            achievements_to_check = ["chatterbox"]
        elif action == "heart_reaction":
            achievements_to_check = ["heart_giver"]  
        elif action == "profitable_trade":
            achievements_to_check = ["first_blood"]
        elif action == "referral_success":
            achievements_to_check = ["referral_master"]
        elif action == "achievement_unlocked":
            # Skip recursive achievement checking
            return
        
        if not achievements_to_check:
            return
            
        # Fetch minimal user data needed for specific achievements
        user = await db.users.find_one(
            {"id": user_id}, 
            {
                "achievements": 1, 
                "achievement_progress": 1,
                "total_profit": 1,
                "successful_referrals": 1
            }
        )
        if not user:
            logger.error(f"User {user_id} not found in check_achievements")
            return
            
        user_achievements = user.get("achievements", [])
        progress = user.get("achievement_progress", {})
        
        logger.info(f"Updated progress for {user_id}: {progress}")
        
        # PERFORMANCE OPTIMIZATION: Check only relevant achievements, not ALL achievements
        new_achievements = []
        
        for achievement_id in achievements_to_check:
            if achievement_id in user_achievements:
                continue  # Already earned
                
            achievement = ACHIEVEMENTS[achievement_id]
            earned = False
            
            if achievement_id == "chatterbox" and progress.get("chatterbox_count", 0) >= 100:
                earned = True
            elif achievement_id == "heart_giver" and progress.get("heart_giver_count", 0) >= 50:
                earned = True
                logger.info(f"🏆 HEART_GIVER ACHIEVEMENT EARNED! Count: {progress.get('heart_giver_count', 0)}")
            elif achievement_id == "first_blood" and progress.get("profitable_trades", 0) >= 1:
                earned = True
            elif achievement_id == "referral_master":
                # Check if user has successfully referred someone
                successful_referrals = user.get("successful_referrals", 0)
                if successful_referrals >= 1:
                    earned = True
                
            if earned:
                new_achievements.append(achievement_id)
                await award_xp(user_id, "achievement_unlocked", achievement["points_reward"])
                
                # Referral badges and XP remain available. Cash rewards are
                # outside this release; do not create pending money awards.
        
        # Update achievements if any new ones were earned
        if new_achievements:
            logger.info(f"🏆 User {user_id} earned NEW achievements: {new_achievements}")
            
            await db.users.update_one(
                {"id": user_id},
                {
                    "$addToSet": {
                        "achievements": {"$each": new_achievements}
                    }
                }
            )
            
            # Auto-share achievements in chat
            for achievement_id in new_achievements:
                achievement = ACHIEVEMENTS[achievement_id]
                logger.info(f"📢 Sharing achievement {achievement_id} in chat for user {user_id}")
                await share_achievement_in_chat(user_id, achievement)
                
                # Create achievement notification for the user
                await create_user_notification(
                    user_id=user_id,
                    notification_type="achievement",
                    title="Achievement Unlocked! 🏆",
                    message=f"Congratulations! You've unlocked: {achievement['name']} - {achievement['description']} {achievement['icon']}",
                    data={
                        "achievement_id": achievement_id,
                        "achievement_name": achievement['name'],
                        "achievement_description": achievement['description'],
                        "achievement_icon": achievement['icon'],
                        "points_reward": achievement['points_reward'],
                        "action": "achievement_unlocked"
                    }
                )
            
    except Exception as e:
        logger.error(f"Error checking achievements: {e}")

def format_pnl_display(pnl):
    """Format P&L display with appropriate precision"""
    if pnl is None:
        return "0.00"
    
    pnl = float(pnl)
    
    if abs(pnl) < 0.01:
        # For very small P&L, show more precision
        return f"{pnl:.6f}".rstrip('0').rstrip('.')
    else:
        # For regular P&L, show 2 decimal places
        return f"{pnl:.2f}"

# Utility function to extract stock tickers from message
def extract_stock_tickers(content: str) -> List[str]:
    """Extract stock tickers that start with $ from message content"""
    pattern = r'\$([A-Z]{1,5})'
    matches = re.findall(pattern, content.upper())
    return matches

async def handle_message_mentions(message_content: str, sender_user: dict, message_id: str):
    """Handle @username mentions in messages"""
    try:
        import re
        mention_pattern = r'@(\w+)'
        mentioned_usernames = re.findall(mention_pattern, message_content)
        
        if mentioned_usernames:
            # Remove duplicates and exclude self-mentions
            mentioned_usernames = list(set(mentioned_usernames))
            sender_username = sender_user.get("username")
            
            for mentioned_username in mentioned_usernames:
                if mentioned_username.lower() != sender_username.lower():  # Case-insensitive comparison
                    # Find the mentioned user (case-insensitive)
                    mentioned_user = await db.users.find_one({
                        "username": {"$regex": f"^{mentioned_username}$", "$options": "i"}
                    })
                    if mentioned_user:
                        sender_name = sender_user.get("screen_name") or sender_user.get("username")
                        await create_user_notification(
                            user_id=mentioned_user["id"],
                            notification_type="mention",
                            title="You were mentioned! 👋",
                            message=f"{sender_name} mentioned you in chat: \"{message_content[:100]}{'...' if len(message_content) > 100 else ''}\"",
                            data={
                                "mentioner_id": sender_user["id"],
                                "mentioner_name": sender_name,
                                "mentioner_avatar": sender_user.get("avatar_url"),
                                "message_id": message_id,
                                "message_content": message_content,
                                "action": "mention"
                            }
                        )
                        logger.info(f"Created mention notification for {mentioned_user['username']} from {sender_name}")
                        
    except Exception as e:
        logger.error(f"Error handling message mentions: {e}")

# Utility functions for authentication and image processing
def validate_new_password(password: str):
    if not isinstance(password, str) or len(password) < 8 or len(password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Use a password of at least 8 characters and no more than 72 UTF-8 bytes.")

def password_reset_context(user):
    """Bind a recovery link to the exact email and credential state it proved.

    Keep only a digest beside the token. The comparison filter also checks field
    presence, so an absent credential cannot match one added during an await.
    """
    fields = ("email", "password_hash", "hashed_password", "password")
    state = [[field, field in user, type(user.get(field)).__name__, user.get(field)] for field in fields]
    digest = hashlib.sha256(json.dumps(state, sort_keys=True, separators=(",", ":"),
                                      default=str).encode("utf-8")).hexdigest()
    guard = {field: {"$exists": True, "$eq": user[field]} if field in user else {"$exists": False}
             for field in fields}
    return digest, guard

async def require_profile_owner(request: Request, user_id: str):
    """Authenticate changes to the recovery email using the existing session."""
    claimed_user = request.headers.get("x-user-id")
    token = request.headers.get("x-session-id", "")
    authorization = request.headers.get("authorization", "")
    if not token and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    if claimed_user and claimed_user != user_id:
        raise HTTPException(status_code=403, detail="This profile belongs to another member.")
    user = await db.users.find_one({"id": user_id})
    stored_token = (user or {}).get("active_session_id")
    if not token or len(token) > 240 or not isinstance(stored_token, str) or not stored_token or not secrets.compare_digest(token.encode(), stored_token.encode()):
        raise HTTPException(status_code=401, detail="Please sign in again.")
    return user

async def require_authenticated_admin(request: Request, claimed_admin_id=None):
    actor_id = request.headers.get("x-user-id", "")
    if not actor_id or len(actor_id) > 240:
        raise HTTPException(status_code=401, detail="Please sign in again.")
    actor = await require_profile_owner(request, actor_id)
    if (not actor.get("is_admin") or actor.get("status") != "approved"
            or actor.get("disabled") is True or (claimed_admin_id is not None and claimed_admin_id != actor_id)):
        raise HTTPException(status_code=403, detail="Administrator access required.")
    return actor

# Applied only to the legacy API router. The Nautilus router has its own member
# and publisher authentication. Match exact operation + route templates, never
# broad prefixes such as /users, /bot, or /admin.
LEGACY_SESSION_EXEMPT_OPERATIONS = frozenset({
    ("GET", "/api/"),
    ("GET", "/api/health"),
    ("POST", "/api/users/register"),
    ("POST", "/api/users/login"),
    ("POST", "/api/users/reset-password-request"),
    ("POST", "/api/users/reset-password-direct"),
    ("POST", "/api/users/reset-password-confirm"),
    ("GET", "/api/referral/{referral_code}"),
    # External stock intake uses its own server-side Zapier shared secret.
    ("POST", "/api/bot/message"),
    ("POST", "/api/bot/email-webhook"),
    # These endpoints verify the specific presented session themselves; status
    # returns a boolean and stale logout is an idempotent no-op.
    ("GET", "/api/users/{user_id}/session-status"),
    ("POST", "/api/users/logout"),
})

async def require_legacy_active_session(request: Request):
    """Bind every legacy member operation to its verified actor and role.

    Authentication alone is insufficient: older handlers also accept user/admin
    IDs in paths, query strings or JSON. Those values must never select another
    actor merely because the caller has a valid membership of their own.
    """
    if request.method == "OPTIONS":
        return
    route_path = getattr(request.scope.get("route"), "path", None)
    operation = (request.method, route_path)
    if operation in LEGACY_SESSION_EXEMPT_OPERATIONS:
        return
    actor_id = request.headers.get("x-user-id", "")
    if not actor_id or len(actor_id) > 240:
        raise HTTPException(status_code=401, detail="Please sign in again.")
    actor = await require_profile_owner(request, actor_id)
    request.state.session_user = actor
    is_admin = bool(actor.get("is_admin") and actor.get("status") == "approved"
                    and actor.get("disabled") is not True)

    # Administrative routes include older operations outside the /admin prefix.
    admin_operation = (route_path or "").startswith("/api/admin/") or operation in {
        ("GET", "/api/users"), ("GET", "/api/users/pending"),
        ("POST", "/api/users/approve"), ("POST", "/api/users/change-role"),
        ("POST", "/api/users/{user_id}/role"), ("DELETE", "/api/users/{user_id}"),
        ("POST", "/api/users/{user_id}/award-xp"),
        ("GET", "/api/email/check"), ("GET", "/api/email/test"),
        ("GET", "/api/fcm/status"), ("POST", "/api/upload-video"),
        ("DELETE", "/api/messages/{message_id}"),
        ("DELETE", "/api/messages/cleanup/debug"),
    }
    if admin_operation and not is_admin:
        raise HTTPException(status_code=403, detail="Administrator access required.")
    if not active_membership(actor, datetime.utcnow()) and not (admin_operation and is_admin):
        # Administrators may still review access if their own paid term ends.
        raise HTTPException(status_code=403, detail=MEMBERSHIP_REQUIRED)

    claimed_admin = request.query_params.get("admin_id")
    if claimed_admin is not None and (not is_admin or claimed_admin != actor_id):
        raise HTTPException(status_code=403, detail="Administrator access required.")

    # Profiles, follower lists and earned social display data are member-visible;
    # private account/ledger/inbox resources and all member writes are owner-only.
    public_member_reads = {
        ("GET", "/api/users/{user_id}/profile"),
        ("GET", "/api/users/{user_id}/profile/public"),
        ("GET", "/api/users/{user_id}/followers"),
        ("GET", "/api/users/{user_id}/following"),
        ("GET", "/api/users/{user_id}/achievements"),
    }
    path_user = request.path_params.get("user_id")
    if (path_user is not None and not admin_operation
            and operation not in public_member_reads and path_user != actor_id):
        raise HTTPException(status_code=403, detail="This resource belongs to another member.")

    query_user = request.query_params.get("user_id")
    # On admin conversion/review routes user_id selects the subject. The legacy
    # message-moderation routes instead name the acting administrator as user_id.
    moderation = operation in {
        ("DELETE", "/api/messages/{message_id}"),
        ("DELETE", "/api/messages/cleanup/debug"),
    }
    if query_user is not None and (not admin_operation or moderation) and query_user != actor_id:
        raise HTTPException(status_code=403, detail="This action belongs to another member.")

    if operation == ("POST", "/api/messages"):
        payload = await request.json()
        if not isinstance(payload, dict) or payload.get("user_id") != actor_id:
            raise HTTPException(status_code=403, detail="Messages must use your signed-in account.")

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password - supports both bcrypt and legacy SHA-256"""
    if not isinstance(hashed, str) or not isinstance(password, str):
        return False
    if hashed.startswith('$2b$') or hashed.startswith('$2a$'):
        try:
            return bcrypt.checkpw(password.encode(), hashed.encode())
        except (ValueError, TypeError):
            return False
    # Legacy SHA-256 fallback
    return hashlib.sha256(password.encode()).hexdigest() == hashed

async def migrate_password_if_needed(user_id: str, password: str, stored_hash: str,
                                     password_field: str = "password_hash", primary_value=None):
    """Canonicalize a verified legacy hash without overwriting a newer password."""
    is_bcrypt = stored_hash.startswith(("$2b$", "$2a$"))
    if is_bcrypt and password_field == "password_hash":
        return stored_hash
    # bcrypt 5 rejects values beyond 72 UTF-8 bytes. A verified historical SHA
    # hash can keep serving its existing long password until the owner resets it.
    new_hash = stored_hash if is_bcrypt or len(password.encode("utf-8")) > 72 else hash_password(password)
    guard = {"id": user_id, password_field: stored_hash}
    if password_field == "hashed_password":
        guard["password_hash"] = primary_value
    result = await db.users.update_one(guard, {
        "$set": {"password_hash": new_hash}, "$unset": {"hashed_password": ""},
    })
    if not result.matched_count:
        raise HTTPException(status_code=401, detail="Credentials changed. Please sign in again.")
    return new_hash

def process_uploaded_image(file_content: bytes, max_size: int = 1024 * 1024) -> str:
    """Process uploaded image and return base64 data URL"""
    if len(file_content) > max_size:
        raise HTTPException(status_code=400, detail="Image too large (max 1MB)")
    
    # Convert to base64 data URL
    base64_content = base64.b64encode(file_content).decode('utf-8')
    return f"data:image/jpeg;base64,{base64_content}"

# One provider-read adapter is shared by ticker cards and legacy portfolios.
try:
    from .stock_quotes import stock_quote_service, QuoteUnavailable, number as quote_number, iso as quote_iso, utcnow as quote_now
except ImportError:
    from stock_quotes import stock_quote_service, QuoteUnavailable, number as quote_number, iso as quote_iso, utcnow as quote_now

async def get_current_stock_price(symbol: str) -> float:
    """Return an execution-eligible quote or fail before a price-based mutation.

    The current last-price endpoint cannot verify market session and delay
    entitlement. Its observations remain displayable but never authorize fills.
    """
    try:
        quote = await stock_quote_service.get_quote(symbol)
    except QuoteUnavailable as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail()) from None
    if not quote.get("execution_eligible") or quote.get("status") != "recent":
        raise HTTPException(status_code=503, detail={
            "code": "quote_not_execution_eligible", "symbol": quote["symbol"],
            "message": "A verified fresh market-session quote is unavailable. Use an explicitly entered manual journal price, or try again after the data integration is verified.",
            "source": quote["source"], "status": quote["status"],
        })
    return quote["price"]

# Utility function to manage positions
async def update_or_create_position(user_id: str, symbol: str, action: str, quantity: int, price: float, trade_id: str, stop_loss: float = None, take_profit: float = None):
    """Update existing position or create new one"""
    existing_position = await db.positions.find_one({
        "user_id": user_id,
        "symbol": symbol.upper(),
        "is_open": True
    })
    
    if action == "BUY":
        if existing_position:
            # Add to existing position
            new_quantity = existing_position["quantity"] + quantity
            new_avg_price = ((existing_position["avg_price"] * existing_position["quantity"]) + (price * quantity)) / new_quantity
            
            # Update stop loss and take profit if provided
            update_data = {
                "quantity": new_quantity,
                "avg_price": round(new_avg_price, 8)  # Higher precision for low-value stocks
            }
            
            if stop_loss is not None:
                update_data["stop_loss"] = stop_loss
            if take_profit is not None:
                update_data["take_profit"] = take_profit
            
            await db.positions.update_one(
                {"id": existing_position["id"]},
                {"$set": update_data}
            )
            
            # Update trade with position_id
            await db.paper_trades.update_one(
                {"id": trade_id},
                {"$set": {"position_id": existing_position["id"]}}
            )
            
            return existing_position["id"]
        else:
            # Create new position
            position = Position(
                user_id=user_id,
                symbol=symbol.upper(),
                quantity=quantity,
                avg_price=price,
                entry_price=price,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            await db.positions.insert_one(position.dict())
            
            # Update trade with position_id
            await db.paper_trades.update_one(
                {"id": trade_id},
                {"$set": {"position_id": position.id}}
            )
            
            return position.id
    
    elif action == "SELL" and existing_position:
        if quantity >= existing_position["quantity"]:
            # Close entire position
            await db.positions.update_one(
                {"id": existing_position["id"]},
                {"$set": {
                    "is_open": False,
                    "closed_at": datetime.utcnow(),
                    "quantity": 0,
                    "auto_close_reason": "MANUAL"
                }}
            )
            
            # Update trade with position_id
            await db.paper_trades.update_one(
                {"id": trade_id},
                {"$set": {"position_id": existing_position["id"], "is_closed": True}}
            )
        else:
            # Partial close
            new_quantity = existing_position["quantity"] - quantity
            await db.positions.update_one(
                {"id": existing_position["id"]},
                {"$set": {"quantity": new_quantity}}
            )
            
            # Update trade with position_id
            await db.paper_trades.update_one(
                {"id": trade_id},
                {"$set": {"position_id": existing_position["id"]}}
            )
        
        return existing_position["id"]
    
    return None

# Utility function to update position P&L and check for auto-close triggers
async def update_positions_pnl(user_id: str):
    """Mark observed valuation with provenance; never synthesize or auto-fill.

    Automatic stop/take-profit execution is suspended until a verified market
    session, data delay and paper-fill policy are integrated. A GET request must
    not close a position using an unqualified last-price observation.
    """
    open_positions = await db.positions.find({"user_id": user_id, "is_open": True}).to_list(1000)
    for position in open_positions:
        try:
            quote = await stock_quote_service.get_quote(position["symbol"])
        except QuoteUnavailable as error:
            # Retain previous valuation numbers and their observation timestamps.
            # Legacy numbers without provenance are explicitly unverified.
            await db.positions.update_one(
                {"id": position["id"], "user_id": user_id, "is_open": True},
                {"$set": {"quote": {**error.detail(), "received_at": quote_iso(quote_now()),
                                    "source_timestamp": None, "execution_eligible": False},
                          "valuation_status": "unavailable", "execution_eligible": False,
                          "price_provenance": position.get("price_provenance", "legacy_unverified")}},
            )
            continue
        try:
            unrealized_pnl = (quote["price"] - position["avg_price"]) * position["quantity"]
        except (TypeError, ValueError, OverflowError):
            unrealized_pnl = None
        if quote_number(unrealized_pnl) is None:
            # Even finite inputs can overflow when calculating a position value.
            # Never persist NaN/Infinity or erase the last valid valuation.
            error = QuoteUnavailable("valuation_invalid", "A finite position valuation could not be calculated.", position["symbol"])
            await db.positions.update_one(
                {"id": position["id"], "user_id": user_id, "is_open": True},
                {"$set": {"quote": {**error.detail(), "received_at": quote["received_at"],
                                    "source_timestamp": quote["source_timestamp"], "execution_eligible": False},
                          "valuation_status": "unavailable", "execution_eligible": False,
                          "price_provenance": position.get("price_provenance", "legacy_unverified")}},
            )
            continue
        await db.positions.update_one(
            {"id": position["id"], "user_id": user_id, "is_open": True,
             "quantity": position["quantity"], "avg_price": position["avg_price"]},
            {"$set": {"current_price": quote["price"], "unrealized_pnl": round(unrealized_pnl, 8),
                      "quote": quote, "valuation_status": quote["status"],
                      "valuation_as_of": quote["source_timestamp"], "valuation_received_at": quote["received_at"],
                      "price_provenance": "provider_observation", "execution_eligible": False}},
        )

# Utility function to calculate user trading performance
async def calculate_user_performance(user_id: str) -> dict:
    """Calculate trading performance metrics for a user"""
    trades = await db.paper_trades.find({"user_id": user_id}).to_list(1000)
    
    if not trades:
        return {
            "total_profit": 0.0,
            "total_pnl": 0.0,  # Frontend compatibility
            "win_percentage": 0.0,
            "win_rate": 0.0,  # Frontend compatibility
            "trades_count": 0,
            "average_gain": 0.0
        }
    
    # Group trades by symbol to calculate profit/loss
    positions = {}
    completed_trades = []
    
    for trade in sorted(trades, key=lambda x: x["timestamp"]):
        symbol = trade["symbol"]
        if symbol not in positions:
            positions[symbol] = {"shares": 0, "total_cost": 0}
        
        if trade["action"] == "BUY":
            positions[symbol]["shares"] += trade["quantity"]
            positions[symbol]["total_cost"] += trade["quantity"] * trade["price"]
        elif trade["action"] == "SELL" and positions[symbol]["shares"] > 0:
            # Calculate profit/loss for this sell
            avg_cost = positions[symbol]["total_cost"] / positions[symbol]["shares"] if positions[symbol]["shares"] > 0 else 0
            sell_quantity = min(trade["quantity"], positions[symbol]["shares"])
            profit_loss = (trade["price"] - avg_cost) * sell_quantity
            
            completed_trades.append({
                "profit_loss": profit_loss,
                "is_profitable": profit_loss > 0
            })
            
            # Update position
            sold_cost = (avg_cost * sell_quantity)  # Cost of shares sold at average cost
            positions[symbol]["shares"] -= sell_quantity
            positions[symbol]["total_cost"] -= sold_cost
            
            # If no shares left, reset total_cost to 0
            if positions[symbol]["shares"] <= 0:
                positions[symbol]["total_cost"] = 0
    
    if not completed_trades:
        return {
            "total_profit": 0.0,
            "total_pnl": 0.0,  # Frontend compatibility
            "win_percentage": 0.0,
            "win_rate": 0.0,  # Frontend compatibility
            "trades_count": len(trades),
            "average_gain": 0.0
        }
    
    total_profit = sum(trade["profit_loss"] for trade in completed_trades)
    winning_trades = sum(1 for trade in completed_trades if trade["is_profitable"])
    win_percentage = (winning_trades / len(completed_trades)) * 100 if completed_trades else 0
    average_gain = total_profit / len(completed_trades) if completed_trades else 0
    
    return {
        "total_profit": round(total_profit, 8),  # Higher precision for low-value stocks
        "total_pnl": round(total_profit, 8),  # Frontend compatibility
        "win_percentage": round(win_percentage, 2),
        "win_rate": round(win_percentage / 100, 4),  # Frontend compatibility (as decimal)
        "trades_count": len(trades),
        "average_gain": round(average_gain, 8)
    }

# API Routes

@api_router.get("/")
async def root():
    return {"message": "CashoutAI API is running", "status": "success"}

@api_router.get("/health")
async def health_check():
    """Health check for monitoring"""
    try:
        await db.command("ping")
        return {"status": "healthy", "db": "connected"}
    except Exception:
        return {"status": "unhealthy", "db": "disconnected"}

@api_router.get("/email/check")
async def check_email_config():
    """Quick check - no email sent, just shows config status"""
    return {
        "email_service_initialized": email_service is not None,
        "env_vars": {
            "RESEND_API_KEY": "***set***" if os.getenv("RESEND_API_KEY") else "NOT SET",
            "SENDER_EMAIL": os.getenv("SENDER_EMAIL", "NOT SET"),
            "ADMIN_EMAIL": os.getenv("ADMIN_EMAIL", "NOT SET"),
        }
    }

@api_router.get("/email/test")
async def test_email_service():
    """Diagnostic endpoint to test email service"""
    if not email_service:
        return {
            "status": "error",
            "message": "Email service failed to initialize",
            "hint": "Check RESEND_API_KEY environment variable"
        }
    
    try:
        admin_email = os.getenv("ADMIN_EMAIL")
        result = await email_service.send_email(
            admin_email,
            "CashOutAi Email Test",
            "Email is working!",
            "<h2>CashOutAi Email Test</h2><p>Resend email service is working correctly!</p>"
        )
        return {
            "status": "success" if result else "failed",
            "message": f"Test email {'sent' if result else 'failed'} to {admin_email}"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@api_router.post("/users/register", response_model=User)
@limiter.limit("5/minute")
async def register_user(request: Request, user_data: UserCreate, background_tasks: BackgroundTasks):
    validate_new_password(user_data.password)
    event_enrollment = user_data.practice_event_id is not None
    if event_enrollment:
        # The explicit server-owned campaign decides eligibility. A plan label
        # alone never creates access, and registration still starts pending.
        practice_event_service.require_open(user_data.practice_event_id)
    # New trial enrollment is paused. This gate applies only to creation; it
    # never rewrites existing members, trials, expiration dates or paid plans.
    # Normalize casing, separators and compatibility characters so an old or
    # crafted client cannot bypass the removed trial option with a label variant.
    import unicodedata
    plan_label = unicodedata.normalize("NFKD", user_data.membership_plan).casefold()
    compact_plan_label = re.sub(r"[^a-z]", "", plan_label)
    if user_data.is_trial or "trial" in compact_plan_label:
        raise HTTPException(
            status_code=403,
            detail="New trial registrations are currently disabled. Choose a paid membership plan; access still requires payment verification and approval.",
        )
    # Registration creates a new identity; it never replaces an existing one.
    # Normalize only this new submission. Legacy records and their stable IDs,
    # relationships, profile, membership and history are not rewritten here.
    username = user_data.username.strip()
    email = user_data.email.strip().lower()
    if not username or not email:
        raise HTTPException(status_code=422, detail="Username and email are required.")
    # Match old case/outer-whitespace variants without renaming existing members.
    existing_user = await db.users.find_one({
        "username": {"$regex": rf"^\s*{re.escape(username)}\s*$", "$options": "i"}
    })
    existing_email = await db.users.find_one({
        "email": {"$regex": rf"^\s*{re.escape(email)}\s*$", "$options": "i"}
    })
    if existing_user or existing_email:
        raise HTTPException(
            status_code=409,
            detail="An account already uses this username or email. Sign in or use password recovery. Contact an administrator if the account needs review.",
        )
    try:
        from .practice_event import ensure_registration_indexes
    except ImportError:
        from practice_event import ensure_registration_indexes
    try:
        await ensure_registration_indexes(db)
    except Exception:
        raise HTTPException(503, detail="Account creation is temporarily unavailable. Please try again later.") from None
    user_data = user_data.model_copy(update={"username": username, "email": email})

    # Keep the password hash in the database record, outside public User output.
    user_dict = user_data.dict()
    user_dict.pop("practice_event_id", None)
    
    # Store referral code for processing after user creation
    referral_code = user_dict.pop('referral_code', None)
    
    password = user_dict.pop('password')
    hashed_password = hash_password(password)
    user_dict['password_hash'] = hashed_password
    
    # Generate unique referral code for this user
    user_dict['referral_code'] = generate_referral_code(user_data.username)
    
    # All public registrations require approval, regardless of username.
    user = User(**user_dict, status=UserStatus.PENDING)
    logger.info(f"📋 NEW USER REGISTERED (pending approval): {user.username} - Plan: {user_data.membership_plan}")
    
    # Send email notification to admin for new registration
    if email_service and not event_enrollment:
        admin_email = os.getenv("ADMIN_EMAIL")
        background_tasks.add_task(
            email_service.send_registration_notification,
            admin_email,
            redact_auth_fields(user_dict)
        )
        logger.info(f"📧 Scheduled admin notification for registration: {user_data.username}")
        
        # Send confirmation email to user
        background_tasks.add_task(
            send_registration_confirmation_to_user,
            user_data.email,
            user_dict.get('real_name', user_data.username)
        )
        logger.info(f"📧 Scheduled user confirmation email to: {user_data.email}")
    elif not event_enrollment:
        logger.warning(f"Email service unavailable. Would send registration notification for user: {user_data.username}")
        
    # Send push notification to admins
    if not event_enrollment:
        background_tasks.add_task(
            send_notification_to_admins,
            "🔔 New User Registration",
            f"{user_dict.get('real_name', user_data.username)} has registered and needs approval",
            {"type": "new_registration", "username": user_data.username}
        )

    # Insert user into database
    try:
        await db.users.insert_one({**user.dict(), "password_hash": hashed_password,
                                   "registration_email_key": email,
                                   "registration_username_key": username.casefold()})
    except Exception as error:
        if getattr(error, "code", None) == 11000:
            raise HTTPException(409, detail="An account already uses this username or email. Sign in or recover your existing account.") from None
        raise
    
    # Event signup is informational: the account is committed, but verification
    # is still pending. Never route it into the paid approval notification.
    if event_enrollment and email_service:
        admin_email = os.getenv("ADMIN_EMAIL")
        if admin_email:
            background_tasks.add_task(
                email_service.send_event_registration_notification,
                admin_email,
                {"username": username, "email": email},
            )

    # Handle referral if provided
    if referral_code:
        background_tasks.add_task(handle_referral_signup, user.id, referral_code)
    
    # Notify admins about new registration via WebSocket (only for regular users, not trials)
    if user.status == UserStatus.PENDING and not event_enrollment:
        await manager.send_admin_notification(json.dumps({
            "type": "new_registration",
            "user": user.dict()
        }, default=str))
    
    return user

@api_router.post("/users/login", response_model=AuthenticatedUser)
async def login_user(login_data: UserLogin):
    # Make username case-insensitive by converting to lowercase
    username_lower = login_data.username.lower()
    user = await db.users.find_one({"username": {"$regex": f"^{re.escape(username_lower)}$", "$options": "i"}})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Older registrations may be missing a persisted hash. They must use the
    # verified email-reset flow; absence of a hash must never grant access.
    password_field, stored_hash = password_record(user)
    if not stored_hash or not verify_password(login_data.password, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials. Use password recovery if needed.")
    if user.get("disabled") is True:
        raise HTTPException(status_code=403, detail="Account access requires administrator review.")
    verified_hash = await migrate_password_if_needed(
        user['id'], login_data.password, stored_hash, password_field, user.get("password_hash"))
    
    user_obj = User(**user)
    
    # Check user status including trial system
    if user_obj.status == UserStatus.PENDING:
        raise HTTPException(status_code=403, detail="Membership is pending payment verification or administrator review. Open billing to review your access.")
    elif user_obj.status == UserStatus.REJECTED:
        raise HTTPException(status_code=403, detail="Account has been rejected")
    elif user_obj.status == UserStatus.TRIAL:
        # Check if trial has expired
        trial_end = utc_datetime(user_obj.trial_end_date)
        if not trial_end or datetime.utcnow() >= trial_end:
            # Convert to trial_expired status
            expected = {"id": user_obj.id, "status": UserStatus.TRIAL,
                        **{field: user[field] if field in user else {"$exists": False}
                           for field in ("trial_end_date", "billing_entitlement", "manual_access_granted", "disabled", "practice_event_grant")}}
            expired = await db.users.update_one(
                expected,
                {"$set": {"status": UserStatus.TRIAL_EXPIRED.value}}
            )
            if expired.modified_count != 1:
                # A concurrent approval/extension wins. Re-login with its fresh
                # state instead of returning a stale trial response/session.
                raise HTTPException(409, detail="Account access changed. Please sign in again.")
            user_obj.status = UserStatus.TRIAL_EXPIRED
            user["status"] = UserStatus.TRIAL_EXPIRED.value
            logger.info(f"⏰ TRIAL EXPIRED: {user_obj.username} - Converting to limited access")

            if not user_obj.trial_upgrade_email_sent:
                asyncio.create_task(send_trial_upgrade_email(user_obj.email, user_obj.real_name))
                await db.users.update_one(
                    {**expected, "status": UserStatus.TRIAL_EXPIRED},
                    {"$set": {"trial_upgrade_email_sent": True}}
                )
    elif user_obj.status not in [UserStatus.APPROVED, UserStatus.TRIAL_EXPIRED]:
        raise HTTPException(status_code=403, detail="Account access denied")
    
    # Generate new session ID
    new_session_id = str(uuid.uuid4())
    
    # PERFORMANCE OPTIMIZATION: Batch all login-related updates into a single operation
    today = datetime.utcnow().strftime('%Y-%m-%d')
    last_login = user.get("last_login_date")
    current_streak = user.get("daily_login_streak", 0)
    
    # Prepare update operations
    update_data = {
        "is_online": True, 
        "last_seen": datetime.utcnow(),
        "active_session_id": new_session_id,
        "session_created_at": datetime.utcnow()
    }
    
    # Calculate XP and streak if it's a new day
    xp_to_add = 0
    if last_login != today:
        # Calculate streak
        if last_login:
            yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
            if last_login == yesterday:
                current_streak += 1
            else:
                current_streak = 1
        else:
            current_streak = 1
        
        # Add to update data
        update_data.update({
            "last_login_date": today,
            "daily_login_streak": current_streak
        })
        
        # Add XP for daily login (but don't process achievements yet)
        xp_to_add = 10
        current_xp = user.get("experience_points", 0)
        new_xp = current_xp + xp_to_add
        new_level = get_level_from_xp(new_xp)
        
        update_data.update({
            "experience_points": new_xp,
            "level": new_level
        })
    
    # SINGLE database update for all login data
    previous_user = await db.users.find_one_and_update(
        {"id": user_obj.id, "password_hash": verified_hash, "status": user["status"],
         "disabled": user["disabled"] if "disabled" in user else {"$exists": False}},
        {"$set": update_data}
    )
    if previous_user is None:
        raise HTTPException(status_code=401, detail="Credentials changed. Please sign in again.")
    # Mongo returns the exact preceding session. A delayed notification from an
    # earlier login must not close a newer login's connection.
    await manager.send_session_invalidation(user_obj.id, previous_user.get("active_session_id"))
    
    # PERFORMANCE OPTIMIZATION: Process XP/achievements asynchronously in background
    if xp_to_add > 0:
        # Schedule background task for heavy operations (achievements, notifications, etc.)
        asyncio.create_task(process_login_rewards_async(user_obj.id, current_streak, xp_to_add))
    
    # Add session_id to user object for frontend - update with new values
    user_obj.active_session_id = new_session_id
    user_obj.session_created_at = datetime.utcnow()
    user_obj.is_online = True
    user_obj.last_seen = datetime.utcnow()
    
    # Update XP/level in response if changed
    if xp_to_add > 0:
        user_obj.experience_points = update_data["experience_points"]
        user_obj.level = update_data["level"]
        user_obj.last_login_date = today
        user_obj.daily_login_streak = current_streak
    
    logger.info("User %s logged in", user_obj.username)
    
    return AuthenticatedUser(**user_obj.dict(), active_session_id=new_session_id, session_created_at=user_obj.session_created_at)

async def process_login_rewards_async(user_id: str, streak: int, xp_added: int):
    """Process heavy login rewards (achievements, notifications) in background"""
    try:
        print(f"🔄 Processing login rewards for user {user_id} in background...")
        
        # Only check specific login-related achievements to avoid heavy processing
        user = await db.users.find_one({"id": user_id})
        if not user:
            return
            
        user_achievements = user.get("achievements", [])
        
        # Check only login streak achievements (not all achievements)
        new_achievements = []
        
        # Check dedication achievement (30-day streak)
        if "dedication" not in user_achievements and streak >= 30:
            new_achievements.append("dedication")
            await award_xp(user_id, "achievement_unlocked", ACHIEVEMENTS["dedication"]["points_reward"])
        
        # Check membership duration achievements only once per week to reduce load
        if user.get("last_membership_check") != datetime.utcnow().strftime('%Y-%m-%d'):
            created_at = user.get("created_at")
            if created_at:
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                days_since_creation = (datetime.utcnow() - created_at).days
                
                # Check membership achievements
                for achievement_id in ["team_member_3m", "team_member_8m", "team_member_12m"]:
                    if achievement_id not in user_achievements:
                        required_days = 90 if "3m" in achievement_id else 240 if "8m" in achievement_id else 365
                        if days_since_creation >= required_days:
                            new_achievements.append(achievement_id)
                            await award_xp(user_id, "achievement_unlocked", ACHIEVEMENTS[achievement_id]["points_reward"])
            
            # Update last check date
            await db.users.update_one(
                {"id": user_id},
                {"$set": {"last_membership_check": datetime.utcnow().strftime('%Y-%m-%d')}}
            )
        
        # Update achievements if any new ones were earned
        if new_achievements:
            print(f"🏆 Background: User {user_id} earned achievements: {new_achievements}")
            
            await db.users.update_one(
                {"id": user_id},
                {"$addToSet": {"achievements": {"$each": new_achievements}}}
            )
            
            # Auto-share achievements in chat and create notifications
            for achievement_id in new_achievements:
                achievement = ACHIEVEMENTS[achievement_id]
                await share_achievement_in_chat(user_id, achievement)
                
                # Create achievement notification
                await create_user_notification(
                    user_id=user_id,
                    notification_type="achievement",
                    title="🏆 Achievement Unlocked!",
                    message=f"Congratulations! You've earned: {achievement['name']}",
                    data={
                        "achievement_id": achievement_id,
                        "achievement_name": achievement["name"],
                        "points": achievement["points_reward"],
                        "action": "achievement_unlocked"
                    }
                )
        
        print(f"✅ Login rewards processing completed for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error processing login rewards: {e}")
        # Don't let background task errors affect login

@api_router.get("/users/online")
async def get_online_users():
    """Get currently online users for HTTP polling fallback"""
    try:
        online_users = await db.users.find(
            {"is_online": True},
            {"_id": 0, "id": 1, "username": 1, "real_name": 1, "screen_name": 1, "is_admin": 1, "avatar_url": 1, "last_seen": 1}
        ).to_list(100)
        return online_users
    except Exception as e:
        logger.error(f"Error getting online users: {e}")
        return []

@api_router.get("/users/online-count")
async def get_online_count():
    """Get current online user count for debugging"""
    try:
        # Clean up stale sessions first
        await cleanup_stale_sessions()
        
        # Get fresh count
        online_count = await db.users.count_documents({"is_online": True})
        online_users = await db.users.find(
            {"is_online": True}, 
            {"username": 1, "real_name": 1, "last_seen": 1, "active_session_id": 1}
        ).to_list(100)
        
        return {
            "online_count": online_count,
            "online_users": [
                {
                    "username": user["username"],
                    "real_name": user.get("real_name"),
                    "last_seen": user.get("last_seen"),
                    "has_session": bool(user.get("active_session_id"))
                } for user in online_users
            ]
        }
    except Exception as e:
        logger.error(f"Error getting online count: {e}")
        raise HTTPException(status_code=500, detail="Failed to get online count")

@api_router.get("/users/{user_id}/session-status")
async def check_session_status(request: Request, user_id: str, session_id: Optional[str] = None):
    """Return only validity; prefer header credentials in current clients."""
    claimed_user = request.headers.get("x-user-id")
    header_token = request.headers.get("x-session-id", "")
    authorization = request.headers.get("authorization", "")
    if not header_token and authorization.startswith("Bearer "):
        header_token = authorization[7:].strip()
    # The legacy query parameter remains accepted for existing app versions.
    # If both are supplied they must describe the same session.
    token = header_token or session_id or ""
    user = await db.users.find_one({"id": user_id})
    active = (user or {}).get("active_session_id")
    is_valid = bool(
        token and len(token) <= 240 and isinstance(active, str) and active
        and (not claimed_user or claimed_user == user_id)
        and (not session_id or not header_token or session_id == header_token)
        and secrets.compare_digest(token.encode(), active.encode())
    )
    return {
        "valid": is_valid,
        "message": "Session is valid" if is_valid else "Session is invalid or expired"
    }

@api_router.post("/users/logout")
async def logout_user(request: Request, user_id: str):
    """Revoke only the presented login, including when logouts race logins."""
    claimed_user = request.headers.get("x-user-id")
    token = request.headers.get("x-session-id", "")
    authorization = request.headers.get("authorization", "")
    if not token and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    if claimed_user and claimed_user != user_id:
        raise HTTPException(status_code=403, detail="This session belongs to another member.")
    if not token or len(token) > 240:
        raise HTTPException(status_code=401, detail="Please sign in again.")
    result = await db.users.update_one(
        {"id": user_id, "active_session_id": token},
        {"$set": {
            "is_online": False, 
            "last_seen": datetime.utcnow(),
            "active_session_id": None,
            "session_created_at": None
        }}
    )
    if result.matched_count:
        await manager.send_session_invalidation(user_id, token)
    return {"message": "Logged out successfully"}

@api_router.get("/community/members")
async def get_community_members(request: Request):
    """Public community profile projection, bounded to 200 active members."""
    actor_id = request.headers.get("x-user-id", "")
    if not actor_id or len(actor_id) > 240:
        raise HTTPException(status_code=401, detail="Please sign in again.")
    actor = await require_profile_owner(request, actor_id)
    now = datetime.utcnow()
    if not active_membership(actor, now):
        raise HTTPException(status_code=403, detail="An active membership is required to open the member directory.")
    users = []
    has_more = False
    cursor = db.users.find({"status": {"$in": ["approved", "trial"]}}).sort("username", 1)
    async for member in cursor:
        if not active_membership(member, now) or not isinstance(member.get("id"), str) or not member["id"]:
            continue
        if len(users) == 200:
            has_more = True
            break
        users.append({
            "id": member["id"], "username": member.get("username", "Member"),
            "screen_name": member.get("screen_name"), "avatar_url": member.get("avatar_url"),
            "level": member.get("level", 1), "is_admin": bool(member.get("is_admin", False)),
            "role": member.get("role", "member"), "is_online": bool(member.get("is_online", False)),
            "follower_count": member.get("follower_count", 0),
        })
    return {"users": users, "has_more": has_more, "limit": 200}

@api_router.get("/users", response_model=List[User])
async def get_users():
    """Get all active users (approved and trial users)"""
    users = await db.users.find({
        "status": {"$in": [UserStatus.APPROVED, UserStatus.TRIAL]}
    }).to_list(1000)
    return [User(**user) for user in users]

@api_router.get("/users/pending", response_model=List[User])
async def get_pending_users():
    """Get all users needing admin attention (pending, trial, trial expired)"""
    pending_users = await db.users.find({"status": UserStatus.PENDING}).to_list(1000)
    trial_users = await db.users.find({"status": UserStatus.TRIAL}).to_list(1000)
    trial_expired_users = await db.users.find({"status": UserStatus.TRIAL_EXPIRED}).to_list(1000)
    
    # Add indicators for different user types
    for user in trial_users:
        user["is_trial_active"] = True
        trial_end = utc_datetime(user.get('trial_end_date'))
        if trial_end:
            days_remaining = (trial_end - datetime.utcnow()).days
            user["admin_note"] = f"🎯 ACTIVE TRIAL: {days_remaining} days remaining - Auto-approved trial user"
        else:
            user["admin_note"] = "🎯 ACTIVE TRIAL: Auto-approved trial user"
    
    for user in trial_expired_users:
        user["is_trial_expired"] = True
        user["admin_note"] = f"⏰ TRIAL EXPIRED: Membership plan '{user.get('membership_plan', 'Unknown')}' - Verify payment before converting to Member"
    
    # Combine and sort by creation date (most recent first)
    all_users = pending_users + trial_users + trial_expired_users
    all_users.sort(key=lambda x: utc_datetime(x.get("created_at")) or datetime.min, reverse=True)
    
    return [User(**user) for user in all_users]

@api_router.post("/users/approve")
async def approve_user(request: Request, approval: UserApproval, background_tasks: BackgroundTasks):
    """Approve or reject a user - admin only"""
    admin = await require_authenticated_admin(request, approval.admin_id)
    
    # Get user before updating to get email and name
    user_to_approve = await db.users.find_one({"id": approval.user_id})
    if not user_to_approve:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update user status
    new_status = UserStatus.APPROVED if approval.approved else UserStatus.REJECTED
    update_data = {
        "status": new_status,
        "approved_by": approval.admin_id,
        "approved_at": datetime.utcnow()
    }
    
    # Set role if approved
    if approval.approved:
        update_data.update(manual_access_granted=True, manual_access_granted_at=datetime.utcnow(),
                           manual_access_granted_by=admin["id"])
        update_data["role"] = approval.role
        if approval.role == UserRole.ADMIN:
            update_data["is_admin"] = True
    
    result = await db.users.update_one(
        {"id": approval.user_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get updated user
    user = await db.users.find_one({"id": approval.user_id})
    status_text = "approved" if approval.approved else "rejected"
    
    # Send email notification to user about approval/rejection
    user_name = user_to_approve.get('real_name', user_to_approve.get('username'))
    user_email = user_to_approve.get('email')
    
    if user_email and email_service and user_to_approve.get("status") != new_status:
        # One welcome on approval; rejection uses its separate confirmation.
        if approval.approved:
            background_tasks.add_task(
                email_service.send_general_welcome_email,
                user_email,
                user_name,
                user_to_approve["username"],
                user_to_approve.get("membership_plan", "Premium")
            )
            logger.info(f"✅ Welcome email scheduled for approved user {user_email}")
        else:
            background_tasks.add_task(email_service.send_approval_confirmation, user_email, user_name, False)
            
    elif user_email and not email_service:
        action = "approved" if approval.approved else "rejected"
        print(f"Email service unavailable. Would send {action} notification to {user_email}")
    
    # Notify all admins via WebSocket
    await manager.send_admin_notification(json.dumps({
        "type": "user_approval",
        "message": f"User {user['username']} has been {status_text}",
        "user": user
    }, default=str))
    
    return {"message": f"User {status_text} successfully"}

@api_router.post("/users/change-role")
async def change_user_role(request: Request, role_change: Dict[str, Any], background_tasks: BackgroundTasks):
    """Change user role - admin only (including demoting other admins)"""
    required_fields = ["user_id", "admin_id", "new_role"]
    for field in required_fields:
        if field not in role_change:
            raise HTTPException(status_code=400, detail=f"Missing field: {field}")
    
    user_id = role_change["user_id"]
    admin_id = role_change["admin_id"]
    new_role = role_change["new_role"]
    
    admin = await require_authenticated_admin(request, admin_id)
    
    # Get target user
    target_user = await db.users.find_one({"id": user_id})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent admin from demoting themselves
    if admin_id == user_id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    
    # Validate new role
    try:
        new_role_enum = UserRole(new_role)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role")
    
    # Update user role
    update_data = {
        "role": new_role_enum,
        "modified_at": datetime.utcnow(),
        "modified_by": admin_id
    }
    
    # Set admin status based on role
    if new_role_enum == UserRole.ADMIN:
        update_data["is_admin"] = True
    else:
        update_data["is_admin"] = False
    
    result = await db.users.update_one(
        {"id": user_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Failed to update user role")
    
    # Get updated user
    updated_user = await db.users.find_one({"id": user_id})
    
    # Send email notification to user about role change
    user_name = target_user.get('real_name', target_user.get('username'))
    user_email = target_user.get('email')
    admin_name = admin.get('real_name', admin.get('username'))
    
    if user_email and email_service:
        background_tasks.add_task(
            send_role_change_notification,
            user_email,
            user_name,
            admin_name,
            new_role_enum.value,
            target_user.get('role', 'member')
        )
    
    # Notify all admins via WebSocket
    await manager.send_admin_notification(json.dumps({
        "type": "role_change",
        "message": f"User {target_user['username']} role changed to {new_role_enum.value} by {admin['username']}",
        "user": updated_user,
        "admin": admin['username']
    }, default=str))
    
    return {"message": f"User role changed to {new_role_enum.value} successfully"}

async def send_role_change_notification(email: str, user_name: str, admin_name: str, new_role: str, old_role: str):
    """Send role change notification email to user"""
    if not email_service:
        print(f"Email service unavailable. Would send role change notification to {email}")
        return
        
    subject = "🔄 Role Change Notification - ArgusAI CashOut"
    
    plain_body = f"""
Hi {user_name},

Your role in ArgusAI CashOut has been updated by admin {admin_name}.

Previous Role: {old_role.title()}
New Role: {new_role.title()}

{"You now have administrative privileges and can manage other users." if new_role == "admin" else "You are now a regular member with standard access privileges."}

If you have any questions about this change, please contact an administrator.

--
ArgusAI CashOut Team
"""
    
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f9f9f9; }}
        .role-box {{ background: white; padding: 20px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #667eea; }}
        .role-change {{ background: #e3f2fd; padding: 15px; border-radius: 6px; margin: 10px 0; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔄 Role Change Notification</h1>
        <p>ArgusAI CashOut</p>
    </div>
    
    <div class="content">
        <div class="role-box">
            <h2>Hi {user_name},</h2>
            <p>Your role in ArgusAI CashOut has been updated by admin <strong>{admin_name}</strong>.</p>
            
            <div class="role-change">
                <p><strong>Previous Role:</strong> {old_role.title()}</p>
                <p><strong>New Role:</strong> {new_role.title()}</p>
            </div>
            
            {"<p><strong>Congratulations!</strong> You now have administrative privileges and can manage other users.</p>" if new_role == "admin" else "<p>You are now a regular member with standard access privileges.</p>"}
        </div>
        
        <p>If you have any questions about this change, please contact an administrator.</p>
    </div>
    
    <div class="footer">
        <p>ArgusAI CashOut Team</p>
    </div>
</body>
</html>
"""
    
    await email_service.send_email(email, subject, plain_body, html_body)

@api_router.post("/users/change-password")
async def change_password(password_data: PasswordChange, background_tasks: BackgroundTasks, user_id: str):
    """Change user password - user must be logged in"""
    # Get user
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    password_field, stored_hash = password_record(user)
    if not stored_hash or not verify_password(password_data.current_password, stored_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    validate_new_password(password_data.new_password)
    
    # Hash new password
    new_password_hash = hash_password(password_data.new_password)
    
    # Update only the credential that was verified, guarding concurrent resets.
    password_guard = {"id": user_id, password_field: stored_hash}
    if password_field == "hashed_password":
        password_guard["password_hash"] = user.get("password_hash")
    result = await db.users.update_one(
        password_guard,
        {"$set": {
            "password_hash": new_password_hash,
            "modified_at": datetime.utcnow(),
            "active_session_id": None,
            "session_created_at": None,
            "is_online": False,
        }, "$unset": {"reset_token": "", "reset_token_hash": "", "reset_expires": "", "reset_context_hash": "", "password": "", "hashed_password": ""}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Failed to update password")
    
    await manager.send_session_invalidation(user_id, user.get("active_session_id"))
    # Send email notification about password change
    user_email = user.get('email')
    user_name = user.get('real_name', user.get('username'))
    
    if user_email and email_service:
        background_tasks.add_task(
            send_password_change_notification,
            user_email,
            user_name
        )
    
    return {"message": "Password changed successfully"}

@api_router.post("/users/reset-password-request")
@limiter.limit("5/minute")
async def request_password_reset(request: Request, reset_request: PasswordResetRequest, background_tasks: BackgroundTasks):
    """Email proof is required; the request itself never changes a password."""
    if not email_service:
        raise HTTPException(status_code=503, detail="Password recovery email is temporarily unavailable. Please contact support.")
    # Find user by email (case-insensitive)
    user = await db.users.find_one({"email": {"$regex": f"^{re.escape(reset_request.email.strip())}$", "$options": "i"}})
    
    # Always return success for security (don't reveal if email exists)
    if not user:
        return {"message": "If an account with that email exists, you will receive a password reset link."}
    
    # Generate reset token
    reset_token = secrets.token_urlsafe(32)
    reset_token_hash = hashlib.sha256(reset_token.encode("utf-8")).hexdigest()
    reset_expires = datetime.utcnow() + timedelta(hours=1)  # Token expires in 1 hour
    
    # A concurrent email/password change wins over this earlier account read.
    # Do not install or email a link for an account state that is already stale.
    context_hash, context_guard = password_reset_context(user)
    stored = await db.users.update_one(
        {"id": user["id"], **context_guard},
        {"$set": {
            "reset_token_hash": reset_token_hash,
            "reset_expires": reset_expires,
            "reset_context_hash": context_hash,
        }, "$unset": {"reset_token": ""}}
    )
    if not stored.matched_count:
        return {"message": "If an account with that email exists, you will receive a password reset link."}
    
    # Send reset email
    user_name = user.get('real_name', user.get('username'))
    user_email = user.get('email')
    
    if email_service:
        background_tasks.add_task(
            send_password_reset_email,
            user_email,
            user_name,
            reset_token
        )
    
    return {"message": "If an account with that email exists, you will receive a password reset link."}

@api_router.post("/users/reset-password-direct")
async def direct_password_reset():
    """Reject obsolete clients that attempt email-only password replacement."""
    raise HTTPException(status_code=410, detail="Request a password recovery email and use its verification link.")

@api_router.post("/users/reset-password-confirm")
@limiter.limit("10/minute")
async def confirm_password_reset(request: Request, reset_confirm: PasswordResetConfirm, background_tasks: BackgroundTasks):
    """Consume one unexpired email token atomically and revoke prior sessions."""
    validate_new_password(reset_confirm.new_password)
    token_hash = hashlib.sha256(reset_confirm.token.encode("utf-8")).hexdigest()
    current = await db.users.find_one(
        {"reset_token_hash": token_hash, "reset_expires": {"$gt": datetime.utcnow()}}
    )
    if not current:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    context_hash, context_guard = password_reset_context(current)
    issued_context = current.get("reset_context_hash")
    if (not isinstance(issued_context, str) or not re.fullmatch(r"[0-9a-f]{64}", issued_context)
            or not secrets.compare_digest(issued_context, context_hash)):
        # Earlier unbound links also require a fresh request. Never guess which
        # email/credential state an already-issued link originally verified.
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    new_password_hash = hash_password(reset_confirm.new_password)
    user = await db.users.find_one_and_update(
        {"id": current["id"], "reset_token_hash": token_hash,
         "reset_expires": {"$gt": datetime.utcnow()}, "reset_context_hash": context_hash,
         **context_guard},
        {"$set": {
            "password_hash": new_password_hash,
            "modified_at": datetime.utcnow(),
            "active_session_id": None,
            "session_created_at": None,
            "is_online": False,
        },
        "$unset": {
            "reset_token": "",
            "reset_token_hash": "",
            "reset_expires": "",
            "reset_context_hash": "",
            "password": "",
            "hashed_password": "",
        }}
    )
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    await manager.send_session_invalidation(user["id"], user.get("active_session_id"))
    # Send confirmation email
    user_email = user.get('email')
    user_name = user.get('real_name', user.get('username'))
    
    if user_email and email_service:
        background_tasks.add_task(
            send_password_reset_confirmation,
            user_email,
            user_name
        )
    
    return {"message": "Password reset successfully"}

async def send_password_change_notification(email: str, user_name: str):
    """Send password change notification email"""
    if not email_service:
        print(f"Email service unavailable. Would send password change notification to {email}")
        return
        
    subject = "🔒 Password Changed - ArgusAI CashOut"
    
    plain_body = f"""
Hi {user_name},

Your ArgusAI CashOut account password has been successfully changed.

Time: {datetime.utcnow().strftime('%B %d, %Y at %I:%M %p UTC')}

If you did not make this change, please contact support immediately.

--
ArgusAI CashOut Team
"""
    
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f9f9f9; }}
        .info-box {{ background: white; padding: 20px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #10b981; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔒 Password Changed</h1>
        <p>ArgusAI CashOut</p>
    </div>
    
    <div class="content">
        <div class="info-box">
            <h2>Hi {user_name},</h2>
            <p>Your ArgusAI CashOut account password has been successfully changed.</p>
            <p><strong>Time:</strong> {datetime.utcnow().strftime('%B %d, %Y at %I:%M %p UTC')}</p>
        </div>
        
        <p>If you did not make this change, please contact support immediately.</p>
    </div>
    
    <div class="footer">
        <p>ArgusAI CashOut Team</p>
    </div>
</body>
</html>
"""
    
    await email_service.send_email(email, subject, plain_body, html_body)

async def send_password_reset_email(email: str, user_name: str, reset_token: str):
    """Send password reset email with link"""
    if not email_service:
        print(f"Email service unavailable. Would send password reset email to {email}")
        return
        
    subject = "🔑 Password Reset Request - ArgusAI CashOut"
    
    # Use environment variable for frontend URL, fallback to production domain
    frontend_url = os.getenv('FRONTEND_URL') or os.getenv('REACT_APP_FRONTEND_URL') or 'https://cashoutai.app'
    reset_link = f"{frontend_url.rstrip('/')}/?reset_token={reset_token}"
    
    plain_body = f"""
Hi {user_name},

You requested a password reset for your ArgusAI CashOut account.

Click the link below to reset your password:
{reset_link}

This link will expire in 1 hour.

If you did not request this reset, please ignore this email.

--
ArgusAI CashOut Team
"""
    
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f9f9f9; }}
        .reset-box {{ background: white; padding: 20px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #667eea; }}
        .reset-btn {{ background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; margin: 15px 0; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔑 Password Reset Request</h1>
        <p>ArgusAI CashOut</p>
    </div>
    
    <div class="content">
        <div class="reset-box">
            <h2>Hi {user_name},</h2>
            <p>You requested a password reset for your ArgusAI CashOut account.</p>
            
            <a href="{reset_link}" class="reset-btn">Reset Your Password</a>
            
            <p><small>This link will expire in 1 hour.</small></p>
        </div>
        
        <p>If you did not request this reset, please ignore this email.</p>
    </div>
    
    <div class="footer">
        <p>ArgusAI CashOut Team</p>
    </div>
</body>
</html>
"""
    
    await email_service.send_email(email, subject, plain_body, html_body)

async def send_password_reset_confirmation(email: str, user_name: str):
    """Send password reset confirmation email"""
    if not email_service:
        print(f"Email service unavailable. Would send password reset confirmation to {email}")
        return
        
    subject = "✅ Password Reset Complete - ArgusAI CashOut"
    
    plain_body = f"""
Hi {user_name},

Your ArgusAI CashOut account password has been successfully reset.

Time: {datetime.utcnow().strftime('%B %d, %Y at %I:%M %p UTC')}

You can now log in with your new password.

If you did not make this change, please contact support immediately.

--
ArgusAI CashOut Team
"""
    
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f9f9f9; }}
        .success-box {{ background: white; padding: 20px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #10b981; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>✅ Password Reset Complete</h1>
        <p>ArgusAI CashOut</p>
    </div>
    
    <div class="content">
        <div class="success-box">
            <h2>Hi {user_name},</h2>
            <p>Your ArgusAI CashOut account password has been successfully reset.</p>
            <p><strong>Time:</strong> {datetime.utcnow().strftime('%B %d, %Y at %I:%M %p UTC')}</p>
            <p>You can now log in with your new password.</p>
        </div>
        
        <p>If you did not make this change, please contact support immediately.</p>
    </div>
    
    <div class="footer">
        <p>ArgusAI CashOut Team</p>
    </div>
</body>
</html>
"""
    
    await email_service.send_email(email, subject, plain_body, html_body)

@api_router.get("/stock/{symbol}")
async def get_stock_price(symbol: str):
    """Last reported provider price with observation time, receipt and limits."""
    try:
        quote = await stock_quote_service.get_quote(symbol)
    except QuoteUnavailable as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail()) from None
    return {**quote, "formatted_price": format_price_display(quote["price"])}

@api_router.post("/users/{user_id}/role")
async def update_user_role(request: Request, user_id: str, role_update: UserRoleUpdate):
    """Update user role - admin only"""
    admin = await require_authenticated_admin(request, role_update.admin_id)
    if role_update.user_id is not None and role_update.user_id != user_id:
        raise HTTPException(status_code=400, detail="The target member does not match.")
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    if role_update.role and role_update.new_role and role_update.role != role_update.new_role:
        raise HTTPException(status_code=400, detail="Conflicting role values.")
    new_role = role_update.role or role_update.new_role
    if new_role is None:
        raise HTTPException(status_code=400, detail="A role is required.")
    
    update_data = {"role": new_role, "modified_by": admin["id"], "modified_at": datetime.utcnow()}
    if new_role == UserRole.ADMIN:
        update_data["is_admin"] = True
    else:
        update_data["is_admin"] = False
    
    result = await db.users.update_one(
        {"id": user_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User role updated successfully"}

@api_router.delete("/users/{user_id}")
async def remove_user(user_id: str, admin_id: str):
    """Remove user from app - admin only (includes trial users)"""
    # Verify admin status
    admin = await db.users.find_one({"id": admin_id})
    if not admin or not admin.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get user details before deletion
    user_to_remove = await db.users.find_one({"id": user_id})
    if not user_to_remove:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Don't allow removing other admins
    if user_to_remove.get("is_admin"):
        raise HTTPException(status_code=403, detail="Cannot remove admin users")
    
    username = user_to_remove.get("username", "Unknown")
    user_status = user_to_remove.get("status", "Unknown")
    membership_plan = user_to_remove.get("membership_plan", "Unknown")
    
    # COMPREHENSIVE CLEANUP: Remove all user-related data
    try:
        # 1. Delete user messages
        messages_deleted = await db.messages.delete_many({"user_id": user_id})
        
        # 2. Delete user notifications
        notifications_deleted = await db.notifications.delete_many({"user_id": user_id})
        
        # 3. Delete user trades/positions
        trades_deleted = await db.trades.delete_many({"user_id": user_id})
        positions_deleted = await db.positions.delete_many({"user_id": user_id})
        
        # 4. Delete FCM tokens
        fcm_deleted = await db.fcm_tokens.delete_many({"user_id": user_id})
        
        # 5. Remove user from other users' followers/following lists
        await db.users.update_many(
            {"followers": user_id},
            {"$pull": {"followers": user_id}, "$inc": {"follower_count": -1}}
        )
        await db.users.update_many(
            {"following": user_id},
            {"$pull": {"following": user_id}, "$inc": {"following_count": -1}}
        )
        
        # 6. Delete user cash prizes
        prizes_deleted = await db.cash_prizes.delete_many({"user_id": user_id})
        
        # 7. Finally, delete the user account
        result = await db.users.delete_one({"id": user_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="User deletion failed")
        
        # Log the removal with details
        logger.info(f"🗑️ USER REMOVED by admin {admin['username']}: {username} (Status: {user_status}, Plan: {membership_plan})")
        logger.info(f"📊 Cleanup stats - Messages: {messages_deleted.deleted_count}, Notifications: {notifications_deleted.deleted_count}, Trades: {trades_deleted.deleted_count}, FCM: {fcm_deleted.deleted_count}")
        
        # Notify other admins about the removal
        await manager.send_admin_notification(json.dumps({
            "type": "user_removed",
            "message": f"User {username} ({user_status}) has been removed by {admin['username']}",
            "admin_action": "user_removal",
            "removed_user": {
                "username": username,
                "status": user_status,
                "membership_plan": membership_plan,
                "removed_by": admin['username']
            }
        }, default=str))
        
        return {
            "message": f"User {username} removed successfully",
            "user_details": {
                "username": username,
                "status": user_status,
                "membership_plan": membership_plan,
                "removed_by": admin['username']
            },
            "cleanup_stats": {
                "messages_deleted": messages_deleted.deleted_count,
                "notifications_deleted": notifications_deleted.deleted_count,
                "trades_deleted": trades_deleted.deleted_count,
                "positions_deleted": positions_deleted.deleted_count,
                "fcm_tokens_deleted": fcm_deleted.deleted_count,
                "cash_prizes_deleted": prizes_deleted.deleted_count
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error during user removal: {e}")
        raise HTTPException(status_code=500, detail=f"Error removing user: {str(e)}")

# NEW: XP and Achievement Endpoints
@api_router.post("/users/{user_id}/award-xp")
async def award_user_xp(user_id: str, xp_action: XPAction):
    """Award XP to user for various actions"""
    await award_xp(user_id, xp_action.action, xp_action.points, xp_action.metadata or {})
    
    # Get updated user data
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "message": "XP awarded successfully",
        "total_xp": user.get("experience_points", 0),
        "level": user.get("level", 1),
        "xp_for_next_level": get_xp_for_next_level(user.get("experience_points", 0))
    }

@api_router.get("/users/{user_id}/achievements")
async def get_user_achievements(user_id: str):
    """Get user's achievements and progress"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_achievements = user.get("achievements", [])
    progress = user.get("achievement_progress", {})
    
    # Format achievement data
    earned_achievements = []
    available_achievements = []
    
    for achievement_id, achievement in ACHIEVEMENTS.items():
        if achievement_id in user_achievements:
            earned_achievements.append(achievement)
        else:
            # Add progress information
            achievement_copy = achievement.copy()
            if achievement_id == "chatterbox":
                achievement_copy["current_progress"] = progress.get("chatterbox_count", 0)
            elif achievement_id == "heart_giver":
                achievement_copy["current_progress"] = progress.get("heart_giver_count", 0)
            elif achievement_id == "dedication":
                achievement_copy["current_progress"] = progress.get("login_streak", 0)
            elif achievement_id == "first_blood":
                achievement_copy["current_progress"] = progress.get("profitable_trades", 0)
            else:
                achievement_copy["current_progress"] = 0
                
            available_achievements.append(achievement_copy)
    
    return {
        "earned": earned_achievements,
        "available": available_achievements,
        "total_earned": len(earned_achievements),
        "total_available": len(ACHIEVEMENTS)
    }

@api_router.get("/achievements")
async def get_all_achievements():
    """Get all available achievements"""
    return {"achievements": list(ACHIEVEMENTS.values())}

# NEW: Profile Customization Endpoints  
@api_router.post("/users/{user_id}/profile")
async def update_user_profile(request: Request, user_id: str, profile_update: ProfileUpdate):
    """Update user profile customization"""
    await require_profile_owner(request, user_id)
    update_data = {}
    
    if profile_update.bio is not None:
        update_data["bio"] = profile_update.bio
    if profile_update.trading_style_tags is not None:
        update_data["trading_style_tags"] = profile_update.trading_style_tags
    if profile_update.profile_banner is not None:
        update_data["profile_banner"] = profile_update.profile_banner
    if profile_update.avatar_url is not None:
        update_data["avatar_url"] = profile_update.avatar_url
    if profile_update.location is not None:
        update_data["location"] = profile_update.location
    if profile_update.show_location is not None:
        update_data["show_location"] = profile_update.show_location
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")
    
    result = await db.users.update_one(
        {"id": user_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Award XP for profile completion
    if profile_update.avatar_url or profile_update.bio or profile_update.profile_banner:
        await award_xp(user_id, "profile_update", 25)
    
    return {"message": "Profile updated successfully"}

@api_router.get("/users/{user_id}/profile")
async def get_user_profile(request: Request, user_id: str):
    """Get a member-visible profile, honoring location privacy on the server."""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": user["id"],
        "username": user["username"],
        "screen_name": user.get("screen_name"),
        "bio": user.get("bio"),
        "trading_style_tags": user.get("trading_style_tags", []),
        "profile_banner": user.get("profile_banner"),
        "avatar_url": user.get("avatar_url"),
        "location": user.get("location") if (
            user.get("show_location", True) is True
            or getattr(request.state, "session_user", {}).get("id") == user_id
        ) else None,
        "show_location": user.get("show_location", True),
        "level": user.get("level", 1),
        "experience_points": user.get("experience_points", 0),
        "achievements": user.get("achievements", []),
        "achievement_progress": user.get("achievement_progress", {}),
        "total_profit": user.get("total_profit", 0),
        "win_percentage": user.get("win_percentage", 0),
        "trades_count": user.get("trades_count", 0),
        "is_admin": user.get("is_admin", False),
        "role": user.get("role", "member"),
        "created_at": user.get("created_at"),
        "is_online": user.get("is_online", False),
        "last_seen": user.get("last_seen"),
        "follower_count": user.get("follower_count", 0),
        "following_count": user.get("following_count", 0)
    }

@api_router.get("/users/{user_id}/profile/public")
async def get_public_user_profile(user_id: str):
    """Get public user profile for other users to view"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Return only public information
    return {
        "id": user["id"],
        "username": user["username"],
        "screen_name": user.get("screen_name"),
        "bio": user.get("bio"),
        "trading_style_tags": user.get("trading_style_tags", []),
        "profile_banner": user.get("profile_banner"),
        "avatar_url": user.get("avatar_url"),
        "level": user.get("level", 1),
        "experience_points": user.get("experience_points", 0),
        "achievements": user.get("achievements", []),
        "is_admin": user.get("is_admin", False),
        "role": user.get("role", "member"),
        "created_at": user.get("created_at"),
        "is_online": user.get("is_online", False),
        "last_seen": user.get("last_seen"),
        # Public trading stats (optional - you can remove if too private)
        "total_profit": user.get("total_profit", 0),
        "win_percentage": user.get("win_percentage", 0),
        "trades_count": user.get("trades_count", 0)
    }

# NEW: Cash Prize and Referral System Endpoints

@api_router.get("/admin/cash-prizes/pending")
async def get_pending_cash_prizes(admin_id: str):
    """Get all pending cash prizes for admin review"""
    # Verify admin status
    admin = await db.users.find_one({"id": admin_id})
    if not admin or not admin.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get all users with pending cash prizes
    users_with_pending = await db.users.find(
        {"pending_cash_review": {"$exists": True, "$ne": []}}
    ).to_list(1000)
    
    pending_prizes = []
    for user in users_with_pending:
        for prize in user.get("pending_cash_review", []):
            prize_info = {
                "user_id": user["id"],
                "username": user["username"],
                "real_name": user.get("real_name"),
                "email": user.get("email"),
                "prize": prize
            }
            pending_prizes.append(prize_info)
    
    return {"pending_cash_prizes": pending_prizes}

@api_router.post("/admin/cash-prizes/review")
async def review_cash_prize(review: CashPrizeReview, admin_id: str):
    """Historical records remain readable, but cash rewards are not enabled."""
    raise HTTPException(status_code=410, detail="Cash rewards are not part of the current program.")

@api_router.post("/admin/convert-trial")
async def convert_trial_to_member(request: Request, user_id: str, admin_id: str):
    """Admin endpoint to convert trial_expired users to member status after payment"""
    admin = await require_authenticated_admin(request, admin_id)
    
    # Find the trial expired user
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.get("status") != UserStatus.TRIAL_EXPIRED:
        raise HTTPException(status_code=400, detail="User is not in trial_expired status")
    
    # Convert to approved member
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "status": UserStatus.APPROVED,
            "role": UserRole.MEMBER,
            "approved_by": admin["username"],
            "approved_at": datetime.utcnow(),
            "manual_access_granted": True,
            "manual_access_granted_at": datetime.utcnow(),
            "manual_access_granted_by": admin["id"]
        }}
    )
    
    logger.info(f"🎉 TRIAL CONVERTED TO MEMBER: {user['username']} by admin {admin['username']}")
    
    # Send one welcome email, not a second approval confirmation as well.
    if email_service:
        try:
            accepted = await email_service.send_general_welcome_email(
                user["email"],
                user.get("real_name", user["username"]), 
                user["username"],
                user.get("membership_plan", "Premium")
            )
            logger.info("Member welcome accepted by email provider." if accepted else "Member welcome acceptance was not confirmed.")
            
        except Exception as e:
            logger.error(f"Error sending approval/welcome emails: {e}")
    
    return {"message": f"User {user['username']} successfully converted to member status"}

@api_router.get("/admin/trial-expired-users")
async def get_trial_expired_users():
    """Get list of trial expired users for admin review"""
    trial_expired_users = await db.users.find(
        {"status": UserStatus.TRIAL_EXPIRED},
        {"id": 1, "username": 1, "real_name": 1, "email": 1, "trial_end_date": 1, "membership_plan": 1, "_id": 0}
    ).to_list(100)
    
    # Convert datetime objects to strings for JSON serialization
    for user in trial_expired_users:
        if "trial_end_date" in user and user["trial_end_date"]:
            user["trial_end_date"] = iso_date(user["trial_end_date"])
    
    return {
        "trial_expired_users": trial_expired_users,
        "count": len(trial_expired_users)
    }

@api_router.get("/admin/trial-users")
async def get_all_trial_users():
    """Get all trial users (active and expired) for admin management"""
    active_trials = await db.users.find(
        {"status": UserStatus.TRIAL},
        {"id": 1, "username": 1, "real_name": 1, "email": 1, "trial_start_date": 1, "trial_end_date": 1, "membership_plan": 1, "_id": 0}
    ).to_list(100)
    
    expired_trials = await db.users.find(
        {"status": UserStatus.TRIAL_EXPIRED},
        {"id": 1, "username": 1, "real_name": 1, "email": 1, "trial_end_date": 1, "membership_plan": 1, "_id": 0}
    ).to_list(100)
    
    # Convert datetime objects to strings for JSON serialization
    for user in active_trials + expired_trials:
        for date_field in ["trial_start_date", "trial_end_date"]:
            if date_field in user and user[date_field]:
                user[date_field] = iso_date(user[date_field])
    
    return {
        "active_trials": active_trials,
        "expired_trials": expired_trials, 
        "active_count": len(active_trials),
        "expired_count": len(expired_trials),
        "total_trials": len(active_trials) + len(expired_trials)
    }

@api_router.delete("/admin/trial-users/bulk")
async def bulk_remove_trial_users(admin_id: str, user_ids: list):
    """Bulk remove multiple trial users - admin only"""
    # Verify admin status
    admin = await db.users.find_one({"id": admin_id})
    if not admin or not admin.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if not user_ids or len(user_ids) == 0:
        raise HTTPException(status_code=400, detail="No user IDs provided")
    
    # Limit bulk operations to prevent abuse
    if len(user_ids) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 users can be removed at once")
    
    removed_users = []
    failed_removals = []
    
    for user_id in user_ids:
        try:
            # Get user details
            user = await db.users.find_one({"id": user_id})
            if not user:
                failed_removals.append({"user_id": user_id, "reason": "User not found"})
                continue
                
            # Only allow removal of trial and trial_expired users in bulk
            if user.get("status") not in [UserStatus.TRIAL, UserStatus.TRIAL_EXPIRED]:
                failed_removals.append({
                    "user_id": user_id, 
                    "username": user.get("username"),
                    "reason": f"Can only bulk remove trial users, found status: {user.get('status')}"
                })
                continue
                
            # Don't allow removing admins
            if user.get("is_admin"):
                failed_removals.append({
                    "user_id": user_id,
                    "username": user.get("username"), 
                    "reason": "Cannot remove admin users"
                })
                continue
            
            # Perform the removal (simplified cleanup for bulk operation)
            await db.messages.delete_many({"user_id": user_id})
            await db.notifications.delete_many({"user_id": user_id})
            await db.fcm_tokens.delete_many({"user_id": user_id})
            result = await db.users.delete_one({"id": user_id})
            
            if result.deleted_count > 0:
                removed_users.append({
                    "user_id": user_id,
                    "username": user.get("username"),
                    "status": user.get("status"),
                    "membership_plan": user.get("membership_plan")
                })
                logger.info(f"🗑️ BULK REMOVAL: {user.get('username')} removed by {admin['username']}")
            else:
                failed_removals.append({
                    "user_id": user_id,
                    "username": user.get("username"),
                    "reason": "Deletion failed"
                })
                
        except Exception as e:
            failed_removals.append({
                "user_id": user_id,
                "reason": f"Error: {str(e)}"
            })
    
    # Notify admins about bulk removal
    if removed_users:
        await manager.send_admin_notification(json.dumps({
            "type": "bulk_user_removal",
            "message": f"{len(removed_users)} trial users bulk removed by {admin['username']}",
            "admin_action": "bulk_removal",
            "removed_count": len(removed_users),
            "removed_by": admin['username']
        }, default=str))
    
    return {
        "message": f"Bulk removal completed: {len(removed_users)} removed, {len(failed_removals)} failed",
        "removed_users": removed_users,
        "failed_removals": failed_removals,
        "summary": {
            "total_requested": len(user_ids),
            "successfully_removed": len(removed_users),
            "failed_removals": len(failed_removals)
        }
    }

@api_router.post("/admin/allow-reregistration")
async def allow_rejected_user_reregistration(request: Request, user_id: str, admin_id: str):
    """Reopen review on the existing account; never delete its identity/history."""
    admin = await require_authenticated_admin(request, admin_id)
    rejected_user = await db.users.find_one({"id": user_id})
    if not rejected_user:
        raise HTTPException(status_code=404, detail="User not found")
    if rejected_user.get("status") != UserStatus.REJECTED:
        raise HTTPException(status_code=400, detail="User is not in rejected status")
    result = await db.users.update_one(
        {"id": user_id, "status": UserStatus.REJECTED},
        {"$set": {
            "status": UserStatus.PENDING,
            "reopened_at": datetime.utcnow(),
            "reopened_by": admin["id"],
            "active_session_id": None,
            "session_created_at": None,
            "is_online": False,
        }}
    )
    if not result.matched_count:
        raise HTTPException(status_code=409, detail="Account status changed. Refresh before reviewing it.")
    await manager.send_session_invalidation(user_id, rejected_user.get("active_session_id"))
    return {
        "message": "The existing account is pending review again. No new registration is needed.",
        "user_id": user_id,
        "username": rejected_user.get("username"),
        "email": rejected_user.get("email"),
        "action_by": admin["username"],
        "note": "Credentials, profile, follows and history were preserved. Access still requires approval.",
    }

@api_router.get("/users/{user_id}/referrals")
async def get_user_referrals(user_id: str):
    """Get user's referral information"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get referred users info
    referred_users = []
    for ref_id in user.get("referrals", []):
        ref_user = await db.users.find_one({"id": ref_id})
        if ref_user:
            referred_users.append({
                "id": ref_user["id"],
                "username": ref_user["username"],
                "real_name": ref_user.get("real_name"),
                "created_at": ref_user.get("created_at"),
                "status": ref_user.get("status")
            })
    
    return {
        "referral_code": user.get("referral_code"),
        "referred_users": referred_users,
        "successful_referrals": user.get("successful_referrals", 0),
        "total_cash_earned": user.get("total_cash_earned", 0),
        "cash_prizes": user.get("cash_prizes", []),
        "pending_cash_review": user.get("pending_cash_review", [])
    }

@api_router.get("/referral/{referral_code}")
async def get_referral_info(referral_code: str):
    """Get information about a referral code for signup form"""
    user = await db.users.find_one({"referral_code": referral_code})
    if not user:
        raise HTTPException(status_code=404, detail="Invalid referral code")
    
    return {
        "valid": True,
        "referrer_username": user["username"],
        "referrer_name": user.get("real_name", user["username"])
    }

async def share_cash_prize_in_chat(user_id: str, cash_prize: dict):
    """Share cash prize award in chat"""
    try:
        # Get user info
        user = await db.users.find_one({"id": user_id})
        if not user:
            return
            
        amount = cash_prize.get("approved_amount", cash_prize.get("amount", 0))
        achievement_id = cash_prize.get("achievement_id", "")
        
        # Create cash prize message
        message = Message(
            user_id=user_id,
            username=user.get("username", ""),
            content=f"💰 Cash Prize Awarded: ${amount:.2f} for {achievement_id} achievement! 🎉",
            is_admin=False,
            avatar_url=user.get("avatar_url"),
            real_name=user.get("real_name"),
            screen_name=user.get("screen_name")
        )
        
        # Save message to database
        await db.messages.insert_one(message.dict())
        
        # Broadcast to all connected users
        await manager.broadcast(json.dumps({
            "type": "message",
            "data": message.dict()
        }, default=str))
        
    except Exception as e:
        logger.error(f"Error sharing cash prize in chat: {e}")

# NEW: Theme Customization Endpoints
@api_router.post("/users/{user_id}/theme")
async def update_user_theme(user_id: str, theme_update: ThemeUpdate):
    """Update user's active theme"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user has unlocked this theme based on level
    user_level = user.get("level", 1)
    locked_themes = {
        "sunrise": 2,
        "ocean": 3, 
        "midnight": 4,
        "golden": 5
    }
    
    if theme_update.theme_name in locked_themes:
        required_level = locked_themes[theme_update.theme_name]
        if user_level < required_level:
            raise HTTPException(
                status_code=403, 
                detail=f"Theme '{theme_update.theme_name}' requires level {required_level}"
            )
    
    update_data = {
        "active_theme_name": theme_update.theme_name
    }
    
    if theme_update.custom_colors:
        update_data["custom_theme"] = theme_update.custom_colors
    
    result = await db.users.update_one(
        {"id": user_id},
        {"$set": update_data}
    )
    
    return {"message": "Theme updated successfully"}

@api_router.get("/users/{user_id}/theme")
async def get_user_theme(user_id: str):
    """Get user's current theme"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_level = user.get("level", 1)
    
    # Available themes based on level
    available_themes = ["dark", "light"]
    if user_level >= 2:
        available_themes.append("sunrise")
    if user_level >= 3:
        available_themes.append("ocean")
    if user_level >= 4:
        available_themes.append("midnight")
    if user_level >= 5:
        available_themes.append("golden")
    
    return {
        "active_theme": user.get("active_theme_name", "dark"),
        "custom_theme": user.get("custom_theme"),
        "available_themes": available_themes,
        "user_level": user_level
    }

# NEW: Follow System Endpoints
@api_router.post("/users/{user_id}/follow")
async def follow_user(user_id: str, follow_request: FollowRequest):
    """Follow another user"""
    follower_id = user_id
    target_id = follow_request.target_user_id
    
    # Can't follow yourself
    if follower_id == target_id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")
    
    # Check if both users exist
    follower = await db.users.find_one({"id": follower_id})
    target = await db.users.find_one({"id": target_id})
    
    if not follower or not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already following
    if target_id in follower.get("following", []):
        raise HTTPException(status_code=400, detail="Already following this user")
    
    # Add to follower's following list
    await db.users.update_one(
        {"id": follower_id},
        {
            "$push": {"following": target_id},
            "$inc": {"following_count": 1}
        }
    )
    
    # Add to target's followers list
    await db.users.update_one(
        {"id": target_id},
        {
            "$push": {"followers": follower_id},
            "$inc": {"follower_count": 1}
        }
    )
    
    # Award XP for social interaction
    await award_xp(follower_id, "follow_user", 10)
    
    # Create notification for the followed user
    follower_name = follower.get("screen_name") or follower.get("username")
    await create_user_notification(
        user_id=target_id,
        notification_type="follow",
        title=f"New Follower",
        message=f"{follower_name} started following you",
        data={
            "follower_id": follower_id,
            "follower_name": follower_name,
            "follower_avatar": follower.get("avatar_url"),
            "action": "follow"
        }
    )
    
    return {"message": "Successfully followed user"}

@api_router.post("/users/{user_id}/unfollow")
async def unfollow_user(user_id: str, follow_request: FollowRequest):
    """Unfollow another user"""
    follower_id = user_id
    target_id = follow_request.target_user_id
    
    # Check if both users exist
    follower = await db.users.find_one({"id": follower_id})
    target = await db.users.find_one({"id": target_id})
    
    if not follower or not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if actually following
    if target_id not in follower.get("following", []):
        raise HTTPException(status_code=400, detail="Not following this user")
    
    # Remove from follower's following list
    await db.users.update_one(
        {"id": follower_id},
        {
            "$pull": {"following": target_id},
            "$inc": {"following_count": -1}
        }
    )
    
    # Remove from target's followers list
    await db.users.update_one(
        {"id": target_id},
        {
            "$pull": {"followers": follower_id},
            "$inc": {"follower_count": -1}
        }
    )
    
    return {"message": "Successfully unfollowed user"}

@api_router.get("/users/{user_id}/notifications")
async def get_user_notifications(request: Request, user_id: str, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    """Read the member's inbox without changing unread state."""
    await require_profile_owner(request, user_id)
    notifications = await db.notifications.find(
        {"user_id": user_id}
    ).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    for notification in notifications:
        for field in ("created_at", "expires_at", "read_at"):
            if isinstance(notification.get(field), datetime):
                notification[field] = notification[field].isoformat()
        notification.pop("_id", None)
    return redact_auth_fields(notifications)

@api_router.put("/users/{user_id}/notifications/{notification_id}/read")
async def mark_notification_as_read(request: Request, user_id: str, notification_id: str):
    """Mark a notification read only after an explicit owner action."""
    await require_profile_owner(request, user_id)
    result = await db.notifications.update_one(
        {"id": notification_id, "user_id": user_id},
        {"$set": {"read": True, "read_at": datetime.utcnow()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification marked as read"}

@api_router.post("/users/{user_id}/notifications/read-all")
async def mark_all_notifications_as_read(request: Request, user_id: str):
    """Mark all of this member's notifications read after an explicit action."""
    await require_profile_owner(request, user_id)
    result = await db.notifications.update_many(
        {"user_id": user_id, "read": False},
        {"$set": {"read": True, "read_at": datetime.utcnow()}}
    )
    return {"message": f"Marked {result.modified_count} notifications as read", "count": result.modified_count}

@api_router.delete("/users/{user_id}/notifications/{notification_id}")
async def delete_notification(request: Request, user_id: str, notification_id: str):
    """Delete only the authenticated member's own notification."""
    await require_profile_owner(request, user_id)
    result = await db.notifications.delete_one({"id": notification_id, "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification deleted"}

@api_router.get("/users/{user_id}/notifications/unread-count")
async def get_unread_notification_count(request: Request, user_id: str):
    await require_profile_owner(request, user_id)
    count = await db.notifications.count_documents({"user_id": user_id, "read": False})
    return {"count": count, "message": f"Unread notification count: {count}"}

# Message Reaction Endpoints
REACTION_EMOJI = {"heart": "❤️", "thumbs_up": "👍", "money": "💰", "rocket": "🚀"}
REACTION_ALIASES = {"heart": "heart", "❤️": "heart", "❤": "heart",
                    "thumbs_up": "thumbs_up", "👍": "thumbs_up", "like": "thumbs_up",
                    "money": "money", "💰": "money", "rocket": "rocket", "🚀": "rocket"}

def normalize_reaction_type(value):
    if not isinstance(value, str) or value not in REACTION_ALIASES:
        raise HTTPException(status_code=422, detail="Choose heart, thumbs_up, money or rocket.")
    return REACTION_ALIASES[value]

@api_router.post("/messages/{message_id}/react")
async def add_message_reaction(request: Request, message_id: str, reaction_data: dict, background_tasks: BackgroundTasks):
    """Add a reaction to a message"""
    user_id = reaction_data.get("user_id")
    reaction_type = normalize_reaction_type(reaction_data.get("reaction_type", "heart"))
    if not isinstance(user_id, str) or not user_id or len(user_id) > 240:
        raise HTTPException(status_code=400, detail="User ID required")
    user = await require_profile_owner(request, user_id)
    # Get the existing message; the authenticated actor supplies the reaction.
    message = await db.messages.find_one({"id": message_id})
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user already reacted to this message
    existing_reaction = await db.reactions.find_one({
        "message_id": message_id,
        "user_id": user_id,
        "reaction_type": {"$in": [alias for alias, canonical in REACTION_ALIASES.items() if canonical == reaction_type]}
    })
    
    if existing_reaction:
        raise HTTPException(status_code=400, detail="Already reacted to this message")
    
    # Create reaction
    reaction = {
        "id": str(uuid.uuid4()),
        "message_id": message_id,
        "user_id": user_id,
        "reaction_type": reaction_type,
        "created_at": datetime.utcnow()
    }
    
    # A stable unique Mongo key prevents simultaneous taps/retries from awarding
    # the same initial reaction twice. Existing legacy reactions remain valid.
    reaction_key = hashlib.sha256((message_id + "\0" + user_id + "\0" + reaction_type).encode()).hexdigest()
    try:
        inserted = await db.reactions.update_one({"_id": reaction_key}, {"$setOnInsert": reaction}, upsert=True)
    except Exception as error:
        if getattr(error, "code", None) != 11000:
            raise
        raise HTTPException(status_code=400, detail="Already reacted to this message")
    if inserted.upserted_id is None:
        raise HTTPException(status_code=400, detail="Already reacted to this message")
    
    # Award XP for giving reaction
    await award_xp(user_id, "heart_reaction", 2)
    
    # Create notification for the message author (if not reacting to own message)
    if message["user_id"] != user_id:
        reactor_name = user.get("screen_name") or user.get("username")
        reaction_emoji = REACTION_EMOJI[reaction_type]
        
        await create_user_notification(
            user_id=message["user_id"],
            notification_type="reaction",
            title="New Reaction",
            message=f"{reactor_name} reacted {reaction_emoji} to your message: \"{message['content'][:50]}{'...' if len(message['content']) > 50 else ''}\"",
            data={
                "reactor_id": user_id,
                "reactor_name": reactor_name,
                "reactor_avatar": user.get("avatar_url"),
                "message_id": message_id,
                "reaction_type": reaction_type,
                "message_content": message["content"],
                "action": "reaction"
            }
        )
    
    await manager.broadcast(json.dumps({"type": "reaction_updated", "message_id": message_id}))
    return {"message": "Reaction added successfully"}

@api_router.delete("/messages/{message_id}/react")
async def remove_message_reaction(request: Request, message_id: str, user_id: str, reaction_type: str = "heart"):
    """Remove only this member's reaction, including its legacy emoji alias."""
    await require_profile_owner(request, user_id)
    reaction_type = normalize_reaction_type(reaction_type)
    result = await db.reactions.delete_many({
        "message_id": message_id,
        "user_id": user_id,
        "reaction_type": {"$in": [alias for alias, canonical in REACTION_ALIASES.items() if canonical == reaction_type]}
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Reaction not found")
    
    await manager.broadcast(json.dumps({"type": "reaction_updated", "message_id": message_id}))
    return {"message": "Reaction removed successfully"}

@api_router.get("/messages/{message_id}/reactions")
async def get_message_reactions(message_id: str):
    """Get all reactions for a message"""
    reactions = await db.reactions.find({"message_id": message_id}).to_list(1000)
    
    # Group reactions by type and get user info
    reaction_summary = {}
    for reaction in reactions:
        reaction_type = REACTION_ALIASES.get(reaction["reaction_type"])
        if not reaction_type:
            continue  # Preserve unsupported legacy records without exposing new UI types.
        if reaction_type not in reaction_summary:
            reaction_summary[reaction_type] = []
        
        # Get user info for the reaction
        user = await db.users.find_one({"id": reaction["user_id"]})
        if user:
            reaction_summary[reaction_type].append({
                "user_id": user["id"],
                "username": user["username"],
                "screen_name": user.get("screen_name"),
                "avatar_url": user.get("avatar_url"),
                "created_at": reaction["created_at"]
            })
    
    return reaction_summary

@api_router.get("/users/{user_id}/followers")
async def get_user_followers(user_id: str):
    """Get list of users following this user"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    follower_ids = user.get("followers", [])
    if not follower_ids:
        return {"followers": [], "count": 0}
    
    # Get follower details
    followers_cursor = db.users.find({"id": {"$in": follower_ids}})
    followers = []
    
    async for follower in followers_cursor:
        followers.append({
            "id": follower["id"],
            "username": follower["username"],
            "screen_name": follower.get("screen_name"),
            "avatar_url": follower.get("avatar_url"),
            "level": follower.get("level", 1),
            "is_admin": follower.get("is_admin", False),
            "is_online": follower.get("is_online", False)
        })
    
    return {"followers": followers, "count": len(followers)}

@api_router.get("/users/{user_id}/following")
async def get_user_following(user_id: str):
    """Get list of users this user is following"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    following_ids = user.get("following", [])
    if not following_ids:
        return {"following": [], "count": 0}
    
    # Get following details
    following_cursor = db.users.find({"id": {"$in": following_ids}})
    following = []
    
    async for followed_user in following_cursor:
        following.append({
            "id": followed_user["id"],
            "username": followed_user["username"],
            "screen_name": followed_user.get("screen_name"),
            "avatar_url": followed_user.get("avatar_url"),
            "level": followed_user.get("level", 1),
            "is_admin": followed_user.get("is_admin", False),
            "is_online": followed_user.get("is_online", False)
        })
    
    return {"following": following, "count": len(following)}

@api_router.get("/users/{user_id}/follow-status/{target_user_id}")
async def get_follow_status(user_id: str, target_user_id: str):
    """Check if user is following target user"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    is_following = target_user_id in user.get("following", [])
    return {"is_following": is_following}

# Bot Message System
@api_router.post("/bot/message")
async def create_bot_message(request: Request, message_data: dict):
    """Compatible Zapier URL; accepts only authenticated stock-alert intake."""
    return await stock_alert_service.ingest(request, message_data)

async def get_or_create_bot_user():
    """Get existing bot user or create one"""
    bot_user = await db.users.find_one({"username": "cashoutai_bot"})
    
    if not bot_user:
        # Create bot user
        bot_user = {
            "id": str(uuid.uuid4()),
            "username": "cashoutai_bot",
            "email": "bot@cashoutai.com",
            "real_name": "CashOutAi Bot",
            "screen_name": "🤖 CashOutAi Bot",
            "membership_plan": "premium",
            "is_admin": True,
            "is_bot": True,
            "role": "bot",
            "status": UserStatus.APPROVED,
            "avatar_url": None,
            "total_profit": 0,
            "win_percentage": 0,
            "trades_count": 0,
            "average_gain": 0,
            "is_online": True,
            "last_seen": datetime.utcnow(),
            "active_session_id": None,
            "session_created_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "approved_at": datetime.utcnow(),
            "approved_by": "system",
            "experience_points": 0,
            "level": 1,
            "daily_login_streak": 0,
            "last_login_date": None,
            "profile_banner": None,
            "bio": "Automated price alert bot for CashOutAi trading platform 🤖📈",
            "trading_style_tags": ["automated", "alerts", "price-tracking"],
            "custom_theme": None,
            "active_theme_name": "dark",
            "achievements": [],
            "achievement_progress": {},
            "location": "Cloud",
            "show_location": False,
            "followers": [],
            "following": [],
            "follower_count": 0,
            "following_count": 0
        }
        
        await db.users.insert_one(bot_user)
        logger.info("CashOutAi Bot user created")
    
    return bot_user

def parse_price_alert(content: str, subject: str = "") -> str:
    """Parse price alert email and format for chat"""
    try:
        # Extract ticker symbol (looks for patterns like "AIMH price alert" or "$AIMH")
        import re
        
        logger.info(f"🔍 PARSING EMAIL - Subject: '{subject}', Content: '{content}'")
        
        ticker = None
        price = None
        
        # Enhanced ticker detection patterns (case insensitive, prioritize standard tickers)
        ticker_patterns = [
            # Pattern 1: (TICKER) format - highest priority for stock symbols
            r'\(([A-Z]{2,5})\)',
            # Pattern 2: $TICKER format  
            r'\$([A-Z]{2,5})',
            # Pattern 3: "TICKER price alert" or "TICKER alert" 
            r'([A-Z]{2,5})\s+(?:price\s+)?alert',
            # Pattern 4: Start of content/subject
            r'^([A-Z]{2,5})\s',
            # Pattern 5: TICKER followed by trading keywords
            r'\b([A-Z]{2,5})\b(?=\s+(?:price|alert|Last|trading|has\s+reached))',
            # Pattern 6: Any isolated ticker (fallback)
            r'\b([A-Z]{2,5})\b'
        ]
        
        combined_text = content.upper() + " " + subject.upper()
        logger.info(f"🔍 COMBINED TEXT FOR TICKER SEARCH: '{combined_text}'")
        
        for i, pattern in enumerate(ticker_patterns):
            ticker_match = re.search(pattern, combined_text, re.IGNORECASE)
            if ticker_match:
                potential_ticker = ticker_match.group(1).upper()
                logger.info(f"🎯 Pattern {i+1} matched ticker: '{potential_ticker}'")
                # Filter out common words that aren't tickers
                if potential_ticker not in ['ALERT', 'PRICE', 'LAST', 'TEST', 'EMAIL', 'FROM', 'SENT', 'WITH', 'THAT', 'THIS', 'HAVE']:
                    ticker = potential_ticker
                    logger.info(f"✅ TICKER FOUND: {ticker}")
                    break
                else:
                    logger.info(f"❌ Ticker '{potential_ticker}' filtered out as common word")
        
        # Enhanced price detection patterns (case insensitive)
        price_patterns = [
            # Pattern 1: "Last = .04" or "Last = $0.04"
            r'Last\s*=\s*\$?([0-9]*\.?[0-9]+)',  
            # Pattern 2: "Last is at or above $.04"
            r'Last\s+is\s+at\s+or\s+above\s+\$([0-9]*\.?[0-9]+)',
            # Pattern 3: "trading at $250.75"
            r'trading\s+at\s+\$([0-9]*\.?[0-9]+)',
            # Pattern 4: Simple "$price" format
            r'\$([0-9]*\.?[0-9]+)',
            # Pattern 5: = $price format
            r'=\s*\$([0-9]*\.?[0-9]+)',
            # Pattern 6: price without $ symbol followed by common indicators
            r'price\s*:?\s*([0-9]*\.?[0-9]+)',
            # Pattern 7: Generic equals pattern
            r'=\s*([0-9]*\.?[0-9]+)',
            # Pattern 8: Any decimal number (fallback)
            r'([0-9]+\.[0-9]+)'
        ]
        
        logger.info(f"🔍 SEARCHING FOR PRICE IN: '{content}'")
        
        for i, pattern in enumerate(price_patterns):
            price_match = re.search(pattern, content, re.IGNORECASE)
            if price_match:
                price = price_match.group(1)
                logger.info(f"🎯 Pattern {i+1} matched price: '{price}'")
                break
        
        logger.info(f"📊 FINAL EXTRACTION - Ticker: {ticker}, Price: {price}")
        
        if ticker and price:
            # Format price properly
            try:
                price_float = float(price)
                if price_float < 1:
                    price_str = f"${price_float:.4f}".rstrip('0').rstrip('.')
                else:
                    price_str = f"${price_float:.2f}"
            except:
                price_str = f"${price}"
            
            # Create formatted message
            formatted = f"🔔 ${ticker} {price_str} 👀"
            
            logger.info(f"✅ Parsed price alert: ticker={ticker}, price={price_str}, formatted={formatted}")
            return formatted
        
        # Enhanced fallback - try to extract any meaningful info
        logger.warning(f"⚠️ Could not parse price alert properly")
        logger.warning(f"   Content: '{content[:100]}...'")
        logger.warning(f"   Subject: '{subject}'")
        logger.warning(f"   Ticker found: {ticker}")
        logger.warning(f"   Price found: {price}")
        
        # Last resort: if we have a ticker but no price, try simpler patterns
        if ticker and not price:
            simple_price = re.search(r'([0-9]+\.?[0-9]*)', content)
            if simple_price:
                price = simple_price.group(1)
                formatted = f"🔔 ${ticker} ${price} 👀"
                logger.info(f"✅ Fallback parse successful: {formatted}")
                return formatted
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Error parsing price alert: {e}")
        return None

def extract_tickers(message: str) -> list:
    """Extract ticker symbols from message for highlighting"""
    import re
    tickers = re.findall(r'\$([A-Z]{1,5})', message)
    return [{"symbol": ticker, "start": message.find(f"${ticker}"), "end": message.find(f"${ticker}") + len(ticker) + 1} for ticker in tickers]

# Email-to-Chat Bridge endpoint
@api_router.post("/bot/email-webhook")
async def email_webhook(request: Request, payload: dict):
    """Schwab thinkorswim email -> Zapier -> the persisted Stocks feed."""
    return await stock_alert_service.ingest(request, payload)

def is_price_alert_email(content: str, subject: str, sender: str) -> bool:
    """Determine if an email is a price alert that should be posted to chat"""
    
    # Trusted trading platform domains (case insensitive)
    trusted_domains = [
        'thinkorswim.com',
        'schwab.com', 
        'tradingview.com',
        'robinhood.com',
        'etrade.com',
        'fidelity.com',
        'alerts.com',
        'tradingplatform.com',
        'stocktrader.com',
        'alerts@',  # Generic alerts prefix
    ]
    
    # Check if sender is from trusted domain
    sender_lower = sender.lower()
    is_trusted_sender = any(domain in sender_lower for domain in trusted_domains)
    
    # Look for trading/alert keywords in subject and content
    alert_keywords = ['alert', 'price', 'target', 'reached', 'trading', 'last', 'bid', 'ask']
    combined_text = (subject + " " + content).lower()
    has_alert_keywords = any(keyword in combined_text for keyword in alert_keywords)
    
    # Look for ticker symbols (2-5 capital letters)
    has_ticker = bool(re.search(r'[A-Z]{2,5}', content + " " + subject))
    
    # Look for price information
    has_price = bool(re.search(r'\$[0-9]*\.?[0-9]+|Last\s*=|Bid\s*=|Ask\s*=', content + " " + subject))
    
    # Must have ticker, price info, and either trusted sender OR alert keywords
    is_alert = has_ticker and has_price and (is_trusted_sender or has_alert_keywords)
    
    logger.info(f"Email filter check - Sender: {sender}, Trusted: {is_trusted_sender}, Keywords: {has_alert_keywords}, Ticker: {has_ticker}, Price: {has_price}, Result: {is_alert}")
    
    return is_alert

@api_router.post("/messages", response_model=Message)
async def create_message(message_data: MessageCreate, background_tasks: BackgroundTasks):
    # Get user info
    user = await db.users.find_one({"id": message_data.user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check user status for chat access
    user_status = user.get("status")
    if user_status == UserStatus.TRIAL_EXPIRED:
        raise HTTPException(
            status_code=403, 
            detail="Chat access restricted. Your trial has expired. Upgrade your account to continue chatting with other traders."
        )
    elif user_status not in [UserStatus.APPROVED, UserStatus.TRIAL]:
        raise HTTPException(status_code=403, detail="Only approved users can send messages")
    
    # Extract stock tickers only for text messages
    tickers = []
    if message_data.content_type == "text":
        tickers = extract_stock_tickers(message_data.content)
    
    # Handle reply data
    reply_to_data = None
    if message_data.reply_to_id:
        reply_to_message = await db.messages.find_one({"id": message_data.reply_to_id})
        if reply_to_message:
            reply_to_data = {
                "id": reply_to_message["id"],
                "username": reply_to_message["username"],
                "screen_name": reply_to_message.get("screen_name"),
                "content": reply_to_message["content"][:200] if reply_to_message.get("content_type") != "image" else "[image]",
                "content_type": reply_to_message.get("content_type", "text")
            }
    
    message = Message(
        user_id=message_data.user_id,
        username=user["username"],
        content=message_data.content,
        content_type=message_data.content_type,
        is_admin=user.get("is_admin", False),
        avatar_url=user.get("avatar_url"),
        real_name=user.get("real_name"),
        screen_name=user.get("screen_name"),
        highlighted_tickers=tickers,
        reply_to_id=message_data.reply_to_id,
        reply_to=reply_to_data,
        text_content=message_data.text_content
    )
    
    await db.messages.insert_one(message.dict())
    
    # Broadcast message to all connected users IMMEDIATELY
    await manager.broadcast(json.dumps({
        "type": "message",
        "data": message.dict()
    }, default=str))
    
    # Move ALL heavy operations to background tasks
    background_tasks.add_task(post_message_tasks, message_data, message, user, reply_to_data)
    
    return message

async def post_message_tasks(message_data, message, user, reply_to_data):
    """Background task for XP, notifications, FCM - runs after response is sent"""
    try:
        # Award XP
        await award_xp(message_data.user_id, "chat_message", 5)
        
        # Award extra XP and notify for reply
        if message_data.reply_to_id:
            await award_xp(message_data.user_id, "reply_message", 8)
            if reply_to_data and reply_to_data.get("username"):
                original_sender = await db.users.find_one({"username": reply_to_data["username"]})
                if original_sender and original_sender["id"] != message_data.user_id:
                    replier_name = user.get("screen_name") or user.get("username")
                    await create_user_notification(
                        user_id=original_sender["id"],
                        notification_type="reply",
                        title="New Reply",
                        message=f"{replier_name} replied to your message: \"{message_data.content[:50]}{'...' if len(message_data.content) > 50 else ''}\"",
                        data={
                            "replier_id": message_data.user_id,
                            "replier_name": replier_name,
                            "replier_avatar": user.get("avatar_url"),
                            "original_message_id": reply_to_data["id"],
                            "reply_content": message_data.content,
                            "action": "reply"
                        }
                    )
        
        # Handle @mentions
        await handle_message_mentions(message_data.content, user, message.id)
        
        # Chat/admin messages keep their in-app WebSocket behavior. Device
        # pushes are reserved for the separately authenticated Stocks pipeline.
        if user.get("is_admin"):
            # Admin WebSocket notifications
            try:
                non_admin_users = await db.users.find({"is_admin": {"$ne": True}, "is_online": True}).to_list(1000)
                for nau in non_admin_users:
                    if nau["id"] in manager.user_connections:
                        try:
                            await manager.send_personal_message(json.dumps({
                                "type": "admin_notification",
                                "message": f"Admin {user.get('real_name') or user['username']}: {message_data.content}",
                                "admin_username": user['username'],
                                "content": message_data.content
                            }, default=str), manager.user_connections[nau["id"]])
                        except:
                            pass
            except Exception as e:
                print(f"Admin WS notification error: {e}")
    except Exception as e:
        print(f"Background task error: {e}")

@api_router.delete("/messages/{message_id}")
async def delete_message(message_id: str, user_id: str):
    """Delete a message - admin only"""
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.messages.delete_one({"id": message_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Broadcast deletion to all connected clients
    await manager.broadcast(json.dumps({
        "type": "message_deleted",
        "data": {"id": message_id}
    }))
    
    return {"message": "Message deleted", "id": message_id}

@api_router.delete("/messages/cleanup/debug")
async def cleanup_debug_messages(user_id: str):
    """Delete all debug messages from chat - admin only"""
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.messages.delete_many({"content": {"$regex": "DEBUG:"}})
    return {"message": f"Deleted {result.deleted_count} debug message(s)"}

@api_router.get("/messages", response_model=List[Message])
async def get_messages(limit: int = 50, user_id: Optional[str] = None, before: Optional[str] = None):
    # TRIAL SYSTEM: Check user access for chat viewing
    if user_id:
        user = await db.users.find_one({"id": user_id})
        if user and user.get("status") == UserStatus.TRIAL_EXPIRED:
            raise HTTPException(
                status_code=403, 
                detail="Chat viewing restricted. Your trial has expired. Upgrade your account to view trader discussions."
            )
    
    query = {}
    if before:
        query["timestamp"] = {"$lt": before}
    
    projection = {"_id": 0}
    messages = await db.messages.find(query, projection).sort("timestamp", -1).limit(limit).to_list(limit)
    
    cleaned_messages = []
    for message in messages:
        try:
            # PERFORMANCE: For image messages, replace huge base64 content with placeholder
            # Frontend will lazy-load full image via /api/messages/{id}/image
            if message.get('content_type') == 'image' and message.get('content', '').startswith('data:'):
                message['content'] = f"__IMAGE__{message.get('id', '')}__"
            
            if 'highlighted_tickers' in message:
                tickers = message['highlighted_tickers']
                if isinstance(tickers, list) and tickers:
                    if isinstance(tickers[0], dict):
                        message['highlighted_tickers'] = [ticker.get('symbol', '') for ticker in tickers if isinstance(ticker, dict) and 'symbol' in ticker]
                    elif not isinstance(tickers[0], str):
                        message['highlighted_tickers'] = []
                else:
                    message['highlighted_tickers'] = []
            else:
                message['highlighted_tickers'] = []
            
            message.setdefault('content_type', 'text')
            message.setdefault('is_admin', False)
            message.setdefault('avatar_url', None)
            message.setdefault('real_name', None)
            message.setdefault('screen_name', None)
            message.setdefault('reply_to_id', None)
            message.setdefault('reply_to', None)
            message.setdefault('text_content', None)
            
            cleaned_messages.append(message)
        except Exception as e:
            logger.warning(f"Skipping invalid message: {e}")
            continue
    
    cleaned_messages.reverse()
    
    try:
        return [Message(**message) for message in cleaned_messages]
    except Exception as e:
        logger.error(f"Error creating Message objects: {e}")
        return []

@api_router.get("/messages/{message_id}/image")
async def get_message_image(message_id: str):
    """Fetch full image content for a single message - used for lazy loading"""
    message = await db.messages.find_one({"id": message_id}, {"_id": 0, "content": 1, "content_type": 1})
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    if message.get("content_type") != "image":
        raise HTTPException(status_code=400, detail="Not an image message")
    return {"image_url": message.get("content", "")}

@api_router.get("/messages/welcome", response_model=List[Message])
async def get_welcome_messages(user_id: Optional[str] = None):
    """Get recent message history for new users to provide context"""
    # TRIAL SYSTEM: Check user access for chat viewing
    if user_id:
        user = await db.users.find_one({"id": user_id})
        if user and user.get("status") == UserStatus.TRIAL_EXPIRED:
            raise HTTPException(
                status_code=403, 
                detail="Chat viewing restricted. Your trial has expired. Upgrade your account to view trader discussions."
            )
    
    # Get last 500 messages to provide good historical context for new users
    messages = await db.messages.find().sort("timestamp", -1).limit(500).to_list(500)
    
    # Clean up messages for compatibility (same logic as regular get_messages)
    cleaned_messages = []
    for message in messages:
        try:
            # Fix highlighted_tickers format for compatibility
            if 'highlighted_tickers' in message:
                tickers = message['highlighted_tickers']
                if isinstance(tickers, list) and tickers:
                    if isinstance(tickers[0], dict):
                        message['highlighted_tickers'] = [ticker.get('symbol', '') for ticker in tickers if isinstance(ticker, dict) and 'symbol' in ticker]
                    elif not isinstance(tickers[0], str):
                        message['highlighted_tickers'] = []
                else:
                    message['highlighted_tickers'] = []
            else:
                message['highlighted_tickers'] = []
            
            # Ensure all required fields exist with defaults
            message.setdefault('content_type', 'text')
            message.setdefault('avatar_url', None)
            message.setdefault('is_admin', False)
            message.setdefault('screen_name', message.get('username', 'Unknown'))
            
            # Ensure reply_to exists
            message.setdefault('reply_to', None)
            
            cleaned_messages.append(Message(**message))
            
        except ValidationError as e:
            logger.error(f"Validation error for message {message.get('id', 'unknown')}: {e}")
            continue
        except Exception as e:
            logger.error(f"Error processing message {message.get('id', 'unknown')}: {e}")
            continue
    
    logger.info(f"📚 NEW USER WELCOME: Loaded {len(cleaned_messages)} historical messages")
    return cleaned_messages

@api_router.post("/trades", response_model=PaperTrade)
async def create_paper_trade(trade_data: PaperTradeCreate, user_id: str):
    """Create a new paper trade"""
    # Verify user exists and is approved
    user = await db.users.find_one({"id": user_id})
    if not active_membership(user, datetime.utcnow()):
        raise HTTPException(status_code=403, detail=MEMBERSHIP_REQUIRED)
    
    if quote_number(trade_data.price, positive=True) is None or trade_data.quantity <= 0 or trade_data.action not in {"BUY", "SELL"}:
        raise HTTPException(status_code=422, detail="Use a positive quantity and finite, positive manual journal price.")
    trade = PaperTrade(
        user_id=user_id,
        price_source="manual_journal", price_verified=False,
        **trade_data.dict()
    )
    
    await db.paper_trades.insert_one(trade.dict())
    
    # Update or create position
    await update_or_create_position(
        user_id=user_id,
        symbol=trade_data.symbol,
        action=trade_data.action,
        quantity=trade_data.quantity,
        price=trade_data.price,
        trade_id=trade.id,
        stop_loss=trade_data.stop_loss,
        take_profit=trade_data.take_profit
    )
    
    # Update user performance metrics
    performance = await calculate_user_performance(user_id)
    await db.users.update_one(
        {"id": user_id},
        {"$set": performance}
    )
    
    # Award XP for trading activity
    await award_xp(user_id, "trade_executed", 25)
    
    # Award extra XP for profitable trades  
    if trade_data.action == "SELL":
        # Calculate if this specific SELL trade was profitable
        # Get the position that was just updated/closed
        position = await db.positions.find_one({
            "user_id": user_id, 
            "symbol": trade_data.symbol.upper()
        })
        
        if position:
            # Calculate P&L for this specific trade
            buy_price = position.get("avg_price", 0)  # Use avg_price (correct field name)
            sell_price = trade_data.price
            quantity_sold = trade_data.quantity
            
            # Calculate profit/loss for this specific trade
            trade_pnl = (sell_price - buy_price) * quantity_sold
            
            logger.info(f"Trade P&L calculation: user={user_id}, symbol={trade_data.symbol}, buy_price={buy_price}, sell_price={sell_price}, quantity={quantity_sold}, pnl={trade_pnl}")
            
            # Award profitable trade XP if this specific trade was profitable
            if trade_pnl > 0:
                logger.info(f"🎯 PROFITABLE TRADE DETECTED! User {user_id} made ${trade_pnl:.2f} profit on {trade_data.symbol}")
                await award_xp(user_id, "profitable_trade", 50)
            else:
                logger.info(f"📉 Trade was not profitable: User {user_id} lost ${abs(trade_pnl):.2f} on {trade_data.symbol}")
        else:
            logger.warning(f"⚠️ Could not find position for profitable trade calculation: user={user_id}, symbol={trade_data.symbol}")
            
            # Fallback: Check if the user's total profit increased
            # This ensures we don't miss profitable trades due to timing issues
            if performance.get("total_profit", 0) > 0:
                logger.info(f"🎯 FALLBACK: User {user_id} has positive total profit: ${performance.get('total_profit', 0):.2f}")
                await award_xp(user_id, "profitable_trade", 50)
    
    return trade

@api_router.get("/positions/{user_id}")
async def get_user_positions(user_id: str):
    """Get all open positions for a user with current P&L and proper formatting"""
    # Update P&L first
    await update_positions_pnl(user_id)
    
    # Get updated positions
    positions = await db.positions.find({"user_id": user_id, "is_open": True}).to_list(1000)
    
    # Format the positions for frontend display
    formatted_positions = []
    for position in positions:
        formatted_position = Position(**position).dict()
        formatted_position.update({
            "quote": position.get("quote"),
            "valuation_status": position.get("valuation_status", "unavailable"),
            "valuation_as_of": position.get("valuation_as_of"),
            "valuation_received_at": position.get("valuation_received_at"),
            "price_provenance": position.get("price_provenance", "legacy_unverified"),
            "execution_eligible": position.get("execution_eligible", False),
        })
        # Add formatted values for frontend
        formatted_position["formatted_avg_price"] = format_price_display(position.get("avg_price"))
        formatted_position["formatted_current_price"] = format_price_display(position.get("current_price"))
        formatted_position["formatted_unrealized_pnl"] = format_pnl_display(position.get("unrealized_pnl"))
        formatted_positions.append(formatted_position)
    
    return formatted_positions

@api_router.post("/positions/{position_id}/action")
async def position_action(position_id: str, action_data: PositionAction, user_id: str):
    """Perform action on position: buy more, sell partial, or sell all"""
    position = await db.positions.find_one({"id": position_id, "user_id": user_id, "is_open": True})
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    
    # User-supplied journal prices remain permitted, with explicit provenance.
    # Omitting one requires an execution-qualified quote and otherwise fails.
    if action_data.price is not None:
        current_price = quote_number(action_data.price, positive=True)
        if current_price is None:
            raise HTTPException(status_code=422, detail="Enter a finite, positive manual journal price.")
        price_source = "manual_journal"
    else:
        current_price = await get_current_stock_price(position["symbol"])
        price_source = "provider_paper_fill"
    
    if action_data.action == "BUY_MORE":
        if not action_data.quantity or action_data.quantity <= 0:
            raise HTTPException(status_code=400, detail="Quantity required for buy more action")
        
        # Create BUY trade
        trade = PaperTrade(
            user_id=user_id,
            symbol=position["symbol"],
            action="BUY",
            quantity=action_data.quantity,
            price=current_price,
            price_source=price_source,
            price_verified=False,
            position_id=position_id,
            notes=f"Added to existing position"
        )
        await db.paper_trades.insert_one(trade.dict())
        
        # Update position
        new_quantity = position["quantity"] + action_data.quantity
        new_avg_price = ((position["avg_price"] * position["quantity"]) + (current_price * action_data.quantity)) / new_quantity
        
        await db.positions.update_one(
            {"id": position_id},
            {"$set": {
                "quantity": new_quantity,
                "avg_price": round(new_avg_price, 8)
            }}
        )
        
        return {"message": f"Added {action_data.quantity} shares at ${current_price}", "price_source": price_source, "price_verified": False}
    
    elif action_data.action in ["SELL_PARTIAL", "SELL_ALL"]:
        sell_quantity = action_data.quantity if action_data.action == "SELL_PARTIAL" else position["quantity"]
        
        if not sell_quantity or sell_quantity <= 0:
            raise HTTPException(status_code=400, detail="Invalid sell quantity")
        
        if sell_quantity > position["quantity"]:
            raise HTTPException(status_code=400, detail="Cannot sell more than owned")
        
        # Create SELL trade
        trade = PaperTrade(
            user_id=user_id,
            symbol=position["symbol"],
            action="SELL",
            quantity=sell_quantity,
            price=current_price,
            price_source=price_source,
            price_verified=False,
            position_id=position_id,
            is_closed=(sell_quantity == position["quantity"]),
            notes=f"{'Full' if sell_quantity == position['quantity'] else 'Partial'} position close"
        )
        await db.paper_trades.insert_one(trade.dict())
        
        # Update position
        if sell_quantity == position["quantity"]:
            # Close entire position
            realized_pnl = (current_price - position["avg_price"]) * sell_quantity
            await db.positions.update_one(
                {"id": position_id},
                {"$set": {
                    "is_open": False,
                    "closed_at": datetime.utcnow(),
                    "current_price": current_price,
                    "unrealized_pnl": round(realized_pnl, 8),
                    "quantity": 0
                }}
            )
        else:
            # Partial close
            new_quantity = position["quantity"] - sell_quantity
            await db.positions.update_one(
                {"id": position_id},
                {"$set": {"quantity": new_quantity}}
            )
        
        profit_loss = (current_price - position["avg_price"]) * sell_quantity
        return {"message": f"Sold {sell_quantity} shares at ${current_price}", "profit_loss": round(profit_loss, 2), "price_source": price_source, "price_verified": False}
    
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

@api_router.post("/positions/{position_id}/close")
async def close_position(position_id: str, user_id: str):
    """Close an entire position at current market price"""
    position = await db.positions.find_one({"id": position_id, "user_id": user_id, "is_open": True})
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    
    # Get current price
    current_price = await get_current_stock_price(position["symbol"])
    realized_pnl = (current_price - position["avg_price"]) * position["quantity"]
    
    # Create SELL trade to record the close
    close_trade = PaperTrade(
        user_id=user_id,
        symbol=position["symbol"],
        action="SELL",
        quantity=position["quantity"],
        price=current_price,
        position_id=position_id,
        is_closed=True,
        notes="Position closed at market price"
    )
    
    await db.paper_trades.insert_one(close_trade.dict())
    
    # Close the position
    await db.positions.update_one(
        {"id": position_id},
        {"$set": {
            "is_open": False,
            "closed_at": datetime.utcnow(),
            "current_price": current_price,
            "unrealized_pnl": round(realized_pnl, 8),
            "quantity": 0,
            "auto_close_reason": "MANUAL"
        }}
    )
    
    # Update user performance metrics
    performance = await calculate_user_performance(user_id)
    await db.users.update_one(
        {"id": user_id},
        {"$set": performance}
    )
    
    return {"message": "Position closed successfully", "realized_pnl": round(realized_pnl, 2)}

@api_router.get("/trades/{user_id}")
async def get_user_trades(user_id: str):
    """Get all trades for a user"""
    trades = await db.paper_trades.find({"user_id": user_id}).sort("timestamp", -1).to_list(1000)
    return [PaperTrade(**trade) for trade in trades]

@api_router.get("/trades/{user_id}/history")
async def get_user_trade_history(user_id: str, limit: int = 50):
    """Get condensed trade history with P&L calculations for closed positions"""
    # Get all trades for the user, sorted by most recent first
    trades = await db.paper_trades.find({"user_id": user_id}).sort("timestamp", -1).to_list(limit)
    
    if not trades:
        return []
    
    # Calculate P&L for closed positions
    trade_history = []
    position_tracker = {}  # Track open positions per symbol
    
    # Process trades in chronological order for P&L calculation
    for trade in reversed(trades):
        symbol = trade["symbol"]
        action = trade["action"]
        quantity = trade["quantity"]
        price = trade["price"]
        
        # Initialize symbol tracking if needed
        if symbol not in position_tracker:
            position_tracker[symbol] = {"shares": 0, "total_cost": 0, "avg_price": 0}
        
        trade_entry = {
            "id": trade["id"],
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "price": price,
            "price_source": trade.get("price_source", "legacy_unverified"),
            "price_verified": trade.get("price_verified", False),
            "timestamp": trade["timestamp"],
            "formatted_price": format_price_display(price),
            "profit_loss": None,
            "formatted_profit_loss": None,
            "is_closed": False
        }
        
        if action == "BUY":
            # Add to position
            position_tracker[symbol]["shares"] += quantity
            position_tracker[symbol]["total_cost"] += quantity * price
            if position_tracker[symbol]["shares"] > 0:
                position_tracker[symbol]["avg_price"] = position_tracker[symbol]["total_cost"] / position_tracker[symbol]["shares"]
        
        elif action == "SELL" and position_tracker[symbol]["shares"] > 0:
            # Calculate P&L for this sell
            avg_cost = position_tracker[symbol]["avg_price"]
            sell_quantity = min(quantity, position_tracker[symbol]["shares"])
            profit_loss = (price - avg_cost) * sell_quantity
            
            trade_entry["profit_loss"] = profit_loss
            trade_entry["formatted_profit_loss"] = format_pnl_display(profit_loss)
            trade_entry["is_closed"] = True
            
            # Update position
            sold_cost = avg_cost * sell_quantity
            position_tracker[symbol]["shares"] -= sell_quantity
            position_tracker[symbol]["total_cost"] -= sold_cost
            
            if position_tracker[symbol]["shares"] <= 0:
                position_tracker[symbol]["total_cost"] = 0
        
        trade_history.append(trade_entry)
    
    # Return in reverse chronological order (most recent first)
    return list(reversed(trade_history))

@api_router.get("/users/{user_id}/performance")
async def get_user_performance(user_id: str):
    performance = await calculate_user_performance(user_id)
    return performance

@api_router.put("/users/{user_id}/profile", response_model=User)
async def update_user_profile(request: Request, user_id: str, profile_data: ExistingProfileUpdate):
    """Update user profile information"""
    user = await require_profile_owner(request, user_id)
    
    # Prepare update data
    update_data = {}
    if profile_data.real_name is not None:
        update_data["real_name"] = profile_data.real_name
    if profile_data.screen_name is not None:
        update_data["screen_name"] = profile_data.screen_name
    if profile_data.username is not None:
        username = profile_data.username.strip()
        if not username:
            raise HTTPException(status_code=422, detail="Username is required.")
        existing = await db.users.find_one({"username": {"$regex": rf"^\s*{re.escape(username)}\s*$", "$options": "i"}})
        if existing and existing["id"] != user_id:
            raise HTTPException(status_code=400, detail="Username already exists")
        update_data.update(username=username, registration_username_key=username.casefold())
    if profile_data.email is not None:
        email = profile_data.email.strip().lower()
        if not email:
            raise HTTPException(status_code=422, detail="Email is required.")
        existing = await db.users.find_one({"email": {"$regex": rf"^\s*{re.escape(email)}\s*$", "$options": "i"}})
        if existing and existing["id"] != user_id:
            raise HTTPException(status_code=400, detail="Email already exists")
        update_data.update(email=email, registration_email_key=email)

    if "registration_email_key" in update_data or "registration_username_key" in update_data:
        try:
            from .practice_event import ensure_registration_indexes
        except ImportError:
            from practice_event import ensure_registration_indexes
        try:
            await ensure_registration_indexes(db)
        except Exception:
            raise HTTPException(503, detail="Account updates are temporarily unavailable. Please try again later.") from None
    
    # Update user
    if update_data:
        update = {"$set": update_data}
        if "email" in update_data and update_data["email"] != user.get("email"):
            update["$unset"] = {"reset_token": "", "reset_token_hash": "", "reset_expires": "", "reset_context_hash": ""}
        try:
            updated = await db.users.update_one(
                {"id": user_id, "active_session_id": user["active_session_id"],
                 "email": user["email"]}, update)
            if not updated.matched_count:
                raise HTTPException(409, detail="Account access changed. Please sign in again before updating your profile.")
        except Exception as error:
            if getattr(error, "code", None) == 11000:
                raise HTTPException(409, detail="Another account already uses that username or email.") from None
            raise
    
    # Get updated user
    updated_user = await db.users.find_one({"id": user_id})
    return User(**updated_user)

@api_router.post("/upload-video")
async def upload_intro_video(video: UploadFile = File(...)):
    """Upload intro video for the application"""
    try:
        # Validate file type
        if not video.content_type.startswith('video/'):
            raise HTTPException(status_code=400, detail="File must be a video")
        
        # Check file size (max 50MB)
        if video.size > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size must be less than 50MB")
        
        # Define the path where the video will be saved
        frontend_public_path = Path("/app/frontend/public")
        video_path = frontend_public_path / "intro-video.mp4"
        
        # Create directory if it doesn't exist
        frontend_public_path.mkdir(parents=True, exist_ok=True)
        
        # Save the uploaded video
        with open(video_path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
        
        # Update the video source in LoadingScreen.js to use local file
        loading_screen_path = Path("/app/frontend/src/LoadingScreen.js")
        if loading_screen_path.exists():
            with open(loading_screen_path, "r") as f:
                content = f.read()
            
            # Replace Google Drive URLs with local video path
            content = content.replace(
                'https://drive.usercontent.google.com/download?id=10geS9b6QtH8ulGiEQE6TOJT00sPoNgQA&export=download',
                '/intro-video.mp4'
            )
            content = content.replace(
                'https://drive.google.com/uc?id=10geS9b6QtH8ulGiEQE6TOJT00sPoNgQA&export=download',
                '/intro-video.mp4'
            )
            
            with open(loading_screen_path, "w") as f:
                f.write(content)
        
        return {
            "message": "Video uploaded successfully",
            "filename": "intro-video.mp4",
            "size": video.size,
            "path": str(video_path)
        }
        
    except Exception as e:
        logger.error(f"Error uploading video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading video: {str(e)}")

# Stock intake and reads use their own external/member authentication boundaries.
try:
    from .stock_alerts import StockAlertService, active_membership
    from .membership import MEMBERSHIP_REQUIRED, utc_datetime, iso_date
    from .account_credentials import password_record
    from .square_billing import SquareBillingService
    from .practice_event import PracticeEventService
    from .traffic_analytics import create_traffic_router
except ImportError:
    from stock_alerts import StockAlertService, active_membership
    from membership import MEMBERSHIP_REQUIRED, utc_datetime, iso_date
    from account_credentials import password_record
    from square_billing import SquareBillingService
    from practice_event import PracticeEventService
    from traffic_analytics import create_traffic_router
practice_event_service = PracticeEventService(
    db, email_sender=email_service.send_email if email_service else None)
app.include_router(practice_event_service.router())
app.include_router(create_traffic_router(db, require_authenticated_admin, limiter))
stock_alert_service = StockAlertService(db, require_profile_owner, get_active_fcm_tokens, community_broadcast=manager.broadcast)
app.include_router(stock_alert_service.router())
square_billing_service = SquareBillingService(
    db, require_profile_owner, verify_password,
    welcome_sender=email_service.send_general_welcome_email_outcome if email_service else None)
app.include_router(square_billing_service.router())

# Include the router in the main app
app.include_router(api_router, dependencies=[Depends(require_legacy_active_session)])

# Five authenticated PAPER observation rooms and per-member practice accounts.
try:
    from .nautilus_api import create_nautilus_router
    from .kalshi_settlements import NautilusSettlementService
except ImportError:
    from nautilus_api import create_nautilus_router
    from kalshi_settlements import NautilusSettlementService
nautilus_settlement_service = NautilusSettlementService(db)

async def broadcast_bot_session_started(notice):
    # Shared in-app event only. Existing access/session checks run before each
    # socket delivery; Stocks remains the sole device-push channel.
    await manager.broadcast(json.dumps({"type": "bot_session_started", "notice": notice}))

app.include_router(create_nautilus_router(db, settlement_service=nautilus_settlement_service,
                                         on_session_started=broadcast_bot_session_started))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
