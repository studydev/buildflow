# Tasks: Pipeline-First Backend Architecture

**Input**: [backend-architecture/stack.md](../backend-architecture/stack.md), [github-analysis-pipeline/design.md](../github-analysis-pipeline/design.md)  
**Constitution**: v2.0.0 compliant  
**Goal**: Azure-first, Pipeline-first backend with Container Apps Jobs  
**Strategy**: Pipeline-oriented milestones separating Control Plane (API) from Data Plane (Jobs)

---

## Overview

This task list follows Constitution v2.0.0:
- **Azure-first**: All execution on Azure-managed infrastructure
- **Pipeline-first**: Heavy processing in async Container Apps Jobs
- **Control/Data Plane separation**: APIs control, Jobs execute

### Task Markers

| Marker | Meaning |
|--------|---------|
| `[x]` | Completed |
| `[ ]` | Not started |
| `[P]` | Can run in parallel (no blocking dependencies) |
| `[BLOCKING]` | Must complete before dependent tasks |
| `[DEV-ONLY]` | Only applicable to Dev environment |
| `[DEPRECATED]` | Replaced by new approach (see migration notes) |
| `[FUTURE]` | Placeholder for future capability |
| `CP` | Control Plane (API) owner |
| `DP` | Data Plane (Jobs) owner |

### Task Format

Each task includes:
```
- [ ] **T###** [Markers] Description
  - **Owner**: CP/DP | **Env**: DEV-ONLY/ALL
  - **Files**: path/to/files
  - **Depends**: T### → T### (dependencies)
  - **Validation**: CLI command or test
  - **DoD**: Definition of Done criteria
```

---

## Milestone 0: Foundation (Completed)

**Status**: ✅ Complete (from previous MVP)

These tasks were completed in the initial MVP and remain valid:

- [x] **T001** FastAPI project structure
- [x] **T002** Response envelope and error handling
- [x] **T003** Correlation ID middleware
- [x] **T004** Cosmos DB client
- [x] **T005** RSA keys and JWT utilities
- [x] **T006-T013** Auth API (OTP + JWT)
- [x] **T014-T018** Frontend auth integration
- [x] **T019-T023** Content API (CRUD)
- [x] **T024-T028** Frontend content integration

---

## Milestone 1: Pipeline Infrastructure [DEV-ONLY]

**Deliverable**: Azure Container Apps Jobs infrastructure with Service Bus triggering

### Milestone 1 Definition of Done (DoD)
- [x] All Azure resources (Service Bus, Container Apps Jobs, Blob Storage, AI Search) provisioned via Bicep
- [x] PipelineRun, RawExtraction, GeneratedAsset models created with CRUD operations
- [x] BasePipeline class with lifecycle hooks implemented
- [x] Pipeline Control API (enqueue, status, retry, cancel) functional
- [x] Pipeline runner can execute any pipeline type from queue message
- [x] CI/CD builds and pushes both `api` and `pipeline` Docker images

---

### Phase 1.1: Azure Infrastructure (Bicep)

- [x] **T100** [BLOCKING] Create Azure Service Bus namespace and topics
  - **Owner**: Infrastructure | **Env**: DEV-ONLY
  - **Files**: `infra/modules/servicebus.bicep`
  - **Depends**: None (first task)
  - **Resources**: 
    - Namespace: `sb-buildflow-dev`
    - Topic: `pipeline-triggers` with subscriptions per pipeline type (analysis, enrichment, localization, asset_generation, indexing)
    - Topic: `pipeline-events` for monitoring
  - **Validation**: 
    ```bash
    az servicebus topic show --namespace-name sb-buildflow-dev --name pipeline-triggers --resource-group rg-buildflow-dev
    az servicebus subscription list --namespace-name sb-buildflow-dev --topic-name pipeline-triggers --resource-group rg-buildflow-dev
    ```
  - **DoD**: 
    - Service Bus namespace exists in Dev resource group
    - `pipeline-triggers` topic has 5 subscriptions (one per pipeline type)
    - `pipeline-events` topic exists for monitoring
    - Managed identity access configured

- [x] **T101** [BLOCKING] Create Container Apps Jobs for each pipeline
  - **Owner**: Infrastructure | **Env**: DEV-ONLY
  - **Files**: `infra/modules/container-apps-jobs.bicep`
  - **Depends**: T100 (needs Service Bus for trigger)
  - **Resources**:
    - `caj-analysis-dev` (triggered by analysis subscription)
    - `caj-enrichment-dev` (triggered by enrichment subscription)
    - `caj-localization-dev` (triggered by localization subscription)
    - `caj-asset-generation-dev` (triggered by asset_generation subscription)
    - `caj-indexing-dev` (triggered by indexing subscription)
  - **Config**: Service Bus trigger, managed identity, Cosmos DB/Key Vault access
  - **Validation**: 
    ```bash
    az containerapp job show --name caj-analysis-dev --resource-group rg-buildflow-dev
    az containerapp job show --name caj-enrichment-dev --resource-group rg-buildflow-dev
    ```
  - **DoD**:
    - All 5 Container Apps Jobs created
    - Each job configured with correct Service Bus subscription trigger
    - Managed identity has access to Cosmos DB, Key Vault, Blob Storage

- [x] **T102** [P] Create Azure Blob Storage for generated assets
  - **Owner**: Infrastructure | **Env**: DEV-ONLY
  - **Files**: `infra/modules/storage.bicep`
  - **Depends**: None (parallel with T101)
  - **Resources**: 
    - Account: `stbuildflowdev`
    - Container: `generated-assets` (for thumbnails, images)
    - Container: `raw-extractions` (for immutable raw data backups)
  - **Validation**: 
    ```bash
    az storage container list --account-name stbuildflowdev --auth-mode login
    ```
  - **DoD**:
    - Storage account exists with correct naming
    - Both containers created with appropriate access policies
    - Managed identity access configured

- [x] **T103** [P] Create Azure AI Search service
  - **Owner**: Infrastructure | **Env**: DEV-ONLY
  - **Files**: `infra/modules/search.bicep`
  - **Depends**: None (parallel with T101, T102)
  - **Resources**: `search-buildflow-dev`
  - **Config**: Standard tier, hybrid search enabled
  - **Validation**: 
    ```bash
    az search service show --name search-buildflow-dev --resource-group rg-buildflow-dev
    ```
  - **DoD**:
    - AI Search service exists in Dev resource group
    - Standard tier configured
    - Admin key accessible via Key Vault

- [x] **T104** [BLOCKING] Update main Bicep to include new modules
  - **Owner**: Infrastructure | **Env**: DEV-ONLY
  - **Files**: `infra/main.bicep`, `infra/main.parameters.json`, `infra/parameters.dev.json`
  - **Depends**: T100 → T101 → T102 → T103 (all modules defined)
  - **Validation**: 
    ```bash
    az deployment group create --resource-group rg-buildflow-dev --template-file infra/main.bicep --parameters infra/parameters.dev.json --what-if
    az deployment group create --resource-group rg-buildflow-dev --template-file infra/main.bicep --parameters infra/parameters.dev.json
    ```
  - **DoD**:
    - `az deployment group create --what-if` succeeds without errors
    - All new resources provisioned in single deployment
    - No orphaned resources from previous deployments

**🎯 Phase 1.1 Checkpoint**: Azure infrastructure ready for pipeline execution

---

### Phase 1.2: Pipeline Data Models

