# B-2 clip reports daily/year history design

## Decisions

1. Create a production table, `b2_clip_reports_daily`, instead of keeping history
   in `b2_clip_reports_test`.
2. Store every clip row on every daily run, even if `view_count` did not change.
3. Use a single `checked_at` timestamp for the execution/report reference time.
   There is no separate `collected_at`.
4. Backfill the 2026-04-30 test crawl as one run.
5. Support both Looker Studio entry points:
   - latest snapshot view for the default dashboard
   - full history view/table for date filters, trend analysis, and cumulative data

## Tables

### `b2_clip_report_runs`

One row per crawl/report execution.

Important columns:
- `run_id`
- `checked_at`
- `status`
- `triggered_by`
- `target_identifier_count`
- `row_count`
- `error_message`

### `b2_clip_reports_daily`

Append-only daily fact table. Each daily run inserts all collected clips again,
including unchanged clips.

Important columns:
- `run_id`
- `checked_at`
- `identifier`
- `work_title`
- `rights_holder_name`
- `video_url`
- `view_count`
- mapping columns: `content_catalog_id`, `rights_holder_id`

Unique key:
- `(run_id, identifier, video_url)`

### `b2_clip_reports_year`

Annual aggregate table maintained from `b2_clip_reports_daily` through
`refresh_b2_clip_reports_year(target_year integer)`.

Primary key:
- `(year, rights_holder_name, work_title, identifier)`

## Looker Studio sources

Default/latest dashboard:
- `v_b2_clip_reports_daily_latest`

History/trend dashboard:
- `v_b2_clip_reports_daily_history`
- or direct `b2_clip_reports_daily`

Annual management:
- `b2_clip_reports_year`

## Migration

Apply:

```text
migrations/003_b2_clip_reports_daily_history.sql
```

This migration creates the new daily/year tables, indexes, latest/history views,
the yearly refresh function, and backfills the 2026-04-30 data from
`b2_clip_reports_test`.
