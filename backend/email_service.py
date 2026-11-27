import os
import asyncio
import logging
from datetime import datetime, timezone
from html import escape
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path
import resend

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

class EmailService:
    def __init__(self):
        self.resend_api_key = os.getenv("RESEND_API_KEY")
        self.sender_email = os.getenv("SENDER_EMAIL", "onboarding@resend.dev")
        
        if not self.resend_api_key:
            raise ValueError("RESEND_API_KEY is missing from environment variables")
        
        resend.api_key = self.resend_api_key
        logger.info(f"EmailService init - using Resend API, sender: {self.sender_email}")
    
    async def send_email(
        self, 
        recipient: str, 
        subject: str, 
        body: str, 
        html_body: Optional[str] = None,
        *,
        return_outcome: bool = False
    ):
        """Send email, optionally distinguishing acceptance from uncertainty.

        Legacy callers retain a boolean result. Paid approval records the more
        precise result so a timeout never causes an automatic duplicate welcome.
        """
        try:
            params = {
                "from": self.sender_email,
                "to": [recipient],
                "subject": subject,
                "text": body,
                "html": html_body or body,
            }
            
            email = await asyncio.to_thread(resend.Emails.send, params)
            message_id = email.get("id") if isinstance(email, dict) else None
            if isinstance(message_id, str) and message_id:
                outcome = {"status": "sent", "provider_message_id": message_id}
                logger.info("Email accepted by provider; inbox delivery is not confirmed.")
            else:
                outcome = {"status": "unknown"}
                logger.warning("Email provider returned no message ID; outcome requires review.")
            
        except Exception as e:
            # A transport error may happen after the provider accepted the send.
            # Only an explicit HTTP rejection is a definite failed attempt.
            code = getattr(e, "status_code", None)
            rejected = type(code) is int and 400 <= code < 500 and code != 408
            outcome = {"status": "failed" if rejected else "unknown"}
            logger.warning("Email send was rejected." if rejected else "Email send outcome is unknown.")
        return outcome if return_outcome else outcome["status"] == "sent"
    
    APP_URL = "https://cashoutai.app/"
    MEMBERSHIP_URL = "https://cashoutai.app/?billing=1"

    @staticmethod
    def _existing_trial_end_label(value) -> str:
        """Render a supplied legacy expiry without inventing a new trial term."""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return "Not available; check Membership in the app"
        if not isinstance(value, datetime):
            return "Not available; check Membership in the app"
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value.strftime("%B %d, %Y at %I:%M %p UTC")

    async def send_registration_notification(
        self,
        admin_email: str,
        user_data: dict
    ) -> bool:
        """Ask an administrator to match the signup to a reviewed payment."""
        subject = "New CashOutAI signup — review required"
        fields = {
            "Name": user_data.get("real_name") or "Not provided",
            "Username": user_data.get("username") or "Not provided",
            "Email": user_data.get("email") or "Not provided",
            "Screen name": user_data.get("screen_name") or "Not provided",
            "Selected plan": user_data.get("membership_plan") or "Not specified",
        }
        plain_details = "\n".join(f"{label}: {value}" for label, value in fields.items())
        html_details = "".join(
            f"<li><strong>{label}:</strong> {escape(str(value), quote=True)}</li>"
            for label, value in fields.items()
        )
        plain_body = f"""A new CashOutAI account is pending administrator approval.

{plain_details}

Selecting a plan does not confirm payment. Check the Square payment and match it to this existing account before approving a paid purchase in the app. Record the actual purchased plan and receipt/reference when you approve access.

Current membership purchases are one-time payments with no automatic renewal. Access is activated after manual review.

Open the administrator panel: {self.APP_URL}

The CashOutAI Team
"""
        html_body = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>CashOutAI signup review</title></head>
<body style="font-family:Arial,sans-serif;line-height:1.6;color:#172033;">
  <h1>New signup awaiting review</h1>
  <ul>{html_details}</ul>
  <p>Selecting a plan does not confirm payment. Check the Square payment and match it to this existing account before approving a paid purchase in the app. Record the actual purchased plan and receipt/reference when you approve access.</p>
  <p>Current membership purchases are one-time payments with no automatic renewal. Access is activated after manual review.</p>
  <p><a href="{self.APP_URL}">Open the administrator panel</a></p>
  <p>The CashOutAI Team</p>
