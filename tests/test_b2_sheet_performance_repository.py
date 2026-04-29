from __future__ import annotations

from datetime import date

from src.core.repositories.b2_sheet_performance_repository import B2SheetPerformanceRepository
from src.models import ClipReport
from tests.fakes import FakeWorksheet


def test_b2_repository_filters_identifiers_by_management_sheet_o_marker() -> None:
    content_ws = FakeWorksheet(
        headers=["식별코드", "작품명", "영상권리사"],
        rows=[
            ["uucO0", "베팅 온 팩트", "웨이브"],
            ["dXdF9", "강호동네서점", "쿠팡플레이"],
            ["NIvxu", "SNL 코리아 리부트 시즌8", "쿠팡플레이"],
        ],
    )
    management_ws = FakeWorksheet(
        headers=["영상저작권자", "이메일", "진행 중인 작품", "네이버 성과 보고 진행 여부", "Looker Studio"],
        rows=[
            ["웨이브", "a@example.com", "베팅 온 팩트", "O", "https://looker/a"],
            ["쿠팡플레이", "b@example.com", "강호동네서점", "", "https://looker/b"],
            ["쿠팡플레이", "b@example.com", "SNL 코리아 리부트 시즌8", "O", "https://looker/b"],
        ],
    )
    repo = B2SheetPerformanceRepository(
        content_ws=content_ws,
        stats_ws=FakeWorksheet(headers=["영상URL"], rows=[]),
        rights_ws=management_ws,
        management_ws=management_ws,
    )

    assert repo.get_content_list() == [
        ("uucO0", "베팅 온 팩트"),
        ("NIvxu", "SNL 코리아 리부트 시즌8"),
    ]


def test_b2_repository_dedupes_rights_holders_by_looker_url() -> None:
    content_ws = FakeWorksheet(headers=["식별코드", "작품명"], rows=[])
    management_ws = FakeWorksheet(
        headers=["영상저작권자", "이메일", "진행 중인 작품", "네이버 성과 보고 진행 여부", "Looker Studio"],
        rows=[
            ["웨이브", "a@example.com", "베팅 온 팩트", "O", "https://looker/a"],
            ["쿠팡플레이", "b@example.com", "강호동네서점", "O", "https://looker/b"],
            ["쿠팡플레이", "b@example.com", "SNL 코리아 리부트 시즌8", "O", "https://looker/b"],
        ],
    )
    repo = B2SheetPerformanceRepository(
        content_ws=content_ws,
        stats_ws=FakeWorksheet(headers=["영상URL"], rows=[]),
        rights_ws=management_ws,
        management_ws=management_ws,
    )

    holders = repo.get_rights_holders()
    assert [(holder.name, holder.dashboard_url) for holder in holders] == [
        ("웨이브", "https://looker/a"),
        ("쿠팡플레이", "https://looker/b"),
    ]


def test_b2_repository_replaces_clip_reports_with_sheet_shape() -> None:
    reports_ws = FakeWorksheet(headers=["old"], rows=[["stale"]])
    repo = B2SheetPerformanceRepository(
        content_ws=FakeWorksheet(headers=["식별코드", "작품명"], rows=[]),
        stats_ws=reports_ws,
        rights_ws=FakeWorksheet(headers=["이메일"], rows=[]),
    )

    count = repo.replace_clip_reports(
        [
            ClipReport(
                video_url="https://clip.naver.com/contents/1",
                uploaded_at=date(2026, 4, 29),
                channel_name="채널 1",
                view_count=123,
                checked_at=date(2026, 4, 29),
                clip_title="클립 1",
                work_title="베팅 온 팩트",
                platform="naver_clip",
                rights_holder_name="웨이브",
            )
        ]
    )

    assert count == 1
    assert reports_ws.updated_ranges[0][0] == "A1:I1"
    assert reports_ws.cleared_ranges == ["A2:I2"]
    assert reports_ws.appended[0][:4] == [
        "https://clip.naver.com/contents/1",
        "2026-04-29",
        "채널 1",
        123,
    ]
