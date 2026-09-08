"""
PromptJoust Providers Package & Factory.

Exposes provider registry and unified factory function `get_provider()`
to instantiate the appropriate LLM adapter dynamically based on user configuration.
"""

from __future__ import annotations

from typing import Optional, Dict, Type
from .base import BaseLLMProvider
from .openai_adapter import OpenAIProvider
from .gemini_adapter import GeminiProvider
from .groq_adapter import GroqProvider
from .ollama_adapter import OllamaProvider
from .claude_adapter import ClaudeProvider

# Registry of supported LLM provider names mapped to their adapter class
PROVIDERS: Dict[str, Type[BaseLLMProvider]] = {
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
    "groq": GroqProvider,
    "claude": ClaudeProvider,
    "anthropic": ClaudeProvider,
    "ollama": OllamaProvider,
}


def get_provider(
    provider_name: str = "gemini",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> BaseLLMProvider:
    """
    Factory function to instantiate the requested LLM provider.

    Args:
        provider_name: Case-insensitive provider key ('gemini', 'claude', 'openai', 'groq', 'ollama').
        api_key: Optional explicit API key override (defaults to environment variable).
        model: Optional explicit model override (defaults to settings/env model).
        **kwargs: Extra arguments passed to the provider class constructor.

    Returns:
        Instantiated BaseLLMProvider adapter.
    """
    name = provider_name.lower().strip()
    if name not in PROVIDERS:
        raise ValueError(
            f"Unknown provider '{provider_name}'. Available providers: {list(PROVIDERS.keys())}"
        )

    provider_cls = PROVIDERS[name]
    init_kwargs = {}
    if api_key:
        init_kwargs["api_key"] = api_key
    if model:
        init_kwargs["model"] = model
    init_kwargs.update(kwargs)

    return provider_cls(**init_kwargs)


__all__ = [
    "BaseLLMProvider",
    "OpenAIProvider",
    "GeminiProvider",
    "GroqProvider",
    "ClaudeProvider",
    "OllamaProvider",
    "get_provider",
    "PROVIDERS",
]

