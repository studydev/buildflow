"""Service layer for Analysis Requests."""

import logging
import urllib.parse
from typing import List, Optional, Tuple

import httpx

from app.models.analysis import AnalysisRequest
from app.models.enums import AnalysisStatus
from app.repositories.analysis_repo import AnalysisRequestRepository, get_analysis_repo
from app.schemas.analysis import AnalysisRequestCreate

logger = logging.getLogger(__name__)


class AnalysisService:
    """Service for managing analysis requests."""

    # GitHub allowlist for SSRF protection (final destination)
    ALLOWED_DOMAINS = ["github.com"]
    
    # Domains allowed to redirect to GitHub
    REDIRECT_DOMAINS = ["aka.ms", "go.microsoft.com", "bit.ly", "t.co", "tinyurl.com"]
    
    # Maximum redirects to follow
    MAX_REDIRECTS = 5

    def __init__(self, repo: Optional[AnalysisRequestRepository] = None):
        """Initialize with optional repository."""
        self._repo = repo

    @property
    def repo(self) -> AnalysisRequestRepository:
        """Get the repository instance."""
        if self._repo is None:
            self._repo = get_analysis_repo()
        return self._repo

    async def resolve_redirect_url(self, url: str) -> Tuple[str, Optional[str]]:
        """
        Resolve redirect URLs to get the final destination.
        
        Args:
            url: The URL to resolve (may be a redirect URL)
            
        Returns:
            Tuple of (resolved_url, error_message)
        """
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc.lower()
            
            # If already a GitHub URL, return as-is
            if any(domain == allowed or domain.endswith(f".{allowed}")
                   for allowed in self.ALLOWED_DOMAINS):
                return url, None
            
            # Check if it's a known redirect domain
            is_redirect_domain = any(
                domain == rd or domain.endswith(f".{rd}")
                for rd in self.REDIRECT_DOMAINS
            )
            
            if not is_redirect_domain:
                return url, None  # Not a redirect domain, validate normally
            
            # Follow redirects to find the final URL
            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                max_redirects=self.MAX_REDIRECTS
            ) as client:
                response = await client.head(url)
                final_url = str(response.url)
                logger.info(f"Resolved redirect: {url} -> {final_url}")
                return final_url, None
                
        except httpx.TooManyRedirects:
            return url, "Too many redirects"
        except httpx.TimeoutException:
            return url, "Request timeout while resolving redirect"
        except Exception as e:
            logger.warning(f"Error resolving redirect URL {url}: {e}")
            return url, f"Failed to resolve redirect: {str(e)}"

    def validate_url(self, url: str) -> Tuple[bool, Optional[str]]:
        """
        Validate the source URL for SSRF protection (sync version).
        For redirect URLs, use validate_url_async instead.

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            parsed = urllib.parse.urlparse(url)

            # Check scheme
            if parsed.scheme not in ("http", "https"):
                return False, "URL must use http or https scheme"

            # Check domain against allowlist
            domain = parsed.netloc.lower()
            if not any(domain == allowed or domain.endswith(f".{allowed}")
                      for allowed in self.ALLOWED_DOMAINS):
                # Check if it's a known redirect domain
                if any(domain == rd or domain.endswith(f".{rd}")
                       for rd in self.REDIRECT_DOMAINS):
                    return True, None  # Allow redirect domains
                return False, f"Domain not allowed. Only {', '.join(self.ALLOWED_DOMAINS)} are supported"

            # Check for private IPs (basic SSRF protection)
            if any(ip in domain for ip in ["127.0.0.1", "localhost", "0.0.0.0"]):
                return False, "Invalid domain"

            return True, None

        except Exception as e:
            logger.warning(f"URL validation error: {e}")
            return False, "Invalid URL format"
    
    async def validate_and_resolve_url(self, url: str) -> Tuple[bool, str, Optional[str]]:
        """
        Validate URL and resolve redirects if needed.
        
        Returns:
            Tuple of (is_valid, resolved_url, error_message)
        """
        # First, basic validation
        is_valid, error = self.validate_url(url)
        if not is_valid:
            return False, url, error
        
        # Try to resolve redirect
        resolved_url, resolve_error = await self.resolve_redirect_url(url)
        if resolve_error:
            logger.warning(f"Redirect resolution warning: {resolve_error}")
            # Continue with original URL if resolution fails
            resolved_url = url
        
        # Validate the resolved URL (must be GitHub)
        parsed = urllib.parse.urlparse(resolved_url)
        domain = parsed.netloc.lower()
        
        if not any(domain == allowed or domain.endswith(f".{allowed}")
                   for allowed in self.ALLOWED_DOMAINS):
            return False, resolved_url, f"Final URL must be a GitHub repository. Got: {domain}"
        
        # Check for valid GitHub repo pattern
        import re
        pattern = r"https?://github\.com/[^/]+/[^/]+"
        if not re.match(pattern, resolved_url):
            return False, resolved_url, "URL must point to a valid GitHub repository"
        
        return True, resolved_url, None

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
