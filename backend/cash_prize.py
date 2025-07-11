"""Cash prize management functions"""
from datetime import datetime
import logging

# Configure logging
logger = logging.getLogger(__name__)

async def create_pending_cash_prize(user_id: str, achievement_id: str, amount: float):
    """Create a pending cash prize for admin review"""
    try:
        from server import db  # Import db from server to avoid circular imports
        
        pending_prize = {
            "achievement_id": achievement_id,
            "amount": amount,
            "status": "pending",
            "created_at": datetime.utcnow(),
            "reviewed_at": None,
            "reviewed_by": None,
            "admin_notes": None
        }
        
        await db.users.update_one(
            {"id": user_id},
            {"$push": {"pending_cash_review": pending_prize}}
        )
        
        logger.info(f"Created pending cash prize for user {user_id}: ${amount} for {achievement_id}")
        
    except Exception as e:
        logger.error(f"Error creating pending cash prize: {e}")

async def handle_message_mentions(message_content: str, sender_user: dict, message_id: str):
    """Handle @username mentions in messages"""
    try:
        from server import db, create_user_notification  # Import needed functions
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

