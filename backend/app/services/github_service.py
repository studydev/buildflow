"""GitHub service for fetching repository data."""

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class RepoInfo:
    """Information extracted from a GitHub repository."""

    owner: str
    repo: str
    readme_content: Optional[str] = None
    description: Optional[str] = None
    topics: list = None  # List of topics
    language: Optional[str] = None  # Primary language
    languages: Optional[str] = None  # Top 10 languages, comma-separated
    stars: int = 0
    forks: int = 0
    license: Optional[str] = None

    # Additional metadata for filtering/sorting
    watchers: int = 0
    open_issues: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    pushed_at: Optional[str] = None  # Last commit date
    default_branch: Optional[str] = None

    # Contributors info
    contributors_count: int = 0
    contributors: list = None  # List of contributor logins

    # Extracted URLs from README
    demo_url: Optional[str] = None
    docs_url: Optional[str] = None
    video_url: Optional[str] = None  # YouTube or other video links
    homepage_url: Optional[str] = None  # Repo homepage setting

    def __post_init__(self):
        if self.topics is None:
            self.topics = []
        if self.contributors is None:
            self.contributors = []

    @property
    def topics_str(self) -> str:
        """Topics as comma-separated string."""
        return ", ".join(self.topics) if self.topics else ""

    @property
    def contributors_str(self) -> str:
        """Contributors as comma-separated string."""
        return ", ".join(self.contributors) if self.contributors else ""


@dataclass
class ComprehensiveRepoExtraction:
    """
    Comprehensive extraction per design.md §3.1 output_contract.

    Contains all data needed for RawExtraction document.
    """

    # Source identification
    source_url: str = ""
    source_url_hash: str = ""

    # Raw README
    raw_readme: str = ""
    readme_hash: str = ""

    # Repository metadata per design.md §3.1
    repository_metadata: Dict[str, Any] = field(default_factory=dict)
    # Expected keys: stars, forks, watchers, open_issues, open_prs,
    #                last_commit_date, created_at, topics, license, default_branch

    # Commit activity per design.md §3.1
    commit_activity: Dict[str, Any] = field(default_factory=dict)
    # Expected keys: total_commits_30d, total_commits_90d, contributors_count

    # Releases per design.md §3.1
    releases: Dict[str, Any] = field(default_factory=dict)
    # Expected keys: latest_version, release_count, last_release_date

    # Extracted URLs per design.md §3.1
    extracted_urls: Dict[str, Optional[str]] = field(default_factory=dict)
    # Expected keys: demo_url, docs_url, video_url

    # Extraction timestamp
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    github_api_version: str = "2022-11-28"


class GitHubError(Exception):
    """Base exception for GitHub service errors."""
    pass


class RepoNotFoundError(GitHubError):
    """Repository not found."""
    pass


class RateLimitError(GitHubError):
    """GitHub rate limit exceeded."""
    pass


