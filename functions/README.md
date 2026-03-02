# Daily Metadata Refresh – Azure Function

매일 한국 시간(KST) 새벽 2시에 실행되어 GitHub/YouTube 컨텐츠의 메타데이터를 자동 갱신합니다.

## 업데이트 대상

| 소스 | 업데이트 항목 | 대상 저장소 |
|------|-------------|------------|
| **GitHub** | stars, forks, last_commit_date | contents, analysis_requests, AI Search (`buildflow-content`) |
| **YouTube** | view_count, like_count, comment_count | youtube_contents, youtube_analysis, AI Search (`buildflow-youtube`) |

> **참고**: AI Search 인덱스에는 스키마에 존재하는 필드만 업데이트합니다.
> - `buildflow-content`: `stars`, `last_commit_date` (forks 필드 없음)
> - `buildflow-youtube`: `view_count`, `like_count` (comment_count 필드 없음)

## API Rate Limit 안전 장치

| API | 제한 | 안전 장치 |
|-----|------|----------|
| GitHub REST API | 5,000/hour (PAT) | 요청 간 1.5초 딜레이, Remaining < 100이면 60초 대기 |
| YouTube Data API v3 | 10,000 units/day | 50개씩 배치 호출 (1 unit/batch), quota 초과 시 즉시 중단 |

## 환경 변수

| 변수 | 설명 | 필수 |
|------|------|------|
| `COSMOS_CONNECTION_STRING` | Cosmos DB 연결 문자열 | ✅ |
| `COSMOS_DATABASE_NAME` | 데이터베이스 이름 (기본: `buildflow`) | |
| `GITHUB_TOKEN` | GitHub PAT (5,000 req/hour) | ✅ |
| `YOUTUBE_API_KEY` | YouTube Data API v3 키 | ✅ |
| `AZURE_SEARCH_ENDPOINT` | AI Search 엔드포인트 | |
| `AZURE_SEARCH_API_KEY` | AI Search 관리 키 | |

## 로컬 실행

### Azure Functions Core Tools로 실행
```bash
cd functions
pip install -r requirements.txt
# local.settings.json에 환경 변수 설정 후
func start
```

### 로컬 테스트 스크립트
```bash
cd functions

# Dry run (읽기만, 업데이트 안함)
python3 test_local.py github --dry    # GitHub만
python3 test_local.py youtube --dry   # YouTube만
python3 test_local.py both --dry      # 전체

# 실제 업데이트 실행
python3 test_local.py both
```

> `test_local.py`는 `backend/.env.local`에서 크레덴셜을 자동 로드합니다.
> `.env.local`이 없으면 Azure CLI(`az`)에서 가져옵니다.

## 수동 실행 (HTTP Trigger)

```bash
# 전체 실행
curl -X POST "https://<function-app>.azurewebsites.net/api/refresh-metadata?code=<function-key>"

# GitHub만
curl -X POST "https://<function-app>.azurewebsites.net/api/refresh-metadata?code=<function-key>&source=github"

# YouTube만
curl -X POST "https://<function-app>.azurewebsites.net/api/refresh-metadata?code=<function-key>&source=youtube"
```

## 배포

### GitHub Actions (자동)
`develop` 브랜치에 push하면 `.github/workflows/deploy-backend.yml`의 `deploy-functions` job이 자동 실행됩니다.

```
deploy-infrastructure → deploy-functions → validate
```

### Azure CLI (수동)
```bash
func azure functionapp publish <function-app-name>
```

## 인프라

| 리소스 | 설명 |
|--------|------|
| Storage Account (`stfunc*`) | AzureWebJobsStorage |
| App Service Plan (Y1/Dynamic) | Consumption 과금 |
| Function App (Python 3.11, Linux) | 실행 환경 |
| Diagnostic Settings | Log Analytics 연동 |

Bicep 모듈: `infra/modules/function-app.bicep`

> 환경변수는 Container App과 동일한 GitHub Secrets에서 Bicep을 통해 주입됩니다.

## 아키텍처

```
Timer (매일 UTC 17:00 = KST 02:00)
  │
  ├─ GitHub Updater (119 repos, ~4분 소요)
  │   ├─ Cosmos DB: contents → stars, forks, last_commit_date
  │   ├─ Cosmos DB: analysis_requests → result.stars, result.forks, result.last_commit_date
  │   └─ AI Search: buildflow-content → stars, last_commit_date
  │
  └─ YouTube Updater (batch 50개씩, ~1초 소요)
      ├─ Cosmos DB: youtube_contents → view_count, like_count, comment_count
      ├─ Cosmos DB: youtube_analysis → result.view_count, result.like_count, result.comment_count
      └─ AI Search: buildflow-youtube → view_count, like_count
```

## 테스트 결과 (2026-03-02)

| 소스 | 전체 | 업데이트 | 실패 | 스킵 |
|------|------|---------|------|------|
| GitHub | 119 | 1 | 0 | 118 |
| YouTube | 8 | 3 | 0 | 5 |
