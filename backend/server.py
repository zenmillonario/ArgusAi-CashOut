from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import uuid
from datetime import datetime
import json
import re
from enum import Enum
import base64
import hashlib


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

manager = ConnectionManager()

# Define Enums
class UserStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

# Define Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: str
    is_admin: bool = False
    status: UserStatus = UserStatus.PENDING
    avatar_url: Optional[str] = None
    total_profit: float = 0.0
    win_percentage: float = 0.0
    trades_count: int = 0
    average_gain: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None

class UserCreate(BaseModel):
    username: str
    email: str
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

class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    username: str
    content: str
    is_admin: bool = False
    avatar_url: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    highlighted_tickers: List[str] = []

class MessageCreate(BaseModel):
    content: str
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

# Utility function to get stock price (mock for now - can integrate with Alpha Vantage later)
async def get_current_stock_price(symbol: str) -> float:
    """Get current stock price (mock implementation for now)"""
    # Mock prices for demonstration - in production, integrate with Alpha Vantage or similar
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
        "INTC": 45.60
    }
    # Add some random variation to simulate price movement
    import random
    base_price = mock_prices.get(symbol.upper(), 100.0)
    variation = random.uniform(-0.05, 0.05)  # ±5% variation
    return round(base_price * (1 + variation), 2)

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
        "message": f"New user {user.username} has registered and is awaiting approval",
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
            raise HTTPException(status_code=403, detail="Account pending admin approval")
        elif user_obj.status == UserStatus.REJECTED:
            raise HTTPException(status_code=403, detail="Account has been rejected")
    
    return user_obj

@api_router.get("/users", response_model=List[User])
async def get_users():
    users = await db.users.find().to_list(1000)
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

