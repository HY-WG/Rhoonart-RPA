-- Migration 010: work_requests 테이블 생성(없을 경우) + 컬럼 확장
-- 실행: Supabase Dashboard > SQL Editor

begin;

-- work_requests 테이블 생성 (없는 경우)
create table if not exists public.work_requests (
  id           uuid primary key default gen_random_uuid(),
  creator_id   uuid references auth.users(id) on delete set null,
  work_title   text not null,
  channel_name  text,
  creator_email text,
  status       text not null default 'pending'
                 check (status in ('pending', 'approved', 'rejected')),
  requested_at timestamptz default now(),
  processed_at timestamptz,
  drive_link   text,
  slack_ts     text
);

-- 이미 테이블이 있었다면 누락 컬럼만 추가
alter table public.work_requests
  add column if not exists channel_name   text;

alter table public.work_requests
  add column if not exists creator_email  text;

-- slack_ts unique 인덱스 (중복 upsert 방지)
create unique index if not exists idx_work_requests_slack_ts
  on public.work_requests (slack_ts)
  where slack_ts is not null;

-- 조회 성능 인덱스
create index if not exists idx_work_requests_status
  on public.work_requests (status);

create index if not exists idx_work_requests_requested_at
  on public.work_requests (requested_at desc);

commit;