</body>
</html>"""
        return await self.send_email(admin_email, subject, plain_body, html_body)

    async def send_event_registration_notification(
        self, admin_email: str, user_data: dict
    ) -> bool:
        """Inform the admin of a saved free-event signup, not a paid approval."""
        subject = "CashOutAI — New Free Event Participant"
        fields = {
            "Username": user_data.get("username") or "Not provided",
            "Email": user_data.get("email") or "Not provided",
            "Access": "Free Event Access",
            "Expires": "Monday, November 30, 2026 at 11:59 PM Eastern",
            "Payment": "Not required",
            "Status at signup": "Awaiting email verification",
        }
        plain_details = "\n".join(f"{label}: {value}" for label, value in fields.items())
        html_details = "".join(
            f"<li><strong>{label}:</strong> {escape(str(value), quote=True)}</li>"
            for label, value in fields.items()
        )
        note = ("The participant receives a separate verification link. Eligible event access is activated "
                "automatically after email verification; no administrator approval is needed. "
                "This notice does not confirm verification or a payment.")
        plain = f"New free event signup\n\n{plain_details}\n\n{note}\n\nOpen Admin: {self.APP_URL}"
        html = (f'<!doctype html><html lang="en"><body style="font-family:Arial,sans-serif;line-height:1.6">'
                f'<h1>New Free Event Participant</h1><ul>{html_details}</ul><p>{note}</p>'
                f'<p><a href="{self.APP_URL}">Open Admin</a></p></body></html>')
        return await self.send_email(admin_email, subject, plain, html)

    async def send_trial_registration_notification(
        self,
        admin_email: str,
        user_data: dict
    ) -> bool:
        """Retain legacy compatibility without announcing a new or approved trial."""
        subject = "CashOutAI — existing trial account details"
        trial_end = self._existing_trial_end_label(user_data.get("trial_end_date"))
        fields = {
            "Name": user_data.get("real_name") or "Not provided",
            "Username": user_data.get("username") or "Not provided",
            "Email": user_data.get("email") or "Not provided",
            "Recorded status": user_data.get("status") or "Not provided",
            "Original trial expiry": trial_end,
        }
        plain_details = "\n".join(f"{label}: {value}" for label, value in fields.items())
        html_details = "".join(
            f"<li><strong>{label}:</strong> {escape(str(value), quote=True)}</li>"
            for label, value in fields.items()
        )
        plain_body = f"""Existing CashOutAI trial account details

{plain_details}

New trials are currently unavailable. This message reports the existing trial record; approval and access depend on the account's current status and original expiry.

Review the existing account in the administrator panel: {self.APP_URL}

The CashOutAI Team
"""
        html_body = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Existing CashOutAI trial account</title></head>
<body style="font-family:Arial,sans-serif;line-height:1.6;color:#172033;">
  <h1>Existing trial account details</h1>
  <ul>{html_details}</ul>
  <p>New trials are currently unavailable. This message reports the existing trial record; approval and access depend on the account's current status and original expiry.</p>
  <p><a href="{self.APP_URL}">Review the existing account</a></p>
  <p>The CashOutAI Team</p>
</body>
</html>"""
        return await self.send_email(admin_email, subject, plain_body, html_body)

    async def send_approval_confirmation(
        self,
        user_email: str,
        user_name: str,
        approved: bool = True
    ) -> bool:
        """Send an account decision without creating another identity or offer."""
        if approved:
            subject = "CashOutAI — your access is approved"
            heading = "Your access is approved"
            message = "Your CashOutAI account has been approved. Open Membership in the app to see your current access and any paid-through date."
        else:
            subject = "CashOutAI — account application update"
            heading = "Account application update"
            message = "We were unable to approve your CashOutAI account at this time. Contact an administrator for the reason or to request another review of this existing account. If you have already paid, include your receipt/reference and account email so the team can match the payment."
        plain_body = f"""Hi {user_name},

{message}

Keep using your existing account; you do not need to register again. If you cannot sign in, choose Recover existing account on the sign-in screen and use your registered email address.

Open CashOutAI: {self.APP_URL}

The CashOutAI Team
"""
        html_body = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{heading}</title></head>
