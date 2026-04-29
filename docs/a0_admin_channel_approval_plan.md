# A-0 어드민 채널 승인 자동화 설계

## 목적

`CONFIG_ADMIN_EMAIL` 메일함으로 들어오는 `"YouTube 채널 액세스를 위한 초대"` 메일을 감지하고, 초대 수락 링크를 따라가 레이블리 관리자 승인 흐름으로 연결하는 자동화 초안을 정의한다.

## Input Gateway

- trigger type: `email`
- source: 관리자 메일함
- classification rule:
  - subject contains `"YouTube 채널 액세스를 위한 초대"`
  - optional sender heuristic contains `youtube`
- normalized intent: `approve_admin_channel_invite`

예시 envelope:

```json
{
  "task_id": "A-0",
  "trigger_type": "email",
  "trigger_source": "youtube-noreply@example.com",
  "dry_run": true,
  "context": {
    "recipient": "hoyoungy2@gmail.com",
    "subject": "YouTube 채널 액세스를 위한 초대",
    "accept_url": "https://accounts.google.com/...",
    "snippet": "채널 초대 수락"
  }
}
```

## Repository Pattern

- `IAdminInviteInboxRepository`
  - `list_pending_invites(admin_email, subject_query)`
  - `mark_processed(message_id)`

실제 구현은 추후 Gmail API / IMAP / SES inbound 저장소 중 하나로 교체한다. 현재는 fake repository로 테스트한다.

## Tool Registry 연계

기존 Tool Registry 패턴을 유지해, A-0은 아래 도구 체인으로 설계한다.

1. `poll_admin_invite_mailbox`
2. `open_invite_link_with_playwright`
3. `sign_in_labelly_admin`
4. `confirm_channel_access`

AI Agent는 Input Gateway가 만든 envelope를 읽고, 위 도구들을 순서대로 실행하는 ReAct 루프를 사용한다.

## Human-in-the-loop

반드시 승인받아야 하는 지점:

1. 메일 본문 검토 직후
2. 실제 초대 수락 링크 클릭 직전
3. 레이블리 최종 승인 직전

이유:

- 외부 계정 권한이 변경된다.
- 제3자 시스템의 실제 승인 액션이 발생한다.
- 잘못 수락하면 권한 오남용 또는 계정 혼선이 생길 수 있다.

## 실행 플로우

1. 메일함 폴링 또는 webhook으로 새 메일 감지
2. 제목 규칙으로 A-0 분류
3. `TaskEnvelope` 생성
4. 관리자 승인 대기
5. Playwright로 `accept_url` 오픈
6. 필요 시 Google/레이블리 로그인
7. 레이블리 관리자 페이지에서 최종 승인
8. 처리 완료 후 메일 레코드 `mark_processed`

## 테스트 전략

- `FakeMailNotifier`
  - 감지 사실 알림이 정상 발행되는지 검증
- `FakeInboxRepository`
  - 대상 메일만 선택되는지 검증
- planner 단위 테스트
  - `poll_and_plan(dry_run=True)` 호출 시 plan 1건 이상 생성
  - envelope가 `trigger_type=email`, `task_id=A-0`인지 검증
