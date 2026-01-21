# GitHub Analysis Pipeline Design

**Created**: 2026-01-18  
**Updated**: 2026-01-20  
**Status**: Draft  
**Constitution**: v2.0.0 compliant

---

## Overview

This specification defines the BuildFlow analysis and enrichment pipeline system.

**Architecture Paradigm**: Azure-first, Pipeline-first

User submits a GitHub repository URL → API enqueues job (returns 202) → Azure Container Apps Job executes pipeline → Extracts and enriches metadata → Stores raw + derived data → Indexes for search → Frontend polls for status.

All non-trivial processing executes asynchronously via Azure Container Apps Jobs. Synchronous APIs are limited to authentication, content read/write, and pipeline control.

---

## Clarifications

### Session 2026-01-20

- Q: GitHub API Rate Limit 소진 시 대응 전략? → A: Fail Fast with Retry-After (실패 처리 + X-RateLimit-Reset 기반 재시도 가능 시간 반환)
- Q: 동일 content_id에 대한 동시 파이프라인 충돌 처리? → A: Sequential Queue (동일 content_id에 대해 한 번에 하나의 파이프라인만 실행)
- Q: Dev → Prod 프로모션 자동화 수준? → A: Semi-Automated (자동 검증 + Admin 수동 승인)
- Q: AI Assistant 내부 지식 부족 시 fallback 동작? → A: External Search Fallback (Bing/Google 검색 결과 제공)
- Q: 파이프라인 실행 시간 제한 (Timeout)? → A: Global Timeout (모든 파이프라인 동일 10분 제한)

---

## 1. Environment Model

### Dev / Prod Separation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ENVIRONMENT ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────┐    ┌─────────────────────────────────────┐ │
│  │           DEV               │    │              PROD                   │ │
│  ├─────────────────────────────┤    ├─────────────────────────────────────┤ │
│  │ Resource Group:             │    │ Resource Group:                     │ │
│  │   rg-buildflow-dev          │    │   rg-buildflow-prod                 │ │
│  │                             │    │                                     │ │
│  │ ✅ Development              │    │ ✅ Stable, read-optimized           │ │
│  │ ✅ Experimentation          │    │ ✅ Content consumption              │ │
│  │ ✅ Pipeline iteration       │    │ ✅ AI assistant queries             │ │
│  │ ✅ Reprocessing allowed     │    │                                     │ │
│  │ ✅ Schema migrations        │    │ ❌ No experimental pipelines        │ │
│  │ ✅ Enrichment version bumps │    │ ❌ No reprocessing jobs             │ │
│  │                             │    │ ❌ No schema migrations             │ │
│  │ Data flows:                 │    │                                     │ │
│  │ • New content ingestion     │    │ Data flows:                         │ │
│  │ • Analysis pipeline runs    │    │ • Read-only content serving         │ │
│  │ • Enrichment iterations     │    │ • Search queries                    │ │
│  │ • Asset generation          │    │ • AI assistant interactions         │ │
│  │                             │    │                                     │ │
│  │         ─────────────────────────────▶ Promotion                       │ │
│  │         (Approved content only)       (Audited, versioned)             │ │
│  └─────────────────────────────┘    └─────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Environment Resources

| Resource | Dev | Prod |
|----------|-----|------|
| Container Apps Environment | `cae-buildflow-dev` | `cae-buildflow-prod` |
| Container Apps (API) | `ca-api-dev` | `ca-api-prod` |
| Container Apps Jobs | `caj-pipeline-dev` | ❌ (no pipeline execution) |
| Service Bus | `sb-buildflow-dev` | ❌ (no async messaging) |
| Cosmos DB | `cosmos-buildflow-dev` | `cosmos-buildflow-prod` |
| Azure AI Search | `search-buildflow-dev` | `search-buildflow-prod` |
| Blob Storage | `stbuildflowdev` | `stbuildflowprod` |
| Key Vault | `kv-buildflow-dev` | `kv-buildflow-prod` |
| Azure OpenAI | `aoai-buildflow-dev` | `aoai-buildflow-prod` |

### Promotion Workflow

**Automation Level**: Semi-Automated (auto-validation + manual approval)

```yaml
promotion_flow:
  1_contributor_request:
    actor: Contributor
    action: Click "Request Promotion" button
    preconditions:
      - content.status = 'published'
      - content.visibility = 'public'
    result: content.promotion_status = 'pending_validation'

  2_automated_validation:
    actor: System
    trigger: On promotion request
    checks:
      - enrichment_complete: content.enrichment_version IS NOT NULL
      - required_fields: title, description, categories, summary_short populated
      - assets_generated: At least thumbnail asset exists
      - no_active_pipelines: No running pipelines for this content_id
      - quality_threshold: popularity_score >= 0.3 (configurable)
    on_pass: content.promotion_status = 'pending_approval'
    on_fail: content.promotion_status = 'validation_failed' + reasons array

  3_admin_approval:
    actor: Admin (role = 'admin')
    ui: Admin dashboard shows pending approvals queue
    actions:
      - Approve: Triggers copy to Prod
      - Reject: Sets promotion_status = 'rejected' with reason
    audit: All decisions logged with admin_id, timestamp, reason

  4_copy_to_prod:
    actor: System
    trigger: On admin approval
    steps:
      - Snapshot content document (immutable copy)
      - Copy associated assets to Prod storage
      - Insert into Prod Cosmos DB
      - Trigger indexing in Prod search index
    result: content.promotion_status = 'promoted', promoted_at timestamp

  5_post_promotion:
    - Dev content remains editable (new version cycle)
    - Prod content is immutable (read-only)
    - Re-promotion requires new validation cycle
```

