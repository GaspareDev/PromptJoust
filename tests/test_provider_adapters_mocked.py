from __future__ import annotations

import json
import pytest
from unittest.mock import patch, MagicMock
from providers.gemini_adapter import GeminiProvider
from providers.openai_adapter import OpenAIProvider
from providers.groq_adapter import GroqProvider
from providers.ollama_adapter import OllamaProvider
from providers.claude_adapter import ClaudeProvider
from core.referee import REFEREE_JSON_SCHEMA
from core.types import ActionType



SAMPLE_DECISION_JSON = json.dumps({
    "round_number": 1,
    "hero_intent": {"action": "ATTACK", "banter": "Strike!", "tactical_reasoning": "Standard"},
    "boss_intent": {"action": "DEFEND", "banter": "Shield!", "tactical_reasoning": "Block"},
    "psych_warfare_eval": {"hero_psych_successful": False, "boss_psych_successful": False, "reasoning": "none"},
    "referee_summary": "Hero strikes boss shield",
})


def test_gemini_provider_init_missing_key():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="Gemini API key missing"):
            GeminiProvider()


def test_gemini_provider_sdk_call_success():
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = SAMPLE_DECISION_JSON
        mock_client.models.generate_content.return_value = mock_response

        provider = GeminiProvider(api_key="fake-gemini-key")
        result = provider.generate_turn_decision(
            system_prompt="sys",
            user_prompt="usr",
            schema=REFEREE_JSON_SCHEMA,
        )
        assert result == SAMPLE_DECISION_JSON


def test_gemini_provider_rest_fallback_success():
    # Simulate google.genai not being available / raising ImportError
    with patch.dict("sys.modules", {"google.genai": None, "google": None}):
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "candidates": [
                    {"content": {"parts": [{"text": SAMPLE_DECISION_JSON}]}}
                ]
            }
            mock_resp.raise_for_status.return_value = None
            mock_post.return_value = mock_resp

            provider = GeminiProvider(api_key="fake-gemini-key")
            result = provider.generate_turn_decision(
                system_prompt="sys",
                user_prompt="usr",
                schema=REFEREE_JSON_SCHEMA,
            )
            assert result == SAMPLE_DECISION_JSON



def test_openai_provider_init_missing_key():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="OpenAI API key missing"):
            OpenAIProvider()


def test_openai_provider_success():
    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = SAMPLE_DECISION_JSON
        mock_client.chat.completions.create.return_value.choices = [mock_choice]

        provider = OpenAIProvider(api_key="fake-openai-key")
        result = provider.generate_turn_decision(
            system_prompt="sys",
            user_prompt="usr",
            schema=REFEREE_JSON_SCHEMA,
        )
        assert result == SAMPLE_DECISION_JSON


def test_groq_provider_init_missing_key():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="Groq API key missing"):
            GroqProvider()


def test_groq_provider_success():
    with patch("groq.Groq") as mock_groq_cls:
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = SAMPLE_DECISION_JSON
        mock_client.chat.completions.create.return_value.choices = [mock_choice]

        provider = GroqProvider(api_key="fake-groq-key")
        result = provider.generate_turn_decision(
            system_prompt="sys",
            user_prompt="usr",
            schema=REFEREE_JSON_SCHEMA,
        )
        assert result == SAMPLE_DECISION_JSON


def test_ollama_provider_success():
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "message": {"content": SAMPLE_DECISION_JSON}
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        provider = OllamaProvider(host="http://localhost:11434")
        result = provider.generate_turn_decision(
            system_prompt="sys",
            user_prompt="usr",
            schema=REFEREE_JSON_SCHEMA,
        )
        assert result == SAMPLE_DECISION_JSON


def test_ollama_provider_connection_error():
    import requests
    with patch("requests.post", side_effect=requests.RequestException("Connection refused")):
        provider = OllamaProvider(host="http://localhost:11434")
        with pytest.raises(ConnectionError, match="Failed to communicate with local Ollama server"):
            provider.generate_turn_decision(
                system_prompt="sys",
                user_prompt="usr",
                schema=REFEREE_JSON_SCHEMA,
            )


def test_claude_provider_init_missing_key():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="Anthropic / Claude API key missing"):
            ClaudeProvider()