class GitHubService:
    """Service for interacting with GitHub API."""

    # GitHub API base URL
    API_BASE_URL = "https://api.github.com"

    # Common README file names
    README_FILES = [
        "README.md",
        "readme.md",
        "Readme.md",
        "README.MD",
        "README",
        "readme",
    ]

    def __init__(self, token: Optional[str] = None):
        """
        Initialize GitHub service.

        Args:
            token: Optional GitHub personal access token for higher rate limits
        """
        self.token = token or getattr(settings, 'github_token', None)
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def headers(self) -> Dict[str, str]:
        """Get headers for GitHub API requests."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "BuildFlow-Content-Analyzer/1.0",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    async def get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers=self.headers,
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def parse_github_url(self, url: str) -> Tuple[str, str]:
        """
        Parse owner and repo from GitHub URL.

        Args:
            url: GitHub repository URL

        Returns:
            Tuple of (owner, repo)

        Raises:
            ValueError: If URL is not a valid GitHub repo URL
        """
        # Match patterns like https://github.com/owner/repo
        pattern = r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$"
        match = re.match(pattern, url.strip())

        if not match:
            raise ValueError(f"Invalid GitHub URL: {url}")

        return match.group(1), match.group(2)

    async def fetch_repo_info(self, owner: str, repo: str) -> RepoInfo:
        """
        Fetch repository information from GitHub API.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            RepoInfo with metadata

        Raises:
            RepoNotFoundError: If repository doesn't exist
            RateLimitError: If rate limit exceeded
            GitHubError: For other errors
        """
        client = await self.get_client()
        url = f"{self.API_BASE_URL}/repos/{owner}/{repo}"

        try:
            response = await client.get(url)

            if response.status_code == 404:
                raise RepoNotFoundError(f"Repository not found: {owner}/{repo}")

            if response.status_code == 403:
                remaining = response.headers.get("X-RateLimit-Remaining", "0")
                if remaining == "0":
                    raise RateLimitError("GitHub API rate limit exceeded")

            response.raise_for_status()

            data = response.json()

            return RepoInfo(
                owner=owner,
                repo=repo,
                description=data.get("description"),
                topics=data.get("topics", []),
                language=data.get("language"),
                stars=data.get("stargazers_count", 0),
                forks=data.get("forks_count", 0),
                license=data.get("license", {}).get("name") if data.get("license") else None,
                watchers=data.get("watchers_count", 0),
                open_issues=data.get("open_issues_count", 0),
                created_at=data.get("created_at"),
                updated_at=data.get("updated_at"),
                pushed_at=data.get("pushed_at"),
                default_branch=data.get("default_branch"),
                homepage_url=data.get("homepage"),
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error for {owner}/{repo}: {e}")
            raise GitHubError(f"GitHub API error: {e}")
        except httpx.RequestError as e:
            logger.error(f"Request error for {owner}/{repo}: {e}")
            raise GitHubError(f"Failed to connect to GitHub: {e}")

    async def fetch_readme(self, owner: str, repo: str) -> Optional[str]:
        """
        Fetch README content from a GitHub repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            README content as string, or None if not found

        Raises:
            RateLimitError: If rate limit exceeded
            GitHubError: For other errors
        """
        client = await self.get_client()

        # Try to get README using the API endpoint
        url = f"{self.API_BASE_URL}/repos/{owner}/{repo}/readme"

        try:
            response = await client.get(
                url,
                headers={**self.headers, "Accept": "application/vnd.github.v3.raw"},
            )

            if response.status_code == 404:
                logger.info(f"No README found for {owner}/{repo}")
                return None

            if response.status_code == 403:
                remaining = response.headers.get("X-RateLimit-Remaining", "0")
                if remaining == "0":
                    raise RateLimitError("GitHub API rate limit exceeded")

            response.raise_for_status()

            return response.text

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"GitHub API error fetching README for {owner}/{repo}: {e}")
            raise GitHubError(f"GitHub API error: {e}")
        except httpx.RequestError as e:
            logger.error(f"Request error fetching README for {owner}/{repo}: {e}")
            raise GitHubError(f"Failed to connect to GitHub: {e}")

    async def fetch_repo_with_readme(self, url: str) -> RepoInfo:
        """
        Fetch complete repository information including README.

        Args:
            url: GitHub repository URL

        Returns:
            RepoInfo with all available data including README
        """
        owner, repo = self.parse_github_url(url)

        # Fetch repo info
        repo_info = await self.fetch_repo_info(owner, repo)

        # Fetch README
        readme = await self.fetch_readme(owner, repo)
        repo_info.readme_content = readme

        # Extract URLs from README (demo, docs, video)
        if readme:
            extracted_urls = self._extract_urls_from_readme(readme)
            repo_info.demo_url = extracted_urls.get("demo_url")
            repo_info.docs_url = extracted_urls.get("docs_url")
            repo_info.video_url = extracted_urls.get("video_url")

        # Fetch top contributors (up to 10)
        contributors = await self._fetch_contributors(owner, repo)
        repo_info.contributors = contributors
        repo_info.contributors_count = len(contributors)

        # Fetch top languages (up to 10)
        repo_info.languages = await self._fetch_languages(owner, repo)

        return repo_info

    async def _fetch_contributors(
        self, owner: str, repo: str, limit: int = 10
    ) -> list:
        """
        Fetch top contributors for the repository.

        Args:
            owner: Repository owner
            repo: Repository name
            limit: Max number of contributors to fetch

        Returns:
            List of contributor logins
        """
        client = await self.get_client()
        url = f"{self.API_BASE_URL}/repos/{owner}/{repo}/contributors"

        try:
            response = await client.get(
                url,
                params={"per_page": limit, "anon": "false"}
            )

            if response.status_code in (404, 403):
                return []

            response.raise_for_status()
            contributors = response.json()

            return [c.get("login") for c in contributors if c.get("login")]

        except Exception as e:
            logger.warning(f"Failed to fetch contributors for {owner}/{repo}: {e}")
            return []

    async def _fetch_languages(
        self, owner: str, repo: str, limit: int = 10
    ) -> str:
        """
        Fetch top languages for the repository.

        Args:
            owner: Repository owner
            repo: Repository name
            limit: Max number of languages to return

        Returns:
            Comma-separated string of top languages (by bytes)
        """
        client = await self.get_client()
        url = f"{self.API_BASE_URL}/repos/{owner}/{repo}/languages"

        try:
            response = await client.get(url)

            if response.status_code in (404, 403):
                return ""

            response.raise_for_status()
            languages_data = response.json()

            # Sort by bytes (value) descending and take top N
            sorted_languages = sorted(
                languages_data.items(),
                key=lambda x: x[1],
                reverse=True
            )[:limit]

            return ", ".join(lang for lang, _ in sorted_languages)

        except Exception as e:
            logger.warning(f"Failed to fetch languages for {owner}/{repo}: {e}")
            return ""

    # =========================================================================
    # Comprehensive Extraction per design.md §3.1 (T200)
    # =========================================================================

    async def fetch_comprehensive_extraction(
        self, source_url: str
    ) -> ComprehensiveRepoExtraction:
        """
        Fetch all data required for RawExtraction per design.md §3.1.

        This is the main entry point for the Analysis Pipeline (T201).

        Args:
            source_url: GitHub repository URL

        Returns:
            ComprehensiveRepoExtraction with all extracted data

        Raises:
            RepoNotFoundError: If repository doesn't exist
            RateLimitError: If rate limit exceeded
            GitHubError: For other errors
        """
        owner, repo = self.parse_github_url(source_url)
        client = await self.get_client()

        logger.info(f"Starting comprehensive extraction for {owner}/{repo}")

        # Initialize extraction result
        extraction = ComprehensiveRepoExtraction(
            source_url=source_url,
            source_url_hash=hashlib.sha256(source_url.encode()).hexdigest(),
            extracted_at=datetime.now(timezone.utc),
        )

        # 1. Fetch repository metadata
        repo_data = await self._fetch_repo_metadata(client, owner, repo)
        extraction.repository_metadata = repo_data

        # 2. Fetch README content
        readme = await self.fetch_readme(owner, repo)
        extraction.raw_readme = readme or ""
        extraction.readme_hash = hashlib.sha256(
            extraction.raw_readme.encode()
        ).hexdigest() if extraction.raw_readme else ""

        # 3. Fetch commit activity
        commit_activity = await self._fetch_commit_activity(client, owner, repo)
        extraction.commit_activity = commit_activity

        # 4. Fetch release information
        releases = await self._fetch_releases(client, owner, repo)
        extraction.releases = releases

        # 5. Extract URLs from README
        extracted_urls = self._extract_urls_from_readme(extraction.raw_readme)
        extraction.extracted_urls = extracted_urls

        logger.info(f"Comprehensive extraction complete for {owner}/{repo}")
        return extraction

    async def _fetch_repo_metadata(
        self, client: httpx.AsyncClient, owner: str, repo: str
    ) -> Dict[str, Any]:
        """
        Fetch repository metadata per design.md §3.1 repository_metadata.

        Returns dict with: stars, forks, watchers, open_issues, open_prs,
        last_commit_date, created_at, topics, license, default_branch
        """
        url = f"{self.API_BASE_URL}/repos/{owner}/{repo}"

        try:
            response = await client.get(url)
            self._check_rate_limit(response)

            if response.status_code == 404:
                raise RepoNotFoundError(f"Repository not found: {owner}/{repo}")

            response.raise_for_status()
            data = response.json()

            # Get open PR count (separate API call)
            open_prs = await self._fetch_open_pr_count(client, owner, repo)

            # Parse last commit date from pushed_at or updated_at
            last_commit_date = data.get("pushed_at") or data.get("updated_at")

            return {
                "stars": data.get("stargazers_count", 0),
                "forks": data.get("forks_count", 0),
                "watchers": data.get("watchers_count", 0),
                "open_issues": data.get("open_issues_count", 0),
                "open_prs": open_prs,
                "last_commit_date": last_commit_date,
                "created_at": data.get("created_at"),
                "topics": data.get("topics", []),
                "license": data.get("license", {}).get("spdx_id") if data.get("license") else None,
                "default_branch": data.get("default_branch", "main"),
                "language": data.get("language"),
                "description": data.get("description"),
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch repo metadata for {owner}/{repo}: {e}")
            raise GitHubError(f"GitHub API error: {e}")

    async def _fetch_open_pr_count(
        self, client: httpx.AsyncClient, owner: str, repo: str
    ) -> int:
        """Fetch count of open pull requests."""
        url = f"{self.API_BASE_URL}/repos/{owner}/{repo}/pulls"

        try:
            response = await client.get(
                url,
                params={"state": "open", "per_page": 1}
            )
            self._check_rate_limit(response)

            if response.status_code == 404:
                return 0

            response.raise_for_status()

            # Get total count from Link header if available
            link_header = response.headers.get("Link", "")
            if "last" in link_header:
                # Parse last page number from Link header
                match = re.search(r'page=(\d+)>; rel="last"', link_header)
                if match:
                    return int(match.group(1))

            # Otherwise count items in response
            return len(response.json())

        except Exception as e:
            logger.warning(f"Failed to fetch PR count for {owner}/{repo}: {e}")
            return 0

    async def _fetch_commit_activity(
        self, client: httpx.AsyncClient, owner: str, repo: str
    ) -> Dict[str, Any]:
        """
        Fetch commit activity per design.md §3.1 commit_activity.

        Returns dict with: total_commits_30d, total_commits_90d, contributors_count
        """
        result = {
            "total_commits_30d": 0,
            "total_commits_90d": 0,
            "contributors_count": 0,
        }

        try:
            # Get commit activity using participation stats
            stats_url = f"{self.API_BASE_URL}/repos/{owner}/{repo}/stats/participation"
            response = await client.get(stats_url)
            self._check_rate_limit(response)

            if response.status_code == 200:
                data = response.json()
                all_commits = data.get("all", [])  # Weekly counts for last 52 weeks

                if all_commits:
                    # Last 4 weeks = 30 days approx
                    result["total_commits_30d"] = sum(all_commits[-4:])
                    # Last 13 weeks = 90 days approx
                    result["total_commits_90d"] = sum(all_commits[-13:])

            # Get contributors count
            contributors_url = f"{self.API_BASE_URL}/repos/{owner}/{repo}/contributors"
            response = await client.get(
                contributors_url,
                params={"per_page": 1, "anon": "true"}
            )
            self._check_rate_limit(response)

            if response.status_code == 200:
                # Parse Link header for total count
                link_header = response.headers.get("Link", "")
                if "last" in link_header:
                    match = re.search(r'page=(\d+)>; rel="last"', link_header)
                    if match:
                        result["contributors_count"] = int(match.group(1))
                else:
                    result["contributors_count"] = len(response.json())

        except Exception as e:
            logger.warning(f"Failed to fetch commit activity for {owner}/{repo}: {e}")

        return result

    async def _fetch_releases(
        self, client: httpx.AsyncClient, owner: str, repo: str
    ) -> Dict[str, Any]:
        """
        Fetch release information per design.md §3.1 releases.

        Returns dict with: latest_version, release_count, last_release_date
        """
        result = {
            "latest_version": None,
            "release_count": 0,
            "last_release_date": None,
        }

        try:
            url = f"{self.API_BASE_URL}/repos/{owner}/{repo}/releases"
            response = await client.get(url, params={"per_page": 100})
            self._check_rate_limit(response)

            if response.status_code == 200:
                releases = response.json()
                result["release_count"] = len(releases)

                if releases:
                    # Get latest non-draft, non-prerelease release
                    for release in releases:
                        if not release.get("draft") and not release.get("prerelease"):
                            result["latest_version"] = release.get("tag_name")
                            result["last_release_date"] = release.get("published_at")
                            break

                    # If all are prereleases, use the first one
                    if not result["latest_version"] and releases:
                        result["latest_version"] = releases[0].get("tag_name")
                        result["last_release_date"] = releases[0].get("published_at")

        except Exception as e:
            logger.warning(f"Failed to fetch releases for {owner}/{repo}: {e}")

        return result

    def _extract_urls_from_readme(self, readme_content: str) -> Dict[str, Optional[str]]:
        """
        Extract demo, docs, and video URLs from README content.

        Per design.md §3.1 extracted_urls.
        """
        result = {
            "demo_url": None,
            "docs_url": None,
            "video_url": None,
        }

        if not readme_content:
            return result

        # Patterns for different URL types (supports Korean labels)
        demo_patterns = [
            r'\[(?:[^]]*demo[^]]*|live|try it|playground|데모|접속|시작하기)\]\((https?://[^\)]+)\)',
            r'(?:demo|live demo|try it|데모):\s*(https?://[^\s\)]+)',
            r'https?://(?:[\w-]+\.)?(?:vercel\.app|netlify\.app|github\.io|herokuapp\.com|azurestaticapps\.net|azurewebsites\.net)[^\s\)]*',
        ]

        docs_patterns = [
            # PDF links in markdown (first match wins)
            r'\[(?:[^\]]*)\]\((https?://[^\)]+\.pdf)\)',
            # PDF URLs directly in text
            r'(https?://[^\s\)]+\.pdf)',
            # Existing patterns
            r'\[(?:documentation|docs|api docs|api reference|wiki)\]\((https?://[^\)]+)\)',
            r'(?:documentation|docs):\s*(https?://[^\s\)]+)',
            r'https?://(?:[\w-]+\.)?(?:readthedocs\.io|gitbook\.io|notion\.so|docs\.[\w-]+\.(?:com|io|dev))[^\s\)]*',
        ]

        video_patterns = [
            # YouTube short links (youtu.be) - common in Korean READMEs
            r'(https?://youtu\.be/[\w-]+)',
            # YouTube watch links
            r'(https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+)',
            # YouTube links in markdown
            r'\[(?:video|tutorial|demo video|youtube|영상|동영상)\]\((https?://[^\)]+)\)',
            r'(?:video|tutorial|watch):\s*(https?://[^\s\)]+)',
            # Vimeo
            r'(https?://(?:www\.)?vimeo\.com/[\w-]+)',
        ]

        readme_lower = readme_content.lower()

        # Find demo URL
        for pattern in demo_patterns:
            match = re.search(pattern, readme_content, re.IGNORECASE)
            if match:
                result["demo_url"] = match.group(1) if match.lastindex else match.group(0)
                break

        # Find docs URL
        for pattern in docs_patterns:
            match = re.search(pattern, readme_content, re.IGNORECASE)
            if match:
                result["docs_url"] = match.group(1) if match.lastindex else match.group(0)
                break

        # Find video URL
        for pattern in video_patterns:
            match = re.search(pattern, readme_content, re.IGNORECASE)
            if match:
                result["video_url"] = match.group(1) if match.lastindex else match.group(0)
                break

        return result

    def _check_rate_limit(self, response: httpx.Response) -> None:
        """Check if rate limit is exceeded and raise if so."""
        if response.status_code == 403:
            remaining = response.headers.get("X-RateLimit-Remaining", "1")
            if remaining == "0":
                reset_time = response.headers.get("X-RateLimit-Reset", "")
                raise RateLimitError(
                    f"GitHub API rate limit exceeded. Resets at: {reset_time}"
                )


# Singleton instance
_service: Optional[GitHubService] = None


def get_github_service() -> GitHubService:
    """Get the GitHub service singleton."""
    global _service
    if _service is None:
        _service = GitHubService()
    return _service