---

## 2. Pipeline-First Architecture

### Pipeline Types

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PIPELINE TAXONOMY                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐      │
│  │  ANALYSIS   │──▶│ ENRICHMENT  │──▶│ LOCALIZATION│──▶│   ASSET     │      │
│  │  Pipeline   │   │  Pipeline   │   │  Pipeline   │   │ GENERATION  │      │
│  └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘      │
│        │                 │                 │                  │              │
│        ▼                 ▼                 ▼                  ▼              │
│  Raw extraction    AI enrichment     Translation        Thumbnails          │
│  README parsing    Summarization     Korean docs        Visual assets       │
│  Metadata fetch    Categorization    Localized repo     Preview images      │
│                    Tagging                                                   │
│                                                                              │
│                              ┌─────────────┐                                │
│                              │  INDEXING   │                                │
│                              │  Pipeline   │                                │
│                              └─────────────┘                                │
│                                    │                                        │
│                                    ▼                                        │
│                             Build search index                              │
│                             Vector embeddings                               │
│                             Keyword index                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Pipeline Execution Model

All pipelines execute as **Azure Container Apps Jobs**.

```python
class PipelineType(str, Enum):
    ANALYSIS = "analysis"               # Raw data extraction
    ENRICHMENT = "enrichment"           # AI-powered enhancement
    LOCALIZATION = "localization"       # Translation and adaptation
    ASSET_GENERATION = "asset_generation"  # Thumbnails, previews
    INDEXING = "indexing"               # Search index updates
```

### Global Timeout Configuration

All pipelines share a unified timeout to simplify operations and ensure predictable resource usage.

```yaml
global_timeout:
  value: 10 minutes (600 seconds)
  applies_to: All pipeline types (analysis, enrichment, localization, asset_generation, indexing)
  
  enforcement:
    - Azure Container Apps Jobs: executionTimeoutSeconds = 600
    - Application level: asyncio.wait_for(pipeline.run(), timeout=600)
    - Both layers enforce to catch edge cases
  
  on_timeout:
    - Mark pipeline run as FAILED with error_code: PIPELINE_TIMEOUT
    - Record elapsed_time_seconds in error_details
    - No automatic retry (timeout indicates systemic issue)
    - Alert ops team if timeout rate > 5% in 1 hour window
  
  rationale:
    - 10 minutes sufficient for: GitHub API (seconds), LLM calls (30-60s), indexing (minutes)
    - Single value simplifies Container Apps Job config
    - If pipeline consistently times out, investigate root cause rather than extend limit
  
  exceptions:
    - Batch indexing (content_ids: "all") may use extended timeout via manual override
    - Override requires admin approval and explicit run_id annotation
```

### API → Pipeline Interaction

APIs MUST NOT execute heavy logic synchronously.

```
┌──────────────────────────────────────────────────────────────────┐
│                   API ↔ PIPELINE BOUNDARY                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  SYNCHRONOUS (API)              ASYNCHRONOUS (Pipeline Jobs)     │
│  ─────────────────              ─────────────────────────────    │
│  • Authentication               • GitHub API fetching            │
│  • Content CRUD                 • README parsing                 │
│  • Pipeline enqueue             • LLM calls                      │
│  • Status queries               • Asset generation               │
│  • Search queries               • Index building                 │
│                                 • Localization                   │
│                                                                   │
│  Response: 200/201/400/401      Response: 202 Accepted           │
│  Latency: <500ms                Latency: 5s–5min                 │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### Pipeline Control API

```
POST /api/v1/pipelines                    # Enqueue new pipeline job
GET  /api/v1/pipelines/{run_id}           # Get pipeline status
GET  /api/v1/pipelines/{run_id}/logs      # Get execution logs
POST /api/v1/pipelines/{run_id}/retry     # Retry failed pipeline
POST /api/v1/pipelines/{run_id}/cancel    # Cancel running pipeline
GET  /api/v1/content/{id}/pipeline-history # List pipeline runs for content
```

---

## 3. Pipeline Definitions

### 3.1 Analysis Pipeline

**Purpose**: Extract raw data from GitHub repositories.

```yaml
pipeline_type: analysis
trigger: user_request | scheduled_refresh
execution: Azure Container Apps Job

input_contract:
  source_url: string (required, GitHub URL)
  force_refresh: boolean (default: false)
  correlation_id: string (from API request)

output_contract:
  raw_readme: string (immutable)
  repository_metadata:
    stars: integer
    forks: integer
    watchers: integer
    open_issues: integer
    open_prs: integer
    last_commit_date: datetime
    created_at: datetime
    topics: string[]
    license: string | null
    default_branch: string
  commit_activity:
    total_commits_30d: integer
    total_commits_90d: integer
    contributors_count: integer
  releases:
    latest_version: string | null
    release_count: integer
    last_release_date: datetime | null
  extracted_urls:
    demo_url: string | null
    docs_url: string | null
    video_url: string | null
  extracted_at: datetime

idempotency_strategy:
  key: SHA256(source_url)
  behavior: skip_if_exists_within_24h (unless force_refresh)

