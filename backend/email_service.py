import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import logging
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

class EmailService:
    def __init__(self):
        self.mail_username = os.getenv("MAIL_USERNAME")
        self.mail_password = os.getenv("MAIL_PASSWORD")
        self.mail_from = os.getenv("MAIL_FROM")
        self.mail_port = int(os.getenv("MAIL_PORT", 587))
        self.mail_server = os.getenv("MAIL_SERVER")
        self.mail_tls = os.getenv("MAIL_TLS", "true").lower() == "true"
        
        if not all([self.mail_username, self.mail_password, self.mail_from, self.mail_server]):
            raise ValueError("Email configuration is incomplete. Check environment variables.")
    
    async def send_email(
        self, 
        recipient: str, 
        subject: str, 
        body: str, 
        html_body: Optional[str] = None
    ) -> bool:
        """Send email using Gmail SMTP"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.mail_from
            msg['To'] = recipient
            msg['Subject'] = subject
            
            # Add plain text part
            text_part = MIMEText(body, 'plain')
            msg.attach(text_part)
            
            # Add HTML part if provided
            if html_body:
                html_part = MIMEText(html_body, 'html')
                msg.attach(html_part)
            
            # Connect to server and send email
            with smtplib.SMTP(self.mail_server, self.mail_port) as server:
                if self.mail_tls:
                    server.starttls()
                server.login(self.mail_username, self.mail_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {recipient}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {recipient}: {str(e)}")
            return False
    
    async def send_registration_notification(
        self, 
        admin_email: str, 
        user_data: dict
    ) -> bool:
        """Send registration notification to admin"""
        subject = f"🔔 New User Registration - {user_data.get('real_name', user_data.get('username'))}"
        
        plain_body = f"""
New User Registration - ArgusAI CashOut

User Details:
• Name: {user_data.get('real_name', 'Not provided')}
• Username: {user_data.get('username')}
• Email: {user_data.get('email')}
• Screen Name: {user_data.get('screen_name', 'Not provided')}
• Membership Plan: {user_data.get('membership_plan', 'Not specified')}
• Registration Date: {datetime.utcnow().strftime('%B %d, %Y at %I:%M %p UTC')}

Please review and approve this registration in the ArgusAI CashOut admin panel.

