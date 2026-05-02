from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from src.api import rpa_server


class _FakeB2Service:
    def __init__(self, *, repository: object, max_clips_per_identifier: int) -> None:
        self.repository = repository
        self.max_clips_per_identifier = max_clips_per_identifier

    def collect_enabled_reports(self, *, triggered_by: str = "manual") -> list[dict[str, Any]]:
        return [
            {
                "video_url": "https://example.com/clip/1",
                "channel_name": "\ud14c\uc2a4\ud2b8 \ucc44\ub110",
                "view_count": 120,
                "work_title": "\ud14c\uc2a4\ud2b8 \uc791\ud488",
                "rights_holder_name": "\ud14c\uc2a4\ud2b8 \uad8c\ub9ac\uc0ac",
            }
        ]


def test_b2_supabase_collect_contract(monkeypatch) -> None:
    monkeypatch.setattr(rpa_server, "build_b2_supabase_repository", lambda: object())
    monkeypatch.setattr(rpa_server, "B2TestReportService", _FakeB2Service)

    client = TestClient(rpa_server.build_app())
    response = client.post(
        "/api/admin/b2/supabase/collect",
        json={"triggered_by": "manual", "max_clips_per_identifier": 10},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["row_count"] == 1
    assert payload["summary"]["total_views"] == 120
