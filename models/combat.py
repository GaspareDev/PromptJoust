"""
PromptJoust Combat & Domain Models.

Defines fighter statistics, live combat states, intent schemas,
decision objects, round logs, and boss definitions.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

from models.enums import ActionType, StatusEffect, DifficultyLevel


class DifficultyConfig(BaseModel):
    """
    Operational parameters associated with a combat difficulty tier.
    """
    level: DifficultyLevel
    name: str
    description: str
    valor_points: int
    max_prompt_length: int
    boss_hp_multiplier: float
    boss_atk_multiplier: float
    boss_def_multiplier: float
    boss_stamina_recovery: int


DIFFICULTY_CONFIGS: dict[DifficultyLevel, DifficultyConfig] = {
    DifficultyLevel.APPRENTICE: DifficultyConfig(
        level=DifficultyLevel.APPRENTICE,
        name="Apprentice",
        description="Ideal for novices mastering tactical prompts. Generous valor pool and reduced boss pressure.",
        valor_points=25,
        max_prompt_length=280,
        boss_hp_multiplier=0.85,
        boss_atk_multiplier=0.85,
        boss_def_multiplier=1.0,
        boss_stamina_recovery=5,
    ),
    DifficultyLevel.WARRIOR: DifficultyConfig(
        level=DifficultyLevel.WARRIOR,
        name="Warrior",
        description="The canonical arena tournament trial. Balanced valor points and standard boss prowess.",
        valor_points=20,
        max_prompt_length=280,
        boss_hp_multiplier=1.0,
        boss_atk_multiplier=1.0,
        boss_def_multiplier=1.0,
        boss_stamina_recovery=5,
    ),
    DifficultyLevel.GRANDMASTER: DifficultyConfig(
        level=DifficultyLevel.GRANDMASTER,
        name="Grandmaster",
        description="Unforgiving gauntlet for master tacticians. Constrained points, concise prompt limits, and relentless boss onslaught.",
        valor_points=15,
        max_prompt_length=200,
        boss_hp_multiplier=1.20,
        boss_atk_multiplier=1.20,
        boss_def_multiplier=1.10,
        boss_stamina_recovery=8,
    ),
}


class FighterStats(BaseModel):
    """
    Immutable base statistics for a combatant.
    - HP: Health Points (1-200)
    - ATK: Attack Power (5-30)
    - DEF: Defense Armor (5-30)
    - STA: Base Stamina (0-100)
    """
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    hp: int = Field(default=100, ge=1, le=200, description="Base Health Points")
    atk: int = Field(default=15, ge=5, le=30, description="Base Attack Power")
    def_: int = Field(default=10, ge=5, le=30, alias="def", description="Base Defense Armor")
    sta: int = Field(default=50, ge=0, le=100, description="Base Stamina")

    def to_dict(self) -> dict:
        """Serializes stats to a standard dictionary format."""
        return {
            "hp": self.hp,
            "atk": self.atk,
            "def": self.def_,
            "sta": self.sta,
        }


class FighterState(BaseModel):
    """
    Mutable snapshot of a fighter's live status during a combat simulation.
    Tracks live HP, Stamina, and active status durations.
    """
    name: str
    max_hp: int
    current_hp: int
    max_sta: int = 100
    current_sta: int
    atk: int
    def_: int = Field(alias="def")
    status: StatusEffect = StatusEffect.NORMAL
    status_duration: int = 0  # Number of combat rounds the status remains active

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_stats(cls, name: str, stats: FighterStats) -> FighterState:
        """Initializes a full-health FighterState from base FighterStats."""
        return cls(
            name=name,
            max_hp=stats.hp,
            current_hp=stats.hp,
            max_sta=100,
            current_sta=stats.sta,
            atk=stats.atk,
            def_=stats.def_,
            status=StatusEffect.NORMAL,
            status_duration=0,
        )

    def is_alive(self) -> bool:
        """Returns True if the fighter still has positive HP."""
        return self.current_hp > 0


class HeroIntent(BaseModel):
    """
    Hero action choice, battle cry / taunt, and tactical rationale for the round.
    """
    action: ActionType = Field(description="Canonical Action chosen for the Hero")
    banter: str = Field(max_length=100, description="Combat dialogue / taunt / battle cry")
    tactical_reasoning: str = Field(max_length=150, description="Strategic rationale for the choice")


class BossIntent(BaseModel):
    """
    Boss action choice, dialogue reaction, and tactical rationale for the round.
    """
    action: ActionType = Field(description="Canonical Action chosen for the Boss")
    banter: str = Field(max_length=100, description="Boss combat dialogue / reaction")
    tactical_reasoning: str = Field(max_length=150, description="Strategic rationale for the choice")


class PsychWarfareEval(BaseModel):
    """
    Referee psychological warfare assessment: evaluates if mental exploits succeeded.
    """
    hero_psych_successful: bool = Field(description="Whether hero successfully exploited boss psychological weakness")
    boss_psych_successful: bool = Field(description="Whether boss successfully exploited hero psychological weakness")
    reasoning: str = Field(max_length=120, description="Referee evaluation rationale for psych warfare")


class TurnDecision(BaseModel):
    """
    Complete JSON schema output produced by the LLM Referee for a single round.
    Contains intents from both combatants plus psychological evaluations and referee commentary.
    """
    round_number: int = Field(ge=1, le=20, description="Current match round")
    hero_intent: HeroIntent
    boss_intent: BossIntent
    psych_warfare_eval: PsychWarfareEval
    referee_summary: str = Field(max_length=160, description="Referee summary of the round encounter")


class CombatActionResolution(BaseModel):
    """
    Deterministic mathematical outcome of an action executed by a fighter in a round.
    """
    actor: str
    action: ActionType
    stamina_spent: int
    damage_dealt: int
    stamina_recovered: int = 0
    status_inflicted: Optional[StatusEffect] = None
    notes: str = ""


class RoundLog(BaseModel):
    """
    Complete state transition record for a single round of battle.
    Stores pre-round states, referee decision, action resolutions, and post-round states.
    """
    round_number: int
    hero_pre_state: FighterState
    boss_pre_state: FighterState
    turn_decision: TurnDecision
    hero_resolution: CombatActionResolution
    boss_resolution: CombatActionResolution
    hero_post_state: FighterState
    boss_post_state: FighterState
    combat_events: List[str]


class MatchResult(BaseModel):
    """
    Final outcome of a completed combat match simulation.
    """
    winner: Optional[str]  # "Hero", "Boss", or None for Stalemate / Draw
    total_rounds: int
    hero_final_hp: int
    boss_final_hp: int
    rounds_log: List[RoundLog]
    victory_reason: str
    difficulty: DifficultyLevel = DifficultyLevel.WARRIOR


class BossData(BaseModel):
    """
    Boss configuration and dossier loaded from content/bosses JSON definitions.
    """
    id: str
    name: str
    floor: int
    stats: FighterStats
    public_lore: str
    visible_hints: List[str]
    secret_personality_prompt: str