<body style="font-family:Arial,sans-serif;line-height:1.6;color:#172033;">
  <h1>{heading}</h1>
  <p>Hi {escape(str(user_name), quote=True)},</p>
  <p>{message}</p>
  <p>Keep using your existing account; you do not need to register again. If you cannot sign in, choose <strong>Recover existing account</strong> on the sign-in screen and use your registered email address.</p>
  <p><a href="{self.APP_URL}">Open CashOutAI</a></p>
  <p>The CashOutAI Team</p>
</body>
</html>"""
        return await self.send_email(user_email, subject, plain_body, html_body)

    async def send_trial_upgrade_email(
        self,
        user_email: str,
        user_name: str
    ) -> bool:
        """Notify an existing expired trial using the app's current catalog."""
        subject = "CashOutAI — your trial has ended"
        plain_body = f"""Hi {user_name},

Your existing CashOutAI trial has ended. Your account and community history remain in place.

Open Membership to see the current plans and payment options:
{self.MEMBERSHIP_URL}

Membership purchases are one-time payments with no automatic renewal. The team reviews the Square payment and matches it to your existing account before approving paid access. Use your CashOutAI account email at checkout; if the payment email differs, provide your account email and receipt/reference to the team.

Use the same account; you do not need to register again. If you cannot sign in, choose Recover existing account on the sign-in screen and use your registered email address. You can then open Membership to review or purchase access.

The CashOutAI Team
"""
        html_body = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>CashOutAI trial ended</title></head>
<body style="font-family:Arial,sans-serif;line-height:1.6;color:#172033;">
  <h1>Your trial has ended</h1>
  <p>Hi {escape(str(user_name), quote=True)},</p>
  <p>Your existing CashOutAI trial has ended. Your account and community history remain in place.</p>
  <p><a href="{self.MEMBERSHIP_URL}">View current membership options</a></p>
  <p>Membership purchases are one-time payments with no automatic renewal. The team reviews the Square payment and matches it to your existing account before approving paid access. Use your CashOutAI account email at checkout; if the payment email differs, provide your account email and receipt/reference to the team.</p>
  <p>Use the same account; you do not need to register again. If you cannot sign in, choose <strong>Recover existing account</strong> on the sign-in screen and use your registered email address. You can then open Membership to review or purchase access.</p>
  <p>The CashOutAI Team</p>
</body>
</html>"""
        return await self.send_email(user_email, subject, plain_body, html_body)

    async def send_trial_welcome_email(
        self,
        user_email: str,
        user_name: str,
        trial_end_date: datetime
    ) -> bool:
        """Describe a legacy trial's supplied expiry without starting a new one."""
        subject = "CashOutAI — your existing trial account"
        trial_end = self._existing_trial_end_label(trial_end_date)
        plain_body = f"""Hi {user_name},

Here are the details for your existing CashOutAI trial account.
Original trial expiry: {trial_end}

Your existing trial keeps its original expiry and access rules. New trials are currently unavailable. Open Membership in the app for your current account status and the available paid plans.

Open Membership: {self.MEMBERSHIP_URL}

Membership purchases are one-time payments with no automatic renewal. Paid access is approved after the team manually reviews the payment and matches it to your existing account.

Use the same account; you do not need to register again. If you cannot sign in, choose Recover existing account on the sign-in screen and use your registered email address.

The CashOutAI Team
"""
        html_body = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Your existing CashOutAI trial account</title></head>
<body style="font-family:Arial,sans-serif;line-height:1.6;color:#172033;">
  <h1>Your existing trial account</h1>
  <p>Hi {escape(str(user_name), quote=True)},</p>
  <p><strong>Original trial expiry:</strong> {escape(trial_end, quote=True)}</p>
  <p>Your existing trial keeps its original expiry and access rules. New trials are currently unavailable. Open Membership in the app for your current account status and the available paid plans.</p>
  <p><a href="{self.MEMBERSHIP_URL}">Open Membership</a></p>
  <p>Membership purchases are one-time payments with no automatic renewal. Paid access is approved after the team manually reviews the payment and matches it to your existing account.</p>
  <p>Use the same account; you do not need to register again. If you cannot sign in, choose <strong>Recover existing account</strong> on the sign-in screen and use your registered email address.</p>
  <p>The CashOutAI Team</p>
