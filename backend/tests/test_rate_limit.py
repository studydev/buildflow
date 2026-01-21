"""Tests for rate limiting functionality."""

import time

import pytest
from fastapi import HTTPException

from app.core.rate_limit import (
    RateLimiter,
    check_rate_limit,
    get_otp_request_limiter,
    get_otp_verify_limiter,
    reset_rate_limiters,
)


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_allows_within_limit(self):
        """Requests within limit should be allowed."""
        limiter = RateLimiter(max_requests=3, window_seconds=60, block_seconds=60)

        assert limiter.is_allowed("test@example.com") is True
        assert limiter.is_allowed("test@example.com") is True
        assert limiter.is_allowed("test@example.com") is True

    def test_blocks_after_limit(self):
        """Requests after limit should be blocked."""
        limiter = RateLimiter(max_requests=3, window_seconds=60, block_seconds=60)

        # Use up the limit
        for _ in range(3):
            limiter.is_allowed("test@example.com")

        # 4th request should be blocked
        assert limiter.is_allowed("test@example.com") is False

    def test_different_keys_tracked_separately(self):
        """Different keys should have separate limits."""
        limiter = RateLimiter(max_requests=2, window_seconds=60, block_seconds=60)

        # Use up limit for key1
        limiter.is_allowed("key1")
        limiter.is_allowed("key1")

        # key1 should be blocked, key2 should be allowed
        assert limiter.is_allowed("key1") is False
        assert limiter.is_allowed("key2") is True

    def test_get_remaining(self):
        """Should return remaining allowed requests."""
        limiter = RateLimiter(max_requests=3, window_seconds=60, block_seconds=60)

        assert limiter.get_remaining("test") == 3

        limiter.is_allowed("test")
        assert limiter.get_remaining("test") == 2

        limiter.is_allowed("test")
        limiter.is_allowed("test")
        assert limiter.get_remaining("test") == 0

    def test_get_retry_after_returns_none_when_not_limited(self):
        """Should return None when not rate limited."""
        limiter = RateLimiter(max_requests=3, window_seconds=60, block_seconds=60)

        limiter.is_allowed("test")
        assert limiter.get_retry_after("test") is None

    def test_get_retry_after_returns_seconds_when_blocked(self):
        """Should return seconds until unblock when rate limited."""
        limiter = RateLimiter(max_requests=2, window_seconds=60, block_seconds=30)

        # Exhaust limit and trigger block
        limiter.is_allowed("test")
        limiter.is_allowed("test")
        limiter.is_allowed("test")  # This triggers block

        retry_after = limiter.get_retry_after("test")
        assert retry_after is not None
        assert 0 < retry_after <= 31

    def test_reset_key(self):
        """Reset should clear limits for a specific key."""
        limiter = RateLimiter(max_requests=2, window_seconds=60, block_seconds=60)

        # Use up limit
        limiter.is_allowed("test")
        limiter.is_allowed("test")
        assert limiter.is_allowed("test") is False

        # Reset and try again
        limiter.reset("test")
        assert limiter.is_allowed("test") is True

    def test_clear_all(self):
        """Clear should reset all limits."""
        limiter = RateLimiter(max_requests=1, window_seconds=60, block_seconds=60)

        limiter.is_allowed("key1")
        limiter.is_allowed("key2")
        assert limiter.is_allowed("key1") is False
        assert limiter.is_allowed("key2") is False

        limiter.clear()
        assert limiter.is_allowed("key1") is True
        assert limiter.is_allowed("key2") is True

    def test_window_expiry(self):
        """Old timestamps should be cleaned up."""
        limiter = RateLimiter(max_requests=2, window_seconds=1, block_seconds=1)

        limiter.is_allowed("test")
        limiter.is_allowed("test")
        assert limiter.is_allowed("test") is False

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again after window expires and block ends
        assert limiter.is_allowed("test") is True


class TestCheckRateLimit:
    """Tests for check_rate_limit helper function."""

    def test_does_not_raise_when_allowed(self):
        """Should not raise when request is allowed."""
        limiter = RateLimiter(max_requests=5, window_seconds=60, block_seconds=60)

        # Should not raise
        check_rate_limit(limiter, "test", "Test error")

    def test_raises_429_when_blocked(self):
        """Should raise 429 HTTPException when rate limited."""
        limiter = RateLimiter(max_requests=1, window_seconds=60, block_seconds=60)

        # Use up the limit
        check_rate_limit(limiter, "test", "Test error")

        # Should raise 429
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(limiter, "test", "Test error")

        assert exc_info.value.status_code == 429
        assert exc_info.value.detail == "Test error"

    def test_includes_retry_after_header(self):
        """Should include Retry-After header when blocked."""
        limiter = RateLimiter(max_requests=1, window_seconds=60, block_seconds=30)

        check_rate_limit(limiter, "test", "Error")

        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(limiter, "test", "Error")

        assert exc_info.value.headers is not None
        assert "Retry-After" in exc_info.value.headers


class TestOTPLimiters:
    """Tests for OTP-specific rate limiters."""

    def setup_method(self):
        """Reset rate limiters before each test."""
        reset_rate_limiters()

    def test_otp_request_limiter_exists(self):
        """OTP request limiter should be available."""
        limiter = get_otp_request_limiter()
        assert limiter is not None
        assert limiter.max_requests == 3

    def test_otp_verify_limiter_exists(self):
        """OTP verify limiter should be available."""
        limiter = get_otp_verify_limiter()
        assert limiter is not None
        assert limiter.max_requests == 5

    def test_otp_request_limiter_is_singleton(self):
        """OTP request limiter should return the same instance."""
        limiter1 = get_otp_request_limiter()
        limiter2 = get_otp_request_limiter()
        assert limiter1 is limiter2

    def test_otp_verify_limiter_is_singleton(self):
        """OTP verify limiter should return the same instance."""
        limiter1 = get_otp_verify_limiter()
        limiter2 = get_otp_verify_limiter()
        assert limiter1 is limiter2
