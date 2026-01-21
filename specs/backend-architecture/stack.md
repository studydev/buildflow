# Backend Stack & Architecture

**Created**: 2026-01-18  
**Updated**: 2026-01-20  
**Status**: Approved  
**Constitution**: v2.0.0 compliant

---

## Architecture Paradigm

### Azure-First, Pipeline-First

This architecture follows Constitution v2.0.0 principles:

1. **Azure-Only Execution**: All services run on Azure-managed infrastructure
2. **Pipeline-First**: Long-running workflows are first-class citizens
3. **Control Plane / Data Plane Separation**: APIs control, Jobs execute

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CONTROL PLANE vs DATA PLANE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  CONTROL PLANE (Azure Container Apps)      DATA PLANE (Container Apps Jobs) │
│  ────────────────────────────────────      ──────────────────────────────── │
│  • Authentication (OTP + JWT)              • Analysis Pipeline              │
│  • Content CRUD                            • Enrichment Pipeline            │
│  • Pipeline enqueue/status/retry           • Localization Pipeline          │
│  • Search queries                          • Asset Generation Pipeline      │
│  • AI assistant chat                       • Indexing Pipeline              │
│                                                                              │
│  Response: 200/201/202/400/401             Execution: Async, minutes        │
│  Latency: <500ms                           Triggered: Queue / Schedule      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Stack Decision

### Chosen: **Python 3.12 + FastAPI**

| Requirement | FastAPI | Node.js/Express | Rationale |
|-------------|---------|-----------------|-----------|
| OpenAPI/Swagger | ✅ Built-in, auto-generated | ⚠️ Requires swagger-jsdoc | FastAPI generates from type hints |
| JWT Auth | ✅ python-jose, authlib | ✅ jsonwebtoken | Both excellent |
| Cosmos DB | ✅ azure-cosmos (async) | ✅ @azure/cosmos | Both supported |
| Type Safety | ✅ Pydantic v2 | ⚠️ TypeScript adds complexity | Pydantic = runtime validation |
| Async | ✅ Native async/await | ✅ Native | Both excellent |
| Azure Container Apps | ✅ First-class Python support | ✅ First-class Node support | Both work well |
| LLM Integration | ✅ LangChain, OpenAI SDK mature | ⚠️ LangChain.js less mature | Python ML ecosystem stronger |
| Container Apps Jobs | ✅ Same codebase as API | ✅ Same codebase | Both work well |

**Winner**: FastAPI for superior OpenAPI generation, Pydantic validation, and Python AI/ML ecosystem.

### Pipeline Execution: Same Python Codebase

Both API and Pipeline Jobs share the same Python codebase to maximize code reuse:

```
backend/
├── app/                    # Shared application code
│   ├── api/               # API routes (Control Plane)
│   ├── pipelines/         # Pipeline definitions (Data Plane) [NEW]
│   ├── services/          # Shared business logic
│   └── ...
├── Dockerfile.api         # API container image
└── Dockerfile.pipeline    # Pipeline job container image
```

---

## Azure Services Stack

### Environment Model

| Service | Dev Environment | Prod Environment |
|---------|----------------|------------------|
| Resource Group | `rg-buildflow-dev` | `rg-buildflow-prod` |
| Container Apps Environment | `cae-buildflow-dev` | `cae-buildflow-prod` |
| Container Apps (API) | `ca-api-dev` | `ca-api-prod` |
| Container Apps Jobs | `caj-pipeline-dev` | ❌ No pipeline execution |
| Service Bus | `sb-buildflow-dev` | ❌ No async messaging |
| Cosmos DB | `cosmos-buildflow-dev` | `cosmos-buildflow-prod` |
| Azure AI Search | `search-buildflow-dev` | `search-buildflow-prod` |
| Blob Storage | `stbuildflowdev` | `stbuildflowprod` |
| Key Vault | `kv-buildflow-dev` | `kv-buildflow-prod` |
| Azure OpenAI | `aoai-buildflow-dev` | `aoai-buildflow-prod` |

### Dev vs Prod Responsibilities

| Capability | Dev | Prod |
|------------|-----|------|
| API serving | ✅ | ✅ |
| Pipeline execution | ✅ | ❌ |
| Content ingestion | ✅ | ❌ |
| Enrichment/reprocessing | ✅ | ❌ |
| Schema migrations | ✅ | ❌ |
| Content consumption | ✅ | ✅ |
| AI assistant | ✅ | ✅ |
| Search queries | ✅ | ✅ |

