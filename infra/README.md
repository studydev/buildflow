# Infrastructure as Code

BuildFlow Azure 인프라 Bicep 템플릿

## 📁 파일 구조

```
infra/
├── main.bicep              # 메인 Bicep 템플릿
├── main.json               # ARM 템플릿 (Bicep 컴파일 결과)
├── main.parameters.json    # 기본 파라미터
├── parameters.dev.json     # Dev 환경 파라미터
├── parameters.prod.json    # Prod 환경 파라미터
└── modules/                # Bicep 모듈
    ├── container-apps-jobs.bicep  # Container Apps Jobs
    ├── monitoring.bicep           # Application Insights
    ├── search.bicep               # Azure AI Search
    ├── servicebus.bicep           # Service Bus
    ├── static-web-app.bicep       # Static Web Apps
    └── storage.bicep              # Blob Storage
```

## 🏗️ 배포되는 Azure 리소스

### Dev 환경 (현재 배포됨)

| 리소스 | 타입 | 상태 | 설명 |
|--------|------|------|------|
| Container Apps Environment | `Microsoft.App/managedEnvironments` | ✅ 배포됨 | 컨테이너 호스팅 환경 |
| Container App (API) | `Microsoft.App/containerApps` | ✅ 배포됨 | FastAPI 백엔드 |
| Container Registry | `Microsoft.ContainerRegistry/registries` | ✅ 배포됨 | Docker 이미지 저장소 |
| Cosmos DB Account | `Microsoft.DocumentDB/databaseAccounts` | ✅ 배포됨 | NoSQL 데이터베이스 |
| Static Web App | `Microsoft.Web/staticSites` | ✅ 배포됨 | Vue 프론트엔드 |
| Application Insights | `Microsoft.Insights/components` | ✅ 배포됨 | 모니터링 |
| Log Analytics Workspace | `Microsoft.OperationalInsights/workspaces` | ✅ 배포됨 | 로그 저장 |

### 예정된 리소스

| 리소스 | 타입 | 상태 | 설명 |
|--------|------|------|------|
| Azure AI Search | `Microsoft.Search/searchServices` | ⏳ 예정 | 하이브리드 검색 |
| Service Bus | `Microsoft.ServiceBus/namespaces` | ⏳ 예정 | 파이프라인 메시지 큐 |
| Storage Account | `Microsoft.Storage/storageAccounts` | ⏳ 예정 | 자산 저장소 |
| Key Vault | `Microsoft.KeyVault/vaults` | ⏳ 예정 | 시크릿 관리 |
| Container Apps Jobs | `Microsoft.App/jobs` | ⏳ 예정 | 파이프라인 실행 |

## 🚀 배포 방법

### Azure CLI로 배포

```bash
# 1. Azure 로그인
az login

# 2. 구독 설정
az account set --subscription "<subscription-id>"

# 3. 리소스 그룹 생성
az group create \
  --name rg-buildflow-dev \
  --location koreacentral

# 4. Bicep 배포
az deployment group create \
  --resource-group rg-buildflow-dev \
  --template-file main.bicep \
  --parameters parameters.dev.json \
  --parameters jwtSecret="<your-jwt-secret>" \
               githubToken="<your-github-token>" \
               azureOpenAiKey="<your-openai-key>" \
               azureOpenAiEndpoint="<your-openai-endpoint>" \
               azureOpenAiDeployment="gpt-4o"
```

### GitHub Actions로 배포 (권장)

`deploy-dev.yml` 워크플로우가 자동으로 인프라를 배포합니다.
자세한 내용은 [.github/workflows/README.md](../.github/workflows/README.md) 참조.

## ⚙️ 파라미터

### 필수 파라미터

| 파라미터 | 설명 | 예시 |
|----------|------|------|
| `environment` | 환경 이름 | `dev`, `prod` |
| `projectName` | 프로젝트 이름 | `buildflow` |
| `jwtSecret` | JWT 서명 키 | (시크릿) |
| `githubToken` | GitHub API 토큰 | (시크릿) |

### 선택 파라미터

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `location` | `koreacentral` | Azure 리전 |
| `enableMonitoring` | `true` | Application Insights 활성화 |
| `enablePipelines` | `true` | Container Apps Jobs 활성화 |
| `enableFrontend` | `true` | Static Web App 활성화 |

## 🌍 환경별 설정

### Dev 환경 (`parameters.dev.json`)

- Container Apps: Consumption 플랜
- Cosmos DB: Serverless
- 파이프라인: 활성화
- 모니터링: 활성화

### Prod 환경 (`parameters.prod.json`) - 미배포

- Container Apps: Dedicated 플랜 (예정)
- Cosmos DB: Provisioned throughput (예정)
- 파이프라인: 비활성화 (Read-only)
- 모니터링: 활성화

## 🔧 로컬에서 Bicep 작업

### Bicep CLI 설치

```bash
# Azure CLI에 포함됨
az bicep install
az bicep upgrade
```

### 템플릿 검증

```bash
az bicep build --file main.bicep
az deployment group validate \
  --resource-group rg-buildflow-dev \
  --template-file main.bicep \
  --parameters parameters.dev.json
```

### What-If 미리보기

```bash
az deployment group what-if \
  --resource-group rg-buildflow-dev \
  --template-file main.bicep \
  --parameters parameters.dev.json
```