retry_policy:
  max_attempts: 3
  backoff: exponential (2s, 4s, 8s)
  retryable_errors: [NETWORK_TIMEOUT, GITHUB_RATE_LIMIT]
  rate_limit_handling:
    strategy: fail_fast_with_retry_after
    behavior: |
      On GITHUB_RATE_LIMIT after max_attempts exhausted:
      1. Mark pipeline run as FAILED with error code GITHUB_RATE_LIMIT
      2. Include retry_after timestamp from X-RateLimit-Reset header
      3. Return 503 with Retry-After header to API caller
      4. User may manually retry after rate limit window expires

enrichment_version: null (raw extraction, no enrichment)
```

### 3.2 Enrichment Pipeline

**Purpose**: Enhance raw data with AI-generated insights.

```yaml
pipeline_type: enrichment
trigger: analysis_completed | manual_trigger | version_bump
execution: Azure Container Apps Job
depends_on: analysis (raw data must exist)

input_contract:
  content_id: UUID
  raw_data_ref: string (pointer to raw extraction)
  enrichment_version: string (e.g., "1.2.0")

output_contract:
  summary:
    short: string (max 200 chars)
    long: string (max 2000 chars)
  categories: string[] (AI-suggested)
  technologies: string[] (detected from content)
  difficulty_level: enum [beginner, intermediate, advanced]
  estimated_time: string (e.g., "2-4 hours")
  prerequisites: string[]
  learning_outcomes: string[]
  popularity_score: float (0.0-1.0)
    # Definition: Normalized composite score reflecting repository health and community adoption.
    # Input signals:
    #   - stars: GitHub star count (primary indicator of community interest)
    #   - last_commit_date: Recency of last commit (maintenance signal)
    #   - commit_activity_30d: Commit count in last 30 days (active development)
    #   - commit_activity_90d: Commit count in last 90 days (sustained activity)
    #   - release_frequency: Number of releases (maturity indicator)
    # Normalization: All inputs normalized to 0.0-1.0 using percentile ranking against catalog.
    # Weighting rationale:
    #   - Stars weighted highest (40%) as primary popularity signal
    #   - Recency weighted second (25%) to favor maintained projects
    #   - Commit activity weighted (20%) to reward active development
    #   - Release frequency weighted (15%) for mature, versioned projects
    # Implementation: See tasks.md T302 for calculation algorithm.
  quality_signals:
    has_documentation: boolean
    has_tests: boolean
    has_ci: boolean
    is_maintained: boolean
  enriched_at: datetime
  model_used: string (e.g., "gpt-4o")

idempotency_strategy:
  key: SHA256(content_id + enrichment_version)
  behavior: replace_if_version_differs

retry_policy:
  max_attempts: 2
  backoff: fixed (5s)
  retryable_errors: [LLM_TIMEOUT, LLM_RATE_LIMIT]

enrichment_version: "1.0.0" (semantic versioning)
```

### 3.3 Localization Pipeline

**Purpose**: Translate and adapt content for Korean market.

```yaml
pipeline_type: localization
trigger: enrichment_completed | manual_trigger
execution: Azure Container Apps Job
depends_on: enrichment

input_contract:
  content_id: UUID
  target_locale: string (e.g., "ko-KR")
  source_fields: string[] (fields to translate)

output_contract:
  translations:
    title_kr: string
    description_kr: string
    summary_kr: string
    prerequisites_kr: string[]
    learning_outcomes_kr: string[]
  localized_at: datetime
  model_used: string

idempotency_strategy:
  key: SHA256(content_id + target_locale + enrichment_version)
  behavior: skip_if_exists

retry_policy:
  max_attempts: 2
  backoff: fixed (3s)

enrichment_version: inherits from enrichment
```

### 3.4 Asset Generation Pipeline

**Purpose**: Create visual and derivative assets.

```yaml
pipeline_type: asset_generation
trigger: enrichment_completed | manual_trigger
execution: Azure Container Apps Job
depends_on: enrichment

input_contract:
  content_id: UUID
  asset_types: enum[] [thumbnail, preview, og_image]

output_contract:
  assets:
    - asset_type: string
      storage_url: string (Azure Blob URL)
      width: integer
      height: integer
      format: string (png, jpg, webp)
      size_bytes: integer
  generated_at: datetime
  model_used: string (for AI-generated assets)

idempotency_strategy:
  key: SHA256(content_id + asset_type + enrichment_version)
  behavior: skip_if_exists

retry_policy:
  max_attempts: 2
  backoff: fixed (5s)

storage:
  container: generated-assets
  path: /{content_id}/{asset_type}.{format}
  cdn_url: https://cdn.buildflow.dev/assets/...
```

### 3.5 Indexing Pipeline

**Purpose**: Build and update search indexes.

```yaml
pipeline_type: indexing
trigger: enrichment_completed | localization_completed | scheduled
execution: Azure Container Apps Job
depends_on: enrichment (optionally localization)

input_contract:
  content_ids: UUID[] (batch) | "all" (full reindex)
  index_targets: enum[] [keyword, vector, hybrid]

output_contract:
  indexed_count: integer
  failed_ids: UUID[]
  index_version: string
  indexed_at: datetime

idempotency_strategy:
  key: SHA256(content_ids_sorted + enrichment_version)
  behavior: upsert

retry_policy:
  max_attempts: 3
  backoff: exponential

search_engine: Azure AI Search
index_fields:
  - title (searchable, filterable)
  - title_kr (searchable, filterable)
  - description (searchable)
  - description_kr (searchable)
  - summary (searchable)
  - categories (filterable, facetable)
  - technologies (filterable, facetable)
  - difficulty_level (filterable, facetable)
  - popularity_score (sortable)
  - stars (sortable)
  - last_commit_date (sortable)
  - content_vector (vector, 1536 dimensions)
