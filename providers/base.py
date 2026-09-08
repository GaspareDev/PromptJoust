"""
PromptJoust Abstract Base LLM Provider.

Defines the contract that every LLM provider adapter must implement
to generate structured TurnDecision arbitration results.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, Union
from core.types import TurnDecision


class BaseLLMProvider(ABC):
    """
    Abstract interface for LLM Providers powering the PromptJoust Referee.
    Implemented by GeminiProvider, ClaudeProvider, OpenAIProvider, GroqProvider, and OllamaProvider.
    """

    @abstractmethod
    def generate_turn_decision(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
    ) -> Union[str, TurnDecision]:
        """
        Executes model inference and returns either a raw JSON string or parsed TurnDecision.

        Args:
            system_prompt: System prompt with referee instructions and rules.
            user_prompt: Round-specific prompt containing hero/boss state and untrusted directives.
            schema: JSON Schema definition for strict structured output formatting.

        Returns:
            JSON string or TurnDecision instance representing the round's decision.
        """
        pass
