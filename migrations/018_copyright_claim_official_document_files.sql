-- Migration 018: Partner official document upload metadata
-- 실행: Supabase Dashboard > SQL Editor

begin;

alter table public.copyright_claims
  add column if not exists official_document_status text not null default 'not_requested',
  add column if not exists official_document_requested_at timestamptz,
  add column if not exists official_document_file_path text,
  add column if not exists official_document_file_name text,
  add column if not exists official_document_content_type text,
  add column if not exists official_document_file_size bigint,
  add column if not exists official_document_uploaded_at timestamptz;

create index if not exists idx_copyright_claims_document_status
  on public.copyright_claims (official_document_status, requested_at desc);

commit;
