#!/usr/bin/env python3
"""
Database Cleanup Script for ArgusAI CashOut
Cleans up stale sessions and inactive users
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables
load_dotenv('/app/backend/.env')

async def cleanup_database():
    """Clean up database from stale data"""
    
    mongo_url = os.environ['MONGO_URL']
    db_name = os.environ['DB_NAME']
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print("🧹 DATABASE CLEANUP STARTING...")
    print("=" * 40)
    
    try:
        # 1. Clean up stale sessions (>30 minutes old)
        thirty_minutes_ago = datetime.utcnow() - timedelta(minutes=30)
        
        stale_sessions = await db.users.find({
            "is_online": True,
            "last_seen": {"$lt": thirty_minutes_ago}
        }).to_list(1000)
        
        if stale_sessions:
            stale_ids = [user['id'] for user in stale_sessions]
            result = await db.users.update_many(
                {"id": {"$in": stale_ids}},
                {"$set": {"is_online": False}}
            )
            print(f"✅ Marked {result.modified_count} stale sessions as offline")
        else:
            print("✅ No stale sessions found")
        
        # 2. Clean up users marked online without valid sessions
        online_without_session = await db.users.find({
            "is_online": True,
            "$or": [
                {"active_session_id": {"$exists": False}},
                {"active_session_id": None}
            ]
        }).to_list(1000)
        
        if online_without_session:
            sessionless_ids = [user['id'] for user in online_without_session]
            result = await db.users.update_many(
                {"id": {"$in": sessionless_ids}},
                {"$set": {"is_online": False}}
            )
            print(f"✅ Marked {result.modified_count} sessionless users as offline")
        else:
            print("✅ No sessionless users found")
        
        # 3. Summary
        final_count = await db.users.count_documents({"is_online": True})
        total_users = await db.users.count_documents({})
        
        print(f"\n📊 CLEANUP SUMMARY:")
        print(f"  - Total Users: {total_users}")
        print(f"  - Currently Online: {final_count}")
        print(f"  - Offline: {total_users - final_count}")
        
        if final_count > 0:
            online_users = await db.users.find(
                {"is_online": True}, 
                {"username": 1, "last_seen": 1}
            ).to_list(100)
            
            print(f"\n🟢 CURRENTLY ONLINE USERS:")
            for user in online_users:
                print(f"  - {user['username']}: {user.get('last_seen', 'Unknown')}")
        
        print(f"\n🎉 Database cleanup completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(cleanup_database())