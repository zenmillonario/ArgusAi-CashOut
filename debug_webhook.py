#!/usr/bin/env python3

import os
import logging
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv('/app/backend/.env')

async def test_database():
    try:
        logger.info("🔧 Testing database connection...")
        mongo_url = os.environ.get('MONGO_URL')
        logger.info(f"MongoDB URL: {mongo_url}")
        
        client = AsyncIOMotorClient(mongo_url)
        db = client.argus_cashout
        
        # Test connection
        await client.admin.command('ping')
        logger.info("✅ Database connection successful")
        
        # Check collections
        collections = await db.list_collection_names()
        logger.info(f"📁 Available collections: {collections}")
        
        # Test bot user creation
        bot_user = await db.users.find_one({"username": "cashoutai_bot"})
        if bot_user:
            logger.info(f"✅ Bot user exists: {bot_user.get('real_name')}")
        else:
            logger.info("❌ Bot user does not exist")
        
        # Test message insertion
        test_message = {
            "id": "test-message-123",
            "user_id": "test-user",
            "username": "test_bot",
            "content": "Test message from debug script",
            "content_type": "text",
            "is_admin": True,
            "is_bot": True,
            "real_name": "Test Bot"
        }
        
        result = await db.messages.insert_one(test_message)
        logger.info(f"✅ Test message inserted: {result.inserted_id}")
        
        # Clean up test message
        await db.messages.delete_one({"id": "test-message-123"})
        logger.info("🧹 Test message cleaned up")
        
        client.close()
        
    except Exception as e:
        logger.error(f"❌ Database test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_database())