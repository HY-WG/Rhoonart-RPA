-- Migration 010: work_requests 컬럼 확장 + Slack upsert용 unique 인덱스
-- 실행: Supabase Dashboard > SQL Editor

begin;

-- A-2 처리 시 채널명·이메일을 직접 저장 (creator_id FK 없이도 조회 가능)
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
