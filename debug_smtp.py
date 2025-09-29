#!/usr/bin/env python3
"""
Debug SMTP connection and delivery issues
"""

import asyncio
import aiosmtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/app/backend/.env')

async def debug_smtp():
    """Debug SMTP connection with detailed error checking"""
    
    print("🔍 DEBUGGING SMTP CONNECTION...")
    print("=" * 50)
    
    try:
        # SMTP Configuration
        smtp_server = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('MAIL_PORT', 587))
        username = os.getenv('MAIL_USERNAME')
        password = os.getenv('MAIL_PASSWORD') 
        from_email = os.getenv('MAIL_FROM')
        
        print(f"📧 SMTP Server: {smtp_server}:{smtp_port}")
        print(f"📧 From: {from_email}")
        print(f"📧 Username: {username}")
        print(f"📧 Password: {'*' * len(password) if password else 'Not set'}")
        
        # Test SMTP connection
        print(f"\n🔌 Testing SMTP connection...")
        
        smtp_client = aiosmtplib.SMTP(
            hostname=smtp_server,
            port=smtp_port,
            start_tls=True,
            username=username,
            password=password
        )
        
        # Connect to server
        print("⏳ Connecting to SMTP server...")
        await smtp_client.connect()
        print("✅ SMTP connection established")
        
        # Test authentication
        print("⏳ Testing authentication...")
        await smtp_client.login(username, password)
        print("✅ SMTP authentication successful")
        
        # Create test message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "🧪 SMTP Debug Test - ArgusAI"
        msg['From'] = from_email
        msg['To'] = "cashoutaibot@gmail.com"
        
        text_content = """
SMTP Debug Test from ArgusAI CashOut

This is a direct SMTP test to verify email delivery.
If you receive this, the SMTP configuration is working correctly.

Test details:
- SMTP Server: smtp.gmail.com:587
- Authentication: Successful
- TLS: Enabled
"""
        
        html_content = """
<html>
<body style="font-family: Arial, sans-serif;">
    <h2 style="color: #8b5cf6;">🧪 SMTP Debug Test - ArgusAI CashOut</h2>
    <p>This is a <strong>direct SMTP test</strong> to verify email delivery.</p>
    <p>If you receive this, the SMTP configuration is working correctly!</p>
    
    <div style="background: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
        <h3>Test Details:</h3>
        <ul>
            <li>SMTP Server: smtp.gmail.com:587</li>
            <li>Authentication: ✅ Successful</li>
            <li>TLS: ✅ Enabled</li>
            <li>Time: {}</li>
        </ul>
    </div>
    
    <p style="color: #059669;"><strong>✅ Email system is working!</strong></p>
</body>
</html>
        """.format(asyncio.get_event_loop().time())
        
        msg.attach(MIMEText(text_content, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))
        
        # Send the message
        print("📤 Sending test email...")
        await smtp_client.send_message(msg)
        print("✅ Email sent via direct SMTP!")
        
        # Close connection
        await smtp_client.quit()
        print("🔌 SMTP connection closed")
        
        print(f"\n🎯 SUCCESS: Email sent to cashoutaibot@gmail.com")
        print(f"📧 Check your Gmail inbox and spam folder")
        print(f"⏰ Email should arrive within 1-2 minutes")
        
    except Exception as e:
        print(f"❌ SMTP Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_smtp())