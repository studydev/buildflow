# Tasks: OTP 기반 이메일 인증 시스템

**Input**: Design documents from `/specs/001-otp-email-auth/`  
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Configuration and dependency setup

- [X] T001 Add ACS config settings in backend/app/config.py (ACS_CONNECTION_STRING, ACS_SENDER_ADDRESS)
- [X] T002 [P] Add azure-communication-email to backend/requirements.txt
- [X] T003 [P] Update CORS settings for credentials support in backend/app/main.py (already configured with allow_credentials=True)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before user stories

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Data Models

- [X] T004 [P] Create LoginAttempt model in backend/app/models/login_attempt.py
- [X] T005 [P] Create LoginHistory model in backend/app/models/login_history.py
- [X] T006 Update backend/app/models/__init__.py to export new models

### Repository Layer

- [X] T007 Create LoginAttemptRepository in backend/app/repositories/login_attempt_repo.py (upsert, get, delete)
- [X] T008 [P] Create LoginHistoryRepository in backend/app/repositories/login_history_repo.py (create, query)
- [X] T009 Update backend/app/repositories/__init__.py to export new repositories

### Domain Validation

- [X] T010 Create domain validation utility in backend/app/core/domain_validator.py (is_allowed_domain, ALLOWED_DOMAINS)

### Cookie-Based Auth Infrastructure

- [X] T011 Modify get_current_user_token in backend/app/dependencies.py to extract JWT from HttpOnly cookie
- [X] T012 Add cookie setting helper in backend/app/core/security.py (set_auth_cookie, clear_auth_cookie)

**Checkpoint**: Foundation ready - user story implementation can begin

---

## Phase 3: User Story 1 - 내부 직원 OTP 로그인 (Priority: P1) 🎯 MVP

**Goal**: 내부 직원이 이메일로 OTP를 받아 로그인할 수 있다

**Independent Test**: @microsoft.com 이메일로 OTP 요청 → 이메일 수신 → 코드 입력 → 로그인 성공

### Implementation for User Story 1

- [X] T013 [US1] Add domain validation to auth_service.request_otp in backend/app/services/auth_service.py
- [X] T014 [US1] Complete AzureCommunicationEmailService.send_otp in backend/app/services/email_service.py
- [X] T015 [US1] Update OTP request endpoint to use domain validation and ACS in backend/app/api/v1/auth.py
- [X] T016 [US1] Return proper error response for invalid domain (400 DOMAIN_NOT_ALLOWED)
- [X] T017 [US1] Modify verify endpoint to set HttpOnly cookie on success in backend/app/api/v1/auth.py
- [X] T018 [US1] Remove dev_code from OTP response (FR-020) in backend/app/api/v1/auth.py
- [X] T019 [US1] Update OTPResponse schema to remove dev_code in backend/app/schemas/auth.py

**Checkpoint**: User Story 1 complete - internal employees can log in via OTP email

---

## Phase 4: User Story 2 - 비인가 도메인 로그인 차단 (Priority: P1)

**Goal**: 외부 도메인 이메일은 로그인이 차단된다

**Independent Test**: @gmail.com 이메일로 OTP 요청 시 "내부 직원 전용" 오류 메시지 확인

### Implementation for User Story 2

- [X] T020 [US2] Add unit tests for domain validation in backend/tests/test_domain_validation.py (include: allowed/blocked domains, email case normalization, previous OTP invalidation, concurrent OTP requests)
- [X] T021 [US2] Update frontend AuthModals to display domain error in frontend/components/auth/AuthModals.vue
- [X] T022 [US2] Add DOMAIN_NOT_ALLOWED error handling in frontend/lib/api.ts

**Checkpoint**: User Story 2 complete - unauthorized domains are blocked with proper error messages

---

## Phase 5: User Story 4 - Contributor 메뉴 접근 제어 (Priority: P1)

**Goal**: 비로그인 사용자는 Contributor 메뉴에 접근할 수 없다

**Independent Test**: 비로그인 상태에서 /contributor/edit 접근 시 로그인 모달 + 메시지 표시

### Implementation for User Story 4

