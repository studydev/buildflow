"""Auth service - handles OTP and JWT token operations."""

import logging
from typing import Optional
from uuid import uuid4

from app.core.security import (
    TokenPair,
    create_token_pair,
    verify_access_token,
    verify_refresh_token,
)
from app.models.user import User
from app.repositories.user_repo import UserRepository, get_user_repository
from app.services.otp_store import OTPStore, get_otp_store, OTP_TTL_MINUTES

logger = logging.getLogger(__name__)


class AuthService:
    """Service for authentication operations."""
    
    def __init__(
        self,
        otp_store: Optional[OTPStore] = None,
        user_repo: Optional[UserRepository] = None,
    ) -> None:
        """Initialize auth service with dependencies."""
        self._otp_store = otp_store
        self._user_repo = user_repo
    
    @property
    def otp_store(self) -> OTPStore:
        """Lazy load OTP store."""
        if self._otp_store is None:
            self._otp_store = get_otp_store()
        return self._otp_store
    
    @property
    def user_repo(self) -> UserRepository:
        """Lazy load user repository."""
        if self._user_repo is None:
            self._user_repo = get_user_repository()
        return self._user_repo
    
    def request_otp(self, email: str) -> tuple[bool, str, int, str]:
        """
        Request an OTP for the given email.
        
        Args:
            email: Email address
        
        Returns:
            Tuple of (is_new, masked_email, expires_in_seconds, otp_code)
        """
        code, is_new = self.otp_store.create(email)
        
        # In production, send email here
        # For MVP, just log the code (development only!)
        if is_new:
            logger.info("OTP for %s: %s (dev only - remove in production!)", email, code)
        
        # Mask email for response
        masked = self._mask_email(email)
        
        return is_new, masked, OTP_TTL_MINUTES * 60, code
    
    async def verify_otp(self, email: str, code: str) -> tuple[bool, str, Optional[TokenPair]]:
        """
        Verify OTP and return JWT tokens if valid.
        
        Args:
            email: Email address
            code: OTP code
        
        Returns:
            Tuple of (success, message, tokens or None)
        """
        # Verify OTP
        success, message = self.otp_store.verify(email, code)
        
        if not success:
            return False, message, None
        
        # Get or create user
        # Note: For MVP without Cosmos, we'll create tokens directly
        # In production, this would create/get user from DB
        try:
            user, created = await self.user_repo.get_or_create_by_email(email)
            
            if created:
                logger.info("Created new user: %s", user.id)
            else:
                # Update last login
                await self.user_repo.update_last_login(user.id)
            
            user_id = user.id
            role = user.role.value
        except Exception as e:
            # Fallback for MVP when Cosmos is not available
            # In development mode, give contributor role for testing
            logger.warning("User repo unavailable, using mock user: %s", e)
            user_id = str(uuid4())
            role = "contributor"  # Dev mode: allow testing contributor features
        
        # Generate tokens
        refresh_jti = str(uuid4())  # Track refresh token
        tokens = create_token_pair(
            user_id=user_id,
            email=email,
            role=role,
            refresh_jti=refresh_jti,
        )
        
        # Clean up OTP
        self.otp_store.delete(email)
        
        return True, "Authentication successful", tokens
    
    def refresh_tokens(self, refresh_token: str) -> tuple[bool, str, Optional[TokenPair]]:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: JWT refresh token
        
        Returns:
            Tuple of (success, message, new tokens or None)
        """
        try:
            payload = verify_refresh_token(refresh_token)
        except Exception as e:
            logger.warning("Invalid refresh token: %s", e)
            return False, "Invalid or expired refresh token", None
        
        # Generate new tokens (rotate refresh token)
        new_refresh_jti = str(uuid4())
        tokens = create_token_pair(
            user_id=payload.sub,
            email=payload.email,
            role=payload.role,
            refresh_jti=new_refresh_jti,
        )
        
        # In production, invalidate old refresh token here
        # (store used jti in Redis/DB to prevent reuse)
        
        return True, "Tokens refreshed", tokens
    
    @staticmethod
    def _mask_email(email: str) -> str:
        """Mask email for privacy (e.g., t***@example.com)."""
        parts = email.split("@")
        if len(parts) != 2:
            return email
        
        local = parts[0]
        domain = parts[1]
        
        if len(local) <= 2:
            masked_local = local[0] + "*"
        else:
            masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
        
        return f"{masked_local}@{domain}"


# Singleton instance
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Get the AuthService singleton."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
