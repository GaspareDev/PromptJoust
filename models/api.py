"""
PromptJoust API Request & Response Schemas.

Defines validation models for FastAPI web endpoints.
"""

from typing import Optional
from pydantic import BaseModel, Field

from models.enums import DifficultyLevel


class SimulationRequest(BaseModel):
    """
    Payload for initiating a match simulation via POST /api/simulate.
    """
    boss_id: str
    hero_name: str = "Tactician Prime"
    tactical_prompt: str
    hp_bonus: int = Field(default=5, ge=0, le=25)
    atk_bonus: int = Field(default=5, ge=0, le=25)
    def_bonus: int = Field(default=5, ge=0, le=25)
    sta_bonus: int = Field(default=5, ge=0, le=25)
    difficulty: DifficultyLevel = DifficultyLevel.WARRIOR
    provider: str = "ollama"
    api_key: Optional[str] = None
    model: Optional[str] = None


class ProviderOption(BaseModel):
    """
    Supported arbiter LLM provider metadata.
    """
    id: str
    name: str
    requires_api_key: bool = False
    default_model: str = ""
