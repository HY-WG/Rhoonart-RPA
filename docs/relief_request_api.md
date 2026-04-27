# Monetization Relief Backoffice API Draft

## Scope

This draft covers the first implementation phase:

- create a relief request
- list requests in the admin backoffice
- inspect request details
- send rights-holder email requests from a managed template

Future phases will add reply ingestion, document upload automation, and customer forwarding.

## Endpoints

### `GET /health`

Simple liveness probe.

Response:

```json
{
  "status": "ok"
}
```

### `POST /api/relief-requests`

Customer intake endpoint used by the future web service tab.

Request:

```json
{
  "requester_channel_name": "예시 채널",
  "requester_email": "creator@example.com",
  "requester_notes": "수익화 제한 해제 요청",
  "submitted_via": "web",
  "items": [
    {
      "work_id": "work-1",
      "work_title": "신병",
      "rights_holder_name": "Rights A",
      "channel_folder_name": "예시 채널"
    }
  ]
}
```

### `GET /api/admin/relief-requests`

List requests for the admin queue.

Query params:

- `status`: optional request status filter

### `GET /api/admin/relief-requests/{request_id}`

Return request summary, selected works, and outbound mail history.

### `POST /api/admin/relief-requests/{request_id}/send-mails`

Send one rights-holder email per resolved holder contact.

Request:

```json
{
  "template_key": "rights_holder_request"
}
```

Response:

```json
{
  "request_id": "relief-123456789abc",
  "attempted": 2,
  "sent": 2,
  "failed": 0,
  "updated_status": "mail_sent"
}
```

## Status model

- `submitted`
- `pending`
- `mail_sent`
- `reply_received`
- `ready_to_forward`
- `forwarded`
- `completed`
- `rejected`

## Template variables

- `${request_id}`
- `${requester_channel_name}`
- `${requester_email}`
- `${requester_notes}`
- `${holder_name}`
- `${work_titles}`
- `${works_bullet_list}`

## Assumptions in this draft

- rights-holder recipient mapping is resolved from a separate directory keyed by work title
- one outbound email is sent per rights holder
- the future web app can pass selected work items in a normalized list
- reply ingestion and Drive upload automation will be implemented in a later phase
