-- ============================================================
-- Rhoonart RPA — Supabase 초기 스키마
-- Supabase SQL Editor에 붙여넣기 후 실행
-- ============================================================

-- ──────────────────────────────────────────
-- 1. user_roles  (RBAC 역할 관리)
-- ──────────────────────────────────────────
create table if not exists public.user_roles (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid references auth.users(id) on delete cascade not null unique,
  role       text not null check (role in ('admin', 'creator')),
  created_at timestamptz default now()
);

-- ──────────────────────────────────────────
-- 2. profiles  (크리에이터 프로필)
-- ──────────────────────────────────────────
create table if not exists public.profiles (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid references auth.users(id) on delete cascade not null unique,
  email            text,
  channel_name     text,
  channel_url      text,
  subscriber_count bigint,
  monthly_views    bigint,
  looker_url       text,                  -- B-2 Looker 개인 대시보드 URL
  created_at       timestamptz default now(),
  updated_at       timestamptz default now()
);

-- ──────────────────────────────────────────
-- 3. channel_approvals  (A-0 채널 초대 승인)
-- ──────────────────────────────────────────
create table if not exists public.channel_approvals (
  id             uuid primary key default gen_random_uuid(),
  channel_id     text not null,
  channel_name   text not null,
  channel_url    text,
  creator_email  text not null,
  status         text not null default 'pending'
                   check (status in ('pending', 'approved', 'rejected')),
  requested_at   timestamptz default now(),
  processed_at   timestamptz
);

-- ──────────────────────────────────────────
-- 4. work_requests  (A-2 작품 사용 신청)
-- ──────────────────────────────────────────
create table if not exists public.work_requests (
  id           uuid primary key default gen_random_uuid(),
  creator_id   uuid references auth.users(id) on delete set null,
  work_title   text not null,
  status       text not null default 'pending'
                 check (status in ('pending', 'approved', 'rejected')),
  requested_at timestamptz default now(),
  processed_at timestamptz,
  drive_link   text,
  slack_ts     text          -- Slack 메시지 타임스탬프 (중복 방지용)
);

-- ──────────────────────────────────────────
-- 5. channel_stats  (B-2 채널 성과 데이터)
-- ──────────────────────────────────────────
create table if not exists public.channel_stats (
  id                    uuid primary key default gen_random_uuid(),
  creator_id            uuid references auth.users(id) on delete cascade,
  month                 text not null,     -- "2026-04" 형식
  monthly_views         bigint default 0,
  monthly_shorts_views  bigint default 0,
  subscriber_count      bigint default 0,
  created_at            timestamptz default now(),
  unique(creator_id, month)
);

-- ──────────────────────────────────────────
-- 6. leads  (C-1 리드 발굴 — YouTube Shorts 채널)
-- ──────────────────────────────────────────
create table if not exists public.leads (
  id                uuid primary key default gen_random_uuid(),
  channel_id        text not null unique,           -- YouTube channel ID
  channel_name      text not null,
  channel_url       text,
  platform          text default 'youtube',
  genre             text,                           -- "드라마/영화", "예능" 등
  grade             text check (grade in ('A', 'B', 'B?', 'C')),
  monthly_views     bigint default 0,               -- 월간 Shorts 조회수
  subscriber_count  bigint default 0,
  email             text,                           -- 채널 이메일 (연락처)
  email_status      text default 'unsent'
                      check (email_status in ('unsent', 'sent', 'replied', 'blocked')),
  blocked           boolean default false,
  block_reason      text,
  prev_monthly_views bigint,                        -- 전월 조회수 (성장률 계산용)
  discovered_at     timestamptz default now(),
  last_updated_at   timestamptz default now()
);

-- ──────────────────────────────────────────
-- 7. email_logs  (C-2 콜드메일 발송 로그)
-- ──────────────────────────────────────────
create table if not exists public.email_logs (
  id              uuid primary key default gen_random_uuid(),
  lead_id         uuid references public.leads(id) on delete set null,
  channel_id      text,
  channel_name    text,
  recipient_email text not null,
  subject         text,
  body_preview    text,                             -- 본문 앞 200자
  status          text not null
                    check (status in ('sent', 'failed', 'bounced')),
  sent_at         timestamptz default now(),
  error_message   text
);

