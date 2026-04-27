"""B-2. 주간 성과 보고 자동화 핸들러.

플로우:
1. 콘텐츠 관리 시트에서 (식별코드, 콘텐츠명) 목록 조회
2. 각 식별코드에 대해 https://clip.naver.com/hashtag/{식별코드} 크롤링
3. 성과 데이터 시트에 upsert
4. 권리사 목록 조회 → 각 권리사 이메일로 Looker Studio 대시보드 링크 발송
"""
from datetime import datetime
import pytz

from ..core.crawlers.naver_clip_crawler import NaverClipCrawler
from ..core.interfaces.repository import IPerformanceRepository, ILogRepository
from ..core.interfaces.notifier import INotifier
from ..core.logger import CoreLogger
from ..models.performance import ChannelStat

KST = pytz.timezone("Asia/Seoul")
log = CoreLogger(__name__)

TASK_ID = "B-2"
TASK_NAME = "주간 성과 보고 자동화"

def run(
    perf_repo: IPerformanceRepository,
    log_repo: ILogRepository,
    email_notifier: INotifier,
    slack_notifier: INotifier,
    headless: bool = True,
) -> dict:
    """B-2 주간 성과 보고 실행.

    Returns:
        {"crawled": int, "updated": int, "notified": int}
    """
    started_at = datetime.now(KST)

    # 1. 크롤링 대상 콘텐츠 목록 조회
    contents = perf_repo.get_content_list()
    if not contents:
        log.warning("[B-2] 콘텐츠 목록이 비어 있습니다. 시트 헤더(%s/%s)를 확인하세요.",
                    perf_repo.COL_IDENTIFIER, perf_repo.COL_CONTENT_NAME)
        return {"crawled": 0, "updated": 0, "notified": 0}

    log.info("[B-2] 크롤링 대상: %d개 콘텐츠", len(contents))

    # 2. 네이버 클립 해시태그 페이지 크롤링
    crawler = NaverClipCrawler(contents=contents)
    raw_stats = crawler.crawl()

    if not raw_stats:
        raise RuntimeError("크롤링 결과가 없습니다. 셀렉터 또는 네트워크 상태를 확인하세요.")

    # 3. 성과 시트 upsert
    channel_stats = [
        ChannelStat(
            channel_id=s["channel_id"],
            channel_name=s["channel_name"],
            platform=s["platform"],
            total_views=s.get("total_views"),
            weekly_views=s.get("weekly_views"),
            video_count=s.get("video_count"),
            subscribers=s.get("subscribers"),
            crawled_at=datetime.now(KST),
        )
        for s in raw_stats
    ]
    updated_count = perf_repo.upsert_channel_stats(channel_stats)
    log.info("[B-2] 성과 시트 업데이트: %d건", updated_count)

    # 4. 권리사별 대시보드 링크 발송
    rights_holders = perf_repo.get_rights_holders()
    notified_count = 0

    for holder in rights_holders:
        if not holder.email:
            continue
        dashboard_url = holder.dashboard_url
        if not dashboard_url:
            log.warning("[B-2] 권리사 %s 대시보드 URL 없음 — 발송 건너뜀", holder.name)
            continue

        body = _build_email_body(holder.name, dashboard_url, started_at)
        success = email_notifier.send(
            recipient=holder.email,
            message=body,
            subject=f"[루나트] {started_at.strftime('%Y년 %m월 %d일')} 주간 성과 보고",
            html=True,
        )
        if success:
            notified_count += 1
            log.info("[B-2] 발송 완료 → %s (%s)", holder.name, holder.email)
        else:
            log.error("[B-2] 발송 실패 → %s (%s)", holder.name, holder.email)
            slack_notifier.send_error(
                TASK_ID,
                RuntimeError(f"권리사 {holder.name} ({holder.email}) 발송 실패"),
            )

    result = {
        "crawled": len(raw_stats),
        "updated": updated_count,
        "notified": notified_count,
        "total_rights_holders": len(rights_holders),
    }
    log.info("[B-2] 완료: %s", result)
    return result


def _build_email_body(holder_name: str, dashboard_url: str, report_date: datetime) -> str:
    week_str = report_date.strftime("%Y년 %m월 %d일")
    return f"""
<html><body style="font-family: sans-serif; color: #333;">
<p>안녕하세요, {holder_name} 담당자님.</p>
<p>루나트입니다.<br>
{week_str} 기준 <strong>주간 성과 보고</strong>를 전달드립니다.</p>

<p style="margin: 24px 0;">
  <a href="{dashboard_url}"
     style="background:#4285F4;color:#fff;padding:12px 24px;border-radius:4px;text-decoration:none;font-weight:bold;">
    📊 Looker Studio 대시보드 보기
  </a>
</p>

<p style="font-size:13px;color:#888;">
  본 메일은 자동 발송되었습니다.<br>
  문의 사항이 있으시면 루나트 담당자에게 연락 주세요.
</p>
</body></html>
""".strip()