- [x] **T105** [BLOCKING] Create PipelineRun model and repository
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/models/pipeline_run.py`, `backend/app/repositories/pipeline_repo.py`, `backend/app/schemas/pipeline.py`
  - **Depends**: T104 (infrastructure deployed)
  - **Schema** (per design.md §5 PipelineRun):
    ```python
    id: UUID                      # Primary key
    pipeline_type: PipelineType   # analysis, enrichment, localization, asset_generation, indexing
    status: PipelineStatus        # pending, running, completed, failed, cancelled
    enrichment_version: str       # Semantic version (e.g., "1.2.0")
    input_params: dict            # Job input parameters
    output_summary: dict | None   # Summary of results
    error_details: dict | None    # Error info if failed
    content_id: UUID | None       # Related content
    triggered_by: UUID | None     # User ID or system
    parent_run_id: UUID | None    # For chained pipelines
    job_id: str                   # Azure Container Apps Job execution ID
    attempt_number: int           # Current retry attempt (default: 1)
    correlation_id: str           # Request correlation
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    ```
  - **Partition Key**: `pipeline_type` (for efficient querying by type)
  - **Validation**: 
    ```bash
    pytest backend/tests/integration/test_pipeline_repo.py -v
    ```
  - **DoD**:
    - Model matches design.md §5 PipelineRun schema exactly
    - Repository has: `create()`, `get_by_id()`, `update_status()`, `list_by_content_id()`, `list_by_type()`
    - Integration test passes with Cosmos DB

- [x] **T106** [P] Create RawExtraction model and repository
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/models/raw_extraction.py`, `backend/app/repositories/raw_extraction_repo.py`
  - **Depends**: T105 (shared base patterns)
  - **Schema** (per design.md §5 RawExtraction - **IMMUTABLE**):
    ```python
    id: UUID
    source_url: str
    source_url_hash: str          # SHA256 for deduplication
    readme_content: str
    readme_hash: str              # SHA256 for change detection
    repository_metadata: dict     # Stars, forks, etc.
    commit_activity: dict
    releases: dict
    extracted_urls: dict
    extracted_at: datetime
    github_api_version: str
    run_id: UUID                  # Pipeline run that created this
    ```
  - **Immutability**: Repository MUST NOT have `update()` method
  - **Partition Key**: `source_url_hash`
  - **Validation**: 
    ```bash
    pytest backend/tests/integration/test_raw_extraction_repo.py -v
    # Test: create succeeds, update raises ImmutableRecordError
    ```
  - **DoD**:
    - Model matches design.md §5 RawExtraction schema exactly
    - Repository has only: `create()`, `get_by_id()`, `get_by_source_url_hash()`, `exists()`
    - **NO** `update()` method (enforces immutability)
    - Integration test confirms immutability constraint

- [x] **T107** [P] Create GeneratedAsset model and repository
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/models/generated_asset.py`, `backend/app/repositories/asset_repo.py`
  - **Depends**: T105 (shared base patterns)
  - **Schema** (per design.md §5 GeneratedAsset):
    ```python
    id: UUID
    content_id: UUID
    run_id: UUID                  # Pipeline run that created this
    asset_type: AssetType         # thumbnail, preview, og_image
    storage_url: str              # Azure Blob URL
    cdn_url: str | None           # CDN URL for public assets
    is_generated: bool = True
    model_used: str               # e.g., "gpt-4o", "dall-e-3"
    visibility: Visibility        # public, internal
    width: int | None
    height: int | None
    format: str | None            # png, jpg, webp
    size_bytes: int | None
    enrichment_version: str
    created_at: datetime
    ```
  - **Partition Key**: `content_id`
  - **Validation**: 
    ```bash
    pytest backend/tests/integration/test_asset_repo.py -v
    ```
  - **DoD**:
    - Model matches design.md §5 GeneratedAsset schema exactly
    - Repository has: `create()`, `get_by_id()`, `list_by_content_id()`, `delete()`
    - Integration test passes

**🎯 Phase 1.2 Checkpoint**: Pipeline data models in place

---

### Phase 1.3: Pipeline Base Classes

- [x] **T108** [BLOCKING] Create BasePipeline class with lifecycle hooks
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/pipelines/__init__.py`, `backend/app/pipelines/base.py`
  - **Depends**: T105 (PipelineRun model for status updates)
  - **Methods**:
    ```python
    class BasePipeline(ABC):
        # Lifecycle
        async def run(self, message: PipelineMessage) -> PipelineResult
        @abstractmethod
        async def execute(self) -> dict  # Subclass implements
        
        # Hooks
        async def on_start(self) -> None
        async def on_success(self, result: dict) -> None
        async def on_failure(self, error: Exception) -> None
        
        # Status management
        async def update_status(self, status: PipelineStatus) -> None
        
        # Retry logic
        def is_retryable(self, error: Exception) -> bool
        async def schedule_retry(self) -> None
        
        # Chaining
        async def trigger_next_pipeline(self) -> None
    ```
  - **Validation**: 
    ```bash
    pytest backend/tests/unit/test_pipeline_base.py -v
    # Tests: lifecycle transitions, status updates, retry logic
    ```
  - **DoD**:
    - `run()` handles full lifecycle: on_start → execute → on_success/on_failure
    - Status correctly updated in PipelineRun at each stage
    - Retry logic respects `max_attempts` and backoff policy
    - `trigger_next_pipeline()` implements chaining per design.md §4

- [x] **T109** [P] Create pipeline message schema
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/schemas/pipeline.py`
  - **Depends**: T108 (BasePipeline needs message type)
  - **Schema** (per stack.md Pipeline Message Schema):
    ```python
    class PipelineMessage(BaseModel):
        run_id: UUID
        pipeline_type: PipelineType
        content_id: UUID | None
        enrichment_version: str
        correlation_id: str
        triggered_by: UUID | None
        input_params: dict
        parent_run_id: UUID | None
        attempt_number: int = 1
        created_at: datetime
    ```
  - **Validation**: 
    ```bash
    pytest backend/tests/unit/test_pipeline_schemas.py -v
    # Tests: serialization, deserialization, from Service Bus message
    ```
  - **DoD**:
    - Schema matches stack.md Pipeline Message Schema
    - `from_service_bus_message()` class method parses raw message
    - `to_service_bus_message()` method serializes for sending
    - All fields validated with Pydantic

- [x] **T110** [BLOCKING] Create Queue service for Service Bus
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/services/queue_service.py`
  - **Depends**: T100 (Service Bus exists), T109 (message schema)
  - **Methods**:
    ```python
    class QueueService:
        async def send_to_topic(self, topic: str, message: PipelineMessage) -> None
        async def send_with_delay(self, topic: str, message: PipelineMessage, delay_seconds: int) -> None
        async def receive_message(self, subscription: str) -> PipelineMessage | None
    ```
  - **Validation**: 
    ```bash
    # Integration test with Azure Service Bus
    pytest backend/tests/integration/test_queue_service.py -v
    # Or use Service Bus emulator locally
    ```
  - **DoD**:
    - Can send message to `pipeline-triggers` topic
    - Can receive message from any subscription
    - Delayed send works for retry scheduling
    - Integration test passes with real Service Bus

**🎯 Phase 1.3 Checkpoint**: Pipeline base infrastructure in code

---

### Phase 1.4: Pipeline Control API (Control Plane)

- [x] **T111** [BLOCKING] Implement `POST /api/v1/pipelines` (enqueue)
  - **Owner**: CP | **Env**: DEV-ONLY
  - **Files**: `backend/app/api/v1/pipelines.py`, `backend/app/services/pipeline_service.py`
  - **Depends**: T105 → T108 → T110 (models, base class, queue)
  - **Behavior**:
    1. Validate request (source_url or content_id required)
    2. Create PipelineRun with status=`pending`
    3. Build PipelineMessage
    4. Send to Service Bus topic
    5. Return 202 Accepted with `run_id`
  - **Request**: 
    ```json
    {
      "pipeline_type": "analysis",
      "source_url": "https://github.com/user/repo",
      "chain": "full_ingestion",  // optional
      "enrichment_version": "1.0.0",
      "force_refresh": false
    }
    ```
  - **Response**: `202 Accepted` with `{ "run_id": "uuid", "status": "pending" }`
  - **Auth**: Requires contributor role
  - **Validation**: 
    ```bash
    curl -X POST http://localhost:8000/api/v1/pipelines \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"pipeline_type": "analysis", "source_url": "https://github.com/microsoft/vscode"}'
    # Should return 202 with run_id
    ```
  - **DoD**:
    - Returns 202 Accepted (NOT 200 or 201)
    - PipelineRun created in Cosmos DB with status=pending
    - Message sent to Service Bus topic
    - Chain stored in input_params if specified

- [x] **T112** [P] Implement `GET /api/v1/pipelines/{run_id}` (status)
  - **Owner**: CP | **Env**: DEV-ONLY
  - **Files**: `backend/app/api/v1/pipelines.py`
  - **Depends**: T111 (API router exists)
  - **Response**: Full PipelineRun with status, timestamps, output/error
  - **Validation**: 
    ```bash
    curl http://localhost:8000/api/v1/pipelines/{run_id} -H "Authorization: Bearer $TOKEN"
    # Poll until status changes from pending → running → completed
    ```
  - **DoD**:
    - Returns PipelineRun with all fields per design.md §5
    - Includes `output_summary` when completed
    - Includes `error_details` when failed

