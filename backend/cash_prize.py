"""Cash prize management functions"""
from datetime import datetime

async def create_pending_cash_prize(user_id: str, achievement_id: str, amount: float):
    """Create a pending cash prize for a user"""
    try:
        from server import db  # Import db from server to avoid circular imports
        
        cash_prize = {
            "user_id": user_id,
            "achievement_id": achievement_id,
            "amount": amount,
            "status": "pending",
            "created_at": datetime.utcnow(),
            "reviewed_at": None,
            "reviewed_by": None,
            "admin_notes": None
        }
        
        # Add to user's pending cash review
        await db.users.update_one(
            {"id": user_id},
            {"$push": {"pending_cash_review": cash_prize}}
        )
        
        print(f"Created pending cash prize for user {user_id}: ${amount} for achievement {achievement_id}")
        return cash_prize
    except Exception as e:
        print(f"Error creating pending cash prize: {e}")
        return None