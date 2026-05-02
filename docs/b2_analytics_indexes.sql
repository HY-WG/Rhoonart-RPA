-- B-2 analytics indexing plan
-- Current fact table: public.b2_clip_reports
-- Future normalized fact table: public.view_stats

-- 1. Current-table indexes for the existing dashboard/admin filters
create index if not exists b2_clip_reports_checked_at_idx
  on public.b2_clip_reports (checked_at desc);

create index if not exists b2_clip_reports_uploaded_at_idx
  on public.b2_clip_reports (uploaded_at desc);

create index if not exists b2_clip_reports_rights_holder_checked_idx
  on public.b2_clip_reports (rights_holder_name, checked_at desc);

create index if not exists b2_clip_reports_work_checked_idx
  on public.b2_clip_reports (work_title, checked_at desc);

create index if not exists b2_clip_reports_channel_checked_idx
  on public.b2_clip_reports (channel_name, checked_at desc);

-- Optional: substring search acceleration for clip_title if data volume grows a lot.
-- Requires pg_trgm extension.
create extension if not exists pg_trgm;

create index if not exists b2_clip_reports_clip_title_trgm_idx
  on public.b2_clip_reports using gin (clip_title gin_trgm_ops);


-- 2. Recommended future normalized schema for long-term scale
-- Dimension tables:
--   clips(id, clip_key, video_url, clip_title, channel_id, work_id, platform, uploaded_at, ...)
--   channels(id, channel_name, ...)
--   works(id, work_title, rights_holder_id, ...)
--   rights_holders(id, rights_holder_name, ...)
--
-- Fact table:
--   view_stats(id, clip_id, recorded_at, view_count, ...)
--
-- The user-requested composite index:
create index if not exists view_stats_clip_recorded_idx
  on public.view_stats (clip_id, recorded_at desc);

-- Useful for period aggregation without clip filter:
create index if not exists view_stats_recorded_at_idx
  on public.view_stats (recorded_at desc);

-- If rights-holder dashboards become the main query pattern, materialized views or
-- pre-aggregated daily tables are recommended instead of piling more wide indexes
-- onto the raw fact table.
