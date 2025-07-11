import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
import uuid
import secrets

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
from cash_prize import create_pending_cash_prize

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException, File, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
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


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Try to import and initialize email service
try:
    sys.path.append(str(ROOT_DIR))
    from email_service import email_service
    print("Email service initialized successfully")
except Exception as e:
    email_service = None
    print(f"Warning: Email service not available. Email notifications will be disabled. Error: {e}")

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# FCM Token storage model
class FCMToken(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    token: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

@api_router.post("/fcm/register-token")
async def register_fcm_token(token_data: Dict[str, str]):
    """Register FCM token for a user"""
    user_id = token_data.get("user_id")
    token = token_data.get("token")
    
    if not user_id or not token:
        raise HTTPException(status_code=400, detail="user_id and token are required")
    
    try:
        # Check if token already exists for this user
        existing_token = await db.fcm_tokens.find_one({"user_id": user_id})
        
        if existing_token:
            # Update existing token
            await db.fcm_tokens.update_one(
                {"user_id": user_id},
                {"$set": {"token": token, "updated_at": datetime.utcnow()}}
            )
        else:
            # Create new token entry
            fcm_token = FCMToken(user_id=user_id, token=token)
            await db.fcm_tokens.insert_one(fcm_token.dict())
        
        return {"message": "Token registered successfully"}
    except Exception as e:
        logger.error(f"Error registering FCM token: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to register token")

@api_router.post("/fcm/test-notification")
async def test_notification(test_data: Dict[str, str]):
    """Send test notification"""
    token = test_data.get("token")
    
    if not token:
        raise HTTPException(status_code=400, detail="token is required")
    
    try:
        from fcm_service import fcm_service
        
        # In test mode, just log and return success
        logger.info(f"Sending test notification to token: {token}")
        
        # This will now succeed even in test environment
        success = await fcm_service.send_notification(
            token=token,
            title="🎉 Test Notification",
            body="This is a test notification from ArgusAI CashOut!",
            data={"type": "test"}
        )
        
        return {"message": "Test notification sent successfully"}
    except Exception as e:
        logger.error(f"Error sending test notification: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send test notification")

async def send_notification_to_admins(title: str, body: str, data: Optional[Dict[str, str]] = None):
    """Send notification to all admin users"""
    try:
        from fcm_service import fcm_service
        
        # Get all admin users
        admin_users = await db.users.find({"is_admin": True}).to_list(1000)
        admin_user_ids = [user["id"] for user in admin_users]
        
        # Get FCM tokens for admin users
        admin_tokens = await db.fcm_tokens.find({"user_id": {"$in": admin_user_ids}}).to_list(1000)
        token_list = [token["token"] for token in admin_tokens]
        
        if token_list:
            result = await fcm_service.send_to_multiple(
                tokens=token_list,
                title=title,
                body=body,
                data=data
            )
            logger.info(f"Sent notification to {result.get('success_count', 0)} admin users")
            return result
    except Exception as e:
        logger.error(f"Error sending notification to admins: {str(e)}")
        return None

async def send_notification_to_user(user_id: str, title: str, body: str, data: Optional[Dict[str, str]] = None):
    """Send notification to a specific user"""
    try:
        from fcm_service import fcm_service
        
        # Get FCM token for user
        user_token = await db.fcm_tokens.find_one({"user_id": user_id})
        
        if user_token:
            success = await fcm_service.send_notification(
                token=user_token["token"],
                title=title,
                body=body,
                data=data
            )
            logger.info(f"Sent notification to user {user_id}: {success}")
            return success
    except Exception as e:
        logger.error(f"Error sending notification to user {user_id}: {str(e)}")
        return False

async def create_user_notification(user_id: str, notification_type: str, title: str, message: str, data: Dict[str, Any] = None):
    """Create a notification for a user"""
    notification = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": notification_type,
        "title": title,
        "message": message,
        "data": data or {},
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
            await manager.user_connections[user_id].send_text(json.dumps({
                "type": "notification",
                "notification": websocket_notification
            }))
        except:
            pass  # Ignore WebSocket errors
    
    # Send FCM notification
    await send_notification_to_user(user_id, title, message, data)
    
    return notification

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.user_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.user_connections[user_id] = websocket

    def disconnect(self, websocket: WebSocket, user_id: str):
        self.active_connections.remove(websocket)
        if user_id in self.user_connections:
            del self.user_connections[user_id]

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

    async def send_admin_notification(self, message: str):
        """Send notifications to all connected admins"""
        admin_users = await db.users.find({"is_admin": True}).to_list(1000)
        admin_ids = [user["id"] for user in admin_users]
        
        for user_id in admin_ids:
            if user_id in self.user_connections:
                try:
                    await self.user_connections[user_id].send_text(message)
                except:
                    pass

    async def send_session_invalidation(self, user_id: str, new_session_id: str):
        """Send session invalidation message to user's old sessions"""
        if user_id in self.user_connections:
            try:
                # Send message but don't close connection immediately
                await self.user_connections[user_id].send_text(json.dumps({
                    "type": "session_invalidated",
                    "message": "Your session has been terminated due to login from another location",
                    "new_session_id": new_session_id
                }))
                print(f"Sent session invalidation message to user {user_id}")
            except Exception as e:
                print(f"Error sending session invalidation message to user {user_id}: {e}")
                # Force remove the connection even if sending fails
                if user_id in self.user_connections:
                    del self.user_connections[user_id]

manager = ConnectionManager()

# Define Enums
class UserStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class UserRole(str, Enum):
    MEMBER = "member"
    MODERATOR = "moderator"
    ADMIN = "admin"

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
    active_session_id: Optional[str] = None  # NEW: Single active session tracking
    session_created_at: Optional[datetime] = None  # NEW: Session timestamp
    created_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    
    # NEW: Experience Points System
    experience_points: int = 0
    level: int = 1
    daily_login_streak: int = 0
    last_login_date: Optional[str] = None  # YYYY-MM-DD format
    
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

class UserCreate(BaseModel):
    username: str
    email: str
    real_name: str  # NEW: Required real name
    membership_plan: str  # NEW: Required membership plan
    password: str
    referral_code: Optional[str] = None  # Optional referral code of referring user

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
    email: str

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class UserApproval(BaseModel):
    user_id: str
    approved: bool
    admin_id: str
    role: Optional[UserRole] = UserRole.MEMBER  # NEW: Role assignment during approval

class UserRoleUpdate(BaseModel):
    user_id: str
    new_role: UserRole

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

class MessageCreate(BaseModel):
    content: str
    content_type: str = "text"  # NEW: Support for different content types
    user_id: str
    reply_to_id: Optional[str] = None  # NEW: Support for replies

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
        "description": "Successfully referred a new member - WIN UP TO $400 CASH! 💸",
        "icon": "💰",
        "points_reward": 200,
        "requirement_type": "referral",
        "requirement_value": 1,
        "category": "growth",
        "cash_prize_eligible": True,
        "max_cash_prize": 400
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
    """Check and award achievements based on user actions"""
    try:
        user = await db.users.find_one({"id": user_id})
        if not user:
            return
            
        user_achievements = user.get("achievements", [])
        progress = user.get("achievement_progress", {})
        
        # Update progress based on action
        if action == "chat_message":
            progress["chatterbox_count"] = progress.get("chatterbox_count", 0) + 1
        elif action == "heart_reaction":
            progress["heart_giver_count"] = progress.get("heart_giver_count", 0) + 1
        elif action == "profitable_trade":
            progress["profitable_trades"] = progress.get("profitable_trades", 0) + 1
        elif action == "daily_login":
            progress["login_streak"] = metadata.get("streak", 0)
        elif action == "referral_success":
            progress["successful_referrals"] = progress.get("successful_referrals", 0) + 1
        
        # Check for new achievements
        new_achievements = []
        
        for achievement_id, achievement in ACHIEVEMENTS.items():
            if achievement_id in user_achievements:
                continue  # Already earned
                
            earned = False
            
            if achievement_id == "chatterbox" and progress.get("chatterbox_count", 0) >= 100:
                earned = True
            elif achievement_id == "heart_giver" and progress.get("heart_giver_count", 0) >= 50:
                earned = True
            elif achievement_id == "dedication" and progress.get("login_streak", 0) >= 30:
                earned = True
            elif achievement_id == "first_blood" and progress.get("profitable_trades", 0) >= 1:
                earned = True
            elif achievement_id == "profit_1k" and user.get("total_profit", 0) >= 1000:
                earned = True
            elif achievement_id == "profit_2k" and user.get("total_profit", 0) >= 2000:
                earned = True
            elif achievement_id == "profit_3k" and user.get("total_profit", 0) >= 3000:
                earned = True
            elif achievement_id == "profit_4k" and user.get("total_profit", 0) >= 4000:
                earned = True
            elif achievement_id == "profit_5k" and user.get("total_profit", 0) >= 5000:
                earned = True
            elif achievement_id == "team_member_3m":
                # Check if user has been a member for 3 months (90 days)
                created_at = user.get("created_at")
                if created_at:
                    if isinstance(created_at, str):
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    days_since_creation = (datetime.utcnow() - created_at).days
                    if days_since_creation >= 90:
                        earned = True
            elif achievement_id == "team_member_8m":
                # Check if user has been a member for 8 months (240 days)
                created_at = user.get("created_at")
                if created_at:
                    if isinstance(created_at, str):
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    days_since_creation = (datetime.utcnow() - created_at).days
                    if days_since_creation >= 240:
                        earned = True
            elif achievement_id == "team_member_12m":
                # Check if user has been a member for 12 months (365 days)
                created_at = user.get("created_at")
                if created_at:
                    if isinstance(created_at, str):
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    days_since_creation = (datetime.utcnow() - created_at).days
                    if days_since_creation >= 365:
                        earned = True
            elif achievement_id == "referral_master":
                # Check if user has successfully referred someone
                successful_referrals = user.get("successful_referrals", 0)
                if successful_referrals >= 1:
                    earned = True
                
            if earned:
                new_achievements.append(achievement_id)
                await award_xp(user_id, "achievement_unlocked", achievement["points_reward"])
                
                # Handle cash prize for referral achievement
                if achievement_id == "referral_master" and achievement.get("cash_prize_eligible"):
                    await create_pending_cash_prize(user_id, achievement_id, achievement.get("max_cash_prize", 400))
        
        # Update user progress and achievements
        if new_achievements or progress != user.get("achievement_progress", {}):
            await db.users.update_one(
                {"id": user_id},
                {
                    "$set": {
                        "achievement_progress": progress,
                        "achievements": user_achievements + new_achievements
                    }
                }
            )
            
        if new_achievements:
            logger.info(f"User {user_id} earned achievements: {new_achievements}")
            
            # Auto-share achievements in chat
            for achievement_id in new_achievements:
                achievement = ACHIEVEMENTS[achievement_id]
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
def hash_password(password: str) -> str:
    """Hash a password for storing in database"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    return hash_password(password) == hashed

def process_uploaded_image(file_content: bytes, max_size: int = 1024 * 1024) -> str:
    """Process uploaded image and return base64 data URL"""
    if len(file_content) > max_size:
        raise HTTPException(status_code=400, detail="Image too large (max 1MB)")
    
    # Convert to base64 data URL
    base64_content = base64.b64encode(file_content).decode('utf-8')
    return f"data:image/jpeg;base64,{base64_content}"

async def get_current_stock_price(symbol: str) -> float:
    """Get current stock price from API or mock data"""
    try:
        # Use FMP API key from environment
        api_key = os.environ.get('FMP_API_KEY')
        url = f"https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={api_key}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            data = response.json()
            
            # Check for API errors
            if isinstance(data, list) and len(data) > 0:
                return data[0]['price']
            else:
                return await get_mock_stock_price(symbol)
                
    except Exception as e:
        print(f"Error fetching real price for {symbol}: {e}")
        return await get_mock_stock_price(symbol)

async def get_mock_stock_price(symbol: str) -> float:
    """Enhanced mock prices with realistic variation"""
    import random
    import hashlib
    
    # Base prices for popular stocks (updated with more realistic recent prices)
    mock_prices = {
        "TSLA": 242.65,
        "AAPL": 188.40,
        "MSFT": 425.20,
        "NVDA": 885.50,
        "GOOGL": 145.30,
        "AMZN": 158.75,
        "META": 495.80,
        "NFLX": 430.15,
        "AMD": 205.60,
        "INTC": 48.20,
        "SPY": 458.90,
        "QQQ": 382.45,
        "IWM": 225.30,
        "VTI": 248.80,
        "BTC": 43500.0,
        "ETH": 2650.0,
        # Add GMNI and other symbols
        "GMNI": 0.0008,  # Penny stock price
        "PENNY1": 0.0025,
        "PENNY2": 0.0001,
        "PENNY3": 0.008,
        "GME": 18.75,
        "AMC": 5.25,
        "PLTR": 22.80,
        "SOFI": 7.95,
        "RIOT": 12.40
    }
    
    # Get base price or generate random one based on symbol hash for consistency
    symbol_upper = symbol.upper()
    if symbol_upper in mock_prices:
        base_price = mock_prices[symbol_upper]
    else:
        # Generate consistent price based on symbol hash
        symbol_hash = int(hashlib.md5(symbol_upper.encode()).hexdigest()[:8], 16)
        random.seed(symbol_hash)
        
        # Different price ranges based on symbol characteristics
        if len(symbol) <= 3:
            base_price = random.uniform(100, 800)  # Major stocks
        elif "PENNY" in symbol_upper or len(symbol) > 4:
            base_price = random.uniform(0.0001, 0.01)  # Penny stocks
        else:
            base_price = random.uniform(10, 200)  # Mid-range stocks
    
    # Add small realistic variation (±0.5% to ±2%) but keep it consistent per session
    import time
    # Use daily seed for consistent prices within the same day
    daily_seed = int(time.time() / 86400)  # Change once per day
    random.seed(hash(symbol_upper + str(daily_seed)) % 2**32)
    
    if base_price < 0.01:
        # For penny stocks, use smaller variation
        variation = random.uniform(-0.005, 0.005)  # ±0.5%
    else:
        # For regular stocks, use normal variation
        variation = random.uniform(-0.02, 0.02)  # ±2%
    
    current_price = base_price * (1 + variation)
    
    # Return appropriate precision based on price
    if current_price < 0.01:
        return round(current_price, 8)  # High precision for penny stocks
    elif current_price < 1:
        return round(current_price, 4)
    else:
        return round(current_price, 2)

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
    """Update current P&L for all open positions and check for stop-loss/take-profit triggers"""
    open_positions = await db.positions.find({"user_id": user_id, "is_open": True}).to_list(1000)
    
    for position in open_positions:
        current_price = await get_current_stock_price(position["symbol"])
        unrealized_pnl = (current_price - position["avg_price"]) * position["quantity"]
        
        # Check for auto-close triggers
        should_close = False
        close_reason = None
        
        # Check stop-loss (price dropped below stop-loss level)
        if position.get("stop_loss") and current_price <= position["stop_loss"]:
            should_close = True
            close_reason = "STOP_LOSS"
        
        # Check take-profit (price reached take-profit level)
        elif position.get("take_profit") and current_price >= position["take_profit"]:
            should_close = True
            close_reason = "TAKE_PROFIT"
        
        if should_close:
            # Auto-close the position
            realized_pnl = (current_price - position["avg_price"]) * position["quantity"]
            
            # Create a SELL trade to record the auto-close
            close_trade = PaperTrade(
                user_id=user_id,
                symbol=position["symbol"],
                action="SELL",
                quantity=position["quantity"],
                price=current_price,
                position_id=position["id"],
                is_closed=True,
                notes=f"Auto-closed by {close_reason.replace('_', ' ').lower()} at ${current_price}"
            )
            
            await db.paper_trades.insert_one(close_trade.dict())
            
            # Close the position
            await db.positions.update_one(
                {"id": position["id"]},
                {"$set": {
                    "is_open": False,
                    "closed_at": datetime.utcnow(),
                    "current_price": current_price,
                    "unrealized_pnl": round(realized_pnl, 8),
                    "auto_close_reason": close_reason
                }}
            )
            
            print(f"Auto-closed position {position['symbol']} - {close_reason}: ${realized_pnl:.2f}")
            
        else:
            # Update position with current price and P&L
            await db.positions.update_one(
                {"id": position["id"]},
                {"$set": {
                    "current_price": current_price,
                    "unrealized_pnl": round(unrealized_pnl, 8)
                }}
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

@api_router.post("/users/register", response_model=User)
async def register_user(user_data: UserCreate, background_tasks: BackgroundTasks):
    # Check if username already exists
    existing_user = await db.users.find_one({"username": user_data.username})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Check if email already exists
    existing_email = await db.users.find_one({"email": user_data.email})
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # Create new user with pending status (in production, hash the password!)
    user_dict = user_data.dict()
    
    # Store referral code for processing after user creation
    referral_code = user_dict.pop('referral_code', None)
    
    # Store the password for testing purposes (in a real app, you'd hash it)
    password = user_dict.pop('password')
    hashed_password = hash_password(password)
    user_dict['password_hash'] = hashed_password
    
    # Generate unique referral code for this user
    user_dict['referral_code'] = generate_referral_code(user_data.username)
    
    # For testing: Make the first user an admin and auto-approve
    users_count = await db.users.count_documents({})
    if users_count == 0 or user_data.username == "admin":
        user_dict["is_admin"] = True
        user_dict["status"] = UserStatus.APPROVED
        user_dict["role"] = UserRole.ADMIN
        user_dict["approved_at"] = datetime.utcnow()
        user_dict["approved_by"] = "system"
        user = User(**user_dict)
    else:
        user = User(**user_dict, status=UserStatus.PENDING)
        
        # Send email notification to admin for new registration
        if email_service:
            admin_email = os.getenv("MAIL_USERNAME", "zenmillonario@gmail.com")
            background_tasks.add_task(
                email_service.send_registration_notification,
                admin_email,
                user_dict
            )
            
            # Send confirmation email to user
            background_tasks.add_task(
                send_registration_confirmation_to_user,
                user_data.email,
                user_dict.get('real_name', user_data.username)
            )
        else:
            print(f"Email service unavailable. Would send registration notification to admin for user: {user_data.username}")
            
        # Send push notification to admins
        background_tasks.add_task(
            send_notification_to_admins,
            "🔔 New User Registration",
            f"{user_dict.get('real_name', user_data.username)} has registered and needs approval",
            {"type": "new_registration", "username": user_data.username}
        )
    
    await db.users.insert_one(user.dict())
    
    # Handle referral if provided
    if referral_code:
        background_tasks.add_task(handle_referral_signup, user.id, referral_code)
    
    # Notify admins about new registration via WebSocket
    await manager.send_admin_notification(json.dumps({
        "type": "new_registration",
        "user": user.dict()
    }, default=str))
    
    return user

@api_router.post("/users/login", response_model=User)
async def login_user(login_data: UserLogin):
    # Make username case-insensitive by converting to lowercase
    username_lower = login_data.username.lower()
    user = await db.users.find_one({"username": {"$regex": f"^{re.escape(username_lower)}$", "$options": "i"}})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Check password (in a real app, you'd verify the hash)
    if 'password_hash' in user:
        if not verify_password(login_data.password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user_obj = User(**user)
    
    # Check if user is approved
    if user_obj.status != UserStatus.APPROVED:
        if user_obj.status == UserStatus.PENDING:
            raise HTTPException(status_code=403, detail="Account pending admin approval. You will be notified within 5 minutes once approved.")
        elif user_obj.status == UserStatus.REJECTED:
            raise HTTPException(status_code=403, detail="Account has been rejected")
    
    # Store the old session ID before generating new one
    old_session_id = user.get("active_session_id")
    
    # Generate new session ID
    new_session_id = str(uuid.uuid4())
    
    # If user has an active session, invalidate it AFTER setting the new session
    if old_session_id:
        # Notify the old session to logout (but don't close connection yet)
        await manager.send_session_invalidation(user_obj.id, new_session_id)
    
    # Calculate daily login streak and award XP
    today = datetime.utcnow().strftime('%Y-%m-%d')
    last_login = user.get("last_login_date")
    current_streak = user.get("daily_login_streak", 0)
    
    if last_login != today:
        # Award daily login XP
        await award_xp(user_obj.id, "daily_login", 10)
        
        # Calculate streak
        if last_login:
            yesterday = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
            if last_login == yesterday:
                current_streak += 1
            else:
                current_streak = 1
        else:
            current_streak = 1
        
        # Update login data
        await db.users.update_one(
            {"id": user_obj.id},
            {"$set": {
                "last_login_date": today,
                "daily_login_streak": current_streak
            }}
        )
        
        # Award streak XP if applicable
        await award_xp(user_obj.id, "daily_login", 0, {"streak": current_streak})
    
    # Update user with new session and online status FIRST
    await db.users.update_one(
        {"id": user_obj.id},
        {"$set": {
            "is_online": True, 
            "last_seen": datetime.utcnow(),
            "active_session_id": new_session_id,
            "session_created_at": datetime.utcnow()
        }}
    )
    
    # Add session_id to user object for frontend
    user_obj.active_session_id = new_session_id
    user_obj.session_created_at = datetime.utcnow()
    
    print(f"User {user_obj.username} logged in with new session: {new_session_id}, old session: {old_session_id}")
    
    return user_obj

@api_router.get("/users/{user_id}/session-status")
async def check_session_status(user_id: str, session_id: str):
    """Check if a user's session is still valid"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    is_valid = user.get("active_session_id") == session_id
    return {
        "valid": is_valid,
        "message": "Session is valid" if is_valid else "Session is invalid or expired"
    }

@api_router.post("/users/logout")
async def logout_user(user_id: str):
    """Update user offline status and clear session"""
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "is_online": False, 
            "last_seen": datetime.utcnow(),
            "active_session_id": None,
            "session_created_at": None
        }}
    )
    return {"message": "Logged out successfully"}

