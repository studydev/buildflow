# Feature Specification: OTP 기반 이메일 인증 시스템

**Feature Branch**: `001-otp-email-auth`  
**Created**: 2026-01-22  
**Status**: Draft  
**Input**: Azure Communication Services를 통한 6자리 OTP 이메일 인증, 내부 직원 전용 로그인, 역할 기반 접근 제어

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 내부 직원 OTP 로그인 (Priority: P1)

내부 직원(@microsoft.com 또는 @github.com 이메일)이 로그인 버튼을 클릭하고 이메일을 입력하면, Azure Communication Services를 통해 6자리 OTP 코드가 이메일로 발송됩니다. 직원은 3분 이내에 OTP 코드를 입력하여 인증을 완료하고 로그인합니다.

**Why this priority**: 핵심 인증 기능으로, 이 기능 없이는 Contributor 기능에 접근할 수 없음

**Independent Test**: 내부 도메인 이메일로 로그인 시도 → OTP 이메일 수신 → 코드 입력 → 로그인 성공 확인

**Acceptance Scenarios**:

1. **Given** 사용자가 로그인 페이지에 있고, **When** @microsoft.com 이메일을 입력하고 OTP 요청을 클릭하면, **Then** 해당 이메일로 6자리 OTP 코드가 발송된다
2. **Given** OTP 코드가 발송되었고, **When** 3분 이내에 올바른 OTP 코드를 입력하면, **Then** 로그인에 성공하고 세션이 생성되며, 원래 접근하려던 페이지로 이동한다 (없으면 Workshops)
3. **Given** OTP 코드가 발송되었고, **When** 잘못된 OTP 코드를 입력하면, **Then** "인증 코드가 올바르지 않습니다" 오류 메시지가 표시된다
4. **Given** OTP 코드가 발송된 지 3분이 경과했고, **When** 해당 OTP 코드를 입력하면, **Then** "인증 코드가 만료되었습니다" 오류 메시지가 표시된다

---

### User Story 2 - 비인가 도메인 로그인 차단 (Priority: P1)

외부 사용자(허용되지 않은 도메인의 이메일)가 로그인을 시도하면 시스템은 로그인을 거부하고 안내 메시지를 표시합니다.

**Why this priority**: 보안상 필수 기능으로, 내부 직원만 접근 가능해야 함

**Independent Test**: 외부 도메인 이메일(@gmail.com 등)로 로그인 시도 시 거부 확인

**Acceptance Scenarios**:

1. **Given** 사용자가 로그인 페이지에 있고, **When** @gmail.com 이메일을 입력하고 OTP 요청을 클릭하면, **Then** "내부 직원 전용 로그인 서비스입니다." 메시지가 표시된다
2. **Given** 사용자가 로그인 페이지에 있고, **When** 유효하지 않은 이메일 형식을 입력하면, **Then** "올바른 이메일 형식을 입력해주세요" 오류 메시지가 표시된다

---

### User Story 3 - 로그인 세션 유지 (Priority: P2)

로그인한 내부 직원은 최대 7일 동안 세션이 유지되어 재로그인 없이 서비스를 이용할 수 있습니다.

**Why this priority**: 사용자 편의성을 위해 중요하지만, 핵심 인증 이후 구현 가능

**Independent Test**: 로그인 후 브라우저 재시작 시 세션 유지 확인, 7일 후 세션 만료 확인

**Acceptance Scenarios**:

1. **Given** 사용자가 로그인에 성공했고, **When** 브라우저를 닫았다가 다시 열면, **Then** 7일 이내라면 로그인 상태가 유지된다
2. **Given** 사용자가 로그인한 지 7일이 경과했고, **When** 페이지에 접근하면, **Then** 로그아웃 처리되고 로그인 페이지로 이동한다

---

### User Story 4 - Contributor 메뉴 접근 제어 (Priority: P1)

로그인한 내부 직원만 "Contribute Content"와 "Create Content" 메뉴에 접근할 수 있습니다. 비로그인 사용자가 해당 페이지에 접근하려 하면 로그인 페이지로 리다이렉트됩니다.

**Why this priority**: 핵심 접근 제어 기능으로, 인증 후 즉시 필요

**Independent Test**: 비로그인 상태에서 Contributor 메뉴 접근 시 리다이렉트 확인

**Acceptance Scenarios**:

1. **Given** 로그인하지 않은 사용자가, **When** Workshops 페이지에 접근하면, **Then** 정상적으로 콘텐츠가 표시된다
2. **Given** 로그인하지 않은 사용자가, **When** Contribute Content 또는 Create Content 페이지 URL에 직접 접근하면, **Then** 로그인 페이지로 리다이렉트된다
3. **Given** 로그인한 내부 직원이, **When** Contribute Content 페이지에 접근하면, **Then** 해당 페이지와 기능을 사용할 수 있다
4. **Given** 로그인한 내부 직원이, **When** Create Content 페이지에 접근하면, **Then** 해당 페이지와 기능을 사용할 수 있다

