-- Migration 020: Portal revenue settlement, lead discovery detail logs, works metadata
-- 실행: Supabase Dashboard > SQL Editor

begin;

create table if not exists public.naver_revenue_settlements (
  id uuid primary key default gen_random_uuid(),
  portal_user_email text,
  name text not null,
  channel_name text not null,
  revenue_month text not null,
  monthly_revenue numeric(14, 2) not null default 0,
  screenshot_file_path text,
  screenshot_file_name text,
  screenshot_content_type text,
  screenshot_file_size bigint,
  status text not null default 'submitted',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_naver_revenue_settlements_month
  on public.naver_revenue_settlements (revenue_month, created_at desc);

create index if not exists idx_naver_revenue_settlements_channel
  on public.naver_revenue_settlements (channel_name);

alter table if exists public.naver_revenue_settlements
  add column if not exists settlement_key text;

update public.naver_revenue_settlements
set settlement_key = concat_ws(
  ':',
  coalesce(nullif(portal_user_email, ''), 'anonymous'),
  coalesce(nullif(name, ''), 'unknown-name'),
  coalesce(nullif(channel_name, ''), 'unknown-channel'),
  coalesce(nullif(revenue_month, ''), 'unknown-month')
)
where settlement_key is null;

create unique index if not exists naver_revenue_settlements_key_uidx
  on public.naver_revenue_settlements (settlement_key);

create table if not exists public.lead_discovery_runs (
  id uuid primary key default gen_random_uuid(),
  run_id text unique,
  task_id text not null default 'C-1',
  trigger_source text,
  status text not null default 'success',
  discovered_count integer not null default 0,
  upserted_count integer not null default 0,
  tier_a_count integer not null default 0,
  tier_b_count integer not null default 0,
  tier_b_potential_count integer not null default 0,
  tier_c_count integer not null default 0,
  excluded_count integer not null default 0,
  drama_titles jsonb not null default '[]'::jsonb,
  detail_log jsonb not null default '[]'::jsonb,
  result_json jsonb not null default '{}'::jsonb,
  started_at timestamptz,
  finished_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists idx_lead_discovery_runs_finished_at
  on public.lead_discovery_runs (finished_at desc);

alter table if exists public.works
  add column if not exists release_year integer,
  add column if not exists description text,
  add column if not exists director text,
  add column if not exists "cast" text,
  add column if not exists genre text,
  add column if not exists video_type text,
  add column if not exists country text,
  add column if not exists platforms text[],
  add column if not exists platform_video_url text,
  add column if not exists trailer_url text,
  add column if not exists thumbnail_url text,
  add column if not exists source_download_url text,
  add column if not exists updated_at timestamptz not null default now();

create index if not exists works_work_title_idx
  on public.works (work_title);

commit;
