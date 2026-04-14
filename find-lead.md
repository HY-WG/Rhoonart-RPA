
# find-lead.md — YouTube Lead Extraction RPA

Specific CLAUDE.md configuration for automating YouTube channel and video data collection for lead generation.
Based on: company-wide.md

---

## 1. Project Overview

- **Business domain:** Sales & Marketing — Lead Generation
- **Target system:** YouTube Data API v3
- **Automation type:** API-based (primary), UI-based fallback for email scraping
- **Goal:** Extract qualified YouTube channel and video metadata to identify and score potential leads

---

## 2. Environment & Infrastructure

- **Runtime:** Python 3.10+
- **Primary API:** YouTube Data API v3 (`googleapis`)
- **API key storage:** Environment variable `YOUTUBE_API_KEY` — never hardcode
- **Output storage:** Local CSV / Google Sheets / database (define per deployment)
- **Quota awareness:** YouTube Data API has a daily quota limit (10,000 units/day by default)
  - `channels.list` costs 1 unit per call
  - `videos.list` costs 1 unit per call
  - Do NOT exceed quota — implement quota tracking and halt if approaching limit
- **Scheduler:** Run during off-peak hours to avoid rate limiting

---

## 3. Data Collection Scope

### Channel-Level Fields

| Field | API Resource | Notes |
|---|---|---|
| Channel ID | `id` | Unique identifier — primary key |
| Channel name (title) | `snippet.title` | |
| Description | `snippet.description` | Truncate if over 500 chars for storage |
| Custom URL | `snippet.customUrl` | May be null for small channels |
| Published date | `snippet.publishedAt` | ISO 8601 format |
| Country | `snippet.country` | May be null — handle gracefully |
| Subscriber count | `statistics.subscriberCount` | Hidden by some channels — log as null |
| Total view count | `statistics.viewCount` | |
| Video count | `statistics.videoCount` | |
| Thumbnail (default) | `snippet.thumbnails.default.url` | 88x88px |
| Thumbnail (medium) | `snippet.thumbnails.medium.url` | 240x240px |
| Thumbnail (high) | `snippet.thumbnails.high.url` | 800x800px |
| Banner image URL | `brandingSettings.image.bannerExternalUrl` | May be null |
| Channel keywords | `brandingSettings.channel.keywords` | Comma-separated string |
| Featured channel IDs | `brandingSettings.channel.featuredChannelsUrls` | Optional — for network mapping |

### Video-Level Fields

| Field | API Resource | Notes |
|---|---|---|
| Video ID | `id` | Unique identifier |
| Title | `snippet.title` | |
| Description | `snippet.description` | Truncate if over 1000 chars |
| Tags | `snippet.tags` | Array — join as pipe-separated string for CSV |
| Published date | `snippet.publishedAt` | ISO 8601 format |
| Duration | `contentDetails.duration` | ISO 8601 duration (e.g. PT4M13S) — convert to seconds |
| View count | `statistics.viewCount` | |
| Like count | `statistics.likeCount` | May be hidden — handle as null |
| Comment count | `statistics.commentCount` | May be disabled — handle as null |
| Thumbnail (default) | `snippet.thumbnails.default.url` | |
| Thumbnail (medium) | `snippet.thumbnails.medium.url` | |
| Thumbnail (high) | `snippet.thumbnails.high.url` | |
| Category ID | `snippet.categoryId` | Map to category name using category lookup |
| Live broadcast status | `snippet.liveBroadcastContent` | Values: `none`, `live`, `upcoming` |

### Email Address

- **Source:** Not available via YouTube API — must be scraped from:
  1. Channel description (regex pattern match)
  2. Channel `About` page (UI scraping fallback)
  3. Video descriptions (regex pattern match)
- **Regex pattern:** `[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}`
- **Deduplication:** Store only unique emails per channel
- **Flag:** Mark email source (`description` / `about_page` / `video_description`)

