"""
PromptJoust Anthropic Claude Adapter.

Integrates with Anthropic Claude models (default: claude-3-5-haiku-20241022 or claude-3-5-sonnet).
Supports official `anthropic` Python SDK when installed, with automatic zero-dependency
REST HTTP fallback via `requests`.
"""

from __future__ import annotations

import json
import os
from typing import Dict, Any, Optional, Union
import requests
from models import TurnDecision
from core.config import settings
from .base import BaseLLMProvider


class ClaudeProvider(BaseLLMProvider):
    """
    Anthropic Claude provider supporting Claude 3.5 Sonnet / Haiku.
    Supports official anthropic SDK if installed, with seamless zero-dependency REST fallback via requests.
    """

    DEFAULT_MODEL = "claude-3-5-haiku-20241022"
    API_URL = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or settings.get_effective_claude_key()
        if not self.api_key:
            raise ValueError(
                "Anthropic / Claude API key missing. Provide via 'api_key' argument, "
                "or set ANTHROPIC_API_KEY / CLAUDE_API_KEY in environment."
            )
        self.model = model or settings.claude_model or self.DEFAULT_MODEL
        self._client = None

        try:
            import anthropic  # type: ignore
            self._client = anthropic.Anthropic(api_key=self.api_key)
            self._async_client = anthropic.AsyncAnthropic(api_key=self.api_key)
        except (ImportError, Exception):
            self._client = None
            self._async_client = None

    def generate_turn_decision(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
    ) -> Union[str, TurnDecision]:
        compact_schema = json.dumps(schema, separators=(",", ":"))
        prompt_with_instructions = (
            f"{user_prompt}\n\n"
            f"[CRITICAL FORMAT INSTRUCTION]\n"
            f"You MUST output valid, parseable JSON strictly adhering to this schema:\n"
            f"{compact_schema}\n"
            f"Do not include any conversational preamble, explanations, or text outside the JSON structure."
        )

        # 1. Attempt official SDK if available
        if self._client is not None:
            try:
                response = self._client.messages.create(
                    model=self.model,
                    max_tokens=512,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": prompt_with_instructions}
                    ],
                )
                if response.content and len(response.content) > 0:
                    first_part = response.content[0]
                    if hasattr(first_part, "text"):
                        return first_part.text
                    elif isinstance(first_part, dict) and "text" in first_part:
                        return first_part["text"]
            except Exception as e:
                # If SDK fails, attempt REST fallback
                pass

        # 2. REST HTTP API Fallback
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.API_VERSION,
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": 512,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": prompt_with_instructions}
            ],
        }

        try:
            resp = requests.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=settings.default_timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            content_blocks = data.get("content", [])
            if content_blocks and "text" in content_blocks[0]:
                return content_blocks[0]["text"]
            raise ValueError(f"Unexpected response structure from Claude API: {data}")
        except requests.RequestException as e:
            raise ConnectionError(f"Claude API request failed: {e}")

    async def generate_turn_decision_async(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
    ) -> Union[str, TurnDecision]:
        compact_schema = json.dumps(schema, separators=(",", ":"))
        prompt_with_instructions = (
            f"{user_prompt}\n\n"
            f"[CRITICAL FORMAT INSTRUCTION]\n"
            f"You MUST output valid, parseable JSON strictly adhering to this schema:\n"
            f"{compact_schema}\n"
            f"Do not include any conversational preamble, explanations, or text outside the JSON structure."
        )

        if self._async_client is not None:
            try:
                response = await self._async_client.messages.create(
                    model=self.model,
                    max_tokens=512,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": prompt_with_instructions}
                    ],
                )
                if response.content and len(response.content) > 0:
                    first_part = response.content[0]
                    if hasattr(first_part, "text"):
                        return first_part.text
                    elif isinstance(first_part, dict) and "text" in first_part:
                        return first_part["text"]
            except Exception:
                pass

        import httpx
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.API_VERSION,
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": 512,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": prompt_with_instructions}
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=float(settings.default_timeout)) as client:
                resp = await client.post(
                    self.API_URL,
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                content_blocks = data.get("content", [])
                if content_blocks and "text" in content_blocks[0]:
                    return content_blocks[0]["text"]
                raise ValueError(f"Unexpected response structure from Claude API: {data}")
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ConnectionError(f"Claude API request failed: {e}")
