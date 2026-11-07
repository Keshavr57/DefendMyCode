"""
Tests for GET /health. These never call the LLM: tests must be free, fast and
work offline, and must not fail just because Groq is slow or down.
"""

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app


def test_health_returns_ok():
    # Using TestClient inside `with` runs the app's lifespan (startup), so
    # init_db() creates the tables, just like the real server.
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert isinstance(body["groq_key_set"], bool)  # only True/False, never the key


class BrokenSession:
    """A fake database session whose every query fails."""

    def execute(self, *args, **kwargs):
        raise RuntimeError("database is down")


def test_health_returns_503_when_database_fails():
    # dependency_overrides swaps get_db for our broken fake, only for this test.
    app.dependency_overrides[get_db] = lambda: BrokenSession()
    try:
        with TestClient(app) as client:
            response = client.get("/health")
    finally:
        app.dependency_overrides.clear()  # undo the swap so other tests aren't affected

    assert response.status_code == 503
    assert response.json()["status"] == "error"
