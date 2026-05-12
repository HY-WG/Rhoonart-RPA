-- Migration 017: Track copyright claim completion status
-- 실행: Supabase Dashboard > SQL Editor

begin;

alter table public.copyright_claims
  add column if not exists completed boolean not null default false,
  add column if not exists completed_at timestamptz;

create index if not exists idx_copyright_claims_completed
  on public.copyright_claims (completed, requested_at desc);

create index if not exists idx_copyright_claims_holder_completed
  on public.copyright_claims (right_holder_id, completed, requested_at desc);

commit;
