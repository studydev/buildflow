<!--
================================================================================
SYNC IMPACT REPORT
================================================================================
Version change: 1.0.0 → 2.0.0 (MAJOR - Azure-first pipeline architecture)

Modified principles:
  - I. Frontend-Backend Separation → unchanged
  - II. API-First Design → unchanged
  - III. Stateless Authentication → unchanged
  - IV. Request Traceability → unchanged
  - V. Fail-Fast Validation → unchanged

Added sections:
  - VI. Pipeline-First Architecture (NEW - core principle)
  - VII. Azure-Only Execution (NEW - core principle)
  - Environment Model (Dev/Prod separation)
  - Pipeline Versioning & Reprocessing
  - Job Reliability (idempotency, retries)
  - Generated Assets (AI-generated artifacts)
  - AI Assistant Integration (chatbot readiness)

Removed sections: None

Templates requiring updates:
  ✅ plan-template.md - no update needed (generic structure)
  ✅ spec-template.md - no update needed (generic structure)
  ✅ tasks-template.md - no update needed (generic structure)

Follow-up TODOs: None
================================================================================
-->

# BuildFlow Constitution

## Core Principles

### I. Frontend-Backend Separation
Frontend (Vite + Vue 3 + TypeScript + Pinia + shadcn-vue + Tailwind) and Backend (Python/Node.js on Azure Container Apps) MUST remain decoupled. Frontend calls backend exclusively via REST API. No server-side rendering; frontend is a static SPA deployed independently.

### II. API-First Design
All backend functionality MUST be exposed through versioned REST endpoints under `/api/v1`. OpenAPI spec MUST be maintained and kept in sync with implementation. Breaking changes require version bump to `/api/v2`.

### III. Stateless Authentication
Backend MUST be stateless. Authentication via email OTP + JWT only. No session storage on server. All auth state carried in JWT tokens. No Entra ID, OAuth, or third-party identity providers.

### IV. Request Traceability
Every request MUST carry a correlation ID (`X-Correlation-ID` header). All logs MUST include this ID. Structured JSON logging required. Logs MUST include: timestamp, level, correlation_id, user_id (if authenticated), action, duration_ms.

### V. Fail-Fast Validation
Input validation MUST occur at API boundary before business logic. Invalid requests return immediately with descriptive errors. No partial processing of invalid payloads.

### VI. Pipeline-First Architecture
The system MUST treat long-running workflows as first-class citizens.

- All non-trivial processing (analysis, enrichment, localization, asset generation, indexing) MUST be executed as asynchronous pipeline jobs.
- Azure Container Apps Jobs are the default execution model for pipelines.
- APIs MAY enqueue or control pipelines but MUST NOT execute heavy logic synchronously.
- Pipelines are the primary unit of work; APIs serve as control plane interfaces.

### VII. Azure-Only Execution
All services MUST run on Azure-managed infrastructure.

- Local execution is allowed only for developer testing and MUST NOT be assumed in system design.
- All production workloads MUST target Azure Container Apps (services) or Azure Container Apps Jobs (pipelines).
- Infrastructure MUST be defined as code using Bicep.

## Environment Model

### Dev and Prod Separation
The system MUST operate with two isolated environments:

- **Dev**: All active development, experimentation, pipeline iteration, and reprocessing occur here.
- **Prod**: Read-only, stable environment serving end users.

No experimental pipelines, reprocessing jobs, or schema migrations may run in Prod unless explicitly approved.

### Environment Configuration
- Environment-specific configuration MUST be managed via Azure Container Apps secrets and environment variables.
- Dev and Prod MUST use separate Azure resource groups.
- Cross-environment data access is prohibited except for explicit, audited promotion workflows.

## Pipeline Versioning & Reprocessing

### Enrichment Versioning
- All derived data MUST be associated with an `enrichment_version`.
- Raw source data MUST be immutable once collected.
- When pipeline logic changes, the system MUST support re-running enrichment and indexing without re-collecting raw data.

