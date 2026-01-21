"""Rate limiting utilities for protecting API endpoints.

This module provides in-memory rate limiting functionality with:
- Configurable time windows and request limits
- Sliding window algorithm for accurate rate limiting
- Per-key tracking (e.g., per email, per IP)
- Automatic cleanup of expired entries
"""

import time
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from fastapi import HTTPException, status


@dataclass
class RateLimitEntry:
    """Tracks rate limit data for a single key."""
    
    timestamps: list = field(default_factory=list)
    blocked_until: Optional[float] = None


class RateLimiter:
    """
    In-memory rate limiter with sliding window algorithm.
    
    Tracks request timestamps and limits requests based on:
    - max_requests: Maximum requests allowed in the window
    - window_seconds: Time window in seconds
    - block_seconds: How long to block after limit is exceeded
    
    Thread-safe implementation using locks.
    """
    
    def __init__(
        self,
        max_requests: int = 5,
        window_seconds: int = 900,  # 15 minutes
        block_seconds: int = 900,   # 15 minutes
    ):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed per window
            window_seconds: Size of the sliding window in seconds
            block_seconds: Duration to block after limit exceeded
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        self._entries: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._lock = threading.Lock()
    
    def _cleanup_old_timestamps(self, entry: RateLimitEntry, now: float) -> None:
        """Remove timestamps outside the current window."""
        cutoff = now - self.window_seconds
        entry.timestamps = [ts for ts in entry.timestamps if ts > cutoff]
    
    def is_allowed(self, key: str) -> bool:
        """
        Check if a request is allowed for the given key.
        
        Args:
            key: Unique identifier (e.g., email, IP address)
            
        Returns:
            True if request is allowed, False if rate limited
        """
        now = time.time()
        
        with self._lock:
            entry = self._entries[key]
            
            # Check if currently blocked
            if entry.blocked_until and now < entry.blocked_until:
                return False
            
            # Clear block if it has expired
            if entry.blocked_until and now >= entry.blocked_until:
                entry.blocked_until = None
                entry.timestamps = []
            
            # Cleanup old timestamps
            self._cleanup_old_timestamps(entry, now)
            
            # Check if limit exceeded
            if len(entry.timestamps) >= self.max_requests:
                entry.blocked_until = now + self.block_seconds
                return False
            
            # Record this request
            entry.timestamps.append(now)
            return True
    
    def get_remaining(self, key: str) -> int:
        """
        Get remaining requests allowed for the key.
        
        Args:
            key: Unique identifier
            
        Returns:
            Number of remaining requests allowed
        """
        now = time.time()
        
        with self._lock:
            entry = self._entries[key]
            
            if entry.blocked_until and now < entry.blocked_until:
                return 0
            
            self._cleanup_old_timestamps(entry, now)
            return max(0, self.max_requests - len(entry.timestamps))
    
    def get_retry_after(self, key: str) -> Optional[int]:
        """
        Get seconds until rate limit resets.
        
        Args:
            key: Unique identifier
            
        Returns:
            Seconds until reset, or None if not limited
        """
        now = time.time()
        
        with self._lock:
            entry = self._entries[key]
            
            if entry.blocked_until and now < entry.blocked_until:
                return int(entry.blocked_until - now) + 1
            
            self._cleanup_old_timestamps(entry, now)
            
            if len(entry.timestamps) >= self.max_requests:
                # Time until oldest timestamp expires
                oldest = min(entry.timestamps)
                return int(self.window_seconds - (now - oldest)) + 1
            
            return None
    
    def reset(self, key: str) -> None:
        """
        Reset rate limit for a key.
        
        Args:
            key: Unique identifier to reset
        """
        with self._lock:
            if key in self._entries:
                del self._entries[key]
    
    def clear(self) -> None:
        """Clear all rate limit entries."""
        with self._lock:
            self._entries.clear()


# Global rate limiters for auth endpoints
_otp_request_limiter: Optional[RateLimiter] = None
_otp_verify_limiter: Optional[RateLimiter] = None


def get_otp_request_limiter() -> RateLimiter:
    """
    Get the rate limiter for OTP request endpoint.
    
    Limit: 3 requests per email per 15 minutes
    """
    global _otp_request_limiter
    if _otp_request_limiter is None:
        _otp_request_limiter = RateLimiter(
            max_requests=3,
            window_seconds=900,  # 15 minutes
            block_seconds=900,
        )
    return _otp_request_limiter


def get_otp_verify_limiter() -> RateLimiter:
    """
    Get the rate limiter for OTP verify endpoint.
    
    Limit: 5 verify attempts per email per 15 minutes
    """
    global _otp_verify_limiter
    if _otp_verify_limiter is None:
        _otp_verify_limiter = RateLimiter(
            max_requests=5,
            window_seconds=900,  # 15 minutes
            block_seconds=900,
        )
    return _otp_verify_limiter


def check_rate_limit(limiter: RateLimiter, key: str, error_message: str = "Too many requests") -> None:
    """
    Check rate limit and raise HTTPException if exceeded.
    
    Args:
        limiter: The rate limiter to use
        key: Unique identifier for rate limiting
        error_message: Message to include in error response
        
    Raises:
        HTTPException: 429 Too Many Requests if limit exceeded
    """
    if not limiter.is_allowed(key):
        retry_after = limiter.get_retry_after(key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_message,
            headers={"Retry-After": str(retry_after)} if retry_after else None,
        )


def reset_rate_limiters() -> None:
    """Reset all rate limiters. Useful for testing."""
    global _otp_request_limiter, _otp_verify_limiter
    if _otp_request_limiter:
        _otp_request_limiter.clear()
    if _otp_verify_limiter:
        _otp_verify_limiter.clear()
