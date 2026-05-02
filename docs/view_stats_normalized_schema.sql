-- Normalized schema for long-term B-2 analytics
-- Run in Supabase SQL Editor before executing the migration script.

create extension if not exists pg_trgm;

create table if not exists public.channels (
  id bigint generated always as identity primary key,
  channel_key text not null unique,
  channel_name text not null,
  platform text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists channels_name_idx
  on public.channels (channel_name);


create table if not exists public.rights_holders (
  id bigint generated always as identity primary key,
  rights_holder_key text not null unique,
  rights_holder_name text not null,
  manager_name text,
  email text,
  participation_channel_sheet_url text,
  review_form_url text,
  review_sheet_url text,
  naver_report_enabled boolean not null default false,
  looker_spreadsheet_url text,
  looker_studio_url text,
  update_cycle text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists rights_holders_name_idx
  on public.rights_holders (rights_holder_name);

create index if not exists rights_holders_enabled_idx
  on public.rights_holders (naver_report_enabled, rights_holder_name);


create table if not exists public.works (
  id bigint generated always as identity primary key,
  work_key text not null unique,
  identifier text,
  work_title text not null,
  rights_holder_id bigint references public.rights_holders(id) on delete set null,
  platform text,
  active_flag text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists works_title_idx
  on public.works (work_title);

create index if not exists works_identifier_idx
  on public.works (identifier);

create index if not exists works_rights_holder_idx
  on public.works (rights_holder_id, work_title);


create table if not exists public.clips (
  id bigint generated always as identity primary key,
  clip_key text not null unique,
  video_url text,
  clip_title text not null,
  channel_id bigint references public.channels(id) on delete cascade,
  work_id bigint references public.works(id) on delete cascade,
  uploaded_at date,
  platform text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists clips_work_idx
  on public.clips (work_id, uploaded_at desc);

create index if not exists clips_channel_idx
  on public.clips (channel_id, uploaded_at desc);

create index if not exists clips_title_trgm_idx
  on public.clips using gin (clip_title gin_trgm_ops);


create table if not exists public.view_stats (
  id bigint generated always as identity primary key,
  clip_id bigint not null references public.clips(id) on delete cascade,
  recorded_at date not null,
  view_count bigint not null default 0,
  created_at timestamptz not null default now(),
  unique (clip_id, recorded_at)
);

create index if not exists view_stats_clip_recorded_idx
  on public.view_stats (clip_id, recorded_at desc);

create index if not exists view_stats_recorded_at_idx
  on public.view_stats (recorded_at desc);


create or replace view public.v_b2_clip_performance as
select
  vs.id as view_stat_id,
  vs.recorded_at,
  vs.view_count,
  c.id as clip_id,
  c.clip_title,
  c.video_url,
  c.uploaded_at,
  ch.id as channel_id,
  ch.channel_name,
  ch.platform as channel_platform,
  w.id as work_id,
  w.identifier,
  w.work_title,
  rh.id as rights_holder_id,
  rh.rights_holder_name,
  rh.email as rights_holder_email,
  coalesce(c.platform, ch.platform, w.platform) as platform
from public.view_stats vs
join public.clips c on c.id = vs.clip_id
left join public.channels ch on ch.id = c.channel_id
left join public.works w on w.id = c.work_id
left join public.rights_holders rh on rh.id = w.rights_holder_id;


create or replace view public.v_b2_daily_work_stats as
select
  vs.recorded_at,
  w.id as work_id,
  w.identifier,
  w.work_title,
  rh.id as rights_holder_id,
  rh.rights_holder_name,
  count(distinct vs.clip_id) as clip_count,
  sum(vs.view_count) as total_views
from public.view_stats vs
join public.clips c on c.id = vs.clip_id
join public.works w on w.id = c.work_id
left join public.rights_holders rh on rh.id = w.rights_holder_id
group by
  vs.recorded_at,
  w.id,
  w.identifier,
  w.work_title,
  rh.id,
  rh.rights_holder_name;


create or replace view public.v_b2_daily_rights_holder_stats as
select
  vs.recorded_at,
  rh.id as rights_holder_id,
  rh.rights_holder_name,
  count(distinct c.id) as clip_count,
  count(distinct w.id) as work_count,
  count(distinct ch.id) as channel_count,
  sum(vs.view_count) as total_views
from public.view_stats vs
join public.clips c on c.id = vs.clip_id
left join public.channels ch on ch.id = c.channel_id
left join public.works w on w.id = c.work_id
left join public.rights_holders rh on rh.id = w.rights_holder_id
group by
  vs.recorded_at,
  rh.id,
  rh.rights_holder_name;
