from __future__ import annotations

from fastapi.testclient import TestClient

from src.api import rpa_server
from src.models import RepresentativeChannelPlatform
from tests.fakes import FakeFormRepo


def test_a3_submission_api_creates_and_lists_applicants(monkeypatch) -> None:
    repo = FakeFormRepo()
    monkeypatch.setattr(rpa_server, "build_naver_clip_repository", lambda: repo)
    monkeypatch.setattr(rpa_server.settings, "X_INTERN_TOKEN", "")
    client = TestClient(rpa_server.build_app())

    payload = {
        "name": "홍길동",
        "phone_number": "010-1234-5678",
        "naver_id": "naver_user_01",
        "naver_clip_profile_name": "홍길동 클립",
        "naver_clip_profile_id": "clip-profile-001",
        "representative_channel_name": "대표 채널 A",
        "representative_channel_platform": RepresentativeChannelPlatform.YOUTUBE.value,
        "channel_url": "https://example.com/channel-a",
    }

    create_response = client.post("/api/a3/applicants", json=payload)
    list_response = client.get("/api/a3/applicants")

    assert create_response.status_code == 200
    assert create_response.json()["name"] == "홍길동"
    assert create_response.json()["representative_channel_platform"] == "유튜브"
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["naver_clip_profile_id"] == "clip-profile-001"
