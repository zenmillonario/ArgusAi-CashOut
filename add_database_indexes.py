#!/usr/bin/env python3
"""
Database Index Optimization Script for ArgusAI CashOut
Adds indexes to improve login and query performance
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/app/backend/.env')

async def add_performance_indexes():
    """Add database indexes for better login performance"""
    
    mongo_url = os.environ['MONGO_URL']
    db_name = os.environ['DB_NAME']
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print("🔧 Adding performance indexes...")
    
    try:
        # Index for case-insensitive username lookup (most critical for login)
        await db.users.create_index("username", background=True)
        print("✅ Added index on users.username")
        
        # Index for user ID lookups (frequently used)
        await db.users.create_index("id", unique=True, background=True)
        print("✅ Added unique index on users.id")
        
        # Index for session lookups
        await db.users.create_index("active_session_id", sparse=True, background=True)
        print("✅ Added index on users.active_session_id")
        
        # Index for online status queries
        await db.users.create_index("is_online", background=True)
        print("✅ Added index on users.is_online")
        
        # Index for user status (pending/approved/rejected)
        await db.users.create_index("status", background=True)
        print("✅ Added index on users.status")
        
        # Compound index for admin role queries
        await db.users.create_index([("is_admin", 1), ("status", 1)], background=True)
        print("✅ Added compound index on users.is_admin + status")
        
        # FCM token indexes
        await db.fcm_tokens.create_index("user_id", unique=True, background=True)
        print("✅ Added unique index on fcm_tokens.user_id")
        
        # Message indexes for chat performance
        await db.messages.create_index("timestamp", background=True)
        print("✅ Added index on messages.timestamp")
        
        await db.messages.create_index("user_id", background=True)
        print("✅ Added index on messages.user_id")
        
        # Notification indexes
        await db.notifications.create_index([("user_id", 1), ("read", 1)], background=True)
        print("✅ Added compound index on notifications.user_id + read")
        
        await db.notifications.create_index("created_at", background=True)
        print("✅ Added index on notifications.created_at")
        
        # Position and trade indexes
        await db.positions.create_index([("user_id", 1), ("is_open", 1)], background=True)
        print("✅ Added compound index on positions.user_id + is_open")
        
        await db.trades.create_index([("user_id", 1), ("timestamp", -1)], background=True)
        print("✅ Added compound index on trades.user_id + timestamp (desc)")
        
        print("\n🚀 All performance indexes added successfully!")
        print("💡 Login performance should be significantly improved!")
        
    except Exception as e:
        print(f"❌ Error adding indexes: {e}")
        
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(add_performance_indexes())