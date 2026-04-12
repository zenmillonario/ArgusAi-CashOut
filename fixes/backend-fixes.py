# Backend Fixes for CashOutAi
# Add these updates to your server.py file

# 1. Updated User Model with Real Name and Screen Name
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str  # Screen name for chat
    real_name: str  # Full real name
    email: str
    is_admin: bool = False
    is_moderator: bool = False  # New moderator role
    status: UserStatus = UserStatus.PENDING
    avatar_url: Optional[str] = None
    avatar_file: Optional[str] = None  # Store base64 image data
    total_profit: float = 0.0
    win_percentage: float = 0.0
    trades_count: int = 0
    average_gain: float = 0.0
    is_online: bool = False  # Track online status
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None

# 2. Updated Registration Model
class UserCreate(BaseModel):
    username: str  # Screen name
    real_name: str  # Full name
    email: str
    password: str

# 3. Updated User Approval Model
class UserApproval(BaseModel):
    user_id: str
    approved: bool
    admin_id: str
    role: str = "member"  # "member", "moderator", "admin"

# 4. New Message Model (no bot messages)
class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    username: str  # Screen name
    real_name: str  # Full name for admin display
    content: str
    is_admin: bool = False
    is_moderator: bool = False
    avatar_url: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    highlighted_tickers: List[str] = []
    image_url: Optional[str] = None  # For posted images
    message_type: str = "text"  # "text", "image", "gif"

