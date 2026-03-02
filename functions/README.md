# Daily Metadata Refresh – Azure Function

매일 한국 시간(KST) 새벽 2시에 실행되어 GitHub/YouTube 컨텐츠의 메타데이터를 자동 갱신합니다.

## 업데이트 대상

| 소스 | 업데이트 항목 | 대상 저장소 |
|------|-------------|------------|
| **GitHub** | stars, forks, last_commit_date | contents, analysis_requests, AI Search |
| **YouTube** | view_count, like_count, comment_count | youtube_contents, youtube_analysis, AI Search |

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

```bash
cd functions
pip install -r requirements.txt
# local.settings.json에 환경 변수 설정 후
func start
```

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

```bash
# Azure CLI로 배포
func azure functionapp publish <function-app-name>
```

## 아키텍처

```
Timer (매일 UTC 17:00 = KST 02:00)
  │
  ├─ GitHub Updater
  │   ├─ Cosmos DB: contents → stars, forks, last_commit_date
  │   ├─ Cosmos DB: analysis_requests → result.stars, result.forks, result.last_commit_date
  │   └─ AI Search: buildflow-contents → stars, forks, last_commit_date
  │
  └─ YouTube Updater (batch 50개씩)
      ├─ Cosmos DB: youtube_contents → view_count, like_count, comment_count
      ├─ Cosmos DB: youtube_analysis → result.view_count, result.like_count, result.comment_count
      └─ AI Search: buildflow-youtube → view_count, like_count, comment_count
```
