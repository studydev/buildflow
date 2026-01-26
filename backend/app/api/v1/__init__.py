"""API v1 package.

Registers all API routers for the BuildFlow API.
"""

from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.assistant import router as assistant_router
from app.api.v1.search import router as search_router

# Create main v1 router
api_router = APIRouter()

# Register search routes (Milestone 4)
api_router.include_router(search_router, prefix="/search", tags=["search"])

# Register assistant routes (Milestone 7)
api_router.include_router(assistant_router, prefix="/assistant", tags=["assistant"])

# Register admin routes (Milestone 8)
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])

# Export routers for main.py
__all__ = ["api_router", "search_router", "assistant_router", "admin_router"]
