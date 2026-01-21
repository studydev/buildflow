# NexusSkill Frontend

> 📦 **코드명:** BuildFlow Frontend

Vue 3 + TypeScript 기반 프론트엔드 - 콘텐츠 탐색 및 학습 플랫폼 UI

## 🚀 빠른 시작

### 사전 요구사항

- Node.js 20+
- npm

### 로컬 실행

```bash
# 의존성 설치
npm install

# 개발 서버 실행
npm run dev

# 프로덕션 빌드
npm run build

# 빌드 미리보기
npm run preview
```

### 개발 서버

http://localhost:5173 에서 확인

## 📁 프로젝트 구조

```
frontend/
├── App.vue                  # 루트 컴포넌트
├── main.ts                  # 앱 진입점
├── style.css                # 글로벌 스타일
├── components/              # Vue 컴포넌트
│   ├── Assistant.vue        # AI 어시스턴트 채팅
│   ├── ContentGrid.vue      # 콘텐츠 카드 그리드
│   ├── LanguageToggle.vue   # EN/KR 언어 전환
│   ├── HelloWorld.vue       # 샘플 컴포넌트
│   ├── auth/                # 인증 관련 컴포넌트
│   ├── layout/              # 레이아웃 컴포넌트
│   │   └── Header.vue       # 헤더
│   └── ui/                  # UI 공통 컴포넌트
│       ├── Button.vue
│       ├── Card.vue
│       ├── Dialog.vue
│       ├── Input.vue
│       └── ...
├── views/                   # 페이지 뷰
│   ├── Home.vue             # 메인 홈 페이지
│   └── contributor/         # 기여자 페이지
│       └── ContributeContent.vue
├── stores/                  # Pinia 상태 관리
│   ├── index.ts             # 스토어 설정
│   ├── auth.ts              # 인증 상태
│   ├── content.ts           # 콘텐츠 상태
│   └── analysis.ts          # 분석 상태
├── router/                  # Vue Router
│   └── index.ts             # 라우트 정의
├── lib/                     # 유틸리티
│   ├── api.ts               # API 클라이언트
│   └── utils.ts             # 헬퍼 함수
├── types/                   # TypeScript 타입
│   ├── content.ts           # 콘텐츠 타입
│   └── pipeline.ts          # 파이프라인 타입
├── assets/                  # 정적 자산
└── __tests__/               # 테스트
    └── App.spec.ts
```

## 🧩 주요 컴포넌트

### ContentGrid.vue
콘텐츠 카드를 그리드 형태로 표시하는 핵심 컴포넌트

**기능:**
- 콘텐츠 카드 렌더링
- 무한 스크롤 / 페이지네이션
- 필터링 및 정렬

### LanguageToggle.vue
영어/한국어 언어 전환 토글

**기능:**
- EN/KR 전환
- 로컬 스토리지 저장
- 다국어 콘텐츠 표시 제어

### Assistant.vue
AI 기반 채팅 어시스턴트 인터페이스

**기능:**
- 채팅 UI
- RAG 기반 콘텐츠 추천 (예정)
- 학습 가이드 제공 (예정)

## 📦 상태 관리 (Pinia)

### content.ts
콘텐츠 관련 상태 및 액션

```typescript
// 주요 상태
contents: ContentItem[]      // 콘텐츠 목록
selectedCategory: string     // 선택된 카테고리
searchQuery: string          // 검색어
loading: boolean             // 로딩 상태

// 주요 액션
fetchContents()              // 콘텐츠 조회
advancedSearch(params)       // 고급 검색
```

### auth.ts
인증 상태 관리

```typescript
// 주요 상태
user: User | null            // 현재 사용자
isAuthenticated: boolean     // 인증 여부
token: string | null         // JWT 토큰

// 주요 액션
login(email, otp)            // 로그인
logout()                     // 로그아웃
refreshToken()               // 토큰 갱신
```

### analysis.ts
GitHub 분석 상태

```typescript
// 주요 상태
analysisResult: AnalysisResult | null
isAnalyzing: boolean

// 주요 액션
analyzeRepository(url)       // 저장소 분석
```

## 🛤️ 라우팅

| 경로 | 컴포넌트 | 설명 |
|------|----------|------|
| `/` | Home.vue | 메인 홈 페이지 |
| `/contribute` | ContributeContent.vue | 콘텐츠 기여 페이지 |

## 🧪 테스트

```bash
# 테스트 실행
npm run test

# 워치 모드
npm run test:watch

# 커버리지
npm run test:coverage
```

## 🔍 린트 및 타입 체크

```bash
# ESLint 검사
npm run lint:check

# ESLint 자동 수정
npm run lint

# TypeScript 타입 체크
npm run type-check

# 전체 빌드 (타입 체크 포함)
npm run build
```

## 🎨 스타일링

- **Tailwind CSS**: 유틸리티 기반 CSS 프레임워크
- **shadcn/vue**: UI 컴포넌트 라이브러리

### Tailwind 설정

```javascript
// tailwind.config.js
module.exports = {
  content: ['./index.html', './frontend/**/*.{vue,js,ts}'],
  theme: {
    extend: {
      // 커스텀 테마
    }
  }
}
```

## 🔧 환경 변수

```env
# API 엔드포인트
VITE_API_URL=http://localhost:8001

# 기타 설정
VITE_APP_TITLE=NexusSkill
```

## 📋 주요 의존성

| 패키지 | 버전 | 용도 |
|--------|------|------|
| Vue | 3.x | UI 프레임워크 |
| TypeScript | 5.x | 타입 안전성 |
| Vite | 7.x | 빌드 도구 |
| Pinia | 2.x | 상태 관리 |
| Vue Router | 4.x | 라우팅 |
| Tailwind CSS | 3.x | 스타일링 |
| Vitest | 4.x | 테스트 프레임워크 |
| ESLint | 9.x | 린터 |

## 🐳 Docker

```bash
# 빌드
docker build -f ../Dockerfile.frontend -t buildflow-frontend ..

# 실행
docker run -p 80:80 buildflow-frontend
```