```

---

## 4. Pipeline Orchestration

### Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PIPELINE ORCHESTRATION                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  User Request                                                                │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────┐                                                            │
│  │   API       │───▶ 202 Accepted + run_id                                  │
│  │  (enqueue)  │                                                            │
│  └─────────────┘                                                            │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                    │
│  │  ANALYSIS   │────▶│ ENRICHMENT  │────▶│ LOCALIZATION│                    │
│  │    Job      │     │    Job      │     │    Job      │                    │
│  └─────────────┘     └─────────────┘     └─────────────┘                    │
│       │                    │                    │                           │
│       │                    │                    │                           │
│       │                    ▼                    ▼                           │
│       │              ┌─────────────┐     ┌─────────────┐                    │
│       │              │   ASSET     │     │  INDEXING   │                    │
│       │              │ GENERATION  │     │    Job      │                    │
│       │              └─────────────┘     └─────────────┘                    │
│       │                    │                    │                           │
│       ▼                    ▼                    ▼                           │
│  ┌─────────────────────────────────────────────────────┐                    │
│  │                  Cosmos DB                          │                    │
│  │  • Raw data (immutable)                            │                    │
│  │  • Enriched data (versioned)                       │                    │
│  │  • Pipeline runs (audit trail)                     │                    │
│  └─────────────────────────────────────────────────────┘                    │
│                              │                                              │
│                              ▼                                              │
│                    ┌─────────────────┐                                      │
│                    │ Azure AI Search │                                      │
│                    │ (keyword+vector)│                                      │
│                    └─────────────────┘                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Pipeline Chaining

Pipelines can be chained automatically or triggered manually.

```python
PIPELINE_CHAIN = {
    "full_ingestion": [
        "analysis",
        "enrichment", 
        "localization",
        "asset_generation",
        "indexing"
    ],
    "refresh_enrichment": [
        "enrichment",
        "localization", 
        "indexing"
    ],
    "reindex_only": [
        "indexing"
    ]
}
```

### Concurrency Control

To prevent data corruption when multiple pipelines target the same content:

```yaml
concurrency_strategy: sequential_queue

rules:
  - Same content_id pipelines execute one at a time
  - Queue order: FIFO based on created_at timestamp
  - Implementation: Service Bus session-based messaging
    session_id: content_id (ensures ordered delivery per content)
  - If pipeline A (enrichment) is running for content X,
    pipeline B (localization) for content X waits in queue
  - Different content_ids execute in parallel (no contention)

queue_behavior:
  max_queue_depth: 10 per content_id
  queue_timeout: 30 minutes (message expires if not processed)
  dead_letter: Messages exceeding timeout moved to DLQ

monitoring:
  - Track queue depth per content_id
  - Alert if queue depth > 5 (potential bottleneck)
  - Log wait_time_ms for queued pipelines
```

---

## 5. Data Model (Constitution v2.0.0 Aligned)

### PipelineRun

```python
class PipelineRun:
    id: UUID                          # Primary key
    pipeline_type: PipelineType       # analysis, enrichment, etc.
    status: PipelineStatus            # pending, running, completed, failed
    enrichment_version: str           # Semantic version (e.g., "1.2.0")
    
    # Input/Output
    input_params: dict                # Job input parameters
    output_summary: dict | None       # Summary of results
    error_details: dict | None        # Error info if failed
    
    # Relations
    content_id: UUID | None           # Related content (if applicable)
    triggered_by: UUID | None         # User ID or system
    parent_run_id: UUID | None        # For chained pipelines
    
    # Timestamps
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    
    # Execution metadata
    job_id: str                       # Azure Container Apps Job ID
    attempt_number: int               # Current retry attempt
    correlation_id: str               # Request correlation
```

### Content (Extended)

```python
class Content:
    id: UUID
    
    # Core fields (unchanged)
    title: str
    title_kr: str | None
    description: str
    description_kr: str | None
    url: str
    source_url: str
    categories: list[str]
    technologies: list[str]
    prerequisites: str | None
    
    # Ownership
    contributor_id: UUID
    status: ContentStatus             # draft, published, archived
    visibility: Visibility            # public, internal
    
    # Versioning (NEW)
    enrichment_version: str | None    # Current enrichment version
    last_enriched_at: datetime | None
    last_indexed_at: datetime | None
    
    # Raw data reference (NEW)
    raw_extraction_id: UUID | None    # Points to immutable raw data
    
    # Enriched data (NEW)
    summary_short: str | None
    summary_long: str | None
    difficulty_level: str | None
    estimated_time: str | None
    learning_outcomes: list[str]
    popularity_score: float | None
    
    # Repository signals (NEW)
    stars: int | None
    forks: int | None
    last_commit_date: datetime | None
    is_maintained: bool | None
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
```

### RawExtraction (NEW - Immutable)

```python
class RawExtraction:
    id: UUID
    source_url: str
    
    # Immutable raw data
    readme_content: str
    readme_hash: str                  # SHA256 for change detection
    
    repository_metadata: dict         # Stars, forks, etc. at extraction time
    commit_activity: dict
    releases: dict
    extracted_urls: dict
    
    # Extraction metadata
    extracted_at: datetime
    github_api_version: str
    run_id: UUID                      # Pipeline run that created this