- [X] T023 [US4] Update router guard to show login required message in frontend/router/index.ts
- [X] T024 [US4] Modify auth store to check authentication via cookie/API in frontend/stores/auth.ts
- [X] T025 [US4] Add /api/v1/auth/me endpoint for session validation in backend/app/api/v1/auth.py
- [X] T026 [US4] Update API client to use credentials: include for all requests in frontend/lib/api.ts
- [X] T027 [US4] Remove dev_code display from AuthModals (FR-020) in frontend/components/auth/AuthModals.vue

**Checkpoint**: User Story 4 complete - protected pages redirect to login with message

---

## Phase 6: User Story 5 - 백엔드 API 접근 제어 (Priority: P1)

**Goal**: Contributor API는 인증된 사용자만 호출할 수 있다

**Independent Test**: 쿠키 없이 /api/v1/content POST 시 401 Unauthorized 응답

### Implementation for User Story 5

- [X] T028 [US5] Ensure all Contributor endpoints use get_current_user dependency in backend/app/api/v1/content.py (already implemented)
- [X] T029 [US5] Ensure all Contributor endpoints use get_current_user dependency in backend/app/api/v1/analysis.py (already implemented)
- [X] T030 [US5] Add integration tests for protected API endpoints in backend/tests/test_auth_api.py

**Checkpoint**: User Story 5 complete - API returns 401 for unauthenticated requests

---

## Phase 7: User Story 3 - 로그인 세션 유지 (Priority: P2)

**Goal**: 로그인한 사용자는 7일간 세션이 유지된다

**Independent Test**: 로그인 후 브라우저 재시작 → 세션 유지 확인

### Implementation for User Story 3

- [X] T031 [US3] Verify JWT expiration is 7 days in backend/app/core/security.py (already configured: jwt_refresh_token_expire_days=7)
- [X] T032 [US3] Verify cookie Max-Age is 604800 (7 days) in backend/app/api/v1/auth.py (already configured: COOKIE_MAX_AGE = 7 * 24 * 60 * 60)
- [X] T033 [US3] Update frontend to check session on app mount in frontend/stores/auth.ts (added checkSession method)
- [X] T034 [US3] Add session validation API call on page load in frontend/App.vue (added onMounted checkSession)

**Checkpoint**: User Story 3 complete - sessions persist for 7 days

---

## Phase 8: User Story 6 - OTP 재발송 제한 (Priority: P2)

**Goal**: 동일 이메일로 3분 내 OTP 재발송이 차단된다

**Independent Test**: OTP 발송 직후 재발송 요청 시 "X분 후에 다시 시도해주세요" 메시지

### Implementation for User Story 6

- [X] T035 [US6] Add otp_ttl_minutes and otp_rate_limit_minutes config in backend/app/config.py (3 minutes each)
- [X] T036 [US6] Add rate limit handling for OTP resend in frontend/components/auth/AuthModals.vue
- [X] T037 [US6] Display countdown timer in AuthModals in frontend/components/auth/AuthModals.vue

**Checkpoint**: User Story 6 complete - OTP resend is limited to 3 minutes

---

## Phase 9: User Story 7 - 로그아웃 (Priority: P2)

**Goal**: 로그아웃 시 세션이 종료되고 메인 페이지로 이동한다

**Independent Test**: 로그아웃 클릭 → 쿠키 삭제 → Workshops 페이지로 이동

### Implementation for User Story 7

- [X] T038 [US7] Add POST /api/v1/auth/logout endpoint in backend/app/api/v1/auth.py
- [X] T039 [US7] Add logout method to API client in frontend/lib/api.ts
- [X] T040 [US7] Update logout action to call API in frontend/stores/auth.ts
- [X] T041 [US7] Add logout tests in backend/tests/test_auth_api.py

**Checkpoint**: User Story 7 complete - logout clears session and redirects

---

## Phase 10: User Story 8 - 로그인 기록 저장 (Priority: P3)

**Goal**: 로그인 성공 시 이력이 기록된다

**Independent Test**: 로그인 성공 후 login_history 컨테이너에 레코드 생성 확인

### Implementation for User Story 8

- [X] T042 [US8] Save login history on successful verification in backend/app/api/v1/auth.py
- [X] T043 [US8] Add user_agent and ip_address extraction from request in backend/app/api/v1/auth.py
- [X] T044 [US8] Add unit tests for login history recording in backend/tests/test_auth_api.py

**Checkpoint**: User Story 8 complete - login history is recorded

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Final cleanup and validation

