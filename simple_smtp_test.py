#!/usr/bin/env python3
"""
Simple SMTP test following proper sequence
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/app/backend/.env')

def test_smtp_simple():
    """Test SMTP with proper sequence"""
    
    print("🔍 SIMPLE SMTP TEST...")
    
    try:
        # SMTP Configuration
        smtp_server = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('MAIL_PORT', 587))
        username = os.getenv('MAIL_USERNAME')
        password = os.getenv('MAIL_PASSWORD') 
        from_email = os.getenv('MAIL_FROM')
        
        print(f"📧 From: {from_email} → cashoutaibot@gmail.com")
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "🧪 Simple SMTP Test - ArgusAI"
        msg['From'] = from_email
        msg['To'] = "cashoutaibot@gmail.com"
        
        text_content = """
Simple SMTP Test from ArgusAI CashOut

This email tests basic SMTP delivery to Gmail.
If you receive this, email delivery is working!
"""
        
        html_content = """
<html>
<body>
    <h2>🧪 Simple SMTP Test - ArgusAI</h2>
    <p>This email tests basic SMTP delivery to Gmail.</p>
    <p><strong>If you receive this, email delivery is working!</strong></p>
</body>
</html>
"""
        
        msg.attach(MIMEText(text_content, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))
        
        # Send email using proper sequence
        print("⏳ Sending email...")
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Enable TLS
            server.login(username, password)  # Login after TLS
            server.send_message(msg)  # Send message
        
        print("✅ Email sent successfully!")
        print("📧 Check cashoutaibot@gmail.com inbox and spam")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_smtp_simple()