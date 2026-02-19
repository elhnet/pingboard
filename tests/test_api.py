"""Tests for the /status API endpoint response shape."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import db as db_module


@pytest.fixture
def tmp_db(tmp_path):
    db_path = tmp_path / "test.db"
    db_module.init_db(db_path)
    return db_path


@pytest.fixture
def client(tmp_db):
    async def noop_checker(stop_event):
        await stop_event.wait()

    with patch.object(db_module, "DB_PATH", tmp_db), \
         patch("checker.run_checker", side_effect=noop_checker):
        from api import app
        with TestClient(app) as tc:
            yield tc


def test_status_empty(client):
    """GET /status returns empty list when no URLs configured."""
    resp = client.get("/status")
    assert resp.status_code == 200
    assert resp.json() == []


def test_status_response_shape(client, tmp_db):
    """GET /status response has correct JSON structure and fields."""
    url_id = db_module.add_url("https://example.com", label="Example", db_path=tmp_db)
    db_module.record_check(url_id, status_code=200, response_time_ms=42.5, db_path=tmp_db)

    resp = client.get("/status")
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1

    entry = data[0]
    assert "url" in entry
    assert "latest" in entry
    assert "checks" in entry
    assert entry["url"] == "https://example.com"

    # latest fields
    latest = entry["latest"]
    assert latest is not None
    assert "status_code" in latest
    assert "latency_ms" in latest
    assert "ok" in latest
    assert "checked_at" in latest
    assert latest["status_code"] == 200
    assert latest["latency_ms"] == 42.5
    assert latest["ok"] is True

    # checks list
    assert isinstance(entry["checks"], list)
    assert len(entry["checks"]) == 1
    check = entry["checks"][0]
    assert "status_code" in check
    assert "latency_ms" in check
    assert "ok" in check
    assert "checked_at" in check


def test_status_latest_none_when_no_checks(client, tmp_db):
    """latest is null when URL has no checks."""
    db_module.add_url("https://example.com", db_path=tmp_db)

    resp = client.get("/status")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["latest"] is None
    assert data[0]["checks"] == []
