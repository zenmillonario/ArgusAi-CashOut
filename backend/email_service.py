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
        
        # Log which env vars are present/missing for debugging
        vars_status = {
            "MAIL_USERNAME": bool(self.mail_username),
            "MAIL_PASSWORD": bool(self.mail_password),
            "MAIL_FROM": bool(self.mail_from),
            "MAIL_SERVER": bool(self.mail_server),
            "MAIL_PORT": self.mail_port,
        }
        logger.info(f"EmailService init - env vars status: {vars_status}")
        
        missing = [k for k, v in vars_status.items() if v is False]
        if missing:
            raise ValueError(f"Email configuration incomplete. Missing: {missing}")
    
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
        subject = f"🔔 New REGULAR User Registration - {user_data.get('real_name', user_data.get('username'))} (Requires Approval)"
        
        plain_body = f"""
New REGULAR User Registration - ArgusAI CashOut

👤 PENDING APPROVAL REQUIRED

User Details:
• Name: {user_data.get('real_name', 'Not provided')}
• Username: {user_data.get('username')}
• Email: {user_data.get('email')}
• Screen Name: {user_data.get('screen_name', 'Not provided')}
• Membership Plan: {user_data.get('membership_plan', 'Not specified')}
• Registration Date: {datetime.utcnow().strftime('%B %d, %Y at %I:%M %p UTC')}

⚠️ This user is PENDING and cannot access the platform until you approve them.

Please review and approve this registration in the ArgusAI CashOut admin panel.
Login at: https://www.CashOutAi.App

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
    
    async def send_trial_registration_notification(
        self, 
        admin_email: str, 
        user_data: dict
    ) -> bool:
        """Send trial registration notification to admin"""
        trial_end_date = user_data.get('trial_end_date')
        trial_end_str = trial_end_date.strftime('%B %d, %Y at %I:%M %p UTC') if trial_end_date else 'Not set'
        
        subject = f"🎯 New TRIAL User Registration - {user_data.get('real_name', user_data.get('username'))}"
        
        plain_body = f"""
New TRIAL User Registration - ArgusAI CashOut

🎯 TRIAL USER DETAILS:
• Name: {user_data.get('real_name', 'Not provided')}
• Username: {user_data.get('username')}
• Email: {user_data.get('email')}
• Membership Plan: {user_data.get('membership_plan', '14-Day Trial')}
• Trial Start: {datetime.utcnow().strftime('%B %d, %Y at %I:%M %p UTC')}
• Trial Ends: {trial_end_str}
• Registration Date: {datetime.utcnow().strftime('%B %d, %Y at %I:%M %p UTC')}

✅ This user was automatically approved and can start using the platform immediately.
🎯 They have 14 days of full access before requiring upgrade.

Login at: https://www.CashOutAi.App

