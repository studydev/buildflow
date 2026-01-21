# CI/CD Workflows

BuildFlow GitHub Actions 워크플로우 문서

## 📊 워크플로우 현황

| 워크플로우 | 상태 | 트리거 | 설명 |
|-----------|------|--------|------|
| Backend CI | ✅ 성공 | `push`, `pull_request` | Lint + Test |
| Frontend CI | ✅ 성공 | `push`, `pull_request` | Lint + Test + Build |
| Deploy to Dev | ✅ 성공 | Backend CI 성공 시 | Dev 환경 배포 |
| Deploy Frontend | ✅ 성공 | `push` | Azure SWA 배포 |

## 🔄 워크플로우 구조

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         GitHub Actions CI/CD                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   [main 브랜치 push - backend/** 변경]                                   │
│                    │                                                     │
│                    ▼                                                     │
│   ┌────────────────────────────────┐                                     │
│   │         Backend CI             │                                     │
│   │  ┌──────────┐   ┌──────────┐   │                                     │
│   │  │   Lint   │ → │   Test   │   │                                     │
│   │  │  (Ruff)  │   │ (pytest) │   │                                     │
│   │  └──────────┘   └──────────┘   │                                     │
│   └────────────────────────────────┘                                     │
│                    │                                                     │
│                    │ workflow_run (success)                              │
│                    ▼                                                     │
│   ┌────────────────────────────────────────────────────────────────┐     │
│   │                      Deploy to Dev                              │     │
│   │                                                                 │     │
│   │  ┌──────────┐   ┌─────────────┐   ┌───────────┐   ┌──────────┐ │     │
│   │  │ Check CI │ → │ Deploy Infra│ → │ Build API │ → │  Deploy  │ │     │
│   │  │  Status  │   │   (Bicep)   │   │ (Docker)  │   │   API    │ │     │
│   │  └──────────┘   └─────────────┘   └───────────┘   └──────────┘ │     │
│   │                                          │                      │     │
│   │                                   ┌──────┴────────┐             │     │
│   │                                   │Build Pipeline │             │     │
│   │                                   │   (Docker)    │             │     │
│   │                                   └───────────────┘             │     │
│   └────────────────────────────────────────────────────────────────┘     │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   [main 브랜치 push - frontend/** 변경]                                  │
│                    │                                                     │
│                    ▼                                                     │
│   ┌────────────────────────────────────────────┐                         │
│   │              Frontend CI                    │                         │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │                         │
│   │  │   Lint   │→ │   Test   │→ │  Build   │  │                         │
│   │  │ (ESLint) │  │ (Vitest) │  │  (Vite)  │  │                         │
│   │  └──────────┘  └──────────┘  └──────────┘  │                         │
│   └────────────────────────────────────────────┘                         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## 📁 워크플로우 파일

### backend-ci.yml

Backend 코드 품질 검증 워크플로우

```yaml
트리거: push, pull_request (backend/** 변경 시)
Jobs:
  1. lint: Ruff 린터 실행
  2. test: pytest 테스트 실행 (lint 성공 후)
```

**실행 조건:**
- `backend/**` 경로 변경 시
- `.github/workflows/backend-ci.yml` 변경 시

### frontend-ci.yml

Frontend 코드 품질 및 빌드 검증 워크플로우

```yaml
트리거: push, pull_request (frontend/** 변경 시)
Jobs:
  1. lint: ESLint 실행
  2. test: Vitest 테스트 실행 (lint 성공 후)
  3. build: Vite 프로덕션 빌드 (test 성공 후)
```

**실행 조건:**
- `frontend/**` 경로 변경 시
- `package.json`, `vite.config.ts`, `tsconfig*.json` 변경 시

### deploy-dev.yml

Dev 환경 배포 워크플로우

```yaml
트리거: workflow_run (Backend CI 성공 시), workflow_dispatch (수동)
Jobs:
  1. check-ci: CI 성공 여부 확인
  2. deploy-infrastructure: Bicep으로 Azure 인프라 배포
  3. build-api: API Docker 이미지 빌드 및 ACR 푸시
  4. build-pipeline: Pipeline Docker 이미지 빌드 및 ACR 푸시
  5. deploy-api: Container App 업데이트
  6. validate: 헬스체크로 배포 검증
```

**주요 특징:**
- Backend CI가 성공해야만 자동 트리거
- `workflow_dispatch`로 수동 배포 가능 (긴급 상황)
- 인프라 → 빌드 → 배포 → 검증 순서로 실행

### deploy-frontend.yml

Frontend Azure Static Web Apps 배포 워크플로우

```yaml
트리거: push (main 브랜치)
Jobs:
  1. build_and_deploy: SWA CLI로 빌드 및 배포
```

## ⚙️ 필요한 Secrets

| Secret 이름 | 설명 | 사용처 |
|-------------|------|--------|
| `AZURE_CREDENTIALS` | Azure 서비스 주체 인증 정보 | 모든 Azure 배포 |
| `JWT_SECRET` | JWT 토큰 서명 키 | Backend API |
| `GH_TOKEN` | GitHub API 토큰 | GitHub 저장소 분석 |
| `AZURE_OPENAI_KEY` | Azure OpenAI API 키 | AI 파이프라인 |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI 엔드포인트 | AI 파이프라인 |
| `AZURE_OPENAI_DEPLOYMENT` | Azure OpenAI 배포 이름 | AI 파이프라인 |
| `AZURE_STATIC_WEB_APPS_API_TOKEN_*` | SWA 배포 토큰 | Frontend 배포 |

## 🚨 CI 실패 시 동작

| 상황 | 결과 |
|------|------|
| Backend CI 실패 | Deploy to Dev 트리거되지 않음 (배포 차단) |
| Frontend CI 실패 | PR에 경고 표시, Frontend 배포와 독립적 |
| Deploy to Dev 실패 | validate job에서 헬스체크 실패 알림 |

## 🔧 수동 배포

긴급 상황 시 CI를 스킵하고 수동 배포:

1. GitHub Actions 탭 이동
2. "Deploy to Dev" 워크플로우 선택
3. "Run workflow" 클릭
4. 옵션 선택 후 실행

```
deploy_infra: true/false  - 인프라 배포 여부
deploy_api: true/false    - API 컨테이너 배포 여부
deploy_pipeline: true/false - Pipeline 컨테이너 배포 여부
```
