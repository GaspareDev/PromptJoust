"""
PromptJoust OpenAI Adapter.

Integrates with OpenAI chat completion models (default: gpt-4o-mini) using
native JSON Schema Structured Outputs (`json_schema`).
"""

from __future__ import annotations

import os
import json
from typing import Dict, Any, Optional, Union
from models import TurnDecision
from core.config import settings
from .base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI adapter leveraging Structured Outputs (json_schema).
    Default model: gpt-4o-mini
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model
        if not self.api_key:
            raise ValueError("OpenAI API key missing. Please set OPENAI_API_KEY environment variable or pass api_key.")

        try:
            from openai import OpenAI, AsyncOpenAI
            self.client = OpenAI(api_key=self.api_key)
            self.async_client = AsyncOpenAI(api_key=self.api_key)

        except ImportError:
            raise ImportError("openai package is required for OpenAIProvider. Install with `pip install openai`.")

    def generate_turn_decision(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
    ) -> Union[str, TurnDecision]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "TurnDecision",
                    "strict": True,
                    "schema": schema,
                },
            },
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
        response = await self.async_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "TurnDecision",
                    "strict": True,
                    "schema": schema,
                },
            },
            temperature=0.2,
            max_tokens=512,
        )

        content = response.choices[0].message.content
        return content
