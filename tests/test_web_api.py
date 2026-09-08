from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from interfaces.web.server import app

client = TestClient(app)


from unittest.mock import patch
from tests.test_helpers import DummyTestProvider


def test_get_bosses():
    resp = client.get("/api/bosses")
    assert resp.status_code == 200
    bosses = resp.json()
    assert len(bosses) >= 3
    # Check that secrets are not leaked in public endpoint
    for b in bosses:
        assert "secret_personality_prompt" not in b
        assert "id" in b
        assert "name" in b
        assert "stats" in b


def test_get_providers():
    resp = client.get("/api/providers")
    assert resp.status_code == 200
    providers = resp.json()
    assert "mock" not in providers
    assert "openai" in providers
    assert "gemini" in providers
    assert "groq" in providers
    assert "claude" in providers
    assert "ollama" in providers


@patch("interfaces.web.server.get_provider")
def test_simulate_match_endpoint(mock_get_p):
    mock_get_p.return_value = DummyTestProvider()
    payload = {
        "boss_id": "boss_level_01",
        "hero_name": "WebTactician",
        "tactical_prompt": "Smash Ferrum with heavy crushing attacks.",
        "hp_bonus": 5,
        "atk_bonus": 10,
        "def_bonus": 5,
        "sta_bonus": 0,
        "provider": "gemini",
    }
    resp = client.post("/api/simulate", json=payload)
    assert resp.status_code == 200
    result = resp.json()
    assert "winner" in result
    assert "total_rounds" in result
    assert len(result["rounds_log"]) == result["total_rounds"]


def test_simulate_invalid_points_allocation():
    payload = {
        "boss_id": "boss_level_01",
        "hero_name": "WebTactician",
        "tactical_prompt": "Attack!",
        "hp_bonus": 10,
        "atk_bonus": 10,
        "def_bonus": 10,
        "sta_bonus": 10,  # Sum is 40 != 20
        "provider": "gemini",
    }
    resp = client.post("/api/simulate", json=payload)
    assert resp.status_code == 400
    assert "bonus points" in resp.json()["detail"]


def test_simulate_unknown_boss_id():
    payload = {
        "boss_id": "non_existent_boss_999",
        "hero_name": "WebTactician",
        "tactical_prompt": "Attack!",
        "hp_bonus": 5,
        "atk_bonus": 5,
        "def_bonus": 5,
        "sta_bonus": 5,
        "provider": "gemini",
    }
    resp = client.post("/api/simulate", json=payload)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_simulate_overlength_prompt():
    payload = {
        "boss_id": "boss_level_01",
        "hero_name": "WebTactician",
        "tactical_prompt": "A" * 300,
        "hp_bonus": 5,
        "atk_bonus": 5,
        "def_bonus": 5,
        "sta_bonus": 5,
        "provider": "gemini",
    }
    resp = client.post("/api/simulate", json=payload)
    assert resp.status_code == 400


def test_root_index_html_route():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "PromptJoust" in resp.text


def test_server_run_invokes_uvicorn():
    from unittest.mock import patch
    from interfaces.web.server import run
    with patch("uvicorn.run") as mock_uvicorn:
        run()
        mock_uvicorn.assert_called_once()


