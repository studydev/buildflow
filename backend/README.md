# NexusSkill Backend API

> 📦 **코드명:** BuildFlow Backend

FastAPI 기반 백엔드 API - 콘텐츠 관리, GitHub 분석, AI 파이프라인

## 🚀 빠른 시작

### 사전 요구사항

- Python 3.9+
- pip

### 로컬 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# 개발 서버 실행
uvicorn app.main:app --reload --port 8000

# 또는 Docker로 실행
docker build -t buildflow-api .
docker run -p 8000:8000 buildflow-api
```

### 헬스 체크

```bash
curl http://localhost:8000/health

# 응답:
# {"success": true, "data": {"status": "healthy"}, "meta": {...}}
```

## 📚 API 문서

| 문서 | URL |
|------|-----|
| Swagger UI | http://localhost:8000/api/v1/docs |
| ReDoc | http://localhost:8000/api/v1/redoc |
| OpenAPI JSON | http://localhost:8000/api/v1/openapi.json |

## 📁 프로젝트 구조

```
backend/
├── app/
│   ├── main.py              # FastAPI 앱 팩토리
│   ├── config.py            # 환경 설정
│   ├── dependencies.py      # 의존성 주입
│   ├── api/v1/              # API 엔드포인트
│   │   ├── admin.py         # 관리자 API
│   │   ├── analysis.py      # GitHub 분석 API
│   │   ├── assistant.py     # AI 어시스턴트 API
│   │   ├── auth.py          # 인증 API (OTP)
│   │   ├── content.py       # 콘텐츠 CRUD API
│   │   ├── search.py        # 검색 API
│   │   └── users.py         # 사용자 API
│   ├── core/                # 핵심 유틸리티
│   │   ├── domain_validator.py  # 도메인 검증 (내부 직원)
│   │   ├── exceptions.py    # 커스텀 예외
│   │   ├── middleware.py    # 미들웨어
│   │   ├── rate_limit.py    # 요청 제한
│   │   ├── retry.py         # 재시도 로직
│   │   └── security.py      # 보안 유틸 (JWT, OTP)
│   ├── db/                  # 데이터베이스
│   │   └── cosmos.py        # Cosmos DB 클라이언트
│   ├── models/              # Pydantic 모델
│   │   ├── analysis.py      # 분석 모델
│   │   ├── content.py       # 콘텐츠 모델
│   │   ├── login_attempt.py # OTP 로그인 시도 모델
│   │   ├── login_history.py # 로그인 이력 모델
│   │   └── user.py          # 사용자 모델
│   ├── repositories/        # 데이터 저장소
│   ├── schemas/             # API 스키마
│   └── services/            # 비즈니스 로직
│       ├── assistant_service.py    # AI 어시스턴트 (RAG)
│       ├── content_service.py      # 콘텐츠 관리
│       ├── github_service.py       # GitHub API 연동
│       ├── image_generation_service.py  # DALL-E 썸네일
│       ├── llm_service.py          # Azure OpenAI 분석
│       ├── search_service.py       # Azure AI Search
│       └── storage_service.py      # Azure Blob Storage
├── tests/                   # 테스트
├── Dockerfile               # API 컨테이너
├── requirements.txt         # 의존성
└── pyproject.toml           # 프로젝트 설정
```

## 🔌 API 엔드포인트

### 콘텐츠 API

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/v1/content` | 콘텐츠 목록 조회 |
| GET | `/api/v1/content/{id}` | 콘텐츠 상세 조회 |
| POST | `/api/v1/content` | 콘텐츠 생성 |
| PUT | `/api/v1/content/{id}` | 콘텐츠 수정 |
| DELETE | `/api/v1/content/{id}` | 콘텐츠 삭제 |

### 분석 API

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/analysis/analyze` | GitHub 저장소 분석 |
| GET | `/api/v1/analysis/{id}` | 분석 결과 조회 |

### 검색 API (Azure AI Search)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/v1/search` | 하이브리드 검색 (BM25 + 벡터) |
| GET | `/api/v1/search/facets` | 패싯 조회 (카테고리, 기술 등) |

### AI 어시스턴트 API

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/assistant/chat` | RAG 기반 채팅 (콘텐츠 추천) |
| POST | `/api/v1/assistant/explain/{id}` | 콘텐츠 상세 설명 |
| POST | `/api/v1/assistant/recommend` | 관련 콘텐츠 추천 |

### 인증 API (OTP 기반)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/auth/otp` | OTP 요청 (이메일 전송) |
| POST | `/api/v1/auth/verify` | OTP 검증 + JWT 발급 |
| GET | `/api/v1/auth/me` | 현재 인증된 사용자 정보 |
| POST | `/api/v1/auth/logout` | 로그아웃 (쿠키 제거) |

> 허용된 도메인: `@microsoft.com`, `@github.com` 내부 직원 전용

## 🔧 환경 변수

```env
# 서버
ENV=development
DEBUG=true

# Cosmos DB
COSMOS_CONNECTION_STRING=
COSMOS_DATABASE_NAME=buildflow

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_DEPLOYMENT=gpt-5.2
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
AZURE_DALLE_DEPLOYMENT=gpt-image-1.5

# Azure AI Search
AZURE_SEARCH_ENDPOINT=
AZURE_SEARCH_API_KEY=
AZURE_SEARCH_INDEX_NAME=buildflow-content

# Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING=
AZURE_STORAGE_CDN_HOST=

# JWT
JWT_SECRET=
JWT_ALGORITHM=RS256
JWT_EXPIRY_MINUTES=60

# Azure Communication Services (OTP 이메일 발송)
ACS_CONNECTION_STRING=
ACS_SENDER_ADDRESS=DoNotReply@your-domain.azurecomm.net

# CORS 설정 (쉼표로 구분)
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

## 🧪 테스트

```bash
# 전체 테스트
pytest tests/ -v

# 커버리지 포함
pytest tests/ -v --cov=app --cov-report=term-missing

# 특정 테스트 실행
pytest tests/test_content_api.py -v
```

## 📋 주요 의존성

| 패키지 | 용도 |
|--------|------|
| FastAPI | 웹 프레임워크 |
| uvicorn | ASGI 서버 |
| Pydantic | 데이터 검증 |
| azure-cosmos | Cosmos DB 클라이언트 |
| PyJWT | JWT 인증 |
| httpx | HTTP 클라이언트 |

## 🐳 Docker

### API 빌드

```bash
docker build -t buildflow-api .
docker run -p 8000:8000 --env-file .env buildflow-api
```
