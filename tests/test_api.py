import json

import pytest
from fastapi.testclient import TestClient

from kisan_agent.api.dependencies import get_agent
from kisan_agent.core.config import Settings
from kisan_agent.main import create_app


@pytest.fixture
def client(agent):
    settings = Settings(nebius_api_key="test", tavily_api_key="test", max_image_bytes=1024)
    app = create_app(settings)
    app.dependency_overrides[get_agent] = lambda: agent
    with TestClient(app) as test_client:
        yield test_client


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_meta_lists_languages_and_models(client):
    body = client.get("/api/meta").json()
    assert "Hindi" in {lang["name"] for lang in body["languages"]}
    assert set(body["models"]) == {"fast", "vision", "reasoning"}


def test_index_page_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "KisanAgent" in response.text


def test_consult_streams_events(client):
    response = client.post(
        "/api/consult",
        data={"question": "Brown spots on leaves", "language": "Hindi", "location": "Nashik"},
        files={"image": ("leaf.jpg", b"\xff\xd8small", "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    assert events[0] == ("step", events[0][1])
    assert events[-1][0] == "done"
    assert any(kind == "token" for kind, _ in events)


def test_consult_rejects_unknown_language(client):
    response = client.post("/api/consult", data={"question": "Brown spots", "language": "Klingon"})
    assert response.status_code == 422


def test_consult_rejects_non_image_upload(client):
    response = client.post(
        "/api/consult",
        data={"question": "Brown spots"},
        files={"image": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 415


def test_consult_rejects_oversized_image(client):
    response = client.post(
        "/api/consult",
        data={"question": "Brown spots"},
        files={"image": ("leaf.jpg", b"x" * 2048, "image/jpeg")},
    )
    assert response.status_code == 413
