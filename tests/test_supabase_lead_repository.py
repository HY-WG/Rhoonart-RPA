from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from src.core.repositories.supabase_repository import (
    SupabaseLeadRepository,
    SupabaseSeedChannelRepository,
)
from src.models.lead import EmailSentStatus, Genre, Lead, LeadFilter


def _make_supabase_mock(return_data: list[dict] | None = None) -> tuple[MagicMock, MagicMock]:
    execute_result = MagicMock()
    execute_result.data = return_data or []

    builder = MagicMock()
    for method in (
        "select",
        "insert",
        "upsert",
        "update",
        "delete",
        "eq",
        "gte",
        "order",
        "limit",
    ):
        getattr(builder, method).return_value = builder
    builder.execute.return_value = execute_result

    client = MagicMock()
    client.table.return_value = builder
    return client, builder


def _sample_lead() -> Lead:
    return Lead(
        channel_id="UC123",
        channel_name="Drama Clip",
        channel_url="https://www.youtube.com/channel/UC123",
        platform="youtube",
        genre=Genre.DRAMA_MOVIE,
        monthly_shorts_views=12_000_000,
        tier="B",
        subscribers=100_000,
        email="hello@example.com",
        email_sent_status=EmailSentStatus.NOT_SENT,
        discovered_at=datetime(2026, 5, 1, 10, 0),
    )


def test_upsert_leads_uses_lead_channels_with_channel_id_conflict() -> None:
    client, builder = _make_supabase_mock()
    repo = SupabaseLeadRepository(client)

    count = repo.upsert_leads([_sample_lead()])

    assert count == 1
    client.table.assert_called_with("lead_channels")
    builder.upsert.assert_called_once()
    rows = builder.upsert.call_args.args[0]
    assert rows[0]["channel_id"] == "UC123"
    assert rows[0]["grade"] == "B"
    assert rows[0]["monthly_views"] == 12_000_000
    assert rows[0]["email_status"] == "unsent"
    assert builder.upsert.call_args.kwargs["on_conflict"] == "channel_id"


def test_get_leads_for_email_maps_filters_and_rows() -> None:
    client, builder = _make_supabase_mock(return_data=[{
        "channel_id": "UC123",
        "channel_name": "Drama Clip",
        "channel_url": "https://www.youtube.com/channel/UC123",
        "platform": "youtube",
        "genre": Genre.DRAMA_MOVIE.value,
        "grade": "A",
        "monthly_views": 25_000_000,
        "subscriber_count": 200_000,
        "email": "hello@example.com",
        "email_status": "unsent",
        "discovered_at": "2026-05-01T10:00:00",
    }])
    repo = SupabaseLeadRepository(client)

    leads = repo.get_leads_for_email(LeadFilter(
        genre=Genre.DRAMA_MOVIE,
        min_monthly_views=10_000_000,
        email_sent_status=EmailSentStatus.NOT_SENT,
        platform="youtube",
    ))

    assert len(leads) == 1
    assert leads[0].channel_id == "UC123"
    assert leads[0].tier == "A"
    builder.eq.assert_any_call("genre", Genre.DRAMA_MOVIE.value)
    builder.eq.assert_any_call("email_status", "unsent")
    builder.eq.assert_any_call("platform", "youtube")
    builder.gte.assert_called_with("monthly_views", 10_000_000)


def test_update_lead_email_status_writes_db_status() -> None:
    client, builder = _make_supabase_mock()
    repo = SupabaseLeadRepository(client)

    repo.update_lead_email_status("UC123", EmailSentStatus.SENT.value)

    client.table.assert_called_with("lead_channels")
    payload = builder.update.call_args.args[0]
    assert payload["email_status"] == "sent"
    assert payload["last_contacted_at"]
    builder.eq.assert_called_with("channel_id", "UC123")


def test_seed_channel_repository_reads_active_youtube_urls() -> None:
    client, builder = _make_supabase_mock(return_data=[
        {"channel_url": "https://www.youtube.com/@one", "active": True},
        {"url": "https://www.youtube.com/@two", "active": True},
        {"channel_url": "", "active": True},
    ])
    repo = SupabaseSeedChannelRepository(client)

    urls = repo.list_seed_channel_urls()

    assert urls == [
        "https://www.youtube.com/@one",
        "https://www.youtube.com/@two",
    ]
    client.table.assert_called_with("seed_channel")
    builder.eq.assert_any_call("platform", "youtube")
    builder.eq.assert_any_call("active", True)