# 5. Enhanced Position Model
class Position(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    symbol: str
    quantity: int
    avg_price: float
    entry_price: float
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_percentage: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    is_open: bool = True
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    notes: Optional[str] = None
    auto_close_reason: Optional[str] = None

# 6. New API Endpoints

@api_router.post("/users/upload-avatar")
async def upload_user_avatar(user_id: str, file: UploadFile = File(...)):
    """Upload profile picture file - ONLY file upload, no URL"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Validate file type and size
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    file_content = await file.read()
    if len(file_content) > 2 * 1024 * 1024:  # 2MB limit
        raise HTTPException(status_code=400, detail="Image too large (max 2MB)")
    
    # Convert to base64 data URL
    base64_content = base64.b64encode(file_content).decode('utf-8')
    file_type = file.content_type.split('/')[-1]
    avatar_data = f"data:image/{file_type};base64,{base64_content}"
    
    # Update user avatar
    result = await db.users.update_one(
        {"id": user_id},
        {"$set": {"avatar_file": avatar_data, "avatar_url": avatar_data}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Failed to update avatar")
    
    return {"message": "Avatar updated successfully", "avatar_url": avatar_data}

@api_router.post("/users/upload-message-image")
async def upload_message_image(user_id: str, file: UploadFile = File(...)):
    """Upload image for chat message"""
    # Similar validation as avatar upload
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    file_content = await file.read()
    if len(file_content) > 5 * 1024 * 1024:  # 5MB limit for chat images
        raise HTTPException(status_code=400, detail="Image too large (max 5MB)")
    
    base64_content = base64.b64encode(file_content).decode('utf-8')
    file_type = file.content_type.split('/')[-1]
    image_data = f"data:image/{file_type};base64,{base64_content}"
    
    return {"image_url": image_data}

@api_router.get("/users/all")
async def get_all_users_admin(admin_id: str):
    """Get all users with online status - Admin only"""
    admin = await db.users.find_one({"id": admin_id})
    if not admin or not (admin.get("is_admin") or admin.get("is_moderator")):
        raise HTTPException(status_code=403, detail="Admin/Moderator access required")
    
    users = await db.users.find().to_list(1000)
    return [User(**user) for user in users]

@api_router.post("/users/{user_id}/set-role")
async def set_user_role(user_id: str, role_data: dict, admin_id: str):
    """Set user role (member/moderator/admin) - Admin only"""
    admin = await db.users.find_one({"id": admin_id})
    if not admin or not admin.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    role = role_data.get("role", "member")
    update_data = {
        "is_admin": role == "admin",
        "is_moderator": role == "moderator"
    }
    
    result = await db.users.update_one(
        {"id": user_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": f"User role updated to {role}"}

@api_router.delete("/users/{user_id}")
async def remove_user(user_id: str, admin_id: str):
    """Remove user from app - Admin only"""
    admin = await db.users.find_one({"id": admin_id})
    if not admin or not admin.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.users.delete_one({"id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User removed successfully"}

@api_router.post("/positions/{position_id}/add-shares")
async def add_shares_to_position(position_id: str, trade_data: dict, user_id: str):
    """Add more shares to existing position"""
    position = await db.positions.find_one({"id": position_id, "user_id": user_id})
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    
    additional_quantity = trade_data.get("quantity", 0)
    additional_price = trade_data.get("price", 0)
    
    # Calculate new average price
    current_value = position["quantity"] * position["avg_price"]
    additional_value = additional_quantity * additional_price
    new_quantity = position["quantity"] + additional_quantity
    new_avg_price = (current_value + additional_value) / new_quantity
    
    # Update position
    await db.positions.update_one(
        {"id": position_id},
        {"$set": {
            "quantity": new_quantity,
            "avg_price": round(new_avg_price, 2)
        }}
    )
    
    # Create trade record
    trade = PaperTrade(
        user_id=user_id,
        symbol=position["symbol"],
        action="BUY",
        quantity=additional_quantity,
        price=additional_price,
        position_id=position_id,
        notes=f"Added to existing position"
    )
    await db.paper_trades.insert_one(trade.dict())
    
    return {"message": "Shares added successfully", "new_avg_price": new_avg_price}

@api_router.post("/positions/{position_id}/sell-shares")
async def sell_shares_from_position(position_id: str, trade_data: dict, user_id: str):
    """Sell shares from existing position"""
    position = await db.positions.find_one({"id": position_id, "user_id": user_id})
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    
    sell_quantity = trade_data.get("quantity", 0)
    sell_price = trade_data.get("price", 0)
    
    if sell_quantity > position["quantity"]:
        raise HTTPException(status_code=400, detail="Cannot sell more shares than owned")
    
    # Calculate realized P&L
    realized_pnl = (sell_price - position["avg_price"]) * sell_quantity
    
    # Update position
    new_quantity = position["quantity"] - sell_quantity
    if new_quantity == 0:
        # Close position completely
        await db.positions.update_one(
            {"id": position_id},
            {"$set": {
                "quantity": 0,
                "is_open": False,
                "closed_at": datetime.utcnow(),
                "auto_close_reason": "MANUAL_SELL"
            }}
        )
    else:
        # Partial sell
        await db.positions.update_one(
            {"id": position_id},
            {"$set": {"quantity": new_quantity}}
        )
    
    # Create trade record
    trade = PaperTrade(
        user_id=user_id,
        symbol=position["symbol"],
        action="SELL",
        quantity=sell_quantity,
        price=sell_price,
        position_id=position_id,
        notes=f"Sold from position - P&L: ${realized_pnl:.2f}",
        is_closed=new_quantity == 0
    )
    await db.paper_trades.insert_one(trade.dict())
    
    return {"message": "Shares sold successfully", "realized_pnl": realized_pnl}

# 7. Update position P&L calculation
async def update_positions_pnl_enhanced(user_id: str):
    """Enhanced P&L calculation with percentages"""
    open_positions = await db.positions.find({"user_id": user_id, "is_open": True}).to_list(1000)
    
    for position in open_positions:
        current_price = await get_current_stock_price(position["symbol"])
        unrealized_pnl = (current_price - position["avg_price"]) * position["quantity"]
        unrealized_pnl_percentage = ((current_price - position["avg_price"]) / position["avg_price"]) * 100
        
        # Check for auto-close triggers (existing logic)
        should_close = False
        close_reason = None
        
        if position.get("stop_loss") and current_price <= position["stop_loss"]:
            should_close = True
            close_reason = "STOP_LOSS"
        elif position.get("take_profit") and current_price >= position["take_profit"]:
            should_close = True
            close_reason = "TAKE_PROFIT"
        
        if should_close:
            # Auto-close logic (existing)
            pass
        else:
            # Update position with enhanced P&L
            await db.positions.update_one(
                {"id": position["id"]},
                {"$set": {
                    "current_price": current_price,
                    "unrealized_pnl": round(unrealized_pnl, 2),
                    "unrealized_pnl_percentage": round(unrealized_pnl_percentage, 2)
                }}
            )