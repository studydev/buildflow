"""Content service for business logic."""

import logging
from typing import Optional

from app.models.analysis import AnalysisResult
from app.models.content import Content
from app.models.enums import ContentStatus, ContentType
from app.repositories.content_repo import ContentRepository, get_content_repo
from app.schemas.content import (
    ContentCreateRequest,
    ContentListResponse,
    ContentResponse,
    ContentUpdateRequest,
)

logger = logging.getLogger(__name__)


class ContentService:
    """Service for content-related business logic."""

    def __init__(self, repo: Optional[ContentRepository] = None):
        """Initialize with content repository."""
        self._repo = repo

    @property
    def repo(self) -> ContentRepository:
        """Lazy load repository."""
        if self._repo is None:
            self._repo = get_content_repo()
        return self._repo

    async def create_from_analysis(
        self,
        contributor_id: str,
        source_url: str,
        result: AnalysisResult,
    ) -> Content:
        """
        Create Content from analysis result.

        Args:
            contributor_id: User ID of the contributor
            source_url: GitHub repository URL
            result: Extracted metadata from analysis

        Returns:
            Created Content
        """
        from datetime import datetime

        # Map content type from analysis result
        content_type = self._map_content_type(result.content_type)

        # Use Korean title if available, otherwise use English title
        title = result.title_kr or result.title or "Untitled Content"
        description = result.description_kr or result.description or ""

        # Determine icon based on content type
        icon_map = {
            ContentType.WORKSHOP: "🎓",
            ContentType.TUTORIAL: "📚",
            ContentType.LAB: "🔬",
            ContentType.SAMPLE: "💻",
            ContentType.TEMPLATE: "📋",
            ContentType.SOLUTION_IDEA: "💡",
            ContentType.OTHER: "📄",
        }
        icon = icon_map.get(content_type, "📄")

        # Create content with PUBLISHED status so it shows immediately
        content = Content(
            contributor_id=contributor_id,
            title=title,
            description=description,
            content_type=content_type,
            status=ContentStatus.PUBLISHED,
            source_url=source_url,
            source_type="github",
            categories=result.categories,
            level=result.level or "beginner",
            duration_minutes=result.duration_minutes or 60,
            icon=icon,
            analysis_status="completed",
            analysis_result=result.to_dict(),
            published_at=datetime.utcnow(),
        )

        # Persist to database
        created = await self.repo.create(content)
        logger.info(f"Created content {created.id} from analysis for {source_url}")

        return created

    async def create(
        self,
        contributor_id: str,
        data: ContentCreateRequest,
    ) -> Content:
        """
        Create new content manually.

        Args:
            contributor_id: User ID of the contributor
            data: Content creation data

        Returns:
            Created Content
        """
        content_type = self._map_content_type(data.content_type)

        content = Content(
            contributor_id=contributor_id,
            title=data.title,
            description=data.description,
            content_type=content_type,
            status=ContentStatus.DRAFT,
            source_url=data.source_url,
            source_type="github",
            categories=data.categories,
            level=data.level,
            duration_minutes=data.duration_minutes,
            thumbnail_url=data.thumbnail_url,
            icon=data.icon,
        )

        try:
            created = await self.repo.create(content)
            logger.info(f"Created content {created.id} for contributor {contributor_id}")
            return created
        except Exception as e:
            logger.warning(f"Failed to persist content to Cosmos, returning unpersisted: {e}")
            # For development without Cosmos
            return content

    async def update(
        self,
        content_id: str,
        data: ContentUpdateRequest,
    ) -> Content:
        """
        Update existing content.

        Args:
            content_id: Content unique identifier
            data: Content update data

        Returns:
            Updated Content
        """
        # Get existing content
        existing = await self.repo.get_by_id(content_id)
        if existing is None:
            raise ValueError(f"Content {content_id} not found")

        # Update fields if provided
        if data.title is not None:
            existing.title = data.title
        if data.description is not None:
            existing.description = data.description
        if data.categories is not None:
            existing.categories = data.categories
        if data.level is not None:
            existing.level = data.level
        if data.duration_minutes is not None:
            existing.duration_minutes = data.duration_minutes
        if data.thumbnail_url is not None:
            existing.thumbnail_url = data.thumbnail_url
        if data.icon is not None:
            existing.icon = data.icon

        try:
            updated = await self.repo.update(existing)
            logger.info(f"Updated content {content_id}")
            return updated
        except Exception as e:
            logger.warning(f"Failed to persist content update to Cosmos: {e}")
            return existing

    async def update_status(
        self,
        content_id: str,
        new_status: str,
    ) -> Content:
        """
        Update content status (publish/archive).

        Args:
            content_id: Content unique identifier
            new_status: New status value ('published' or 'archived')

        Returns:
            Updated Content
        """
        from datetime import datetime

        # Get existing content
        existing = await self.repo.get_by_id(content_id)
        if existing is None:
            raise ValueError(f"Content {content_id} not found")

        # Map status string to enum
        status_mapping = {
            "published": ContentStatus.PUBLISHED,
            "archived": ContentStatus.ARCHIVED,
        }

        existing.status = status_mapping[new_status]

        # Set published_at timestamp when publishing
        if new_status == "published" and existing.published_at is None:
            existing.published_at = datetime.utcnow()

        try:
            updated = await self.repo.update(existing)
            logger.info(f"Updated content {content_id} status to {new_status}")
            return updated
        except Exception as e:
            logger.warning(f"Failed to persist status update to Cosmos: {e}")
            return existing

    def _map_content_type(self, type_str: Optional[str]) -> ContentType:
        """
        Map analysis result content type to ContentType enum.

        Args:
            type_str: Content type string from analysis

        Returns:
            ContentType enum value
        """
        if not type_str:
            return ContentType.TUTORIAL

        type_lower = type_str.lower()

        mapping = {
            "workshop": ContentType.WORKSHOP,
            "tutorial": ContentType.TUTORIAL,
            "sample": ContentType.SAMPLE,
            "demo": ContentType.SAMPLE,  # Map demo to sample
            "documentation": ContentType.OTHER,  # Map documentation to other
            "tool": ContentType.OTHER,  # Map tool to other
            "lab": ContentType.LAB,
            "template": ContentType.TEMPLATE,
            "solution_idea": ContentType.SOLUTION_IDEA,
        }

        return mapping.get(type_lower, ContentType.TUTORIAL)

    async def list_published(
        self,
        page: int = 1,
        limit: int = 20,
        category: Optional[str] = None,
    ) -> ContentListResponse:
        """
        List published content with pagination.

        Args:
            page: Page number (1-indexed)
            limit: Items per page
            category: Filter by category

        Returns:
            Paginated content list response
        """
        from app.db.cosmos import is_mock_mode

        offset = (page - 1) * limit

        # In mock mode, combine mock data with dynamically created content
        if is_mock_mode():
            contents, total = self._get_combined_mock_content(limit, offset, category)
        else:
            try:
                contents, total = await self.repo.list_published(
                    limit=limit,
                    offset=offset,
                    category=category,
                )
            except Exception as e:
                logger.warning(f"Failed to fetch from Cosmos, using mock data: {e}")
                contents, total = self._get_combined_mock_content(limit, offset, category)

        items = [
            ContentResponse(
                id=c.id,
                title=c.title,
                description=c.description,
                content_type=c.content_type.value if isinstance(c.content_type, ContentType) else c.content_type,
                categories=c.categories,
                level=c.level,
                duration_minutes=c.duration_minutes,
                thumbnail_url=c.thumbnail_url,
                icon=c.icon,
                source_url=c.source_url,
                view_count=c.view_count,
                bookmark_count=c.bookmark_count,
                published_at=c.published_at,
            )
            for c in contents
        ]

        return ContentListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            has_more=(page * limit) < total,
        )

    async def search(
        self,
        query: str,
        page: int = 1,
        limit: int = 20,
    ) -> ContentListResponse:
        """
        Search content by text.

        Args:
            query: Search query
            page: Page number
            limit: Items per page

        Returns:
            Paginated search results
        """
        from app.db.cosmos import is_mock_mode

        offset = (page - 1) * limit

        # In mock mode, use combined search
        if is_mock_mode():
            contents, total = self._search_mock_content(query, limit, offset)
        else:
            try:
                contents, total = await self.repo.search(
                    query_text=query,
                    limit=limit,
                    offset=offset,
                )
            except Exception as e:
                logger.warning(f"Failed to search Cosmos, using mock data: {e}")
                contents, total = self._search_mock_content(query, limit, offset)

        items = [
            ContentResponse(
                id=c.id,
                title=c.title,
                description=c.description,
                content_type=c.content_type.value if isinstance(c.content_type, ContentType) else c.content_type,
                categories=c.categories,
                level=c.level,
                duration_minutes=c.duration_minutes,
                thumbnail_url=c.thumbnail_url,
                icon=c.icon,
                source_url=c.source_url,
                view_count=c.view_count,
                bookmark_count=c.bookmark_count,
                published_at=c.published_at,
            )
            for c in contents
        ]

        return ContentListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            has_more=(page * limit) < total,
        )

    async def get_by_id(self, content_id: str) -> Optional[Content]:
        """
        Get content by ID.

        Args:
            content_id: Content ID

        Returns:
            Content if found
        """
        try:
            return await self.repo.get_by_id_cross_partition(content_id)
        except Exception as e:
            logger.warning(f"Failed to get content from Cosmos: {e}")
            # Check mock data
            for content in self._get_mock_content_list():
                if content.id == content_id:
                    return content
            return None

    def _get_mock_content_list(self) -> list[Content]:
        """Generate mock content from pre-collected LAB data."""
        from datetime import datetime

        # Pre-collected Ignite 2025 LAB content data
        return [
            Content(
                id="lab510-vs-code-copilot",
                contributor_id="system",
                title="LAB510: VS Code에서 GitHub Copilot의 강력한 기능",
                description="이 실습형 랩에서는 Visual Studio Code에서 GitHub Copilot을 활용하여 일상적인 코딩 작업에서 가치를 극대화하는 방법을 심층적으로 다룹니다. 참가자는 agent mode, 모델 선택 전략, 그리고 코드 품질을 유지하면서 생산성을 높이는 기법을 통해 Copilot이 워크플로를 어떻게 변화시키는지 학습합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB510-the-power-of-github-copilot-in-vs-code",
                source_type="github",
                categories=["AI", "Copilot", "DevOps", "Azure"],
                level="intermediate",
                duration_minutes=90,
                icon="🤖",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab511-azure-ai-search-rag",
                contributor_id="system",
                title="LAB511: Azure AI Search로 에이전틱 지식 베이스 구축: 차세대 RAG",
                description="이 실습형 랩에서는 Azure AI Search의 차세대 검색 방식인 에이전틱 RAG를 사용하여 Knowledge Base를 구축합니다. 여러 인덱스와 스토리지 시스템 전반에서 스마트 소스 선택을 활용해 에이전틱 검색 엔진을 엔터프라이즈 데이터에 연결합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB511-build-agentic-knowledge-bases-next-level-rag-with-azure-ai-search",
                source_type="github",
                categories=["AI", "Azure", "Data", "Agent", "Analytics"],
                level="intermediate",
                duration_minutes=90,
                icon="🔍",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab512-multimodal-agents",
                contributor_id="system",
                title="LAB512: Microsoft Foundry 및 AI Toolkit을 사용한 멀티모달 에이전트 프로토타이핑",
                description="이 실습에서는 VS Code에서 AI Toolkit(AITK)과 Microsoft Foundry를 직접 사용하여 Model Catalog의 최신 멀티모달 및 추론 모델을 탐색하고 비교합니다. 프롬프트 및 컨텍스트 엔지니어링을 활용해 실제 비즈니스 시나리오에 맞게 모델을 보강하는 방법을 학습합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB512-prototyping-multimodal-agents-with-microsoft-foundry-and-the-ai-toolkit",
                source_type="github",
                categories=["AI", "Azure", "Agent", "Copilot", "DevOps"],
                level="intermediate",
                duration_minutes=90,
                icon="🎨",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab513-a2a-mcp-agents",
                contributor_id="system",
                title="LAB513: SWE Agents 및 agent-framework를 사용하여 A2A 및 MCP 시스템 구축",
                description="Semantic Kernel 및 AutoGen 엔지니어링 팀이 제공하는 통합 플랫폼인 Microsoft Agent Framework를 활용하여 A2A 호환 에이전트를 구축하는 방법을 학습합니다. GitHub Copilot 코딩 에이전트와 Azure OpenAI 모델을 사용하는 Codex 등 SWE Agents를 활용해 개발을 가속화합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB513-build-a2a-and-mcp-systems-using-swe-agents-and-agent-framework",
                source_type="github",
                categories=["AI", "Azure", "Agent", "Copilot", "Security"],
                level="advanced",
                duration_minutes=90,
                icon="🤝",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab514-mcp-azure-functions",
                contributor_id="system",
                title="LAB514: MCP 및 Azure Functions로 AI 에이전트를 빌드하고 배포하기",
                description="Azure Functions를 사용하여 GitHub Copilot과 같은 AI 어시스턴트를 위한 MCP(Model Context Protocol) 도구를 만드는 방법을 보여주는 지능형 코드 스니펫 서비스를 구축합니다. Microsoft Agent Framework로 내구성 있는(durable) AI 에이전트를 구현하고, Durable Functions로 멀티 에이전트 워크플로를 오케스트레이션합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB514-build-and-deploy-ai-agents-with-mcp-and-azure-functions",
                source_type="github",
                categories=["AI", "Azure", "Agent", "DevOps", "Data"],
                level="intermediate",
                duration_minutes=90,
                icon="⚡",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab515-postgresql-ai-agents",
                contributor_id="system",
                title="LAB515: PostgreSQL로 고급 AI 에이전트를 구축하기",
                description="이 실습형 랩에서는 PostgreSQL과 Microsoft Agent Framework를 사용하여 실제 판례 데이터를 기반으로 추론하는 AI 기반 법률 리서치 어시스턴트를 구축합니다. retrieval-augmented generation(RAG), 벡터 검색, 그래프 인텔리전스를 결합하여 정확하고 맥락에 맞으며 설명 가능한 답변을 생성하는 에이전틱 워크플로를 구현합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB515-build-advanced-ai-agents-with-postgresql",
                source_type="github",
                categories=["AI", "Azure", "Data", "Agent", "Analytics"],
                level="advanced",
                duration_minutes=90,
                icon="🗄️",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab516-ai-red-teaming",
                contributor_id="system",
                title="LAB516: Microsoft Foundry의 AI Red Teaming Agent로 에이전트를 안전하게 보호하기",
                description="이 실습형 워크숍에서는 Microsoft Foundry를 사용하여 생성형 AI 시스템의 안전 및 보안 위험을 평가하기 위한 자동화된 AI 레드팀의 기본 개념을 소개합니다. 참가자는 배포 전에 여러 위험 차원에 걸쳐 안전 문제와 보안 취약점을 찾기 위해 자동화된 공격 기법을 적용하는 방법을 학습합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB516-safeguard-your-agents-with-ai-red-teaming-agent-in-microsoft-foundry",
                source_type="github",
                categories=["AI", "Azure", "Security", "Agent"],
                level="intermediate",
                duration_minutes=90,
                icon="🛡️",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab517-aks-mcp-agents",
                contributor_id="system",
                title="LAB517: 모델, 에이전트 및 MCP를 활용한 차세대 AKS 운영",
                description="차세대 운영 도구를 활용하여 대규모 AKS 관리를 자신 있게 수행하는 방법을 익힙니다. 이 실습형 랩에서는 트래픽 급증으로 영향을 받는 프로덕션 서비스를 시뮬레이션하고, AI 기반 알림이 숨겨진 병목을 어떻게 드러내는지 확인하며, 노드를 자가 치유하는 에이전트를 배포합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB517-next-gen-aks-operations-with-models-and-agents-and-mcps-oh-my",
                source_type="github",
                categories=["Azure", "Kubernetes", "AI", "DevOps", "Agent"],
                level="intermediate",
                duration_minutes=90,
                icon="☸️",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab518-multi-agent-apps",
                contributor_id="system",
                title="LAB518: Microsoft Agent Framework 또는 LangGraph를 활용한 멀티 에이전트 앱",
                description="Azure Cosmos DB를 통해 확장 가능하고 고성능의 데이터 영속화 및 조회를 구현하면서, C#의 Microsoft Agent Framework 또는 Python의 LangChain을 사용해 MCP(Model Context Protocol)를 활용하는 멀티 에이전트 애플리케이션을 구축합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB518-multi-agent-apps-with-microsoft-agent-framework-or-langgraph",
                source_type="github",
                categories=["AI", "Azure", "Agent", "Data", "Analytics"],
                level="advanced",
                duration_minutes=90,
                icon="🤖",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab519-ai-gateway-governance",
                contributor_id="system",
                title="LAB519: Azure API Management의 AI Gateway로 AI 앱 및 에이전트를 거버넌스하기",
                description="이 실습형 랩에서는 Azure API Management의 AI Gateway를 사용하여 AI 앱과 에이전트를 거버넌스하는 방법을 학습합니다. AI 모델을 온보딩하고 토큰 사용량을 모니터링 및 제어하며, 안전 및 컴플라이언스 정책을 적용하는 동시에 semantic caching으로 성능을 향상시킵니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB519-governing-ai-apps-agents-with-ai-gateway-in-azure-api-management",
                source_type="github",
                categories=["AI", "Azure", "Governance", "Security", "Compliance"],
                level="intermediate",
                duration_minutes=90,
                icon="🔐",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab571-pizza-ordering-agent",
                contributor_id="system",
                title="LAB571: Microsoft Foundry 및 MCP로 피자 주문 에이전트 구축",
                description="이 실습형 워크숍에서는 Foundry Agent Service를 사용하여 도메인 특화 AI 에이전트를 구축하는 방법을 학습합니다. 간단한 에이전트에서 시작하여 시스템 프롬프트, 사용자 지정 지침, RAG를 통한 지식 추가를 단계적으로 적용합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB571-build-a-pizza-ordering-agent-with-microsoft-foundry-and-mcp",
                source_type="github",
                categories=["AI", "Azure", "Agent", "Copilot", "Data"],
                level="beginner",
                duration_minutes=90,
                icon="🍕",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab596-healthcare-ai-models",
                contributor_id="system",
                title="LAB596: 헬스케어 AI 모델 활용: 설정부터 사용 사례까지",
                description="헬스케어 AI 샘플 리포지토리를 살펴보며 Health & Life Sciences를 위한 멀티모달 AI를 성공적으로 활용할 수 있도록 준비합니다. 이미지 검색, 방사선/병리 이미지 기반 암 등급 분류, 이상치 탐지, 검사 파라미터 분류와 같은 문제를 다루는 노트북과 샘플 솔루션을 탐색합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB596-working-with-healthcare-ai-models-from-set-up-to-use-case",
                source_type="github",
                categories=["AI", "Azure", "Healthcare", "Machine Learning", "Agent"],
                level="intermediate",
                duration_minutes=90,
                icon="🏥",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab598-healthcare-multi-agent",
                contributor_id="system",
                title="LAB598: 헬스케어에서의 Agentic AI: 멀티 에이전트 오케스트레이션 실전 적용",
                description="Agentic framework의 역량을 활용하여 헬스케어 운영을 효율화하는 방법을 살펴봅니다. Healthcare Agent Orchestrator를 통해 지능형 에이전트를 맞춤 구성하고, 비공개 데이터셋과 공개 소스를 통합한 뒤, Teams 및 Word와 같은 Microsoft 365 도구에 원활하게 배포할 수 있습니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB598-agentic-ai-in-healthcare-multi-agent-orchestration-in-action",
                source_type="github",
                categories=["AI", "Healthcare", "Agent", "Microsoft 365", "Azure"],
                level="advanced",
                duration_minutes=90,
                icon="🏥",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab500-azure-copilot-observability",
                contributor_id="system",
                title="LAB500: Azure Copilot으로 관측 가능성과 최적화를 추진하기",
                description="AI가 Azure에서 클라우드 운영을 어떻게 변화시키는지 살펴봅니다. 이 랩에서는 AI를 사용하여 이상 징후를 조사하고, 텔레메트리를 상관 분석하며, 모니터링 태세를 강화합니다. Copilot의 새로운 agentic 최적화 기능을 활용해 비용 및 탄소 절감 기회를 식별하고 검증합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB500-drive-observability-and-optimization-with-azure-copilot",
                source_type="github",
                categories=["AI", "Azure", "Analytics", "Governance", "Sustainability"],
                level="intermediate",
                duration_minutes=90,
                icon="📊",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab502-aks-automatic-migration",
                contributor_id="system",
                title="LAB502: GitHub Copilot을 활용한 앱 현대화를 통해 AKS Automatic으로 마이그레이션",
                description="AI 기반 도구를 사용하여 레거시 Spring Boot 애플리케이션을 Azure Kubernetes Service(AKS) Automatic으로 현대화하고 마이그레이션하는 방법을 학습합니다. 이 실습 랩에서는 로컬 개발부터 클라우드 배포까지의 전체 과정을 다룹니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB502-migrate-to-aks-automatic-with-github-copilot-for-app-modernization",
                source_type="github",
                categories=["Azure", "Kubernetes", "AI", "Migration", "Security"],
                level="intermediate",
                duration_minutes=90,
                icon="☸️",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab503-avs-migration-modernization",
                contributor_id="system",
                title="LAB503: 마이그레이션 및 최적화에서 현대화까지의 AVS",
                description="참가자는 클릭스루 방식의 AVS 랩을 활용하여 Azure VMware Solution(AVS) 배포 및 현대화 워크플로를 엔드투엔드로 수행하는 실습형 랩에 참여합니다. 이 랩은 디스커버리와 배포부터 마이그레이션, 연결, 스토리지 확장, 현대화까지의 여정을 다루는 6개 모듈로 구성됩니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB503-avs-from-migration-and-optimization-to-modernization",
                source_type="github",
                categories=["Azure", "Migration", "Data", "Governance", "Security"],
                level="intermediate",
                duration_minutes=90,
                icon="🖥️",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab504-azure-arc-hybrid",
                contributor_id="system",
                title="LAB504: Azure Arc로 하이브리드, 멀티클라우드 및 엣지를 연결하고 보안 강화 및 관리하기",
                description="하이브리드 및 멀티클라우드 환경은 연결, 거버넌스, 보안 측면에서 복잡성을 증가시킵니다. 이 실습형 랩에서는 Azure Arc가 다양한 인프라 전반의 관리를 어떻게 단순화하는지 보여줍니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB504-connect-secure-and-manage-hybrid-multicloud-and-edge-with-azure-arc",
                source_type="github",
                categories=["Azure", "Security", "Governance", "Hybrid", "Monitoring"],
                level="intermediate",
                duration_minutes=90,
                icon="🔗",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab505-linux-postgresql-migration",
                contributor_id="system",
                title="LAB505: Azure Migrate로 Linux 및 PostgreSQL 마이그레이션을 빠르게 진행하기",
                description="Azure에서 Linux 애플리케이션 스택을 원활하게 현대화하는 방법을 학습합니다. 참가자는 Linux/Postgres/Java 애플리케이션을 사용하여 마이그레이션 프로세스를 단계별로 진행하고, 대규모 마이그레이션을 위해 infrastructure as code(IaC)를 활용합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB505-fast-track-your-linux-and-postgresql-migration-with-azure-migrate",
                source_type="github",
                categories=["Azure", "Migration", "Data", "DevOps"],
                level="intermediate",
                duration_minutes=90,
                icon="🐧",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab506-windows-sql-migration",
                contributor_id="system",
                title="LAB506: Windows 및 SQL Server 워크로드를 Azure로 마이그레이션 및 현대화",
                description="이 랩은 Windows Server, SQL Server 및 .NET 애플리케이션을 Azure로 마이그레이션하고 현대화하는 방법에 중점을 둡니다. 참가자는 Azure Migrate와 Azure Database Migration Service(DMS)를 사용하여 워크로드를 평가하고 마이그레이션하는 방법을 학습합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB506-migrate-and-modernize-windows-and-sql-server-workloads-to-azure",
                source_type="github",
                categories=["Azure", "Migration", "Data", "Security"],
                level="intermediate",
                duration_minutes=90,
                icon="🪟",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab520-azure-resiliency",
                contributor_id="system",
                title="LAB520: Azure 운영 플랫폼에서 미션 크리티컬 애플리케이션 및 인프라를 위한 복원력 시작, 강화, 지속하기",
                description="이 랩은 Azure의 복원력 및 구성(Configuration) 경험을 활용하여 미션 크리티컬 애플리케이션을 설계하기 위한 'Start, Get, and Stay Resilient' 여정을 다룹니다. 참가자는 복원력 상태를 평가하고 권장 사항을 적용하여 개선 사항을 검증하며 복구를 오케스트레이션합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB520-start-get-and-stay-resilient-with-azure",
                source_type="github",
                categories=["Azure", "Security", "Governance", "Compliance", "Data"],
                level="intermediate",
                duration_minutes=90,
                icon="🛡️",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab530-azure-sql-ai",
                contributor_id="system",
                title="LAB530: Azure SQL Database로 새로운 AI 애플리케이션 구축",
                description="이 실습형 워크숍에서는 애플리케이션 개발을 가속화하는 최신 Azure SQL 혁신을 소개합니다. 참가자는 Azure SQL Database와 함께 generative AI를 활용하는 방법을 학습하며, language model, prompt engineering, Retrieval Augmented Generation(RAG)과 같은 AI 개념을 다룹니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB530-build-new-ai-applications-with-azure-sql-databases",
                source_type="github",
                categories=["AI", "Azure", "Data", "Copilot"],
                level="intermediate",
                duration_minutes=90,
                icon="🗄️",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab531-databricks-bi",
                contributor_id="system",
                title="LAB531: AI 시대의 Azure Databricks로 BI를 가속화하기",
                description="이 90분 분량의 초급자 친화형 실습에서는 Azure Databricks를 사용하여 엔드 투 엔드 분석 솔루션을 구축합니다. Lakeflow를 통한 자동화된 데이터 파이프라인, Unity Catalog를 활용한 엔터프라이즈 거버넌스, Metric Views 기반의 시맨틱 메트릭 레이어를 다룹니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB531-accelerate-bi-with-azure-databricks-in-the-era-of-ai",
                source_type="github",
                categories=["Azure", "Data", "Analytics", "AI", "Governance"],
                level="beginner",
                duration_minutes=90,
                icon="📊",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab532-realtime-intelligence",
                contributor_id="system",
                title="WRK532: Real-Time Intelligence로 실시간 데이터를 행동으로 전환하기",
                description="이 세션에서는 실시간 분석과 디지털 트윈의 역량을 활용하여 핵심 운영 과제를 수행하는 방법을 다룹니다. 본 실습에서 참가자는 물리적 시스템을 동적인 디지털 복제본으로 전환하여 시뮬레이션을 강화하고 운영을 최적화합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB532-get-real-with-real-time-intelligence-to-transform-data-into-action",
                source_type="github",
                categories=["Azure", "Data", "Analytics", "AI", "Agent"],
                level="intermediate",
                duration_minutes=90,
                icon="⚡",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab533-fabric-sql",
                contributor_id="system",
                title="LAB533: Microsoft Fabric의 SQL Database로 확장 가능한 데이터 솔루션 개발",
                description="이 실습형 랩은 Microsoft Fabric의 SQL database를 중심으로 확장 가능한 데이터 솔루션을 설계, 구축, 운영하는 과정을 안내합니다. 참가자는 Copilot을 활용한 T-SQL 개발 및 자연어 쿼리 기능을 사용하고, 벡터 임베딩과 유사도 검색을 기반으로 Azure OpenAI를 활용한 RAG를 구현합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB533-build-scalable-ai-and-data-solutions-in-sql-database-in-microsoft-fabric",
                source_type="github",
                categories=["Data", "AI", "Azure", "Analytics", "Copilot"],
                level="intermediate",
                duration_minutes=90,
                icon="🧵",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab540-purview-defender-xdr",
                contributor_id="system",
                title="Lab540: Microsoft Purview와 Microsoft Defender XDR 통합",
                description="위협이 점점 더 복잡해짐에 따라, 팀은 더 빠르게 위협에 대응하기 위해 향상된 가시성과 컨텍스트가 필요합니다. 이 랩에서는 Microsoft Purview와 Microsoft Defender XDR이 통합되어 단일 화면에서 보안 인시던트를 조사할 수 있도록 조직을 지원하는 방법을 살펴봅니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB540-microsoft-purview-integration-with-microsoft-defender-xdr",
                source_type="github",
                categories=["Security", "Governance", "Compliance", "Microsoft 365"],
                level="intermediate",
                duration_minutes=90,
                icon="🔐",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab541-defender-xdr",
                contributor_id="system",
                title="LAB541: Microsoft Defender XDR로 위협으로부터 방어하기",
                description="이 랩에서는 Microsoft Defender XDR 및 Microsoft Defender for Endpoint를 도입하는 회사의 보안 운영 분석가 역할을 수행합니다. 소수의 디바이스를 온보딩하여 구성을 검증하고 SecOps 대응 절차에 필요한 변경 사항을 파악합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB541-defend-against-threats-with-microsoft-defender",
                source_type="github",
                categories=["Security", "Azure", "Defender", "SecOps"],
                level="intermediate",
                duration_minutes=90,
                icon="🛡️",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab542-zero-trust-intune-entra",
                contributor_id="system",
                title="Zero Trust 랩: Intune 및 Entra를 사용하여 ID와 디바이스를 보호하기",
                description="이 리포지토리는 'Zero Trust 랩: Intune 및 Entra를 사용하여 ID와 디바이스를 보호하기' 실습 랩의 전체 콘텐츠를 포함합니다. 참가자는 Microsoft Intune과 Microsoft Entra ID를 사용하여 현대적인 엔터프라이즈 환경에서 ID와 디바이스를 보호하는 Zero Trust 보안 원칙을 구현하는 실무 경험을 얻습니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB542-zero-trust-lab-securing-identities-and-devices-with-intune-and-entra",
                source_type="github",
                categories=["Security", "Azure", "Governance", "Compliance"],
                level="intermediate",
                duration_minutes=90,
                icon="🔑",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab543-sentinel-threat-hunting",
                contributor_id="system",
                title="LAB543: Microsoft Sentinel에서 위협 헌팅 수행",
                description="이 랩에서는 Microsoft Sentinel을 도입하는 회사의 Security Operations Analyst 역할을 수행합니다. 로그 데이터를 분석하여 악성 활동을 탐지하고, 시각화를 구성하며, 위협 헌팅을 수행합니다. Sentinel Data Lake 및 고급 헌팅 기능을 포함하여 Kusto Query Language(KQL)를 사용해 데이터를 쿼리하고 조사합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB543-perform-threat-hunting-in-microsoft-sentinel",
                source_type="github",
                categories=["Security", "Azure", "Data", "Analytics"],
                level="intermediate",
                duration_minutes=90,
                icon="🔍",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab597-geospatial-intelligence",
                contributor_id="system",
                title="LAB597: 지리공간 인텔리전스로 더 정보에 기반한 의사결정하기",
                description="이 실습형 랩에서는 Microsoft Planetary Computer Pro를 사용하여 지리공간 인텔리전스를 활용하는 방법을 학습합니다. 참가자는 실제 데이터를 기반으로 위성 영상과 항공 사진을 활용해 피닉스 지역 학교 캠퍼스를 분석하고, 지표면 온도와 식생 피복을 측정합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB597-make-more-informed-decisions-with-geospatial-intelligence",
                source_type="github",
                categories=["Azure", "Data", "Analytics", "AI"],
                level="intermediate",
                duration_minutes=90,
                icon="🗺️",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab560-declarative-agents",
                contributor_id="system",
                title="LAB560: TypeSpec 및 M365 Agents Toolkit을 사용하여 Declarative Agent 구축",
                description="Microsoft 365 Copilot의 네이티브 스택을 사용하여 지능적이고 작업 지향적인 Copilot agent를 만드는 방법을 학습합니다. 이 실습 랩에서는 agent 사양을 작성하기 위한 타입 안전 언어인 TypeSpec과 Microsoft 365 Agents Toolkit을 사용하여 Declarative agent를 구축합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB560-building-declarative-agents-with-typespec-and-m365-agents-toolkit",
                source_type="github",
                categories=["AI", "Agent", "Copilot", "Microsoft 365", "DevOps"],
                level="intermediate",
                duration_minutes=90,
                icon="🤖",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab564-goal-driven-agent",
                contributor_id="system",
                title="LAB564: Copilot Studio로 목표 지향형 AI 에이전트를 설계하기",
                description="이 실습형 랩에서는 Microsoft 365 Copilot용 에이전트 구축 방식 이해를 돕는 내부 학습 도우미인 AgentWise에서 영감을 받은 고급 에이전트를 구축합니다. Copilot Studio를 사용하여 사용자 목표에 적응하고, 페르소나에 따라 안내를 개인화하며, 구조화된 플로우와 실시간 데이터를 활용해 지능적으로 의사결정을 수행하는 다계층 에이전트를 설계합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB564-architect-a-goal-driven-ai-agent-with-copilot-studio",
                source_type="github",
                categories=["AI", "Agent", "Copilot", "Microsoft 365"],
                level="advanced",
                duration_minutes=90,
                icon="🎯",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            # PREL & Additional LAB Sessions
            Content(
                id="prel13-agentic-ai-observability",
                contributor_id="system",
                title="PREL13: Azure를 사용하여 에이전틱 AI 앱을 관찰, 관리 및 확장하는 방법 알아보기",
                description="이 실습형 워크숍은 Azure 및 Azure AI Foundry를 사용하여 에이전틱 AI 애플리케이션을 효과적으로 관리, 거버넌스 적용 및 확장하는 역량을 제공합니다. 관찰 가능성(Observability) 기능, 모델 관리 정책, 에이전트 기능, 거버넌스 전략을 다룹니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-PREL13-observe-manage-and-scale-agentic-ai-apps-with-microsoft-foundry",
                source_type="github",
                categories=["AI", "Azure", "Agent", "Governance", "Analytics"],
                level="intermediate",
                duration_minutes=180,
                icon="📊",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="prel15-ai-ready-apps-containerize",
                contributor_id="system",
                title="PREL15: AI-Ready Apps: Azure로 컨테이너화 및 현대화",
                description="이 실습 랩에서는 Azure Container Apps에 AI 기반 애플리케이션을 배포하여 Azure에서 컨테이너화된 애플리케이션을 AI와 함께 현대화하는 방법을 다룹니다. 참가자는 Azure OpenAI를 통합하고 서버리스 GPU에서 오픈 소스 모델(Ollama)을 실행하여 비용 효율적인 추론을 구현합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-PREL15-ai-ready-apps-containerize-and-modernize-with-azure",
                source_type="github",
                categories=["AI", "Azure", "DevOps", "Security", "Agent"],
                level="intermediate",
                duration_minutes=180,
                icon="🐳",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="prel16-semantic-memory-cosmos",
                contributor_id="system",
                title="PREL16: Azure Cosmos DB용 MCP Server를 사용하여 Microsoft Foundry에서 멀티 에이전트 앱을 위한 시맨틱 메모리 구현",
                description="이 실습형 워크숍에서는 Azure Cosmos DB에서 MCP Server를 사용하여 지속적인 시맨틱 메모리를 갖춘 지능형 멀티 에이전트 애플리케이션을 구축하는 방법을 학습합니다. 스레드 전반에서 컨텍스트를 임베딩하고 검색하는 패턴을 살펴보고, LangGraph(Python)와 Azure AI Foundry를 사용해 내구성 있는 메모리, 시맨틱 검색, 에이전트 협업을 구현합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-PREL16-semantic-memory-for-multi-agent-apps-in-microsoft-foundry-with-cosmos-db",
                source_type="github",
                categories=["AI", "Azure", "Agent", "Data", "Analytics"],
                level="advanced",
                duration_minutes=180,
                icon="🧠",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="prel19-it-pro-ai-deployment",
                contributor_id="system",
                title="PREL19: IT 전문가를 위한 AI 애플리케이션 배포 및 관리 가이드",
                description="하이브리드 환경 전반에서 AI 앱을 안전하게 배포하고 관리하는 방법을 학습합니다. 이 워크숍에서는 ID, 네트워킹, Key Vault, 모니터링과 함께 프롬프트 실드 및 데이터 라벨링과 같은 AI 특화 제어를 다룹니다. 인프라를 현대화하는 IT 전문가를 대상으로, 각 계층이 실제 워크로드에 대비한 안전하고 신뢰할 수 있는 AI 솔루션에 어떻게 기여하는지 설명합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-PREL19-an-it-pros-guide-to-deploying-and-managing-ai-applications",
                source_type="github",
                categories=["AI", "Azure", "Security", "Governance", "DevOps"],
                level="intermediate",
                duration_minutes=180,
                icon="👨‍💼",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="prel20-it-estate-modernization",
                contributor_id="system",
                title="PREL20: IT 자산 현대화: 전략에서 실행까지 - 포트폴리오 전환을 위한 실습 워크숍",
                description="이 실습 워크숍은 IT 리더와 실무자를 대상으로, 전략 수립부터 실행까지 IT 자산을 현대화하는 방법에 초점을 맞춥니다. 참가자는 실습과 실제 사례 연구를 통해 6가지 핵심 마이그레이션 및 현대화 전략(Retire, Rehost, Replatform, Refactor, Rearchitect, Rebuild)을 학습하고 적용합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-PREL20-modernize-it-estate-a-hands-on-workshop-for-portfolio-transformation",
                source_type="github",
                categories=["Azure", "Migration", "DevOps", "Copilot", "Governance"],
                level="intermediate",
                duration_minutes=180,
                icon="🚀",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="prel14-fabric-data-ai",
                contributor_id="system",
                title="PREL14: Microsoft Fabric로 데이터를 통합하고 인사이트에 기반해 실행하며 AI 솔루션을 구축하기",
                description="이 반일(half-day) 기술 랩에서는 Microsoft Fabric를 엔드 투 엔드로 직접 경험합니다. OneLake에서 시작하여 단일 데이터 사본이 거버넌스를 간소화하고 중복을 제거하는 방식을 살펴봅니다. 참가자는 역할 기반 가이드 랩을 통해 데이터를 수집, 변환, 보강하고 Copilot으로 데이터 솔루션 개발을 가속화하며 Fabric data agents를 사용해 대화형 Q&A 시스템을 구축합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-PREL14-unify-data-act-on-insights-and-build-ai-solutions-with-microsoft-fabric",
                source_type="github",
                categories=["Data", "AI", "Analytics", "Copilot", "Azure"],
                level="intermediate",
                duration_minutes=180,
                icon="🧵",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="prel17-copilot-agent-lifecycle",
                contributor_id="system",
                title="PREL17: 비용과 복잡성 제어: Copilot 및 Agent 라이프사이클 관리",
                description="이 워크숍은 Copilot Studio Lite 및 Copilot Studio에서 구축한 Microsoft Copilot과 커스텀 agent를 관리하는 IT 관리자와 플랫폼 소유자를 대상으로 합니다. 참가자는 비용을 제어하고 agent 난립을 줄이며, 액세스 정책을 적용하고, 분석을 구성하고, agent 프로비저닝을 비즈니스 우선순위에 맞추기 위한 라이프사이클 프로세스 거버넌스를 학습합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-PREL17-controlling-costs--complexity-managing-copilot-and-agent-lifecycle",
                source_type="github",
                categories=["AI", "Agent", "Microsoft 365", "Governance", "Compliance"],
                level="intermediate",
                duration_minutes=180,
                icon="💰",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="prel18-copilot-ready-security",
                contributor_id="system",
                title="PREL18: Copilot Ready: 전략, 데이터 및 보안",
                description="이 세션은 Microsoft 365 테넌트의 보안을 개선하기 위한 실습 중심의 접근 방식을 제공합니다. Copilot 및 AI 도입을 지원하기 위해 안전하지 않은 기본 설정을 식별하고, 보안 기준선을 적용하며, 데이터 레이블링 전략을 활용하는 과정을 안내합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-PREL18-secure-your-m365-tenant-from-defaults-to-ai-ready",
                source_type="github",
                categories=["Security", "Microsoft 365", "Copilot", "AI", "Governance"],
                level="intermediate",
                duration_minutes=180,
                icon="🔒",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab534-cosmos-realtime-analytics",
                contributor_id="system",
                title="LAB534: Microsoft Fabric에서 Cosmos DB로 실시간 분석 구축",
                description="Cosmos DB in Microsoft Fabric를 사용하여 완전한 실시간 분석 솔루션을 구축하는 방법을 학습합니다. 이 실습 랩에서는 운영 데이터 저장소를 생성하고, 스트리밍 데이터 파이프라인을 구현하며, 크로스 데이터베이스 분석을 구축하고, Reverse ETL 패턴을 활용해 개인화 추천을 배포하는 과정을 시연합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB534-build-real-time-analytics-with-cosmos-db-in-microsoft-fabric",
                source_type="github",
                categories=["Azure", "Data", "Analytics", "Machine Learning", "DevOps"],
                level="intermediate",
                duration_minutes=90,
                icon="⚡",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab535-databricks-unified-analytics",
                contributor_id="system",
                title="LAB535: Azure Databricks 실전: Microsoft 전반에서 통합 AI 및 분석 구현",
                description="이 실습형 랩에서는 Azure Databricks, Azure AI Foundry, Microsoft Copilot Studio를 사용하여 현대적인 클라우드 네이티브 분석 및 AI 솔루션을 설계하고 배포합니다. Zava-Litware 시나리오를 기반으로 데이터 수집, Lakeflow를 통한 오케스트레이션, Genie를 활용한 AI 기반 인사이트 도출을 수행합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB535-azure-databricks-in-action-unified-ai-and-analytics-across-microsoft",
                source_type="github",
                categories=["Azure", "Data", "AI", "Analytics", "Copilot"],
                level="intermediate",
                duration_minutes=90,
                icon="📊",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab544-entra-identity-governance",
                contributor_id="system",
                title="Lab544: Microsoft Entra를 사용하여 신뢰할 수 있게 ID를 거버넌스하기",
                description="Microsoft Entra를 사용하여 대규모로 ID를 거버넌스하는 역량을 습득합니다. 프로비저닝 자동화, 액세스 간소화, 거버넌스 정책 적용, 그리고 위험을 줄이고 규정 준수를 보장하기 위한 ID 검증용 Face Check 구성에 대한 실습 경험을 제공합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB544-govern-identities-with-confidence-using-microsoft-entra",
                source_type="github",
                categories=["Security", "Governance", "Compliance", "Azure"],
                level="intermediate",
                duration_minutes=90,
                icon="🔑",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab545-sensitive-info-labels",
                contributor_id="system",
                title="LAB545: 중요한 정보 유형 및 레이블 생성 및 관리",
                description="조직이 Microsoft 365 Copilot과 같은 AI 도구를 도입함에 따라 중요한 데이터를 보호하는 것이 필수적입니다. 이 실습 세션에서는 Microsoft Purview Information Protection 및 DLP를 사용하여 프로젝트 데이터를 분류하고 보호합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB545-manage-sensitive-data-using-information-protection-in-the-age-of-ai",
                source_type="github",
                categories=["Security", "AI", "Microsoft 365", "Governance", "Compliance"],
                level="intermediate",
                duration_minutes=90,
                icon="🏷️",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab546-zero-trust-stack",
                contributor_id="system",
                title="LAB546: 스택 보안 강화 – 데이터, 인프라, 네트워크 및 SOC를 위한 Zero Trust",
                description="이 실습형 랩에서는 Microsoft Zero Trust Workshop을 소개하고 데이터, 인프라, 네트워크, 보안 운영의 네 가지 핵심 축에 걸쳐 기술 스택을 보호하는 방법을 안내합니다. 참가자는 워크숍 도구와 제공 가이드를 살펴본 뒤, 데모와 시나리오를 수행하며 엔터프라이즈 환경에서 Zero Trust 원칙을 적용합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB546-securing-the-stack-zero-trust-for-data-infra-network-and-soc",
                source_type="github",
                categories=["Security", "Azure", "Governance", "Compliance", "Copilot"],
                level="intermediate",
                duration_minutes=90,
                icon="🛡️",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab547-insider-risk-adaptive",
                contributor_id="system",
                title="LAB547: Insider Risk Management 및 Adaptive Protection 구현",
                description="Microsoft Copilot과 같은 AI 도구는 생산성을 높이지만 민감한 데이터가 노출될 위험도 있습니다. 이 세션에서는 Microsoft Purview Insider Risk Management를 사용하여 위험한 AI 활동을 탐지하고 대응합니다. 분석을 활성화하고 AI 및 DLP 신호를 활용하는 정책을 생성하며, 위험 수준 변화에 따라 적용을 자동으로 조정하도록 Adaptive Protection을 설정합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB547-implement-insider-risk-management-and-adaptive-protection-for-ai",
                source_type="github",
                categories=["Security", "AI", "Governance", "Compliance"],
                level="intermediate",
                duration_minutes=90,
                icon="⚠️",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab548-dlp-copilot-ai",
                contributor_id="system",
                title="LAB548: 데이터 손실 방지를 통해 Copilot 및 AI 앱에서 데이터 노출을 방지하기",
                description="Microsoft 365 Copilot과 같은 AI 도구는 생산성을 높이지만 민감한 정보가 노출될 위험도 있습니다. 이 랩에서는 Microsoft Purview Data Loss Prevention(DLP)을 사용하여 Copilot 및 AI 환경 전반에서 데이터를 보호하기 위해 DLP 정책을 생성하고 테스트합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB548-prevent-data-exposure-in-copilot-and-ai-apps-with-data-loss-prevention",
                source_type="github",
                categories=["Security", "AI", "Compliance", "Governance"],
                level="intermediate",
                duration_minutes=90,
                icon="🔐",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab549-conditional-access-security",
                contributor_id="system",
                title="LAB549: Conditional Access로 ID 보안 태세를 강화하기",
                description="Zero Trust에 맞춰 Conditional Access로 테넌트를 보호합니다. 이 실습형 랩에서는 안전한 롤아웃 패턴을 학습하고, Entra의 CA Optimization Agent–Security Copilot을 사용하여 매일 스캔하고 격차를 표시하며, 원클릭 및 단계적 적용으로 개선 조치를 수행하는 방법을 다룹니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB549-strengthen-your-identity-security-posture-with-conditional-access",
                source_type="github",
                categories=["Security", "Azure", "Governance", "Copilot"],
                level="intermediate",
                duration_minutes=90,
                icon="🔑",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab550-defender-cloud-threats",
                contributor_id="system",
                title="LAB550: Microsoft Defender for Cloud를 사용하여 클라우드 위협을 완화하기",
                description="참가자는 Microsoft Defender for Cloud를 활성화하고 대시보드를 탐색하며 규정 준수 및 워크로드 보호 인사이트를 해석하는 방법을 학습합니다. 실습에서는 Secure Score 분석, 보안 권장 사항, 인벤토리 관리, 가격 책정 모델, 거버넌스 규칙 할당을 다룹니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB550-mitigating-cloud-threats-with-microsoft-defender-for-cloud",
                source_type="github",
                categories=["Security", "Azure", "Governance", "Compliance"],
                level="intermediate",
                duration_minutes=90,
                icon="☁️",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab551-cspm-defender-cloud",
                contributor_id="system",
                title="LAB551: 클라우드 보안 극대화: Microsoft Defender for Cloud의 CSPM",
                description="이 랩은 Microsoft Defender for Cloud의 CSPM 기능을 실습 중심으로 심층적으로 다루며, 하이브리드 환경 전반에서 클라우드 보안을 평가하고 개선하는 방법을 학습합니다. 참가자는 구성 오류를 식별하고, 규정 준수 프레임워크를 적용하며, 자동화된 수정(리미디에이션) 전략을 적용하여 전반적인 보안 태세를 강화합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB551-maximizing-cloud-security-cspm-in-microsoft-defender-cloud",
                source_type="github",
                categories=["Security", "Azure", "Governance", "Compliance"],
                level="intermediate",
                duration_minutes=90,
                icon="🛡️",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab562-employee-self-service-agent",
                contributor_id="system",
                title="LAB562: Employee Self-Service Agent로 AI 기반 HR 및 IT 지원을 빠르게 시작하기",
                description="Ignite 2025에서 Microsoft의 Employee Self-Service Agent를 활용하여 AI 기반 HR 및 IT 지원을 빠르게 시작합니다. 워크플로를 간소화하고 생산성을 향상시키며, 더 스마트한 엔터프라이즈 솔루션을 위해 Azure AI 도구를 통합하는 방법을 학습합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB562-jumpstart-ai-powered-hr-and-it-support-with-employee-self-service-agent",
                source_type="github",
                categories=["AI", "Azure", "Agent", "Copilot", "DevOps"],
                level="intermediate",
                duration_minutes=90,
                icon="👥",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab565-makers-copilot-agents",
                contributor_id="system",
                title="LAB565: Makers in action: 실제 업무를 위한 Microsoft 365 Copilot Agents 제작",
                description="이 실습형 랩에서는 makers가 topics, MCP Tools, 자율 동작(autonomous behaviors)을 활용하여 Microsoft 365 Copilot용 지능형 에이전트를 만드는 방법을 학습합니다. 참가자는 에이전트의 기본 개념을 살펴보고, 맞춤형 워크플로를 구축하며, Copilot Studio의 기능을 활용해 실제 업무 작업을 간소화하는 실전 경험을 쌓습니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB565-makers-in-action-crafting-microsoft-365-copilot-agents-for-real-world",
                source_type="github",
                categories=["AI", "Copilot", "Agent", "Microsoft 365", "Azure"],
                level="intermediate",
                duration_minutes=90,
                icon="🛠️",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab568-teams-admin-security",
                contributor_id="system",
                title="LAB568: Teams Admin Center 및 보안 혁신 심층 분석",
                description="이 실습형 랩은 IT 전문가와 기술 의사결정자를 대상으로 Microsoft Teams 관리 및 보안의 최신 도구와 기능을 익히도록 설계되었습니다. 참가자는 운영 효율성을 높이고 협업을 보호하는 새로운 진단, 모니터링 및 보호 기능을 살펴봅니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB568-deep-dive-into-teams-admin-center-and-security-innovations",
                source_type="github",
                categories=["Microsoft 365", "Security", "Governance", "Compliance"],
                level="intermediate",
                duration_minutes=90,
                icon="👥",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab570-agentic-copilot-studio",
                contributor_id="system",
                title="LAB570: Copilot Studio로 에이전틱 솔루션 구축하기",
                description="이 실습형 랩은 Microsoft Copilot Studio를 사용하여 목적 중심 설계부터 고급 기능까지 에이전트 라이프사이클 전 과정을 안내합니다. 참가자는 Agent Flows와 Model Context Protocol(MCP) 같은 도구를 활용해 완전한 기능을 갖춘 에이전트를 구축, 통합, 자동화 및 배포하는 방법을 학습합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB570-building-agentic-solutions-with-copilot-studio",
                source_type="github",
                categories=["AI", "Agent", "Copilot", "Automation", "DevOps"],
                level="intermediate",
                duration_minutes=90,
                icon="🤖",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab572-mcp-enterprise-workflows",
                contributor_id="system",
                title="LAB572: MCP Tools로 엔터프라이즈 워크플로를 자동화하기",
                description="이 랩에서는 Agent 365의 에이전트와 함께 사용할 수 있도록 새로 출시된 Model Context Protocol(MCP) 서버를 시연합니다. 참가자는 Agent 365와 MCP를 소개받은 뒤 Copilot Studio 에이전트를 빌드하고 구성하며, 메일/캘린더/OneDrive 및 SharePoint용 MCP 서버를 추가합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB572-automate-your-enterprise-workflows-with-agent-365",
                source_type="github",
                categories=["AI", "Agent", "Copilot", "Microsoft 365", "DevOps"],
                level="intermediate",
                duration_minutes=90,
                icon="⚙️",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab580-windows365-reserve",
                contributor_id="system",
                title="LAB580: Windows 365 Reserve: 빠르고 유연하며 어떤 상황에도 대비할 수 있습니다",
                description="이 실습형 랩에서는 여행, 복구, 임시 접근과 같은 시나리오에 적합한 Windows 365 Reserve를 사용하여 안전한 온디맨드 Cloud PC를 배포하는 방법을 학습합니다. 참가자는 프로비저닝 프로필을 생성하고 Cloud PC를 할당하며 Conditional Access, Entra ID 및 네트워킹을 구성합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB580-windows-365-reserve-fast-flexible-and-ready-for-anything",
                source_type="github",
                categories=["Azure", "Security", "Microsoft 365", "Governance"],
                level="intermediate",
                duration_minutes=90,
                icon="💻",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab581-windows365-frontline",
                contributor_id="system",
                title="LAB581: Windows 365 Frontline: Dedicated, Shared, Cloud Apps 살펴보기",
                description="이 실습형 랩에서는 Windows 365 Frontline을 살펴보고 Dedicated, Shared, Cloud Apps 환경을 생성 및 구성하는 방법을 학습합니다. 참가자는 교대 근무자, 작업 기반 역할, 앱 전용 액세스 시나리오에 따라 각 모델을 언제 사용해야 하는지 이해합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB581-windows-365-frontline-explore-dedicated-shared-cloud-apps",
                source_type="github",
                categories=["Azure", "Security", "Compliance", "Microsoft 365"],
                level="intermediate",
                duration_minutes=90,
                icon="👷",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab582-windows365-zero-trust",
                contributor_id="system",
                title="LAB582: Windows 365 배포 랩: 클라우드 네이티브, Zero Trust, 완전한 준비 상태",
                description="안전하고 확장 가능한 모델을 사용하여 Windows 365 Cloud PC를 배포하는 방법을 학습합니다. 이 실습 랩에서는 프로비저닝 정책을 설정하고 Microsoft Entra와 통합하며 Zero Trust 네트워킹을 적용하고 Conditional Access를 구성합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB582-windows-365-deployment-lab-cloud-native-zero-trust-fully-ready",
                source_type="github",
                categories=["Azure", "Security", "Zero Trust", "Microsoft 365", "Device Management"],
                level="intermediate",
                duration_minutes=90,
                icon="🔒",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab583-copilot-plus-ai",
                contributor_id="system",
                title="LAB583: Copilot+ PC 및 Windows 11을 위한 AI 기능 관리",
                description="이 랩 세션은 Copilot+ PC에서 AI 기능과 사용자 경험을 사용하고 관리하는 실습 경험을 제공합니다. 참가자는 이러한 경험을 활성화하고 제어하는 방법, 사용자 맞춤 설정과 IT 관리자가 사용할 수 있는 제어 항목의 차이를 이해하며, Microsoft Intune을 사용해 Recall, Click to Do 등의 기능을 세부 조정하는 방법을 학습합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB583-manage-ai-capabilities-for-copilot-plus-pcs-and-windows-11",
                source_type="github",
                categories=["AI", "Security", "Microsoft 365", "Governance"],
                level="intermediate",
                duration_minutes=90,
                icon="🖥️",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab584-windows-ml-local-ai",
                contributor_id="system",
                title="LAB584: Windows ML로 로컬 AI 통합하기",
                description="이 실습에서는 이제 정식 출시된 Windows ML을 사용하여 더 똑똑한 이미지 분류 앱을 구축합니다. NPU용 Execution Provider(EP)를 동적으로 다운로드하고, 하드웨어별 EP에 맞게 모델을 컴파일한 뒤, 로컬에서 추론을 실행하는 과정을 단계별로 다룹니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB584-integrating-local-ai-with-windows-ml",
                source_type="github",
                categories=["AI", "Windows", "Machine Learning", "DevOps"],
                level="intermediate",
                duration_minutes=90,
                icon="🧠",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab585-supercharge-local-ai",
                contributor_id="system",
                title="LAB585: 로컬 AI로 앱을 강화하기",
                description="이 실습에서는 WPF 앱에 새로운 AI 기능을 추가하여 PDF 파일을 질의하고 그 내용에 기반한 답변을 반환하는 애플리케이션을 구축하는 방법을 학습합니다. Semantic Search를 사용해 인덱싱 및 검색을 수행하고, OCR로 텍스트를 추출하며, 로컬 Phi-Silica 언어 모델로 응답을 생성합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB585-supercharge-your-apps-with-local-ai",
                source_type="github",
                categories=["AI", "Windows", "Search", "RAG", "OCR"],
                level="intermediate",
                duration_minutes=90,
                icon="📱",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab587-windows365-ai-search",
                contributor_id="system",
                title="LAB587: Windows 365 AI 랩: 시맨틱 검색, 페더레이티드 검색 및 Click2Do 실습",
                description="이 실습형 랩에서는 Windows 365 AI의 시맨틱 검색, 페더레이티드 검색, Click2Do 기능을 구성하고 직접 체험합니다. Cloud PC에서 이러한 기능을 활성화하는 방법과 사전 요구 사항을 이해하고, IT 관리자 워크플로우와 최종 사용자 생산성을 어떻게 향상시키는지 살펴봅니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB587-windows-365-ai-lab-improved-windows-search-and-click-to-do-in-action",
                source_type="github",
                categories=["AI", "Microsoft 365", "Copilot", "Agent", "DevOps"],
                level="intermediate",
                duration_minutes=90,
                icon="🔍",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab590-teams-ai-library",
                contributor_id="system",
                title="LAB590: Teams AI Library로 Microsoft Teams에서 협업 에이전트 구축하기",
                description="이 랩은 Teams SDK를 사용하여 기존 AI 에이전트를 Microsoft Teams로 가져와 채팅, 회의, 채널 전반에서 협업 경험을 제공하며 확장하는 방법에 초점을 둡니다. 참가자는 다른 플랫폼에서 Teams로 에이전트를 마이그레이션하는 방법과 agent-to-agent communication(A2A), Model Context Protocol(MCP)과 같은 새로운 기능을 활용하는 방법을 학습합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB590-building-collaborative-agents-in-microsoft-teams-with-teams-ai-library",
                source_type="github",
                categories=["AI", "Agent", "Microsoft 365", "Copilot", "DevOps"],
                level="intermediate",
                duration_minutes=90,
                icon="👥",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
            Content(
                id="lab595-dragon-copilot-extensibility",
                contributor_id="system",
                title="LAB595: 파트너가 구축한 AI 솔루션으로 Dragon Copilot 확장하기",
                description="이 실습형 랩에서는 개발자와 파트너가 Dragon Copilot을 통해 제공할 수 있는 솔루션, 에이전트 및 확장 기능을 구축하는 방법을 안내합니다. Dragon Copilot 확장성 프레임워크를 활용하여 동작하는 AI 앱을 만들고 배포를 위한 준비 과정을 학습합니다.",
                content_type=ContentType.LAB,
                status=ContentStatus.PUBLISHED,
                source_url="https://github.com/microsoft/ignite25-LAB595-extending-dragon-copilot-with-partner-built-ai-solutions",
                source_type="github",
                categories=["AI", "Agent", "Healthcare", "Copilot"],
                level="intermediate",
                duration_minutes=90,
                icon="🐉",
                view_count=0,
                bookmark_count=0,
                published_at=datetime.utcnow(),
            ),
        ]

    def _get_dynamically_created_content(self) -> list[Content]:
        """Get content created from analysis (stored in mock container)."""
        from app.db.cosmos import _mock_data

        contents = []
        container_data = _mock_data.get("contents", [])

        for item in container_data:
            try:
                content = Content.from_cosmos_item(item)
                contents.append(content)
            except Exception as e:
                logger.debug(f"Failed to parse content item: {e}")

        return contents

    def _get_combined_mock_content(
        self,
        limit: int,
        offset: int,
        category: Optional[str] = None,
    ) -> tuple[list[Content], int]:
        """Get paginated content combining mock data with dynamically created content."""
        # Get static mock content
        mock_items = self._get_mock_content_list()

        # Get dynamically created content from analysis
        dynamic_items = self._get_dynamically_created_content()

        # Filter dynamic items to published only
        dynamic_items = [c for c in dynamic_items if c.status == ContentStatus.PUBLISHED]

        # Combine: dynamic items first (newest), then mock items
        all_items = dynamic_items + mock_items

        # Remove duplicates by source_url
        seen_urls = set()
        unique_items = []
        for item in all_items:
            url = item.source_url or item.id
            if url not in seen_urls:
                seen_urls.add(url)
                unique_items.append(item)

        # Apply category filter
        if category:
            unique_items = [c for c in unique_items if category in c.categories]

        total = len(unique_items)
        paginated = unique_items[offset:offset + limit]

        return paginated, total

    def _get_mock_content(
        self,
        limit: int,
        offset: int,
        category: Optional[str] = None,
    ) -> tuple[list[Content], int]:
        """Get paginated mock content."""
        items = self._get_mock_content_list()

        if category:
            items = [c for c in items if category in c.categories]

        total = len(items)
        items = items[offset:offset + limit]

        return items, total

    def _search_mock_content(
        self,
        query: str,
        limit: int,
        offset: int,
    ) -> tuple[list[Content], int]:
        """Search mock content including dynamically created content."""
        # Combine static and dynamic content
        mock_items = self._get_mock_content_list()
        dynamic_items = self._get_dynamically_created_content()
        dynamic_items = [c for c in dynamic_items if c.status == ContentStatus.PUBLISHED]

        all_items = dynamic_items + mock_items

        query_lower = query.lower()

        filtered = [
            c for c in all_items
            if query_lower in c.title.lower()
            or query_lower in c.description.lower()
            or any(query_lower in cat.lower() for cat in c.categories)
        ]

        # Remove duplicates
        seen_urls = set()
        unique_items = []
        for item in filtered:
            url = item.source_url or item.id
            if url not in seen_urls:
                seen_urls.add(url)
                unique_items.append(item)

        total = len(unique_items)
        paginated = unique_items[offset:offset + limit]

        return paginated, total

    # =========================================================================
    # Pipeline Integration Methods (Milestone 2)
    # =========================================================================

    async def update_raw_extraction_ref(
        self,
        content_id: str,
        raw_extraction_id,
    ) -> Content:
        """
        Update content with reference to RawExtraction.

        Used by Analysis Pipeline (T201) to link content to its raw extraction.

        Args:
            content_id: Content unique identifier
            raw_extraction_id: ID of the RawExtraction document

        Returns:
            Updated Content
        """
        # Get existing content
        existing = await self.repo.get_by_id(str(content_id))
        if existing is None:
            raise ValueError(f"Content {content_id} not found")

        # Update raw_extraction_id reference
        existing.raw_extraction_id = raw_extraction_id

        try:
            updated = await self.repo.update(existing)
            logger.info(
                f"Updated content {content_id} with raw_extraction_id {raw_extraction_id}"
            )
            return updated
        except Exception as e:
            logger.warning(f"Failed to update raw_extraction_id: {e}")
            return existing

    async def create_skeleton(self, content: Content) -> Content:
        """
        Create a minimal content skeleton.

        Used by Analysis Pipeline (T201) to create initial content
        before enrichment.

        Args:
            content: Pre-populated Content model

        Returns:
            Created Content
        """
        try:
            created = await self.repo.create(content)
            logger.info(
                f"Created content skeleton {created.id} for {content.source_url}"
            )
            return created
        except Exception as e:
            logger.warning(f"Failed to create content skeleton: {e}")
            # Return the original content for development without Cosmos
            return content

    async def get_by_source_url(self, source_url: str) -> Optional[Content]:
        """
        Get content by source URL.

        Used to check if content already exists for a URL.

        Args:
            source_url: GitHub repository URL

        Returns:
            Content if found, None otherwise
        """
        try:
            return await self.repo.get_by_source_url(source_url)
        except Exception as e:
            logger.warning(f"Error fetching content by source_url: {e}")
            return None


# Singleton instance
_content_service: Optional[ContentService] = None


def get_content_service() -> ContentService:
    """Get content service singleton."""
    global _content_service
    if _content_service is None:
        _content_service = ContentService()
    return _content_service
