# Integration Smoke Test Scenarios

These scenarios are the standard operating baseline for the browser dashboard at `/dashboard/`.

## Rules

- Use `dry_run` first for every task.
- Use `real_run` only after confirming payload, environment, and approval requirements.
- Tasks with external email or state changes require the approval checkbox before `real_run`.
- Record the run ID, result JSON, and any matching Google Sheets / Slack / email evidence.

## Task Matrix

| Task | Dry Run Goal | Real Run Goal | External Verification |
| --- | --- | --- | --- |
| A-2 | Validate Slack parsing and payload shape | Verify creator email lookup, Drive permission, approval email, Slack thread reply | Creator sheet row, Drive sharing change, inbox, Slack thread |
| A-3 | Force `confirm` path and verify Slack notification branch | Verify confirm or send flow with real monthly data | Slack channel, manager inbox, attachment |
| B-2 | Preview-only safety check | Verify crawler, aggregation, and report delivery | Performance sheet, rights-holder mail, Slack |
| C-1 | Preview-only safety check | Verify lead discovery and sheet upsert | Lead sheet, Slack log |
| C-2 | Preview-only safety check | Verify outbound cold mail send and lead status update | Lead sheet status, inbox, Slack |
| C-3 | Verify payload through native `dry_run` | Verify Admin API / Notion side effects | Admin API record, Notion page |
| C-4 | Validate coupon keyword detection | Verify coupon sheet append and Slack DM | Coupon sheet, Slack DM |
| D-2 | Preview request + rights-holder routing | Verify request creation and optional rights-holder mail send | D-2 list endpoint, outbound mail log |
| D-3 | Verify onboarding read/write plan without sheet writes | Verify new rows appended to final sheet | Kakao output sheet |

## Suggested Payloads

### A-2

```json
{
  "channel_name": "테스트 채널",
  "work_title": "테스트 작품",
  "slack_channel_id": "C_HTTP_TRIGGER",
  "slack_message_ts": "smoke-a2-0001"
}
```

### A-3

```json
{
  "mode": "confirm"
}
```

### B-2

```json
{
  "source": "dashboard"
}
```

### C-1

```json
{
  "_trigger_source": "dashboard"
}
```

### C-2

```json
{
  "batch_size": 5,
  "min_monthly_views": 0
}
```

### C-3

```json
{
  "work_title": "테스트 작품",
  "rights_holder_name": "테스트 권리사",
  "release_year": 2025,
  "description": "통합 테스트용 작품 등록",
  "director": "테스트 감독",
  "cast": "배우 A, 배우 B",
  "genre": "드라마",
  "video_type": "드라마",
  "country": "한국",
  "platforms": ["wavve"]
}
```

### C-4

```json
{
  "source": "slack",
  "creator_name": "테스트 크리에이터",
  "text": "수익 100% 쿠폰 요청합니다."
}
```

### D-2

```json
{
  "requester_channel_name": "테스트 채널",
  "requester_email": "creator@example.com",
  "requester_notes": "통합 테스트용 소명 요청",
  "auto_send_mails": false,
  "items": [
    {
      "work_id": "work-1",
      "work_title": "샘플 작품",
      "rights_holder_name": "Rights A",
      "channel_folder_name": "테스트 채널"
    }
  ]
}
```

### D-3

```json
{}
```

## Real-Run Checklist

1. Open `/dashboard/`.
2. Paste or confirm the payload.
3. Click `Dry Run` and confirm the result JSON is sane.
4. For risky tasks, tick `real-run 승인`.
5. Click `Real Run`.
6. Capture:
   - dashboard run ID
   - result JSON
   - external evidence link or screenshot
7. If a task fails, record the first failing external dependency and rerun only after correcting the environment.
