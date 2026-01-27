# NexusSkill

A curated learning platform for Microsoft & Azure content

[![GitHub license](https://img.shields.io/github/license/studydev/buildflow.svg)](https://github.com/studydev/buildflow/blob/develop/LICENSE)
[![Backend CI](https://github.com/studydev/buildflow/actions/workflows/backend-ci.yml/badge.svg?branch=develop)](https://github.com/studydev/buildflow/actions/workflows/backend-ci.yml)
[![Frontend CI](https://github.com/studydev/buildflow/actions/workflows/frontend-ci.yml/badge.svg?branch=develop)](https://github.com/studydev/buildflow/actions/workflows/frontend-ci.yml)
[![Deploy Backend](https://github.com/studydev/buildflow/actions/workflows/deploy-backend.yml/badge.svg?branch=develop)](https://github.com/studydev/buildflow/actions/workflows/deploy-backend.yml)
[![Deploy Frontend](https://github.com/studydev/buildflow/actions/workflows/deploy-frontend.yml/badge.svg?branch=develop)](https://github.com/studydev/buildflow/actions/workflows/deploy-frontend.yml)

## Preview

![NexusSkill Platform Preview](docs/images/platform-preview.png)

*Explore workshops and tutorials with curated learning paths to accelerate your technical skills.*  
[Try the Demo](https://nexus.studydev.com/)

## Overview

NexusSkill automatically curates Microsoft and Azure cloud development learning content by analyzing GitHub repositories, powered by AI-based search and recommendation features.

### Key Features

| Feature | Description |
|---------|-------------|
| **GitHub Repository Analysis** | Automatically extracts README, metadata, and commit activity |
| **AI-Powered Content Enrichment** | Generates summaries, difficulty levels, and learning outcomes using GPT |
| **Multilingual Support** | Automatic Korean ↔ English translation |
| **Asset Auto-Generation** | Automatic thumbnail image generation with DALL-E |
| **Hybrid Search** | Keyword + vector search powered by Azure AI Search |
| **AI Chatbot** | Semantic content search and recommendation assistant |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         NexusSkill                              │
├──────────────────────┬──────────────────────────────────────────┤
│  Frontend            │  Vue 3 + TypeScript + Vite               │
│  (Azure SWA)         │  Pinia state management, Tailwind CSS    │
├──────────────────────┼──────────────────────────────────────────┤
│  Backend API         │  FastAPI + Python 3.9                    │
│  (Container Apps)    │  Cosmos DB, Azure OpenAI                 │
├──────────────────────┼──────────────────────────────────────────┤
│  Analysis Pipeline   │  BackgroundTasks (in-process)            │
│                      │  GitHub analysis, AI metadata extraction │
└──────────────────────┴──────────────────────────────────────────┘
```

## Project Structure

```
buildflow/
├── backend/              # FastAPI backend → backend/README.md
├── frontend/             # Vue 3 frontend
├── infra/                # Azure Bicep IaC → infra/README.md
├── .github/workflows/    # CI/CD workflows
└── docs/                 # Additional documentation
```

## Tech Stack

| Area | Technology |
|------|------------|
| Frontend | Vue 3, TypeScript, Vite, Pinia, Tailwind CSS |
| Backend | FastAPI, Python 3.9, Pydantic v2 |
| Database | Azure Cosmos DB (Serverless) |
| Search | Azure AI Search (Hybrid: BM25 + Vector) |
| AI | Azure OpenAI (GPT, DALL-E, Embeddings) |
| Hosting | Azure Container Apps, Azure Static Web Apps |
| CI/CD | GitHub Actions |
| IaC | Bicep |

## Quick Start

### Local Development

```bash
# Frontend
npm install
npm run dev

# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Documentation

- **Infrastructure Deployment**: [infra/README.md](infra/README.md)
- **Backend Development**: [backend/README.md](backend/README.md)
- **Frontend Development**: [frontend/README.md](frontend/README.md)

## License

MIT License

---

## Implementation History

<details>
<summary>Click to expand</summary>

### Completed Features

| Category | Item | Date | Notes |
|----------|------|------|-------|
| **Infrastructure** | Azure Container Apps deployment | 2026-01-21 | Dev environment |
| **Infrastructure** | Azure Static Web Apps deployment | 2026-01-21 | Frontend hosting |
| **Infrastructure** | Cosmos DB setup | 2026-01-21 | Serverless mode |
| **Infrastructure** | Container Registry (ACR) | 2026-01-21 | Docker image storage |
| **Infrastructure** | Azure AI Search integration | 2026-01-27 | Hybrid search index |
| **CI/CD** | Backend CI (Lint + Test) | 2026-01-21 | Ruff + pytest |
| **CI/CD** | Frontend CI (Lint + Test + Build) | 2026-01-21 | ESLint + Vitest + Vite |
| **CI/CD** | Deploy to Dev pipeline | 2026-01-21 | Auto-deploy on Backend CI success |
| **CI/CD** | Deploy Frontend pipeline | 2026-01-21 | Azure SWA auto-deploy |
| **Backend** | Health Check endpoints | 2026-01-21 | /health, /api/v1/health |
| **Backend** | Content CRUD API | 2026-01-21 | Basic CRUD operations |
| **Backend** | GitHub Analysis Pipeline | 2026-01-21 | Repository metadata extraction |
| **Backend** | OTP Email Authentication | 2026-01-22 | @microsoft.com, @github.com domains |
| **Backend** | Hybrid Search API | 2026-01-27 | BM25 + vector search |
| **Backend** | AI Assistant API | 2026-01-27 | RAG-based chat, content recommendations |
| **Backend** | Image Auto-Generation | 2026-01-27 | DALL-E thumbnail generation |
| **Frontend** | Content Grid UI | 2026-01-21 | ContentGrid component |
| **Frontend** | Language Toggle (EN/KR) | 2026-01-21 | LanguageToggle component |
| **Frontend** | OTP Login UI | 2026-01-22 | Email + OTP input modal |
| **Frontend** | AI Assistant UI | 2026-01-27 | Floating chat, markdown rendering |
| **Frontend** | Advanced Search Filters | 2026-01-27 | Category, difficulty, technology filters |

</details>