@api_router.post("/messages", response_model=Message)
async def create_message(message_data: MessageCreate):
    # Get user info
    user = await db.users.find_one({"id": message_data.user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user is approved
    if user.get("status") != UserStatus.APPROVED:
        raise HTTPException(status_code=403, detail="Only approved users can send messages")
    
    # Extract stock tickers
    tickers = extract_stock_tickers(message_data.content)
    
    message = Message(
        user_id=message_data.user_id,
        username=user["username"],
        content=message_data.content,
        is_admin=user.get("is_admin", False),
        avatar_url=user.get("avatar_url"),
        highlighted_tickers=tickers
    )
    
    await db.messages.insert_one(message.dict())
    
    # Broadcast message to all connected users
    await manager.broadcast(json.dumps({
        "type": "message",
        "data": message.dict()
    }, default=str))
    
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

@api_router.post("/positions/{position_id}/close")
async def close_position(position_id: str, user_id: str, close_price: Optional[float] = None):
    """Close an open position"""
    position = await db.positions.find_one({"id": position_id, "user_id": user_id, "is_open": True})
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    
    # Use current market price if not provided
    if close_price is None:
        close_price = await get_current_stock_price(position["symbol"])
    
    # Create a SELL trade to close the position
    close_trade = PaperTrade(
        user_id=user_id,
        symbol=position["symbol"],
        action="SELL",
        quantity=position["quantity"],
        price=close_price,
        position_id=position_id,
        is_closed=True,
        notes=f"Position closed at market price"
    )
    
    await db.paper_trades.insert_one(close_trade.dict())
    
    # Close the position
    realized_pnl = (close_price - position["avg_price"]) * position["quantity"]
    await db.positions.update_one(
        {"id": position_id},
        {"$set": {
            "is_open": False,
            "closed_at": datetime.utcnow(),
            "current_price": close_price,
            "unrealized_pnl": round(realized_pnl, 2)
        }}
    )
    
    # Update user performance metrics
    performance = await calculate_user_performance(user_id)
    await db.users.update_one(
        {"id": user_id},
        {"$set": performance}
    )
    
    return {"message": "Position closed successfully", "realized_pnl": round(realized_pnl, 2)}

@api_router.get("/stock-price/{symbol}")
async def get_stock_price(symbol: str):
    """Get current stock price for a symbol"""
    price = await get_current_stock_price(symbol)
    return {"symbol": symbol.upper(), "price": price}

@api_router.get("/trades/{user_id}", response_model=List[PaperTrade])
async def get_user_trades(user_id: str):
    """Get all trades for a user"""
    trades = await db.paper_trades.find({"user_id": user_id}).sort("timestamp", -1).to_list(1000)
    return [PaperTrade(**trade) for trade in trades]

@api_router.post("/users/{user_id}/avatar-upload")
async def upload_avatar_file(user_id: str, file: UploadFile = File(...)):
    """Upload profile picture file"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Validate file type
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Read and process file
    file_content = await file.read()
    avatar_url = process_uploaded_image(file_content)
    
    # Update user avatar
    result = await db.users.update_one(
        {"id": user_id},
        {"$set": {"avatar_url": avatar_url}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Failed to update avatar")
    
    return {"message": "Avatar updated successfully", "avatar_url": avatar_url}

@api_router.post("/users/{user_id}/change-password")
async def change_password(user_id: str, password_data: PasswordChange):
    """Change user password"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # In this simple implementation, we'll just check if current password matches username
    # In production, you'd verify against stored password hash
    if password_data.current_password != user.get("username"):  # Simple validation
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Hash and store new password (in production)
    hashed_password = hash_password(password_data.new_password)
    
    result = await db.users.update_one(
        {"id": user_id},
        {"$set": {"password_hash": hashed_password}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Failed to update password")
    
    return {"message": "Password updated successfully"}

@api_router.post("/users/{user_id}/avatar")
async def upload_avatar(user_id: str, avatar_url: str):
    """Update user avatar URL (legacy endpoint)"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    result = await db.users.update_one(
        {"id": user_id},
        {"$set": {"avatar_url": avatar_url}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Failed to update avatar")
    
    return {"message": "Avatar updated successfully"}

@api_router.put("/users/{user_id}/profile")
async def update_profile(user_id: str, profile_data: dict):
    """Update user profile information"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Only allow updating certain fields
    allowed_fields = ["username", "email", "avatar_url"]
    update_data = {k: v for k, v in profile_data.items() if k in allowed_fields}
    
    if update_data:
        result = await db.users.update_one(
            {"id": user_id},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="Failed to update profile")
    
    # Return updated user
    updated_user = await db.users.find_one({"id": user_id})
    return User(**updated_user)

@api_router.get("/users/{user_id}/performance")
async def get_user_performance(user_id: str):
    """Get performance metrics for a user"""
    return await calculate_user_performance(user_id)

# Create default admin user on startup
@app.on_event("startup")
async def create_default_admin():
    # Check if any admin exists
    admin_exists = await db.users.find_one({"is_admin": True})
    if not admin_exists:
        # Create default admin
        admin_user = User(
            username="admin",
            email="admin@cashoutai.com",
            is_admin=True,
            status=UserStatus.APPROVED
        )
        await db.users.insert_one(admin_user.dict())
        print("Created default admin user: admin")

# WebSocket endpoint
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(websocket, user_id)
    logger.info(f"WebSocket connected for user: {user_id}")
    
    try:
        # Send initial connection confirmation
        await manager.send_personal_message(
            json.dumps({"type": "connection", "message": f"Connected as user {user_id}"}),
            websocket
        )
        
        while True:
            # Keep connection alive by receiving ping/pong or heartbeat messages
            data = await websocket.receive_text()
            logger.info(f"WebSocket received from {user_id}: {data}")
            
            # Echo back to confirm connection is alive
            await manager.send_personal_message(
                json.dumps({"type": "heartbeat", "message": "Connection alive"}),
                websocket
            )
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user: {user_id}")
        manager.disconnect(websocket, user_id)

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
