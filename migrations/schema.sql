-- =============================================================================
-- Rhoonart RPA — Consolidated Supabase Schema
-- 생성일: 2026-05-11
-- 출처: migrations/001 ~ migrations/010 통합 (최종 상태)
--
-- 원본 마이그레이션 파일들은 이 파일로 대체되었습니다.
-- 적용: Supabase SQL Editor에서 실행 또는 psql $DATABASE_URL -f schema.sql
-- =============================================================================

-- =============================================================================
-- 섹션 1. 독립 테이블 (FK 없음 또는 auth.users 참조)
-- =============================================================================

-- ── 1-1. user_roles (RBAC) ───────────────────────────────────────────────────
create table if not exists public.user_roles (
  id         uuid        primary key default gen_random_uuid(),
  user_id    uuid        references auth.users(id) on delete cascade not null unique,
  role       text        not null check (role in ('admin', 'creator')),
  created_at timestamptz default now()
);

-- ── 1-2. user_profiles (크리에이터 프로필) ───────────────────────────────────
create table if not exists public.user_profiles (
  id               uuid        primary key default gen_random_uuid(),
  user_id          uuid        references auth.users(id) on delete cascade not null unique,
  email            text,
  channel_name     text,
  channel_url      text,
  subscriber_count bigint,
  monthly_views    bigint,
  looker_url       text,
  created_at       timestamptz default now(),
  updated_at       timestamptz default now()
);

-- ── 1-3. creator_channel_applications (A-0 채널 초대 승인) ───────────────────
create table if not exists public.creator_channel_applications (
  id             uuid        primary key default gen_random_uuid(),
  channel_id     text        not null,
  channel_name   text        not null,
  channel_url    text,
  creator_email  text        not null,
  status         text        not null default 'pending'
                               check (status in ('pending', 'approved', 'rejected')),
  requested_at   timestamptz default now(),
  processed_at   timestamptz
);

-- ── 1-4. work_usage_requests (A-2 작품 사용 신청 — 관리자 승인 플로우) ──────
create table if not exists public.work_usage_requests (
  id           uuid        primary key default gen_random_uuid(),
  creator_id   uuid        references auth.users(id) on delete set null,
  work_title   text        not null,
  status       text        not null default 'pending'
                             check (status in ('pending', 'approved', 'rejected')),
  requested_at timestamptz default now(),
  processed_at timestamptz,
  drive_link   text,
  slack_ts     text
);

-- ── 1-5. creator_channel_monthly_stats (B-2 채널 성과) ───────────────────────
create table if not exists public.creator_channel_monthly_stats (
  id                    uuid        primary key default gen_random_uuid(),
  creator_id            uuid        references auth.users(id) on delete cascade,
  month                 text        not null,  -- "2026-04" 형식
  monthly_views         bigint      default 0,
  monthly_shorts_views  bigint      default 0,
  subscriber_count      bigint      default 0,
  created_at            timestamptz default now(),
  unique (creator_id, month)
);

-- ── 1-6. automation_runs (RPA 실행 로그) ─────────────────────────────────────
create table if not exists public.automation_runs (
  run_id            uuid        primary key default gen_random_uuid(),
  task_id           text        not null,
  title             text,
  payload           jsonb,
  status            text        not null,
  execution_mode    text,
  requires_approval boolean     default false,
  approved          boolean     default false,
  started_at        timestamptz default now(),
  updated_at        timestamptz default now(),
  finished_at       timestamptz,
  result            jsonb,
  error             text,
  logs              text[]
);

-- ── 1-7. lead_channels (C-1 리드 채널) ───────────────────────────────────────
create table if not exists public.lead_channels (
  id                    uuid        primary key default gen_random_uuid(),
  channel_id            text        not null unique,
  channel_name          text        not null,
  channel_url           text,
  platform              text        default 'youtube',
  genre                 text,
  grade                 text        check (grade in ('A', 'B', 'B?', 'C')),
  monthly_views         bigint      default 0,
  subscriber_count      bigint      default 0,
  email                 text,
  email_status          text        default 'unsent'
                          check (email_status in ('unsent', 'sent', 'replied', 'bounced', 'blocked')),
  blocked               boolean     default false,
  block_reason          text,
  prev_monthly_views    bigint,
  discovered_at         timestamptz default now(),
  last_updated_at       timestamptz default now(),
  last_contacted_at     timestamptz,           -- 008 추가
  review_status         text        not null default 'pending'
                          check (review_status in ('pending', 'promoted', 'blocked')),  -- 009 추가
  reviewed_at           timestamptz,           -- 009 추가
  reviewed_by           text,                  -- 009 추가
  promoted_from_lead_id text                   -- 009: seed_channel 승격 출처
);

