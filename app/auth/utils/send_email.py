# utils/send_email.py
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import os
from dotenv import load_dotenv

# Load .env
load_dotenv(dotenv_path="app/auth/.env")


SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")

def send_otp_email(to_email: str, otp: str):
    if not SENDGRID_API_KEY or not FROM_EMAIL:
        raise ValueError("SendGrid API key or FROM_EMAIL is not loaded from .env")

    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=to_email,
        subject="Your Login OTP",
        html_content=f"""
        <p>Your OTP is:</p>
        <h2>{otp}</h2>
        <p>This OTP expires in 5 minutes.</p>
        """
    )

    sg = SendGridAPIClient(SENDGRID_API_KEY)
    sg.send(message)
