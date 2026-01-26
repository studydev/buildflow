"""FastAPI application factory and main entry point."""

import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.core.exceptions import AppException
from app.core.middleware import CorrelationIDMiddleware
from app.schemas import (
    APIErrorResponse,
    APIResponse,
    ErrorBody,
    ErrorDetail,
    HealthData,
    Meta,
)

settings = get_settings()
logger = logging.getLogger(__name__)


# =============================================================================
# Exception Handlers (Constitution v1.0.0 Compliant)
# =============================================================================


def get_correlation_id(request: Request) -> str:
    """Extract or generate correlation ID from request."""
    return getattr(request.state, "correlation_id", None) or request.headers.get(
        "X-Correlation-ID", str(uuid4())
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """
    Handle custom AppException and subclasses.

    Returns Constitution-compliant error response:
    {
        "success": false,
        "error": {"code": "...", "message": "...", "details": [...]},
        "meta": {"timestamp": "...", "correlationId": "..."}
    }
    """
    correlation_id = get_correlation_id(request)

    response = APIErrorResponse(
        error=ErrorBody(
            code=exc.code,
            message=exc.message,
            details=exc.details,
        ),
        meta=Meta.create(correlation_id),
    )

    logger.warning(
        "AppException: %s - %s",
        exc.code,
        exc.message,
        extra={"correlation_id": correlation_id, "status_code": exc.status_code},
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(),
        headers={"X-Correlation-ID": correlation_id},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handle Pydantic/FastAPI validation errors.

    Converts validation errors to Constitution-compliant format.
    """
    correlation_id = get_correlation_id(request)

    details = [
        ErrorDetail(
            field=".".join(str(loc) for loc in error["loc"]),
            issue=error["msg"],
        )
        for error in exc.errors()
    ]

    response = APIErrorResponse(
        error=ErrorBody(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            details=details,
        ),
        meta=Meta.create(correlation_id),
    )

    return JSONResponse(
        status_code=422,
        content=response.model_dump(),
        headers={"X-Correlation-ID": correlation_id},
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """
    Handle standard HTTP exceptions (404, 405, etc.).

    Converts to Constitution-compliant format.
    """
    correlation_id = get_correlation_id(request)

    # Map status codes to error codes
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_ERROR",
    }

    response = APIErrorResponse(
        error=ErrorBody(
            code=code_map.get(exc.status_code, "HTTP_ERROR"),
            message=str(exc.detail),
            details=[],
        ),
        meta=Meta.create(correlation_id),
    )

    # Merge exception headers with correlation ID
    headers = {"X-Correlation-ID": correlation_id}
    if exc.headers:
        headers.update(exc.headers)

    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(),
        headers=headers,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions.

    Logs the full error but returns a safe message to the client.
    """
    correlation_id = get_correlation_id(request)

    logger.exception(
        "Unhandled exception",
        extra={"correlation_id": correlation_id},
    )

    response = APIErrorResponse(
        error=ErrorBody(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            details=[],
        ),
        meta=Meta.create(correlation_id),
    )

    return JSONResponse(
        status_code=500,
        content=response.model_dump(),
        headers={"X-Correlation-ID": correlation_id},
    )


# =============================================================================
# Application Factory
# =============================================================================


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url=f"{settings.api_v1_prefix}/docs",
        redoc_url=f"{settings.api_v1_prefix}/redoc",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    )

    # Register exception handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Correlation ID middleware (must be added first to wrap all requests)
    app.add_middleware(CorrelationIDMiddleware)

    # CORS middleware for frontend (uses module-level settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID"],
    )

    # Register routes
    register_routes(app)

    return app


def register_routes(app: FastAPI) -> None:
    """Register all API routes."""

    # Import and include API routers
    from app.api.v1.analysis import router as analysis_router
    from app.api.v1.auth import router as auth_router
    from app.api.v1.content import router as content_router
    from app.api.v1.search import router as search_router
    from app.api.v1.users import router as users_router

    app.include_router(auth_router, prefix=settings.api_v1_prefix)
    app.include_router(users_router, prefix=settings.api_v1_prefix)
    app.include_router(content_router, prefix=settings.api_v1_prefix)
    app.include_router(analysis_router, prefix=settings.api_v1_prefix)
    app.include_router(search_router, prefix=f"{settings.api_v1_prefix}/search")

    @app.get(
        f"{settings.api_v1_prefix}/health",
        response_model=APIResponse,
        tags=["Health"],
        summary="Health Check",
        description="Returns the health status of the API.",
    )
    async def health_check(request: Request) -> JSONResponse:
        """
        Health check endpoint.

        Returns 200 OK with {"status": "healthy"} when the API is running.
        Used by Azure Container Apps for liveness/readiness probes.
        """
        # Correlation ID is set by middleware
        correlation_id = request.state.correlation_id

        response = APIResponse(
            success=True,
            data=HealthData(status="healthy"),
            meta=Meta.create(correlation_id),
        )

        # Note: X-Correlation-ID header is added by middleware
        return JSONResponse(
            content=response.model_dump(),
        )

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        """Root redirect info."""
        return {
            "message": "BuildFlow API",
            "docs": f"{settings.api_v1_prefix}/docs",
            "health": f"{settings.api_v1_prefix}/health",
        }

    @app.get("/health", include_in_schema=False)
    async def root_health_check(request: Request) -> JSONResponse:
        """
        Root-level health check endpoint for Azure Container Apps probes.
        """
        correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
        response = APIResponse(
            success=True,
            data=HealthData(status="healthy"),
            meta=Meta.create(correlation_id),
        )
        return JSONResponse(content=response.model_dump())

    # Test endpoint to verify error handling (development only)
    if settings.debug:
        from app.core.exceptions import NotFoundError, ValidationError

        @app.get(
            f"{settings.api_v1_prefix}/test/error/validation",
            tags=["Test"],
            include_in_schema=settings.debug,
        )
        async def test_validation_error():
            """Test endpoint to trigger validation error."""
            raise ValidationError(
                message="Test validation error",
                details=[
                    ErrorDetail(field="email", issue="Invalid email format"),
                    ErrorDetail(field="name", issue="Name is required"),
                ],
            )

        @app.get(
            f"{settings.api_v1_prefix}/test/error/notfound",
            tags=["Test"],
            include_in_schema=settings.debug,
        )
        async def test_not_found_error():
            """Test endpoint to trigger not found error."""
            raise NotFoundError(resource="TestResource")


# =============================================================================
# Application Instance
# =============================================================================

app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