---

## 4. Automation Rules

- **In-scope:**
  - Channels matching defined search keywords or category filters
  - Videos from the last N days (configurable parameter)
- **Out-of-scope:**
  - Private or age-restricted videos
  - Channels with subscriber count below threshold (configurable, e.g. < 1,000)
- **Human-in-the-loop required:**
  - Final lead qualification and outreach — Claude must NOT send emails autonomously
  - Any channel flagged as sensitive content
- **Retry logic:**
  - Max 3 retries per API call with exponential backoff (1s, 2s, 4s)
  - On 403 quota exceeded: halt immediately, log, and alert operator
  - On 404 channel not found: skip and log, do not retry
- **Batch size:** Process channels in batches of 50 (API max per request)

---

## 5. Data Handling

- **Output format:** CSV (default), with option to write to Google Sheets or SQL
- **Output columns:** One row per channel; video data stored in a separate related table/sheet
- **Null handling:** Always write `null` explicitly — never leave fields blank
- **Deduplication:** Check Channel ID before inserting — skip if already exists
- **PII:** Email addresses are PII — store securely, do not log to console
- **Retention:** Raw API responses should not be stored longer than 30 days
- **Audit trail:** Log every channel processed with timestamp and status (success/skipped/failed)

---

## 6. Error Handling & Alerting

- **Quota exceeded (403):** Halt entire run, log remaining quota, send alert
- **Channel not found (404):** Skip and log channel ID, continue
- **Network timeout:** Retry up to 3 times, then skip and log
- **Invalid API key:** Halt immediately, alert operator — do not continue
- **Email regex no match:** Write `null` to email field — do not raise error
- **Alert channel:** Log file + optional Slack/email notification on run completion
- **Run summary:** At end of each run, output: total processed, total skipped, total failed, emails found, quota used

---

## 7. Security & Compliance

- API key stored in environment variable `YOUTUBE_API_KEY` — never in code or logs
- Email addresses must not be used for unsolicited bulk outreach (CAN-SPAM / GDPR)
- Collected data must only be accessed by authorized team members
- Do not scrape data in ways that violate YouTube Terms of Service
- Rate limit all requests — do not hammer the API in tight loops
- Log access to lead data (who exported, when)

---

## 8. Testing Standards

- **Unit tests:** Test regex email extractor with known patterns (valid, invalid, edge cases)
- **Mock API:** Use saved JSON fixtures for API responses in unit tests — do not call live API in tests
- **Integration test:** Run against a fixed list of known channel IDs and validate field completeness
- **Quota test:** Simulate 403 response and verify bot halts correctly
- **Null handling test:** Verify all nullable fields (country, subscriberCount, email) write `null` cleanly

---

## 9. Code Conventions

- One function per data type: `fetch_channel_data()`, `fetch_video_data()`, `extract_email()`
- All API parameters (quota limit, batch size, retry count, subscriber threshold) in a single `config.py` or `.env` — never inline
- Use `logging` module — not `print()` — with levels: INFO for progress, WARNING for skips, ERROR for failures
- Store output file path and name in config, not hardcoded
- Comment any regex pattern with explanation and example match

---

## Priority Reference (Derived from company-wide.md)

| Priority | Attribute | Why |
|---|---|---|
| High | API quota management | Exceeding quota halts all data collection |
| High | Null field handling | Many YouTube fields are optional — unhandled nulls crash the pipeline |
| High | Email as PII | Legal/compliance risk if mishandled |
| High | Human approval before outreach | Prevents unsolicited contact |
| Medium | Deduplication logic | Prevents duplicate leads in CRM |
| Medium | Retry + backoff | Network instability is common |
| Low | Thumbnail URL collection | Useful for UI but not critical for lead scoring |

---

*This file configures Claude for the find-lead RPA workflow. Review and update thresholds (subscriber count, date range, batch size) per campaign.*
