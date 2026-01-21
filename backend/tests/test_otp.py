"""Test OTP storage."""

import time
from datetime import datetime, timedelta, timezone

import pytest

from app.services.otp_store import OTPStore, get_otp_store, OTP_LENGTH, MAX_ATTEMPTS


class TestOTPGeneration:
    """Tests for OTP code generation."""

    def test_generate_otp_length(self):
        """Generated OTP should have correct length."""
        store = OTPStore()
        code = store.generate_otp()
        
        assert len(code) == OTP_LENGTH

    def test_generate_otp_digits_only(self):
        """Generated OTP should only contain digits."""
        store = OTPStore()
        code = store.generate_otp()
        
        assert code.isdigit()

    def test_generate_otp_unique(self):
        """Generated OTPs should be unique (probabilistically)."""
        store = OTPStore()
        codes = [store.generate_otp() for _ in range(100)]
        
        # With 6 digits, collision in 100 codes is very unlikely
        assert len(set(codes)) > 90


class TestOTPCreate:
    """Tests for OTP creation."""

    def test_create_otp_returns_code(self):
        """Should return OTP code and is_new=True."""
        store = OTPStore()
        code, is_new = store.create("test@example.com")
        
        assert len(code) == OTP_LENGTH
        assert is_new is True

    def test_create_otp_stores_entry(self):
        """Should store OTP entry."""
        store = OTPStore()
        code, _ = store.create("test@example.com")
        
        entry = store.get("test@example.com")
        assert entry is not None
        assert entry.code == code
        assert entry.email == "test@example.com"

    def test_create_otp_case_insensitive(self):
        """Email should be case insensitive."""
        store = OTPStore()
        code1, _ = store.create("Test@Example.COM")
        
        entry = store.get("test@example.com")
        assert entry is not None
        assert entry.code == code1

    def test_create_otp_rate_limited(self):
        """Should rate limit repeated requests."""
        store = OTPStore()
        code1, is_new1 = store.create("test@example.com")
        code2, is_new2 = store.create("test@example.com")
        
        # Second request should return same code
        assert code1 == code2
        assert is_new1 is True
        assert is_new2 is False  # Rate limited


class TestOTPVerify:
    """Tests for OTP verification."""

    def test_verify_correct_code(self):
        """Should verify correct code."""
        store = OTPStore()
        code, _ = store.create("test@example.com")
        
        success, message = store.verify("test@example.com", code)
        
        assert success is True
        assert "verified" in message.lower()

    def test_verify_wrong_code(self):
        """Should reject wrong code."""
        store = OTPStore()
        store.create("test@example.com")
        
        success, message = store.verify("test@example.com", "000000")
        
        assert success is False
        assert "invalid" in message.lower()

    def test_verify_no_otp(self):
        """Should reject when no OTP exists."""
        store = OTPStore()
        
        success, message = store.verify("unknown@example.com", "123456")
        
        assert success is False
        assert "no otp" in message.lower()

    def test_verify_already_used(self):
        """Should reject already used OTP."""
        store = OTPStore()
        code, _ = store.create("test@example.com")
        
        # First verification
        store.verify("test@example.com", code)
        
        # Second verification should fail
        success, message = store.verify("test@example.com", code)
        
        assert success is False
        assert "already used" in message.lower()

    def test_verify_max_attempts(self):
        """Should lock out after max attempts."""
        store = OTPStore()
        code, _ = store.create("test@example.com")
        
        # Use up all attempts
        for i in range(MAX_ATTEMPTS):
            success, message = store.verify("test@example.com", "000000")
            assert success is False
        
        # Next attempt should fail with "too many attempts" or be deleted
        success, message = store.verify("test@example.com", code)
        assert success is False  # Should fail even with correct code

    def test_verify_expired(self):
        """Should reject expired OTP."""
        store = OTPStore()
        store.create("test@example.com")
        
        # Manually expire the entry
        entry = store.get("test@example.com")
        entry.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        
        success, message = store.verify("test@example.com", entry.code)
        
        assert success is False
        assert "expired" in message.lower()


class TestOTPDelete:
    """Tests for OTP deletion."""

    def test_delete_existing(self):
        """Should delete existing entry."""
        store = OTPStore()
        store.create("test@example.com")
        
        result = store.delete("test@example.com")
        
        assert result is True
        assert store.get("test@example.com") is None

    def test_delete_nonexistent(self):
        """Should return False for nonexistent entry."""
        store = OTPStore()
        
        result = store.delete("unknown@example.com")
        
        assert result is False


class TestOTPCleanup:
    """Tests for expired OTP cleanup."""

    def test_cleanup_removes_expired(self):
        """Should remove expired entries."""
        store = OTPStore()
        store.create("expired@example.com")
        store.create("valid@example.com")
        
        # Expire one entry
        entry = store.get("expired@example.com")
        entry.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        
        removed = store.cleanup_expired()
        
        assert removed == 1
        assert store.get("expired@example.com") is None
        assert store.get("valid@example.com") is not None

    def test_clear(self):
        """Should clear all entries."""
        store = OTPStore()
        store.create("test1@example.com")
        store.create("test2@example.com")
        
        store.clear()
        
        assert store.get("test1@example.com") is None
        assert store.get("test2@example.com") is None


class TestOTPSingleton:
    """Tests for OTPStore singleton."""

    def test_get_otp_store_returns_singleton(self):
        """Should return same instance."""
        store1 = get_otp_store()
        store2 = get_otp_store()
        
        assert store1 is store2
