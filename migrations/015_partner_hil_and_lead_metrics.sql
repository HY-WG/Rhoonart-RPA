-- Migration 015: Partner/HIL workflow and lead metric support
-- 실행: Supabase Dashboard > SQL Editor

begin;

alter table public.work_requests
  add column if not exists decision_note text,
  add column if not exists decided_by text,
  add column if not exists rejection_message text;

create index if not exists idx_work_requests_creator_email
  on public.work_requests (creator_email);

alter table public.lead_channels
  add column if not exists subscriber_count_previous bigint,
  add column if not exists subscriber_count_current bigint,
  add column if not exists subscriber_delta bigint,
  add column if not exists subscriber_refreshed_at timestamptz,
  add column if not exists discovery_query text,
  add column if not exists last_run_id text;

create table if not exists public.partner_guidelines (
  id uuid primary key default gen_random_uuid(),
  rights_holder_name text not null,
  work_title text not null,
  source_delivery_date date,
  upload_available_date date,
  work_guideline text,
  video_format_guideline text,
  allow_youtube boolean not null default true,
  allow_naver_clip boolean not null default false,
  allow_kakao_shortform boolean not null default false,
  provides_logo boolean not null default false,
  provides_subtitle boolean not null default false,
  requires_pre_review boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_partner_guidelines_holder_work
  on public.partner_guidelines (rights_holder_name, work_title);

commit;
