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
uvicorn app.main:app --reload --port 8001

# 또는 Docker로 실행
docker build -t buildflow-api .
docker run -p 8001:8000 buildflow-api
```

### 헬스 체크

```bash
curl http://localhost:8001/health

# 응답:
# {"success": true, "data": {"status": "healthy"}, "meta": {...}}
```

## 📚 API 문서

| 문서 | URL |
|------|-----|
| Swagger UI | http://localhost:8001/docs |
| ReDoc | http://localhost:8001/redoc |
| OpenAPI JSON | http://localhost:8001/openapi.json |

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
│   │   ├── auth.py          # 인증 API
│   │   ├── content.py       # 콘텐츠 CRUD API
│   │   ├── pipelines.py     # 파이프라인 트리거 API
│   │   ├── search.py        # 검색 API
│   │   └── users.py         # 사용자 API
│   ├── core/                # 핵심 유틸리티
│   │   ├── exceptions.py    # 커스텀 예외
│   │   ├── middleware.py    # 미들웨어
│   │   ├── rate_limit.py    # 요청 제한
│   │   ├── retry.py         # 재시도 로직
│   │   └── security.py      # 보안 유틸
│   ├── db/                  # 데이터베이스
│   │   └── cosmos.py        # Cosmos DB 클라이언트
│   ├── models/              # Pydantic 모델
│   │   ├── analysis.py      # 분석 모델
│   │   ├── content.py       # 콘텐츠 모델
│   │   ├── pipeline_run.py  # 파이프라인 실행 모델
│   │   └── user.py          # 사용자 모델
│   ├── pipelines/           # 데이터 파이프라인
│   │   ├── base.py          # 파이프라인 베이스 클래스
│   │   ├── analysis.py      # GitHub 저장소 분석
│   │   ├── enrichment.py    # AI 메타데이터 강화
│   │   ├── localization.py  # 다국어 번역
│   │   ├── asset_generation.py # 이미지 생성
│   │   ├── indexing.py      # 검색 인덱싱
│   │   └── runner.py        # 파이프라인 실행기
│   ├── repositories/        # 데이터 저장소
│   ├── schemas/             # API 스키마
│   └── services/            # 비즈니스 로직
├── tests/                   # 테스트
├── Dockerfile               # API 컨테이너
├── Dockerfile.pipeline      # 파이프라인 컨테이너
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

### 파이프라인 API

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/pipelines/trigger` | 파이프라인 트리거 |
| GET | `/api/v1/pipelines/runs` | 실행 이력 조회 |

### 인증 API

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/auth/otp/request` | OTP 요청 |
| POST | `/api/v1/auth/otp/verify` | OTP 검증 |
| POST | `/api/v1/auth/refresh` | 토큰 갱신 |

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
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# JWT
JWT_SECRET=
JWT_ALGORITHM=RS256
JWT_EXPIRY_MINUTES=60
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
docker run -p 8001:8000 --env-file .env buildflow-api
```

### 파이프라인 빌드

```bash
docker build -f Dockerfile.pipeline -t buildflow-pipeline .
```
