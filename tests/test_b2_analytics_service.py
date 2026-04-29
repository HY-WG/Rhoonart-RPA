from datetime import date

from src.services import B2AnalyticsFilters, B2AnalyticsService


def _sample_rows() -> list[dict[str, object]]:
    return [
        {
            "video_url": "https://example.com/1",
            "uploaded_at": "2026-04-01",
            "channel_name": "채널 A",
            "view_count": 100,
            "checked_at": "2026-04-28",
            "clip_title": "클립 1",
            "work_title": "작품 A",
            "platform": "네이버 클립",
            "rights_holder_name": "웨이브",
        },
        {
            "video_url": "https://example.com/2",
            "uploaded_at": "2026-04-03",
            "channel_name": "채널 B",
            "view_count": 200,
            "checked_at": "2026-04-28",
            "clip_title": "클립 2",
            "work_title": "작품 A",
            "platform": "네이버 클립",
            "rights_holder_name": "웨이브",
        },
        {
            "video_url": "https://example.com/3",
            "uploaded_at": "2026-04-05",
            "channel_name": "채널 C",
            "view_count": 300,
            "checked_at": "2026-04-29",
            "clip_title": "하이라이트",
            "work_title": "작품 B",
            "platform": "네이버 TV",
            "rights_holder_name": "쿠팡플레이",
        },
    ]


def test_filter_rows_supports_period_and_dimension_filters() -> None:
    service = B2AnalyticsService()

    filtered = service.filter_rows(
        _sample_rows(),
        B2AnalyticsFilters(
            checked_from=date(2026, 4, 29),
            rights_holder_name="쿠팡플레이",
            platform="네이버 TV",
            clip_title="하이라이트",
        ),
    )

    assert len(filtered) == 1
    assert filtered[0]["channel_name"] == "채널 C"


def test_group_rows_aggregates_by_rights_holder() -> None:
    service = B2AnalyticsService()

    groups = service.group_rows(_sample_rows(), group_by="rights_holder")

    by_holder = {group["group_key"]: group for group in groups}

    assert set(by_holder) == {"웨이브", "쿠팡플레이"}
    assert by_holder["웨이브"]["clip_count"] == 2
    assert by_holder["웨이브"]["total_views"] == 300
    assert by_holder["쿠팡플레이"]["clip_count"] == 1


def test_filter_options_and_summary_are_derived_from_rows() -> None:
    service = B2AnalyticsService()
    rows = _sample_rows()

    options = service.filter_options(rows)
    summary = service.summarize(rows)

    assert options["checked_date_min"] == "2026-04-28"
    assert options["checked_date_max"] == "2026-04-29"
    assert options["rights_holder_names"] == ["웨이브", "쿠팡플레이"]
    assert summary == {
        "clip_count": 3,
        "channel_count": 3,
        "work_count": 2,
        "rights_holder_count": 2,
        "total_views": 600,
        "max_views": 300,
    }
