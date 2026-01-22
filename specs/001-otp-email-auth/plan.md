# Implementation Plan: OTP 기반 이메일 인증 시스템

**Branch**: `001-otp-email-auth` | **Date**: 2026-01-22 | **Spec**: [spec.md](spec.md)
**Input**: Azure Communication Services OTP 이메일 인증, 내부 직원 전용 로그인, HttpOnly 쿠키 기반 JWT 세션

## Summary

내부 직원(@microsoft.com, @github.com)만 로그인할 수 있는 OTP 기반 인증 시스템을 구현합니다. Azure Communication Services를 통해 6자리 OTP를 이메일로 발송하고, 인증 성공 시 HttpOnly 쿠키에 JWT를 저장하여 7일간 세션을 유지합니다. Contributor 메뉴(Contribute Content, Create Content)와 관련 API는 인증된 사용자만 접근 가능하도록 보호합니다.

## Technical Context

**Language/Version**: Python 3.11 (Backend), TypeScript 5.x (Frontend)  
**Primary Dependencies**: FastAPI, Vue 3, Pinia, Azure Communication Services SDK  
**Storage**: Azure Cosmos DB (LoginAttempt, LoginHistory 컨테이너)  
**Testing**: pytest (Backend), Vitest (Frontend)  
**Target Platform**: Azure Container Apps (Backend), Azure Static Web Apps (Frontend)  
**Project Type**: web (frontend + backend)  
**Performance Goals**: OTP 이메일 발송 < 30초, API 응답 < 200ms p95  
**Constraints**: OTP 유효시간 3분, 재발송 제한 3분, 세션 유지 7일  
**Scale/Scope**: 내부 직원 ~1000명, 동시 로그인 ~100명

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Frontend-Backend Separation | ✅ Pass | SPA + REST API 구조 유지 |
| II. API-First Design | ✅ Pass | /api/v1/auth/* 엔드포인트 사용 |
| III. Stateless Authentication | ✅ Pass | JWT + OTP, 서버 세션 없음 |
| IV. Request Traceability | ✅ Pass | X-Correlation-ID 사용 |
| V. Fail-Fast Validation | ✅ Pass | 도메인/이메일 즉시 검증 |
| VI. Pipeline-First Architecture | N/A | 인증은 동기 처리 |
| VII. Azure-Only Execution | ✅ Pass | Azure Communication Services 사용 |
| Security: Rate Limiting | ✅ Pass | OTP 3분 재발송 제한 |
| Security: Token Storage | ✅ Pass | HttpOnly 쿠키 사용 |
| Data Models | ✅ Pass | LoginAttempt, LoginHistory 추가 |

## Project Structure

### Documentation (this feature)

```text
specs/001-otp-email-auth/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (OpenAPI specs)
└── tasks.md             # Phase 2 output
```

### Source Code (changes)

```text
backend/
├── app/
│   ├── api/v1/
│   │   └── auth.py              # MODIFY: 도메인 검증, HttpOnly 쿠키, 로그아웃
│   ├── config.py                # MODIFY: ACS 설정 추가
│   ├── dependencies.py          # MODIFY: 쿠키 기반 JWT 검증
│   ├── models/
│   │   └── login_attempt.py     # NEW: LoginAttempt, LoginHistory 모델
│   ├── repositories/
│   │   ├── login_attempt_repo.py # NEW: LoginAttempt Cosmos DB 저장소
│   │   └── login_history_repo.py # NEW: LoginHistory Cosmos DB 저장소
│   ├── schemas/
│   │   └── auth.py              # MODIFY: 응답 스키마 업데이트
│   └── services/
│       ├── auth_service.py      # MODIFY: 도메인 검증, 로그인 이력 저장
│       ├── email_service.py     # MODIFY: ACS 연동 완성
│       └── otp_store.py         # MODIFY: OTP_TTL_MINUTES=3, RATE_LIMIT_MINUTES=3 (Cosmos 전환은 향후 과제)
└── tests/
    ├── test_auth_api.py         # MODIFY: 새 테스트 케이스
    └── test_domain_validation.py # NEW: 도메인 검증 테스트

frontend/
├── components/
│   └── auth/
│       └── AuthModals.vue       # MODIFY: 도메인 오류 메시지, dev_code 제거
├── lib/
│   └── api.ts                   # MODIFY: 쿠키 credentials 설정
├── router/
│   └── index.ts                 # MODIFY: 로그인 필요 메시지 표시
└── stores/
    └── auth.ts                  # MODIFY: 쿠키 기반 인증 상태 관리
```

**Structure Decision**: 기존 web 구조 유지. 인증 관련 변경은 기존 파일 수정 + 2개 신규 파일(models/login_attempt.py, repositories/login_repo.py) 추가.

---

## Phase 0: Research

### Research Tasks

| Task | Question | Priority |
|------|----------|----------|
| R-1 | Azure Communication Services Python SDK 이메일 발송 패턴 | High |
| R-2 | FastAPI HttpOnly 쿠키 설정 및 CORS 고려사항 | High |
| R-3 | Cosmos DB TTL 기반 OTP 만료 처리 | Medium |
| R-4 | Vue Router 네비게이션 가드에서 토스트 메시지 표시 | Medium |
| R-5 | JWT RS256 키 로테이션 베스트 프랙티스 | Low |

### Research Findings (to be filled)

*Phase 0 실행 후 research.md에 문서화*

---

## Phase 1: Design

### Data Model

#### LoginAttempt (CosmosDB Container: `login_attempts`)

| Field | Type | Description | TTL |
|-------|------|-------------|-----|
| id | string | UUID | - |
| email | string | Partition Key, lowercase | - |
| otp_code | string | 6자리 숫자 (해시 저장 권장) | - |
| created_at | datetime | 발급 시간 | - |
| expires_at | datetime | 만료 시간 (created_at + 3분) | - |
| _ttl | int | 180 (3분 후 자동 삭제) | ✓ |

#### LoginHistory (CosmosDB Container: `login_history`)

| Field | Type | Description |
|-------|------|-------------|
| id | string | UUID |
| email | string | Partition Key, lowercase |
| logged_in_at | datetime | 로그인 성공 시간 |
| user_agent | string | 브라우저 정보 |
| ip_address | string | 클라이언트 IP |

### API Contracts

#### POST /api/v1/auth/otp

**Request:**
```json
{
  "email": "user@microsoft.com"
}
```

**Response 200 (Success):**
```json
{
  "success": true,
  "data": {
    "message": "OTP sent successfully",
    "email": "u***@microsoft.com",
    "expires_in_seconds": 180
  },
  "meta": { "timestamp": "...", "correlationId": "..." }
}
```

**Response 400 (Invalid Domain):**
```json
{
  "success": false,
  "error": {
    "code": "DOMAIN_NOT_ALLOWED",
    "message": "내부 직원 전용 로그인 서비스입니다."
  },
  "meta": { ... }
}
```

**Response 429 (Rate Limited):**
```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "2분 후에 다시 시도해주세요.",
    "details": { "retry_after_seconds": 120 }
  },
  "meta": { ... }
}
```

#### POST /api/v1/auth/verify

**Response 200:**
Set-Cookie: `access_token=<jwt>; HttpOnly; Secure; SameSite=Lax; Max-Age=604800; Path=/`

```json
{
  "success": true,
  "data": {
    "message": "Authentication successful",
    "user": {
      "id": "...",
      "email": "user@microsoft.com",
      "role": "contributor"
    }
  },
  "meta": { ... }
}
```

#### POST /api/v1/auth/logout

**Response 200:**
Set-Cookie: `access_token=; HttpOnly; Secure; SameSite=Lax; Max-Age=0; Path=/`

```json
{
  "success": true,
  "data": { "message": "Logged out successfully" },
  "meta": { ... }
}
```

#### GET /api/v1/auth/me

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "...",
    "email": "user@microsoft.com",
    "role": "contributor"
  },
  "meta": { ... }
}
```

**Response 401:**
```json
{
  "success": false,
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Missing or invalid authentication token"
  },
  "meta": { ... }
}
```

---

## Phase 2: Implementation Tasks

*Phase 2는 `/speckit.tasks` 명령어로 생성됩니다.*

### Task Outline (Preview)

| # | Task | Priority | Effort |
|---|------|----------|--------|
| 1 | 도메인 검증 로직 추가 (auth_service.py) | P1 | 2h |
| 2 | ACS 이메일 발송 연동 완성 (email_service.py) | P1 | 4h |
| 3 | HttpOnly 쿠키 JWT 설정 (auth.py) | P1 | 3h |
| 4 | 쿠키 기반 인증 미들웨어 (dependencies.py) | P1 | 3h |
| 5 | LoginAttempt Cosmos 저장소 (login_repo.py) | P1 | 4h |
| 6 | LoginHistory 로그인 이력 저장 | P2 | 2h |
| 7 | 로그아웃 엔드포인트 추가 | P2 | 1h |
| 8 | Frontend 쿠키 인증 전환 (auth.ts) | P1 | 3h |
| 9 | 도메인 오류 메시지 표시 (AuthModals.vue) | P1 | 2h |
| 10 | dev_code 표시 기능 제거 | P1 | 1h |
| 11 | 로그인 필요 메시지 표시 (router) | P2 | 2h |
| 12 | 단위 테스트 (도메인 검증, 쿠키) | P1 | 4h |
| 13 | 통합 테스트 (E2E 로그인 흐름) | P2 | 4h |

---

## Complexity Tracking

> 모든 Constitution Check 통과 - 복잡도 정당화 불필요

---

## Dependencies & Prerequisites

### Azure Resources Required

- [ ] Azure Communication Services 리소스 생성
- [ ] ACS Email Domain 설정 (sender address)
- [ ] Connection String 환경변수 설정

### Environment Variables to Add

```bash
# Azure Communication Services
ACS_CONNECTION_STRING=endpoint=https://<name>.communication.azure.com/;accesskey=<key>
ACS_SENDER_ADDRESS=DoNotReply@<domain>.azurecomm.net

# JWT (existing, may need rotation)
JWT_PRIVATE_KEY_PATH=keys/private.pem
JWT_PUBLIC_KEY_PATH=keys/public.pem
```

### Cosmos DB Containers to Create

```bash
# LoginAttempts container (with TTL enabled)
az cosmosdb sql container create \
  --account-name <account> \
  --database-name buildflow \
  --name login_attempts \
  --partition-key-path /email \
  --default-ttl 300

# LoginHistory container
az cosmosdb sql container create \
  --account-name <account> \
  --database-name buildflow \
  --name login_history \
  --partition-key-path /email
```

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| ACS 이메일 지연 | Medium | 30초 타임아웃, 사용자 안내 메시지 |
| 도메인 스푸핑 | High | 서버사이드 도메인 검증 필수 |
| 쿠키 CORS 이슈 | Medium | SameSite=Lax, CORS 설정 테스트 |
| Cosmos TTL 미작동 | Low | 애플리케이션 레벨 만료 체크 병행 |

---

## Next Steps

1. `/speckit.plan` 완료 → Phase 0 research.md 생성
2. Phase 1 data-model.md, contracts/ 생성
3. `/speckit.tasks` 실행 → tasks.md 생성
4. 구현 시작
