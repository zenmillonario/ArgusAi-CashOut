from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
import uuid
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


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

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

class UserCreate(BaseModel):
    username: str
    email: str
    real_name: str  # NEW: Required real name
    membership_plan: str  # NEW: Required membership plan
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class UserApproval(BaseModel):
    user_id: str
    approved: bool
    admin_id: str
    role: Optional[UserRole] = UserRole.MEMBER  # NEW: Role assignment during approval

class UserRoleUpdate(BaseModel):
    user_id: str
    role: UserRole
    admin_id: str

class ProfileUpdate(BaseModel):
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

class MessageCreate(BaseModel):
    content: str
    content_type: str = "text"  # NEW: Support for different content types
    user_id: str

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

# Utility function to extract stock tickers from message
def extract_stock_tickers(content: str) -> List[str]:
    """Extract stock tickers that start with $ from message content"""
    pattern = r'\$([A-Z]{1,5})'
    matches = re.findall(pattern, content.upper())
    return matches

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
    
    # Base prices for popular stocks
    mock_prices = {
        "TSLA": 250.75,
        "AAPL": 185.20,
        "MSFT": 420.50,
        "NVDA": 875.30,
        "GOOGL": 142.80,
        "AMZN": 155.90,
        "META": 485.60,
        "NFLX": 425.20,
        "AMD": 198.40,
        "INTC": 45.60,
        "SPY": 452.30,
        "QQQ": 375.80,
        "IWM": 218.90,
        "VTI": 245.60,
        "BTC": 42000.0,
        "ETH": 2500.0
    }
    
    # Get base price or generate random one
    base_price = mock_prices.get(symbol.upper(), random.uniform(50, 500))
    
    # Add realistic daily variation (-3% to +3%)
    variation = random.uniform(-0.03, 0.03)
    current_price = base_price * (1 + variation)
    
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
                "avg_price": round(new_avg_price, 2)
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
                    "unrealized_pnl": round(realized_pnl, 2),
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
                    "unrealized_pnl": round(unrealized_pnl, 2)
                }}
            )

# Utility function to calculate user trading performance
async def calculate_user_performance(user_id: str) -> dict:
    """Calculate trading performance metrics for a user"""
    trades = await db.paper_trades.find({"user_id": user_id}).to_list(1000)
    
    if not trades:
        return {
            "total_profit": 0.0,
            "win_percentage": 0.0,
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
            positions[symbol]["shares"] -= sell_quantity
            if positions[symbol]["shares"] > 0:
                positions[symbol]["total_cost"] = (positions[symbol]["total_cost"] / positions[symbol]["shares"]) * positions[symbol]["shares"]
            else:
                positions[symbol]["total_cost"] = 0
    
    if not completed_trades:
        return {
            "total_profit": 0.0,
            "win_percentage": 0.0,
            "trades_count": len(trades),
            "average_gain": 0.0
        }
    
    total_profit = sum(trade["profit_loss"] for trade in completed_trades)
    winning_trades = sum(1 for trade in completed_trades if trade["is_profitable"])
    win_percentage = (winning_trades / len(completed_trades)) * 100 if completed_trades else 0
    average_gain = total_profit / len(completed_trades) if completed_trades else 0
    
    return {
        "total_profit": round(total_profit, 2),
        "win_percentage": round(win_percentage, 2),
        "trades_count": len(trades),
        "average_gain": round(average_gain, 2)
    }

# API Routes

@api_router.get("/")
async def root():
    return {"message": "CashoutAI API is running", "status": "success"}

@api_router.post("/users/register", response_model=User)
async def register_user(user_data: UserCreate):
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
    del user_dict['password']  # Don't store password in this simple version
    user = User(**user_dict, status=UserStatus.PENDING)
    await db.users.insert_one(user.dict())
    
    # Notify admins about new registration
    await manager.send_admin_notification(json.dumps({
        "type": "new_registration",
        "user": user.dict()
    }, default=str))
    
    return user

@api_router.post("/users/login", response_model=User)
async def login_user(login_data: UserLogin):
    user = await db.users.find_one({"username": login_data.username})
    if not user:
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
async def approve_user(approval: UserApproval):
    """Approve or reject a user - admin only"""
    # Verify admin status (in production, use proper JWT auth)
    admin = await db.users.find_one({"id": approval.admin_id})
    if not admin or not admin.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
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
    
    # Notify all admins
    await manager.send_admin_notification(json.dumps({
        "type": "user_approval",
        "message": f"User {user['username']} has been {status_text}",
        "user": user
    }, default=str))
    
    return {"message": f"User {status_text} successfully"}

@api_router.get("/stock/{symbol}")
async def get_stock_price(symbol: str):
    """Get real-time stock price using FMP API"""
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
                        return {
                            "symbol": symbol,
                            "price": stock_data.get("price", 0),
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
    
    message = Message(
        user_id=message_data.user_id,
        username=user["username"],
        content=message_data.content,
        content_type=message_data.content_type,
        is_admin=user.get("is_admin", False),
        avatar_url=user.get("avatar_url"),
        real_name=user.get("real_name"),
        screen_name=user.get("screen_name"),  # NEW: Include screen_name in message
        highlighted_tickers=tickers
    )
    
    await db.messages.insert_one(message.dict())
    
    # Broadcast message to all connected users
    await manager.broadcast(json.dumps({
        "type": "message",
        "data": message.dict()
    }, default=str))
    
    # Send push notification only if message is from admin
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
    
    return trade

@api_router.get("/positions/{user_id}")
async def get_user_positions(user_id: str):
    """Get all open positions for a user with current P&L"""
    # Update P&L first
    await update_positions_pnl(user_id)
    
    # Get updated positions
    positions = await db.positions.find({"user_id": user_id, "is_open": True}).to_list(1000)
    return [Position(**position) for position in positions]

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
                "avg_price": round(new_avg_price, 2)
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
                    "unrealized_pnl": round(realized_pnl, 2),
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
            "unrealized_pnl": round(realized_pnl, 2),
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