- [x] **T113** [P] Implement `GET /api/v1/pipelines/{run_id}/logs`
  - **Owner**: CP | **Env**: DEV-ONLY
  - **Files**: `backend/app/api/v1/pipelines.py`
  - **Depends**: T111 (API router exists), T101 (Jobs exist)
  - **Behavior**: Fetch logs from Container Apps Job execution
  - **Validation**: 
    ```bash
    curl http://localhost:8000/api/v1/pipelines/{run_id}/logs -H "Authorization: Bearer $TOKEN"
    # Should return execution logs after job runs
    ```
  - **DoD**:
    - Returns structured logs from Container Apps Job
    - Handles case where job hasn't started yet

- [x] **T114** [P] Implement `POST /api/v1/pipelines/{run_id}/retry`
  - **Owner**: CP | **Env**: DEV-ONLY
  - **Files**: `backend/app/api/v1/pipelines.py`
  - **Depends**: T111 (API router exists)
  - **Behavior**: 
    1. Validate run is in `failed` status
    2. Increment `attempt_number`
    3. Reset status to `pending`
    4. Re-send to Service Bus
  - **Validation**: 
    ```bash
    curl -X POST http://localhost:8000/api/v1/pipelines/{run_id}/retry -H "Authorization: Bearer $TOKEN"
    # Should return 202, pipeline re-executes
    ```
  - **DoD**:
    - Only works on failed pipelines (returns 400 otherwise)
    - Increments attempt_number
    - New execution starts

- [x] **T115** [P] Implement `POST /api/v1/pipelines/{run_id}/cancel`
  - **Owner**: CP | **Env**: DEV-ONLY
  - **Files**: `backend/app/api/v1/pipelines.py`
  - **Depends**: T111 (API router exists)
  - **Behavior**: Sets status to `cancelled`, attempts to stop job if running
  - **Validation**: 
    ```bash
    curl -X POST http://localhost:8000/api/v1/pipelines/{run_id}/cancel -H "Authorization: Bearer $TOKEN"
    # Status should become 'cancelled'
    ```
  - **DoD**:
    - Status updated to `cancelled`
    - Works on `pending` or `running` pipelines
    - Returns 400 for already completed/failed

- [x] **T116** [P] Implement `GET /api/v1/content/{id}/pipeline-history`
  - **Owner**: CP | **Env**: DEV-ONLY
  - **Files**: `backend/app/api/v1/pipelines.py`
  - **Depends**: T111 (API router exists)
  - **Response**: List of all pipeline runs for content, ordered by created_at desc
  - **Validation**: 
    ```bash
    curl http://localhost:8000/api/v1/content/{content_id}/pipeline-history -H "Authorization: Bearer $TOKEN"
    # Should list all runs after multiple pipeline executions
    ```
  - **DoD**:
    - Returns list of PipelineRuns for given content_id
    - Includes all pipeline types
    - Paginated (limit/offset)

**🎯 Phase 1.4 Checkpoint**: Pipeline control API complete

---

### Phase 1.5: Pipeline Runner (Data Plane)

- [x] **T117** [BLOCKING] Create pipeline runner entry point
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/pipelines/runner.py`
  - **Depends**: T108 → T109 → T110 (base class, message, queue)
  - **Behavior**:
    1. Read message from environment variable (set by Container Apps Jobs)
    2. Parse into PipelineMessage
    3. Instantiate correct pipeline class based on `pipeline_type`
    4. Call `pipeline.run(message)`
    5. Exit with success/failure code
  - **CLI**: 
    ```bash
    python -m app.pipelines.runner
    # Reads SERVICEBUS_MESSAGE env var
    ```
  - **Pipeline Registry**:
    ```python
    PIPELINE_REGISTRY = {
        "analysis": AnalysisPipeline,
        "enrichment": EnrichmentPipeline,
        "localization": LocalizationPipeline,
        "asset_generation": AssetGenerationPipeline,
        "indexing": IndexingPipeline,
    }
    ```
  - **Validation**: 
    ```bash
    # Manual test with mock message
    export SERVICEBUS_MESSAGE='{"run_id":"uuid","pipeline_type":"analysis",...}'
    python -m app.pipelines.runner
    ```
  - **DoD**:
    - Correctly dispatches to pipeline class based on type
    - Handles unknown pipeline types gracefully
    - Exits with code 0 on success, non-zero on failure
    - Logs structured JSON for observability

- [x] **T118** [P] Create Dockerfile.pipeline
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/Dockerfile.pipeline`
  - **Depends**: T117 (runner exists)
  - **Base**: Same as API but different entrypoint
  - **Entrypoint**: `python -m app.pipelines.runner`
  - **Validation**: 
    ```bash
    docker build -f Dockerfile.pipeline -t buildflow-pipeline:local .
    docker run --rm buildflow-pipeline:local --help
    ```
  - **DoD**:
    - Image builds successfully
    - Entrypoint runs pipeline runner
    - All dependencies included (same as API image)

- [x] **T119** [P] Update CI/CD to build pipeline image
  - **Owner**: Infrastructure | **Env**: DEV-ONLY
  - **Files**: `.github/workflows/deploy-pipeline.yml`
  - **Depends**: T118 (Dockerfile exists)
  - **Behavior**: Builds and pushes both `api` and `pipeline` images to ACR
  - **Validation**: 
    ```bash
    # After push to develop branch:
    az acr repository show-tags --name acrbuildflow --repository buildflow-api
    az acr repository show-tags --name acrbuildflow --repository buildflow-pipeline
    ```
  - **DoD**:
    - GitHub Actions workflow produces two images
    - Both tagged with commit SHA and `latest`
    - Images pushed to Azure Container Registry

**🎯 Milestone 1 Complete**: Pipeline jobs can be triggered and executed

---

## Milestone 2: Analysis Pipeline [DEV-ONLY]

**Deliverable**: GitHub repository analysis running as Container Apps Job

**Pipeline Type**: `analysis`

### Milestone 2 Definition of Done (DoD)
- [x] AnalysisPipeline class extracts all data per design.md §3.1 output_contract
- [x] RawExtraction stored as immutable record
- [x] Content skeleton created or updated with raw_extraction_id reference
- [x] Idempotency enforced (skip if same URL within 24h unless force_refresh)
- [x] Retry logic handles GitHub rate limits and network timeouts
- [ ] Frontend displays pipeline status for content being analyzed

---

### Phase 2.1: GitHub Data Extraction

- [x] **T200** [BLOCKING] Extend GitHub service for comprehensive extraction
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/services/github_service.py`
  - **Depends**: M1 complete (T100-T119)
  - **Extract** (per design.md §3.1 output_contract):
    - `raw_readme`: README.md content (immutable)
    - `repository_metadata`: stars, forks, watchers, open_issues, open_prs, last_commit_date, created_at, topics, license, default_branch
    - `commit_activity`: total_commits_30d, total_commits_90d, contributors_count
    - `releases`: latest_version, release_count, last_release_date
    - `extracted_urls`: demo_url, docs_url, video_url (parsed from README)
  - **Validation**: 
    ```bash
    pytest backend/tests/unit/test_github_service.py -v
    # Test with mocked GitHub API responses
    ```
  - **DoD**:
    - All fields from design.md §3.1 output_contract extracted
    - URL parsing extracts demo, docs, video links from README
    - GitHub rate limit handled with retry

- [x] **T201** [BLOCKING] Implement AnalysisPipeline class
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/pipelines/analysis.py`
  - **Depends**: T108 (BasePipeline) → T200 (GitHub service) → T106 (RawExtraction)
  - **Steps** (per design.md §3.1):
    1. Validate URL (T202)
    2. Check for duplicate / idempotency (T203)
    3. Update status to `running`
    4. Fetch from GitHub (T200)
    5. Store RawExtraction (immutable, T106)
    6. Create or update Content skeleton with `raw_extraction_id`
    7. Update status to `completed`
    8. Trigger next pipeline if chain specified (enrichment)
  - **Validation**: 
    ```bash
    pytest backend/tests/integration/test_analysis_pipeline.py -v
    # End-to-end test with real GitHub repo
    ```
  - **DoD**:
    - Pipeline completes full lifecycle (pending → running → completed)
    - RawExtraction created with all fields
    - Content created/updated with raw_extraction_id
    - Next pipeline triggered if chain specified

