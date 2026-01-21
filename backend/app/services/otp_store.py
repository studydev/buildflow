"""OTP (One-Time Password) storage for email verification.

For MVP, uses in-memory storage with TTL-based expiration.
For production, consider using Redis or Cosmos DB with TTL.
"""

import logging
import secrets
import string
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# OTP Configuration
OTP_LENGTH = 6
OTP_TTL_MINUTES = 5
MAX_ATTEMPTS = 3
RATE_LIMIT_MINUTES = 1  # Min time between OTP requests for same email


@dataclass
class OTPEntry:
    """OTP entry with metadata."""
    
    code: str
    email: str
    created_at: datetime
    expires_at: datetime
    attempts: int = 0
    verified: bool = False


@dataclass
class OTPStore:
    """In-memory OTP storage with thread safety.
    
    Note: This is suitable for single-instance MVP.
    For multi-instance production, use Redis or Cosmos DB.
    """
    
    _store: Dict[str, OTPEntry] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)
    
    def generate_otp(self) -> str:
        """Generate a random 6-digit OTP code."""
        return "".join(secrets.choice(string.digits) for _ in range(OTP_LENGTH))
    
    def create(self, email: str) -> tuple[str, bool]:
        """
        Create a new OTP for the given email.
        
        Args:
            email: Email address to create OTP for
        
        Returns:
            Tuple of (otp_code, is_new). is_new is False if rate limited.
        """
        email_lower = email.lower()
        now = datetime.now(timezone.utc)
        
        with self._lock:
            # Check rate limiting
            existing = self._store.get(email_lower)
            if existing and not existing.verified:
                time_since_created = (now - existing.created_at).total_seconds()
                if time_since_created < RATE_LIMIT_MINUTES * 60:
                    logger.warning(
                        "OTP rate limited for %s (%.0fs since last)",
                        email_lower,
                        time_since_created,
                    )
                    # Return existing code for idempotency
                    return existing.code, False
            
            # Generate new OTP
            code = self.generate_otp()
            entry = OTPEntry(
                code=code,
                email=email_lower,
                created_at=now,
                expires_at=now + timedelta(minutes=OTP_TTL_MINUTES),
            )
            
            self._store[email_lower] = entry
            logger.info("Created OTP for %s", email_lower)
            
            return code, True
    
    def verify(self, email: str, code: str) -> tuple[bool, str]:
        """
        Verify an OTP code.
        
        Args:
            email: Email address
            code: OTP code to verify
        
        Returns:
            Tuple of (success, message)
        """
        email_lower = email.lower()
        now = datetime.now(timezone.utc)
        
        with self._lock:
            entry = self._store.get(email_lower)
            
            if not entry:
                return False, "No OTP found for this email"
            
            if entry.verified:
                return False, "OTP already used"
            
            if entry.expires_at < now:
                # Clean up expired entry
                del self._store[email_lower]
                return False, "OTP has expired"
            
            if entry.attempts >= MAX_ATTEMPTS:
                # Too many failed attempts
                del self._store[email_lower]
                return False, "Too many failed attempts"
            
            if not secrets.compare_digest(entry.code, code):
                # Wrong code
                entry.attempts += 1
                remaining = MAX_ATTEMPTS - entry.attempts
                logger.warning(
                    "Invalid OTP attempt for %s (%d remaining)",
                    email_lower,
                    remaining,
                )
                return False, f"Invalid OTP code ({remaining} attempts remaining)"
            
            # Success - mark as verified
            entry.verified = True
            logger.info("OTP verified for %s", email_lower)
            return True, "OTP verified successfully"
    
    def delete(self, email: str) -> bool:
        """
        Delete OTP entry for email.
        
        Args:
            email: Email address
        
        Returns:
            True if deleted, False if not found
        """
        email_lower = email.lower()
        
        with self._lock:
            if email_lower in self._store:
                del self._store[email_lower]
                return True
            return False
    
    def get(self, email: str) -> Optional[OTPEntry]:
        """Get OTP entry for email (for testing)."""
        with self._lock:
            return self._store.get(email.lower())
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.
        
        Returns:
            Number of entries removed
        """
        now = datetime.now(timezone.utc)
        removed = 0
        
        with self._lock:
            expired_emails = [
                email
                for email, entry in self._store.items()
                if entry.expires_at < now
            ]
            
            for email in expired_emails:
                del self._store[email]
                removed += 1
        
        if removed > 0:
            logger.info("Cleaned up %d expired OTP entries", removed)
        
        return removed
    
    def clear(self) -> None:
        """Clear all entries (for testing)."""
        with self._lock:
            self._store.clear()


# Singleton instance
_otp_store: Optional[OTPStore] = None


def get_otp_store() -> OTPStore:
    """Get the OTPStore singleton."""
    global _otp_store
    if _otp_store is None:
        _otp_store = OTPStore()
    return _otp_store
