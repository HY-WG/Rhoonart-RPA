# Rhoonart RPA

B2B 영상 저작권 관리 · 리드 발굴 · 파트너 소명 요청 자동화 시스템

---

## 목차

- [프로젝트 개요](#프로젝트-개요)
- [시스템 구성](#시스템-구성)
- [주요 기능](#주요-기능)
- [기술 스택](#기술-스택)
- [로컬 실행](#로컬-실행)
- [Metabase 설정](#metabase-설정)
- [환경 변수](#환경-변수)
- [디렉토리 구조](#디렉토리-구조)
- [API 엔드포인트](#api-엔드포인트)
- [데이터베이스 마이그레이션](#데이터베이스-마이그레이션)
- [테스트 실행](#테스트-실행)
- [에이전트 설계 참고](#에이전트-설계-참고)
- [미결 사항](#미결-사항)

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
| **저작권 소명 요청 리스트** | `/admin/copyright-claims` | 권리사 공문 발송 및 소명 요청 관리 |
| **공문 작성** | `/admin/official-documents` | 권리사별 작품 단위 공문 편집 |
| 네이버 클립 성과 확인 | `/admin/reports/naver-clip` | 권리사별 수익 현황 |
| 보고 작품 관리 | `/admin/reports/naver-works` | 보고 대상 작품 등록 |
| 보고 스케줄 | `/admin/reports/naver-schedule` | 자동 보고 스케줄 설정 |

### 저작권 소명 요청 플로우

```
[admin] 저작권 소명 요청 리스트
   │
   ├─ 공문 없음 ──► 안내 모달 → "공문 작성하기" 버튼 → /admin/official-documents (필터 자동 적용)
   │
   └─ 공문 있음 ──► "요청" 버튼 클릭
                      │
                      ▼
              official_document_status = "requested" 저장
                      │
                      ▼
            [partner] /partner/relief 에 즉시 노출
                      │
                      ├─ 공문 확인 (admin 작성 공문 열람)
                      └─ 파일 제출 (권리사 공문 업로드)
                              │
                              ▼
                   status = "received" → 접수 완료 처리
```

### 파트너 포털 (`/partner`)

| 메뉴 | 경로 | 설명 |
|---|---|---|
| **저작권 소명 요청 리스트** | `/partner/relief` | admin 요청 수신 · 공문 확인 · 파일 제출 |
| 공문 가이드라인 | `/partner/guidelines` | 소명 공문 작성 가이드 |

---

## 기술 스택

| 분류 | 기술 |
|---|---|
| Frontend | Next.js 15 (App Router), TypeScript, Tailwind CSS, TanStack Query |
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
# 의존성 설치 (uvicorn은 requirements.txt에 없으므로 별도 설치)
pip install -r requirements.txt
pip install uvicorn

# 개발 서버 실행 (포트 8000)
python -m src.api.rpa_server
```

### 프론트엔드 실행

> **포트 주의:** Metabase Docker가 포트 3000을 사용 중이면 Next.js와 충돌합니다.
> Metabase 실행 중에는 포트 3001로 Next.js를 기동하세요.

```bash
cd web
npm install

npm run dev          # 포트 3000 (Metabase 미실행 시)
npm run dev -- -p 3001  # 포트 3001 (Metabase 실행 중일 때)
```

### 환경 변수 설정

```bash
cp .env.example .env
# .env 파일에 Supabase, Google API 키 등 입력
```

---

## 환경 변수

### 필수

| 변수 | 설명 |
|---|---|
| `SUPABASE_URL` | Supabase 프로젝트 URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase 서비스 롤 키 |
| `GOOGLE_CREDENTIALS_FILE` | Google SA 키 파일 경로 (기본: `credentials.json`) |
| `YOUTUBE_API_KEY` | YouTube Data API v3 키 |
| `X_INTERN_TOKEN` | RPA 서버 API 인증 토큰 (`X-RPA-Token` 헤더). 미설정 시 인증 비활성화 |

### Google Sheets

| 변수 | 설명 |
|---|---|
| `CONTENT_SHEET_ID` | 콘텐츠 목록 시트 ID |
| `NAVER_INBOUND_REPORT_SHEET_ID` | 네이버 보고용 인바운드 시트 ID |
| `LEAD_SHEET_ID` | C-1 리드 결과 저장 시트 ID |
| `SEED_CHANNEL_SHEET_ID` | 시드 채널 목록 시트 ID |
| `RIGHTS_HOLDER_SHEET_ID` | 권리사 목록 시트 ID |

### Slack

| 변수 | 설명 |
|---|---|
| `SLACK_BOT_TOKEN` | Slack Bot 토큰 (알림 발송 시 필수) |
| `SLACK_ERROR_CHANNEL` | 에러 알림 채널 (기본: `#rpa-error`) |
| `SLACK_RELIEF_CHANNEL` | 소명 요청 알림 채널 |

### 이메일 발송 (SMTP)

| 변수 | 설명 |
|---|---|
| `SMTP_HOST` | SMTP 서버 호스트 (기본: `smtp.gmail.com`) |
| `SMTP_PORT` | SMTP 포트 (기본: `587`) |
| `SMTP_USER` | SMTP 계정 |
| `SMTP_PASSWORD` | SMTP 비밀번호 (App Password 권장) |
| `SENDER_EMAIL` | 발신자 이메일 주소 |

### 외부 API

| 변수 | 설명 |
|---|---|
| `TMDB_API_KEY` | TMDB API 키 (C-1 드라마 제목 자동 수집에 필요) |
| `NOTION_API_KEY` | Notion API 키 (C-3 가이드라인 페이지 생성에 필요) |
| `NOTION_GUIDELINE_PARENT_PAGE_ID` | Notion 가이드라인 상위 페이지 ID |
| `ADMIN_API_BASE_URL` | Labelive 어드민 API 기본 URL |
| `ADMIN_API_TOKEN` | Labelive 어드민 API 인증 토큰 |

### 스케줄러 / 기타

| 변수 | 설명 | 기본값 |
|---|---|---|
| `NAVER_REPORT_SCHEDULER_ENABLED` | 네이버 보고 스케줄러 활성화 | `true` |
| `NAVER_REPORT_SCHEDULER_INTERVAL_SECONDS` | 스케줄러 폴링 간격 (초) | `60` |
| `INTEGRATION_DASHBOARD_DB_TYPE` | 대시보드 Runner DB 타입 (`memory` / `supabase`) | `memory` |

> `INTEGRATION_DASHBOARD_DB_TYPE=supabase`로 설정 시 `integration_runs` 테이블 마이그레이션이 적용되어 있어야 합니다.

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
│   │   ├── portal/           # 크리에이터 포털 페이지
│   │   ├── dashboard/        # 통합 대시보드 페이지
│   │   ├── auth/             # Supabase 인증 콜백
│   │   └── login/            # 로그인 페이지
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

## Metabase 설정

> **로컬 개발 전용 설정입니다.** 아래 Docker 명령은 개발 환경 기준이며, 운영 서버에 그대로 사용하지 마세요.
> 운영 배포 시 [원격 서버 배포 시 고려사항](#원격-서버-배포-시-고려사항)을 반드시 먼저 확인하세요.

Metabase는 WSL Docker로 실행합니다. **볼륨을 반드시 마운트**해야 컨테이너 재생성 후에도 대시보드·카드·설정이 유지됩니다.

### 컨테이너 최초 실행

```powershell
wsl docker run -d `
  --name metabase `
  -p 3000:3000 `
  -v metabase-data:/metabase-data `
  -e MB_DB_FILE=/metabase-data/metabase.db `
  -e MAX_SESSION_AGE=525600 `
  -e MB_SESSION_COOKIES=false `
  metabase/metabase
```

> `-v metabase-data:/metabase-data` 없이 실행하면 컨테이너 재생성 시 대시보드·카드·사용자 설정이 전부 초기화됩니다.

> **포트 충돌:** Metabase가 포트 3000을 점유하므로 Next.js 개발 서버는 `npm run dev -- -p 3001`로 실행해야 합니다.

### 볼륨 확인

```powershell
# Mounts=[] 이면 볼륨 없이 실행 중 — 즉시 중지하고 위 명령으로 재실행
wsl docker inspect metabase --format 'Mounts={{json .Mounts}}'
```

### 기존 컨테이너 DB 백업 (볼륨 없는 경우)

```powershell
wsl docker cp metabase:/metabase.db ./metabase-db-backup
```

### 일상적인 시작·중지

```powershell
wsl docker start metabase
wsl docker stop metabase
wsl docker logs -f metabase   # "Metabase Initialization COMPLETE" 확인
```

### 대시보드 재생성 (리셋 후 복구 시)

```powershell
python scripts\create_metabase_b2_dashboard.py `
  --url http://localhost:3000 `
  --public-url http://localhost:3000 `
  --database-id 2 `
  --mode split
```

```powershell
$env:METABASE_URL='http://localhost:3000'
$env:METABASE_DATABASE_ID='2'
python scripts\patch_metabase_work_title_dropdown.py
```

> 자세한 복구 절차는 [`docs/metabase_dashboard_recovery.md`](docs/metabase_dashboard_recovery.md)를 참고하세요.

### 원격 서버 배포 시 고려사항

| 항목 | 로컬 (현재) | 운영 서버 권장 |
|---|---|---|
| DB 저장소 | 컨테이너 내부 H2 (`metabase.db`) | **PostgreSQL 전환 필수** — H2는 프로덕션 비권장 |
| 볼륨 | named volume `metabase-data` | 원격 디스크 또는 EFS 마운트 |
| 공개 URL | `http://localhost:3000` | HTTPS 도메인 필수 |
| 세션 설정 | `MAX_SESSION_AGE=525600` (1년) | 보안 정책에 맞게 조정 |
| embed URL 재등록 | — | `scripts/update_metabase_public_urls.py` 실행하여 Supabase URL 갱신 |

원격 배포 후에는 반드시 `METABASE_PUBLIC_URL` 환경변수를 실제 서버 주소로 변경하고, Supabase `naver_rights_holders.metabase_embed_url`을 새 URL로 덮어써야 프론트엔드 iframe이 정상 작동합니다.

---

## 데이터베이스 마이그레이션

### 신규 Supabase 프로젝트 초기 세팅

신규 프로젝트를 처음 세팅할 때는 **`migrations/schema.sql` 하나만** 먼저 실행합니다.
이 파일은 `001`~`010` 마이그레이션을 통합한 최종 베이스라인입니다.

```sql
-- migrations/schema.sql 전체를 Supabase SQL Editor에서 실행
```

> **주의:** `001_portal_schema.sql`은 `schema.sql` 안에 포함되어 있습니다.
> 신규 세팅 시 `001`을 별도로 실행하지 마세요 — 중복 실행으로 오류가 납니다.

이후 아래 증분 마이그레이션을 **번호 순서대로** 실행합니다.

```
migrations/
├── schema.sql                                        ← 신규 세팅 시 이 파일만 먼저 실행 (001~010 통합)
├── 011_naver_rights_holders_metabase_url.sql
├── 012_seed_channel_schema_and_test_data.sql
├── 013_kakao_creators_application_fields.sql
├── 014_kakao_creators_standard_fields.sql
├── 015_partner_hil_and_lead_metrics.sql
├── 016_copyright_claim_documents.sql
├── 017_rights_holders_and_official_documents.sql
├── 017_copyright_claims_completed.sql               ← 017이 두 파일. 두 파일 모두 실행
├── 018_copyright_claim_official_document_files.sql
├── 018_copyright_claims_text_columns.sql            ← 018도 두 파일. 두 파일 모두 실행
├── 019_official_documents_work_scope.sql
└── 020_revenue_lead_work_registration.sql
```

### 기존 운영 DB 업데이트

이미 운영 중인 DB에는 아직 적용하지 않은 번호의 파일만 실행합니다.
현재 어느 마이그레이션까지 적용했는지 아래 쿼리로 확인하세요.

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

### 마이그레이션 실행 후 검증

| 확인 항목 | 쿼리 |
|---|---|
| 핵심 테이블 존재 | `SELECT COUNT(*) FROM works;` |
| 네이버 권리사 URL | `SELECT metabase_embed_url FROM naver_rights_holders LIMIT 3;` |
| 소명 요청 테이블 | `SELECT COUNT(*) FROM copyright_claim_documents;` |
| 공문 범위 컬럼 | `SELECT work_scope FROM official_documents LIMIT 1;` |
| 대시보드 Runner 테이블 | `SELECT COUNT(*) FROM integration_runs;` |

> `integration_runs` 테이블이 없으면 대시보드 Runner의 DB 저장이 전부 실패합니다.
> `INTEGRATION_DASHBOARD_DB_TYPE=supabase`로 운영 중이라면 반드시 확인하세요.

---

## 테스트 실행

```bash
# 전체 테스트 (live API 호출 없이)
pytest tests/ --no-live-api

# 특정 도메인만
pytest tests/api/
pytest tests/test_agents/
pytest tests/ -k "trending"

# 타입 검사
python -m mypy src/
```

### 테스트 구조

```
tests/
├── api/              # FastAPI 엔드포인트 단위 테스트
├── test_agents/      # 에이전트·승인 큐·도구 레지스트리 테스트
├── tasks/            # 태스크 핸들러 테스트
├── fixtures/         # 공통 JSON 픽스처 (live API 불필요)
├── conftest.py       # 공용 픽스처·패치 설정
└── fakes.py          # FakeLLMClient 등 테스트 더블
```

> `tests/fixtures/*.json` 픽스처를 사용하므로 테스트 시 YouTube·Supabase API를 실제로 호출하지 않습니다.
> live DB에 의존하는 `test_dashboard_runner.py`는 `integration_runs` 마이그레이션 적용 후에 통과합니다.

---

## 에이전트 설계 참고

### 시스템 프롬프트 조립 방식 — 코드 기반 vs. Markdown 기반

현재 `RhoArtAgent._build_system_prompt()`는 **코드에서 직접 문자열을 조립**하는 방식입니다.

```python
# src/agents/runtime/agent.py
def _build_system_prompt(self) -> str:
    return (
        "당신은 루나르트(Rhoonart) 업무 자동화 에이전트입니다.\n"
        "주어진 업무 지시(instruction)를 분석하여 적합한 도구를 선택하고 실행합니다.\n"
        ...
    )
```

| 항목 | 코드 기반 (현재) | Markdown 파일 기반 |
|---|---|---|
| 변경 방법 | 코드 수정 + 재배포 필요 | `.md` 파일만 수정 |
| 버전 관리 | git diff로 추적 가능 | 동일 |
| 도구 목록 포함 | 불필요 (native `tools=` 파라미터로 전달) | 동일 |
| 적합한 시점 | 현재처럼 프롬프트가 단순·고정적일 때 | 역할·규칙이 많아지고 비개발자도 조정할 때 |

현재 단계에서는 코드 기반으로 충분합니다. 규칙이 복잡해지면 Markdown 파일 로드 방식으로 전환을 검토하세요.

### agent.py 이중 구조 — 결정론적 코드 + LLM 추론

`RhoArtAgent`는 두 레이어로 구성됩니다.

```
결정론적 레이어 (Python 코드)
  ├── 승인 필요 여부 판단  (_needs_approval)
  ├── MAX_STEPS 상한 적용  (_react_loop)
  ├── dry_run 강제 플래그  (_think)
  └── 도구 실행·에러 처리  (_act)

LLM 추론 레이어 (Anthropic API)
  ├── 도구 선택
  └── 완료 신호 판단 (finish 호출)
```

**Think 기능 (Extended Thinking) 현재 상태:**
- `claude-3-5-haiku-20241022` 모델 기본 사용 — Extended Thinking 미지원 모델
- 에러 발생 시 워크플로우로 내보내는 별도 코드 없음 (에러는 `_act` 내 `try/except`로만 처리됨)
- 자동화 범위 확대 시 Extended Thinking 도입을 고려한다면, **feature flag** 방식으로 비활성화 상태로 추가하는 것을 권장합니다

```python
# 권장 패턴 (현재 미적용)
ENABLE_EXTENDED_THINKING = os.getenv("AGENT_EXTENDED_THINKING", "false") == "true"
```

> 자세한 에이전트 아키텍처는 [`docs/ai_agent_architecture.md`](docs/ai_agent_architecture.md)를 참고하세요.

---

## 개발 규칙

- 시크릿은 `.env`에만 저장, 코드에 하드코딩 금지
- `print()` 사용 금지 — `logging` 모듈만 사용
- 이메일 자동 발송 불가 — 반드시 사람 승인 필요
- YouTube API 쿼터 초과 시 즉시 중단 (10,000 units/day)
- 새 기능 구현 전 `.claude/rules/` 에 설계 문서 먼저 작성

자세한 규칙은 [CLAUDE.md](.claude/CLAUDE.md)를 참고하세요.

---

## 미결 사항

> 조사 기준일: 2026-05-12 — 원본: [Notion 미결사항 보고서](https://www.notion.so/2026-05-12-35d4e58491f2807eb465fa740e6fb715)

### 전체 목록

| ID | 미결사항 | 현재 상태 | 위험도 | 다음 액션 | 담당 |
|---|---|---|---|---|---|
| **T1** | `test_b2_sheet_performance_repository.py` — 모듈 삭제 후 테스트 파일 미제거, collection error | pytest 전체 실행 차단 (exit 2) | **High** | 테스트 파일 삭제 또는 모듈 복구 | Codex |
| **T2** | `test_c1_lead_filter.py` 7개 실패 — C-1 핸들러 변경 후 테스트 미갱신 | AttributeError 계열 실패, CI 통과 불가 | **High** | 실패 원인 추적 후 핸들러 or 테스트 수정 | Codex |
| **T3** | `test_dashboard_runner.py` 3개 실패 — 실제 Supabase `integration_runs` 테이블 404 | 테스트가 live DB에 직접 호출, 마이그레이션 미적용 의심 | **High** | `integration_runs` 마이그레이션 적용 확인 or mock 분리 | Manual Test |
| **T4** | `test_portal_admin_api.py` 1개 실패 — `/api/admin/lead-discovery` 400 반환 | 엔드포인트 응답 코드 불일치 | **Medium** | 라우터 변경사항과 테스트 기대값 대조 | Codex |
| **T5** | `test_copyright.py::TestRequestCopyrightClaim` mock이 구버전 로직 기준 | 테스트는 pass되나 `has_admin_document` 체크 검증 안 됨 | **Medium** | mock 시퀀스 + assert를 새 로직 기준으로 재작성 | Codex |
| **I1** | `send_channel_claim_email` — 실제 이메일 미발송, DB 상태 업데이트만 (`TODO` 주석) | stub 수준 구현, 채널 발송 버튼이 실제로는 작동 안 함 | **High** | EmailNotifier 연동 또는 채널 메일 발송 방식 결정 | Human |
| **I2** | `HttpAdminAPIClient.register_work()` / `update_guideline()` — API 필드명 미확인 (TODO 6개) | 실제 엔드포인트 명세 미수령, StubClient로 fallback 중 | **High** | 외부 API 명세 수령 후 TODO 해소 | Human |
| **I3** | Browser executor (A-2, B-2, C-1) — Playwright 미구현, 전부 `NotImplementedError` | 브라우저 자동화 경로 전면 미구현 | **Medium** | Playwright 도입 여부 결정 | Human |
| **I4** | 쿠폰 알림톡 템플릿 코드 하드코딩 (`template_code="COUPON_APPLIED"`) | 실제 카카오 템플릿 코드 미확인 | **Medium** | 실제 템플릿 코드 확인 후 교체 | Human |
| **H1** | 파트너 포털 `PARTNER_HOLDER_NAME = "CJ"` 하드코딩 — 동적 처리 미구현 | CJ 외 다른 권리사 로그인 시 데이터 표시 안 됨 | **High** | 파트너 인증 → right_holder_id 동적 주입 설계 | Human |
| **H2** | 파트너 API가 어드민 토큰(`check_auth`)으로만 인증 — 파트너 전용 인증 없음 | 파트너가 다른 파트너 데이터 접근 가능한 구조 | **High** | 파트너 인증 체계 설계 필요 | Human |
| **M1** | `send_channel_claim_email` 엔드포인트 테스트 없음 | 채널 발송 버튼 코드 경로 무검증 | **Medium** | 단위 테스트 추가 | Codex |
| **M2** | 파트너 파일 업로드 엔드포인트 테스트 없음 | 스토리지 연동 코드 무검증 | **Medium** | mock 기반 업로드 테스트 추가 | Codex |
| **D1** | `integration_runs` 테이블 마이그레이션 적용 여부 미확인 | 대시보드 Runner 기능 전체가 DB 저장 실패 중일 수 있음 | **High** | Supabase 대시보드에서 테이블 존재 확인 | Manual Test |
| **D2** | SMTP 없을 때 네이버 보고서 스케줄러 발송 실패 처리 미검증 | 스케줄러는 동작, 실제 발송 성공 여부 불명 | **Medium** | 실제 SMTP 환경에서 발송 테스트 | Manual Test |
| **A1** | tasks 레이어가 `src.api.dependencies`에서 `get_supabase` import — 레이어 위반 | 코드 동작은 하나 아키텍처 오염 | **Low** | `src/core/clients/supabase_client.py` 분리 | Claude |
| **A2** | `@app.on_event("startup")` deprecated — Python 3.16에서 제거 예정 | Deprecation warning 248회, 현재 동작은 정상 | **Low** | `lifespan` 컨텍스트 매니저로 교체 | Claude |
| **A3** | `datetime.utcnow()` deprecated | Deprecation warning만 | **Low** | `datetime.now(UTC)` 로 교체 | Claude |
| **C1** | C-3 동명이작 — `work_title`만으로 작품 식별, 등록 전 중복 체크 없음[^c3-dup] | Stub: 동명이작이 동일 `work_id` 수령 → 가이드라인 덮어쓰기 발생 가능 | **High** | 복합 키(`title + rights_holder + year`) 기반 중복 조회 메서드 추가 | Human |

### 지금 당장 처리해야 할 Top 5

1. **[T1]** `test_b2_sheet_performance_repository.py` 삭제 → pytest collection error로 전체 CI 차단 중
2. **[H2]** 파트너 API 인증 없음 → 현재 어드민 토큰 없이도 파트너 데이터 노출 가능한 구조
3. **[H1]** `PARTNER_HOLDER_NAME = "CJ"` 하드코딩 → 다른 권리사 로그인 시 아무것도 표시 안 됨
4. **[I1]** `send_channel_claim_email` 실제 미발송 → 버튼 누르면 "완료"가 뜨지만 실제 메일은 발송되지 않음
5. **[D1]** `integration_runs` 테이블 Supabase 적용 여부 → 대시보드 Runner 기능 전체가 DB 저장 실패 중일 수 있음

---

[^c3-dup]: 상세 분석은 [Notion — C-3 동명이작 문제](https://www.notion.so/C-3-24b4e58491f282549f9f81d4b390dff9?source=copy_link) 참고. 핵심: `work_title`만으로 식별 → 동명이작 등록 시 Stub은 동일 `work_id` 반환, 실 API는 기존 작품 가이드라인 덮어쓰기 또는 어드민 중복 노출 발생. 복합 키(`title + rights_holder + year`) 기반 중복 조회 및 사람 승인 흐름 필요.
