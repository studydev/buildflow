# Quickstart: OTP 이메일 인증

**Feature**: 001-otp-email-auth  
**Date**: 2026-01-22

## 개요

이 가이드는 OTP 기반 이메일 인증 기능을 로컬에서 테스트하고 개발하는 방법을 설명합니다.

---

## 사전 요구사항

### 1. Azure Communication Services 설정

```bash
# ACS 리소스 생성 (Azure CLI)
az communication create \
  --name buildflow-acs \
  --resource-group buildflow-rg \
  --location global \
  --data-location unitedstates

# Connection String 가져오기
az communication list-key \
  --name buildflow-acs \
  --resource-group buildflow-rg \
  --query primaryConnectionString -o tsv
```

### 2. 환경 변수 설정

`.env.local` 파일에 추가:

```bash
# Azure Communication Services
ACS_CONNECTION_STRING=endpoint=https://buildflow-acs.communication.azure.com/;accesskey=<key>
ACS_SENDER_ADDRESS=DoNotReply@<domain>.azurecomm.net

# Cosmos DB (기존)
COSMOS_CONNECTION_STRING=<your-connection-string>
COSMOS_DATABASE_NAME=buildflow

# JWT Keys (기존)
JWT_PRIVATE_KEY_PATH=keys/private.pem
JWT_PUBLIC_KEY_PATH=keys/public.pem
```

### 3. Cosmos DB 컨테이너 생성

```bash
cd backend

# 스크립트로 컨테이너 생성
python scripts/setup_auth_containers.py

# 또는 Azure CLI
az cosmosdb sql container create \
  --account-name <account> \
  --database-name buildflow \
  --name login_attempts \
  --partition-key-path /email \
  --default-ttl 300

az cosmosdb sql container create \
  --account-name <account> \
  --database-name buildflow \
  --name login_history \
  --partition-key-path /email
```

---

## 로컬 개발 실행

### Backend

```bash
cd backend

# 의존성 설치
pip install -r requirements.txt

# 서버 실행
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# 의존성 설치
npm install

# 개발 서버 실행
npm run dev
```

---

## API 테스트

### 1. OTP 요청

```bash
curl -X POST http://localhost:8000/api/v1/auth/otp \
  -H "Content-Type: application/json" \
  -d '{"email": "test@microsoft.com"}'
```

**예상 응답:**
```json
{
  "success": true,
  "data": {
    "message": "OTP sent successfully",
    "email": "t***@microsoft.com",
    "expires_in_seconds": 180
  }
}
```

### 2. 잘못된 도메인 테스트

```bash
curl -X POST http://localhost:8000/api/v1/auth/otp \
  -H "Content-Type: application/json" \
  -d '{"email": "test@gmail.com"}'
```

**예상 응답 (400):**
```json
{
  "success": false,
  "error": {
    "code": "DOMAIN_NOT_ALLOWED",
    "message": "내부 직원 전용 로그인 서비스입니다."
  }
}
```

### 3. OTP 검증

```bash
curl -X POST http://localhost:8000/api/v1/auth/verify \
  -H "Content-Type: application/json" \
  -c cookies.txt \
  -d '{"email": "test@microsoft.com", "code": "123456"}'
```

**예상 응답 (쿠키 설정됨):**
```json
{
  "success": true,
  "data": {
    "message": "Authentication successful",
    "user": {
      "id": "...",
      "email": "test@microsoft.com",
      "role": "contributor"
    }
  }
}
```

### 4. 인증된 요청

```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
  -b cookies.txt
```

### 5. 로그아웃

```bash
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -b cookies.txt \
  -c cookies.txt
```

---

## 개발 모드 (이메일 없이 테스트)

ACS 설정 없이 테스트하려면:

1. `backend/app/config.py`에서 `debug=True` 확인
2. OTP 요청 시 로그에서 코드 확인:
   ```
   INFO: OTP for test@microsoft.com: 123456 (dev only)
   ```

**주의**: Production에서는 반드시 `debug=False`로 설정하세요.

---

## 테스트 실행

### Backend 단위 테스트

```bash
cd backend
pytest tests/test_auth_api.py -v
pytest tests/test_domain_validation.py -v
```

### Frontend 테스트

```bash
cd frontend
npm run test
```

---

## 문제 해결

### 쿠키가 전송되지 않음

1. Frontend의 fetch 요청에 `credentials: 'include'` 확인
2. CORS 설정에 `allow_credentials=True` 확인
3. 동일 도메인 또는 HTTPS 환경에서 테스트

### OTP 이메일이 발송되지 않음

1. ACS_CONNECTION_STRING 확인
2. ACS_SENDER_ADDRESS가 유효한 발신자 주소인지 확인
3. Azure Portal에서 Email Domain 설정 확인

### 도메인 검증 우회 (개발용)

테스트 목적으로 도메인 검증을 우회하려면:

```python
# auth_service.py (개발 환경에서만!)
ALLOWED_DOMAINS = ["microsoft.com", "github.com", "test.local"]
```

---

## 다음 단계

1. [ ] ACS 리소스 생성 및 설정
2. [ ] Cosmos DB 컨테이너 생성
3. [ ] 환경 변수 설정
4. [ ] 로컬 테스트 완료
5. [ ] dev 환경 배포
