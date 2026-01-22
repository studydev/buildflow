# Research: OTP 기반 이메일 인증 시스템

**Feature**: 001-otp-email-auth  
**Date**: 2026-01-22  
**Status**: Complete

## R-1: Azure Communication Services Python SDK 이메일 발송

### Decision
Azure Communication Services Python SDK (`azure-communication-email`) 사용

### Rationale
- 공식 Microsoft SDK로 장기 지원 보장
- 비동기 발송 지원으로 API 응답 지연 없음
- 기존 email_service.py에 AzureCommunicationEmailService 클래스 이미 존재

### Implementation Pattern

```python
from azure.communication.email import EmailClient

client = EmailClient.from_connection_string(connection_string)

message = {
    "senderAddress": sender_address,
    "recipients": {
        "to": [{"address": email}]
    },
    "content": {
        "subject": "BuildFlow - 인증 코드",
        "html": f"<p>인증 코드: <strong>{otp}</strong></p>"
    }
}

# 비동기 발송 (폴링 불필요 - fire and forget)
poller = client.begin_send(message)
# 또는 동기 대기: result = poller.result()
```

### Alternatives Considered
- SendGrid: 외부 서비스, Azure 통합 복잡
- SMTP 직접 발송: Azure에서 포트 25 차단됨

---

## R-2: FastAPI HttpOnly 쿠키 설정

### Decision
JSONResponse에 Set-Cookie 헤더 직접 설정

### Rationale
- FastAPI Response 객체의 set_cookie 메서드 사용
- CORS 설정에서 credentials: true 필수
- SameSite=Lax로 CSRF 방지 + 일반적인 링크 탐색 허용

### Implementation Pattern

```python
from fastapi.responses import JSONResponse

@router.post("/verify")
async def verify_otp(request: Request, body: VerifyRequest):
    # ... OTP 검증 ...
    
    response = JSONResponse(content={"success": True, "data": {...}})
    
    response.set_cookie(
        key="access_token",
        value=jwt_token,
        httponly=True,
        secure=True,  # HTTPS only (production)
        samesite="lax",
        max_age=7 * 24 * 60 * 60,  # 7 days
        path="/",
    )
    
    return response
```

### CORS Configuration

```python
# main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend.com"],
    allow_credentials=True,  # Required for cookies
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Frontend Fetch Configuration

```typescript
// api.ts
const response = await fetch(url, {
  method: 'POST',
  credentials: 'include',  // Required to send cookies
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data),
})
```

### Alternatives Considered
- localStorage JWT: XSS 취약점
- sessionStorage: 탭 닫으면 삭제됨

---

## R-3: Cosmos DB TTL 기반 OTP 만료 처리

### Decision
Cosmos DB 컨테이너 TTL + 애플리케이션 레벨 만료 체크 병행

### Rationale
- TTL은 백그라운드에서 자동 삭제 (비용 효율적)
- 삭제 타이밍이 정확하지 않을 수 있어 애플리케이션에서도 expires_at 체크
- 이메일당 하나의 레코드만 유지 (upsert 패턴)

### Implementation Pattern

```python
# Container 생성 시 TTL 활성화
container = database.create_container_if_not_exists(
    id="login_attempts",
    partition_key=PartitionKey(path="/email"),
    default_ttl=300  # 5분 (안전 마진)
)

# Document에 ttl 필드 포함
document = {
    "id": str(uuid4()),
    "email": email.lower(),
    "otp_code": hashed_otp,
    "created_at": now.isoformat(),
    "expires_at": (now + timedelta(minutes=3)).isoformat(),
    "ttl": 300  # 개별 문서 TTL
}

# Upsert로 기존 OTP 덮어쓰기
container.upsert_item(document)
```

### Verification Pattern

```python
def verify_otp(email: str, code: str) -> bool:
    # 1. 문서 조회
    items = list(container.query_items(
        query="SELECT * FROM c WHERE c.email = @email",
        parameters=[{"name": "@email", "value": email.lower()}]
    ))
    
    if not items:
        return False, "No OTP found"
    
    entry = items[0]
    
    # 2. 애플리케이션 레벨 만료 체크
    if datetime.fromisoformat(entry["expires_at"]) < datetime.now(timezone.utc):
        container.delete_item(entry["id"], partition_key=email)
        return False, "OTP has expired"
    
    # 3. 코드 비교
    if not verify_hash(entry["otp_code"], code):
        return False, "Invalid OTP"
    
    # 4. 성공 시 삭제
    container.delete_item(entry["id"], partition_key=email)
    return True, "Success"
```

---

## R-4: Vue Router 네비게이션 가드에서 메시지 표시

### Decision
라우터 쿼리 파라미터 + App.vue에서 토스트 표시

### Rationale
- 기존 패턴 (query: { login: 'required' }) 유지
- 토스트 라이브러리 또는 커스텀 컴포넌트 사용
- 로그인 모달 자동 열기 + 안내 메시지 표시

### Implementation Pattern

```typescript
// router/index.ts
router.beforeEach(async (to, from, next) => {
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    sessionStorage.setItem('redirectAfterLogin', to.fullPath)
    return next({ 
      name: 'Home', 
      query: { 
        login: 'required',
        message: '이 기능을 사용하려면 로그인이 필요합니다'
      }
    })
  }
  next()
})
```

```vue
<!-- App.vue -->
<script setup>
import { watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

watch(() => route.query, (query) => {
  if (query.login === 'required') {
    // 토스트 표시
    showToast(query.message || '로그인이 필요합니다')
    // 로그인 모달 열기
    authModalsRef.value?.openLogin()
  }
}, { immediate: true })
</script>
```

---

## R-5: JWT RS256 키 관리

### Decision
기존 키 파일 방식 유지, 키 로테이션은 향후 과제

### Rationale
- 현재 keys/private.pem, keys/public.pem 사용 중
- 단일 키 쌍으로 MVP 충분
- 키 로테이션은 별도 피처로 분리

### Current Implementation

```python
# config.py
jwt_private_key_path: str = "keys/private.pem"
jwt_public_key_path: str = "keys/public.pem"

# security.py
def get_private_key():
    with open(settings.jwt_private_key_path, "r") as f:
        return f.read()
```

### Future Consideration
- Azure Key Vault 저장
- kid (Key ID) 헤더로 다중 키 지원
- 자동 키 로테이션 스케줄

---

## Summary

| Research Item | Decision | Confidence |
|---------------|----------|------------|
| R-1: ACS SDK | azure-communication-email | High |
| R-2: Cookie Auth | HttpOnly + SameSite=Lax | High |
| R-3: OTP Storage | Cosmos TTL + App-level check | High |
| R-4: Login Message | Query param + Toast | High |
| R-5: JWT Keys | Existing file-based | Medium |

모든 주요 기술 결정이 완료되었습니다. Phase 1 설계로 진행할 수 있습니다.