-- ── 1-8. lead_email_deliveries (C-2 콜드메일 로그) ───────────────────────────
create table if not exists public.lead_email_deliveries (
  id              uuid        primary key default gen_random_uuid(),
  lead_id         uuid        references public.lead_channels(id) on delete set null,
  channel_id      text,
  channel_name    text,
  recipient_email text        not null,
  subject         text,
  body_preview    text,
  status          text        not null
                    check (status in ('sent', 'failed', 'bounced')),
  sent_at         timestamptz default now(),
  error_message   text
);

-- ── 1-9. channel_blocklist (C-1 영구 블록리스트) ─────────────────────────────
create table if not exists public.channel_blocklist (
  channel_id   text        primary key,
  channel_name text,
  channel_url  text,
  platform     text        not null default 'youtube',
  reason       text,
  blocked_at   timestamptz not null default now(),
  blocked_by   text        not null default 'system'
);

-- ── 1-10. seed_channel (채널 시드 DB) ─────────────────────────────────────────
create table if not exists public.seed_channel (
  id                    uuid        primary key default gen_random_uuid(),
  channel_id            text,
  channel_name          text,
  channel_url           text,
  platform              text        not null default 'youtube',
  active                boolean     not null default true,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  promoted_from_lead_id text,       -- 009 추가
  promoted_by           text,       -- 009 추가
  promoted_at           timestamptz -- 009 추가
);

-- ── 1-11. work_requests (A-2 신청 확장 테이블 — 010) ─────────────────────────
create table if not exists public.work_requests (
  id            uuid        primary key default gen_random_uuid(),
  creator_id    uuid        references auth.users(id) on delete set null,
  work_title    text        not null,
  channel_name  text,
  creator_email text,
  status        text        not null default 'pending'
                  check (status in ('pending', 'approved', 'rejected')),
  requested_at  timestamptz default now(),
  processed_at  timestamptz,
  drive_link    text,
  slack_ts      text
);

-- =============================================================================
-- 섹션 2. Naver 클립 보고 테이블
-- =============================================================================

-- ── 2-1. naver_works (작품 카탈로그) ──────────────────────────────────────────
create table if not exists public.naver_works (
  id                   bigint      generated by default as identity primary key,
  work_title           text        not null unique,
  identifier           text,
  rights_holder_name   text,
  status               text        not null default 'Active',
  naver_report_enabled boolean     not null default false,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now()
);

