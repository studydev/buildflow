"""API v1 package.

Registers all API routers for the BuildFlow API.
"""

from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.assistant import router as assistant_router
from app.api.v1.pipelines import history_router as pipeline_history_router
from app.api.v1.pipelines import router as pipelines_router
from app.api.v1.search import router as search_router

# Create main v1 router
api_router = APIRouter()

# Register pipeline routes (Milestone 1)
api_router.include_router(pipelines_router, prefix="/pipelines", tags=["pipelines"])
api_router.include_router(pipeline_history_router, prefix="/content", tags=["pipelines"])

# Register search routes (Milestone 4)
api_router.include_router(search_router, prefix="/search", tags=["search"])

# Register assistant routes (Milestone 7)
api_router.include_router(assistant_router, prefix="/assistant", tags=["assistant"])

# Register admin routes (Milestone 8)
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])

# Export routers for main.py
__all__ = ["api_router", "pipelines_router", "pipeline_history_router", "search_router", "assistant_router", "admin_router"]
