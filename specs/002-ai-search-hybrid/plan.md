# Implementation Plan: Azure AI Search 하이브리드 검색

**Branch**: `002-ai-search-hybrid` | **Date**: 2026-01-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-ai-search-hybrid/spec.md`

## Summary

CosmosDB `contents` 컨테이너에 저장된 워크샵/랩 콘텐츠를 Azure AI Search(`srch-buildflow-dev-wcea6l3wulmzi`)를 통해 키워드 + 벡터 하이브리드 검색으로 제공합니다. 기존 `search_service.py`와 `search.py` API가 이미 구현되어 있으므로, Azure AI Search 연결 설정, 인덱스 생성, 기존 콘텐츠 인덱싱, 그리고 콘텐츠 CRUD 시 자동 동기화를 구현합니다.

## Technical Context

**Language/Version**: Python 3.9, TypeScript 5.x  
**Primary Dependencies**: FastAPI, httpx, Azure AI Search REST API, Azure OpenAI (text-embedding-3-small), Vue 3, Pinia  
**Storage**: Azure Cosmos DB (contents), Azure AI Search (buildflow-content index)  
**Testing**: pytest (backend), vitest (frontend)  
**Target Platform**: Azure Container Apps (backend), Azure Static Web Apps (frontend)  
**Project Type**: Web application (frontend + backend separated)  
**Performance Goals**: 검색 응답 2초 이내, 하이브리드 검색 품질 향상  
**Constraints**: 인덱스 동기화 5분 이내  
**Scale/Scope**: 초기 100개 콘텐츠, 확장 가능

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Frontend-Backend Separation | ✅ PASS | 프론트엔드는 `/api/v1/search` API만 호출 |
| II. API-First Design | ✅ PASS | 기존 `/api/v1/search` 엔드포인트 사용 |
| III. Stateless Authentication | ✅ PASS | JWT 기반 인증, 검색은 옵션 인증 |
| IV. Request Traceability | ✅ PASS | correlation_id 포함 |
| V. Fail-Fast Validation | ✅ PASS | 검색어 유효성 검증 |
| VI. Pipeline-First Architecture | ✅ PASS | 인덱싱은 콘텐츠 CRUD 시 비동기 처리 가능 |
| VII. Azure-Only Execution | ✅ PASS | Azure AI Search, Azure OpenAI 사용 |

## Project Structure

### Documentation (this feature)

```text
specs/002-ai-search-hybrid/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/v1/
│   │   └── search.py           # ✅ 이미 구현됨 - 하이브리드 검색 API
│   ├── services/
│   │   ├── search_service.py   # ✅ 이미 구현됨 - Azure AI Search 클라이언트
│   │   ├── content_service.py  # 🔧 수정 필요 - 인덱싱 연동 추가
│   │   └── llm_service.py      # ✅ 이미 구현됨 - 임베딩 생성
│   └── config.py               # 🔧 수정 필요 - Search 환경변수 확인
├── scripts/
│   └── seed_search_index.py    # 🆕 신규 - 초기 인덱싱 스크립트
└── tests/
    └── test_search_api.py      # 🆕 신규 - 검색 API 테스트

frontend/
├── src/
│   ├── stores/
│   │   └── content.ts          # ✅ 이미 구현됨 - 검색 상태 관리
│   └── views/
│       └── Home.vue            # ✅ 이미 구현됨 - 검색 UI
└── tests/
    └── search.spec.ts          # 🆕 신규 - 검색 UI 테스트
```

**Structure Decision**: 기존 프로젝트 구조 유지. 대부분의 코드가 이미 구현되어 있으므로 설정 연동과 인덱싱 동기화에 집중.

## Existing Implementation Analysis

### 이미 구현된 기능 (재사용)

1. **search_service.py** (760 lines)
   - Azure AI Search REST API 클라이언트
   - 인덱스 스키마 정의 (INDEX_SCHEMA)
   - hybrid_search, keyword_search, vector_search 메서드
   - upsert_document, delete_document 메서드
   - HNSW 벡터 검색 프로파일 설정
   - Scoring profile (popularity-boost)

2. **search.py API** (240 lines)
   - GET `/api/v1/search` 엔드포인트
   - SearchMode enum (hybrid, keyword, vector)
   - 필터링 (categories, technologies, difficulty, min_stars)
   - 임베딩 생성 연동 (llm_service)
   - 인증 옵션 (visibility 필터)

3. **content.ts store** (740 lines)
   - advancedSearch 액션
   - SearchParams, SearchResponse 타입
   - 검색 모드, 필터, 정렬 상태 관리

4. **Home.vue** (443 lines)
   - 검색 입력 UI
   - 검색 모드 선택
   - 고급 필터 UI
   - URL 파라미터 동기화

### 누락된 구현 (신규 작업)

1. **환경 설정**: Azure AI Search 연결 정보 (.env.local)
2. **인덱스 초기화**: 인덱스 생성 및 기존 콘텐츠 일괄 인덱싱
3. **자동 동기화**: 콘텐츠 생성/수정/삭제 시 검색 인덱스 업데이트
4. **임베딩 생성**: 콘텐츠 저장 시 벡터 임베딩 생성
5. **테스트**: 검색 기능 통합 테스트

## Complexity Tracking

> 위반 사항 없음 - 기존 구현 활용으로 최소한의 변경만 필요

---

## Phase 1 Design Complete

### Generated Artifacts

| File | Description | Status |
|------|-------------|--------|
| [research.md](research.md) | 기술 결정 및 대안 분석 | ✅ Complete |
| [data-model.md](data-model.md) | 인덱스 스키마 및 엔티티 매핑 | ✅ Complete |
| [contracts/search-api.yaml](contracts/search-api.yaml) | OpenAPI 스펙 | ✅ Complete |
| [quickstart.md](quickstart.md) | 구현 가이드 | ✅ Complete |

### Constitution Re-Check (Post Phase 1)

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Frontend-Backend Separation | ✅ PASS | API 계약 분리 확인됨 |
| II. API-First Design | ✅ PASS | OpenAPI 스펙 작성 완료 |
| III. Stateless Authentication | ✅ PASS | JWT 옵션 인증 유지 |
| IV. Request Traceability | ✅ PASS | correlation_id 포함 |
| V. Fail-Fast Validation | ✅ PASS | 검색어 유효성 검증 |
| VI. Pipeline-First Architecture | ✅ PASS | 동기 인덱싱 (저빈도 작업) |
| VII. Azure-Only Execution | ✅ PASS | Azure 서비스만 사용 |

### Next Step

`/speckit.tasks` 명령으로 상세 태스크 분해를 진행합니다.
