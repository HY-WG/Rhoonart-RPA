-- Deduplicate legacy b2_clip_reports by video_url, then enforce uniqueness.
-- Keep the most recent row per video_url. Tie-breakers:
--   1. checked_at desc
--   2. view_count desc
--   3. id desc

with ranked as (
  select
    id,
    row_number() over (
      partition by video_url
      order by checked_at desc nulls last, view_count desc nulls last, id desc
    ) as rn
  from public.b2_clip_reports
  where video_url is not null
    and video_url <> ''
)
delete from public.b2_clip_reports target
using ranked
where target.id = ranked.id
  and ranked.rn > 1;

create unique index if not exists b2_clip_reports_video_url_uidx
  on public.b2_clip_reports (video_url)
  where video_url is not null and video_url <> '';

with ranked_daily as (
  select
    id,
    row_number() over (
      partition by run_id, video_url
      order by view_count desc nulls last, uploaded_at desc nulls last, id desc
    ) as rn
  from public.b2_clip_reports_daily
  where video_url is not null
    and video_url <> ''
)
delete from public.b2_clip_reports_daily target
using ranked_daily
where target.id = ranked_daily.id
  and ranked_daily.rn > 1;

drop index if exists public.b2_clip_reports_daily_run_video_uidx;

create unique index if not exists b2_clip_reports_daily_run_video_uidx
  on public.b2_clip_reports_daily (run_id, video_url)
  where video_url is not null and video_url <> '';
