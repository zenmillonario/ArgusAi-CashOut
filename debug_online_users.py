#!/usr/bin/env python3
"""
Debug script to investigate online users issue
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json

# Load environment variables
load_dotenv('/app/backend/.env')

async def debug_online_users():
    """Debug online users tracking"""
    
    mongo_url = os.environ['MONGO_URL']
    db_name = os.environ['DB_NAME']
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print("🔍 DEBUGGING ONLINE USERS ISSUE")
    print("=" * 50)
    
    try:
        # Check total users
        total_users = await db.users.count_documents({})
        print(f"📊 Total Users: {total_users}")
        
        # Check users marked as online
        online_users_cursor = db.users.find({"is_online": True})
        online_users = await online_users_cursor.to_list(1000)
        print(f"🟢 Users Marked Online: {len(online_users)}")
        
        # Display online users details
        if online_users:
            print("\n📋 ONLINE USERS DETAILS:")
            for i, user in enumerate(online_users, 1):
                last_seen = user.get('last_seen', 'Never')
                session_id = user.get('active_session_id', 'None')
                created_at = user.get('session_created_at', 'Unknown')
                
                print(f"  {i}. {user['username']} ({user.get('real_name', 'No Name')})")
                print(f"     - Last Seen: {last_seen}")
                print(f"     - Session ID: {session_id}")
                print(f"     - Session Created: {created_at}")
                print()
        
        # Check for stale sessions (older than 1 hour)
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        stale_sessions = await db.users.find({
            "is_online": True,
            "last_seen": {"$lt": one_hour_ago}
        }).to_list(1000)
        
        print(f"⚠️ Potentially Stale Sessions (>1 hour old): {len(stale_sessions)}")
        
        if stale_sessions:
            print("\n🕐 STALE SESSIONS:")
            for user in stale_sessions:
                print(f"  - {user['username']}: Last seen {user.get('last_seen', 'Unknown')}")
        
        # Check WebSocket connections (can't directly access from here, but show session data)
        print(f"\n📡 SESSION ANALYSIS:")
        active_sessions = await db.users.find({
            "active_session_id": {"$exists": True, "$ne": None}
        }).to_list(1000)
        print(f"  - Users with Active Sessions: {len(active_sessions)}")
        
        # Check if all online users have valid sessions
        online_without_session = await db.users.find({
            "is_online": True,
            "$or": [
                {"active_session_id": {"$exists": False}},
                {"active_session_id": None}
            ]
        }).to_list(1000)
        
        print(f"  - Online Users Without Sessions: {len(online_without_session)}")
        
        if online_without_session:
            print("\n❌ USERS ONLINE WITHOUT VALID SESSIONS:")
            for user in online_without_session:
                print(f"  - {user['username']}: No session but marked online")
        
        # Suggest cleanup if needed
        if stale_sessions or online_without_session:
            print(f"\n💡 RECOMMENDATIONS:")
            if stale_sessions:
                print(f"  1. Mark {len(stale_sessions)} stale sessions as offline")
            if online_without_session:
                print(f"  2. Mark {len(online_without_session)} sessionless users as offline")
            
            cleanup_choice = input("\n🔧 Would you like to clean up stale/invalid online users? (y/n): ")
            
            if cleanup_choice.lower() == 'y':
                # Cleanup stale sessions
                if stale_sessions:
                    stale_ids = [user['id'] for user in stale_sessions]
                    result = await db.users.update_many(
                        {"id": {"$in": stale_ids}},
                        {"$set": {"is_online": False}}
                    )
                    print(f"✅ Marked {result.modified_count} stale sessions as offline")
                
                # Cleanup users online without sessions
                if online_without_session:
                    sessionless_ids = [user['id'] for user in online_without_session]
                    result = await db.users.update_many(
                        {"id": {"$in": sessionless_ids}},
                        {"$set": {"is_online": False}}
                    )
                    print(f"✅ Marked {result.modified_count} sessionless users as offline")
                    
                print(f"\n🎉 Cleanup completed! Check the app now.")
            else:
                print("👍 No cleanup performed.")
        else:
            print(f"\n✅ No obvious issues found with online user tracking.")
            print(f"📝 The issue might be in the frontend WebSocket handling or data sync.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(debug_online_users())