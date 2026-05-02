-- Validation queries after running scripts/migrate_b2_to_view_stats.py

-- 1. Row counts: raw clip reports vs normalized daily snapshots
select
  (select count(*) from public.b2_clip_reports) as raw_clip_report_rows,
  (select count(*) from public.view_stats) as normalized_view_stats_rows;

-- 2. Distinct clip cardinality
select
  count(*) as clip_rows_in_normalized
from public.clips;

select
  count(distinct coalesce(video_url, clip_title || '|' || work_title || '|' || channel_name))
    as distinct_clips_in_raw
from public.b2_clip_reports;

-- 3. Distinct works cardinality
select
  (select count(*) from public.works) as normalized_works,
  (select count(distinct work_title) from public.b2_clip_reports where work_title is not null and work_title <> '')
    as raw_distinct_works;

-- 4. Distinct rights holders cardinality
select
  (select count(*) from public.rights_holders) as normalized_rights_holders,
  (select count(distinct rights_holder_name) from public.b2_clip_reports where rights_holder_name is not null and rights_holder_name <> '')
    as raw_distinct_rights_holders;

-- 5. Daily totals should match between raw table and normalized view
with raw_daily as (
  select
    checked_at::date as recorded_at,
    sum(view_count) as total_views
  from public.b2_clip_reports
  where checked_at is not null
  group by checked_at::date
),
normalized_daily as (
  select
    recorded_at,
    sum(view_count) as total_views
  from public.view_stats
  group by recorded_at
)
select
  coalesce(r.recorded_at, n.recorded_at) as recorded_at,
  r.total_views as raw_total_views,
  n.total_views as normalized_total_views,
  coalesce(r.total_views, 0) - coalesce(n.total_views, 0) as diff
from raw_daily r
full outer join normalized_daily n on n.recorded_at = r.recorded_at
order by recorded_at desc;

-- 6. Rights-holder totals should match
with raw_rights as (
  select
    rights_holder_name,
    sum(view_count) as total_views
  from public.b2_clip_reports
  group by rights_holder_name
),
normalized_rights as (
  select
    rights_holder_name,
    sum(view_count) as total_views
  from public.v_b2_clip_performance
  group by rights_holder_name
)
select
  coalesce(r.rights_holder_name, n.rights_holder_name) as rights_holder_name,
  r.total_views as raw_total_views,
  n.total_views as normalized_total_views,
  coalesce(r.total_views, 0) - coalesce(n.total_views, 0) as diff
from raw_rights r
full outer join normalized_rights n
  on n.rights_holder_name = r.rights_holder_name
order by rights_holder_name;

-- 7. Sample query pattern for dashboard filters
select *
from public.v_b2_clip_performance
where recorded_at between date '2026-04-01' and date '2026-04-30'
  and rights_holder_name = '웨이브'
order by recorded_at desc, view_count desc
limit 50;

-- 8. Sample query pattern for rights-holder Looker source
select *
from public.v_b2_daily_rights_holder_stats
where rights_holder_name = '웨이브'
order by recorded_at desc;
