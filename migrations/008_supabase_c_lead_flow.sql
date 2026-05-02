begin;

create table if not exists public.seed_channel (
  id uuid primary key default gen_random_uuid(),
  channel_id text,
  channel_name text,
  channel_url text not null,
  platform text not null default 'youtube',
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table if exists public.seed_channel
  add column if not exists channel_id text;

alter table if exists public.seed_channel
  add column if not exists channel_name text;

alter table if exists public.seed_channel
  add column if not exists channel_url text;

alter table if exists public.seed_channel
  add column if not exists platform text not null default 'youtube';

alter table if exists public.seed_channel
  add column if not exists active boolean not null default true;

alter table if exists public.seed_channel
  add column if not exists created_at timestamptz not null default now();

alter table if exists public.seed_channel
  add column if not exists updated_at timestamptz not null default now();

create unique index if not exists idx_seed_channel_url
  on public.seed_channel (channel_url);

create index if not exists idx_seed_channel_platform
  on public.seed_channel (platform, active);

alter table if exists public.lead_channels
  add column if not exists last_contacted_at timestamptz;

alter table if exists public.lead_channels
  add column if not exists last_updated_at timestamptz default now();

alter table if exists public.lead_channels
  drop constraint if exists leads_email_status_check;

alter table if exists public.lead_channels
  drop constraint if exists lead_channels_email_status_check;

alter table if exists public.lead_channels
  add constraint lead_channels_email_status_check
  check (email_status in ('unsent', 'sent', 'replied', 'bounced', 'blocked'));

commit;
