#!/usr/bin/env python3
"""
Test email service with real Gmail address
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

async def test_real_gmail():
    """Test sending email to real Gmail address with detailed diagnostics"""
    
    print("🧪 Testing Email to Real Gmail Address...")
    print("=" * 50)
    
    try:
        # Initialize email service
        email_service = EmailService()
        print("✅ Email service initialized")
        
        # Show SMTP configuration (without passwords)
        print(f"📧 SMTP Server: {os.getenv('MAIL_SERVER')}")
        print(f"📧 SMTP Port: {os.getenv('MAIL_PORT')}")
        print(f"📧 From Email: {os.getenv('MAIL_FROM')}")
        print(f"📧 SSL Enabled: {os.getenv('MAIL_SSL')}")
        print(f"📧 TLS Enabled: {os.getenv('MAIL_TLS')}")
        
        # Test trial welcome email to real address
        trial_end = datetime.utcnow() + timedelta(days=14)
        real_email = "cashoutaibot@gmail.com"
        
        print(f"\n📤 Sending trial welcome email to: {real_email}")
        print("⏳ This may take a few seconds...")
        
        result = await email_service.send_trial_welcome_email(
            user_email=real_email,
            user_name="Trial Test User", 
            trial_end_date=trial_end
        )
        
        if result:
            print("✅ Email sent successfully!")
            print("📧 Check your Gmail inbox and spam folder")
            print("⏰ Email may take 1-2 minutes to arrive")
        else:
            print("❌ Email failed to send")
        
        # Also test a simple email
        print(f"\n📤 Testing simple email to: {real_email}")
        simple_result = await email_service.send_email(
            user_email=real_email,
            subject="🧪 Test Email from ArgusAI",
            plain_body="This is a test email from ArgusAI CashOut to verify email delivery.",
            html_body="""
            <html>
            <body>
                <h2>🧪 Test Email from ArgusAI CashOut</h2>
                <p>This is a test email to verify email delivery is working.</p>
                <p>If you receive this, the email system is configured correctly!</p>
            </body>
            </html>
            """
        )
        
        if simple_result:
            print("✅ Simple test email sent successfully!")
        else:
            print("❌ Simple test email failed")
            
    except Exception as e:
        print(f"❌ Error testing email: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_real_gmail())