-- ──────────────────────────────────────────
-- 8. integration_runs  (RPA 실행 로그)
-- ──────────────────────────────────────────
create table if not exists public.integration_runs (
  run_id            uuid primary key default gen_random_uuid(),
  task_id           text not null,
  title             text,
  payload           jsonb,
  status            text not null,
  execution_mode    text,
  requires_approval boolean default false,
  approved          boolean default false,
  started_at        timestamptz default now(),
  updated_at        timestamptz default now(),
  finished_at       timestamptz,
  result            jsonb,
  error             text,
  logs              text[]
);

-- ============================================================
-- RLS (Row Level Security) 정책
-- ============================================================

-- user_roles: 본인 역할만 조회 가능 / admin은 전체 관리
alter table public.user_roles enable row level security;

create policy "본인 역할 조회"
  on public.user_roles for select
  using (auth.uid() = user_id);

create policy "admin 전체 조회"
  on public.user_roles for select
  using (
    exists (
      select 1 from public.user_roles ur
      where ur.user_id = auth.uid() and ur.role = 'admin'
    )
  );

-- profiles: 본인만 조회/수정, admin은 전체 조회
alter table public.profiles enable row level security;

create policy "본인 프로필 조회"
  on public.profiles for select
  using (auth.uid() = user_id);

create policy "본인 프로필 수정"
  on public.profiles for update
  using (auth.uid() = user_id);

create policy "admin 전체 프로필 조회"
  on public.profiles for select
  using (
    exists (
      select 1 from public.user_roles ur
      where ur.user_id = auth.uid() and ur.role = 'admin'
    )
  );

-- channel_approvals: admin만 관리
alter table public.channel_approvals enable row level security;

create policy "admin 채널승인 전체 관리"
  on public.channel_approvals for all
  using (
    exists (
      select 1 from public.user_roles ur
      where ur.user_id = auth.uid() and ur.role = 'admin'
    )
  );

-- work_requests: 본인 요청 조회 + admin 전체 관리
alter table public.work_requests enable row level security;

create policy "본인 작품신청 조회"
  on public.work_requests for select
  using (auth.uid() = creator_id);

create policy "admin 작품신청 전체 관리"
  on public.work_requests for all
  using (
    exists (
      select 1 from public.user_roles ur
      where ur.user_id = auth.uid() and ur.role = 'admin'
    )
  );

-- channel_stats: 본인 데이터만 조회, admin 전체 관리
alter table public.channel_stats enable row level security;

create policy "본인 성과 조회"
  on public.channel_stats for select
  using (auth.uid() = creator_id);

create policy "admin 성과 전체 관리"
  on public.channel_stats for all
  using (
    exists (
      select 1 from public.user_roles ur
      where ur.user_id = auth.uid() and ur.role = 'admin'
    )
  );

-- leads: admin + 서비스 역할(Lambda)만 접근
alter table public.leads enable row level security;

create policy "admin 리드 전체 관리"
  on public.leads for all
  using (
    exists (
      select 1 from public.user_roles ur
      where ur.user_id = auth.uid() and ur.role = 'admin'
    )
  );

-- email_logs: admin만 접근
alter table public.email_logs enable row level security;

create policy "admin 이메일로그 전체 관리"
  on public.email_logs for all
  using (
    exists (
      select 1 from public.user_roles ur
      where ur.user_id = auth.uid() and ur.role = 'admin'
    )
  );

-- integration_runs: admin만 접근
alter table public.integration_runs enable row level security;

create policy "admin 실행로그 전체 관리"
  on public.integration_runs for all
  using (
    exists (
      select 1 from public.user_roles ur
      where ur.user_id = auth.uid() and ur.role = 'admin'
    )
  );

-- ============================================================
-- 편의 함수: 신규 유저 가입 시 profiles 자동 생성
-- ============================================================
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public
as $$
begin
  insert into public.profiles (user_id, email)
  values (new.id, new.email);
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- ============================================================
-- 인덱스
-- ============================================================
create index if not exists idx_leads_grade            on public.leads(grade);
create index if not exists idx_leads_email_status     on public.leads(email_status);
create index if not exists idx_leads_blocked          on public.leads(blocked);
create index if not exists idx_email_logs_lead_id     on public.email_logs(lead_id);
create index if not exists idx_email_logs_sent_at     on public.email_logs(sent_at desc);
create index if not exists idx_channel_stats_month    on public.channel_stats(month desc);
create index if not exists idx_integration_runs_task  on public.integration_runs(task_id);
create index if not exists idx_integration_runs_status on public.integration_runs(status);
create index if not exists idx_channel_approvals_status on public.channel_approvals(status);