- [x] **T202** [P] Implement URL validation with allowlist
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/pipelines/analysis.py`
  - **Depends**: T201 (part of pipeline)
  - **Checks**: HTTPS only, github.com domain, no IP addresses, valid repo path format
  - **Validation**: 
    ```bash
    pytest backend/tests/unit/test_analysis_url_validation.py -v
    # Tests: valid URLs pass, invalid rejected with clear error
    ```
  - **DoD**:
    - Rejects http:// URLs
    - Rejects non-GitHub domains
    - Rejects IP addresses
    - Accepts valid github.com/owner/repo URLs

- [x] **T203** [P] Implement idempotency check
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/pipelines/analysis.py`
  - **Depends**: T201 (part of pipeline), T106 (RawExtraction repo)
  - **Behavior** (per design.md §3.1 idempotency_strategy):
    - Key: `SHA256(source_url)`
    - Skip if RawExtraction exists within 24h (unless `force_refresh=true`)
  - **Validation**: 
    ```bash
    pytest backend/tests/unit/test_analysis_idempotency.py -v
    # Test: submit same URL twice, second is skipped
    ```
  - **DoD**:
    - Uses SHA256 hash of source_url
    - Skips if extraction within 24h
    - `force_refresh=true` bypasses check
    - PipelineRun marked with `skipped` reason in output_summary

- [x] **T204** [P] Add retry logic with exponential backoff
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/pipelines/analysis.py`
  - **Depends**: T201 (part of pipeline)
  - **Retry Policy** (per design.md §3.1):
    - `max_attempts`: 3
    - `backoff`: exponential (2s, 4s, 8s)
    - Retryable: NETWORK_TIMEOUT, GITHUB_RATE_LIMIT
    - Non-retryable: Invalid URL, 404, 403
  - **Validation**: 
    ```bash
    pytest backend/tests/unit/test_analysis_retry.py -v
    # Test: mock GitHub failure, verify retry attempts in logs
    ```
  - **DoD**:
    - Retries on network timeout
    - Retries on GitHub rate limit (with appropriate delay)
    - Does NOT retry on 404 or invalid URL
    - Logs each retry attempt

**🎯 Phase 2.1 Checkpoint**: Analysis pipeline extracts raw data from GitHub

---

### Phase 2.2: Frontend Analysis Integration

- [x] **T205** [P] Update analysis store for pipeline model
  - **Owner**: CP (Frontend) | **Env**: ALL
  - **Files**: `frontend/stores/analysis.ts`, `frontend/types/pipeline.ts`
  - **Depends**: T111 (API exists)
  - **Changes**: 
    - Replace AnalysisRequest with PipelineRun
    - Add polling for status updates
    - Support run_id instead of request_id
  - **Validation**: Vue DevTools shows pipeline runs with correct types
  - **DoD**:
    - `PipelineRun` type defined matching API response
    - Store actions: `enqueuePipeline()`, `getPipelineStatus()`, `getPipelineHistory()`
    - Polling implemented for status updates

- [x] **T206** [P] Update ContributeContent.vue for pipeline status
  - **Owner**: CP (Frontend) | **Env**: ALL
  - **Files**: `frontend/views/contributor/ContributeContent.vue`
  - **Depends**: T205 (store updated)
  - **Show**: Pipeline run status (pending/running/completed/failed), type, timestamps, progress
  - **Validation**: UI shows pipeline progression in real-time
  - **DoD**:
    - Status indicator shows current pipeline state
    - Timestamps displayed (created, started, completed)
    - Error message shown on failure
    - Retry button visible on failed pipelines

- [x] **T207** [P] Add pipeline history view
  - **Owner**: CP (Frontend) | **Env**: ALL
  - **Files**: `frontend/views/contributor/PipelineHistory.vue`, `frontend/router/index.ts`
  - **Depends**: T116 (history API), T205 (store)
  - **Show**: All runs for a content item with status, duration, type
  - **Validation**: Navigate to content, see full run history
  - **DoD**:
    - Route: `/content/{id}/pipelines`
    - Lists all pipeline runs for content
    - Sortable by date, filterable by type
    - Click to view run details

**🎯 Milestone 2 Complete**: Frontend shows pipeline status

---

## Milestone 3: Enrichment Pipeline [DEV-ONLY]

**Deliverable**: AI-powered content enrichment running as Container Apps Job

**Pipeline Type**: `enrichment`

### Milestone 3 Definition of Done (DoD)
- [x] EnrichmentPipeline class generates all fields per design.md §3.2 output_contract
- [x] Content updated with enriched fields and enrichment_version
- [x] Popularity score calculated from repository signals
- [x] Pipeline chaining implemented (analysis → enrichment → ...)
- [x] enrichment_version tracked for reprocessing support

---

### Phase 3.1: LLM Enrichment

- [x] **T300** [BLOCKING] Extend LLM service for enrichment
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/services/llm_service.py`
  - **Depends**: M2 complete (T200-T207)
  - **Generate** (per design.md §3.2 output_contract):
    - `summary.short`: max 200 chars
    - `summary.long`: max 2000 chars
    - `categories`: AI-suggested categories
    - `technologies`: detected from content
    - `difficulty_level`: beginner/intermediate/advanced
    - `estimated_time`: e.g., "2-4 hours"
    - `prerequisites`: list of prerequisites
    - `learning_outcomes`: list of outcomes
    - `quality_signals`: has_documentation, has_tests, has_ci, is_maintained
  - **Model**: Azure OpenAI GPT-4o
  - **Validation**: 
    ```bash
    pytest backend/tests/unit/test_llm_enrichment.py -v
    # Test with mocked LLM responses
    ```
  - **DoD**:
    - All fields from design.md §3.2 output_contract generated
    - Structured output via JSON mode
    - Error handling for LLM timeouts

- [x] **T301** [BLOCKING] Implement EnrichmentPipeline class
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/pipelines/enrichment.py`
  - **Depends**: T108 (BasePipeline) → T300 (LLM service) → T105 (PipelineRun)
  - **Steps** (per design.md §3.2):
    1. Load RawExtraction for content
    2. Call LLM for enrichment
    3. Calculate popularity score (T302)
    4. Update Content with enriched data
    5. Set `enrichment_version` and `last_enriched_at`
    6. Trigger next pipeline if chain specified (localization, indexing)
  - **Input**: `content_id`, `enrichment_version`
  - **Idempotency**: Key = `SHA256(content_id + enrichment_version)`, replace if version differs
  - **Validation**: 
    ```bash
    pytest backend/tests/integration/test_enrichment_pipeline.py -v
    ```
  - **DoD**:
    - Content updated with all enriched fields
    - `enrichment_version` stored on Content
    - `last_enriched_at` timestamp set
    - Next pipeline triggered if chain

- [x] **T302** [P] Implement popularity score calculation
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/pipelines/enrichment.py`
  - **Depends**: T301 (part of pipeline)
  - **Definition** (per design.md §3.2):
    - **Input signals**: stars, last_commit_date, commit_activity_30d, commit_activity_90d, release_frequency
    - **Normalization**: Percentile ranking against catalog (0.0-1.0)
    - **Weighting**:
      - Stars: 40% (primary popularity signal)
      - Recency: 25% (maintenance signal)
      - Commit activity: 20% (active development)
      - Release frequency: 15% (maturity indicator)
  - **Output**: Float 0.0-1.0
  - **Validation**: 
    ```bash
    pytest backend/tests/unit/test_popularity_score.py -v
    # Test: various repo profiles produce expected scores
    # Test: weights sum to 1.0
    # Test: edge cases (0 stars, no commits, no releases)
    ```
  - **DoD**:
    - Score calculation deterministic given same inputs
    - Score normalized to 0.0-1.0 range using percentile ranking
    - Weights match design.md §3.2 specification (40/25/20/15)
    - High-star, recently-updated repos score higher
    - Edge cases handled gracefully (no division by zero)

