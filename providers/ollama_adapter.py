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
    Default model: llama3.2 (or llama3, qwen2.5, mistral)
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
        # Minified JSON schema representation to minimize token consumption
        min_schema = json.dumps(schema, separators=(',', ':'))
        system_with_schema = f"{system_prompt}\n\nSTRICT REQUIREMENT: Output must strictly validate against this JSON Schema:\n{min_schema}"

        # Optimized performance parameters:
        # - keep_alive: retains model in memory across rounds to avoid reload latency
        # - num_predict: caps maximum generated tokens (~100 tokens needed for round JSON)
        # - num_ctx: limits KV cache allocation to 1024 tokens for faster attention processing
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_with_schema},
                {"role": "user", "content": user_prompt},
            ],
            "format": "json",
            "stream": False,
            "keep_alive": "15m",
            "options": {
                "temperature": 0.1,
                "num_predict": 180,
                "num_ctx": 1024,
                "top_k": 20,
                "top_p": 0.85,
            },
        }

        try:
            resp = requests.post(url, json=payload, timeout=45)
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]
        except requests.RequestException as exc:
            raise ConnectionError(
                f"Failed to communicate with local Ollama server at {self.host}. "
                f"Is Ollama running (`ollama serve`) and is '{self.model}' installed (`ollama pull {self.model}`)? Details: {exc}"
            ) from exc