---

## Folder Structure (Updated)

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app factory
│   ├── config.py                  # Settings from environment
│   ├── dependencies.py            # Dependency injection
│   │
│   ├── api/                       # CONTROL PLANE
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── router.py          # Aggregates all v1 routes
│   │   │   ├── auth.py            # /api/v1/auth/*
│   │   │   ├── content.py         # /api/v1/content/*
│   │   │   ├── pipelines.py       # /api/v1/pipelines/* [NEW]
│   │   │   ├── search.py          # /api/v1/search [NEW]
│   │   │   ├── assistant.py       # /api/v1/assistant/* [NEW]
│   │   │   └── users.py           # /api/v1/users/*
│   │   └── health.py              # /api/v1/health
│   │
│   ├── pipelines/                 # DATA PLANE [NEW]
│   │   ├── __init__.py
│   │   ├── base.py                # BasePipeline class
│   │   ├── analysis.py            # Analysis pipeline
│   │   ├── enrichment.py          # Enrichment pipeline
│   │   ├── localization.py        # Localization pipeline
│   │   ├── asset_generation.py    # Asset generation pipeline
│   │   ├── indexing.py            # Indexing pipeline
│   │   └── runner.py              # Container Apps Job entry point
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py            # JWT, password hashing
│   │   ├── exceptions.py          # Custom exceptions
│   │   ├── middleware.py          # Correlation ID, logging
│   │   ├── rate_limit.py          # Rate limiting logic
│   │   └── retry.py               # Retry logic with tenacity
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py                # Base model with common fields
│   │   ├── user.py                # User model
│   │   ├── content.py             # Content model (extended)
│   │   ├── pipeline_run.py        # PipelineRun model [NEW]
│   │   ├── raw_extraction.py      # RawExtraction model [NEW]
│   │   ├── generated_asset.py     # GeneratedAsset model [NEW]
│   │   └── enums.py               # Status enums, roles
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── base.py                # Response envelope
│   │   ├── auth.py                # Auth request/response schemas
│   │   ├── content.py             # Content schemas
│   │   ├── pipeline.py            # Pipeline schemas [NEW]
│   │   ├── search.py              # Search schemas [NEW]
│   │   └── user.py                # User schemas
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py        # OTP generation, JWT
│   │   ├── email_service.py       # Send OTP emails
│   │   ├── content_service.py     # Content CRUD
│   │   ├── pipeline_service.py    # Pipeline orchestration [NEW]
│   │   ├── github_service.py      # GitHub API client
│   │   ├── llm_service.py         # Azure OpenAI for enrichment
│   │   ├── search_service.py      # Azure AI Search [NEW]
│   │   ├── storage_service.py     # Azure Blob Storage [NEW]
│   │   └── queue_service.py       # Azure Service Bus [NEW]
│   │
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── base.py                # Base repository pattern
│   │   ├── user_repo.py
│   │   ├── content_repo.py
│   │   ├── pipeline_repo.py       # [NEW]
│   │   ├── raw_extraction_repo.py # [NEW]
│   │   └── asset_repo.py          # [NEW]
│   │
│   └── db/
│       ├── __init__.py
│       └── cosmos.py              # Cosmos DB client
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures
│   ├── unit/
│   │   ├── test_security.py
│   │   ├── test_auth_service.py
│   │   └── test_pipelines.py      # [NEW]
│   ├── integration/
│   │   ├── test_auth_flow.py
│   │   ├── test_content_api.py
│   │   └── test_pipeline_api.py   # [NEW]
│   └── contract/
│       └── test_openapi_schema.py
│
├── scripts/
│   ├── seed_data.py               # Development data seeding
│   ├── generate_keys.py           # RSA key pair generation
│   └── run_pipeline.py            # Manual pipeline trigger [NEW]
│
├── Dockerfile.api                 # API container image [RENAMED]
├── Dockerfile.pipeline            # Pipeline job container image [NEW]
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## Key Libraries (Updated)

### pyproject.toml