def test_claude_provider_sdk_call_success():
    mock_anthropic = MagicMock()
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_part = MagicMock()
    mock_part.text = SAMPLE_DECISION_JSON
    mock_resp = MagicMock()
    mock_resp.content = [mock_part]
    mock_client.messages.create.return_value = mock_resp

    with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
        provider = ClaudeProvider(api_key="fake-claude-key")
        result = provider.generate_turn_decision(
            system_prompt="sys",
            user_prompt="usr",
            schema=REFEREE_JSON_SCHEMA,
        )
        assert result == SAMPLE_DECISION_JSON


def test_claude_provider_rest_fallback_success():
    # Force SDK import to fail / client to be None
    with patch.dict("sys.modules", {"anthropic": None}):
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "content": [{"text": SAMPLE_DECISION_JSON}]
            }
            mock_resp.raise_for_status.return_value = None
            mock_post.return_value = mock_resp

            provider = ClaudeProvider(api_key="fake-claude-key")
            result = provider.generate_turn_decision(
                system_prompt="sys",
                user_prompt="usr",
                schema=REFEREE_JSON_SCHEMA,
            )
            assert result == SAMPLE_DECISION_JSON


def test_claude_provider_connection_error():
    import requests
    with patch.dict("sys.modules", {"anthropic": None}):
        with patch("requests.post", side_effect=requests.RequestException("Connection refused")):
            provider = ClaudeProvider(api_key="fake-claude-key")
            with pytest.raises(ConnectionError, match="Claude API request failed"):
                provider.generate_turn_decision(
                    system_prompt="sys",
                    user_prompt="usr",
                    schema=REFEREE_JSON_SCHEMA,
                )


def test_openai_missing_package_raises():
    with patch.dict("sys.modules", {"openai": None}):
        with pytest.raises(ImportError, match="openai package is required"):
            OpenAIProvider(api_key="fake-key")


def test_groq_missing_package_raises():
    with patch.dict("sys.modules", {"groq": None}):
        with pytest.raises(ImportError, match="groq package is required"):
            GroqProvider(api_key="fake-key")


def test_base_provider_abstract_pass():
    from providers.base import BaseLLMProvider
    # Direct invocation of abstract base class pass
    BaseLLMProvider.generate_turn_decision(None, "sys", "usr", {})


def test_get_provider_factory_with_all_options():
    from providers import get_provider
    with patch("openai.OpenAI"):
        p_openai = get_provider("openai", api_key="fake-key", model="gpt-4o-mini")
        assert p_openai.model == "gpt-4o-mini"

    with patch("google.genai.Client"):
        p_gemini = get_provider("gemini", api_key="fake-key", model="gemini-2.5-flash")
        assert p_gemini.model == "gemini-2.5-flash"

    with patch("groq.Groq"):
        p_groq = get_provider("groq", api_key="fake-key", model="llama-3.3-70b-versatile")
        assert p_groq.model == "llama-3.3-70b-versatile"

    p_claude = get_provider("claude", api_key="fake-key", model="claude-3-5-haiku-20241022")
    assert p_claude.model == "claude-3-5-haiku-20241022"

    p_anthropic = get_provider("anthropic", api_key="fake-key", model="claude-3-5-sonnet-20241022")
    assert p_anthropic.model == "claude-3-5-sonnet-20241022"

    p_ollama = get_provider("ollama", host="http://localhost:11434", model="llama3")
    assert p_ollama.model == "llama3"


def test_referee_unparseable_errors():
    from core.referee import parse_and_validate_turn_decision
    # 1. No JSON at all
    with pytest.raises(ValueError, match="No valid JSON found"):
        parse_and_validate_turn_decision("Random narrative without braces", expected_round=1)

    # 2. Braces present but corrupted syntax
    with pytest.raises(ValueError, match="Failed to parse JSON"):
        parse_and_validate_turn_decision("Some text { corrupted json: invalid } end text", expected_round=1)


def test_sanitizer_stat_bounds_errors():
    from core.sanitizer import validate_and_allocate_stats, SanitizationError
    # ATK bonus of 20 makes base ATK 15 + 20 = 35 > 30
    with pytest.raises(SanitizationError, match="Final ATK"):
        validate_and_allocate_stats(hp_bonus=0, atk_bonus=20, def_bonus=0, sta_bonus=0)


def test_dummy_provider_fallback_regexes():
    from tests.test_helpers import DummyTestProvider
    dummy_p = DummyTestProvider()
    # Prompt without standard tags or round numbers
    d1 = dummy_p.generate_turn_decision("sys", "Raw instruction string with schede perforate", REFEREE_JSON_SCHEMA)
    assert d1.round_number == 1
    assert d1.hero_intent.action == ActionType.ATTACK



