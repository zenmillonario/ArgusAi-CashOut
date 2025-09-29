#!/usr/bin/env python3
"""
Test email service functionality
"""

import asyncio
import sys
import os
sys.path.append('/app/backend')

from email_service import EmailService
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables
load_dotenv('/app/backend/.env')

async def test_email_service():
    """Test the email service with trial welcome email"""
    
    print("🧪 Testing Email Service...")
    
    try:
        # Initialize email service
        email_service = EmailService()
        print("✅ Email service initialized")
        
        # Test trial welcome email
        trial_end = datetime.utcnow() + timedelta(days=14)
        
        result = await email_service.send_trial_welcome_email(
            user_email="test@example.com",
            user_name="Test User", 
            trial_end_date=trial_end
        )
        
        if result:
            print("✅ Trial welcome email sent successfully!")
        else:
            print("❌ Trial welcome email failed to send")
            
    except Exception as e:
        print(f"❌ Error testing email service: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_email_service())