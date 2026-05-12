-- Migration 019: 작품 단위 공문 저장
-- 실행: Supabase Dashboard > SQL Editor

begin;

alter table public.official_documents
  drop constraint if exists official_documents_right_holder_id_key,
  add column if not exists work_id bigint;

create unique index if not exists official_documents_holder_work_uidx
  on public.official_documents (right_holder_id, work_id);

create index if not exists idx_official_documents_work_id
  on public.official_documents (work_id);

commit;
