# Rhoonart RPA

B2B 영상 저작권 관리 · 리드 발굴 · 파트너 소명 요청 자동화 시스템

---

## 목차

- [프로젝트 개요](#프로젝트-개요)
- [시스템 구성](#시스템-구성)
- [주요 기능](#주요-기능)
- [기술 스택](#기술-스택)
- [로컬 실행](#로컬-실행)
- [환경 변수](#환경-변수)
- [디렉토리 구조](#디렉토리-구조)
- [API 엔드포인트](#api-엔드포인트)
- [데이터베이스 마이그레이션](#데이터베이스-마이그레이션)

---

## 프로젝트 개요

Rhoonart RPA는 콘텐츠 라이선싱 비즈니스의 반복 업무를 자동화하는 내부 운영 시스템입니다.

| 업무 도메인 | 설명 |
|---|---|
| 저작권 소명 관리 | 채널별 저작권 침해 신고에 대한 권리사 공문 발송 및 접수 관리 |
| 리드 채널 발굴 | YouTube Shorts 데이터 기반 잠재 파트너 채널 자동 수집 |
| 네이버 클립 보고 | 권리사별 주간·월간 성과 보고 자동 생성 및 발송 |
| 작품 사용 신청 | 채널 크리에이터의 작품 사용 요청 접수 및 승인 처리 |

---

## 시스템 구성

```
┌─────────────────────────────────────────────────────────┐
│                        Web (Next.js)                     │
│  /admin  — 내부 운영 어드민                               │
│  /partner — 권리사 파트너 포털                            │
│  /portal  — 채널 크리에이터 포털                          │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP (localhost:8000)
┌───────────────────────▼─────────────────────────────────┐
│              RPA Control Server (FastAPI)                 │
│  /api/admin/*    — 어드민 API                            │
│  /api/partner/*  — 파트너 API                            │
│  /dashboard      — 통합 대시보드 (sub-app)               │
│  /relief         — 소명 요청 백오피스 (sub-app)           │
└───────────────────────┬─────────────────────────────────┘
                        │
          ┌─────────────┴─────────────┐
          │                           │
   ┌──────▼──────┐           ┌────────▼────────┐
   │  Supabase   │           │  Google Sheets  │
   │  (PostgreSQL│           │  (네이버 보고)   │
   │  + Storage) │           └─────────────────┘
   └─────────────┘
```

---

## 주요 기능

### 어드민 (`/admin`)

| 메뉴 | 경로 | 설명 |
|---|---|---|
| 채널 조회 | `/admin/channels` | 등록된 채널 목록 및 상태 확인 |
| 리드 채널 관리 | `/admin/lead-discovery` | YouTube Shorts 리드 채널 발굴 현황 |
| 신규 영상 등록 | `/admin/new-work` | 작품·영상 등록 및 채널 매핑 |
| 영상별 채널 현황 | `/admin/videos` | 영상 단위 채널 소명 현황 |
| 작품 사용 신청 현황 | `/admin/work-application` | 크리에이터 신청 승인 처리 |
| 저작권 소명 요청 리스트 | `/admin/copyright-claims` | 권리사 공문 발송 및 소명 요청 관리 |
| 공문 작성 | `/admin/official-documents` | 권리사별 작품 단위 공문 편집 |
| 네이버 클립 성과 확인 | `/admin/reports/naver-clip` | 권리사별 수익 현황 |
| 보고 작품 관리 | `/admin/reports/naver-works` | 보고 대상 작품 등록 |
| 보고 스케줄 | `/admin/reports/naver-schedule` | 자동 보고 스케줄 설정 |


### 파트너 포털 (`/partner`)

| 메뉴 | 경로 | 설명 |
|---|---|---|
| 저작권 소명 요청 리스트| `/partner/relief` | admin 요청 수신 · 공문 확인 · 파일 제출 |

---

## 기술 스택

| 분류 | 기술 |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS, TanStack Query |
| Backend | Python 3.10+, FastAPI, Uvicorn |
| Database | Supabase (PostgreSQL), Supabase Storage |
| 자동화 | Python RPA, YouTube Data API v3, Google Sheets API |
| 인프라 | Windows Server (로컬 실행), Vercel (프론트 배포 예정) |

---

## 로컬 실행

### 요구사항

- Python 3.10+
- Node.js 18+
- `.env` 파일 설정 (`.env.example` 참고)

### 백엔드 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# 개발 서버 실행 (포트 8000)
python -m src.api.rpa_server
```

### 프론트엔드 실행

```bash
cd web
npm install
npm run dev   # 포트 3000
```

### 환경 변수 설정

```bash
cp .env.example .env
# .env 파일에 Supabase, Google API 키 등 입력
```

---

## 환경 변수

| 변수 | 설명 | 필수 |
|---|---|---|
| `SUPABASE_URL` | Supabase 프로젝트 URL | ✅ |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase 서비스 롤 키 | ✅ |
| `GOOGLE_CREDENTIALS_FILE` | Google SA 키 파일 경로 | ✅ |
| `GOOGLE_SPREADSHEET_ID` | 보고용 Google Sheets ID | ✅ |
| `YOUTUBE_API_KEY` | YouTube Data API v3 키 | ✅ |
| `NAVER_REPORT_SCHEDULER_ENABLED` | 네이버 보고 스케줄러 활성화 (`true`/`false`) | - |
| `NAVER_REPORT_SCHEDULER_INTERVAL_SECONDS` | 스케줄러 폴링 간격 (기본 60초) | - |
| `ADMIN_API_TOKEN` | 어드민 API 인증 토큰 | ✅ |

> 시크릿 정보는 `.env`에만 저장. 코드에 하드코딩 금지.

---

## 디렉토리 구조

```
rhoonart-rpa/
├── src/
│   ├── api/
│   │   ├── routes/           # FastAPI 도메인 라우터
│   │   │   ├── admin_copyright.py   # 저작권 소명 · 공문 API
│   │   │   ├── admin_naver.py       # 네이버 클립 API
│   │   │   ├── admin_leads.py       # 리드 채널 API
│   │   │   └── ...
│   │   ├── rpa_server.py     # FastAPI 앱 진입점
│   │   └── dependencies.py  # 공용 의존성 (Supabase, 캐시 등)
│   ├── agents/               # RPA 에이전트 파이프라인
│   ├── core/
│   │   ├── clients/          # 외부 API 클라이언트
│   │   ├── repositories/     # Supabase · Sheets 저장소
│   │   └── interfaces/       # 공통 인터페이스 (ITaskHandler)
│   ├── tasks/                # 태스크 핸들러 (A-0, A-2, B-2 등)
│   └── services/             # 비즈니스 서비스 레이어
├── web/
│   ├── app/
│   │   ├── admin/            # 어드민 페이지
│   │   ├── partner/          # 파트너 포털 페이지
│   │   └── portal/           # 크리에이터 포털 페이지
│   ├── components/           # 공용 컴포넌트
│   └── lib/
│       ├── api.ts            # API 클라이언트 함수 및 타입
│       └── query-client.ts  # TanStack Query 설정
├── migrations/               # Supabase SQL 마이그레이션
├── tests/                    # 단위 · 통합 테스트
└── .claude/                  # Claude Code 프로젝트 설정
```

---

## API 엔드포인트

### 저작권 소명 (`/api/admin/copyright-claims`)

| Method | Path | 설명 |
|---|---|---|
| `GET` | `/api/admin/copyright-claims` | 소명 요청 목록 조회 |
| `POST` | `/api/admin/copyright-claims/right-holders/{id}/request` | 권리사에 소명 요청 발송 |
| `POST` | `/api/admin/copyright-claims/channels/{id}/send-email` | 채널 일괄 메일 발송 |
| `GET` | `/api/admin/copyright-claims/{id}/official-document-file` | 업로드된 공문 파일 다운로드 |

### 공문 (`/api/admin/official-documents`)

| Method | Path | 설명 |
|---|---|---|
| `GET` | `/api/admin/official-documents` | 권리사별 공문 목록 조회 |
| `GET` | `/api/admin/official-documents/{right_holder_id}` | 특정 권리사·작품 공문 조회 |
| `PUT` | `/api/admin/official-documents/{right_holder_id}` | 공문 저장 (upsert) |

### 파트너 (`/api/partner`)

| Method | Path | 설명 |
|---|---|---|
| `GET` | `/api/partner/copyright-claims` | 파트너 소명 요청 목록 (requested · received 건) |
| `GET` | `/api/partner/official-documents/{right_holder_id}` | 파트너 공문 조회 |
| `POST` | `/api/partner/copyright-claims/official-document-upload` | 파트너 공문 파일 업로드 |

---

## 데이터베이스 마이그레이션

`migrations/` 디렉터리의 SQL 파일을 Supabase SQL Editor에서 순서대로 실행합니다.

```
migrations/
├── 001_portal_schema.sql
├── ...
├── 016_copyright_claim_documents.sql
├── 017_rights_holders_and_official_documents.sql
├── 018_copyright_claim_official_document_files.sql
└── 019_official_documents_work_scope.sql
```

---

## 개발 규칙

- 시크릿은 `.env`에만 저장, 코드에 하드코딩 금지
- `print()` 사용 금지 — `logging` 모듈만 사용
- 이메일 자동 발송 불가 — 반드시 사람 승인 필요
- YouTube API 쿼터 초과 시 즉시 중단 (10,000 units/day)
- 새 기능 구현 전 `.claude/rules/` 에 설계 문서 먼저 작성

자세한 규칙은 [CLAUDE.md](.claude/CLAUDE.md)를 참고하세요.