--
ArgusAI CashOut System
"""
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trial Registration Notification</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background-color: #f8fafc; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px 20px; text-align: center; }}
        .header h1 {{ color: white; margin: 0; font-size: 24px; font-weight: 600; }}
        .content {{ padding: 30px 20px; }}
        .trial-badge {{ background: #10b981; color: white; padding: 8px 16px; border-radius: 20px; display: inline-block; font-weight: 600; margin-bottom: 20px; }}
        .user-info {{ background: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .user-info h3 {{ margin-top: 0; color: #374151; }}
        .info-row {{ display: flex; justify-content: space-between; margin: 10px 0; padding: 8px 0; border-bottom: 1px solid #e5e7eb; }}
        .info-label {{ font-weight: 600; color: #6b7280; }}
        .info-value {{ color: #374151; }}
        .trial-info {{ background: #ecfdf5; border: 1px solid #10b981; border-radius: 8px; padding: 20px; margin: 20px 0; }}
        .trial-info h4 {{ margin-top: 0; color: #047857; }}
        .footer {{ background: #f8fafc; padding: 20px; text-align: center; border-top: 1px solid #e5e7eb; }}
        .button {{ background: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 New Trial Registration</h1>
        </div>
        <div class="content">
            <div class="trial-badge">TRIAL USER</div>
            
            <div class="user-info">
                <h3>User Information</h3>
                <div class="info-row">
                    <span class="info-label">Name:</span>
                    <span class="info-value">{user_data.get('real_name', 'Not provided')}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Username:</span>
                    <span class="info-value">{user_data.get('username')}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Email:</span>
                    <span class="info-value">{user_data.get('email')}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Membership:</span>
                    <span class="info-value">{user_data.get('membership_plan', '14-Day Trial')}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Registration:</span>
                    <span class="info-value">{datetime.utcnow().strftime('%B %d, %Y at %I:%M %p UTC')}</span>
                </div>
            </div>
            
            <div class="trial-info">
                <h4>📅 Trial Information</h4>
                <p><strong>Trial Period:</strong> 14 days of full access</p>
                <p><strong>Status:</strong> ✅ Automatically approved - active now</p>
                <p><strong>Trial Ends:</strong> {trial_end_str}</p>
                <p>This user can immediately access chat, trading tools, and all platform features.</p>
            </div>
        </div>
        <div class="footer">
            <a href="https://www.CashOutAi.App" class="button">View Platform</a>
            <p style="margin-top: 15px; color: #6b7280; font-size: 14px;">ArgusAI CashOut Admin System</p>
        </div>
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
    
    
    async def send_trial_upgrade_email(
        self, 
        user_email: str, 
        user_name: str
    ) -> bool:
        """Send trial upgrade email with Square payment links"""
        subject = "🎯 Your CashOutAi Trial Has Expired - Upgrade Now!"
        
        plain_body = f"""
Hi {user_name},

Your 14-day trial with CashOutAi has ended. Upgrade now to keep full access!

💰 CHOOSE YOUR PLAN - ONE CLICK PAYMENT:

💳 MONTHLY PLAN: $199/month
   ► PAYMENT LINK: https://square.link/u/dhjuwn84

🏆 YEARLY PLAN: $1,296/year [BEST VALUE]
   ► PAYMENT LINK: https://square.link/u/kKmNauCe

💎 LIFETIME PLAN: $3,969 one-time [NEVER PAY AGAIN]
   ► PAYMENT LINK: https://square.link/u/dRSryNkx

🚀 UPGRADE BENEFITS:
• Unlimited real-time chat with successful traders
• Advanced portfolio analytics and insights
• Priority customer support
• Exclusive trading signals and alerts
• Access to premium educational content

Your account is now in LIMITED ACCESS mode:
✅ Portfolio management available
✅ Paper trading accessible
✅ Market data viewing
❌ Chat access restricted (upgrade to unlock)

Ready to rejoin our trading community? Choose your plan above!

