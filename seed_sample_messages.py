#!/usr/bin/env python3
"""
Seed sample messages for ArgusAI CashOut chat
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from datetime import datetime, timedelta
import uuid

# Load environment variables
load_dotenv('/app/backend/.env')

async def seed_sample_messages():
    """Add sample messages to make chat look active"""
    
    mongo_url = os.environ['MONGO_URL']
    db_name = os.environ['DB_NAME']
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print("🌱 Seeding sample messages for better UX...")
    
    try:
        # Check if messages already exist
        existing_count = await db.messages.count_documents({})
        
        if existing_count > 0:
            print(f"✅ Database already has {existing_count} messages - skipping seed")
            return
            
        # Sample messages to make chat look active
        sample_messages = [
            {
                "id": str(uuid.uuid4()),
                "user_id": "system",
                "username": "🤖 CashOutAi Bot",
                "content": "🚀 Welcome to ArgusAI CashOut! Real-time trading discussions start here.",
                "timestamp": datetime.utcnow() - timedelta(hours=2),
                "highlighted_tickers": [],
                "content_type": "text",
                "avatar_url": None,
                "is_admin": True,
                "screen_name": "CashOutAi Bot",
                "reply_to": None
            },
            {
                "id": str(uuid.uuid4()),
                "user_id": "system", 
                "username": "🤖 CashOutAi Bot",
                "content": "💡 Share your trades, discuss market trends, and learn from the community!",
                "timestamp": datetime.utcnow() - timedelta(hours=1, minutes=45),
                "highlighted_tickers": [],
                "content_type": "text", 
                "avatar_url": None,
                "is_admin": True,
                "screen_name": "CashOutAi Bot",
                "reply_to": None
            },
            {
                "id": str(uuid.uuid4()),
                "user_id": "system",
                "username": "🤖 CashOutAi Bot", 
                "content": "📊 Market is looking interesting today. What positions are you watching?",
                "timestamp": datetime.utcnow() - timedelta(hours=1, minutes=30),
                "highlighted_tickers": [],
                "content_type": "text",
                "avatar_url": None,
                "is_admin": True,
                "screen_name": "CashOutAi Bot",
                "reply_to": None
            },
            {
                "id": str(uuid.uuid4()),
                "user_id": "sample_user_1",
                "username": "TraderMike",
                "content": "Good morning everyone! Ready for another trading day 📈",
                "timestamp": datetime.utcnow() - timedelta(minutes=45),
                "highlighted_tickers": [],
                "content_type": "text",
                "avatar_url": None,
                "is_admin": False,
                "screen_name": "TraderMike",
                "reply_to": None
            },
            {
                "id": str(uuid.uuid4()),
                "user_id": "sample_user_2",
                "username": "InvestorSarah",
                "content": "Watching $SPY closely today, volume looking strong 💪",
                "timestamp": datetime.utcnow() - timedelta(minutes=30),
                "highlighted_tickers": ["SPY"],
                "content_type": "text",
                "avatar_url": None,
                "is_admin": False,
                "screen_name": "InvestorSarah",
                "reply_to": None
            },
            {
                "id": str(uuid.uuid4()),
                "user_id": "system",
                "username": "🤖 CashOutAi Bot",
                "content": "🔔 Market Alert: High volatility detected in tech stocks 📊",
                "timestamp": datetime.utcnow() - timedelta(minutes=15),
                "highlighted_tickers": [],
                "content_type": "text",
                "avatar_url": None,
                "is_admin": True,
                "screen_name": "CashOutAi Bot", 
                "reply_to": None
            }
        ]
        
        # Insert sample messages
        result = await db.messages.insert_many(sample_messages)
        print(f"✅ Seeded {len(result.inserted_ids)} sample messages")
        
        # Create sample users for chat context
        sample_users = [
            {
                "id": "sample_user_1",
                "username": "TraderMike", 
                "email": "sample1@example.com",
                "real_name": "Mike Johnson",
                "status": "approved",
                "role": "member",
                "created_at": datetime.utcnow() - timedelta(days=30),
                "is_online": False,
                "last_seen": datetime.utcnow() - timedelta(minutes=45),
                "experience_points": 150,
                "level": 1,
                "membership_plan": "Monthly"
            },
            {
                "id": "sample_user_2", 
                "username": "InvestorSarah",
                "email": "sample2@example.com",
                "real_name": "Sarah Williams",
                "status": "approved",
                "role": "member", 
                "created_at": datetime.utcnow() - timedelta(days=60),
                "is_online": False,
                "last_seen": datetime.utcnow() - timedelta(minutes=30),
                "experience_points": 320,
                "level": 2,
                "membership_plan": "Yearly"
            }
        ]
        
        # Insert sample users (if they don't exist)
        for user in sample_users:
            existing_user = await db.users.find_one({"id": user["id"]})
            if not existing_user:
                await db.users.insert_one(user)
                print(f"✅ Created sample user: {user['username']}")
        
        print(f"\n🎉 Chat seeded successfully!")
        print(f"📊 Users will now see active conversation instead of empty chat")
        print(f"💡 This creates better first impression for new users")
        
    except Exception as e:
        print(f"❌ Error seeding messages: {e}")
        
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(seed_sample_messages())