-- ── 2-2. naver_rights_holders (권리사) ───────────────────────────────────────
create table if not exists public.naver_rights_holders (
  id                    bigint      generated by default as identity primary key,
  rights_holder_name    text        not null unique,
  email                 text,
  current_work_title    text,
  naver_report_enabled  boolean     not null default true,
  update_cycle          text,
  looker_spreadsheet_url text,
  looker_studio_url     text,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

-- ── 2-3. naver_clip_report_legacy_rows (레거시 단건 테이블) ──────────────────
create table if not exists public.naver_clip_report_legacy_rows (
  id                 bigint      generated by default as identity primary key,
  video_url          text,
  uploaded_at        date,
  channel_name       text,
  view_count         bigint      not null default 0,
  checked_at         date        not null default current_date,
  clip_title         text,
  work_title         text,
  platform           text,
  rights_holder_name text,
  identifier         text,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

-- ── 2-4. naver_clip_report_staging (스테이징 테이블) ─────────────────────────
create table if not exists public.naver_clip_report_staging (
  id                 bigint      generated by default as identity primary key,
  video_url          text,
  uploaded_at        date,
  channel_name       text,
  view_count         bigint      not null default 0,
  checked_at         date        not null default current_date,
  clip_title         text,
  work_title         text,
  platform           text,
  rights_holder_name text,
  identifier         text,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

-- ── 2-5. naver_report_delivery_logs (보고 전송 로그) ─────────────────────────
create table if not exists public.naver_report_delivery_logs (
  id                   bigint      generated by default as identity primary key,
  run_id               text,
  execution_mode       text,
  send_notifications   boolean     not null default false,
  status               text        not null default 'stub_only',
  result_json          jsonb       not null default '{}',
  created_at           timestamptz not null default now()
);

-- ── 2-6. naver_clip_report_runs (배치 실행 단위) ──────────────────────────────
create table if not exists public.naver_clip_report_runs (
  run_id                    uuid        primary key default gen_random_uuid(),
  checked_at                timestamptz not null default now(),
  finished_at               timestamptz,
  status                    text        not null default 'running'
                              check (status in ('running', 'success', 'failed')),
  triggered_by              text        not null default 'manual'
                              check (triggered_by in ('manual', 'schedule', 'api')),
  target_identifier_count   integer     not null default 0,
  row_count                 integer     not null default 0,
  error_message             text,
  created_at                timestamptz not null default now()
);

-- ── 2-7. naver_clip_report_daily_rows (일별 클립 행) ─────────────────────────
create table if not exists public.naver_clip_report_daily_rows (
  id                 bigint      generated by default as identity primary key,
  run_id             uuid        not null references public.naver_clip_report_runs(run_id) on delete cascade,
  video_url          text,
  uploaded_at        date,
  channel_name       text,
  view_count         bigint      not null default 0,
  checked_at         timestamptz not null,
  clip_title         text,
  work_title         text,
  platform           text        not null default 'naver_clip',
  rights_holder_name text,
  identifier         text,
  content_catalog_id bigint,
  rights_holder_id   bigint,
  created_at         timestamptz not null default now()
);

-- ── 2-8. naver_clip_report_yearly_summary (연간 집계) ────────────────────────
create table if not exists public.naver_clip_report_yearly_summary (
  year               integer     not null,
  rights_holder_name text        not null,
  work_title         text        not null,
  identifier         text        not null,
  clip_count         bigint      not null default 0,
  total_views        bigint      not null default 0,
  max_view_count     bigint      not null default 0,
  first_checked_at   timestamptz,
  latest_checked_at  timestamptz,
  updated_at         timestamptz not null default now(),
  primary key (year, rights_holder_name, work_title, identifier)
);

-- =============================================================================
-- 섹션 3. AI 에이전트 테이블
-- =============================================================================

-- ── 3-1. automation_agent_traces ─────────────────────────────────────────────
create table if not exists public.automation_agent_traces (
  trace_id    text        primary key,
  task_id     text        not null,
  envelope_id text        not null,
  status      text        not null default 'observing',
  steps       jsonb       not null default '[]',
  started_at  timestamptz not null default now(),
  finished_at timestamptz,
  constraint automation_agent_traces_status_check check (
    status in (
      'observing', 'thinking', 'awaiting_approval',
      'acting', 'reflecting', 'completed', 'failed'
    )
  )
);

-- ── 3-2. automation_approvals ────────────────────────────────────────────────
create table if not exists public.automation_approvals (
  approval_id      text        primary key,
  trace_id         text        not null references public.automation_agent_traces(trace_id) on delete cascade,
  task_id          text        not null,
  status           text        not null default 'pending',
  summary          text        not null,
  risk_level       text        not null,
  preview          jsonb       not null default '{}',
  checkpoint       jsonb       not null default '{}',
  execution_result jsonb,
  requested_at     timestamptz not null default now(),
  decided_at       timestamptz,
  decided_by       text        not null default '',
  decision_note    text        not null default '',
  constraint automation_approvals_status_check check (
    status in ('pending', 'approved', 'rejected', 'executed', 'failed', 'expired')
  ),
  constraint automation_approvals_risk_level_check check (
    risk_level in ('low', 'medium', 'high', 'critical')
  )
);

-- ── 3-3. automation_tool_invocations ─────────────────────────────────────────
create table if not exists public.automation_tool_invocations (
  invocation_id bigint      generated by default as identity primary key,
  trace_id      text        not null references public.automation_agent_traces(trace_id) on delete cascade,
  step_num      integer     not null,
  tool_name     text        not null,
  tool_input    jsonb       not null default '{}',
  tool_output   jsonb,
  error         text,
  duration_ms   integer,
  invoked_at    timestamptz not null default now()
);

-- =============================================================================
-- 섹션 4. 인덱스
-- =============================================================================

-- lead_channels
create index if not exists idx_lead_channels_grade          on public.lead_channels (grade);
create index if not exists idx_lead_channels_email_status   on public.lead_channels (email_status);
create index if not exists idx_lead_channels_blocked        on public.lead_channels (blocked);
create index if not exists idx_lead_channels_review_status  on public.lead_channels (review_status);

-- lead_email_deliveries
create index if not exists idx_lead_email_deliveries_lead_id on public.lead_email_deliveries (lead_id);
create index if not exists idx_lead_email_deliveries_sent_at on public.lead_email_deliveries (sent_at desc);

-- creator_channel_monthly_stats
create index if not exists idx_creator_channel_monthly_stats_month on public.creator_channel_monthly_stats (month desc);

-- automation_runs
create index if not exists idx_automation_runs_task   on public.automation_runs (task_id);
create index if not exists idx_automation_runs_status on public.automation_runs (status);

-- creator_channel_applications
create index if not exists idx_creator_channel_applications_status on public.creator_channel_applications (status);

-- work_requests
create unique index if not exists idx_work_requests_slack_ts  on public.work_requests (slack_ts) where slack_ts is not null;
create        index if not exists idx_work_requests_status     on public.work_requests (status);
create        index if not exists idx_work_requests_requested_at on public.work_requests (requested_at desc);

-- seed_channel
create unique index if not exists idx_seed_channel_url      on public.seed_channel (channel_url) where channel_url is not null;
create        index if not exists idx_seed_channel_platform  on public.seed_channel (platform, active);
create        index if not exists idx_seed_channel_channel_id on public.seed_channel (channel_id) where channel_id is not null;

-- channel_blocklist
create index if not exists idx_channel_blocklist_platform on public.channel_blocklist (platform);

-- naver_works
create index if not exists naver_works_report_enabled_idx on public.naver_works (naver_report_enabled, identifier);

-- naver_clip_report_runs
create index if not exists naver_clip_report_runs_checked_at_idx    on public.naver_clip_report_runs (checked_at desc);
create index if not exists naver_clip_report_runs_status_checked_idx on public.naver_clip_report_runs (status, checked_at desc);

-- naver_clip_report_daily_rows
create unique index if not exists naver_clip_report_daily_rows_run_video_uidx
  on public.naver_clip_report_daily_rows (run_id, video_url)
  where video_url is not null and video_url <> '';
create index if not exists naver_clip_report_daily_rows_checked_at_idx      on public.naver_clip_report_daily_rows (checked_at desc);
create index if not exists naver_clip_report_daily_rows_holder_checked_idx   on public.naver_clip_report_daily_rows (rights_holder_name, checked_at desc);
create index if not exists naver_clip_report_daily_rows_work_checked_idx     on public.naver_clip_report_daily_rows (work_title, checked_at desc);
create index if not exists naver_clip_report_daily_rows_identifier_checked_idx on public.naver_clip_report_daily_rows (identifier, checked_at desc);

-- naver_clip_report_staging
create index if not exists naver_clip_report_staging_checked_at_idx    on public.naver_clip_report_staging (checked_at desc);
create index if not exists naver_clip_report_staging_rights_holder_idx  on public.naver_clip_report_staging (rights_holder_name, checked_at desc);
create index if not exists naver_clip_report_staging_identifier_idx     on public.naver_clip_report_staging (identifier, checked_at desc);

-- naver_clip_report_yearly_summary
create index if not exists naver_clip_report_yearly_summary_holder_year_idx on public.naver_clip_report_yearly_summary (rights_holder_name, year desc);

-- automation_agent_traces
create index if not exists idx_automation_agent_traces_task_id on public.automation_agent_traces (task_id, started_at desc);
create index if not exists idx_automation_agent_traces_status  on public.automation_agent_traces (status)
  where status not in ('completed', 'failed');

-- automation_approvals
create index if not exists idx_automation_approvals_status  on public.automation_approvals (status, requested_at desc)
  where status = 'pending';
create index if not exists idx_automation_approvals_task_id on public.automation_approvals (task_id, requested_at desc);

-- automation_tool_invocations
create index if not exists idx_automation_tool_invocations_trace on public.automation_tool_invocations (trace_id, step_num);
create index if not exists idx_automation_tool_invocations_tool  on public.automation_tool_invocations (tool_name, invoked_at desc);

-- =============================================================================
-- 섹션 5. 뷰
-- =============================================================================

create or replace view public.v_naver_clip_report_daily_latest as
select d.*
from public.naver_clip_report_daily_rows d
join (
  select run_id
  from   public.naver_clip_report_runs
  where  status = 'success'
  order  by checked_at desc
  limit  1
) latest on latest.run_id = d.run_id;

create or replace view public.v_naver_clip_report_daily_history as
select
  d.*,
  r.status        as run_status,
  r.triggered_by,
  r.finished_at,
  extract(year from d.checked_at at time zone 'Asia/Seoul')::integer as checked_year,
  (d.checked_at at time zone 'Asia/Seoul')::date                     as checked_date_kst
from public.naver_clip_report_daily_rows d
join public.naver_clip_report_runs       r on r.run_id = d.run_id;

-- =============================================================================
-- 섹션 6. 함수
-- =============================================================================

-- 연간 클립 집계 갱신
create or replace function public.refresh_naver_clip_report_year(target_year integer)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  delete from public.naver_clip_report_yearly_summary
  where year = target_year;

  insert into public.naver_clip_report_yearly_summary (
    year, rights_holder_name, work_title, identifier,
    clip_count, total_views, max_view_count,
    first_checked_at, latest_checked_at, updated_at
  )
  select
    extract(year from checked_at at time zone 'Asia/Seoul')::integer,
    coalesce(rights_holder_name, ''),
    coalesce(work_title, ''),
    coalesce(identifier, ''),
    count(*),
    sum(view_count),
    max(view_count),
    min(checked_at),
    max(checked_at),
    now()
  from public.naver_clip_report_daily_rows
  where extract(year from checked_at at time zone 'Asia/Seoul')::integer = target_year
  group by 1, 2, 3, 4;
end;
$$;

-- 신규 유저 가입 시 user_profiles 자동 생성
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public
as $$
begin
  insert into public.user_profiles (user_id, email)
  values (new.id, new.email);
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- =============================================================================
-- 섹션 7. Row Level Security (RLS)
-- =============================================================================

-- user_roles
alter table public.user_roles enable row level security;
create policy "본인 역할 조회"         on public.user_roles for select using (auth.uid() = user_id);
create policy "admin 전체 조회"        on public.user_roles for select using (
  exists (select 1 from public.user_roles ur where ur.user_id = auth.uid() and ur.role = 'admin')
);

-- user_profiles
alter table public.user_profiles enable row level security;
create policy "본인 프로필 조회"       on public.user_profiles for select using (auth.uid() = user_id);
create policy "본인 프로필 수정"       on public.user_profiles for update using (auth.uid() = user_id);
create policy "admin 전체 프로필 조회" on public.user_profiles for select using (
  exists (select 1 from public.user_roles ur where ur.user_id = auth.uid() and ur.role = 'admin')
);

-- creator_channel_applications
alter table public.creator_channel_applications enable row level security;
create policy "admin 채널승인 전체 관리" on public.creator_channel_applications for all using (
  exists (select 1 from public.user_roles ur where ur.user_id = auth.uid() and ur.role = 'admin')
);

-- work_usage_requests
alter table public.work_usage_requests enable row level security;
create policy "본인 작품신청 조회"       on public.work_usage_requests for select using (auth.uid() = creator_id);
create policy "admin 작품신청 전체 관리" on public.work_usage_requests for all using (
  exists (select 1 from public.user_roles ur where ur.user_id = auth.uid() and ur.role = 'admin')
);

-- creator_channel_monthly_stats
alter table public.creator_channel_monthly_stats enable row level security;
create policy "본인 성과 조회"       on public.creator_channel_monthly_stats for select using (auth.uid() = creator_id);
create policy "admin 성과 전체 관리" on public.creator_channel_monthly_stats for all using (
  exists (select 1 from public.user_roles ur where ur.user_id = auth.uid() and ur.role = 'admin')
);

-- lead_channels
alter table public.lead_channels enable row level security;
create policy "admin 리드 전체 관리" on public.lead_channels for all using (
  exists (select 1 from public.user_roles ur where ur.user_id = auth.uid() and ur.role = 'admin')
);

-- lead_email_deliveries
alter table public.lead_email_deliveries enable row level security;
create policy "admin 이메일로그 전체 관리" on public.lead_email_deliveries for all using (
  exists (select 1 from public.user_roles ur where ur.user_id = auth.uid() and ur.role = 'admin')
);

-- automation_runs
alter table public.automation_runs enable row level security;
create policy "admin 실행로그 전체 관리" on public.automation_runs for all using (
  exists (select 1 from public.user_roles ur where ur.user_id = auth.uid() and ur.role = 'admin')
);

-- automation_agent_traces, automation_approvals, automation_tool_invocations
alter table public.automation_agent_traces      enable row level security;
alter table public.automation_approvals         enable row level security;
alter table public.automation_tool_invocations  enable row level security;

create policy "service_role_all_automation_agent_traces"
  on public.automation_agent_traces      for all to service_role using (true) with check (true);
create policy "service_role_all_automation_approvals"
  on public.automation_approvals         for all to service_role using (true) with check (true);
create policy "service_role_all_automation_tool_invocations"
  on public.automation_tool_invocations  for all to service_role using (true) with check (true);
