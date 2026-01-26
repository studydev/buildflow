# Feature Specification: Azure AI Search 하이브리드 검색

**Feature Branch**: `002-ai-search-hybrid`  
**Created**: 2026-01-26  
**Status**: Draft  
**Input**: Azure AI Search 기반 키워드 + 벡터 하이브리드 검색 구현

## 개요

CosmosDB의 `contents` 컨테이너에 저장된 워크샵/랩/튜토리얼 콘텐츠를 Azure AI Search(`srch-buildflow-dev-wcea6l3wulmzi`)를 통해 검색할 수 있도록 연동합니다. 키워드 검색과 text-embedding-3-small 기반 벡터 검색을 결합한 하이브리드 검색을 지원하여 사용자가 더 정확하고 의미 있는 검색 결과를 얻을 수 있도록 합니다.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 키워드 검색으로 콘텐츠 찾기 (Priority: P1)

사용자가 Home 페이지의 검색창에 "Azure OpenAI"를 입력하면, 제목, 설명, 기술 스택에 해당 키워드가 포함된 콘텐츠가 카드 형태로 표시됩니다.

**Why this priority**: 키워드 검색은 가장 기본적이고 직관적인 검색 방식으로, 사용자가 정확한 용어를 알고 있을 때 빠르게 원하는 콘텐츠를 찾을 수 있습니다.

**Independent Test**: 검색창에 "Azure OpenAI" 입력 → 관련 콘텐츠 카드 표시 확인

**Acceptance Scenarios**:

1. **Given** 사용자가 Home 페이지에 있고 콘텐츠가 인덱싱되어 있을 때, **When** 검색창에 "RAG"를 입력하면, **Then** 제목/설명/기술에 "RAG"가 포함된 콘텐츠가 카드로 표시된다
2. **Given** 검색 결과가 표시된 상태에서, **When** 검색어를 지우면, **Then** 전체 콘텐츠 목록이 다시 표시된다
3. **Given** 존재하지 않는 키워드로 검색했을 때, **When** 결과가 없으면, **Then** "검색 결과가 없습니다" 메시지가 표시된다

---

### User Story 2 - 시맨틱(벡터) 검색으로 관련 콘텐츠 찾기 (Priority: P1)

사용자가 "AI 에이전트 만드는 방법"과 같은 자연어 질문을 입력하면, 정확히 일치하는 키워드가 없더라도 의미적으로 관련된 콘텐츠가 검색됩니다.

**Why this priority**: 벡터 검색은 사용자가 정확한 기술 용어를 모르더라도 의도에 맞는 콘텐츠를 찾을 수 있게 해주어 검색 경험을 크게 향상시킵니다.

**Independent Test**: "챗봇 개발 워크샵" 검색 → Azure OpenAI 관련 콘텐츠 반환 확인 (키워드 불일치하지만 의미적 관련성)

**Acceptance Scenarios**:

1. **Given** 사용자가 "LLM 기반 애플리케이션 구축"을 검색할 때, **When** 정확히 일치하는 제목이 없더라도, **Then** Azure OpenAI, GPT 관련 워크샵이 결과에 포함된다
2. **Given** 한국어로 "프롬프트 엔지니어링 배우기"를 검색할 때, **When** 검색을 실행하면, **Then** 영어 제목의 프롬프트 엔지니어링 콘텐츠도 결과에 포함된다

---

### User Story 3 - 하이브리드 검색으로 최적 결과 얻기 (Priority: P1)

사용자가 검색 모드를 "Hybrid"로 선택하면, 키워드 매칭과 시맨틱 유사도를 결합하여 가장 관련성 높은 결과를 상위에 표시합니다.

**Why this priority**: 하이브리드 검색은 키워드와 벡터 검색의 장점을 결합하여 최상의 검색 품질을 제공합니다.

**Independent Test**: 하이브리드 모드로 "Azure AI Search RAG" 검색 → 정확한 키워드 매칭 + 관련 콘텐츠 모두 결과에 포함

**Acceptance Scenarios**:

1. **Given** 검색 모드가 "Hybrid"로 설정되어 있을 때, **When** "Azure AI Search 튜토리얼"을 검색하면, **Then** 정확히 일치하는 콘텐츠가 최상위에, 관련 콘텐츠가 그 아래에 표시된다
2. **Given** 하이브리드 검색 결과에서, **When** 결과 카드를 확인하면, **Then** 관련성 점수순으로 정렬되어 있다

---

### User Story 4 - CosmosDB 콘텐츠 자동 인덱싱 (Priority: P2)

관리자가 CosmosDB에 새 콘텐츠를 추가하면, 해당 콘텐츠가 자동으로 Azure AI Search 인덱스에 추가되어 검색 가능해집니다.

**Why this priority**: 콘텐츠 추가/수정 시 자동 인덱싱은 운영 효율성과 데이터 일관성을 보장합니다.

**Independent Test**: 새 콘텐츠 생성 API 호출 → 검색 인덱스에 반영 확인 → 검색으로 조회 가능

**Acceptance Scenarios**:

1. **Given** 관리자가 새 워크샵 콘텐츠를 생성할 때, **When** 콘텐츠가 CosmosDB에 저장되면, **Then** 5분 이내에 검색 인덱스에 반영되어 검색 가능해진다
2. **Given** 기존 콘텐츠의 제목을 수정할 때, **When** 업데이트가 저장되면, **Then** 변경된 제목으로 검색 시 해당 콘텐츠가 조회된다
3. **Given** 콘텐츠가 삭제될 때, **When** CosmosDB에서 제거되면, **Then** 검색 인덱스에서도 제거되어 더 이상 검색되지 않는다

---

### User Story 5 - 검색 필터링 및 정렬 (Priority: P2)

사용자가 카테고리, 난이도, 기술 스택 등으로 검색 결과를 필터링하고, 관련성/인기도/별점 등으로 정렬할 수 있습니다.

**Why this priority**: 필터와 정렬은 대량의 검색 결과에서 원하는 콘텐츠를 효율적으로 찾는 데 필수적입니다.

**Independent Test**: 카테고리 "AI" 필터 + 난이도 "beginner" 필터 적용 → 조건에 맞는 결과만 표시

**Acceptance Scenarios**:

1. **Given** 검색 결과가 표시된 상태에서, **When** 카테고리 필터로 "Azure"를 선택하면, **Then** Azure 카테고리 콘텐츠만 표시된다
2. **Given** 필터가 적용된 상태에서, **When** 정렬을 "Most Stars"로 변경하면, **Then** 결과가 GitHub 별점 높은 순으로 재정렬된다
3. **Given** 여러 필터가 적용된 상태에서, **When** "필터 초기화" 버튼을 클릭하면, **Then** 모든 필터가 해제되고 전체 결과가 표시된다

---

### Edge Cases

- 검색어가 너무 짧을 때 (1-2글자): 키워드 검색으로 fallback하거나 최소 글자 수 안내
- 특수문자만 포함된 검색어: 적절한 에러 메시지 표시
- Azure AI Search 서비스 일시 불가 시: CosmosDB 직접 쿼리로 fallback 또는 에러 메시지
- 임베딩 생성 실패 시: 키워드 검색만으로 결과 반환
- 대량 동시 검색 요청 시: 요청 제한 및 큐잉 처리

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 시스템은 Azure AI Search 인덱스를 생성하고 CosmosDB contents 컨테이너의 스키마와 동기화해야 한다
- **FR-002**: 시스템은 콘텐츠의 title, title_kr, description, description_kr, technologies, learning_outcomes 필드를 검색 가능하도록 인덱싱해야 한다
- **FR-003**: 시스템은 categories, level, content_type 필드로 필터링을 지원해야 한다
- **FR-004**: 시스템은 stars, created_at, popularity_score 필드로 정렬을 지원해야 한다
- **FR-005**: 시스템은 text-embedding-3-small 모델을 사용하여 콘텐츠 벡터를 생성해야 한다
- **FR-006**: 시스템은 title + description + technologies를 결합한 텍스트로 임베딩을 생성해야 한다
- **FR-007**: 시스템은 키워드 검색, 벡터 검색, 하이브리드 검색 세 가지 모드를 지원해야 한다
- **FR-008**: 시스템은 콘텐츠 생성/수정/삭제 시 검색 인덱스를 자동 업데이트해야 한다
- **FR-009**: 프론트엔드는 검색 모드 선택 UI를 제공해야 한다
- **FR-010**: 시스템은 검색 결과에 대해 facet(카테고리별, 기술별 집계)을 반환해야 한다

### Key Entities

- **Content**: 워크샵/랩/튜토리얼 콘텐츠 (CosmosDB에 저장)
- **SearchIndex**: Azure AI Search 인덱스 (buildflow-content)
- **Embedding**: 콘텐츠별 벡터 표현 (1536차원, text-embedding-3-small)
- **SearchQuery**: 사용자 검색 요청 (쿼리문, 모드, 필터, 정렬)
- **SearchResult**: 검색 결과 (콘텐츠 + 관련성 점수)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 사용자가 검색어 입력 후 2초 이내에 검색 결과를 확인할 수 있다
- **SC-002**: 하이브리드 검색이 키워드 단독 검색 대비 관련성 높은 결과를 상위에 노출한다 (상위 5개 결과의 사용자 만족도 향상)
- **SC-003**: 콘텐츠 추가/수정 후 5분 이내에 검색 인덱스에 반영된다
- **SC-004**: 검색 서비스 가용성 99.9% 유지 (월간 다운타임 43분 이하)
- **SC-005**: 동시 50명 사용자 검색 시 평균 응답 시간 3초 이내 유지
- **SC-006**: 한국어/영어 검색 모두 관련 콘텐츠 검색 가능 (언어 무관 검색 지원)

## Assumptions

- Azure AI Search 서비스(`srch-buildflow-dev-wcea6l3wulmzi`)가 이미 배포되어 있음
- CosmosDB(`cosmos-buildflow-dev-yk6s7exodrar2`)의 `buildflow` 데이터베이스에 `contents` 컨테이너 존재
- Azure OpenAI 서비스에서 `text-embedding-3-small` 모델 사용 가능
- 현재 `search_service.py`에 기본 구조가 구현되어 있으며, 실제 연동 및 벡터 검색 통합 필요
- 프론트엔드에 검색 UI 기본 구조가 존재하며, 실제 API 연동 필요