```toml
[tool.poetry]
name = "buildflow-api"
version = "2.0.0"
python = "^3.12"

[tool.poetry.dependencies]
# Core
fastapi = "^0.115.0"
uvicorn = { extras = ["standard"], version = "^0.32.0" }
pydantic = "^2.10.0"
pydantic-settings = "^2.6.0"

# Auth & Security
python-jose = { extras = ["cryptography"], version = "^3.3.0" }
passlib = { extras = ["bcrypt"], version = "^1.7.4" }
python-multipart = "^0.0.12"

# Azure Services
azure-cosmos = "^4.7.0"                    # Cosmos DB
azure-servicebus = "^7.12.0"               # Service Bus (pipelines) [NEW]
azure-storage-blob = "^12.19.0"            # Blob Storage [NEW]
azure-search-documents = "^11.4.0"         # AI Search [NEW]
azure-communication-email = "^1.0.0"       # Email

# AI/LLM
openai = "^1.55.0"                         # Azure OpenAI
tiktoken = "^0.8.0"

# HTTP Client
httpx = "^0.28.0"
aiohttp = "^3.11.0"

# Observability
structlog = "^24.4.0"
opentelemetry-api = "^1.28.0"
opentelemetry-sdk = "^1.28.0"
opentelemetry-instrumentation-fastapi = "^0.49b0"

# Utilities
python-dotenv = "^1.0.1"
tenacity = "^9.0.0"                        # Retry logic

[tool.poetry.group.dev.dependencies]
pytest = "^8.3.0"
pytest-asyncio = "^0.24.0"
pytest-cov = "^6.0.0"
httpx = "^0.28.0"
ruff = "^0.8.0"
mypy = "^1.13.0"
pre-commit = "^4.0.0"
```

---

## Pipeline Architecture

### Pipeline Message Schema

All pipeline triggers use a standard message format via Azure Service Bus:

```python
class PipelineMessage(BaseModel):
    """Standard message schema for pipeline triggering."""
    run_id: UUID                          # Unique pipeline run ID
    pipeline_type: PipelineType           # analysis, enrichment, etc.
    content_id: UUID | None               # Related content (if applicable)
    enrichment_version: str               # e.g., "1.2.0"
    correlation_id: str                   # Request correlation
    triggered_by: UUID | None             # User ID or None (system)
    input_params: dict                    # Pipeline-specific parameters
    parent_run_id: UUID | None            # For chained pipelines
    created_at: datetime
```

### Pipeline Chaining

```python
# How pipelines are chained
PIPELINE_CHAINS = {
    "full_ingestion": [
        PipelineType.ANALYSIS,
        PipelineType.ENRICHMENT,
        PipelineType.LOCALIZATION,
        PipelineType.ASSET_GENERATION,
        PipelineType.INDEXING,
    ],
    "refresh_enrichment": [
        PipelineType.ENRICHMENT,
        PipelineType.LOCALIZATION,
        PipelineType.INDEXING,
    ],
    "reindex_only": [
        PipelineType.INDEXING,
    ],
}

# After a pipeline completes successfully, it enqueues the next in chain
async def on_pipeline_complete(run: PipelineRun, chain: str):
    current_index = PIPELINE_CHAINS[chain].index(run.pipeline_type)
    if current_index < len(PIPELINE_CHAINS[chain]) - 1:
        next_type = PIPELINE_CHAINS[chain][current_index + 1]
        await enqueue_pipeline(
            pipeline_type=next_type,
            content_id=run.content_id,
            enrichment_version=run.enrichment_version,
            parent_run_id=run.id,
            correlation_id=run.correlation_id,
        )
```

### Azure Service Bus Topics

```yaml
namespace: sb-buildflow-dev

topics:
  - name: pipeline-triggers
    subscriptions:
      - name: analysis-sub
        filter: "pipeline_type = 'analysis'"
      - name: enrichment-sub
        filter: "pipeline_type = 'enrichment'"
      - name: localization-sub
        filter: "pipeline_type = 'localization'"
      - name: asset-generation-sub
        filter: "pipeline_type = 'asset_generation'"
      - name: indexing-sub
        filter: "pipeline_type = 'indexing'"

  - name: pipeline-events
    subscriptions:
      - name: all-events
        filter: "1 = 1"  # All events for monitoring
```

### Container Apps Job Configuration

