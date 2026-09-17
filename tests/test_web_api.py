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


def test_load_bosses_corrupt_file():
    from interfaces.web.server import load_bosses
    with patch("pathlib.Path.glob") as mock_glob:
        from pathlib import Path
        fake_file = Path("corrupted_boss.json")
        mock_glob.return_value = [fake_file]
        with patch("builtins.open", side_effect=IOError("Corrupt file")):
            bosses = load_bosses()
            assert bosses == {}


def test_simulate_provider_initialization_error():
    payload = {
        "boss_id": "boss_level_01",
        "hero_name": "WebTactician",
        "tactical_prompt": "Attack!",
        "hp_bonus": 5,
        "atk_bonus": 5,
        "def_bonus": 5,
        "sta_bonus": 5,
        "provider": "unknown_provider_xyz",
    }
    resp = client.post("/api/simulate", json=payload)
    assert resp.status_code == 400
    assert "Provider initialization error" in resp.json()["detail"]


def test_server_module_main_and_sys_path():
    import runpy
    import sys
    from pathlib import Path
    root = str(Path(__file__).resolve().parent.parent)
    with patch("uvicorn.run"):
        # Remove root temporarily so line 21 executes
        was_in_path = root in sys.path
        if was_in_path:
            sys.path.remove(root)
        try:
            runpy.run_module("interfaces.web.server", run_name="__main__")
        finally:
            if was_in_path and root not in sys.path:
                sys.path.insert(0, root)


def test_get_difficulties():
    resp = client.get("/api/difficulties")
    assert resp.status_code == 200
    diffs = resp.json()
    assert len(diffs) == 3
    levels = [d["level"] for d in diffs]
    assert "apprentice" in levels
    assert "warrior" in levels
    assert "grandmaster" in levels


@patch("interfaces.web.server.get_provider")
def test_simulate_match_apprentice_and_grandmaster(mock_get_p):
    mock_get_p.return_value = DummyTestProvider()

    # Apprentice (25 valor points)
    payload_apprentice = {
        "boss_id": "boss_level_01",
        "hero_name": "NoviceHero",
        "tactical_prompt": "Standard strike with quick blade.",
        "hp_bonus": 10,
        "atk_bonus": 5,
        "def_bonus": 5,
        "sta_bonus": 5,  # Sum is 25
        "difficulty": "apprentice",
        "provider": "gemini",
    }
    resp_app = client.post("/api/simulate", json=payload_apprentice)
    assert resp_app.status_code == 200
    res_app = resp_app.json()
    assert res_app["difficulty"] == "apprentice"

    # Grandmaster (15 valor points)
    payload_grandmaster = {
        "boss_id": "boss_level_01",
        "hero_name": "MasterHero",
        "tactical_prompt": "Concise attack order.",
        "hp_bonus": 5,
        "atk_bonus": 5,
        "def_bonus": 5,
        "sta_bonus": 0,  # Sum is 15
        "difficulty": "grandmaster",
        "provider": "gemini",
    }
    resp_gm = client.post("/api/simulate", json=payload_grandmaster)
    assert resp_gm.status_code == 200
    res_gm = resp_gm.json()
    assert res_gm["difficulty"] == "grandmaster"


@patch("interfaces.web.server.get_provider")
def test_simulate_match_stream_endpoint(mock_get_p):
    mock_get_p.return_value = DummyTestProvider()

    payload = {
        "boss_id": "boss_level_01",
        "hero_name": "StreamChampion",
        "tactical_prompt": "Fast slash with iron sword.",
        "hp_bonus": 5,
        "atk_bonus": 5,
        "def_bonus": 5,
        "sta_bonus": 5,
        "difficulty": "warrior",
        "provider": "ollama",
    }
    resp = client.post("/api/simulate/stream", json=payload)
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    body = resp.text
    assert "event: init" in body
    assert "event: round" in body
    assert "event: complete" in body


def test_simulate_match_stream_validation_errors():
    # 1. Unknown boss
    resp = client.post("/api/simulate/stream", json={
        "boss_id": "non_existent_boss",
        "tactical_prompt": "Fight",
        "hp_bonus": 5,
        "atk_bonus": 5,
        "def_bonus": 5,
        "sta_bonus": 5,
    })
    assert resp.status_code == 404

    # 2. Invalid points
    resp = client.post("/api/simulate/stream", json={
        "boss_id": "boss_level_01",
        "tactical_prompt": "Fight",
        "hp_bonus": 0,
        "atk_bonus": 0,
        "def_bonus": 0,
        "sta_bonus": 0,
    })
    assert resp.status_code == 400

    # 3. Overlength prompt
    resp = client.post("/api/simulate/stream", json={
        "boss_id": "boss_level_01",
        "tactical_prompt": "A" * 300,
        "hp_bonus": 5,
        "atk_bonus": 5,
        "def_bonus": 5,
        "sta_bonus": 5,
    })
    assert resp.status_code == 400

    # 4. Provider init error
    with patch("interfaces.web.server.get_provider", side_effect=ValueError("Bad provider key")):
        resp = client.post("/api/simulate/stream", json={
            "boss_id": "boss_level_01",
            "tactical_prompt": "Fight",
            "hp_bonus": 5,
            "atk_bonus": 5,
            "def_bonus": 5,
            "sta_bonus": 5,
        })
        assert resp.status_code == 400
        assert "Provider initialization error" in resp.json()["detail"]


def test_simulate_empty_prompt_stream_and_json():
    # Verify empty prompt is allowed in web endpoints and hero enters confusion
    with patch("interfaces.web.server.get_provider") as mock_get_provider:
        mock_get_provider.return_value = DummyTestProvider()

        # 1. JSON endpoint
        resp = client.post("/api/simulate", json={
            "boss_id": "boss_level_01",
            "hero_name": "Silent Hero",
            "tactical_prompt": "",
            "hp_bonus": 5,
            "atk_bonus": 5,
            "def_bonus": 5,
            "sta_bonus": 5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["winner"] == "Boss"
        assert data["rounds_log"][0]["turn_decision"]["hero_intent"]["action"] == "CONFUSED"

        # 2. SSE Stream endpoint
        resp_stream = client.post("/api/simulate/stream", json={
            "boss_id": "boss_level_01",
            "hero_name": "Silent Hero",
            "tactical_prompt": "   ",
            "hp_bonus": 5,
            "atk_bonus": 5,
            "def_bonus": 5,
            "sta_bonus": 5,
        })
        assert resp_stream.status_code == 200
        assert "CONFUSED" in resp_stream.text