---

### User Story 5 - 백엔드 API 접근 제어 (Priority: P1)

Contributor 관련 백엔드 API는 인증된 내부 직원만 호출할 수 있습니다. 인증되지 않은 요청은 401 Unauthorized 응답을 반환합니다.

**Why this priority**: 보안상 필수 기능으로, 프론트엔드 보호만으로는 불충분

**Independent Test**: 인증 토큰 없이 보호된 API 호출 시 401 응답 확인

**Acceptance Scenarios**:

1. **Given** 인증되지 않은 클라이언트가, **When** Contributor 관련 API를 호출하면, **Then** 401 Unauthorized 응답을 받는다
2. **Given** 유효한 세션을 가진 클라이언트가, **When** Contributor 관련 API를 호출하면, **Then** 정상적으로 API 응답을 받는다
3. **Given** 만료된 세션을 가진 클라이언트가, **When** Contributor 관련 API를 호출하면, **Then** 401 Unauthorized 응답을 받는다

---

### User Story 6 - OTP 재발송 제한 (Priority: P2)

이메일 전송 비용 및 남용 방지를 위해 동일 이메일로 OTP 발송 후 3분간 추가 발송을 제한합니다.

**Why this priority**: 운영 비용 관리와 보안을 위해 중요하지만, 기본 로그인 이후 구현 가능

**Independent Test**: OTP 발송 후 즉시 재발송 시도 시 차단 확인, 3분 후 재발송 가능 확인

**Acceptance Scenarios**:

1. **Given** OTP 이메일이 발송된 지 1분이 경과했고, **When** 동일 이메일로 재발송을 요청하면, **Then** "2분 후에 다시 시도해주세요" 메시지와 함께 거부된다
2. **Given** OTP 이메일이 발송된 지 3분이 경과했고, **When** 동일 이메일로 재발송을 요청하면, **Then** 새로운 OTP가 발송된다

---

### User Story 7 - 로그아웃 (Priority: P2)

로그인한 사용자가 로그아웃하면 세션이 종료되고 메인 페이지로 리다이렉트됩니다.

**Why this priority**: 필수 기능이지만, 로그인 기능 완료 후 구현 가능

**Independent Test**: 로그아웃 클릭 후 세션 종료 및 메인 페이지 이동 확인

**Acceptance Scenarios**:

1. **Given** 로그인한 사용자가, **When** 로그아웃 버튼을 클릭하면, **Then** 세션이 종료되고 메인 페이지(Workshops)로 리다이렉트된다
2. **Given** 로그아웃한 사용자가, **When** Contributor 페이지에 접근하려 하면, **Then** 로그인 페이지로 리다이렉트된다

---

### User Story 8 - 로그인 기록 저장 (Priority: P3)

로그인 성공 시 사용자 정보(이메일)와 로그인 시간이 기록되어 향후 사용자 활동 추적에 활용됩니다.

**Why this priority**: 감사 및 추적 목적으로 필요하지만, 핵심 기능 이후 구현 가능

**Independent Test**: 로그인 성공 후 DB에 로그인 기록 생성 확인

**Acceptance Scenarios**:

1. **Given** 사용자가 OTP 인증에 성공했을 때, **When** 로그인이 완료되면, **Then** CosmosDB에 이메일과 로그인 시간이 기록된다
2. **Given** 동일 사용자가 여러 번 로그인했을 때, **When** 로그인 기록을 조회하면, **Then** 모든 로그인 이력이 조회된다

---

### Edge Cases

- **OTP 발송 실패**: Azure Communication Services 오류 시 사용자에게 "이메일 발송에 실패했습니다. 잠시 후 다시 시도해주세요" 메시지 표시
- **동시 로그인 시도**: 동일 이메일로 여러 디바이스에서 OTP 요청 시, 가장 최근 OTP만 유효 (이전 OTP 무효화)
- **브라우저 쿠키 비활성화**: 쿠키가 비활성화된 경우 세션 유지 불가, 사용자에게 쿠키 활성화 안내
- **세션 탈취 시도**: JWT 토큰 검증 실패 시 즉시 세션 무효화
- **이메일 대소문자**: 이메일 비교 시 대소문자 구분 없이 처리 (정규화)

## Requirements *(mandatory)*

### Functional Requirements

#### 인증 흐름

- **FR-001**: 시스템은 @microsoft.com 또는 @github.com 도메인의 이메일만 로그인을 허용해야 한다
- **FR-002**: 시스템은 Azure Communication Services를 통해 6자리 숫자 OTP 코드를 이메일로 발송해야 한다
- **FR-003**: OTP 코드는 랜덤하게 생성된 6자리 숫자(000000~999999)여야 한다
- **FR-004**: OTP 코드의 유효 기간은 발송 시점으로부터 3분이어야 한다
- **FR-005**: 동일 이메일에 대해 새로운 OTP 요청 시 이전 OTP는 즉시 무효화되어야 한다
- **FR-006**: 동일 이메일로 OTP 발송 후 3분간 추가 OTP 발송 요청을 차단해야 한다

