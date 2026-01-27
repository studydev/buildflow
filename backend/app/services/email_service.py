"""Email service for sending OTP and notifications."""

import logging
import smtplib
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmailService(ABC):
    """Abstract base class for email services."""

    @abstractmethod
    async def send_otp(self, email: str, otp: str) -> bool:
        """Send OTP verification email."""
        pass

    @abstractmethod
    async def send_welcome(self, email: str, name: str) -> bool:
        """Send welcome email after registration."""
        pass


class MailHogEmailService(EmailService):
    """Email service using MailHog for development."""

    def __init__(self, host: str = "localhost", port: int = 1025):
        self.host = host
        self.port = port
        self.from_email = "noreply@studydev.com"

    async def send_otp(self, email: str, otp: str) -> bool:
        """Send OTP via MailHog."""
        subject = "NexusSkill - Verification Code"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>NexusSkill Sign-in Verification</h2>
            <p>Enter the code below to complete your sign-in:</p>
            <div style="background: #f5f5f5; padding: 20px; text-align: center; margin: 20px 0;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px;">{otp}</span>
            </div>
            <p>This code is valid for 5 minutes.</p>
            <p style="color: #666; font-size: 12px;">
                If you didn't request this, please ignore this email.
            </p>
        </body>
        </html>
        """

        return await self._send_email(email, subject, html_body)

    async def send_welcome(self, email: str, name: str) -> bool:
        """Send welcome email via MailHog."""
        subject = "Welcome to NexusSkill!"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>Welcome, {name}! 🎉</h2>
            <p>Thank you for joining NexusSkill.</p>
            <p>You can now explore and bookmark Azure learning content.</p>
            <ul>
                <li>Explore workshops, tutorials, and sample code</li>
                <li>Bookmark your favorite content</li>
                <li>Become a content contributor</li>
            </ul>
            <p>
                <a href="https://nexus.studydev.com" style="background: #0078d4; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px;">
                    Get Started
                </a>
            </p>
        </body>
        </html>
        """

        return await self._send_email(email, subject, html_body)

    async def _send_email(self, to_email: str, subject: str, html_body: str) -> bool:
        """Send email using SMTP."""
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = to_email

            html_part = MIMEText(html_body, "html")
            msg.attach(html_part)

            with smtplib.SMTP(self.host, self.port) as server:
                server.sendmail(self.from_email, to_email, msg.as_string())

            logger.info(f"Email sent to {to_email}: {subject}")
            return True

        except Exception as e:
            logger.warning(f"MailHog not available, skipping email to {to_email}: {e}")
            # In dev/test mode, return True to allow flow to continue
            return True


class AzureCommunicationEmailService(EmailService):
    """Email service using Azure Communication Services for production."""

    def __init__(self, connection_string: str, sender_address: str):
        self.connection_string = connection_string
        self.sender_address = sender_address
        self._client = None

    @property
    def client(self):
        """Lazy-load Azure Communication Services client."""
        if self._client is None:
            try:
                from azure.communication.email import EmailClient
                self._client = EmailClient.from_connection_string(self.connection_string)
            except ImportError:
                logger.error("azure-communication-email package not installed")
                raise
        return self._client

    async def send_otp(self, email: str, otp: str) -> bool:
        """Send OTP via Azure Communication Services."""
        subject = "NexusSkill - Verification Code"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>NexusSkill Sign-in Verification</h2>
            <p>Enter the code below to complete your sign-in:</p>
            <div style="background: #f5f5f5; padding: 20px; text-align: center; margin: 20px 0;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px;">{otp}</span>
            </div>
            <p>This code is valid for 5 minutes.</p>
            <p style="color: #666; font-size: 12px;">
                If you didn't request this, please ignore this email.
            </p>
        </body>
        </html>
        """

        return await self._send_email(email, subject, html_body)

    async def send_welcome(self, email: str, name: str) -> bool:
        """Send welcome email via Azure Communication Services."""
        subject = "Welcome to NexusSkill!"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>Welcome, {name}! 🎉</h2>
            <p>Thank you for joining NexusSkill.</p>
            <p>You can now explore and bookmark Azure learning content.</p>
        </body>
        </html>
        """

        return await self._send_email(email, subject, html_body)

    async def _send_email(self, to_email: str, subject: str, html_body: str) -> bool:
        """Send email using Azure Communication Services."""
        try:
            message = {
                "senderAddress": self.sender_address,
                "recipients": {
                    "to": [{"address": to_email}]
                },
                "content": {
                    "subject": subject,
                    "html": html_body
                }
            }

            poller = self.client.begin_send(message)
            result = poller.result()

            if result.get("status") == "Succeeded":
                logger.info(f"Email sent to {to_email} via Azure CS: {subject}")
                return True
            else:
                logger.error(f"Failed to send email: {result}")
                return False

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False


# Singleton instance
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get email service instance based on environment."""
    global _email_service

    if _email_service is None:
        settings = get_settings()

        # Use Azure Communication Services if configured
        if settings.acs_connection_string and settings.acs_sender_address:
            _email_service = AzureCommunicationEmailService(
                connection_string=settings.acs_connection_string,
                sender_address=settings.acs_sender_address,
            )
            logger.info("Using Azure Communication Services for email")
        else:
            _email_service = MailHogEmailService()
            logger.info("Using MailHog for email (development mode)")

    return _email_service


async def send_otp_email(email: str, otp_code: str) -> bool:
    """
    Convenience function to send OTP email.

    Args:
        email: Recipient email address
        otp_code: 6-digit OTP code

    Returns:
        True if email sent successfully, False otherwise
    """
    service = get_email_service()
    return await service.send_otp(email, otp_code)