- [x] **T303** [P] Update Content model with enriched fields
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/models/content.py`, `backend/app/schemas/content.py`
  - **Depends**: T301 (fields needed)
  - **Add** (per design.md §5 Content Extended):
    ```python
    summary_short: str | None
    summary_long: str | None
    difficulty_level: str | None
    estimated_time: str | None
    learning_outcomes: list[str]
    prerequisites: list[str]
    popularity_score: float | None
    stars: int | None
    forks: int | None
    last_commit_date: datetime | None
    is_maintained: bool | None
    enrichment_version: str | None
    last_enriched_at: datetime | None
    raw_extraction_id: UUID | None
    ```
  - **Validation**: Schema update applied, API returns new fields
  - **DoD**:
    - Model matches design.md §5 Content (Extended)
    - Schema includes all new fields
    - Existing content not broken (nullable fields)

**🎯 Phase 3.1 Checkpoint**: Enrichment pipeline adds AI insights

---

### Phase 3.2: Pipeline Chaining

- [x] **T304** [BLOCKING] Implement pipeline chaining logic
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/services/pipeline_service.py`, `backend/app/pipelines/base.py`
  - **Depends**: T108 (BasePipeline) → T110 (QueueService)
  - **Chains** (per design.md §4):
    ```python
    PIPELINE_CHAINS = {
        "full_ingestion": ["analysis", "enrichment", "localization", "asset_generation", "indexing"],
        "refresh_enrichment": ["enrichment", "localization", "indexing"],
        "reindex_only": ["indexing"],
    }
    ```
  - **Behavior**: On success, enqueue next in chain with same `correlation_id` and `parent_run_id`
  - **Validation**: 
    ```bash
    pytest backend/tests/integration/test_pipeline_chaining.py -v
    # Start full_ingestion, verify all 5 pipelines complete
    ```
  - **DoD**:
    - `trigger_next_pipeline()` correctly identifies next step
    - `parent_run_id` links chained runs
    - Chain terminates correctly at end
    - Failed pipeline stops chain (no cascading)

- [x] **T305** [P] Add chain selection to pipeline enqueue API
  - **Owner**: CP | **Env**: DEV-ONLY
  - **Files**: `backend/app/api/v1/pipelines.py`, `backend/app/schemas/pipeline.py`
  - **Depends**: T304 (chaining logic), T111 (enqueue API)
  - **Request**: `{ "chain": "full_ingestion", "source_url": "..." }`
  - **Behavior**: Stores chain name in `input_params`, first pipeline starts
  - **Validation**: 
    ```bash
    curl -X POST http://localhost:8000/api/v1/pipelines \
      -H "Authorization: Bearer $TOKEN" \
      -d '{"chain": "full_ingestion", "source_url": "https://github.com/user/repo"}'
    # Single request triggers entire chain
    ```
  - **DoD**:
    - `chain` parameter accepted in request
    - First pipeline in chain started
    - Chain info persisted for continuation

**🎯 Milestone 3 Complete**: Pipelines chain automatically

---

## Milestone 4: Search & Indexing Pipeline [DEV-ONLY]

**Deliverable**: Azure AI Search with hybrid (keyword + vector) search

**Pipeline Type**: `indexing`

### Milestone 4 Definition of Done (DoD)
- [x] Azure AI Search index created with schema per design.md §6
- [x] SearchService implements hybrid, keyword, and vector search modes
- [x] IndexingPipeline upserts content to search index
- [x] Embedding generation via Azure OpenAI text-embedding-ada-002
- [x] Search API returns paginated, filterable results
- [x] Frontend search uses new API with filters

---

### Phase 4.1: Search Infrastructure

- [x] **T400** [BLOCKING] Create Azure AI Search index schema
  - **Owner**: Infrastructure + DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/services/search_service.py`, `infra/modules/search-index.bicep`
  - **Depends**: T103 (AI Search service exists)
  - **Schema** (per design.md §6):
    - `id` (key)
    - `title`, `title_kr` (searchable, analyzer)
    - `description`, `summary` (searchable)
    - `categories`, `technologies` (filterable, facetable)
    - `difficulty_level` (filterable, facetable)
    - `visibility` (filterable)
    - `popularity_score`, `stars`, `last_commit_date` (sortable)
    - `content_vector` (vector, 1536 dimensions, HNSW, cosine)
  - **Scoring Profile**: `popularity-boost` with magnitude and freshness functions
  - **Validation**: 
    ```bash
    az search index show --service-name search-buildflow-dev --name buildflow-content
    ```
  - **DoD**:
    - Index exists with all fields per design.md §6
    - Vector search configured with HNSW algorithm
    - Scoring profile applied
    - Korean analyzer configured for kr fields

- [x] **T401** [BLOCKING] Implement Search Service
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/services/search_service.py`
  - **Depends**: T400 (index exists)
  - **Methods**:
    ```python
    async def hybrid_search(query: str, filters: SearchFilters, limit: int, offset: int) -> SearchResults
    async def keyword_search(query: str, filters: SearchFilters, limit: int, offset: int) -> SearchResults
    async def vector_search(embedding: list[float], filters: SearchFilters, limit: int, offset: int) -> SearchResults
    async def upsert_document(content: Content) -> None
    async def delete_document(content_id: UUID) -> None
    ```
  - **Validation**: 
    ```bash
    pytest backend/tests/integration/test_search_service.py -v
    ```
  - **DoD**:
    - All search modes implemented
    - Filters correctly applied
    - Pagination works
    - Facets returned for categories, technologies

- [x] **T402** [P] Implement embedding generation
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/services/llm_service.py`
  - **Depends**: T400 (vector field defined)
  - **Model**: Azure OpenAI `text-embedding-ada-002`
  - **Output**: 1536-dimension vector
  - **Input**: Concatenated title + description + summary
  - **Validation**: 
    ```bash
    pytest backend/tests/unit/test_embedding_generation.py -v
    # Verify output dimensions = 1536
    ```
  - **DoD**:
    - `generate_embedding()` method added to LLM service
    - Returns 1536-dimension float array
    - Caches embeddings to avoid recomputation

- [x] **T403** [BLOCKING] Implement `GET /api/v1/search`
  - **Owner**: CP | **Env**: ALL
  - **Files**: `backend/app/api/v1/search.py`, `backend/app/schemas/search.py`
  - **Depends**: T401 (search service)
  - **Params** (per design.md §6 Search API):
    - `q`: query string
    - `mode`: hybrid | keyword | vector
    - `categories[]`: category filter
    - `technologies[]`: technology filter
    - `difficulty`: difficulty filter
    - `min_stars`: minimum stars filter
    - `sort`: relevance | popularity | recent
    - `limit`, `offset`: pagination
  - **Validation**: 
    ```bash
    curl "http://localhost:8000/api/v1/search?q=react&mode=hybrid&limit=10"
    ```
  - **DoD**:
    - All params from design.md §6 supported
    - Facet counts returned
    - Pagination with total count
    - Visibility filter enforced (public only for unauthenticated)

**🎯 Phase 4.1 Checkpoint**: Search infrastructure ready

---

### Phase 4.2: Indexing Pipeline

- [x] **T404** [BLOCKING] Implement IndexingPipeline class
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/pipelines/indexing.py`
  - **Depends**: T108 (BasePipeline) → T401 (SearchService) → T402 (embeddings)
  - **Steps** (per design.md §3.5):
    1. Load Content(s) with enriched data
    2. Generate embedding for each content
    3. Upsert to Azure AI Search
    4. Update `last_indexed_at` on Content
  - **Input**: `content_ids[]` or `"all"` for full reindex
  - **Idempotency**: Key = `SHA256(content_ids_sorted + enrichment_version)`, upsert
  - **Validation**: 
    ```bash
    pytest backend/tests/integration/test_indexing_pipeline.py -v
    # After indexing, content appears in search
    ```
  - **DoD**:
    - Content upserted to search index
    - `last_indexed_at` timestamp set
    - Batch processing supported
    - Failed items reported but don't fail entire batch

- [x] **T405** [P] Implement batch indexing
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/pipelines/indexing.py`
  - **Depends**: T404 (indexing pipeline)
  - **Behavior**: Process multiple content items per job execution
  - **Batch size**: 100 items
  - **Validation**: 
    ```bash
    # Trigger full reindex
    curl -X POST http://localhost:8000/api/v1/pipelines \
      -d '{"pipeline_type": "indexing", "input_params": {"content_ids": "all"}}'
    ```
  - **DoD**:
    - Full reindex processes all content
    - Batches of 100 sent to Azure AI Search
    - Progress logged

**🎯 Phase 4.2 Checkpoint**: Content indexed and searchable

---

### Phase 4.3: Frontend Search Integration

- [x] **T406** [P] Update search store for new API
  - **Owner**: CP (Frontend) | **Env**: ALL
  - **Files**: `frontend/stores/content.ts`, `frontend/types/search.ts`
  - **Depends**: T403 (search API)
  - **Changes**: 
    - Use new `/api/v1/search` endpoint
    - Support all filter parameters
    - Handle facets for UI
  - **Validation**: Search returns results from AI Search
  - **DoD**:
    - `SearchParams` type matches API
    - `searchContent()` action updated
    - Facet data stored for filter UI

- [x] **T407** [P] Update Home.vue with advanced filters
  - **Owner**: CP (Frontend) | **Env**: ALL
  - **Files**: `frontend/views/Home.vue`, `frontend/components/SearchFilters.vue`
  - **Depends**: T406 (store updated)
  - **Filters**: Categories dropdown, technologies dropdown, difficulty selector, sort options
  - **Validation**: Filters applied to search results
  - **DoD**:
    - Filter UI matches available facets
    - Multiple filters combinable
    - Sort options: relevance, popularity, recent
    - URL reflects filter state (bookmarkable)

**🎯 Milestone 4 Complete**: Hybrid search working end-to-end

---

## Milestone 5: Localization Pipeline [DEV-ONLY]

**Deliverable**: Korean translation of content via AI

**Pipeline Type**: `localization`

### Milestone 5 Definition of Done (DoD)
- [x] LocalizationPipeline translates specified fields to Korean
- [x] Content model has _kr suffix fields for translations
- [x] Frontend language toggle switches between EN/KR

---

### Phase 5.1: Translation Pipeline

- [x] **T500** Implement LocalizationPipeline class
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/pipelines/localization.py`
  - **Depends**: M3 complete
  - **Steps** (per design.md §3.3):
    1. Load Content
    2. Translate fields via Azure OpenAI
    3. Update Content with _kr fields
  - **Target**: ko-KR
  - **Idempotency**: Key = `SHA256(content_id + target_locale + enrichment_version)`
  - **Validation**: Content has Korean translations
  - **DoD**: Schema matches design.md §3.3 output_contract