--
ArgusAI CashOut System
"""
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f9f9f9; }}
        .user-details {{ background: white; padding: 15px; border-radius: 8px; margin: 15px 0; }}
        .detail-row {{ margin: 8px 0; }}
        .label {{ font-weight: bold; color: #555; }}
        .action-btn {{ background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; margin: 15px 0; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔔 New User Registration</h1>
        <p>ArgusAI CashOut</p>
    </div>
    
    <div class="content">
        <p>A new user has registered and is awaiting admin approval:</p>
        
        <div class="user-details">
            <div class="detail-row">
                <span class="label">Name:</span> {user_data.get('real_name', 'Not provided')}
            </div>
            <div class="detail-row">
                <span class="label">Username:</span> {user_data.get('username')}
            </div>
            <div class="detail-row">
                <span class="label">Email:</span> {user_data.get('email')}
            </div>
            <div class="detail-row">
                <span class="label">Screen Name:</span> {user_data.get('screen_name', 'Not provided')}
            </div>
            <div class="detail-row">
                <span class="label">Membership Plan:</span> {user_data.get('membership_plan', 'Not specified')}
            </div>
            <div class="detail-row">
                <span class="label">Registration Date:</span> {datetime.utcnow().strftime('%B %d, %Y at %I:%M %p UTC')}
            </div>
        </div>
        
        <p><strong>Action Required:</strong> Please review and approve this registration in the ArgusAI CashOut admin panel.</p>
    </div>
    
    <div class="footer">
        <p>This notification was sent automatically by ArgusAI CashOut System</p>
    </div>
</body>
</html>
"""
        
        return await self.send_email(admin_email, subject, plain_body, html_body)
    
    async def send_approval_confirmation(
        self, 
        user_email: str, 
        user_name: str,
        approved: bool = True
    ) -> bool:
        """Send confirmation email to user after approval/rejection"""
        if approved:
            subject = "✅ Account Approved - Welcome to ArgusAI CashOut!"
            
            plain_body = f"""
Hi {user_name},

Great news! Your ArgusAI CashOut account has been approved.

You can now log in and start trading with our community:
• Access real-time chat with other traders
• Practice paper trading
• Manage your portfolio
• Get real-time stock quotes

Welcome to the ArgusAI CashOut family!

--
ArgusAI CashOut Team
"""
            
            html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f9f9f9; }}
        .welcome-box {{ background: white; padding: 20px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #10b981; }}
        .features {{ background: white; padding: 15px; border-radius: 8px; margin: 15px 0; }}
        .feature-item {{ margin: 8px 0; }}
        .action-btn {{ background: #10b981; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; margin: 15px 0; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>✅ Account Approved!</h1>
        <p>Welcome to ArgusAI CashOut</p>
    </div>
    
    <div class="content">
        <div class="welcome-box">
            <h2>Hi {user_name},</h2>
            <p>Great news! Your ArgusAI CashOut account has been approved.</p>
        </div>
        
        <div class="features">
            <h3>You now have access to:</h3>
            <div class="feature-item">💬 Real-time chat with other traders</div>
            <div class="feature-item">📈 Practice paper trading</div>
            <div class="feature-item">💼 Portfolio management tools</div>
            <div class="feature-item">📊 Real-time stock quotes and data</div>
            <div class="feature-item">⭐ Favorites and watchlists</div>
        </div>
        
        <p><strong>Ready to start trading?</strong> Log in to your account and join our community!</p>
        
        <p>Welcome to the ArgusAI CashOut family! 🚀</p>
    </div>
    
    <div class="footer">
        <p>ArgusAI CashOut Team</p>
    </div>
</body>
</html>
"""
        else:
            subject = "❌ Account Application Update - ArgusAI CashOut"
            
            plain_body = f"""
Hi {user_name},

Thank you for your interest in ArgusAI CashOut.

Unfortunately, we're unable to approve your account at this time. This could be due to:
• Incomplete registration information
• Current membership limitations
• Other requirements not met

If you believe this is an error or would like to reapply, please contact our support team.

Thank you for your understanding.

--
ArgusAI CashOut Team
"""
            
            html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f9f9f9; }}
        .message-box {{ background: white; padding: 20px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #ef4444; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Account Application Update</h1>
        <p>ArgusAI CashOut</p>
    </div>
    
    <div class="content">
        <div class="message-box">
            <h2>Hi {user_name},</h2>
            <p>Thank you for your interest in ArgusAI CashOut.</p>
            <p>Unfortunately, we're unable to approve your account at this time.</p>
        </div>
        
        <p>If you have questions or would like to reapply, please contact our support team.</p>
        
        <p>Thank you for your understanding.</p>
    </div>
    
    <div class="footer">
        <p>ArgusAI CashOut Team</p>
    </div>
</body>
</html>
"""
        
        return await self.send_email(user_email, subject, plain_body, html_body)
    
    
    async def send_trial_welcome_email(
        self, 
        user_email: str, 
        user_name: str,
        trial_end_date: datetime
    ) -> bool:
        """Send welcome email to trial users"""
        subject = "🎉 Welcome to ArgusAI CashOut - 14-Day Trial Started!"
        
        trial_end_str = trial_end_date.strftime('%B %d, %Y at %I:%M %p UTC')
        
        plain_body = f"""
Hi {user_name},

Welcome to ArgusAI CashOut! 🚀

Your 14-day trial has started and you now have full access to our platform:

• Real-time chat with traders
• Paper trading practice
• Portfolio management
• Stock quotes and analysis
• Achievement system and rewards

Your trial period ends on: {trial_end_str}

Before your trial expires, you'll receive information about upgrading to a full membership to continue enjoying all features.

Start exploring and happy trading!

--
ArgusAI CashOut Team
"""
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%); color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f9f9f9; }}
        .welcome-box {{ background: white; padding: 20px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #8b5cf6; }}
        .features {{ background: white; padding: 15px; border-radius: 8px; margin: 15px 0; }}
        .feature-item {{ margin: 8px 0; }}
        .trial-info {{ background: #fef3c7; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #f59e0b; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎉 Welcome to ArgusAI CashOut!</h1>
        <p>Your 14-Day Trial Has Started</p>
    </div>
    
    <div class="content">
        <div class="welcome-box">
            <h2>Hi {user_name},</h2>
            <p>Welcome to ArgusAI CashOut! Your trial account is now active and ready to use.</p>
        </div>
        
        <div class="features">
            <h3>You now have access to:</h3>
            <div class="feature-item">💬 Real-time chat with other traders</div>
            <div class="feature-item">📈 Paper trading practice</div>
            <div class="feature-item">💼 Portfolio management tools</div>
            <div class="feature-item">📊 Real-time stock quotes and data</div>
            <div class="feature-item">🏆 Achievement system and rewards</div>
            <div class="feature-item">⭐ Favorites and watchlists</div>
        </div>
        
        <div class="trial-info">
            <h3>⏰ Trial Information</h3>
            <p><strong>Trial Period:</strong> 14 days</p>
            <p><strong>Trial Ends:</strong> {trial_end_str}</p>
            <p>Before your trial expires, you'll receive information about upgrading to continue enjoying all features.</p>
        </div>
        
        <p><strong>Ready to start?</strong> Log in to your account and start exploring!</p>
        
        <p>Happy trading! 🚀</p>
    </div>
    
    <div class="footer">
        <p>ArgusAI CashOut Team</p>
    </div>
</body>
</html>
"""
        
        return await self.send_email(user_email, subject, plain_body, html_body)
    
    async def send_trial_upgrade_email(
        self, 
        user_email: str, 
        user_name: str
    ) -> bool:
        """Send trial upgrade email with Argus20 discount code"""
        subject = "🎯 Your ArgusAI Trial Expired - 20% OFF with ARGUS20!"
        
        plain_body = f"""
Hi {user_name},

Your 14-day trial with ArgusAI CashOut has ended, but don't worry - we have a special offer for you!

🎉 EXCLUSIVE OFFER: Use code ARGUS20 for 20% OFF any membership plan!

What You're Missing:
• Real-time chat with traders (RESTRICTED)
• Full access to all premium features
• Advanced portfolio analytics
• Priority support

Your account is now in LIMITED ACCESS mode:
✅ You can still view your portfolio
✅ Access paper trading
✅ View market data
❌ Chat access is restricted

Ready to upgrade? Use discount code: ARGUS20

Upgrade now to get back full access with 20% savings!

--
ArgusAI CashOut Team
"""
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f9f9f9; }}
        .offer-box {{ background: #fef3c7; padding: 20px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #f59e0b; text-align: center; }}
        .discount-code {{ background: #1f2937; color: #fbbf24; padding: 10px 20px; font-size: 24px; font-weight: bold; border-radius: 8px; display: inline-block; margin: 10px 0; }}
        .restrictions {{ background: #fef2f2; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #ef4444; }}
        .benefits {{ background: white; padding: 15px; border-radius: 8px; margin: 15px 0; }}
        .cta-button {{ background: #8b5cf6; color: white; padding: 15px 30px; border-radius: 8px; text-decoration: none; display: inline-block; margin: 20px 0; font-weight: bold; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 Special Upgrade Offer!</h1>
        <p>Your trial has expired, but we have something special for you</p>
    </div>
    
    <div class="content">
        <h2>Hi {user_name},</h2>
        
        <div class="offer-box">
            <h2>🎉 EXCLUSIVE 20% OFF DISCOUNT!</h2>
            <p>Use this code for any membership plan:</p>
            <div class="discount-code">ARGUS20</div>
            <p><strong>Limited time offer - Don't miss out!</strong></p>
        </div>
        
        <div class="restrictions">
            <h3>⚠️ Your Account is Now in LIMITED ACCESS Mode</h3>
            <p>❌ <strong>Chat access is restricted</strong> - You can't view or participate in trader discussions</p>
            <p>✅ Portfolio management still available</p>
            <p>✅ Paper trading still accessible</p>
            <p>✅ Market data viewing allowed</p>
        </div>
        
        <div class="benefits">
            <h3>💎 Upgrade to get back:</h3>
            <p>💬 Full real-time chat access</p>
            <p>🏆 Achievement system and rewards</p>
            <p>📊 Advanced portfolio analytics</p>
            <p>⭐ Priority customer support</p>
            <p>🔔 Premium notifications and alerts</p>
        </div>
        
        <div style="text-align: center;">
            <a href="#" class="cta-button">🚀 Upgrade Now with ARGUS20</a>
        </div>
        
        <p><strong>Don't let this opportunity slip away!</strong> Use code <strong>ARGUS20</strong> and save 20% on any plan.</p>
    </div>
    
    <div class="footer">
        <p>ArgusAI CashOut Team</p>
        <p>This offer is valid for a limited time. Terms and conditions apply.</p>
    </div>
</body>
</html>
"""
        
        return await self.send_email(user_email, subject, plain_body, html_body)

# Create global email service instance
email_service = EmailService()