@api_router.get("/users", response_model=List[User])
async def get_users():
    """Get all approved users (excludes pending and rejected users)"""
    users = await db.users.find({"status": UserStatus.APPROVED}).to_list(1000)
    return [User(**user) for user in users]

@api_router.get("/users/pending", response_model=List[User])
async def get_pending_users():
    """Get all users pending approval - admin only"""
    users = await db.users.find({"status": UserStatus.PENDING}).to_list(1000)
    return [User(**user) for user in users]

@api_router.post("/users/approve")
async def approve_user(approval: UserApproval, background_tasks: BackgroundTasks):
    """Approve or reject a user - admin only"""
    # Verify admin status (in production, use proper JWT auth)
    admin = await db.users.find_one({"id": approval.admin_id})
    if not admin or not admin.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
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
        update_data["role"] = approval.role
        if approval.role == UserRole.ADMIN:
            update_data["is_admin"] = True
    
    result = await db.users.update_one(
        {"id": approval.user_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get updated user
    user = await db.users.find_one({"id": approval.user_id})
    status_text = "approved" if approval.approved else "rejected"
    
    # Send email notification to user about approval/rejection
    user_name = user_to_approve.get('real_name', user_to_approve.get('username'))
    user_email = user_to_approve.get('email')
    
    if user_email and email_service:
        background_tasks.add_task(
            email_service.send_approval_confirmation,
            user_email,
            user_name,
            approval.approved
        )
    elif user_email:
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
async def change_user_role(role_change: Dict[str, Any], background_tasks: BackgroundTasks):
    """Change user role - admin only (including demoting other admins)"""
    required_fields = ["user_id", "admin_id", "new_role"]
    for field in required_fields:
        if field not in role_change:
            raise HTTPException(status_code=400, detail=f"Missing field: {field}")
    
    user_id = role_change["user_id"]
    admin_id = role_change["admin_id"]
    new_role = role_change["new_role"]
    
    # Verify admin status
    admin = await db.users.find_one({"id": admin_id})
    if not admin or not admin.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
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
    
    # Verify current password
    if 'password_hash' in user:
        if not verify_password(password_data.current_password, user['password_hash']):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
    else:
        # Legacy password check (remove in production)
        if user.get('password') != password_data.current_password:
            raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Hash new password
    new_password_hash = hash_password(password_data.new_password)
    
    # Update password
    result = await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "password_hash": new_password_hash,
            "modified_at": datetime.utcnow()
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Failed to update password")
    
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
async def request_password_reset(reset_request: PasswordResetRequest, background_tasks: BackgroundTasks):
    """Request password reset via email"""
    # Find user by email (case-insensitive)
    user = await db.users.find_one({"email": {"$regex": f"^{re.escape(reset_request.email)}$", "$options": "i"}})
    
    # Always return success for security (don't reveal if email exists)
    if not user:
        return {"message": "If an account with that email exists, you will receive a password reset link."}
    
    # Generate reset token
    reset_token = str(uuid.uuid4())
    reset_expires = datetime.utcnow() + timedelta(hours=1)  # Token expires in 1 hour
    
    # Store reset token
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "reset_token": reset_token,
            "reset_expires": reset_expires
        }}
    )
    
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

