# Data Model: OTP 기반 이메일 인증

**Feature**: 001-otp-email-auth  
**Date**: 2026-01-22  
**Storage**: Azure Cosmos DB

## Overview

인증 시스템에서 사용하는 데이터 엔티티 정의입니다.

---

## Entities

### 1. LoginAttempt

OTP 인증 대기 상태를 저장합니다. 이메일당 하나의 레코드만 유지됩니다.

**Container**: `login_attempts`  
**Partition Key**: `/email`  
**TTL**: Enabled (default: 300 seconds)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string (UUID) | ✓ | 고유 식별자 |
| email | string | ✓ | 이메일 (lowercase, partition key) |
| otp_code_hash | string | ✓ | SHA256 해시된 OTP 코드 |
| created_at | datetime (ISO8601) | ✓ | OTP 발급 시간 |
| expires_at | datetime (ISO8601) | ✓ | OTP 만료 시간 (created_at + 3분) |
| ttl | integer | ✓ | Cosmos DB TTL (초 단위) |

**Example Document:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@microsoft.com",
  "otp_code_hash": "5e884898da28047d9141...",
  "created_at": "2026-01-22T10:00:00Z",
  "expires_at": "2026-01-22T10:03:00Z",
  "ttl": 300
}
```

**Operations:**
- `upsert`: OTP 요청 시 기존 레코드 덮어쓰기
- `read`: OTP 검증 시 조회
- `delete`: 검증 성공 후 삭제 (또는 TTL 자동 삭제)

---

### 2. LoginHistory

로그인 성공 이력을 저장합니다. 감사(audit) 및 사용자 활동 추적용입니다.

**Container**: `login_history`  
**Partition Key**: `/email`  
**TTL**: None (영구 보관, 정책에 따라 조정 가능)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string (UUID) | ✓ | 고유 식별자 |
| email | string | ✓ | 이메일 (lowercase, partition key) |
| user_id | string (UUID) | ✓ | 사용자 ID |
| logged_in_at | datetime (ISO8601) | ✓ | 로그인 성공 시간 |
| user_agent | string | - | 브라우저 User-Agent |
| ip_address | string | - | 클라이언트 IP 주소 |

**Example Document:**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "email": "user@microsoft.com",
  "user_id": "770e8400-e29b-41d4-a716-446655440002",
  "logged_in_at": "2026-01-22T10:01:30Z",
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
  "ip_address": "203.0.113.42"
}
```

**Operations:**
- `create`: 로그인 성공 시 새 레코드 생성
- `query`: 사용자별 로그인 이력 조회

---

### 3. User (기존 - 수정 없음)

기존 User 엔티티는 변경 없이 유지됩니다. 참고용으로 포함합니다.

**Container**: `users`  
**Partition Key**: `/id`

| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | 고유 식별자 |
| email | string | 이메일 (unique) |
| display_name | string | 표시 이름 |
| role | enum | user, contributor, admin |
| is_active | boolean | 활성화 상태 |
| created_at | datetime | 생성 시간 |
| last_login_at | datetime | 마지막 로그인 시간 |

---

## Relationships

```
User (1) ──────────────── (N) LoginHistory
  │                              │
  │ email                        │ email
  │                              │
  └──────────────────────────────┘

LoginAttempt (1:1 per email) ──── 임시 저장, User와 직접 연결 없음
```

---

## Validation Rules

### Email
- RFC 5322 형식 준수
- 도메인 검증: `@microsoft.com` 또는 `@github.com`만 허용
- 저장 시 lowercase 변환

### OTP Code
- 6자리 숫자 (000000 ~ 999999)
- 저장 시 SHA256 해시
- 비교 시 constant-time comparison

### Timestamps
- UTC 타임존 필수 (ISO8601 형식)
- `created_at`: 생성 시 서버에서 설정
- `expires_at`: `created_at + timedelta(minutes=3)`

---

## Indexes

### login_attempts
- Partition Key: `/email` (자동 인덱싱)
- 추가 인덱스 불필요 (이메일로만 조회)

### login_history
- Partition Key: `/email` (자동 인덱싱)
- Composite Index (optional): `/email`, `/logged_in_at DESC` (최근 로그인 조회)

---

## State Transitions

### LoginAttempt Lifecycle

```
┌─────────────┐     OTP Request     ┌─────────────┐
│  (없음)      │ ──────────────────► │  Created    │
└─────────────┘                      └──────┬──────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    │                       │                       │
                    ▼                       ▼                       ▼
            ┌───────────────┐       ┌───────────────┐       ┌───────────────┐
            │ Verified      │       │ Expired       │       │ New Request   │
            │ (삭제됨)       │       │ (TTL 삭제)     │       │ (덮어씀)       │
            └───────────────┘       └───────────────┘       └───────────────┘
```

---

## Migration Notes

### New Containers to Create

```bash
# 1. login_attempts (with TTL)
az cosmosdb sql container create \
  --account-name <account> \
  --database-name buildflow \
  --name login_attempts \
  --partition-key-path /email \
  --default-ttl 300

# 2. login_history
az cosmosdb sql container create \
  --account-name <account> \
  --database-name buildflow \
  --name login_history \
  --partition-key-path /email
```

### Backwards Compatibility
- 기존 users 컨테이너 변경 없음
- 새 컨테이너 추가만 필요
- 데이터 마이그레이션 불필요
