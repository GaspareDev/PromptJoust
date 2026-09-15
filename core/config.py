"""
PromptJoust Central Configuration & Environment Manager.

Loads runtime configuration parameters from `.env` files and environment variables:
- Supported API keys (OpenAI, Gemini, Groq, Claude / Anthropic)
- Configured model names for each provider
- Server hosting, port, timeouts, and debug flags
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


def _load_env_file(env_path: Path = Path(".env")) -> None:
    """
    Lightweight zero-dependency parser for local `.env` files.
    Injects key-value pairs into `os.environ` without overriding existing variables.
    """
    if not env_path.exists():
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


_load_env_file()

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        """
        Centralized runtime configuration management for PromptJoust.
        Automatically reads from environment variables and local .env files.
        """
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
        )

        # Default Provider
        default_llm_provider: str = "ollama"

        # API Keys & Endpoints
        openai_api_key: Optional[str] = None
        gemini_api_key: Optional[str] = None
        google_api_key: Optional[str] = None
        groq_api_key: Optional[str] = None
        anthropic_api_key: Optional[str] = None
        claude_api_key: Optional[str] = None
        ollama_host: str = "http://localhost:11434"

        # Model Selections (Configurable in .env)
        gemini_model: str = "gemini-2.5-flash"
        claude_model: str = "claude-3-5-haiku-20241022"
        openai_model: str = "gpt-4o-mini"
        groq_model: str = "llama-3.3-70b-versatile"
        ollama_model: str = "llama3.2"

        # Server Configuration
        server_host: str = "0.0.0.0"
        server_port: int = 8000
        debug: bool = False
        default_timeout: int = 30

        def get_effective_gemini_key(self) -> Optional[str]:
            return self.gemini_api_key or self.google_api_key

        def get_effective_claude_key(self) -> Optional[str]:
            return self.anthropic_api_key or self.claude_api_key

except ImportError:
    # Graceful zero-dependency fallback using standard Pydantic BaseModel
    class Settings(BaseModel):  # type: ignore[no-redef]
        """
        Fallback Settings class when pydantic-settings is not installed.
        """
        default_llm_provider: str = Field(default_factory=lambda: os.getenv("DEFAULT_LLM_PROVIDER", "ollama"))

        openai_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
        gemini_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY"))
        google_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("GOOGLE_API_KEY"))
        groq_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("GROQ_API_KEY"))
        anthropic_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
        claude_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("CLAUDE_API_KEY"))
        ollama_host: str = Field(default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434"))

        gemini_model: str = Field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
        claude_model: str = Field(default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-3-5-haiku-20241022"))
        openai_model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
        groq_model: str = Field(default_factory=lambda: os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
        ollama_model: str = Field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.2"))

        server_host: str = Field(default_factory=lambda: os.getenv("SERVER_HOST", "0.0.0.0"))
        server_port: int = Field(default_factory=lambda: int(os.getenv("SERVER_PORT", "8000")))
        debug: bool = Field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
        default_timeout: int = Field(default_factory=lambda: int(os.getenv("DEFAULT_TIMEOUT", "30")))

        def get_effective_gemini_key(self) -> Optional[str]:
            return self.gemini_api_key or self.google_api_key

        def get_effective_claude_key(self) -> Optional[str]:
            return self.anthropic_api_key or self.claude_api_key


# Global singleton settings instance
settings = Settings()


