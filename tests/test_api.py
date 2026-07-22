"""Tests for the DevLog API. The CI pipeline runs these on every PR."""

import os

import pytest
from fastapi.testclient import TestClient

# Point the app at a temporary database BEFORE importing it.
os.environ["DEVLOG_DB"] = "test_devlog.db"

from app.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    """Fresh database for every test."""
    if os.path.exists("test_devlog.db"):
        os.remove("test_devlog.db")
    yield
    if os.path.exists("test_devlog.db"):
        os.remove("test_devlog.db")


def make_entry(**overrides):
    payload = {
        "type": "study",
        "what": "Learned about Deployments",
        "tags": ["kubernetes"],
        "minutes": 30,
    }
    payload.update(overrides)
    return client.post("/entries", json=payload)


def test_create_entry():
    resp = make_entry()
    assert resp.status_code == 201
    body = resp.json()
    assert body["what"] == "Learned about Deployments"
    assert body["tags"] == ["kubernetes"]
    assert body["minutes"] == 30


def test_create_entry_rejects_invalid_type():
    resp = make_entry(type="nap")
    assert resp.status_code == 422


def test_list_entries_filters_by_tag():
    make_entry(tags=["docker"])
    make_entry(tags=["kubernetes"])
    resp = client.get("/entries", params={"tag": "docker"})
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["tags"] == ["docker"]


def test_stats_counts_minutes_and_streak():
    make_entry(minutes=30)
    make_entry(minutes=15, tags=["python"])
    resp = client.get("/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_entries"] == 2
    assert body["minutes_last_7_days"] == 45
    assert body["streak_days"] == 1  # both entries are from today


def test_weekly_breakdown_percentages():
    make_entry(minutes=30, tags=["kubernetes"])
    make_entry(minutes=10, tags=["python"])
    resp = client.get("/weekly")
    body = resp.json()
    assert body["total_minutes"] == 40
    top = body["by_tag"][0]
    assert top["tag"] == "kubernetes"
    assert top["percent"] == 75


def test_info_returns_runtime_details():
    resp = client.get("/info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["namespace"] == "local"  # no POD_NAMESPACE env var set
    assert "hostname" in body
    assert "headers" in body


def test_health():
    assert client.get("/health").json() == {"status": "ok"}
