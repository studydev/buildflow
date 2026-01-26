# Quickstart: Azure AI Search 하이브리드 검색

**Feature**: 002-ai-search-hybrid  
**Date**: 2026-01-26

## 사전 요구사항

- Azure AI Search 서비스: `srch-buildflow-dev-wcea6l3wulmzi`
- Azure Portal 접근 권한 (API 키 조회용)
- 백엔드 개발 환경 설정 완료

## 1. 환경 변수 설정

### 1.1 Azure Portal에서 API 키 조회

1. Azure Portal → `srch-buildflow-dev-wcea6l3wulmzi` 검색 서비스
2. Settings → Keys
3. **Primary admin key** 또는 **Secondary admin key** 복사

### 1.2 .env.local 업데이트

```bash
cd /Users/hyounsookim/Desktop/Azure/buildflow/backend

# .env.local에 추가
AZURE_SEARCH_ENDPOINT=https://srch-buildflow-dev-wcea6l3wulmzi.search.windows.net
AZURE_SEARCH_API_KEY=<복사한-admin-api-key>
AZURE_SEARCH_INDEX_NAME=buildflow-content
```

## 2. 검색 인덱스 생성

### 2.1 인덱스 생성 스크립트 실행

```bash
cd /Users/hyounsookim/Desktop/Azure/buildflow/backend
python -m scripts.seed_search_index --create-index
```

### 2.2 인덱스 생성 확인

```bash
# curl로 확인
curl -X GET "https://srch-buildflow-dev-wcea6l3wulmzi.search.windows.net/indexes/buildflow-content?api-version=2024-07-01" \
  -H "api-key: <your-api-key>"
```

## 3. 기존 콘텐츠 인덱싱

### 3.1 일괄 인덱싱 실행

```bash
cd /Users/hyounsookim/Desktop/Azure/buildflow/backend
python -m scripts.seed_search_index --index-all
```

예상 출력:
```
Loading content from CosmosDB...
Found 10 content items
Generating embeddings...
Indexing content 1/10: Azure OpenAI Prompt Engineering Workshop
Indexing content 2/10: LAB511: Build Agentic Knowledge Bases
...
Successfully indexed 10 items
```

### 3.2 인덱싱 확인

```bash
# 문서 개수 확인
curl -X GET "https://srch-buildflow-dev-wcea6l3wulmzi.search.windows.net/indexes/buildflow-content/docs/\$count?api-version=2024-07-01" \
  -H "api-key: <your-api-key>"
```

## 4. 검색 테스트

### 4.1 백엔드 시작

```bash
cd /Users/hyounsookim/Desktop/Azure/buildflow/backend
python -m uvicorn app.main:app --reload --port 8000
```

### 4.2 API 테스트

```bash
# 하이브리드 검색
curl "http://localhost:8000/api/v1/search?q=Azure%20OpenAI&mode=hybrid"

# 키워드 검색
curl "http://localhost:8000/api/v1/search?q=RAG&mode=keyword"

# 벡터 검색
curl "http://localhost:8000/api/v1/search?q=AI%20에이전트%20만들기&mode=vector"

# 필터링
curl "http://localhost:8000/api/v1/search?q=workshop&categories=AI&difficulty=beginner"
```

### 4.3 예상 응답

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "a0ad946b-3524-419f-b7f8-4b719b8cedf6",
        "title": "Azure OpenAI Prompt Engineering Samples and Workshop (Korean)",
        "description": "...",
        "categories": ["AI", "Azure"],
        "technologies": ["Azure OpenAI Service", "Python"],
        "difficulty_level": "beginner",
        "popularity_score": 0.85,
        "stars": 182,
        "score": 12.5
      }
    ],
    "total": 5,
    "facets": {
      "categories": [{"value": "AI", "count": 3}],
      "technologies": [{"value": "Azure OpenAI", "count": 2}]
    },
    "query": "Azure OpenAI",
    "mode": "hybrid",
    "limit": 20,
    "offset": 0
  },
  "meta": {
    "timestamp": "2026-01-26T12:00:00Z",
    "correlationId": "abc123"
  }
}
```

## 5. 프론트엔드 테스트

### 5.1 프론트엔드 시작

```bash
cd /Users/hyounsookim/Desktop/Azure/buildflow
npm run dev
```

### 5.2 브라우저에서 테스트

1. http://localhost:5173 접속
2. 검색창에 "Azure OpenAI" 입력
3. 검색 결과 카드 확인
4. 검색 모드 변경 (Hybrid → Keyword → Semantic)
5. 필터 적용 테스트

## 6. 트러블슈팅

### 6.1 검색 결과가 없는 경우

```bash
# 인덱스에 문서가 있는지 확인
curl "https://srch-buildflow-dev-wcea6l3wulmzi.search.windows.net/indexes/buildflow-content/docs/\$count?api-version=2024-07-01" \
  -H "api-key: <your-api-key>"

# 인덱스 스키마 확인
curl "https://srch-buildflow-dev-wcea6l3wulmzi.search.windows.net/indexes/buildflow-content?api-version=2024-07-01" \
  -H "api-key: <your-api-key>"
```

### 6.2 벡터 검색이 작동하지 않는 경우

```bash
# Azure OpenAI 임베딩 테스트
cd /Users/hyounsookim/Desktop/Azure/buildflow/backend
python -c "
import asyncio
from app.services.llm_service import get_llm_service

async def test():
    llm = get_llm_service()
    embedding = await llm.generate_embedding('테스트')
    print(f'Embedding dimension: {len(embedding)}')

asyncio.run(test())
"
```

### 6.3 401/403 에러

- API 키가 올바른지 확인
- Admin key vs Query key 구분 (인덱스 생성은 Admin key 필요)

## 7. 다음 단계

1. **자동 동기화 구현**: 콘텐츠 CRUD 시 자동 인덱싱
2. **통합 테스트 작성**: pytest 기반 검색 API 테스트
3. **성능 모니터링**: 검색 지연 시간 모니터링 설정
