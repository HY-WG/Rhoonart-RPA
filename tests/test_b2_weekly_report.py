from __future__ import annotations

from datetime import datetime, timezone

from src.core.crawlers.naver_clip_crawler import ClipStat, NaverClipHashtagStat
from src.handlers import b2_weekly_report
from src.models import ContentCatalogItem
from tests.fakes import FakeLogRepo, FakeNotifier, FakePerformanceRepo, FakeRightsHolder


def _fake_stats() -> list[NaverClipHashtagStat]:
    return [
        NaverClipHashtagStat(
            identifier="uucO0",
            content_name="베팅 온 팩트",
            total_views=100,
            clip_count=1,
            weekly_views=10,
            new_clips_this_week=1,
            total_likes=3,
            clips=[
                ClipStat(
                    media_id="m1",
                    profile_id="profile-1",
                    nickname="채널 1",
                    title="클립 1",
                    video_url="https://clip.naver.com/contents/1",
                    published_time=datetime(2026, 4, 29, tzinfo=timezone.utc),
                    views=100,
                    likes=3,
                    comments=1,
                )
            ],
        )
    ]


def test_b2_uses_clip_level_reports_and_sends_mail(monkeypatch) -> None:
    class FakeCrawler:
        def __init__(self, contents, **kwargs):
            self.contents = contents

        def crawl_stats(self):
            return _fake_stats()

        def run(self):  # pragma: no cover
            raise AssertionError("legacy run() should not be used")

    monkeypatch.setattr(b2_weekly_report, "NaverClipCrawler", FakeCrawler)
    perf_repo = FakePerformanceRepo(
        catalog=[
            ContentCatalogItem(
                identifier="uucO0",
                content_name="베팅 온 팩트",
                rights_holder_name="웨이브",
            )
        ],
        rights_holders=[
            FakeRightsHolder(
                holder_id="1",
                name="웨이브",
                email="holder@example.com",
                dashboard_url="https://looker.example.com/a",
            )
        ],
    )
    email_notifier = FakeNotifier(send_result=True)
    slack_notifier = FakeNotifier(send_result=True)

    result = b2_weekly_report.run(
        perf_repo=perf_repo,
        log_repo=FakeLogRepo(),
        email_notifier=email_notifier,
        slack_notifier=slack_notifier,
    )

    assert result["crawled"] == 1
    assert result["updated"] == 1
    assert result["notified"] == 1
    assert result["send_notifications"] is True
    assert len(perf_repo.upserted_stats) == 1
    assert len(perf_repo.replaced_reports) == 1
    assert result["sample_reports"][0]["영상URL"] == "https://clip.naver.com/contents/1"
    assert result["sample_reports"][0]["작품"] == "베팅 온 팩트"
    assert result["sample_reports"][0]["채널명"] == "채널 1"


def test_b2_can_skip_email_notifications(monkeypatch) -> None:
    class FakeCrawler:
        def __init__(self, contents, **kwargs):
            self.contents = contents

        def crawl_stats(self):
            return _fake_stats()

    monkeypatch.setattr(b2_weekly_report, "NaverClipCrawler", FakeCrawler)
    perf_repo = FakePerformanceRepo(
        catalog=[
            ContentCatalogItem(
                identifier="uucO0",
                content_name="베팅 온 팩트",
                rights_holder_name="웨이브",
            )
        ],
        rights_holders=[
            FakeRightsHolder(
                holder_id="1",
                name="웨이브",
                email="holder@example.com",
                dashboard_url="https://looker.example.com/a",
            )
        ],
    )
    email_notifier = FakeNotifier(send_result=True)
    slack_notifier = FakeNotifier(send_result=True)

    result = b2_weekly_report.run(
        perf_repo=perf_repo,
        log_repo=FakeLogRepo(),
        email_notifier=email_notifier,
        slack_notifier=slack_notifier,
        send_notifications=False,
    )

    assert result["crawled"] == 1
    assert result["updated"] == 1
    assert result["notified"] == 0
    assert result["send_notifications"] is False
    assert email_notifier.sent == []
    assert result["sample_reports"][0]["플랫폼"] == "naver_clip"
