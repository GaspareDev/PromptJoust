from __future__ import annotations

import os
import pytest
from unittest.mock import patch
from core.config import Settings


def test_settings_defaults():
    s = Settings(
        openai_api_key=None,
        gemini_api_key=None,
        google_api_key=None,
        groq_api_key=None,
        anthropic_api_key=None,
        claude_api_key=None,
        ollama_host="http://localhost:11434",
    )
    assert s.ollama_host == "http://localhost:11434"
    assert s.server_port == 8000
    assert s.server_host == "0.0.0.0"
    assert s.gemini_model == "gemini-2.5-flash"
    assert s.claude_model == "claude-3-5-haiku-20241022"
    assert s.openai_model == "gpt-4o-mini"
    assert s.groq_model == "llama-3.3-70b-versatile"
    assert s.ollama_model == "llama3"
    assert s.get_effective_gemini_key() is None
    assert s.get_effective_claude_key() is None


def test_settings_gemini_fallback():
    s1 = Settings(gemini_api_key="gem-key", google_api_key="goog-key")
    assert s1.get_effective_gemini_key() == "gem-key"

    s2 = Settings(gemini_api_key=None, google_api_key="goog-key")
    assert s2.get_effective_gemini_key() == "goog-key"


def test_settings_claude_fallback():
    s1 = Settings(anthropic_api_key="anth-key", claude_api_key="claude-key")
    assert s1.get_effective_claude_key() == "anth-key"

    s2 = Settings(anthropic_api_key=None, claude_api_key="claude-key")
    assert s2.get_effective_claude_key() == "claude-key"


def test_load_env_file(tmp_path):
    from core.config import _load_env_file
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_CUSTOM_CONFIG_KEY=custom_value\n# Comment line\nINVALID_LINE\n")
    _load_env_file(env_file)
    assert os.getenv("TEST_CUSTOM_CONFIG_KEY") == "custom_value"
    # Calling on non-existent file should be a no-op
    _load_env_file(tmp_path / "non_existent.env")

