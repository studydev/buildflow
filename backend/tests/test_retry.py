"""Tests for retry utilities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.retry import (
    DEFAULT_RETRY_CONFIG,
    NETWORK_RETRY_CONFIG,
    RetryConfig,
    RetryError,
    is_retryable_network_error,
    retry_async,
    with_retry,
)


class TestRetryConfig:
    """Tests for RetryConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RetryConfig()

        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=0.5,
            max_delay=30.0,
            exponential_base=3.0,
            jitter=False,
        )

        assert config.max_attempts == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.exponential_base == 3.0
        assert config.jitter is False

    def test_calculate_delay_without_jitter(self):
        """Test delay calculation without jitter."""
        config = RetryConfig(
            base_delay=1.0,
            exponential_base=2.0,
            jitter=False,
        )

        # delay = base_delay * (exponential_base ^ attempt)
        assert config.calculate_delay(0) == 1.0   # 1 * 2^0 = 1
        assert config.calculate_delay(1) == 2.0   # 1 * 2^1 = 2
        assert config.calculate_delay(2) == 4.0   # 1 * 2^2 = 4
        assert config.calculate_delay(3) == 8.0   # 1 * 2^3 = 8

    def test_calculate_delay_respects_max(self):
        """Test delay calculation respects max_delay."""
        config = RetryConfig(
            base_delay=1.0,
            exponential_base=2.0,
            max_delay=5.0,
            jitter=False,
        )

        # Should cap at max_delay
        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(3) == 5.0  # Would be 8, capped at 5
        assert config.calculate_delay(5) == 5.0  # Would be 32, capped at 5

    def test_calculate_delay_with_jitter(self):
        """Test delay calculation with jitter."""
        config = RetryConfig(
            base_delay=1.0,
            exponential_base=2.0,
            jitter=True,
        )

        # With jitter, delay should vary but be within range
        delays = [config.calculate_delay(1) for _ in range(10)]

        # All delays should be between 0.5 * 2 and 1.5 * 2 (1 to 3)
        for delay in delays:
            assert 1.0 <= delay <= 3.0


class TestRetryAsync:
    """Tests for retry_async function."""

    @pytest.mark.asyncio
    async def test_success_on_first_try(self):
        """Test function succeeds on first attempt."""
        mock_func = AsyncMock(return_value="success")

        result = await retry_async(mock_func, operation_name="test")

        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_success_after_retry(self):
        """Test function succeeds after retries."""
        mock_func = AsyncMock(side_effect=[Exception("fail"), Exception("fail"), "success"])
        config = RetryConfig(max_attempts=3, base_delay=0.01, jitter=False)

        result = await retry_async(mock_func, config=config, operation_name="test")

        assert result == "success"
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_failure_after_max_attempts(self):
        """Test raises RetryError after max attempts."""
        mock_func = AsyncMock(side_effect=Exception("always fails"))
        config = RetryConfig(max_attempts=3, base_delay=0.01, jitter=False)

        with pytest.raises(RetryError) as exc_info:
            await retry_async(mock_func, config=config, operation_name="test_op")

        assert "test_op failed after 3 attempts" in str(exc_info.value)
        assert exc_info.value.last_exception is not None
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_non_retryable_exception(self):
        """Test non-retryable exceptions are raised immediately."""
        class CustomError(Exception):
            pass

        mock_func = AsyncMock(side_effect=CustomError("not retryable"))
        config = RetryConfig(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(ValueError,),  # Only retry ValueError
        )

        with pytest.raises(CustomError):
            await retry_async(mock_func, config=config, operation_name="test")

        assert mock_func.call_count == 1


class TestWithRetryDecorator:
    """Tests for with_retry decorator."""

    @pytest.mark.asyncio
    async def test_decorator_success(self):
        """Test decorated function succeeds."""
        call_count = 0

        @with_retry(config=RetryConfig(base_delay=0.01))
        async def my_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await my_func()

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_decorator_retries(self):
        """Test decorated function retries on failure."""
        call_count = 0

        @with_retry(config=RetryConfig(max_attempts=3, base_delay=0.01))
        async def my_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("fail")
            return "success"

        result = await my_func()

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_decorator_raises_after_max_attempts(self):
        """Test decorated function raises RetryError after max attempts."""
        @with_retry(
            config=RetryConfig(max_attempts=2, base_delay=0.01),
            operation_name="my_operation",
        )
        async def my_func():
            raise Exception("always fails")

        with pytest.raises(RetryError) as exc_info:
            await my_func()

        assert "my_operation failed after 2 attempts" in str(exc_info.value)


class TestIsRetryableNetworkError:
    """Tests for is_retryable_network_error function."""

    def test_connection_error_is_retryable(self):
        """Test ConnectionError is retryable."""
        assert is_retryable_network_error(ConnectionError()) is True

    def test_timeout_error_is_retryable(self):
        """Test TimeoutError is retryable."""
        assert is_retryable_network_error(TimeoutError()) is True

    def test_value_error_is_not_retryable(self):
        """Test ValueError is not retryable."""
        assert is_retryable_network_error(ValueError("test")) is False

    def test_httpx_connect_error_is_retryable(self):
        """Test httpx ConnectError is retryable."""
        import httpx
        assert is_retryable_network_error(httpx.ConnectError("test")) is True

    def test_httpx_500_error_is_retryable(self):
        """Test httpx 500 error is retryable."""
        import httpx
        response = MagicMock()
        response.status_code = 500
        error = httpx.HTTPStatusError("error", request=MagicMock(), response=response)
        assert is_retryable_network_error(error) is True

    def test_httpx_429_error_is_retryable(self):
        """Test httpx 429 (rate limit) error is retryable."""
        import httpx
        response = MagicMock()
        response.status_code = 429
        error = httpx.HTTPStatusError("error", request=MagicMock(), response=response)
        assert is_retryable_network_error(error) is True

    def test_httpx_404_error_is_not_retryable(self):
        """Test httpx 404 error is not retryable."""
        import httpx
        response = MagicMock()
        response.status_code = 404
        error = httpx.HTTPStatusError("error", request=MagicMock(), response=response)
        assert is_retryable_network_error(error) is False


class TestPredefinedConfigs:
    """Tests for predefined retry configurations."""

    def test_default_config_values(self):
        """Test DEFAULT_RETRY_CONFIG values."""
        assert DEFAULT_RETRY_CONFIG.max_attempts == 3
        assert DEFAULT_RETRY_CONFIG.base_delay == 1.0
        assert DEFAULT_RETRY_CONFIG.max_delay == 30.0

    def test_network_config_values(self):
        """Test NETWORK_RETRY_CONFIG values."""
        assert NETWORK_RETRY_CONFIG.max_attempts == 3
        assert NETWORK_RETRY_CONFIG.base_delay == 2.0
        assert NETWORK_RETRY_CONFIG.max_delay == 60.0