```

### GeneratedAsset

```python
class GeneratedAsset:
    id: UUID
    content_id: UUID
    run_id: UUID                      # Pipeline run that created this
    
    asset_type: AssetType             # thumbnail, summary, translation, etc.
    storage_url: str                  # Azure Blob URL
    cdn_url: str | None               # CDN URL for public assets
    
    # Metadata
    is_generated: bool = True
    model_used: str                   # e.g., "gpt-4o", "dall-e-3"
    visibility: Visibility            # public, internal
    
    # Dimensions (for images)
    width: int | None
    height: int | None
    format: str | None
    size_bytes: int | None
    
    # Versioning
    enrichment_version: str
    created_at: datetime
```

---

## 6. Search & Indexing

### Azure AI Search Configuration

```yaml
index_name: buildflow-content
search_mode: hybrid (keyword + vector)

fields:
  # Identifiers
  - name: id
    type: Edm.String
    key: true
    
  # Searchable text
  - name: title
    type: Edm.String
    searchable: true
    analyzer: en.microsoft
    
  - name: title_kr
    type: Edm.String
    searchable: true
    analyzer: ko.microsoft
    
  - name: description
    type: Edm.String
    searchable: true
    
  - name: summary
    type: Edm.String
    searchable: true
    
  # Filterable/Facetable
  - name: categories
    type: Collection(Edm.String)
    filterable: true
    facetable: true
    
  - name: technologies
    type: Collection(Edm.String)
    filterable: true
    facetable: true
    
  - name: difficulty_level
    type: Edm.String
    filterable: true
    facetable: true
    
  - name: visibility
    type: Edm.String
    filterable: true
    
  # Sortable metrics
  - name: popularity_score
    type: Edm.Double
    sortable: true
    
  - name: stars
    type: Edm.Int32
    sortable: true
    filterable: true
    
  - name: last_commit_date
    type: Edm.DateTimeOffset
    sortable: true
    filterable: true
    
  # Vector field
  - name: content_vector
    type: Collection(Edm.Single)
    dimensions: 1536
    vectorSearchProfile: default-profile

vector_search:
  algorithm: hnsw
  metric: cosine
  
scoring_profiles:
  - name: popularity-boost
    functions:
      - type: magnitude
        fieldName: popularity_score
        boost: 2.0
      - type: freshness
        fieldName: last_commit_date
        boost: 1.5
```

### Search API

```
GET /api/v1/search
  ?q={query}
  &mode=hybrid|keyword|vector
  &categories[]={category}
  &technologies[]={tech}
  &difficulty={level}
  &min_stars={n}
  &sort=relevance|popularity|recent
  &limit={n}
  &offset={n}
```

---

## 7. Role-Based UX & Visibility

### Visibility Model

Content visibility controls who can access content items across all system surfaces.

```python
class Visibility(str, Enum):
    PUBLIC = "public"       # Anyone can see (including anonymous users)
    INTERNAL = "internal"   # Logged-in users only
```

**Visibility Assignment Rules:**
- Default visibility for new content: `INTERNAL`
- Contributors can set visibility when creating or editing content
- Only content with `status: published` respects visibility; drafts are always contributor-only
- Visibility can be changed by the content owner or admin
- Promotion to Prod requires `visibility: PUBLIC` (internal content stays in Dev only)

### Role Capabilities

| Capability | Anonymous | User (logged in) | Contributor |
|------------|-----------|------------------|-------------|
| Browse public content | ✅ | ✅ | ✅ |
| Search public content | ✅ | ✅ | ✅ |
| View internal content | ❌ | ✅ | ✅ |
| Use AI assistant | ❌ | ✅ | ✅ |
| Create content | ❌ | ❌ | ✅ |
| Edit own content | ❌ | ❌ | ✅ |
| Trigger analysis | ❌ | ❌ | ✅ |
| Trigger reprocessing | ❌ | ❌ | ✅ |
| View pipeline history | ❌ | ❌ | ✅ |
| See ownership labels | ❌ | ❌ | ✅ |
| Mark for promotion | ❌ | ❌ | ✅ |

### Content Field Visibility by Role

Not all fields are exposed to all users. This table defines field-level access control:

| Field | Anonymous | User | Contributor |
|-------|-----------|------|-------------|
| `id` | ✅ | ✅ | ✅ |
| `title` | ✅ | ✅ | ✅ |
| `title_kr` | ✅ | ✅ | ✅ |
| `description` | ✅ | ✅ | ✅ |
| `description_kr` | ✅ | ✅ | ✅ |
| `url` | ✅ | ✅ | ✅ |
| `source_url` | ❌ | ✅ | ✅ |
| `categories` | ✅ | ✅ | ✅ |
| `technologies` | ✅ | ✅ | ✅ |
| `difficulty_level` | ✅ | ✅ | ✅ |
| `summary_short` | ✅ | ✅ | ✅ |
| `summary_long` | ❌ | ✅ | ✅ |
| `prerequisites` | ❌ | ✅ | ✅ |
| `learning_outcomes` | ❌ | ✅ | ✅ |
| `popularity_score` | ✅ | ✅ | ✅ |
| `stars` | ✅ | ✅ | ✅ |
| `contributor_id` | ❌ | ❌ | ✅ |
| `status` | ❌ | ❌ | ✅ |
| `visibility` | ❌ | ❌ | ✅ |
| `enrichment_version` | ❌ | ❌ | ✅ |
| `raw_extraction_id` | ❌ | ❌ | ✅ |
| `last_enriched_at` | ❌ | ❌ | ✅ |
| `last_indexed_at` | ❌ | ❌ | ✅ |
| `created_at` | ✅ | ✅ | ✅ |
| `updated_at` | ❌ | ❌ | ✅ |

### Visibility Impact on System Components

#### Search Indexing

```yaml
indexing_rules:
  - All content indexed in Dev (both public and internal)
  - Only PUBLIC content indexed in Prod
  - Search queries MUST apply visibility filter:
      anonymous: visibility = 'public'
      authenticated: visibility IN ('public', 'internal')
  - Facet counts MUST respect visibility filter
