-- Migration 009: Human-in-the-Loop Lead Review + Supabase Blocklist
-- 실행: Supabase Dashboard > SQL Editor

begin;

-- 1. lead_channels: 리뷰 상태 컬럼 추가
alter table public.lead_channels
  add column if not exists review_status text not null default 'pending'
    check (review_status in ('pending', 'promoted', 'blocked'));

alter table public.lead_channels
  add column if not exists reviewed_at timestamptz;

alter table public.lead_channels
  add column if not exists reviewed_by text;

alter table public.lead_channels
  add column if not exists block_reason text;

create index if not exists idx_lead_channels_review_status
  on public.lead_channels (review_status);

-- 2. channel_blocklist: Supabase 영구 블록리스트 (JSON 파일 대체)
create table if not exists public.channel_blocklist (
  channel_id  text primary key,
  channel_name text,
  channel_url  text,
  platform     text not null default 'youtube',
  reason       text,
  blocked_at   timestamptz not null default now(),
  blocked_by   text not null default 'system'
);

create index if not exists idx_channel_blocklist_platform
  on public.channel_blocklist (platform);

-- 3. seed_channel: 누가 언제 승격했는지 추적
alter table public.seed_channel
  add column if not exists promoted_from_lead_id text;

alter table public.seed_channel
  add column if not exists promoted_by text;

alter table public.seed_channel
  add column if not exists promoted_at timestamptz;

commit;
