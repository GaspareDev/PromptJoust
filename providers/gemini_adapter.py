"""
PromptJoust Google Gemini Adapter.

Integrates with Google Gemini models (default: gemini-2.5-flash) using
native structured JSON output enforcement. Supports both `google-genai` SDK
and zero-dependency REST HTTP fallback.
"""

from __future__ import annotations

import os
import json
from typing import Dict, Any, Optional, Union
import requests
from core.types import TurnDecision
from core.config import settings
from .base import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini adapter with Structured JSON outputs.
    Default model: gemini-2.5-flash
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.get_effective_gemini_key()
        self.model = model or settings.gemini_model
        if not self.api_key:
            raise ValueError("Gemini API key missing. Please set GEMINI_API_KEY or GOOGLE_API_KEY environment variable.")


    def generate_turn_decision(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
    ) -> Union[str, TurnDecision]:
        # Try google-genai or google.generativeai if available, otherwise use REST API
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.2,
                ),
            )
            return response.text
        except ImportError:
            pass

        # Direct REST API call
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "parts": [{"text": user_prompt}]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "response_schema": schema,
                "temperature": 0.2,
            },
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return text