### Reprocessing Traceability
- All reprocessing runs MUST be traceable via a `run_id`.
- The system MUST maintain a history of pipeline runs per content item.
- Rollback to previous enrichment versions MUST be possible.

## Job Reliability

### Idempotency
- All pipeline jobs MUST be idempotent.
- Jobs MUST tolerate retries without producing duplicated or corrupted state.
- Each job execution MUST check for existing results before processing.

### Execution Status
- All jobs MUST record execution status transitions: `pending → running → completed | failed`.
- Failures are expected and MUST be observable and recoverable.
- Failed jobs MUST include error details sufficient for debugging.

### Retry Policy
- Jobs MUST implement exponential backoff for transient failures.
- Maximum retry count MUST be configurable per job type.
- Dead-letter mechanisms MUST exist for permanently failed jobs.

## Generated Assets

The system MAY generate derived assets using AI models, including but not limited to:
- Thumbnails
- Summaries
- Translations
- Localized repositories or documentation

### Asset Requirements
Generated assets MUST:
- Be explicitly marked as generated (`is_generated: true`)
- Be associated with a pipeline run (`run_id`) and version (`enrichment_version`)
- Respect visibility rules (public/internal)
- Include generation metadata (model used, timestamp, source content ID)

### Asset Storage
- Generated assets MUST be stored in Azure Blob Storage.
- Asset URLs MUST be served via CDN for public content.
- Internal assets MUST require authentication.

## AI Assistant Integration

The system MUST support an AI assistant capable of:
- Answering questions using indexed content
- Recommending relevant repositories or workflows
- Explaining how to use a selected content item
- Providing contextual guidance based on user queries

### Assistant Constraints
The assistant MUST:
- Respect content visibility boundaries (public vs. internal)
- Prefer internal indexed knowledge before external search
- Cite sources when providing recommendations
- Not hallucinate or fabricate content references

### Integration Architecture
- The assistant MUST be implemented as a separate service.
- Assistant queries MUST be traceable via correlation ID.
- Response latency targets: p95 < 3 seconds for simple queries.

## Backend Conventions

### Hosting
- **Platform**: Azure Container Apps (services), Azure Container Apps Jobs (pipelines)
- **Environment Variables**: Use Azure Container Apps secrets for sensitive config
- **Health Check**: `GET /api/v1/health` MUST return `200 OK` with `{"status":"healthy"}`

### API Style
- **Prefix**: All endpoints under `/api/v1/`
- **Format**: JSON request/response bodies
- **Methods**: Use correct HTTP verbs (GET=read, POST=create, PUT=replace, PATCH=update, DELETE=remove)
- **Naming**: Lowercase, hyphen-separated paths (e.g., `/api/v1/analysis-requests`)

### Response Envelope
All responses MUST use this envelope:
```json
{
  "success": true,
  "data": { ... },
  "meta": { "timestamp": "ISO8601", "correlationId": "uuid" }
}
```

