from __future__ import annotations

import time
from datetime import date, datetime

import pytz

from ..core.crawlers.naver_clip_crawler import NaverClipCrawler, NaverClipHashtagStat
from ..core.interfaces.notifier import INotifier
from ..core.interfaces.repository import ILogRepository, IPerformanceRepository
from ..core.logger import CoreLogger
from ..models.performance import ChannelStat, ClipReport, ContentCatalogItem

KST = pytz.timezone("Asia/Seoul")
log = CoreLogger(__name__)

TASK_ID = "B-2"
TASK_NAME = "네이버 클립 성과보고"


def run(
    perf_repo: IPerformanceRepository,
    log_repo: ILogRepository,
    email_notifier: INotifier,
    slack_notifier: INotifier,
    headless: bool = True,
    send_notifications: bool = True,
) -> dict:
    """Run B-2 Naver Clip crawling and reporting."""
    del headless
    started_at = datetime.now(KST)
    started_perf = time.perf_counter()

    catalog = perf_repo.get_content_catalog()
    if not catalog:
        log.warning("[B-2] 대상 작품이 없습니다.")
        return {
            "crawled": 0,
            "updated": 0,
            "notified": 0,
            "crawl_seconds": 0.0,
            "elapsed_seconds": 0.0,
            "send_notifications": send_notifications,
            "sample_reports": [],
        }

    contents = [(item.identifier, item.content_name) for item in catalog if item.identifier]
    if not contents:
        raise RuntimeError("[B-2] 선택된 작품에 식별코드가 없습니다.")

    total_contents = len(contents)
    log.info("[B-2] 크롤링 대상 %d개 작품", total_contents)

    def _on_crawl_progress(completed: int, total: int) -> None:
        log.info("[B-2] 데이터 %d/%d개 수집 완료", completed, total)

    crawler = _build_crawler(contents=contents, on_progress=_on_crawl_progress)
    stats = crawler.crawl_stats() if hasattr(crawler, "crawl_stats") else []
    if not stats:
        raw_stats = crawler.crawl()
        stats = _coerce_legacy_stats(raw_stats)

    crawl_seconds = round(time.perf_counter() - started_perf, 3)
    log.info("[B-2] 크롤링 완료 - %.3f초 소요", crawl_seconds)

    if not stats:
        raise RuntimeError("[B-2] 크롤링 결과가 없습니다.")

    channel_stats = [_to_channel_stat(stat) for stat in stats]
    perf_repo.upsert_channel_stats(channel_stats)

    reports = _build_clip_reports(stats=stats, catalog=catalog, checked_at=started_at.date())
    updated_count = perf_repo.replace_clip_reports(reports)

    rights_holders = perf_repo.get_rights_holders()
    notified_count = 0
    if send_notifications:
        for holder in rights_holders:
            if not holder.email or not holder.dashboard_url:
                continue
            body = _build_email_body(holder.name, holder.dashboard_url, started_at)
            success = email_notifier.send(
                recipient=holder.email,
                message=body,
                subject=f"[르호안아트] {started_at.strftime('%Y-%m-%d')} 네이버 클립 성과 보고",
                html=True,
            )
            if success:
                notified_count += 1
                log.info("[B-2] 발송 완료: %s (%s)", holder.name, holder.email)
            else:
                log.error("[B-2] 발송 실패: %s (%s)", holder.name, holder.email)
                slack_notifier.send_error(
                    TASK_ID,
                    RuntimeError(f"권리사 {holder.name} ({holder.email}) 메일 발송 실패"),
                )
    else:
        log.info("[B-2] 메일 발송은 생략하고 크롤링+시트 업데이트까지만 수행했습니다.")

    result = {
        "crawled": len(stats),
        "updated": updated_count,
        "notified": notified_count,
        "total_rights_holders": len(rights_holders),
        "crawl_seconds": crawl_seconds,
        "elapsed_seconds": round(time.perf_counter() - started_perf, 3),
        "send_notifications": send_notifications,
        "sample_reports": [
            {
                "영상URL": report.video_url,
                "영상업로드일": report.uploaded_at.isoformat() if report.uploaded_at else "",
                "채널명": report.channel_name,
                "조회수": report.view_count,
                "데이터확인일": report.checked_at.isoformat(),
                "제목": report.clip_title,
                "작품": report.work_title,
                "플랫폼": report.platform,
                "권리사": report.rights_holder_name or "",
            }
            for report in reports[:3]
        ],
    }
    log.info("[B-2] 완료: %s", result)
    return result


def _build_crawler(contents: list[tuple[str, str]], on_progress) -> NaverClipCrawler:
    try:
        return NaverClipCrawler(
            contents=contents,
            use_parallel=True,
            max_workers=4,
            on_progress=on_progress,
        )
    except TypeError:
        return NaverClipCrawler(contents=contents)


def _coerce_legacy_stats(raw_stats: list[dict]) -> list[NaverClipHashtagStat]:
    coerced: list[NaverClipHashtagStat] = []
    for row in raw_stats:
        coerced.append(
            NaverClipHashtagStat(
                identifier=row["channel_id"],
                content_name=row["channel_name"],
                total_views=int(row.get("total_views") or 0),
                clip_count=int(row.get("video_count") or 0),
                weekly_views=int(row.get("weekly_views") or 0),
                new_clips_this_week=int(row.get("new_clips_week") or 0),
                total_likes=int(row.get("total_likes") or 0),
                clips=[],
            )
        )
    return coerced


def _to_channel_stat(stat: NaverClipHashtagStat) -> ChannelStat:
    return ChannelStat(
        channel_id=stat.identifier,
        channel_name=stat.content_name,
        platform="naver_clip",
        total_views=stat.total_views,
        weekly_views=stat.weekly_views,
        video_count=stat.clip_count,
        crawled_at=datetime.now(KST),
    )


def _build_clip_reports(
    *,
    stats: list[NaverClipHashtagStat],
    catalog: list[ContentCatalogItem],
    checked_at: date,
) -> list[ClipReport]:
    rights_by_identifier = {
        item.identifier: item.rights_holder_name or ""
        for item in catalog
        if item.identifier
    }
    reports: list[ClipReport] = []
    for stat in stats:
        for clip in stat.clips:
            reports.append(
                ClipReport(
                    video_url=clip.video_url,
                    uploaded_at=clip.published_time.date() if clip.published_time else None,
                    channel_name=clip.nickname or clip.profile_id,
                    view_count=clip.views,
                    checked_at=checked_at,
                    clip_title=clip.title,
                    work_title=stat.content_name,
                    platform="naver_clip",
                    rights_holder_name=rights_by_identifier.get(stat.identifier) or None,
                    identifier=stat.identifier,
                )
            )
    return reports


def _build_email_body(holder_name: str, dashboard_url: str, report_date: datetime) -> str:
    date_label = report_date.strftime("%Y-%m-%d")
    return f"""
<html><body style="font-family: sans-serif; color: #333;">
<p>안녕하세요, {holder_name} 담당자님.</p>
<p>르호안아트입니다.<br>
{date_label} 기준 <strong>네이버 클립 성과 보고</strong>를 전달드립니다.</p>

<p style="margin: 24px 0;">
  <a href="{dashboard_url}"
     style="background:#4285F4;color:#fff;padding:12px 24px;border-radius:4px;text-decoration:none;font-weight:bold;">
    Looker Studio 대시보드 보기
  </a>
</p>

<p style="font-size:13px;color:#888;">
  본 메일은 자동 발송되었습니다.<br>
  문의 사항이 있으시면 르호안아트 담당자에게 연락 주세요.
</p>
</body></html>
""".strip()
