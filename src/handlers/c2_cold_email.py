"""C-2. 콜드메일 발송 핸들러.

리드 시트에서 미발송 리드를 조회하여 채널명·장르 기반 개인화 메일을 발송한다.
발송 결과(발송완료 / 반송)를 리드 시트에 즉시 업데이트한다.

발송 전략:
  - 이메일 주소가 없는 리드는 건너뜀 (skip_no_email)
  - 발송 성공 → EmailSentStatus.SENT
  - 발송 실패 → EmailSentStatus.BOUNCED (재시도 대상)
  - batch_size: 1회 실행당 최대 발송 수 (기본 50)
"""
from dataclasses import dataclass
from typing import Optional

from ..core.interfaces.repository import ILeadRepository, ILogRepository
from ..core.interfaces.notifier import INotifier
from ..core.logger import CoreLogger
from ..models.lead import Lead, LeadFilter, Genre, EmailSentStatus

log = CoreLogger(__name__)

TASK_ID   = "C-2"
TASK_NAME = "콜드메일 발송"


@dataclass
class SendResult:
    sent: int = 0
    bounced: int = 0
    skipped_no_email: int = 0
    skipped_by_filter: int = 0

    def to_dict(self) -> dict:
        return {
            "sent": self.sent,
            "bounced": self.bounced,
            "skipped_no_email": self.skipped_no_email,
            "skipped_by_filter": self.skipped_by_filter,
        }


def run(
    lead_repo: ILeadRepository,
    log_repo: ILogRepository,
    email_notifier: INotifier,
    slack_notifier: INotifier,
    sender_name: str = "루나트",
    batch_size: int = 50,
    genre: Optional[Genre] = None,
    min_monthly_views: int = 0,
    platform: Optional[str] = None,
) -> dict:
    """C-2 실행.

    Args:
        sender_name: 발신자 이름 (메일 본문에 표시)
        batch_size: 1회 실행당 최대 발송 수
        genre: 특정 장르만 발송 (None이면 전체)
        min_monthly_views: 최소 월간 조회수 필터
        platform: 특정 플랫폼만 발송 (None이면 전체)
    Returns:
        {"sent": int, "bounced": int, "skipped_no_email": int, "skipped_by_filter": int}
    """
    filters = LeadFilter(
        genre=genre,
        min_monthly_views=min_monthly_views,
        email_sent_status=EmailSentStatus.NOT_SENT,
        platform=platform,
    )
    candidates = lead_repo.get_leads_for_email(filters)
    log.info("[C-2] 발송 대상 후보: %d건 (batch_size=%d)", len(candidates), batch_size)

    result = SendResult(skipped_by_filter=max(0, len(candidates) - batch_size))
    targets = candidates[:batch_size]

    for lead in targets:
        if not lead.email:
            result.skipped_no_email += 1
            log.debug("[C-2] 이메일 없음, 건너뜀: %s", lead.channel_name)
            continue

        subject = _build_subject(lead)
        body    = _build_body(lead, sender_name)

        success = email_notifier.send(
            recipient=lead.email,
            message=body,
            subject=subject,
            html=True,
        )

        if success:
            result.sent += 1
            lead_repo.update_lead_email_status(lead.channel_id, EmailSentStatus.SENT.value)
            log.info("[C-2] 발송 완료 → %s (%s)", lead.channel_name, lead.email)
        else:
            result.bounced += 1
            lead_repo.update_lead_email_status(lead.channel_id, EmailSentStatus.BOUNCED.value)
            log.warning("[C-2] 발송 실패 → %s (%s)", lead.channel_name, lead.email)

    log.info(
        "[C-2] 완료 — 발송: %d, 실패: %d, 이메일없음: %d, 배치초과: %d",
        result.sent, result.bounced, result.skipped_no_email, result.skipped_by_filter,
    )
    return result.to_dict()


# ── 메일 빌더 ─────────────────────────────────────────

def _build_subject(lead: Lead) -> str:
    return f"[루나트] {lead.channel_name} 채널 제휴 제안드립니다"


def _build_body(lead: Lead, sender_name: str) -> str:
    subscribers_line = (
        f"<li>구독자 수: <strong>{lead.subscribers:,}명</strong></li>"
        if lead.subscribers else ""
    )
    views_line = (
        f"<li>월간 숏츠 조회수: <strong>{lead.monthly_shorts_views:,}회</strong></li>"
        if lead.monthly_shorts_views else ""
    )

    return f"""
<html>
<body style="font-family:sans-serif;color:#333;line-height:1.6;max-width:600px;">
<p>안녕하세요, <strong>{lead.channel_name}</strong> 채널 담당자님.</p>

<p>저는 <strong>{sender_name}</strong>에서 크리에이터 파트너십을 담당하고 있습니다.<br>
귀 채널의 콘텐츠를 인상 깊게 살펴보았으며, 함께 성장할 수 있는 기회를 제안드리고자 연락드렸습니다.</p>

<h3 style="color:#1a73e8;">제안 내용</h3>
<p>{sender_name}는 유튜브 채널의 수익화 및 성장을 지원하는 MCN으로,<br>
콘텐츠 기획·배포·저작권 관리·광고 수익화 등 다양한 분야에서 파트너 채널을 지원하고 있습니다.</p>

<h3 style="color:#1a73e8;">채널 정보</h3>
<ul>
  <li>채널명: <strong>{lead.channel_name}</strong></li>
  <li>장르: <strong>{lead.genre.value}</strong></li>
  {subscribers_line}
  {views_line}
</ul>

<p>관심이 있으시다면 이 메일로 회신 주시거나,<br>
아래 링크를 통해 파트너십 신청서를 작성해 주시면 담당자가 빠르게 연락드리겠습니다.</p>

<p>
  <a href="{lead.channel_url}" style="color:#1a73e8;">채널 바로가기</a>
</p>

<p>바쁘신 중에 읽어주셔서 감사합니다.<br>
궁금하신 점은 언제든지 회신 주세요!</p>

<p>감사합니다.<br>
<strong>{sender_name}</strong> 파트너십 팀 드림</p>

<hr style="border:none;border-top:1px solid #eee;margin-top:32px;">
<p style="font-size:11px;color:#999;">
  본 메일은 공개된 채널 정보를 기반으로 발송되었습니다.<br>
  수신을 원하지 않으시면 회신으로 수신 거부 의사를 알려주세요.
</p>
</body>
</html>
""".strip()
