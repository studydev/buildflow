# BuildFlow

Microsoft & Azure 콘텐츠 학습 플랫폼

[![Deploy to Dev](https://github.com/buildflow/buildflow/actions/workflows/deploy-dev.yml/badge.svg)](https://github.com/buildflow/buildflow/actions/workflows/deploy-dev.yml)
[![Deploy to Prod](https://github.com/buildflow/buildflow/actions/workflows/deploy-prod.yml/badge.svg)](https://github.com/buildflow/buildflow/actions/workflows/deploy-prod.yml)

## 🎯 프로젝트 개요

BuildFlow는 GitHub 저장소를 분석하여 Microsoft 및 Azure 및 클라우드 개발 학습 콘텐츠를 자동으로 큐레이션하고, AI 기반 검색 및 추천 기능을 제공하는 플랫폼입니다.

### 주요 기능

- 🔍 **GitHub 저장소 분석** - README, 메타데이터, 커밋 활동 자동 추출
- 🤖 **AI 기반 콘텐츠 강화** - GPT-4o를 활용한 요약, 난이도, 학습 성과 생성
- 🌐 **다국어 지원** - 한국어 자동 번역 (Localization Pipeline)
- 🖼️ **자산 자동 생성** - 썸네일, OG 이미지 자동 생성
- 🔎 **하이브리드 검색** - Azure AI Search 기반 키워드 + 벡터 검색
- 💬 **AI 어시스턴트** - RAG 기반 콘텐츠 검색 및 추천 챗봇

## 🏗️ 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              BuildFlow                                   │
├─────────────────────────────────────────────────────────────────────────┤
│  Frontend (Vue 3 + TypeScript)                                          │
│  ├── ContentGrid - 콘텐츠 카드 그리드                                    │
│  ├── LanguageToggle - EN/KR 언어 전환                                   │
│  └── Assistant - AI 채팅 인터페이스                                      │
├─────────────────────────────────────────────────────────────────────────┤
│  Backend API (FastAPI + Python)                                          │
│  ├── /api/v1/content - 콘텐츠 CRUD                                       │
│  ├── /api/v1/search - 하이브리드 검색                                    │
│  ├── /api/v1/assistant - AI 채팅                                         │
│  ├── /api/v1/pipelines - 파이프라인 트리거                               │
│  └── /api/v1/admin - 관리자 (Dev→Prod 프로모션)                          │
├─────────────────────────────────────────────────────────────────────────┤
│  Data Pipelines (Container Apps Jobs)                                    │
│  ├── AnalysisPipeline - GitHub 저장소 분석                               │
│  ├── EnrichmentPipeline - AI 메타데이터 강화                             │
│  ├── LocalizationPipeline - 한국어 번역                                  │
│  ├── AssetGenerationPipeline - 이미지 생성                               │
│  └── IndexingPipeline - 검색 인덱스 업데이트                             │
├─────────────────────────────────────────────────────────────────────────┤
│  Azure Services                                                          │
│  ├── Cosmos DB - 콘텐츠, 사용자, 파이프라인 데이터                        │
│  ├── Azure AI Search - 하이브리드 검색 인덱스                            │
│  ├── Azure OpenAI - GPT-4o, Embeddings                                   │
│  ├── Service Bus - 파이프라인 메시지 큐 (Dev Only)                       │
│  ├── Blob Storage - 생성된 자산 저장                                     │
│  └── Container Apps - API 및 파이프라인 잡 호스팅                        │
└─────────────────────────────────────────────────────────────────────────┘
```

## 🌍 환경 분리

| 환경 | 용도 | 파이프라인 | 설명 |
|------|------|-----------|------|
| **Dev** | 개발/테스트 | ✅ 활성화 | 전체 파이프라인 실행, 콘텐츠 처리 |
| **Prod** | 운영 | ❌ 비활성화 | Read-only API, Dev에서 프로모션된 콘텐츠만 |

## 📁 프로젝트 구조

```
buildflow/
├── backend/                    # FastAPI 백엔드
│   ├── app/
│   │   ├── api/v1/            # API 엔드포인트
│   │   ├── models/            # Pydantic 모델
│   │   ├── pipelines/         # 데이터 파이프라인
│   │   ├── repositories/      # Cosmos DB 저장소
│   │   └── services/          # 비즈니스 로직
│   ├── Dockerfile             # API 컨테이너
│   └── Dockerfile.pipeline    # 파이프라인 컨테이너
├── frontend/                  # Vue 3 프론트엔드
│   ├── components/            # Vue 컴포넌트
│   ├── stores/                # Pinia 스토어
│   └── views/                 # 페이지 뷰
├── infra/                     # Azure Bicep IaC
│   ├── main.bicep             # 메인 템플릿
│   ├── parameters.dev.json    # Dev 환경 파라미터
│   ├── parameters.prod.json   # Prod 환경 파라미터
│   └── modules/               # Bicep 모듈
└── .github/workflows/         # CI/CD
    ├── deploy-dev.yml         # Backend Dev 배포 (develop 브랜치)
    ├── deploy-prod.yml        # Backend Prod 배포 (main 브랜치)
    └── deploy-frontend.yml    # Frontend SWA 배포
```

## 🚀 시작하기

### 사전 요구사항

- Node.js 18+
- Python 3.11+
- Docker & Docker Compose
- Azure CLI
- Azure 구독

### 로컬 개발

```bash
# 프론트엔드
npm install
npm run dev

# 백엔드
cd backend
pip install -e .
uvicorn app.main:app --reload --port 8001

# Docker Compose (전체 스택)
docker-compose -f backend/docker-compose.yml up
```

### Azure 배포

```bash
# 리소스 그룹 생성
az group create --name rg-buildflow-dev --location koreacentral

# Bicep 배포
az deployment group create \
  --resource-group rg-buildflow-dev \
  --template-file infra/main.bicep \
  --parameters infra/parameters.dev.json
```

## 📋 완료된 마일스톤

| # | 마일스톤 | 설명 | 상태 |
|---|---------|------|------|
| 1 | Pipeline Infrastructure | Service Bus, Container Apps Jobs 인프라 | ✅ |
| 2 | Analysis Pipeline | GitHub 저장소 분석 파이프라인 | ✅ |
| 3 | Enrichment Pipeline | AI 기반 메타데이터 강화 | ✅ |
| 4 | Search & Indexing | Azure AI Search 통합 | ✅ |
| 5 | Localization Pipeline | 한국어 번역 파이프라인 | ✅ |
| 6 | Asset Generation | 썸네일/OG 이미지 생성 | ✅ |
| 7 | AI Assistant | RAG 기반 채팅 어시스턴트 | ✅ |
| 8 | Production Deployment | CI/CD, 모니터링, Dev→Prod 프로모션 | ✅ |

## 🔧 환경 변수

```env
# Cosmos DB
COSMOS_CONNECTION_STRING=
COSMOS_DATABASE_NAME=buildflow

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# Azure AI Search
AZURE_SEARCH_ENDPOINT=
AZURE_SEARCH_API_KEY=

# Service Bus (Dev Only)
SERVICEBUS_CONNECTION_STRING=

# Blob Storage
AZURE_STORAGE_CONNECTION_STRING=

# JWT
JWT_SECRET=
```

## 📚 API 문서

로컬 실행 시: http://localhost:8001/docs

### 주요 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/v1/content` | 콘텐츠 목록 조회 |
| GET | `/api/v1/search` | 하이브리드 검색 |
| POST | `/api/v1/assistant/chat` | AI 어시스턴트 채팅 |
| POST | `/api/v1/pipelines/trigger` | 파이프라인 트리거 |
| POST | `/api/v1/admin/promotion/promote` | Dev→Prod 프로모션 |

## 🛠️ 기술 스택

### Frontend
- Vue 3 + TypeScript
- Vite
- Pinia (상태 관리)
- Tailwind CSS

### Backend
- FastAPI
- Python 3.11+
- Pydantic v2

### Azure Services
- Azure Container Apps
- Azure Cosmos DB (Serverless)
- Azure AI Search
- Azure OpenAI Service
- Azure Service Bus
- Azure Blob Storage
- Azure Key Vault
- Application Insights

### Infrastructure
- Bicep (IaC)
- GitHub Actions (CI/CD)

## 📄 라이선스

MIT License