- [x] **T501** Add translation fields to Content model
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/models/content.py`
  - **Fields**: `title_kr`, `description_kr`, `summary_kr`, `prerequisites_kr`, `learning_outcomes_kr`, `localized_at`, `localization_model`
  - **DoD**: Translations stored and returned in API

- [x] **T502** Frontend language toggle
  - **Owner**: CP (Frontend) | **Env**: ALL
  - **Files**: `frontend/components/LanguageToggle.vue`, `frontend/components/ContentGrid.vue`, `frontend/stores/content.ts`
  - **Toggle**: EN / KR content display
  - **DoD**: Toggle switches displayed content language

**🎯 Milestone 5 Complete**: Content available in Korean

---

## Milestone 6: Asset Generation Pipeline [DEV-ONLY] [COMPLETE]

**Deliverable**: AI-generated thumbnails and preview assets

**Pipeline Type**: `asset_generation`

### Milestone 6 Definition of Done (DoD)
- [X] StorageService uploads/downloads from Azure Blob Storage
- [X] AssetGenerationPipeline creates thumbnails and OG images
- [X] GeneratedAsset records created with storage URLs
- [X] Content API returns asset URLs

---

### Phase 6.1: Asset Generation

- [X] **T600** [COMPLETE] Implement Storage Service for Blob
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/services/storage_service.py`
  - **Depends**: T102 (Blob Storage exists)
  - **Methods**: `upload_blob()`, `get_blob_url()`, `get_sas_url()`, `delete_blob()`
  - **DoD**: Integration test uploads and retrieves blob

- [X] **T601** [COMPLETE] Implement AssetGenerationPipeline
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `backend/app/pipelines/asset_generation.py`
  - **Depends**: T600 (storage) → T107 (GeneratedAsset)
  - **Assets**: Thumbnails (DALL-E or template-based), OG images
  - **Steps** (per design.md §3.4):
    1. Load Content
    2. Generate asset via AI or template
    3. Upload to Blob Storage
    4. Create GeneratedAsset record
  - **DoD**: Assets generated and accessible via CDN URL

- [X] **T602** [COMPLETE] Add asset URLs to Content API
  - **Owner**: CP | **Env**: ALL
  - **Files**: `backend/app/api/v1/content.py`, `backend/app/models/content.py`
  - **Response**: Include `thumbnail_url`, `og_image_url`
  - **DoD**: API returns asset URLs from GeneratedAsset

**🎯 Milestone 6 Complete**: Content has generated thumbnails

---

## Milestone 7: AI Assistant [COMPLETE]

**Deliverable**: AI-powered assistant for content discovery

### Milestone 7 Definition of Done (DoD)
- [X] AssistantService answers questions using indexed content (RAG)
- [X] Chat API with conversation history
- [X] Visibility enforcement (users only see accessible content)
- [X] Frontend chat UI with citations

---

### Phase 7.1: Assistant Service

- [X] **T700** [COMPLETE] Create Assistant Service
  - **Owner**: DP | **Env**: ALL
  - **Files**: `backend/app/services/assistant_service.py`
  - **Depends**: M4 complete (search for RAG)
  - **Capabilities**: Answer questions, recommend repos, explain usage
  - **Model**: Azure OpenAI GPT-4o with RAG
  - **DoD**: Assistant responds with citations from indexed content

- [X] **T701** [COMPLETE] Implement `POST /api/v1/assistant/chat`
  - **Owner**: CP | **Env**: ALL
  - **Files**: `backend/app/api/v1/assistant.py`
  - **Request**: `message`, `conversation_id`, `context`
  - **Response**: `response`, `citations[]`, `suggested_content[]`
  - **DoD**: Chat endpoint responds intelligently with sources

- [X] **T702** [COMPLETE] Add visibility enforcement
  - **Owner**: DP | **Env**: ALL
  - **Files**: `backend/app/services/assistant_service.py`
  - **Behavior**: Only search content user can access
  - **DoD**: Internal content hidden from public users

- [X] **T703** [COMPLETE] Frontend assistant UI
  - **Owner**: CP (Frontend) | **Env**: ALL
  - **Files**: `frontend/components/Assistant.vue`
  - **UI**: Chat interface with citations
  - **DoD**: User can chat with assistant, citations clickable

**🎯 Milestone 7 Complete**: AI assistant helps users discover content

---

## Milestone 8: Production Deployment [COMPLETE]

**Deliverable**: Full stack deployed to Azure with CI/CD

### Milestone 8 Definition of Done (DoD)
- [X] Dev environment fully deployed with all pipelines
- [X] Prod environment deployed (API + Search only, NO pipelines)
- [X] Monitoring and alerting configured
- [X] Dev → Prod promotion workflow implemented
- [X] CI/CD pipelines for both environments

---

### Phase 8.1: Dev Environment

- [X] **T800** [COMPLETE] Deploy Dev environment via Bicep
  - **Owner**: Infrastructure | **Env**: DEV-ONLY
  - **Files**: `infra/main.bicep`, `infra/parameters.dev.json`
  - **Depends**: M1-M4 complete
  - **Resources**: Full Dev stack with all pipelines
  - **Validation**: 
    ```bash
    az deployment group create --resource-group rg-buildflow-dev \
      --template-file infra/main.bicep --parameters infra/parameters.dev.json
    ```
  - **DoD**:
    - All resources created in Dev resource group
    - Container Apps Jobs running
    - Service Bus topics configured
    - API accessible

- [X] **T801** [COMPLETE] Configure GitHub Actions for Dev
  - **Owner**: Infrastructure | **Env**: DEV-ONLY
  - **Files**: `.github/workflows/deploy-dev.yml`
  - **Trigger**: Push to `develop` branch
  - **Validation**: Push triggers deployment, verify in Azure
  - **DoD**:
    - Workflow runs on develop push
    - Builds and deploys API + pipeline images
    - Infrastructure updated if Bicep changed

- [X] **T802** [COMPLETE] Setup monitoring and alerting
  - **Owner**: Infrastructure | **Env**: ALL
  - **Files**: `infra/modules/monitoring.bicep`
  - **Resources**: Application Insights, Log Analytics, alert rules
  - **Validation**: Logs and metrics visible in Azure Portal
  - **DoD**:
    - Application Insights configured for API
    - Container Apps Jobs logs visible
    - Alerts for failures configured

**🎯 Phase 8.1 Checkpoint**: Dev environment fully operational

---

### Phase 8.2: Prod Environment

- [X] **T803** [COMPLETE] Deploy Prod environment (read-only)
  - **Owner**: Infrastructure | **Env**: PROD
  - **Files**: `infra/parameters.prod.json`
  - **Depends**: T800 (Dev proven)
  - **Resources**: API, Cosmos, Search, Blob (NO Container Apps Jobs, NO Service Bus)
  - **Validation**: 
    ```bash
    az deployment group create --resource-group rg-buildflow-prod \
      --template-file infra/main.bicep --parameters infra/parameters.prod.json
    ```
  - **DoD**:
    - All read-only resources created in Prod
    - NO pipeline jobs deployed
    - API in read-only mode (no enqueue endpoints)