#### 세션 관리

- **FR-007**: 로그인 성공 시 세션은 최대 7일간 유지되어야 한다
- **FR-008**: 세션 정보는 JWT 토큰 형태로 HttpOnly 쿠키에 저장되어야 한다 (XSS 방지)
- **FR-009**: 로그아웃 시 클라이언트의 세션 토큰을 삭제하고 메인 페이지로 리다이렉트해야 한다
- **FR-010**: 사용자 이메일 정보는 세션에 포함되어 이후 사용자 활동 추적에 활용되어야 한다

#### 접근 제어

- **FR-011**: Workshops 메뉴는 인증 없이 모든 사용자가 접근 가능해야 한다
- **FR-012**: Contribute Content 및 Create Content 메뉴는 인증된 사용자만 접근 가능해야 한다
- **FR-013**: 비인증 사용자가 보호된 페이지 접근 시 "이 기능을 사용하려면 로그인이 필요합니다" 메시지와 함께 로그인 페이지로 리다이렉트해야 한다
- **FR-014**: Contributor 관련 백엔드 API는 유효한 세션 토큰이 있는 요청만 처리해야 한다
- **FR-015**: 인증되지 않은 API 요청에 대해 401 Unauthorized 응답을 반환해야 한다

#### 데이터 저장

- **FR-016**: OTP 요청 시 CosmosDB의 로그인 대기 테이블에 이메일, OTP 코드, 발송 시간을 저장해야 한다
- **FR-017**: 동일 이메일에 대한 OTP 재요청 시 기존 레코드를 삭제하고 새 레코드를 생성해야 한다
- **FR-018**: 로그인 성공 시 사용자 로그인 이력 테이블에 이메일과 로그인 시간을 기록해야 한다
- **FR-019**: 로그인 실패는 별도로 저장하지 않는다

#### 임시 기능 제거

- **FR-020**: 기존의 OTP 코드를 프론트엔드에 표시하는 임시 기능을 제거해야 한다

### Key Entities

- **LoginAttempt (로그인 대기)**: 이메일로 식별되는 OTP 인증 대기 정보. 이메일, OTP 코드, 발송 시간, 만료 시간 포함. 이메일당 하나의 레코드만 유지
- **LoginHistory (로그인 이력)**: 성공한 로그인 기록. 이메일, 로그인 시간 포함. 사용자 활동 추적용
- **User Session (사용자 세션)**: 인증된 사용자의 세션 정보. 이메일, 발급 시간, 만료 시간 포함. JWT 토큰으로 관리

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 내부 직원이 OTP 요청부터 로그인 완료까지 2분 이내에 완료할 수 있다
- **SC-002**: 외부 도메인 이메일로 로그인 시도 시 100% 차단된다
- **SC-003**: OTP 이메일이 요청 후 30초 이내에 발송된다
- **SC-004**: 비인증 사용자의 보호된 리소스 접근이 100% 차단된다
- **SC-005**: 로그인한 사용자의 세션이 7일간 정상 유지된다
- **SC-006**: 3분 이내 OTP 재발송 시도가 100% 차단된다

## Clarifications

### Session 2026-01-22

- Q: OTP 입력 실패 시 시도 횟수를 제한해야 할까요? → A: 제한 없음 - 3분 만료만으로 충분
- Q: OTP 이메일 발송 실패 시 자동 재시도를 해야 할까요? → A: 재시도 없음 - 즉시 오류 표시, 사용자가 다시 요청
- Q: 로그인 성공 후 사용자를 어디로 리다이렉트해야 할까요? → A: 원래 접근하려던 보호된 페이지로 이동 (없으면 Workshops)
- Q: JWT 토큰을 클라이언트 어디에 저장해야 할까요? → A: HttpOnly 쿠키 - XSS 방지, 서버에서 설정
- Q: 비인증 사용자가 보호된 페이지 접근 시 어떤 안내를 표시해야 할까요? → A: "이 기능을 사용하려면 로그인이 필요합니다" 메시지 표시

## Assumptions

- Azure Communication Services가 이미 수동으로 구성되어 있다
- CosmosDB 연결이 이미 설정되어 있다
- 프론트엔드와 백엔드 간 CORS 설정이 완료되어 있다
- HTTPS 통신이 보장된다
- JWT 시크릿 키가 안전하게 관리된다

## Dependencies

- Azure Communication Services (이메일 발송)
- Azure Cosmos DB (데이터 저장)
- 기존 프론트엔드 라우팅 시스템 (Vue Router)
- 기존 백엔드 API 구조 (FastAPI)

## Out of Scope

- 소셜 로그인 (OAuth)
- 비밀번호 기반 인증
- 이중 인증 (2FA) - OTP 자체가 인증 수단
- 회원가입 프로세스 (별도 없음, 로그인 시 자동 생성)
- 사용자 프로필 관리
- 권한 레벨 세분화 (현재는 인증/비인증 2단계만)