</body>
</html>"""
        return await self.send_email(user_email, subject, plain_body, html_body)

    async def send_general_welcome_email(
        self,
        user_email: str,
        user_name: str,
        username: str,
        membership_plan: str,
        *,
        return_outcome: bool = False
    ):
        """Send one approval welcome using the member's existing account."""
        subject = "Welcome to CashOutAI — your access is approved"
        login_url = self.APP_URL
        plain_body = f"""Welcome to CashOutAI, {user_name}!

Your access has been approved.
Membership: {membership_plan}

Sign in at {login_url} with your existing account:
Username: {username}
Email: {user_email}
Use your current password. If you cannot sign in, choose Recover existing account on the sign-in screen and use your registered email address. You do not need to register again.

Open Membership in the app to see your access status and any paid-through date.

Getting started:
1. Set up your profile and connect with the community.
2. Explore the bot rooms and practice with your simulated balance.
3. Join the conversation and share your learning progress.

Practice balances and bot examples are for training. They do not place real-money trades.

For account help, contact the ZenMillionaires team through the channel where you joined.

The CashOutAI Team
"""
        # Account fields are user-controlled. Escape only their HTML rendering;
        # plain text retains the member's exact username and email address.
        safe_name, safe_username, safe_email, safe_plan = (
            escape(str(value), quote=True)
            for value in (user_name, username, user_email, membership_plan)
        )
        html_body = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>CashOutAI access approved</title></head>
<body style="margin:0;padding:24px;background:#f4f7fa;color:#172033;font-family:Arial,sans-serif;line-height:1.6;">
  <main style="max-width:600px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;">
    <header style="padding:28px;background:#102a36;color:white;">
      <p style="margin:0;color:#79e6bd;font-weight:bold;">CashOutAI</p>
      <h1 style="margin:10px 0 0;font-size:27px;">Your access is approved</h1>
    </header>
    <section style="padding:28px;">
      <h2 style="font-size:20px;">Welcome, {safe_name}.</h2>
      <p>Your <strong>{safe_plan}</strong> access has been approved.</p>
      <p>Sign in with your existing account. You do not need to register again.</p>
      <div style="padding:18px;background:#f0f8f5;border-radius:8px;">
        <p style="margin:0;"><strong>Username:</strong> {safe_username}<br>
        <strong>Email:</strong> {safe_email}</p>
        <p>Use your current password. If you cannot sign in, choose <strong>Recover existing account</strong> on the sign-in screen and use your registered email address.</p>
        <a href="{login_url}" style="display:inline-block;background:#08765c;color:white;padding:10px 20px;border-radius:6px;text-decoration:none;">Open CashOutAI</a>
      </div>
      <p>Open <strong>Membership</strong> in the app to see your access status and any paid-through date.</p>
      <h2 style="font-size:20px;">Getting started</h2>
      <ol>
        <li>Set up your profile and connect with the community.</li>
        <li>Explore the bot rooms and practice with your simulated balance.</li>
        <li>Join the conversation and share your learning progress.</li>
      </ol>
      <p style="font-size:14px;color:#526174;">Practice balances and bot examples are for training. They do not place real-money trades.</p>
      <p>For account help, contact the ZenMillionaires team through the channel where you joined.</p>
      <p>The CashOutAI Team</p>
    </section>
  </main>
</body>
</html>"""
        return await self.send_email(user_email, subject, plain_body, html_body, return_outcome=return_outcome)

    async def send_general_welcome_email_outcome(self, user_email, user_name, username, membership_plan):
        """Existing welcome template with an auditable provider acceptance result."""
        return await self.send_general_welcome_email(
            user_email, user_name, username, membership_plan, return_outcome=True)

# Create global email service instance
email_service = EmailService()