- [X] **T804** [COMPLETE] Configure GitHub Actions for Prod
  - **Owner**: Infrastructure | **Env**: PROD
  - **Files**: `.github/workflows/deploy-prod.yml`
  - **Trigger**: Push to `main` branch (with environment approval)
  - **Validation**: Merge to main triggers deployment after approval
  - **DoD**:
    - Workflow requires approval before deployment
    - Only API image deployed (no pipeline image)
    - Infrastructure updated if Bicep changed

- [X] **T805** [COMPLETE] Implement Dev → Prod promotion workflow
  - **Owner**: CP + DP | **Env**: ALL
  - **Files**: `backend/app/services/promotion_service.py`, `backend/app/api/v1/admin.py`
  - **Depends**: T803 (Prod exists)
  - **Behavior**: 
    1. Admin selects content for promotion
    2. Validation checks (enrichment complete, required fields)
    3. Copy content + assets from Dev Cosmos/Blob to Prod
    4. Trigger indexing in Prod search
  - **Validation**: Promoted content visible in Prod
  - **DoD**:
    - Promotion API available to admins
    - Content copied with all enriched data
    - Assets copied to Prod blob storage
    - Search index updated in Prod

**🎯 Milestone 8 Complete**: Full system running in Azure

---

## Deprecated Tasks & Migration Notes

### Deprecated Approaches

| Task/Pattern | Status | Replacement | Migration Notes |
|--------------|--------|-------------|-----------------|
| `BackgroundTasks` (FastAPI) | [DEPRECATED] | Azure Container Apps Jobs | Move all `BackgroundTasks` usage to pipeline queue |
| `AnalysisRequest` model | [DEPRECATED] | `PipelineRun` model (T105) | Generic model supports all pipeline types |
| In-process LLM calls | [DEPRECATED] | `EnrichmentPipeline` (T301) | LLM calls only in Data Plane |
| `analysis_service.py` pipeline logic | [DEPRECATED] | `app/pipelines/analysis.py` (T201) | Move analysis logic to pipeline class |
| Local execution assumptions | [DEPRECATED] | Azure-first | All execution on Azure infrastructure |
| Synchronous GitHub fetching in API | [DEPRECATED] | `AnalysisPipeline` (T201) | API returns 202, job fetches |

### How to Identify Deprecated Code

Search for these patterns and migrate:

```bash
# Find BackgroundTasks usage
grep -r "BackgroundTasks" backend/app/

# Find AnalysisRequest references
grep -r "AnalysisRequest" backend/app/ frontend/

# Find in-process heavy operations
grep -r "await llm_service" backend/app/api/
grep -r "await github_service" backend/app/api/
```

---

## Explicit Dependency Graph

```
MILESTONE 1: Pipeline Infrastructure
══════════════════════════════════════════════════════════════════════════════

Phase 1.1: Azure Infrastructure
┌─────┐
│T100 │ Service Bus namespace + topics
└──┬──┘
   │
   ▼
┌─────┐   ┌─────┐   ┌─────┐
│T101 │   │T102 │   │T103 │  (T101 depends on T100; T102, T103 parallel)
└──┬──┘   └──┬──┘   └──┬──┘
   │         │         │
   └────┬────┴────┬────┘
        │         │
        ▼         ▼
      ┌─────┐
      │T104 │ Main Bicep (depends on T100-T103)
      └──┬──┘
         │
         ▼

Phase 1.2: Pipeline Data Models
┌─────┐
│T105 │ PipelineRun model (BLOCKING)
└──┬──┘
   │
   ├───────┬───────┐
   ▼       ▼       ▼
┌─────┐ ┌─────┐ ┌─────┐
│T106 │ │T107 │ │T108 │  (T106, T107 parallel; T108 needs T105)
└─────┘ └─────┘ └──┬──┘
                   │
Phase 1.3: Pipeline Base Classes
                   ▼
┌─────┐         ┌─────┐
│T109 │◄────────│T108 │ BasePipeline (T109 parallel)
└─────┘         └──┬──┘
                   │
                   ▼
                ┌─────┐
                │T110 │ QueueService (depends on T100, T109)
                └──┬──┘
                   │
                   ▼

Phase 1.4: Pipeline Control API
┌─────┐
│T111 │ POST /pipelines (BLOCKING, depends on T105, T108, T110)
└──┬──┘
   │
   ├───────┬───────┬───────┬───────┐
   ▼       ▼       ▼       ▼       ▼
┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐
│T112 │ │T113 │ │T114 │ │T115 │ │T116 │  (all parallel after T111)
└─────┘ └─────┘ └─────┘ └─────┘ └─────┘

Phase 1.5: Pipeline Runner
┌─────┐
│T117 │ Runner entry point (BLOCKING, depends on T108, T109, T110)
└──┬──┘
   │
   ├───────┐
   ▼       ▼
┌─────┐ ┌─────┐
│T118 │ │T119 │  (parallel after T117)
└─────┘ └─────┘


MILESTONE 2: Analysis Pipeline
══════════════════════════════════════════════════════════════════════════════
Depends on: M1 complete (T100-T119)

┌─────┐
│T200 │ GitHub service extension (BLOCKING)
└──┬──┘
   │
   ▼
┌─────┐
│T201 │ AnalysisPipeline class (BLOCKING, depends on T108, T200, T106)
└──┬──┘
   │
   ├───────┬───────┐
   ▼       ▼       ▼
┌─────┐ ┌─────┐ ┌─────┐
│T202 │ │T203 │ │T204 │  (parallel, part of T201)
└─────┘ └─────┘ └─────┘
   │
   ▼

Phase 2.2: Frontend
┌─────┐
│T205 │ Analysis store update
└──┬──┘
   │
   ├───────┐
   ▼       ▼
┌─────┐ ┌─────┐
│T206 │ │T207 │  (parallel)
└─────┘ └─────┘


MILESTONE 3: Enrichment Pipeline
══════════════════════════════════════════════════════════════════════════════
Depends on: M2 complete (T200-T207)

┌─────┐
│T300 │ LLM service extension (BLOCKING)
└──┬──┘
   │
   ▼
┌─────┐
│T301 │ EnrichmentPipeline class (BLOCKING)
└──┬──┘
   │
   ├───────┐
   ▼       ▼
┌─────┐ ┌─────┐
│T302 │ │T303 │  (parallel)
└─────┘ └─────┘
   │
   ▼

Phase 3.2: Chaining
┌─────┐
│T304 │ Pipeline chaining logic (BLOCKING)
└──┬──┘
   │
   ▼
┌─────┐
│T305 │ Chain selection API
└─────┘


MILESTONE 4: Search & Indexing
══════════════════════════════════════════════════════════════════════════════
Depends on: M3 complete (T300-T305)

Phase 4.1: Infrastructure
┌─────┐
│T400 │ AI Search index schema (BLOCKING)
└──┬──┘
   │
   ▼
┌─────┐
│T401 │ Search Service (BLOCKING)
└──┬──┘
   │
   ├───────┐
   ▼       ▼
┌─────┐ ┌─────┐
│T402 │ │T403 │  (parallel)
└─────┘ └─────┘

Phase 4.2: Indexing Pipeline
┌─────┐
│T404 │ IndexingPipeline (BLOCKING, depends on T401, T402)
└──┬──┘
   │
   ▼
┌─────┐
│T405 │ Batch indexing
└─────┘

Phase 4.3: Frontend
┌─────┐
│T406 │ Search store update
└──┬──┘
   │
   ▼
┌─────┐
│T407 │ Advanced filters UI
└─────┘


MILESTONE 5-7: [FUTURE]
══════════════════════════════════════════════════════════════════════════════
T500-T502: Localization
T600-T602: Asset Generation
T700-T703: AI Assistant


MILESTONE 9: Daily Metadata Refresh (Azure Functions)
══════════════════════════════════════════════════════════════════════════════

**Status**: ✅ Complete  
**Created**: 2026-03-02  
**Goal**: GitHub/YouTube 콘텐츠 메타데이터를 매일 자동 갱신하는 Azure Function 구축

### Phase 9.1: API Rate Limit 분석 및 설계

- [x] **T900** GitHub REST API rate limit 분석 (5,000 req/hour, 1.5s delay)
  - **Owner**: DP | **Env**: ALL
  - **DoD**: Rate limit 전략 문서화 완료

- [x] **T901** YouTube Data API v3 quota 분석 (10,000 units/day, batch 50 IDs)
  - **Owner**: DP | **Env**: ALL
  - **DoD**: Quota 전략 문서화 완료

### Phase 9.2: Azure Function 코드 구현

- [x] **T902** [BLOCKING] Function App 프로젝트 생성 (Python v2 모델)
  - **Owner**: DP | **Env**: ALL
  - **Files**: `functions/function_app.py`, `functions/requirements.txt`, `functions/host.json`
  - **DoD**: Timer trigger (CRON `0 0 17 * * *` = KST 02:00) + HTTP manual trigger

- [x] **T903** GitHub metadata updater 구현
  - **Owner**: DP | **Env**: ALL
  - **Files**: `functions/github_updater.py`
  - **Depends**: T902
  - **DoD**: contents, analysis_requests, AI Search 업데이트. Rate limit 모니터링, 변경 없으면 skip

- [x] **T904** YouTube metadata updater 구현
  - **Owner**: DP | **Env**: ALL
  - **Files**: `functions/youtube_updater.py`
  - **Depends**: T902
  - **DoD**: youtube_contents, youtube_analysis, AI Search 업데이트. Batch 50 IDs/request

### Phase 9.3: 인프라 및 배포

- [x] **T905** [BLOCKING] Bicep 모듈 생성 (function-app.bicep)
  - **Owner**: CP | **Env**: ALL
  - **Files**: `infra/modules/function-app.bicep`
  - **Depends**: T902
  - **DoD**: Storage Account + Consumption Plan (Y1) + Function App + Diagnostics

- [x] **T906** main.bicep에 Function App 모듈 통합
  - **Owner**: CP | **Env**: ALL
  - **Files**: `infra/main.bicep`, `infra/parameters.dev.json`, `infra/parameters.prod.json`
  - **Depends**: T905
  - **DoD**: enableFunctions 파라미터, 기존 secrets (GITHUB_TOKEN, YOUTUBE_API_KEY 등) 재활용

- [x] **T907** 인프라 배포 검증
  - **Owner**: CP | **Env**: DEV
  - **Depends**: T906
  - **Validation**: `az functionapp list --resource-group rg-buildflow-dev`
  - **DoD**: func-buildflow-dev 리소스 생성 확인

- [x] **T908** GitHub Actions deploy-functions job 추가
  - **Owner**: CP | **Env**: ALL
  - **Files**: `.github/workflows/deploy-backend.yml`
  - **Depends**: T906
  - **DoD**: deploy-infrastructure → deploy-functions → validate 흐름 완성

### Phase 9.4: 테스트 및 버그 수정

- [x] **T909** 로컬 테스트 스크립트 작성
  - **Owner**: DP | **Env**: DEV-ONLY
  - **Files**: `functions/test_local.py`
  - **Depends**: T903, T904
  - **DoD**: `--dry` 모드 지원, `.env.local` / Azure CLI 크레덴셜 자동 로드

- [x] **T910** Python 3.9 호환성 수정
  - **Owner**: DP | **Env**: ALL
  - **Depends**: T909
  - **DoD**: `tuple[str, str] | None` → `Optional[Tuple[str, str]]` 변환, 로컬 테스트 통과

- [x] **T911** Cosmos DB partition key 버그 수정
  - **Owner**: DP | **Env**: ALL
  - **Files**: `functions/github_updater.py`
  - **Depends**: T909
  - **DoD**: `read_item` partition key를 `contributor_id` → `content_id`로 수정, 93 failed → 0

- [x] **T912** AI Search 스키마 불일치 수정
  - **Owner**: DP | **Env**: ALL
  - **Files**: `functions/github_updater.py`, `functions/youtube_updater.py`
  - **Depends**: T909
  - **DoD**: 인덱스명 `buildflow-contents` → `buildflow-content`, `forks`/`comment_count` 필드 제거

- [x] **T913** 로컬 전체 테스트 통과 확인
  - **Owner**: DP | **Env**: DEV
  - **Depends**: T910, T911, T912
  - **Validation**: `python3 test_local.py both`
  - **DoD**: GitHub 119개 (updated 1, failed 0), YouTube 8개 (updated 3, failed 0)

```
Phase 9.1: 분석
┌─────┐ ┌─────┐
│T900 │ │T901 │  (parallel)
└──┬──┘ └──┬──┘
   │       │
   ▼       ▼
