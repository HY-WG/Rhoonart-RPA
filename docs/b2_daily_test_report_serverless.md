# B-2 daily test report serverless flow

## Goal

Every day at 10:00 KST, collect Naver Clip data for identifiers whose rights holder has
`naver_report_enabled = true`, save the rows into `public.b2_clip_reports_daily`,
create per-rights-holder Google Sheets, and email the report to
`kirby.lee@laeebly.com`.

## Data seed

The requested seed row is managed by `scripts/b2_test_report.py --seed`.

- `b2_content_catalog`
  - `content_name = 현상수배`
  - `identifier = 1UBvb`
  - `rights_holder_name = 이놀미디어`
- `b2_rights_holders`
  - `rights_holder_name = 이놀미디어`
  - `email = kirby.lee@laeebly.com`
  - `current_work_title = 현상수배`
  - `naver_report_enabled = true`
  - `update_cycle = daily 10:00 KST`

## Database migration

Apply these migrations once before enabling the schedule.
The Supabase REST API cannot create tables, so this must run through Supabase SQL
Editor, Supabase CLI migration, or another Postgres migration step.

1. `migrations/002_b2_clip_reports_test.sql`
2. `migrations/003_b2_clip_reports_daily_history.sql`

## Serverless schedule

`serverless.yml` defines `b2DailyTestReport`:

```yaml
events:
  - schedule:
      rate: cron(0 1 * * ? *)
      enabled: true
```

AWS EventBridge cron is UTC. `cron(0 1 * * ? *)` runs at 01:00 UTC, which is
10:00 KST.

## Runtime flow

1. Lambda `lambda/b2_test_report_handler.handler` starts at 10:00 KST.
2. It ensures the requested seed rows exist.
3. It reads enabled rights holders from `b2_rights_holders`.
4. It collects catalog rows whose `rights_holder_name` is enabled and has an identifier.
5. It crawls Naver Clip data for those identifiers.
6. It appends rows to `b2_clip_reports_daily` and records one row in
   `b2_clip_report_runs`.
7. It refreshes `b2_clip_reports_year` for the run year.
8. It updates a separate Google Sheet per rights holder and shares it with the recipient.
   - If `b2_rights_holders.looker_spreadsheet_url` exists, that spreadsheet is reused.
   - If it is empty, a new spreadsheet is created and its URL is saved back to
     `looker_spreadsheet_url`.
9. It sends an email with:
   - per-rights-holder Google Sheet links
   - existing Looker Studio links if stored in `b2_rights_holders.looker_studio_url`
   - an Excel attachment with the same report data

Looker Studio report creation is not automated here. The serverless job keeps a
stable Google Sheet per rights holder, so Looker Studio can be connected once to
that spreadsheet and then reused. Store the resulting report URL in
`b2_rights_holders.looker_studio_url`; the daily email will include it.

## Deployment requirements

The Lambda environment needs:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `GOOGLE_CREDENTIALS_FILE`
- `SENDER_EMAIL`
- `USE_SES`
- SES IAM permission `ses:SendRawEmail`, or SMTP settings if `USE_SES=false`

Deploy after applying the DB migration:

```powershell
npx serverless deploy --stage dev
```

## Manual dry run

Seed only:

```powershell
python scripts\b2_test_report.py --seed
```

After the daily history migration exists, collect and create Sheets without sending email:

```powershell
python scripts\b2_test_report.py --collect --create-sheets --share-sheets --max-clips 50
```

Send email manually only when explicitly approved:

```powershell
python scripts\b2_test_report.py --collect --create-sheets --share-sheets --send-email
```
