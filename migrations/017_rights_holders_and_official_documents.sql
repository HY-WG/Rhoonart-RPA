-- Migration 017: rights_holders 테이블 및 공문/소명 워크플로우 전체 스키마
-- Migration 016(copyright_claim_documents)이 rights_holders FK에 의존하므로
-- 이 파일을 먼저 실행하거나 016과 통합하여 실행하세요.
-- 실행: Supabase Dashboard > SQL Editor

begin;

-- ── 1. rights_holders (계약 권리사 마스터) ────────────────────────────────────
create table if not exists public.rights_holders (
  id                 uuid primary key default gen_random_uuid(),
  rights_holder_name text not null,
  contact_email      text,
  contact_name       text,
  contract_status    text not null default 'active'
                       check (contract_status in ('active', 'inactive')),
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

create unique index if not exists idx_rights_holders_name
  on public.rights_holders (rights_holder_name);

-- ── 2. copyright_claims (저작권 소명 요청) ────────────────────────────────────
-- channel_id / work_id 는 기존 테이블 타입에 맞춰 FK 없이 선언합니다.
-- (channels.id = bigint, works.id = integer — UUID와 타입 불일치로 FK 제약 불가)
create table if not exists public.copyright_claims (
  id              uuid    primary key default gen_random_uuid(),
  channel_id      bigint,                                          -- soft ref → channels(id)
  work_id         integer,                                         -- soft ref → works(id)
  right_holder_id uuid    references public.rights_holders(id),
  due             date,
  requested_at    timestamptz not null default now(),
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

create index if not exists idx_copyright_claims_holder
  on public.copyright_claims (right_holder_id, requested_at desc);
create index if not exists idx_copyright_claims_work
  on public.copyright_claims (work_id);
create index if not exists idx_copyright_claims_channel
  on public.copyright_claims (channel_id);

-- ── 3. right_holder_status (소명 이력 추적) ─────────────────────────────────
create table if not exists public.right_holder_status (
  right_holder_id    uuid primary key references public.rights_holders(id),
  has_previous_claim boolean not null default false,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

-- ── 4. official_documents (관리자 작성 공문, 권리사별 1건) ────────────────────
create table if not exists public.official_documents (
  id              uuid not null primary key default gen_random_uuid(),
  right_holder_id uuid not null unique references public.rights_holders(id),
  content_body    jsonb not null default '{}'::jsonb,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

commit;
