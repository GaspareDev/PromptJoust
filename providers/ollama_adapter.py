"""
PromptJoust Ollama Adapter.

Integrates with locally hosted Ollama instances for 100% offline, zero-cost
LLM inference (default model: llama3, mistral, qwen2.5) using native JSON schema mode.
"""

from __future__ import annotations

import os
import json
from typing import Dict, Any, Optional, Union
import requests
from core.types import TurnDecision
from core.config import settings
from .base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """
    Ollama adapter for 100% offline, zero-cost local LLM execution.
    Default model: llama3 (or mistral, qwen2.5)
    """

    def __init__(self, host: Optional[str] = None, model: Optional[str] = None):
        self.host = host or settings.ollama_host
        self.model = model or settings.ollama_model


    def generate_turn_decision(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
    ) -> Union[str, TurnDecision]:
        url = f"{self.host.rstrip('/')}/api/chat"
        system_with_schema = f"{system_prompt}\n\nSTRICT REQUIREMENT: Output must strictly validate against this JSON Schema:\n{json.dumps(schema)}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_with_schema},
                {"role": "user", "content": user_prompt},
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.2,
            },
        }

        try:
            resp = requests.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]
        except requests.RequestException as exc:
            raise ConnectionError(
                f"Failed to communicate with local Ollama server at {self.host}. "
                f"Is Ollama running (`ollama serve`) and is '{self.model}' installed (`ollama pull {self.model}`)? Details: {exc}"
            ) from exc
