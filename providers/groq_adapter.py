"""
PromptJoust Groq Adapter.

Integrates with Groq ultra-low-latency LPU inference (default: llama-3.3-70b-versatile)
using JSON mode output formatting.
"""

from __future__ import annotations

import os
import json
from typing import Dict, Any, Optional, Union
from models import TurnDecision
from core.config import settings
from .base import BaseLLMProvider


class GroqProvider(BaseLLMProvider):
    """
    Groq ultra-low latency adapter with JSON mode.
    Default model: llama-3.3-70b-versatile
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.groq_api_key
        self.model = model or settings.groq_model
        if not self.api_key:
            raise ValueError("Groq API key missing. Please set GROQ_API_KEY environment variable or pass api_key.")


        try:
            from groq import Groq, AsyncGroq
            self.client = Groq(api_key=self.api_key)
            self.async_client = AsyncGroq(api_key=self.api_key)
        except ImportError:
            raise ImportError("groq package is required for GroqProvider. Install with `pip install groq`.")

    def generate_turn_decision(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
    ) -> Union[str, TurnDecision]:
        compact_schema = json.dumps(schema, separators=(",", ":"))
        system_with_schema = f"{system_prompt}\n\nYou MUST respond strictly in valid JSON matching this schema:\n{compact_schema}"
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_with_schema},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=512,
        )
        content = response.choices[0].message.content
        return content

    async def generate_turn_decision_async(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
    ) -> Union[str, TurnDecision]:
        compact_schema = json.dumps(schema, separators=(",", ":"))
        system_with_schema = f"{system_prompt}\n\nYou MUST respond strictly in valid JSON matching this schema:\n{compact_schema}"
        response = await self.async_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_with_schema},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=512,
        )
        content = response.choices[0].message.content
        return content