@api_router.post("/users/reset-password-confirm")
async def confirm_password_reset(reset_confirm: PasswordResetConfirm, background_tasks: BackgroundTasks):
    """Confirm password reset with token"""
    # Find user by reset token
    user = await db.users.find_one({
        "reset_token": reset_confirm.token,
        "reset_expires": {"$gt": datetime.utcnow()}
    })
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    # Hash new password
    new_password_hash = hash_password(reset_confirm.new_password)
    
    # Update password and clear reset token
    result = await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "password_hash": new_password_hash,
            "modified_at": datetime.utcnow()
        },
        "$unset": {
            "reset_token": "",
            "reset_expires": ""
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Failed to reset password")
    
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
    
    # In production, this would be your actual domain
    reset_link = f"https://13862577-3d92-43cb-9170-6c39adc05ef3.preview.emergentagent.com/reset-password?token={reset_token}"
    
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
    """Get real-time stock price using FMP API with proper formatting"""
    fmp_api_key = os.getenv("FMP_API_KEY")
    if not fmp_api_key:
        raise HTTPException(status_code=500, detail="FMP API key not configured")
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={fmp_api_key}"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 0:
                        stock_data = data[0]
                        raw_price = stock_data.get("price", 0)
                        return {
                            "symbol": symbol,
                            "price": raw_price,
                            "formatted_price": format_price_display(raw_price),
                            "change": stock_data.get("change", 0),
                            "changesPercentage": stock_data.get("changesPercentage", 0),
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    else:
                        raise HTTPException(status_code=404, detail=f"Stock symbol {symbol} not found")
                else:
                    raise HTTPException(status_code=response.status, detail="Failed to fetch stock data")
    except Exception as e:
        logging.error(f"Error fetching stock price for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching stock price")

@api_router.post("/users/{user_id}/role")
async def update_user_role(user_id: str, role_update: UserRoleUpdate):
    """Update user role - admin only"""
    # Verify admin status
    admin = await db.users.find_one({"id": role_update.admin_id})
    if not admin or not admin.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    update_data = {"role": role_update.role}
    if role_update.role == UserRole.ADMIN:
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
    """Remove user from app - admin only"""
    # Verify admin status
    admin = await db.users.find_one({"id": admin_id})
    if not admin or not admin.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Don't allow removing other admins
    user_to_remove = await db.users.find_one({"id": user_id})
    if user_to_remove and user_to_remove.get("is_admin"):
        raise HTTPException(status_code=403, detail="Cannot remove admin users")
    
    result = await db.users.delete_one({"id": user_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User removed successfully"}

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
async def update_user_profile(user_id: str, profile_update: ProfileUpdate):
    """Update user profile customization"""
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
async def get_user_profile(user_id: str):
    """Get user profile for display"""
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
        "location": user.get("location"),
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
    """Admin review and approve/reject cash prize"""
    # Verify admin status
    admin = await db.users.find_one({"id": admin_id})
    if not admin or not admin.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get user with pending cash prize
    user = await db.users.find_one({"id": review.user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Find and update the pending cash prize
    pending_prizes = user.get("pending_cash_review", [])
    updated_pending = []
    prize_found = False
    
    for prize in pending_prizes:
        if prize.get("achievement_id") == review.achievement_id:
            if review.status == "approved":
                # Move to approved cash prizes
                approved_prize = {
                    **prize,
                    "status": "approved",
                    "reviewed_at": datetime.utcnow(),
                    "reviewed_by": admin["id"],
                    "admin_notes": review.admin_notes,
                    "approved_amount": review.amount
                }
                
                # Add to cash prizes and update total
                await db.users.update_one(
                    {"id": review.user_id},
                    {
                        "$push": {"cash_prizes": approved_prize},
                        "$inc": {"total_cash_earned": review.amount}
                    }
                )
                
                # Send notification to chat about cash prize
                await share_cash_prize_in_chat(review.user_id, approved_prize)
                
                # Create cash prize notification for the user
                await create_user_notification(
                    user_id=review.user_id,
                    notification_type="cash_prize",
                    title="Cash Prize Approved! 💰",
                    message=f"Congratulations! Your cash prize of ${review.amount:.2f} has been approved for {review.achievement_id} achievement!",
                    data={
                        "amount": review.amount,
                        "achievement_id": review.achievement_id,
                        "admin_notes": review.admin_notes,
                        "approved_at": datetime.utcnow(),
                        "action": "cash_prize_approved"
                    }
                )
                
            elif review.status == "rejected":
                # Just remove from pending
                pass
            
            prize_found = True
        else:
            updated_pending.append(prize)
    
    if not prize_found:
        raise HTTPException(status_code=404, detail="Pending cash prize not found")
    
    # Update user's pending cash review list
    await db.users.update_one(
        {"id": review.user_id},
        {"$set": {"pending_cash_review": updated_pending}}
    )
    
    return {"message": f"Cash prize {review.status} successfully"}

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
async def get_user_notifications(user_id: str, limit: int = 50, offset: int = 0):
    """Get notifications for a user"""
    notifications = await db.notifications.find(
        {"user_id": user_id}
    ).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    
    return notifications

@api_router.post("/users/{user_id}/notifications/{notification_id}/read")
async def mark_notification_as_read(user_id: str, notification_id: str):
    """Mark a notification as read"""
    result = await db.notifications.update_one(
        {"id": notification_id, "user_id": user_id},
        {"$set": {"read": True}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return {"message": "Notification marked as read"}

@api_router.post("/users/{user_id}/notifications/read-all")
async def mark_all_notifications_as_read(user_id: str):
    """Mark all notifications as read for a user"""
    result = await db.notifications.update_many(
        {"user_id": user_id, "read": False},
        {"$set": {"read": True}}
    )
    
    return {"message": f"Marked {result.modified_count} notifications as read"}

@api_router.delete("/users/{user_id}/notifications/{notification_id}")
async def delete_notification(user_id: str, notification_id: str):
    """Delete a notification"""
    result = await db.notifications.delete_one(
        {"id": notification_id, "user_id": user_id}
    )
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return {"message": "Notification deleted"}

@api_router.get("/users/{user_id}/notifications/unread-count")
async def get_unread_notification_count(user_id: str):
    """Get count of unread notifications for a user"""
    count = await db.notifications.count_documents(
        {"user_id": user_id, "read": False}
    )
    
    return {"message": f"Unread notification count: {count}"}

# Message Reaction Endpoints
@api_router.post("/messages/{message_id}/react")
async def add_message_reaction(message_id: str, reaction_data: dict, background_tasks: BackgroundTasks):
    """Add a reaction to a message"""
    user_id = reaction_data.get("user_id")
    reaction_type = reaction_data.get("reaction_type", "heart")  # Default to heart
    
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID required")
    
    # Get the message and user
    message = await db.messages.find_one({"id": message_id})
    user = await db.users.find_one({"id": user_id})
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user already reacted to this message
    existing_reaction = await db.reactions.find_one({
        "message_id": message_id,
        "user_id": user_id,
        "reaction_type": reaction_type
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
    
    await db.reactions.insert_one(reaction)
    
    # Award XP for giving reaction
    await award_xp(user_id, "heart_reaction", 2)
    
    # Create notification for the message author (if not reacting to own message)
    if message["user_id"] != user_id:
        reactor_name = user.get("screen_name") or user.get("username")
        reaction_emoji = "❤️" if reaction_type == "heart" else "👍"
        
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
    
    return {"message": "Reaction added successfully", "reaction": reaction}

@api_router.delete("/messages/{message_id}/react")
async def remove_message_reaction(message_id: str, user_id: str, reaction_type: str = "heart"):
    """Remove a reaction from a message"""
    result = await db.reactions.delete_one({
        "message_id": message_id,
        "user_id": user_id,
        "reaction_type": reaction_type
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Reaction not found")
    
    return {"message": "Reaction removed successfully"}

@api_router.get("/messages/{message_id}/reactions")
async def get_message_reactions(message_id: str):
    """Get all reactions for a message"""
    reactions = await db.reactions.find({"message_id": message_id}).to_list(1000)
    
    # Group reactions by type and get user info
    reaction_summary = {}
    for reaction in reactions:
        reaction_type = reaction["reaction_type"]
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

@api_router.post("/messages", response_model=Message)
async def create_message(message_data: MessageCreate):
    # Get user info
    user = await db.users.find_one({"id": message_data.user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user is approved
    if user.get("status") != UserStatus.APPROVED:
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
                "content": reply_to_message["content"],
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
        screen_name=user.get("screen_name"),  # NEW: Include screen_name in message
        highlighted_tickers=tickers,
        reply_to_id=message_data.reply_to_id,
        reply_to=reply_to_data
    )
    
    await db.messages.insert_one(message.dict())
    
    # Award XP for sending message
    await award_xp(message_data.user_id, "chat_message", 5)
    
    # Award extra XP for reply
    if message_data.reply_to_id:
        await award_xp(message_data.user_id, "reply_message", 8)
        
        # Create notification for the user being replied to
        if reply_to_data and reply_to_data.get("username"):
            # Find the original message sender
            original_sender = await db.users.find_one({"username": reply_to_data["username"]})
            if original_sender and original_sender["id"] != message_data.user_id:  # Don't notify self-replies
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
    
    # Broadcast message to all connected users
    await manager.broadcast(json.dumps({
        "type": "message",
        "data": message.dict()
    }, default=str))
    
    # Send push notification to all other users ONLY when sender is an admin
    try:
        # Only send notifications if the sender is an admin
        if user.get("is_admin"):
            # Get all users except the sender
            other_users = await db.users.find({
                "id": {"$ne": message_data.user_id},
                "status": UserStatus.APPROVED
            }).to_list(1000)
            
            # Get their FCM tokens
            other_user_ids = [u["id"] for u in other_users]
            tokens_cursor = db.fcm_tokens.find({"user_id": {"$in": other_user_ids}})
            tokens = await tokens_cursor.to_list(1000)
            token_list = [token["token"] for token in tokens]
            
            if token_list:
                # Prepare notification
                sender_name = user.get("screen_name") or user.get("real_name") or user["username"]
                
                # Truncate message content for notification
                if message_data.content_type == "image":
                    message_preview = "📷 Admin sent an image"
                else:
                    message_preview = message_data.content[:100] + "..." if len(message_data.content) > 100 else message_data.content
                
                # Send notification using FCM service
                from fcm_service import fcm_service
                
                await fcm_service.send_to_multiple(
                    tokens=token_list,
                    title=f"👑 Admin {sender_name}",
                    body=message_preview,
                    data={
                        "type": "admin_message",
                        "sender_id": message_data.user_id,
                        "sender_name": sender_name,
                        "message_type": message_data.content_type,
                        "timestamp": str(int(datetime.utcnow().timestamp()))
                    }
                )
                
    except Exception as e:
        # Don't fail message creation if push notification fails
        print(f"Failed to send push notification: {str(e)}")
    
    # Send admin notification to online users (existing logic)
    if user.get("is_admin"):
        print(f"📢 Admin message from {user['username']}: {message_data.content}")
        
        # Send specific admin notification to all non-admin users
        non_admin_users = await db.users.find({"is_admin": {"$ne": True}, "is_online": True}).to_list(1000)
        
        for non_admin_user in non_admin_users:
            if non_admin_user["id"] in manager.user_connections:
                try:
                    await manager.user_connections[non_admin_user["id"]].send_text(json.dumps({
                        "type": "admin_notification",
                        "message": f"Admin {user['real_name'] or user['username']}: {message_data.content}",
                        "admin_username": user['username'],
                        "admin_real_name": user.get('real_name'),
                        "content": message_data.content
                    }, default=str))
                    print(f"🔔 Sent admin notification to user: {non_admin_user['username']}")
                except Exception as e:
                    print(f"Failed to send admin notification to {non_admin_user['username']}: {e}")
                    pass
    
    return message

@api_router.get("/messages", response_model=List[Message])
async def get_messages(limit: int = 50):
    messages = await db.messages.find().sort("timestamp", -1).limit(limit).to_list(limit)
    # Reverse to show oldest first
    messages.reverse()
    return [Message(**message) for message in messages]

@api_router.post("/trades", response_model=PaperTrade)
async def create_paper_trade(trade_data: PaperTradeCreate, user_id: str):
    """Create a new paper trade"""
    # Verify user exists and is approved
    user = await db.users.find_one({"id": user_id})
    if not user or user.get("status") != UserStatus.APPROVED:
        raise HTTPException(status_code=403, detail="User not found or not approved")
    
    trade = PaperTrade(
        user_id=user_id,
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
        # For sell trades, check if the overall position became profitable
        # This is a simplified check - you might want more sophisticated logic
        if performance.get("total_profit", 0) > 0:
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
    
    # Get current price if not provided
    current_price = action_data.price or await get_current_stock_price(position["symbol"])
    
    if action_data.action == "BUY_MORE":
        if not action_data.quantity:
            raise HTTPException(status_code=400, detail="Quantity required for buy more action")
        
        # Create BUY trade
        trade = PaperTrade(
            user_id=user_id,
            symbol=position["symbol"],
            action="BUY",
            quantity=action_data.quantity,
            price=current_price,
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
        
        return {"message": f"Added {action_data.quantity} shares at ${current_price}"}
    
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
        return {"message": f"Sold {sell_quantity} shares at ${current_price}", "profit_loss": round(profit_loss, 2)}
    
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
async def update_user_profile(user_id: str, profile_data: ProfileUpdate):
    """Update user profile information"""
    # Check if user exists
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prepare update data
    update_data = {}
    if profile_data.real_name is not None:
        update_data["real_name"] = profile_data.real_name
    if profile_data.screen_name is not None:
        update_data["screen_name"] = profile_data.screen_name
    if profile_data.username is not None:
        # Check if username already exists
        if profile_data.username != user["username"]:
            existing = await db.users.find_one({"username": profile_data.username})
            if existing:
                raise HTTPException(status_code=400, detail="Username already exists")
        update_data["username"] = profile_data.username
    if profile_data.email is not None:
        # Check if email already exists
        if profile_data.email != user["email"]:
            existing = await db.users.find_one({"email": profile_data.email})
            if existing:
                raise HTTPException(status_code=400, detail="Email already exists")
        update_data["email"] = profile_data.email
    
    # Update user
    if update_data:
        await db.users.update_one(
            {"id": user_id},
            {"$set": update_data}
        )
    
    # Get updated user
    updated_user = await db.users.find_one({"id": user_id})
    return User(**updated_user)

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
