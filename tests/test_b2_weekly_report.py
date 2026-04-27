from __future__ import annotations

from src.handlers import b2_weekly_report
from tests.fakes import FakeLogRepo, FakeNotifier, FakePerformanceRepo, FakeRightsHolder


def test_b2_uses_http_crawler_interface(monkeypatch) -> None:
    class FakeCrawler:
        def __init__(self, contents):
            self.contents = contents

        def crawl(self):
            return [
                {
                    "channel_id": "tag-1",
                    "channel_name": "Content 1",
                    "platform": "naver_clip",
                    "total_views": 100,
                    "weekly_views": 10,
                    "video_count": 3,
                }
            ]

        def run(self):  # pragma: no cover
            raise AssertionError("legacy run() should not be used")

    monkeypatch.setattr(b2_weekly_report, "NaverClipCrawler", FakeCrawler)
    perf_repo = FakePerformanceRepo(
        contents=[("tag-1", "Content 1")],
        rights_holders=[
            FakeRightsHolder(
                holder_id="1",
                name="Holder A",
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
    assert len(perf_repo.upserted_stats) == 1