```yaml
# Each pipeline runs as a Container Apps Job
jobs:
  - name: caj-analysis
    image: ghcr.io/buildflow/pipeline:latest
    trigger: azure-servicebus
    subscription: analysis-sub
    command: ["python", "-m", "app.pipelines.runner", "--type", "analysis"]
    
  - name: caj-enrichment
    image: ghcr.io/buildflow/pipeline:latest
    trigger: azure-servicebus
    subscription: enrichment-sub
    command: ["python", "-m", "app.pipelines.runner", "--type", "enrichment"]
    
  - name: caj-localization
    image: ghcr.io/buildflow/pipeline:latest
    trigger: azure-servicebus
    subscription: localization-sub
    command: ["python", "-m", "app.pipelines.runner", "--type", "localization"]
    
  - name: caj-asset-generation
    image: ghcr.io/buildflow/pipeline:latest
    trigger: azure-servicebus
    subscription: asset-generation-sub
    command: ["python", "-m", "app.pipelines.runner", "--type", "asset_generation"]
    
  - name: caj-indexing
    image: ghcr.io/buildflow/pipeline:latest
    trigger: azure-servicebus
    subscription: indexing-sub
    command: ["python", "-m", "app.pipelines.runner", "--type", "indexing"]
```

---

## Data Model (Cosmos DB NoSQL)

### Container Design (Updated)

```
Database: buildflow
├── Container: users
│   ├── Partition Key: /id
│   └── Documents: User
│
├── Container: content
│   ├── Partition Key: /contributor_id
│   └── Documents: Content (extended with enrichment fields)
│
├── Container: pipeline_runs [NEW]
│   ├── Partition Key: /content_id (or /triggered_by for orphan runs)
│   └── Documents: PipelineRun
│
├── Container: raw_extractions [NEW]
│   ├── Partition Key: /source_url_hash
│   └── Documents: RawExtraction (immutable)
│
├── Container: generated_assets [NEW]
│   ├── Partition Key: /content_id
│   └── Documents: GeneratedAsset
│
└── Container: auth_tokens
    ├── Partition Key: /user_id
    ├── TTL: enabled
    └── Documents: RefreshToken
```

### Document Schemas (Extended)

```python
# app/models/content.py (Extended)
class Content(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    
    # Core fields
    title: str = Field(max_length=200)
    title_kr: str | None = Field(default=None, max_length=200)
    description: str = Field(max_length=2000)
    description_kr: str | None = Field(default=None, max_length=2000)
    url: HttpUrl
    source_url: HttpUrl | None = None
    categories: list[str] = Field(min_length=1, max_length=10)
    technologies: list[str] = Field(default_factory=list, max_length=20)
    prerequisites: str | None = None
    
    # Ownership
    contributor_id: UUID  # Partition key
    status: ContentStatus = ContentStatus.DRAFT
    visibility: Visibility = Visibility.INTERNAL  # [NEW]
    
    # Versioning [NEW]
    enrichment_version: str | None = None
    last_enriched_at: datetime | None = None
    last_indexed_at: datetime | None = None
    raw_extraction_id: UUID | None = None
    
    # Enriched data [NEW]
    summary_short: str | None = None
    summary_long: str | None = None
    difficulty_level: str | None = None
    estimated_time: str | None = None
    learning_outcomes: list[str] = Field(default_factory=list)
    popularity_score: float | None = None
    
    # Repository signals [NEW]
    stars: int | None = None
    forks: int | None = None
    last_commit_date: datetime | None = None
    is_maintained: bool | None = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# app/models/pipeline_run.py [NEW]
class PipelineRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    pipeline_type: PipelineType
    status: PipelineStatus = PipelineStatus.PENDING
    enrichment_version: str
    
    # Input/Output
    input_params: dict = Field(default_factory=dict)
    output_summary: dict | None = None
    error_details: dict | None = None
    
    # Relations
    content_id: UUID | None = None  # Partition key
    triggered_by: UUID | None = None
    parent_run_id: UUID | None = None
    
    # Execution metadata
    job_id: str | None = None  # Azure Container Apps Job ID
    attempt_number: int = 1
    correlation_id: str
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None


# app/models/raw_extraction.py [NEW]
class RawExtraction(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_url: HttpUrl
    source_url_hash: str  # Partition key (SHA256)
    
    # Immutable raw data
    readme_content: str
    readme_hash: str
    repository_metadata: dict
    commit_activity: dict
    releases: dict
    extracted_urls: dict
    
    # Metadata
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    github_api_version: str = "2022-11-28"
    run_id: UUID


# app/models/generated_asset.py [NEW]
class GeneratedAsset(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    content_id: UUID  # Partition key
    run_id: UUID
    
    asset_type: AssetType
    storage_url: str
    cdn_url: str | None = None
    
    is_generated: bool = True
    model_used: str
    visibility: Visibility
    
    width: int | None = None
    height: int | None = None
    format: str | None = None
    size_bytes: int | None = None
    
    enrichment_version: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

---

## Pipeline Runner Entry Point

```python
# app/pipelines/runner.py
"""Container Apps Job entry point for pipeline execution."""