```

#### AI Assistant Responses

```yaml
assistant_visibility_rules:
  - Anonymous users: Cannot use assistant (401 Unauthorized)
  - Authenticated users:
      - Query only searches PUBLIC + INTERNAL content
      - Citations only include accessible content
      - MUST NOT reveal internal content IDs to anonymous context
  - Contributor context:
      - Can ask about own draft content
      - Can reference pipeline history in queries
  - All responses:
      - MUST cite source content_id
      - MUST NOT hallucinate content references
      - MUST respect visibility at query time (not cached)
```

#### Content Cards and Contributor Controls

```yaml
ui_visibility_rules:
  content_card:
    - Anonymous: Show title, description, categories, stars, difficulty
    - User: Add source_url, summary_long, prerequisites, learning outcomes
    - Contributor: Add ownership badge, enrichment version, pipeline controls
  
  contributor_controls:
    - Visible only when: userRole === 'contributor' AND content.contributor_id === currentUser.id
    - Controls:
        - Edit button
        - Reprocess button (triggers enrichment chain)
        - View Pipeline History link
        - Visibility toggle (public/internal)
        - Mark for Promotion button (if published + public)
  
  internal_content_badge:
    - Show "Internal" badge on cards when visibility === 'internal'
    - Only visible to authenticated users
```

### UI Adaptations by Role

```typescript
// Frontend role-based rendering
interface ContentCardProps {
  content: Content;
  userRole: 'anonymous' | 'user' | 'contributor';
  isOwner: boolean;
}

function ContentCard({ content, userRole, isOwner }: ContentCardProps) {
  return (
    <Card>
      <Title>{content.title}</Title>
      <Description>{content.description}</Description>
      
      {/* Internal badge for non-public content */}
      {content.visibility === 'internal' && (
        <Badge variant="outline">Internal</Badge>
      )}
      
      {/* Logged-in users: extended content */}
      {userRole !== 'anonymous' && (
        <>
          <SummaryLong>{content.summary_long}</SummaryLong>
          <Prerequisites items={content.prerequisites} />
          <LearningOutcomes items={content.learning_outcomes} />
          <AskAssistantButton content={content} />
        </>
      )}
      
      {/* Contributor + owner: management controls */}
      {userRole === 'contributor' && isOwner && (
        <>
          <OwnershipBadge owner={content.contributor_id} />
          <EnrichmentVersion version={content.enrichment_version} />
          <PipelineHistoryLink contentId={content.id} />
          <ReprocessButton contentId={content.id} />
          <VisibilityToggle 
            current={content.visibility} 
            onToggle={handleVisibilityChange} 
          />
          {content.status === 'published' && content.visibility === 'public' && (
            <PromoteButton contentId={content.id} />
          )}
        </>
      )}
    </Card>
  );
}
```

### API Response Filtering

The API MUST filter response fields based on caller role:

```python
def filter_content_response(content: Content, role: str, user_id: UUID | None) -> dict:
    """Filter content fields based on caller role."""
    
    # Base fields visible to all
    base_fields = [
        'id', 'title', 'title_kr', 'description', 'description_kr',
        'url', 'categories', 'technologies', 'difficulty_level',
        'summary_short', 'popularity_score', 'stars', 'created_at'
    ]
    
    # Additional fields for authenticated users
    user_fields = [
        'source_url', 'summary_long', 'prerequisites', 'learning_outcomes',
        'forks', 'last_commit_date', 'is_maintained', 'estimated_time'
    ]
    
    # Contributor-only fields (own content or all for admins)
    contributor_fields = [
        'contributor_id', 'status', 'visibility', 'enrichment_version',
        'raw_extraction_id', 'last_enriched_at', 'last_indexed_at', 'updated_at'
    ]
    
    allowed_fields = base_fields.copy()
    
    if role in ['user', 'contributor']:
        allowed_fields.extend(user_fields)
    
    if role == 'contributor':
        # Contributors see metadata only on own content
        if user_id and content.contributor_id == user_id:
            allowed_fields.extend(contributor_fields)
    
    return {k: v for k, v in content.dict().items() if k in allowed_fields}
```

---

## 8. AI Assistant Integration

### Assistant Capabilities

```yaml
assistant_name: BuildFlow Assistant
purpose: Help users discover and understand Azure learning content

capabilities:
  - answer_questions:
      description: Answer questions using indexed content
      data_source: Azure AI Search (internal first)
      fallback: External search (if enabled)
      
  - recommend_content:
      description: Suggest relevant repositories and learning paths
      based_on: user query, browsing history, skill level
      
  - explain_content:
      description: Explain how to use a selected content item
      context: content details, prerequisites, related items
      
  - suggest_enrichment:
      description: Trigger search + enrichment if content is missing
      action: Propose adding new content to catalog

constraints:
  - MUST respect visibility boundaries
  - MUST cite sources for all recommendations
  - MUST NOT fabricate content references
  - MUST prefer internal indexed knowledge
  - SHOULD acknowledge when information is uncertain

