"""Service layer for Analysis Requests."""

import logging
from typing import List, Optional, Tuple

from app.models.analysis import AnalysisRequest
from app.models.enums import AnalysisStatus
from app.repositories.analysis_repo import AnalysisRequestRepository, get_analysis_repo
from app.schemas.analysis import AnalysisRequestCreate

logger = logging.getLogger(__name__)


class AnalysisService:
    """Service for managing analysis requests."""

    # GitHub allowlist for SSRF protection
    ALLOWED_DOMAINS = ["github.com"]

    def __init__(self, repo: Optional[AnalysisRequestRepository] = None):
        """Initialize with optional repository."""
        self._repo = repo

    @property
    def repo(self) -> AnalysisRequestRepository:
        """Get the repository instance."""
        if self._repo is None:
            self._repo = get_analysis_repo()
        return self._repo

    def validate_url(self, url: str) -> Tuple[bool, Optional[str]]:
        """
        Validate the source URL for SSRF protection.

        Returns:
            Tuple of (is_valid, error_message)
        """
        import urllib.parse

        try:
            parsed = urllib.parse.urlparse(url)

            # Check scheme
            if parsed.scheme not in ("http", "https"):
                return False, "URL must use http or https scheme"

            # Check domain against allowlist
            domain = parsed.netloc.lower()
            if not any(domain == allowed or domain.endswith(f".{allowed}")
                      for allowed in self.ALLOWED_DOMAINS):
                return False, f"Domain not allowed. Only {', '.join(self.ALLOWED_DOMAINS)} are supported"

            # Check for private IPs (basic SSRF protection)
            # Note: In production, use more comprehensive IP validation
            if any(ip in domain for ip in ["127.0.0.1", "localhost", "0.0.0.0"]):
                return False, "Invalid domain"

            return True, None

        except Exception as e:
            logger.warning(f"URL validation error: {e}")
            return False, "Invalid URL format"

    async def create_request(
        self,
        user_id: str,
        data: AnalysisRequestCreate,
        check_duplicate: bool = True,
    ) -> Tuple[AnalysisRequest, bool]:
        """
        Create a new analysis request.

        Args:
            user_id: The user ID making the request
            data: The request data with source URL
            check_duplicate: Whether to check for existing requests

        Returns:
            Tuple of (request, is_duplicate)
            If duplicate exists within 24h, returns existing request and True
        """
        source_url = data.source_url.strip().rstrip("/")

        # Check for duplicate requests
        if check_duplicate:
            try:
                existing = await self.repo.find_duplicate(
                    user_id=user_id,
                    source_url=source_url,
                    within_hours=24,
                )
                if existing:
                    logger.info(
                        f"Duplicate request found for user {user_id}, url: {source_url}"
                    )
                    return existing, True
            except Exception as e:
                logger.warning(f"Error checking for duplicates: {e}")
                # Continue with creation even if duplicate check fails

        # Create new request
        request = AnalysisRequest(
            user_id=user_id,
            source_url=source_url,
        )

        try:
            created = await self.repo.create(request)
            logger.info(f"Created analysis request {created.id} for user {user_id}")
            return created, False
        except Exception as e:
            logger.error(f"Failed to create analysis request: {e}")
            raise

    async def get_request(
        self,
        request_id: str,
        user_id: str,
    ) -> Optional[AnalysisRequest]:
        """Get an analysis request by ID for a specific user."""
        try:
            return await self.repo.get_by_id(request_id, user_id)
        except Exception as e:
            logger.error(f"Failed to get analysis request {request_id}: {e}")
            return None

    async def list_user_requests(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        status: Optional[AnalysisStatus] = None,
    ) -> Tuple[List[AnalysisRequest], int]:
        """
        List analysis requests for a user.

        Returns:
            Tuple of (requests, total_count)
        """
        try:
            return await self.repo.list_by_user(
                user_id=user_id,
                page=page,
                limit=limit,
                status=status,
            )
        except Exception as e:
            logger.error(f"Failed to list requests for user {user_id}: {e}")
            return [], 0

    async def update_status(
        self,
        request_id: str,
        user_id: str,
        status: AnalysisStatus,
        message: Optional[str] = None,
        progress: Optional[int] = None,
    ) -> Optional[AnalysisRequest]:
        """Update the status of an analysis request."""
        try:
            return await self.repo.update_status(
                request_id=request_id,
                user_id=user_id,
                status=status,
                message=message,
                progress=progress,
            )
        except Exception as e:
            logger.error(f"Failed to update status for request {request_id}: {e}")
            return None

    async def cancel_request(
        self,
        request_id: str,
        user_id: str,
    ) -> Optional[AnalysisRequest]:
        """Cancel a pending analysis request."""
        request = await self.get_request(request_id, user_id)
        if not request:
            return None

        # Only pending or in-progress requests can be cancelled
        if request.status in (AnalysisStatus.COMPLETED, AnalysisStatus.FAILED):
            logger.warning(
                f"Cannot cancel request {request_id} with status {request.status}"
            )
            return request

        return await self.update_status(
            request_id=request_id,
            user_id=user_id,
            status=AnalysisStatus.FAILED,
            message="Cancelled by user",
        )

    async def delete_request(
        self,
        request_id: str,
        user_id: str,
    ) -> bool:
        """Delete an analysis request."""
        try:
            return await self.repo.delete(request_id, user_id)
        except Exception as e:
            logger.error(f"Failed to delete request {request_id}: {e}")
            return False


# Singleton instance
_service: Optional[AnalysisService] = None


def get_analysis_service() -> AnalysisService:
    """Get the analysis service singleton."""
    global _service
    if _service is None:
        _service = AnalysisService()
    return _service
