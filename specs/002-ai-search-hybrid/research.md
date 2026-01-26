# Research: Azure AI Search 하이브리드 검색

**Feature**: 002-ai-search-hybrid  
**Date**: 2026-01-26  
**Status**: Complete

## 1. Azure AI Search 연동 방식

### Decision: REST API 직접 호출 (기존 구현 유지)

**Rationale**: 
- 기존 `search_service.py`가 httpx 기반 REST API로 구현되어 있음
- Azure SDK (`azure-search-documents`)보다 가볍고 의존성이 적음
- 이미 동작하는 코드가 있으므로 변경 불필요

**Alternatives Considered**:
- `azure-search-documents` SDK: 추가 의존성, 기존 코드 재작성 필요
- CosmosDB 직접 검색: 벡터 검색 미지원, 복잡한 쿼리 성능 저하

## 2. 벡터 임베딩 모델 선택

### Decision: text-embedding-3-small (1536차원)

**Rationale**:
- Azure OpenAI에 이미 배포되어 있음 (`azure_openai_embedding_deployment`)
- 비용 효율적 (text-embedding-3-large 대비 저렴)
- 1536차원으로 충분한 시맨틱 표현력
- 기존 `llm_service.py`에 `generate_embedding` 메서드 구현됨

**Alternatives Considered**:
- text-embedding-3-large (3072차원): 더 높은 품질이나 비용/저장공간 증가
- text-embedding-ada-002: 레거시 모델, 신규 모델이 더 우수

## 3. 임베딩 대상 필드

### Decision: title + description + technologies 결합

**Rationale**:
- title: 핵심 키워드 포함
- description: 상세 내용 설명
- technologies: 기술 스택 (중요한 검색 키워드)
- 한국어 필드(title_kr, description_kr)도 포함하여 다국어 검색 지원

**생성 로직**:
```python
embedding_text = f"{title} {title_kr or ''} {description} {description_kr or ''} {' '.join(technologies or [])}"
```

**Alternatives Considered**:
- 개별 필드별 임베딩: 저장 공간 증가, 복잡도 증가
- learning_outcomes 포함: 텍스트가 길어져 임베딩 품질 저하 가능

## 4. 인덱스 스키마 검토

### Decision: 기존 INDEX_SCHEMA 유지 (search_service.py)

**현재 스키마 분석**:
```python
# 검색 가능 필드 (searchable: True)
- title (en.microsoft analyzer)
- title_kr (ko.microsoft analyzer)
- description
- summary
- categories (Collection)
- technologies (Collection)

# 필터 가능 필드 (filterable: True)
- categories, technologies, difficulty_level
- content_type, visibility
- stars, popularity_score

# 정렬 가능 필드 (sortable: True)
- title, popularity_score, stars
- last_commit_date, created_at

# 벡터 필드
- content_vector (1536차원, HNSW, cosine)
```

**Rationale**: 스키마가 이미 최적화되어 있음. 변경 불필요.

## 5. 콘텐츠 동기화 전략

### Decision: 동기식 인덱싱 (CRUD 시 즉시 반영)

**Rationale**:
- 콘텐츠 생성/수정 빈도가 낮음 (분당 몇 건 미만)
- 실시간 반영이 UX에 중요
- 비동기 큐 도입 시 복잡도 증가

**구현 방식**:
1. `content_service.py`의 create/update/delete 메서드에서
2. `search_service.upsert_document()` 또는 `delete_document()` 호출
3. 임베딩은 `llm_service.generate_embedding()`으로 생성

**Alternatives Considered**:
- Change Feed + Azure Function: 복잡도 증가, 지연 발생
- 주기적 배치 동기화: 실시간성 부족
- Service Bus 큐: 오버엔지니어링

## 6. 에러 처리 및 폴백

### Decision: 단계별 폴백 전략

1. **임베딩 생성 실패**: 키워드 검색만 수행 (벡터 없이)
2. **Azure AI Search 불가**: 에러 메시지 반환 (CosmosDB 폴백 고려)
3. **인덱싱 실패**: 로그 기록, 재시도 큐에 추가 (향후 구현)

**Rationale**: 검색은 핵심 기능이므로 graceful degradation 필요

## 7. 성능 최적화

### Decision: 기존 설정 유지

**현재 설정**:
- HNSW parameters: m=4, efConstruction=400, efSearch=500
- Scoring profile: popularity-boost (freshness + magnitude)
- Facets: categories, technologies, difficulty_level

**Rationale**: 초기 데이터 규모(100개 이하)에서는 충분. 필요시 튜닝.

## 8. 필요한 Azure 리소스 정보

### 확인 필요 항목

| 항목 | 값 | 상태 |
|------|-----|------|
| Search Service Name | srch-buildflow-dev-wcea6l3wulmzi | ✅ 확인됨 |
| Search Endpoint | https://srch-buildflow-dev-wcea6l3wulmzi.search.windows.net | 🔧 확인 필요 |
| Admin API Key | (Azure Portal에서 조회) | 🔧 설정 필요 |
| Index Name | buildflow-content | ✅ 코드에 정의됨 |

## 9. 환경 변수 설정

### .env.local에 추가할 항목

```bash
# Azure AI Search
AZURE_SEARCH_ENDPOINT=https://srch-buildflow-dev-wcea6l3wulmzi.search.windows.net
AZURE_SEARCH_API_KEY=<admin-api-key-from-portal>
AZURE_SEARCH_INDEX_NAME=buildflow-content
```

## 10. 구현 우선순위

| 순서 | 작업 | 우선순위 | 예상 시간 |
|-----|------|----------|---------|
| 1 | 환경 변수 설정 | P1 | 10분 |
| 2 | 인덱스 생성 스크립트 | P1 | 30분 |
| 3 | 기존 콘텐츠 일괄 인덱싱 | P1 | 1시간 |
| 4 | content_service 인덱싱 연동 | P1 | 1시간 |
| 5 | E2E 테스트 | P1 | 30분 |
| 6 | 프론트엔드 검색 테스트 | P2 | 30분 |
