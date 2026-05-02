from fastapi.testclient import TestClient

from src.dashboard.app import build_app


def test_creator_portal_contracts() -> None:
    client = TestClient(build_app())

    channels = client.get("/api/channels/me")
    assert channels.status_code == 200
    assert channels.json()["items"][0]["platform"] == "youtube"

    videos = client.get("/api/channels/me/videos")
    assert videos.status_code == 200
    first_video = videos.json()["items"][0]
    assert first_video["active_channel_count"] >= 5

    usage = client.post(f"/api/channels/me/videos/{first_video['video_id']}/usage-requests", json={})
    assert usage.status_code == 200
    assert usage.json()["action"] == "A-2"

    creator = client.post(
        "/api/channels/me/creator-applications",
        json={"channel_id": "ch-kakao-original", "platform": "kakao"},
    )
    assert creator.status_code == 200
    assert creator.json()["status"] == "received"


def test_admin_dashboard_and_lead_discovery_contracts() -> None:
    client = TestClient(build_app())

    overview = client.get("/api/admin/overview")
    assert overview.status_code == 200
    assert [item["title"] for item in overview.json()["pending"]] == [
        "\uc791\ud488 \uc0ac\uc6a9 \uc2e0\uccad",
        "\uad8c\ub9ac \uc18c\uba85 \uc2e0\uccad",
        "\ub124\uc774\ubc84 \uc131\uacfc\ubcf4\uace0 \uc694\uccad",
    ]

    videos = client.get("/api/admin/videos")
    assert videos.status_code == 200
    enabled_video = next(item for item in videos.json()["items"] if item["active_channel_count"] >= 5)

    discovery = client.post("/api/admin/lead-discovery", json={"video_id": enabled_video["video_id"]})
    assert discovery.status_code == 200
    assert discovery.json()["status"] == "completed"
    assert discovery.json()["leads"][0]["contact_email"]

    metabase = client.get("/api/admin/reports/metabase")
    assert metabase.status_code == 200
    payload = metabase.json()
    assert "embed_url" in payload
    assert payload["env_key"] == "METABASE_" + "NAVER_CLIP_URL"
    assert [item["name"] for item in payload["reports"]] == ["\uc6e8\uc774\ube0c", "\ucee8\ud150\uce20\ub9c8\uc774\ub2dd"]
