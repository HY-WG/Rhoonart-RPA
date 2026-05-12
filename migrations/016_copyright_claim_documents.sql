-- Migration 016: Copyright claim request and official document workflow
-- 실행: Supabase Dashboard > SQL Editor

begin;

create table if not exists public.copyright_claims (
  id bigserial primary key,
  channel_id bigint,
  channel_name text,
  work_id bigint references public.works(id),
  work_title text,
  right_holder_id bigint references public.rights_holders(id),
  requested_at timestamptz not null default now(),
  due date,
  completed boolean not null default false,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.copyright_claims
  add column if not exists channel_name text,
  add column if not exists work_title text,
  add column if not exists due date,
  add column if not exists completed boolean not null default false,
  add column if not exists completed_at timestamptz;

create index if not exists idx_copyright_claims_holder
  on public.copyright_claims (right_holder_id, completed, requested_at desc);

create index if not exists idx_copyright_claims_work
  on public.copyright_claims (work_id);

create index if not exists idx_copyright_claims_channel
  on public.copyright_claims (channel_id);

create index if not exists idx_copyright_claims_completed
  on public.copyright_claims (completed, requested_at desc);

create table if not exists public.right_holder_status (
  right_holder_id bigint primary key references public.rights_holders(id),
  has_previous_claim boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.official_documents (
  id uuid primary key default gen_random_uuid(),
  right_holder_id bigint not null unique references public.rights_holders(id),
  content_body jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

commit;
