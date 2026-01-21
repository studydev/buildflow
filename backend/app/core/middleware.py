"""Middleware components for the application."""

import logging
import time
from typing import Callable
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle correlation IDs for request tracing.
    
    - Extracts X-Correlation-ID from request headers if present
    - Generates a new UUID if not present
    - Stores correlation_id in request.state for access in handlers
    - Adds X-Correlation-ID to response headers
    - Logs request/response with correlation_id for distributed tracing
    """

    HEADER_NAME = "X-Correlation-ID"

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Process the request with correlation ID tracking."""
        # Extract or generate correlation ID
        correlation_id = request.headers.get(self.HEADER_NAME) or str(uuid4())
        
        # Store in request state for access by handlers and exception handlers
        request.state.correlation_id = correlation_id
        
        # Add to logging context
        start_time = time.perf_counter()
        
        # Log incoming request
        logger.info(
            "Request started: %s %s",
            request.method,
            request.url.path,
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "query": str(request.query_params) if request.query_params else None,
            },
        )
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        # Add correlation ID to response headers
        response.headers[self.HEADER_NAME] = correlation_id
        
        # Log completed request
        logger.info(
            "Request completed: %s %s -> %d (%.2fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Additional request logging middleware for debugging.
    
    Logs detailed request information in debug mode.
    """

    def __init__(self, app: ASGIApp, debug: bool = False) -> None:
        super().__init__(app)
        self.debug = debug

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Log request details if in debug mode."""
        if self.debug:
            correlation_id = getattr(request.state, "correlation_id", "unknown")
            logger.debug(
                "Request details: headers=%s, client=%s",
                dict(request.headers),
                request.client,
                extra={"correlation_id": correlation_id},
            )
        
        return await call_next(request)