--
CashOutAi Team
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
        .plans-section {{ background: white; padding: 20px; border-radius: 8px; margin: 15px 0; }}
        .plan-card {{ border: 2px solid #e5e7eb; border-radius: 8px; padding: 15px; margin: 10px 0; text-align: center; }}
        .plan-price {{ font-size: 24px; font-weight: bold; color: #1f2937; margin: 10px 0; }}
        .plan-button {{ background: #8b5cf6; color: white; padding: 12px 25px; border-radius: 6px; text-decoration: none; display: inline-block; margin: 10px 0; font-weight: bold; transition: background 0.3s; }}
        .plan-button:hover {{ background: #7c3aed; }}
        .restrictions {{ background: #fef2f2; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #ef4444; }}
        .benefits {{ background: white; padding: 15px; border-radius: 8px; margin: 15px 0; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 Time to Upgrade!</h1>
        <p>Your trial has expired - choose a plan to continue</p>
    </div>
    
    <div class="content">
        <h2>Hi {user_name},</h2>
        <p>Your 14-day free trial has ended. Upgrade now to keep full access to CashOutAi!</p>
        
        <div class="plans-section">
            <h3 style="text-align: center; margin-bottom: 20px;">💰 Choose Your Plan - One Click Payment:</h3>
            
            <div class="plan-card" style="border: 2px solid #3b82f6;">
                <h4>📅 Monthly Plan</h4>
                <div class="plan-price">$199/month</div>
                <p>Perfect for getting started</p>
                <a href="https://square.link/u/dhjuwn84" class="plan-button" style="background: #3b82f6;">💳 Pay Now - $199/month</a>
            </div>
            
            <div class="plan-card" style="border: 3px solid #f59e0b; position: relative;">
                <div style="position: absolute; top: -15px; left: 50%; transform: translateX(-50%); background: #ef4444; color: white; padding: 6px 16px; border-radius: 20px; font-size: 13px; font-weight: bold;">🏆 BEST VALUE</div>
                <h4>🌟 Yearly Plan (Most Popular)</h4>
                <div class="plan-price">$1,296/year</div>
                <p>Save over $1,000 compared to monthly!</p>
                <a href="https://square.link/u/kKmNauCe" class="plan-button" style="background: #f59e0b;">🏆 Pay Now - $1,296/year</a>
            </div>
            
            <div class="plan-card" style="border: 2px solid #8b5cf6;">
                <h4>♾️ Lifetime Plan</h4>
                <div class="plan-price">$3,969 one-time</div>
                <p>Never pay again - lifetime access</p>
                <a href="https://square.link/u/dRSryNkx" class="plan-button" style="background: #8b5cf6;">💎 Pay Now - $3,969</a>
            </div>
        </div>
        
        <div class="restrictions">
            <h3>⚠️ Your Account is Now in LIMITED ACCESS Mode</h3>
            <p>❌ <strong>Chat access is restricted</strong> - You can't view or participate in trader discussions</p>
            <p>✅ Portfolio management still available</p>
            <p>✅ Paper trading still accessible</p>
            <p>✅ Market data viewing allowed</p>
        </div>
        
        <div class="benefits">
            <h3>🚀 Upgrade to unlock:</h3>
            <p>💬 <strong>Unlimited real-time chat</strong> with successful traders</p>
            <p>📊 <strong>Advanced portfolio analytics</strong> and insights</p>
            <p>🔔 <strong>Exclusive trading signals</strong> and alerts</p>
            <p>⭐ <strong>Priority customer support</strong></p>
            <p>🎓 <strong>Access to premium educational content</strong></p>
        </div>
        
        <p style="text-align: center;"><strong>Ready to rejoin our trading community?</strong><br>Choose your plan above!</p>
    </div>
    
    <div class="footer">
        <p>CashOutAi Team</p>
        <p>After payment, your account will be upgraded to full member status within 24 hours.</p>
    </div>
</body>
</html>
"""
        
        return await self.send_email(user_email, subject, plain_body, html_body)
    
    async def send_trial_welcome_email(
        self, 
        user_email: str, 
        user_name: str,
        trial_end_date
    ) -> bool:
        """Send comprehensive trial welcome email with login info"""
        subject = "🎉 Welcome to CashOutAi - Your 14-Day FREE Trial Starts Now!"
        
        trial_end_formatted = trial_end_date.strftime('%B %d, %Y at %I:%M %p UTC')
        
        plain_body = f"""
🎉 Welcome to CashOutAi, {user_name}!

Congratulations! Your 14-day FREE trial has started and you now have FULL ACCESS to our premium trading platform.

🔑 YOUR LOGIN CREDENTIALS:
• Website: www.CashOutAi.App
• Email: {user_email}
• Password: [The password you created during registration]

✨ WHAT YOU GET DURING YOUR TRIAL:
• Unlimited real-time chat with successful traders
• Complete message history and trading discussions
• Advanced portfolio management tools  
• Paper trading practice mode
• Real-time market data and alerts
• Achievement system and XP rewards
• Priority support

⏰ TRIAL DETAILS:
• Trial Started: Now
• Trial Ends: {trial_end_formatted}
• Full Access: 14 days of unlimited features

💰 MEMBERSHIP PLANS (upgrade anytime):

💳 MONTHLY PLAN: $199/month
   Payment Link: https://square.link/u/dhjuwn84

🏆 YEARLY PLAN: $1,296/year [MOST POPULAR]
   Payment Link: https://square.link/u/kKmNauCe

💎 LIFETIME PLAN: $3,969 one-time
   Payment Link: https://square.link/u/dRSryNkx

🚀 GET STARTED:
1. Login at: www.CashOutAi.App
2. Join the live trading chat
3. Connect with our community of traders
4. Start building your portfolio

Questions? Reply to this email for instant support!

Welcome to the CashOutAi trading family! 🎯

--
The CashOutAi Team
"""
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; background: #f4f4f4; margin: 0; padding: 20px; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 0 20px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #8b5cf6 0%, #3b82f6 100%); color: white; padding: 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 28px; }}
        .content {{ padding: 30px; }}
        .login-box {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #8b5cf6; }}
        .features-box {{ background: #e0f2fe; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .pricing-box {{ background: #fff3e0; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ff9800; }}
        .cta-button {{ background: #8b5cf6; color: white; padding: 15px 30px; border-radius: 8px; text-decoration: none; display: inline-block; margin: 20px 0; font-weight: bold; }}
        .trial-timer {{ background: #fee; padding: 15px; border-radius: 8px; border-left: 4px solid #ef4444; margin: 20px 0; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 14px; background: #f8f9fa; }}
        .feature-list {{ margin: 15px 0; }}
        .feature-list li {{ margin: 5px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎉 Welcome to CashOutAi!</h1>
            <p>Your 14-Day FREE Trial Starts Now</p>
        </div>
        
        <div class="content">
            <h2>Congratulations, {user_name}! 🚀</h2>
            <p>You now have <strong>FULL ACCESS</strong> to our premium trading platform for the next 14 days!</p>
            
            <div class="login-box">
                <h3>🔑 Your Login Credentials</h3>
                <p><strong>Website:</strong> <a href="https://www.CashOutAi.App">www.CashOutAi.App</a></p>
                <p><strong>Email:</strong> {user_email}</p>
                <p><strong>Password:</strong> [The password you created during registration]</p>
                <div style="text-align: center; margin: 20px 0;">
                    <a href="https://www.CashOutAi.App" class="cta-button">🚀 Start Trading Now</a>
                </div>
            </div>
            
            <div class="trial-timer">
                <h3>⏰ Trial Information</h3>
                <p><strong>Trial Started:</strong> Right Now!</p>
                <p><strong>Trial Ends:</strong> {trial_end_formatted}</p>
                <p><strong>Access Level:</strong> FULL Premium Access</p>
            </div>
            
            <div class="features-box">
                <h3>✨ What You Get During Your Trial</h3>
                <ul class="feature-list">
                    <li>💬 <strong>Unlimited real-time chat</strong> with successful traders</li>
                    <li>📚 <strong>Complete message history</strong> and trading discussions</li>
                    <li>📊 <strong>Advanced portfolio management</strong> tools</li>
                    <li>📈 <strong>Paper trading practice</strong> mode</li>
                    <li>🔔 <strong>Real-time market data</strong> and alerts</li>
                    <li>🏆 <strong>Achievement system</strong> and XP rewards</li>
                    <li>⭐ <strong>Priority customer support</strong></li>
                </ul>
            </div>
            
            <div class="pricing-box">
                <h3>💰 Membership Plans</h3>
                <p>Upgrade anytime to keep full access after your trial:</p>
                
                <div style="background: white; padding: 15px; border-radius: 8px; margin: 10px 0; border: 2px solid #e5e7eb; text-align: center;">
                    <h4 style="margin: 0; color: #1f2937;">🗓️ Monthly Plan</h4>
                    <p style="margin: 5px 0; font-size: 20px; font-weight: bold; color: #1f2937;">$199/month</p>
                    <a href="https://square.link/u/dhjuwn84" style="background: #3b82f6; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: bold; display: inline-block; margin-top: 10px;">💳 Choose Monthly</a>
                </div>
                
                <div style="background: linear-gradient(135deg, #fef3c7 0%, #fbbf24 100%); padding: 15px; border-radius: 8px; margin: 10px 0; border: 2px solid #f59e0b; text-align: center; position: relative;">
                    <div style="position: absolute; top: -10px; left: 50%; transform: translateX(-50%); background: #ef4444; color: white; padding: 4px 12px; border-radius: 15px; font-size: 12px; font-weight: bold;">MOST POPULAR</div>
                    <h4 style="margin: 0; color: #1f2937;">📅 Yearly Plan</h4>
                    <p style="margin: 5px 0; font-size: 20px; font-weight: bold; color: #1f2937;">$1,296/year</p>
                    <a href="https://square.link/u/kKmNauCe" style="background: #f59e0b; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: bold; display: inline-block; margin-top: 10px;">🏆 Choose Yearly</a>
                </div>
                
                <div style="background: white; padding: 15px; border-radius: 8px; margin: 10px 0; border: 2px solid #e5e7eb; text-align: center;">
                    <h4 style="margin: 0; color: #1f2937;">♾️ Lifetime Plan</h4>
                    <p style="margin: 5px 0; font-size: 20px; font-weight: bold; color: #1f2937;">$3,969 one-time</p>
                    <a href="https://square.link/u/dRSryNkx" style="background: #8b5cf6; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: bold; display: inline-block; margin-top: 10px;">💎 Choose Lifetime</a>
                </div>
            </div>
            
            <div style="background: #e8f5e8; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center;">
                <h3>🚀 Ready to Get Started?</h3>
                <p>Join our community of successful traders and start building your portfolio today!</p>
                <a href="https://www.CashOutAi.App" class="cta-button">Login & Start Trading</a>
            </div>
            
            <p>Questions? Simply reply to this email for instant support from our team!</p>
            <p><strong>Welcome to the CashOutAi trading family!</strong> 🎯</p>
        </div>
        
        <div class="footer">
            <p>The CashOutAi Team</p>
            <p>This trial gives you full access to our premium features for 14 days.</p>
        </div>
    </div>
</body>
</html>
"""
        
        return await self.send_email(user_email, subject, plain_body, html_body)
    
    async def send_general_welcome_email(
        self, 
        user_email: str, 
        user_name: str,
        username: str,
        membership_plan: str
    ) -> bool:
        """Send general welcome email for approved users with login info"""
        subject = "🎉 Welcome to ArgusAI CashOut - Account Approved!"
        
        plain_body = f"""
🎉 Welcome to ArgusAI CashOut, {user_name}!

Great news! Your account has been approved and you now have full access to our premium trading platform.

🔑 YOUR LOGIN CREDENTIALS:
• Website: https://www.CashOutAi.App/
• Username: {username}
• Email: {user_email}
• Password: [The password you created during registration]
• Membership Plan: {membership_plan}

🚀 PREMIUM FEATURES YOU NOW HAVE ACCESS TO:
• Unlimited real-time chat with successful traders
• Complete trading discussion history
• Advanced portfolio management tools
• Paper trading practice mode
• Real-time market data and alerts
• Achievement system and XP rewards
• Priority customer support
• Email-to-chat price alerts
• WhatsApp trading alerts

💡 GET STARTED:
1. Login at: https://www.CashOutAi.App/
2. Join the live trading chat
3. Connect with our community of traders
4. Start building and tracking your portfolio
5. Practice with paper trading

🎯 COMMUNITY GUIDELINES:
• Share your trades and insights
• Help fellow traders learn and grow
• Ask questions - our community loves to help
• Stay respectful and professional

Questions or need help getting started? Reply to this email!

Welcome to the ArgusAI trading family! 🎯

--
The ArgusAI CashOut Team
"""
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; background: #f4f4f4; margin: 0; padding: 20px; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 0 20px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 28px; }}
        .content {{ padding: 30px; }}
        .login-box {{ background: #f0f9ff; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #0ea5e9; }}
        .features-box {{ background: #f0fdf4; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .cta-button {{ background: #059669; color: white; padding: 15px 30px; border-radius: 8px; text-decoration: none; display: inline-block; margin: 20px 0; font-weight: bold; }}
        .approved-badge {{ background: #dcfce7; color: #166534; padding: 10px 20px; border-radius: 20px; display: inline-block; font-weight: bold; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 14px; background: #f8f9fa; }}
        .feature-list {{ margin: 15px 0; }}
        .feature-list li {{ margin: 5px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎉 Account Approved!</h1>
            <p>Welcome to ArgusAI CashOut Premium</p>
        </div>
        
        <div class="content">
            <div style="text-align: center; margin: 20px 0;">
                <div class="approved-badge">✅ APPROVED - FULL ACCESS GRANTED</div>
            </div>
            
            <h2>Welcome, {user_name}! 🚀</h2>
            <p>Congratulations! Your <strong>{membership_plan}</strong> membership has been approved and you now have full access to our premium trading platform.</p>
            
            <div class="login-box">
                <h3>🔑 Your Login Credentials</h3>
                <p><strong>Website:</strong> <a href="https://www.CashOutAi.App/">https://www.CashOutAi.App/</a></p>
                <p><strong>Username:</strong> {username}</p>
                <p><strong>Email:</strong> {user_email}</p>
                <p><strong>Password:</strong> [Your registration password]</p>
                <p><strong>Membership:</strong> {membership_plan}</p>
                <div style="text-align: center; margin: 20px 0;">
                    <a href="https://www.CashOutAi.App/" class="cta-button">🚀 Login & Start Trading</a>
                </div>
            </div>
            
            <div class="features-box">
                <h3>🚀 Your Premium Features</h3>
                <ul class="feature-list">
                    <li>💬 <strong>Unlimited real-time chat</strong> with successful traders</li>
                    <li>📚 <strong>Complete trading history</strong> and discussions</li>
                    <li>📊 <strong>Advanced portfolio management</strong></li>
                    <li>📈 <strong>Paper trading practice</strong> mode</li>
                    <li>🔔 <strong>Real-time alerts</strong> and notifications</li>
                    <li>🏆 <strong>Achievement system</strong> and XP rewards</li>
                    <li>⭐ <strong>Priority support</strong></li>
                    <li>📧 <strong>Email-to-chat</strong> price alerts</li>
                    <li>📱 <strong>WhatsApp</strong> trading alerts</li>
                </ul>
            </div>
            
            <div style="background: #fef3c7; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3>💡 Getting Started</h3>
                <p><strong>1.</strong> Login to your account</p>
                <p><strong>2.</strong> Join the live trading chat</p>
                <p><strong>3.</strong> Connect with our trader community</p>
                <p><strong>4.</strong> Start building your portfolio</p>
                <p><strong>5.</strong> Practice with paper trading</p>
            </div>
            
            <div style="background: #e0e7ff; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3>🎯 Community Guidelines</h3>
                <p>• Share trades and insights with the community</p>
                <p>• Help fellow traders learn and grow</p>
                <p>• Ask questions - we love helping members succeed</p>
                <p>• Maintain respectful and professional discussions</p>
            </div>
            
            <p>Questions or need help getting started? Simply reply to this email for instant support!</p>
            <p><strong>Welcome to the ArgusAI trading family!</strong> 🎯</p>
        </div>
        
        <div class="footer">
            <p>The ArgusAI CashOut Team</p>
            <p>Your premium membership gives you access to all our trading features and community.</p>
        </div>
    </div>
</body>
</html>
"""
        
        return await self.send_email(user_email, subject, plain_body, html_body)

# Create global email service instance
email_service = EmailService()