import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add the backend directory to the Python path
backend_dir = Path('/app/backend')
sys.path.append(str(backend_dir))

# Load environment variables from .env file
load_dotenv(backend_dir / '.env')

# Print environment variables
print("Environment variables:")
print(f"MAIL_USERNAME: {os.environ.get('MAIL_USERNAME')}")
print(f"MAIL_PASSWORD: {os.environ.get('MAIL_PASSWORD')}")
print(f"MAIL_FROM: {os.environ.get('MAIL_FROM')}")
print(f"MAIL_PORT: {os.environ.get('MAIL_PORT')}")
print(f"MAIL_SERVER: {os.environ.get('MAIL_SERVER')}")
print(f"MAIL_TLS: {os.environ.get('MAIL_TLS')}")

# Try to import the email_service module
try:
    from email_service import EmailService
    print("\nSuccessfully imported EmailService class")
    
    # Try to initialize the email service
    try:
        email_service = EmailService()
        print("Successfully initialized email_service")
        print(f"email_service.mail_username: {email_service.mail_username}")
        print(f"email_service.mail_server: {email_service.mail_server}")
        print(f"email_service.mail_port: {email_service.mail_port}")
        print(f"email_service.mail_tls: {email_service.mail_tls}")
    except Exception as e:
        print(f"Error initializing email_service: {e}")
except ImportError as e:
    print(f"Error importing EmailService: {e}")