fallback_behavior:
  trigger: Internal search returns < 3 relevant results (relevance_score < 0.5)
  strategy: external_search_fallback
  implementation:
    1. Acknowledge: "I couldn't find enough in our catalog, searching external sources..."
    2. Execute Bing Web Search API query (Azure Cognitive Services)
    3. Filter results to trusted domains:
       - docs.microsoft.com, learn.microsoft.com
       - github.com (official repos only)
       - dev.to, medium.com (tech articles)
       - stackoverflow.com
    4. Return top 3 external results with:
       - title, url, snippet
       - source_type: "external" (clearly marked)
       - disclaimer: "External content not verified by BuildFlow"
  rate_limit: 10 external searches per user per hour
  logging: Log all external fallbacks for catalog gap analysis
  future_enhancement: Offer "Add to BuildFlow" for promising external repos
```

### Assistant Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AI ASSISTANT ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  User Query                                                                  │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────┐                                                            │
│  │  Assistant  │───▶ Understand intent                                      │
│  │   Service   │                                                            │
│  └─────────────┘                                                            │
│       │                                                                      │
│       ├──────────────────┬──────────────────┐                               │
│       ▼                  ▼                  ▼                               │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                        │
│  │   Search    │   │   Content   │   │   LLM       │                        │
│  │   Index     │   │   Store     │   │  (GPT-4o)   │                        │
│  │ (AI Search) │   │ (Cosmos DB) │   │             │                        │
│  └─────────────┘   └─────────────┘   └─────────────┘                        │
│       │                  │                  │                               │
│       └──────────────────┴──────────────────┘                               │
│                          │                                                  │
│                          ▼                                                  │
│                   Generate Response                                         │
│                   (with citations)                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Assistant API

```
POST /api/v1/assistant/chat
{
  "message": "What's a good tutorial for AKS beginners?",
  "conversation_id": "uuid (optional)",
  "context": {
    "current_content_id": "uuid (optional)",
    "filters": { "difficulty": "beginner" }
  }
}

Response:
{
  "success": true,
  "data": {
    "response": "For AKS beginners, I recommend...",
    "citations": [
      { "content_id": "uuid", "title": "AKS Workshop", "relevance": 0.95 }
    ],
    "suggested_content": [...],
    "conversation_id": "uuid"
  }
}
```

---

## 9. Pipeline Execution Details

### Analysis Pipeline Steps

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ANALYSIS PIPELINE (DETAILED)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  [1] VALIDATE         [2] FETCH           [3] EXTRACT         [4] STORE    │
│  ────────────────────────────────────────────────────────────────────────   │
│  URL validation       GitHub API calls    Parse README        Save to DB    │
│  Domain allowlist     README.md           Repo metadata                     │
│  Duplicate check      Repo API            Commit activity                   │
│                       Releases API        Detect URLs                       │
│                                                                              │
│       │                    │                    │                  │        │
│       ▼                    ▼                    ▼                  ▼        │
│  ┌─────────┐         ┌──────────┐         ┌──────────┐       ┌──────────┐   │
│  │validate │────────▶│ fetching │────────▶│extracting│──────▶│  stored  │   │
│  └─────────┘         └──────────┘         └──────────┘       └──────────┘   │
│       │                    │                    │                           │
│       │              FAIL: fetch_error    FAIL: parse_error                 │
│       │              FAIL: not_found                                        │
│       │              FAIL: rate_limit                                       │
│                                                                              │
│  ❌ FAIL: invalid_url                                                       │
│  ❌ FAIL: blocked_domain                                                    │
│  ❌ FAIL: duplicate (within 24h, no force)                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### GitHub Data Extraction

```python
class GitHubExtractor:
    """Extract comprehensive data from GitHub repository."""
    
    async def extract(self, repo_url: str) -> RawExtraction:
        owner, repo = parse_github_url(repo_url)
        
        # Parallel API calls
        readme, repo_info, commits, releases = await asyncio.gather(
            self.fetch_readme(owner, repo),
            self.fetch_repo_info(owner, repo),
            self.fetch_commit_activity(owner, repo),
            self.fetch_releases(owner, repo),
        )
        
        return RawExtraction(
            source_url=repo_url,
            readme_content=readme.content,
            readme_hash=sha256(readme.content),
            repository_metadata={
                "stars": repo_info.stargazers_count,
                "forks": repo_info.forks_count,
                "watchers": repo_info.watchers_count,
                "open_issues": repo_info.open_issues_count,
                "topics": repo_info.topics,
                "license": repo_info.license.spdx_id if repo_info.license else None,
                "default_branch": repo_info.default_branch,
                "created_at": repo_info.created_at,
                "updated_at": repo_info.updated_at,
            },
            commit_activity={
                "total_commits_30d": commits.count_30d,
                "total_commits_90d": commits.count_90d,
                "last_commit_date": commits.last_commit_date,
                "contributors_count": commits.contributors_count,
            },
            releases={
                "latest_version": releases[0].tag_name if releases else None,
                "release_count": len(releases),
                "last_release_date": releases[0].published_at if releases else None,
            },
            extracted_urls=self.extract_urls_from_readme(readme.content),
            extracted_at=datetime.utcnow(),
        )
    
    def extract_urls_from_readme(self, content: str) -> dict:
        """Detect demo, docs, and video URLs from README."""
        return {
            "demo_url": self.find_demo_url(content),
            "docs_url": self.find_docs_url(content),
            "video_url": self.find_video_url(content),
        }