import argparse
import asyncio
from app.pipelines import (
    AnalysisPipeline,
    EnrichmentPipeline,
    LocalizationPipeline,
    AssetGenerationPipeline,
    IndexingPipeline,
)

PIPELINE_CLASSES = {
    "analysis": AnalysisPipeline,
    "enrichment": EnrichmentPipeline,
    "localization": LocalizationPipeline,
    "asset_generation": AssetGenerationPipeline,
    "indexing": IndexingPipeline,
}

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", required=True, choices=PIPELINE_CLASSES.keys())
    args = parser.parse_args()
    
    # Read message from environment (set by Container Apps Job)
    message_json = os.environ.get("PIPELINE_MESSAGE")
    if not message_json:
        raise ValueError("PIPELINE_MESSAGE environment variable not set")
    
    message = PipelineMessage.model_validate_json(message_json)
    
    # Instantiate and run pipeline
    pipeline_class = PIPELINE_CLASSES[args.type]
    pipeline = pipeline_class()
    
    try:
        await pipeline.run(message)
    except Exception as e:
        await pipeline.on_failure(message, e)
        raise

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Retry & Error Handling

### Retry Policy

```python
# app/core/retry.py
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

RETRYABLE_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.NetworkError,
    azure.cosmos.exceptions.CosmosHttpResponseError,
)

def with_retry(max_attempts: int = 3, min_wait: int = 2, max_wait: int = 30):
    """Decorator for retryable operations."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        reraise=True,
    )
```

### Pipeline Failure Handling

```python
# app/pipelines/base.py
class BasePipeline:
    async def run(self, message: PipelineMessage) -> PipelineRun:
        run = await self.create_run(message)
        
        try:
            await self.update_status(run, PipelineStatus.RUNNING)
            result = await self.execute(message)
            await self.update_status(run, PipelineStatus.COMPLETED, output=result)
            await self.on_success(run)
            return run
        except Exception as e:
            await self.update_status(run, PipelineStatus.FAILED, error=e)
            await self.on_failure(run, e)
            raise
    
    async def on_failure(self, run: PipelineRun, error: Exception):
        """Handle pipeline failure - log, notify, optionally retry."""
        logger.error(
            "Pipeline failed",
            run_id=str(run.id),
            pipeline_type=run.pipeline_type,
            error=str(error),
            correlation_id=run.correlation_id,
        )
        
        # Check if retryable
        if run.attempt_number < self.max_attempts and self.is_retryable(error):
            await self.schedule_retry(run)
    
    async def schedule_retry(self, run: PipelineRun):
        """Re-enqueue with incremented attempt number."""
        await self.queue_service.send(
            topic="pipeline-triggers",
            message=PipelineMessage(
                run_id=run.id,  # Same run ID for tracking
                pipeline_type=run.pipeline_type,
                content_id=run.content_id,
                enrichment_version=run.enrichment_version,
                correlation_id=run.correlation_id,
                attempt_number=run.attempt_number + 1,
                # ... rest of fields
            ),
            delay=timedelta(seconds=2 ** run.attempt_number),  # Exponential backoff
        )
```

---

## API Endpoints (Updated)

### Pipeline Control API