- [X] T045 [P] Remove localStorage token storage from auth store (only persist user info) in frontend/stores/auth.ts
- [X] T046 [P] Update tests to use @microsoft.com domain for OTP tests
- [X] T047 Run full test suite: pytest backend/tests/ -v - ✅ 41 tests passed
- [X] T048 Run frontend tests: npm run test (from frontend/) - ✅ 1 test passed
- [X] T049 Manual E2E test following quickstart.md scenarios - ✅ OTP 이메일 발송, 로그인, 로그아웃 확인 완료

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
    │
    ▼
Phase 2 (Foundational) ─────────────────────────────────────┐
    │                                                        │
    ├──────────────┬──────────────┬──────────────┐          │
    ▼              ▼              ▼              ▼          │
Phase 3        Phase 4        Phase 5        Phase 6        │
(US1-OTP)      (US2-Domain)   (US4-Menu)     (US5-API)      │
    │              │              │              │          │
    └──────────────┴──────────────┴──────────────┘          │
                        │                                    │
    ┌───────────────────┼───────────────────┐               │
    ▼                   ▼                   ▼               │
Phase 7            Phase 8             Phase 9              │
(US3-Session)      (US6-Resend)        (US7-Logout)         │
    │                   │                   │               │
    └───────────────────┴───────────────────┘               │
                        │                                    │
                        ▼                                    │
                   Phase 10                                  │
                   (US8-History)                             │
                        │                                    │
                        ▼                                    │
                   Phase 11 (Polish) ◄───────────────────────┘
```

### User Story Dependencies

| Story | Depends On | Can Parallel With |
|-------|------------|-------------------|
| US1 (OTP Login) | Phase 2 | - |
| US2 (Domain Block) | US1 (T016) | US4, US5 |
| US4 (Menu Access) | Phase 2 | US2, US5, US6 |
| US5 (API Access) | Phase 2 | US2, US4, US6 |
| US3 (Session) | US1 | US6, US7 |
| US6 (Resend Limit) | US1 | US3, US7 |
| US7 (Logout) | US1 | US3, US6 |
| US8 (History) | US1 | - |

### Parallel Opportunities per Phase

**Phase 2 (Foundational)**:
```
T004 (LoginAttempt model) ─┐
T005 (LoginHistory model) ─┼─► T006 (exports)
                           │
T007 (LoginAttemptRepo) ───┼─► T009 (exports)
T008 (LoginHistoryRepo) ───┘
                           │
T010 (domain validator) ───┼─► Can run independently
T011, T012 (cookie auth) ──┘
```

**P1 Stories (US1, US2, US4, US5)** - After Phase 2:
```
US1 completes first (core login)
    │
    ├── US2 (domain errors) ─┐
    ├── US4 (menu guard) ────┼─► Can run in parallel
    └── US5 (API guard) ─────┘
```

**P2 Stories (US3, US6, US7)** - After US1:
```
US3 (session) ────┐
US6 (resend) ─────┼─► Can run in parallel
US7 (logout) ─────┘
```

---

## Summary

| Phase | Story | Tasks | Priority | Effort |
|-------|-------|-------|----------|--------|
| 1 | Setup | T001-T003 | - | 1h |
| 2 | Foundational | T004-T012 | - | 4h |
| 3 | US1 - OTP Login | T013-T019 | P1 | 4h |
| 4 | US2 - Domain Block | T020-T022 | P1 | 2h |
| 5 | US4 - Menu Access | T023-T027 | P1 | 3h |
| 6 | US5 - API Access | T028-T030 | P1 | 2h |
| 7 | US3 - Session | T031-T034 | P2 | 2h |
| 8 | US6 - Resend Limit | T035-T037 | P2 | 2h |
| 9 | US7 - Logout | T038-T041 | P2 | 2h |
| 10 | US8 - History | T042-T044 | P3 | 2h |
| 11 | Polish | T045-T049 | - | 2h |
| **Total** | | **49 tasks** | | **~26h** |

---

## MVP Scope

**Minimum Viable Product** (P1 stories only):
- Phase 1: Setup (T001-T003)
- Phase 2: Foundational (T004-T012)
- Phase 3: US1 - OTP Login (T013-T019)
- Phase 4: US2 - Domain Block (T020-T022)
- Phase 5: US4 - Menu Access (T023-T027)
- Phase 6: US5 - API Access (T028-T030)

**MVP Total**: 30 tasks, ~16h estimated effort
