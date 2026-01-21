"""Retry utilities with exponential backoff."""

import asyncio
import logging
import random
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type, Union

logger = logging.getLogger(__name__)


class RetryError(Exception):
    """All retry attempts failed."""
    
    def __init__(self, message: str, last_exception: Optional[Exception] = None):
        super().__init__(message)
        self.last_exception = last_exception


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_attempts: Maximum number of attempts (including first try)
            base_delay: Initial delay in seconds before first retry
            max_delay: Maximum delay in seconds between retries
            exponential_base: Base for exponential backoff calculation
            jitter: Add random jitter to prevent thundering herd
            retryable_exceptions: Tuple of exception types that should trigger retry
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for a given attempt number.
        
        Uses exponential backoff: delay = base_delay * (exponential_base ^ attempt)
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            Delay in seconds
        """
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            # Add random jitter: 0.5 to 1.5 times the calculated delay
            jitter_factor = 0.5 + random.random()
            delay = delay * jitter_factor
        
        return delay


# Default configurations for different use cases
DEFAULT_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
)

NETWORK_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    max_delay=60.0,
    exponential_base=2.0,
)

AGGRESSIVE_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=0.5,
    max_delay=30.0,
)


async def retry_async(
    func: Callable,
    config: Optional[RetryConfig] = None,
    operation_name: str = "operation",
    **kwargs,
) -> Any:
    """
    Execute an async function with retry logic.
    
    Args:
        func: Async function to execute
        config: Retry configuration
        operation_name: Name of operation for logging
        **kwargs: Arguments to pass to the function
        
    Returns:
        Result from the function
        
    Raises:
        RetryError: If all retry attempts fail
    """
    if config is None:
        config = DEFAULT_RETRY_CONFIG
    
    last_exception = None
    
    for attempt in range(config.max_attempts):
        try:
            return await func(**kwargs)
        except config.retryable_exceptions as e:
            last_exception = e
            
            if attempt < config.max_attempts - 1:
                delay = config.calculate_delay(attempt)
                logger.warning(
                    f"{operation_name} failed (attempt {attempt + 1}/{config.max_attempts}): {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"{operation_name} failed after {config.max_attempts} attempts: {e}"
                )
    
    raise RetryError(
        f"{operation_name} failed after {config.max_attempts} attempts",
        last_exception=last_exception,
    )


def with_retry(
    config: Optional[RetryConfig] = None,
    operation_name: Optional[str] = None,
):
    """
    Decorator to add retry logic to an async function.
    
    Args:
        config: Retry configuration
        operation_name: Name of operation for logging (defaults to function name)
        
    Returns:
        Decorated function
    """
    if config is None:
        config = DEFAULT_RETRY_CONFIG
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < config.max_attempts - 1:
                        delay = config.calculate_delay(attempt)
                        logger.warning(
                            f"{op_name} failed (attempt {attempt + 1}/{config.max_attempts}): {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"{op_name} failed after {config.max_attempts} attempts: {e}"
                        )
            
            raise RetryError(
                f"{op_name} failed after {config.max_attempts} attempts",
                last_exception=last_exception,
            )
        
        return wrapper
    
    return decorator


def is_retryable_network_error(exception: Exception) -> bool:
    """
    Check if an exception is a retryable network error.
    
    Args:
        exception: The exception to check
        
    Returns:
        True if the error should be retried
    """
    import httpx
    
    # Network-related errors that are worth retrying
    retryable_types = (
        httpx.ConnectError,
        httpx.ConnectTimeout,
        httpx.ReadTimeout,
        httpx.WriteTimeout,
        httpx.PoolTimeout,
        ConnectionError,
        TimeoutError,
    )
    
    if isinstance(exception, retryable_types):
        return True
    
    # Check for specific HTTP status codes that are retryable
    if isinstance(exception, httpx.HTTPStatusError):
        status_code = exception.response.status_code
        # Retry on 429 (rate limit) and 5xx (server errors)
        return status_code == 429 or 500 <= status_code < 600
    
    return False