```python
# app/api/v1/pipelines.py
router = APIRouter(prefix="/pipelines", tags=["Pipelines"])

@router.post("", response_model=APIResponse[PipelineRunResponse], status_code=202)
async def enqueue_pipeline(
    request: EnqueuePipelineRequest,
    user: User = Depends(require_role(UserRole.CONTRIBUTOR)),
    pipeline_service: PipelineService = Depends(),
):
    """Enqueue a new pipeline job. Returns 202 Accepted with run_id."""
    run = await pipeline_service.enqueue(
        pipeline_type=request.pipeline_type,
        content_id=request.content_id,
        enrichment_version=request.enrichment_version,
        triggered_by=user.id,
        correlation_id=request.state.correlation_id,
    )
    return APIResponse(
        success=True,
        data=PipelineRunResponse.from_orm(run),
    )

@router.get("/{run_id}", response_model=APIResponse[PipelineRunDetailResponse])
async def get_pipeline_status(
    run_id: UUID,
    user: User = Depends(get_current_user),
    pipeline_service: PipelineService = Depends(),
):
    """Get pipeline run status and details."""
    run = await pipeline_service.get_run(run_id)
    if not run:
        raise NotFoundError("Pipeline run")
    return APIResponse(success=True, data=run)

@router.post("/{run_id}/retry", response_model=APIResponse[PipelineRunResponse], status_code=202)
async def retry_pipeline(
    run_id: UUID,
    user: User = Depends(require_role(UserRole.CONTRIBUTOR)),
    pipeline_service: PipelineService = Depends(),
):
    """Retry a failed pipeline run."""
    run = await pipeline_service.retry(run_id, triggered_by=user.id)
    return APIResponse(success=True, data=run)

@router.post("/{run_id}/cancel", response_model=APIResponse[PipelineRunResponse])
async def cancel_pipeline(
    run_id: UUID,
    user: User = Depends(require_role(UserRole.CONTRIBUTOR)),
    pipeline_service: PipelineService = Depends(),
):
    """Cancel a running pipeline."""
    run = await pipeline_service.cancel(run_id)
    return APIResponse(success=True, data=run)

@router.get("/content/{content_id}/history", response_model=APIResponse[list[PipelineRunResponse]])
async def get_pipeline_history(
    content_id: UUID,
    user: User = Depends(require_role(UserRole.CONTRIBUTOR)),
    pipeline_service: PipelineService = Depends(),
):
    """List all pipeline runs for a content item."""
    runs = await pipeline_service.list_by_content(content_id)
    return APIResponse(success=True, data=runs)
```

---

## Search Integration

### Azure AI Search Service

```python
# app/services/search_service.py
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

class SearchService:
    def __init__(self):
        self.client = SearchClient(
            endpoint=settings.SEARCH_ENDPOINT,
            index_name="buildflow-content",
            credential=AzureKeyCredential(settings.SEARCH_KEY),
        )
    
    async def hybrid_search(
        self,
        query: str,
        filters: dict | None = None,
        top: int = 20,
    ) -> list[SearchResult]:
        """Perform hybrid (keyword + vector) search."""
        # Generate embedding for semantic search
        embedding = await self.get_embedding(query)
        
        vector_query = VectorizedQuery(
            vector=embedding,
            k_nearest_neighbors=top,
            fields="content_vector",
        )
        
        results = self.client.search(
            search_text=query,
            vector_queries=[vector_query],
            filter=self.build_filter(filters),
            top=top,
            scoring_profile="popularity-boost",
        )
        
        return [SearchResult.from_hit(r) for r in results]
```

---

## ⚠️ Deprecated Approaches

The following approaches from v1.0.0 are **DEPRECATED**:

| Deprecated | Replacement |
|------------|-------------|
| `BackgroundTasks` for analysis | Azure Container Apps Jobs |
| In-process async execution | Queue-based pipeline triggering |
| `AnalysisRequest` model | `PipelineRun` model |
| `analysis_service.py` pipeline logic | `app/pipelines/*.py` |
| Local Cosmos Emulator assumption | Azure-first (emulator for dev only) |

### Migration Steps

1. Replace `BackgroundTasks` with Service Bus message publishing
2. Move pipeline logic from `analysis_service.py` to `app/pipelines/analysis.py`
3. Update models to include `enrichment_version`, `run_id`
4. Add `PipelineRun`, `RawExtraction`, `GeneratedAsset` models
5. Implement queue-based triggering with Container Apps Jobs

---

## Summary

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Language** | Python 3.12 | LLM ecosystem, FastAPI |
| **API Framework** | FastAPI | Auto OpenAPI, Pydantic, async |
| **Pipeline Execution** | Azure Container Apps Jobs | Serverless, event-driven |
| **Message Queue** | Azure Service Bus | Topics for pipeline routing |
| **Database** | Cosmos DB NoSQL | Serverless, partition by content_id |
| **Search** | Azure AI Search | Hybrid keyword + vector |
| **LLM** | Azure OpenAI | GPT-4o for enrichment |
| **Storage** | Azure Blob Storage | Generated assets |
| **Auth** | OTP + JWT (RS256) | Stateless, constitution compliant |
| **Container** | Azure Container Apps | API serving |
| **CI/CD** | GitHub Actions | lint → test → build → deploy |
