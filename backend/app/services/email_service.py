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
        self.from_email = "noreply@buildflow.dev"

    async def send_otp(self, email: str, otp: str) -> bool:
        """Send OTP via MailHog."""
        subject = "BuildFlow - 인증 코드"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>BuildFlow 로그인 인증</h2>
            <p>아래 코드를 입력하여 로그인을 완료하세요:</p>
            <div style="background: #f5f5f5; padding: 20px; text-align: center; margin: 20px 0;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px;">{otp}</span>
            </div>
            <p>이 코드는 5분간 유효합니다.</p>
            <p style="color: #666; font-size: 12px;">
                본인이 요청하지 않은 경우, 이 이메일을 무시하세요.
            </p>
        </body>
        </html>
        """

        return await self._send_email(email, subject, html_body)

    async def send_welcome(self, email: str, name: str) -> bool:
        """Send welcome email via MailHog."""
        subject = "BuildFlow에 오신 것을 환영합니다!"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>환영합니다, {name}님! 🎉</h2>
            <p>BuildFlow에 가입해 주셔서 감사합니다.</p>
            <p>이제 Azure 학습 콘텐츠를 탐색하고 북마크할 수 있습니다.</p>
            <ul>
                <li>워크샵, 튜토리얼, 샘플 코드 탐색</li>
                <li>관심 콘텐츠 북마크</li>
                <li>콘텐츠 기여자로 참여</li>
            </ul>
            <p>
                <a href="https://buildflow.dev" style="background: #0078d4; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px;">
                    시작하기
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
        subject = "BuildFlow - 인증 코드"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>BuildFlow 로그인 인증</h2>
            <p>아래 코드를 입력하여 로그인을 완료하세요:</p>
            <div style="background: #f5f5f5; padding: 20px; text-align: center; margin: 20px 0;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px;">{otp}</span>
            </div>
            <p>이 코드는 5분간 유효합니다.</p>
            <p style="color: #666; font-size: 12px;">
                본인이 요청하지 않은 경우, 이 이메일을 무시하세요.
            </p>
        </body>
        </html>
        """

        return await self._send_email(email, subject, html_body)

    async def send_welcome(self, email: str, name: str) -> bool:
        """Send welcome email via Azure Communication Services."""
        subject = "BuildFlow에 오신 것을 환영합니다!"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>환영합니다, {name}님! 🎉</h2>
            <p>BuildFlow에 가입해 주셔서 감사합니다.</p>
            <p>이제 Azure 학습 콘텐츠를 탐색하고 북마크할 수 있습니다.</p>
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