```

### Status Transitions

```python
class PipelineStatus(str, Enum):
    PENDING = "pending"           # Queued, waiting to start
    RUNNING = "running"           # Currently executing
    COMPLETED = "completed"       # Successfully finished
    FAILED = "failed"             # Terminal failure
    CANCELLED = "cancelled"       # User cancelled
    RETRYING = "retrying"         # Failed, attempting retry

# Valid transitions
VALID_TRANSITIONS = {
    "pending": ["running", "cancelled"],
    "running": ["completed", "failed", "cancelled"],
    "failed": ["retrying", "pending"],  # pending = manual retry
    "retrying": ["running"],
    "completed": [],  # Terminal
    "cancelled": [],  # Terminal
}
```

---

## 10. Security Constraints

### SSRF Prevention

```python
GITHUB_DOMAIN_ALLOWLIST = [
    "github.com",
    "raw.githubusercontent.com",
    "api.github.com"
]

def validate_github_url(url: str) -> bool:
    parsed = urlparse(url)
    
    # Must be HTTPS
    if parsed.scheme != "https":
        raise ValidationError("HTTPS required")
    
    # Must be in allowlist
    if parsed.netloc not in GITHUB_DOMAIN_ALLOWLIST:
        raise ValidationError("Domain not allowed", code="BLOCKED_DOMAIN")
    
    # No IP addresses
    if is_ip_address(parsed.netloc):
        raise ValidationError("IP addresses not allowed")
    
    # Path must look like a repo
    if not re.match(r"^/[\w\-\.]+/[\w\-\.]+/?", parsed.path):
        raise ValidationError("Invalid repository path")
    
    return True
```

### Rate Limiting (Pipeline-specific)

| Action | Limit | Window |
|--------|-------|--------|
| Enqueue analysis pipeline | 10 | per user per hour |
| Force reprocessing | 3 | per content per day |
| Concurrent pipelines | 5 | per user |
| AI assistant queries | 30 | per user per minute |

---

## 11. Polling for Status Updates

### Decision: **Polling with Exponential Backoff**

| Factor | Polling | WebSocket |
|--------|---------|-----------|
| Complexity | Simple | Requires connection management |
| Scaling | Stateless (fits Container Apps) | Sticky sessions needed |
| Constitution compliance | ✅ Stateless | ❌ Stateful connections |
| Typical pipeline time | 5s–5min | More efficient for long jobs |
| Mobile/offline friendly | ✅ Resumable | ❌ Reconnection logic |

### Polling Strategy

```typescript
// Frontend polling logic
const POLL_INTERVALS = [500, 1000, 2000, 3000, 5000, 10000]; // ms
const MAX_POLL_TIME = 300000; // 5 minutes timeout

async function pollPipelineStatus(runId: string) {
  let attempt = 0;
  const startTime = Date.now();
  
  while (Date.now() - startTime < MAX_POLL_TIME) {
    const response = await fetch(`/api/v1/pipelines/${runId}`);
    const { data } = await response.json();
    
    if (['completed', 'failed', 'cancelled'].includes(data.status)) {
      return data;
    }
    
    const interval = POLL_INTERVALS[Math.min(attempt, POLL_INTERVALS.length - 1)];
    await sleep(interval);
    attempt++;
  }
  
  throw new Error('Pipeline timeout');
}
```

---

## 12. Error Codes

| Code | HTTP | Description |
|------|------|-------------|
| `INVALID_URL` | 400 | URL format invalid |
| `BLOCKED_DOMAIN` | 400 | Domain not in allowlist |
| `DUPLICATE_PIPELINE` | 409 | Same pipeline already running |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many pipeline requests |
| `CONCURRENT_LIMIT` | 429 | Too many running pipelines |
| `GITHUB_NOT_FOUND` | 404 | Repository or README not found |
| `GITHUB_RATE_LIMIT` | 503 | GitHub API rate limit hit |
| `LLM_TIMEOUT` | 504 | LLM processing timeout |
| `PIPELINE_TIMEOUT` | 504 | Overall pipeline exceeded timeout |
| `ENRICHMENT_FAILED` | 500 | AI enrichment failed |
| `INDEXING_FAILED` | 500 | Search indexing failed |

---

## 13. Constitution v2.0.0 Compliance Checklist

- [x] **Azure-first**: All execution on Azure Container Apps / Jobs
- [x] **Pipeline-first**: Heavy processing in async jobs, not APIs
- [x] **Stateless APIs**: JWT auth, no sessions
- [x] **Dev/Prod separation**: Isolated environments defined
- [x] **Enrichment versioning**: `enrichment_version` on all derived data
- [x] **Raw data immutability**: `RawExtraction` is immutable
- [x] **Reprocessing support**: Can re-run without re-collecting
- [x] **Job idempotency**: Defined per pipeline type
- [x] **Job reliability**: Retry policies, status tracking
- [x] **Generated assets**: Marked, versioned, visibility-aware
- [x] **AI assistant**: Architecture defined, respects boundaries
- [x] **Search indexing**: Azure AI Search with hybrid mode
- [x] **Role-based UX**: Public vs contributor capabilities
- [x] **Correlation ID**: In all logs and pipeline runs
- [x] **Security headers**: Standard response envelope

---

## 14. Next Steps

1. **Phase 1**: Implement Analysis Pipeline (Container Apps Job)
2. **Phase 2**: Implement Enrichment Pipeline with LLM integration
3. **Phase 3**: Azure AI Search integration
4. **Phase 4**: Localization and Asset Generation pipelines
5. **Phase 5**: AI Assistant service
6. **Phase 6**: Dev → Prod promotion workflow