### Error Format
Errors MUST use this structure:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable message",
    "details": [ { "field": "email", "issue": "Invalid format" } ]
  },
  "meta": { "timestamp": "ISO8601", "correlationId": "uuid" }
}
```

### Status Codes
| Code | Usage |
|------|-------|
| 200 | Success (GET, PUT, PATCH) |
| 201 | Created (POST) |
| 202 | Accepted (async job enqueued) |
| 204 | No Content (DELETE) |
| 400 | Validation error, malformed request |
| 401 | Missing or invalid token |
| 403 | Valid token but insufficient permissions |
| 404 | Resource not found |
| 409 | Conflict (duplicate resource) |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

### Authentication Flow
1. User requests OTP: `POST /api/v1/auth/otp` with `{ "email": "user@example.com" }`
2. Backend sends OTP to email (valid 5 minutes, 6-digit code)
3. User verifies: `POST /api/v1/auth/verify` with `{ "email": "...", "otp": "123456" }`
4. Backend returns JWT access token (15 min) + refresh token (7 days)
5. Refresh: `POST /api/v1/auth/refresh` with refresh token in body

### Roles
| Role | Permissions |
|------|-------------|
| `user` | Read all content, create analysis requests, use AI assistant |
| `contributor` | All user permissions + create/edit/delete content, trigger pipelines |

Role stored in JWT claim `role`. Middleware MUST validate role before protected endpoints.

### Data Models

#### Content
```
Content {
  id: UUID (PK)
  title: string (required, max 200)
  title_kr: string (optional, max 200)
  description: string (required, max 2000)
  description_kr: string (optional, max 2000)
  url: string (required, valid URL)
  categories: string[] (required, min 1)
  technologies: string[]
  prerequisites: string
  contributor_id: UUID (FK → User)
  status: enum [draft, published, archived]
  enrichment_version: string (semantic version)
  last_enriched_at: datetime (nullable)
  created_at: datetime
  updated_at: datetime
}
```

#### AnalysisRequest
```
AnalysisRequest {
  id: UUID (PK)
  user_id: UUID (FK → User)
  source_url: string (required, valid URL)
  status: enum [pending, processing, completed, failed]
  result: JSON (nullable)
  error_message: string (nullable)
  run_id: UUID (FK → PipelineRun, nullable)
  created_at: datetime
  completed_at: datetime (nullable)
}
```

#### PipelineRun (NEW)
```
PipelineRun {
  id: UUID (PK)
  pipeline_type: enum [analysis, enrichment, localization, asset_generation, indexing]
  status: enum [pending, running, completed, failed]
  enrichment_version: string (semantic version)
  input_params: JSON
  output_summary: JSON (nullable)
  error_details: JSON (nullable)
  started_at: datetime
  completed_at: datetime (nullable)
  created_at: datetime
}
```

#### GeneratedAsset (NEW)
```
GeneratedAsset {
  id: UUID (PK)
  content_id: UUID (FK → Content)
  run_id: UUID (FK → PipelineRun)
  asset_type: enum [thumbnail, summary, translation, localized_repo]
  storage_url: string (Azure Blob URL)
  is_generated: boolean (always true)
  model_used: string (e.g., "gpt-4o", "dall-e-3")
  visibility: enum [public, internal]
  created_at: datetime
}
```

## Security & Compliance

### Rate Limiting
- OTP requests: Max 3 per email per 15 minutes
- OTP verification: Max 5 attempts per email per 15 minutes (then block 1 hour)
- API general: 100 requests per minute per user
- Unauthenticated: 20 requests per minute per IP
- AI assistant: 30 queries per minute per user

### Token Security
- Access token expiry: 15 minutes
- Refresh token expiry: 7 days
- Refresh tokens are single-use (rotation on each refresh)
- Tokens MUST be signed with RS256 or ES256 (no HS256 in production)

### Input Validation Rules
- Email: RFC 5322 compliant
- URLs: MUST be valid HTTP/HTTPS
- String fields: Sanitize HTML, limit length per field spec
- Arrays: Max 20 items unless specified
- UUIDs: Validate format before database lookup

### Security Headers
All responses MUST include:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-Correlation-ID: {correlationId}`

### Logging Restrictions
NEVER log: passwords, OTP codes, full JWT tokens, PII beyond user ID.
ALWAYS log: correlation ID, user ID, action, response status, duration, run_id (for pipeline operations).

## Governance

- This constitution supersedes all other backend development practices
- All PRs MUST verify compliance with these principles before merge
- Amendments require: documented rationale, team review, migration plan if breaking
- Use `/specs/` folder for feature specifications following template structure
- Backend implementation MUST pass constitution check before Phase 1 design
- Pipeline changes MUST include enrichment version bump rationale
- AI assistant changes MUST include content safety review

### Version Bump Policy
- MAJOR: Backward incompatible changes to principles, removal of core rules
- MINOR: New principle/section added or materially expanded guidance
- PATCH: Clarifications, wording, typo fixes, non-semantic refinements

**Version**: 2.0.0 | **Ratified**: 2026-01-18 | **Last Amended**: 2026-01-20