Phase 9.2: 구현
┌─────┐
│T902 │ Function App 프로젝트 (BLOCKING)
└──┬──┘
   │
   ├───────┐
   ▼       ▼
┌─────┐ ┌─────┐
│T903 │ │T904 │  (parallel)
└─────┘ └─────┘

Phase 9.3: 인프라
┌─────┐
│T905 │ Bicep 모듈 (BLOCKING)
└──┬──┘
   │
   ▼
┌─────┐
│T906 │ main.bicep 통합
└──┬──┘
   │
   ├───────┐
   ▼       ▼
┌─────┐ ┌─────┐
│T907 │ │T908 │  (parallel)
└─────┘ └─────┘

Phase 9.4: 테스트
┌─────┐
│T909 │ 테스트 스크립트 (BLOCKING)
└──┬──┘
   │
   ├───────┬───────┐
   ▼       ▼       ▼
┌─────┐ ┌─────┐ ┌─────┐
│T910 │ │T911 │ │T912 │  (parallel)
└──┬──┘ └──┬──┘ └──┬──┘
   │       │       │
   └───────┼───────┘
           ▼
         ┌─────┐
         │T913 │ 전체 테스트 통과
         └─────┘
```


MILESTONE 8: Production
══════════════════════════════════════════════════════════════════════════════
Depends on: M1-M4 complete

Phase 8.1: Dev
┌─────┐
│T800 │ Deploy Dev (BLOCKING)
└──┬──┘
   │
   ├───────┐
   ▼       ▼
┌─────┐ ┌─────┐
│T801 │ │T802 │  (parallel)
└─────┘ └─────┘

Phase 8.2: Prod
┌─────┐
│T803 │ Deploy Prod (BLOCKING)
└──┬──┘
   │
   ├───────┐
   ▼       ▼
┌─────┐ ┌─────┐
│T804 │ │T805 │  (T804 parallel, T805 depends on T803)
└─────┘ └─────┘
```

---

## Estimated Timeline

| Milestone | Tasks | Est. Time | Dependencies | Cumulative |
|-----------|-------|-----------|--------------|------------|
| 0: Foundation | Completed | - | - | - |
| 1: Pipeline Infrastructure | T100-T119 | 5-7 days | None | 5-7 days |
| 2: Analysis Pipeline | T200-T207 | 3-4 days | M1 | 8-11 days |
| 3: Enrichment Pipeline | T300-T305 | 3-4 days | M2 | 11-15 days |
| 4: Search & Indexing | T400-T407 | 4-5 days | M3 | 15-20 days |
| 5-7: Future | T500-T703 | TBD | M4 | TBD |
| 8: Production | T800-T805 | 3-4 days | M4 | 18-24 days |

**Total (MVP with Search)**: ~3-4 weeks

---

## Alignment Verification

### Constitution v2.0.0 Compliance

| Principle | Status | Implementation |
|-----------|--------|----------------|
| Azure-first | ✅ | All resources in Azure (Bicep) |
| Pipeline-first | ✅ | Container Apps Jobs for processing |
| Stateless APIs | ✅ | JWT auth, no sessions |
| Dev/Prod separation | ✅ | Separate resource groups, Prod read-only |
| Enrichment versioning | ✅ | `enrichment_version` on Content (T303) |
| Raw data immutability | ✅ | RawExtraction model, no update() (T106) |
| Job idempotency | ✅ | SHA256 keys per pipeline (T203) |
| Job reliability | ✅ | Retry policies defined (T204) |
| Generated assets | ✅ | GeneratedAsset model (T107) |
| AI assistant | ✅ | Milestone 7 placeholder |

### Design.md Contract Compliance

| Contract | Status | Task |
|----------|--------|------|
| PipelineRun schema | ✅ | T105 matches §5 exactly |
| RawExtraction immutability | ✅ | T106 has no update() |
| Content extended fields | ✅ | T303 matches §5 exactly |
| GeneratedAsset schema | ✅ | T107 matches §5 exactly |
| Pipeline Control API | ✅ | T111-T116 match §2 exactly |
| Search API params | ✅ | T403 matches §6 exactly |
| Pipeline chaining | ✅ | T304 matches §4 PIPELINE_CHAINS |

### Spec Alignment

| Document | Aligned | Verification |
|----------|---------|--------------|
| constitution.md v2.0.0 | ✅ | All 7 principles implemented |
| design.md | ✅ | Pipeline types, schemas match |
| stack.md | ✅ | Folder structure, services match |
