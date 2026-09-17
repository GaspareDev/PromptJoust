"""
Unit tests for models package and core.types backward-compatibility shim.
Ensures 100% test coverage across models.enums, models.combat, models.api, models.__init__, and core.types.
"""

import pytest
from pydantic import ValidationError

import models
import core.types as legacy_types
from models.enums import ActionType, StatusEffect, DifficultyLevel
from models.combat import (
    DifficultyConfig,
    DIFFICULTY_CONFIGS,
    FighterStats,
    FighterState,
    HeroIntent,
    BossIntent,
    PsychWarfareEval,
    TurnDecision,
    CombatActionResolution,
    RoundLog,
    MatchResult,
    BossData,
)
from models.api import SimulationRequest, ProviderOption


def test_models_package_exports():
    """Verifies all expected symbols are exported from models and core.types."""
    expected_symbols = [
        "ActionType",
        "StatusEffect",
        "DifficultyLevel",
        "DifficultyConfig",
        "DIFFICULTY_CONFIGS",
        "FighterStats",
        "FighterState",
        "HeroIntent",
        "BossIntent",
        "PsychWarfareEval",
        "TurnDecision",
        "CombatActionResolution",
        "RoundLog",
        "MatchResult",
        "BossData",
        "SimulationRequest",
        "ProviderOption",
    ]
    for sym in expected_symbols:
        assert hasattr(models, sym), f"Missing {sym} in models"
        assert hasattr(legacy_types, sym), f"Missing {sym} in core.types"
        assert getattr(models, sym) is getattr(legacy_types, sym)


def test_enums_values():
    """Verifies canonical values and string inheritance of all enums."""
    assert ActionType.ATTACK.value == "ATTACK"
    assert ActionType.HEAVY_ATTACK.value == "HEAVY_ATTACK"
    assert ActionType.DEFEND.value == "DEFEND"
    assert ActionType.DODGE.value == "DODGE"
    assert ActionType.PSYCH_WARFARE.value == "PSYCH_WARFARE"
    assert ActionType.CONFUSED.value == "CONFUSED"

    assert StatusEffect.NORMAL.value == "NORMAL"
    assert StatusEffect.STAGGERED.value == "STAGGERED"
    assert StatusEffect.ENRAGED.value == "ENRAGED"
    assert StatusEffect.CONFUSED.value == "CONFUSED"

    assert DifficultyLevel.APPRENTICE.value == "apprentice"
    assert DifficultyLevel.WARRIOR.value == "warrior"
    assert DifficultyLevel.GRANDMASTER.value == "grandmaster"


def test_difficulty_configs():
    """Verifies all difficulty tier configs and attributes."""
    assert len(DIFFICULTY_CONFIGS) == 3
    apprentice = DIFFICULTY_CONFIGS[DifficultyLevel.APPRENTICE]
    assert apprentice.valor_points == 25
    assert apprentice.boss_hp_multiplier == 0.85
    assert apprentice.boss_stamina_recovery == 5

    warrior = DIFFICULTY_CONFIGS[DifficultyLevel.WARRIOR]
    assert warrior.valor_points == 20
    assert warrior.boss_hp_multiplier == 1.0

    grandmaster = DIFFICULTY_CONFIGS[DifficultyLevel.GRANDMASTER]
    assert grandmaster.valor_points == 15
    assert grandmaster.max_prompt_length == 200
    assert grandmaster.boss_hp_multiplier == 1.20
    assert grandmaster.boss_stamina_recovery == 8


def test_fighter_stats_model():
    """Tests FighterStats validation, aliases, immutability, and to_dict method."""
    stats = FighterStats(hp=120, atk=20, **{"def": 15}, sta=60)
    assert stats.hp == 120
    assert stats.atk == 20
    assert stats.def_ == 15
    assert stats.sta == 60

    d = stats.to_dict()
    assert d == {"hp": 120, "atk": 20, "def": 15, "sta": 60}

    # Frozen check
    with pytest.raises(ValidationError):
        stats.hp = 130


def test_fighter_state_model():
    """Tests FighterState creation from stats and is_alive method."""
    stats = FighterStats(hp=100, atk=15, **{"def": 10}, sta=50)
    state = FighterState.from_stats("Champion", stats)
    assert state.name == "Champion"
    assert state.current_hp == 100
    assert state.max_hp == 100
    assert state.current_sta == 50
    assert state.max_sta == 100
    assert state.atk == 15
    assert state.def_ == 10
    assert state.status == StatusEffect.NORMAL
    assert state.status_duration == 0
    assert state.is_alive() is True

    state.current_hp = 0
    assert state.is_alive() is False


def test_intent_and_decision_models():
    """Tests HeroIntent, BossIntent, PsychWarfareEval, and TurnDecision models."""
    hero_intent = HeroIntent(
        action=ActionType.ATTACK,
        banter="Taste steel!",
        tactical_reasoning="Quick strike to exploit foe stance.",
    )
    boss_intent = BossIntent(
        action=ActionType.DEFEND,
        banter="Your blade is frail.",
        tactical_reasoning="Raise armor plating.",
    )
    psych = PsychWarfareEval(
        hero_psych_successful=False,
        boss_psych_successful=False,
        reasoning="No psychological maneuvers used.",
    )
    decision = TurnDecision(
        round_number=1,
        hero_intent=hero_intent,
        boss_intent=boss_intent,
        psych_warfare_eval=psych,
        referee_summary="The duel begins with a clash of steel.",
    )
    assert decision.round_number == 1
    assert decision.hero_intent.action == ActionType.ATTACK
    assert decision.boss_intent.action == ActionType.DEFEND


def test_combat_action_resolution_and_round_log():
    """Tests CombatActionResolution and RoundLog models."""
    res_hero = CombatActionResolution(
        actor="Hero",
        action=ActionType.ATTACK,
        stamina_spent=0,
        damage_dealt=10,
        stamina_recovered=5,
        status_inflicted=StatusEffect.STAGGERED,
        notes="Clean hit.",
    )
    res_boss = CombatActionResolution(
        actor="Boss",
        action=ActionType.DEFEND,
        stamina_spent=5,
        damage_dealt=0,
        stamina_recovered=10,
    )
    assert res_hero.damage_dealt == 10
    assert res_hero.status_inflicted == StatusEffect.STAGGERED
    assert res_boss.status_inflicted is None

    stats = FighterStats(hp=100, atk=15, **{"def": 10}, sta=50)
    hero_state = FighterState.from_stats("Hero", stats)
    boss_state = FighterState.from_stats("Boss", stats)
    hero_intent = HeroIntent(action=ActionType.ATTACK, banter="Fight!", tactical_reasoning="Go")
    boss_intent = BossIntent(action=ActionType.DEFEND, banter="Block!", tactical_reasoning="Block")
    psych = PsychWarfareEval(hero_psych_successful=False, boss_psych_successful=False, reasoning="")
    decision = TurnDecision(
        round_number=1,
        hero_intent=hero_intent,
        boss_intent=boss_intent,
        psych_warfare_eval=psych,
        referee_summary="Clash",
    )

    log = RoundLog(
        round_number=1,
        hero_pre_state=hero_state,
        boss_pre_state=boss_state,
        turn_decision=decision,
        hero_resolution=res_hero,
        boss_resolution=res_boss,
        hero_post_state=hero_state,
        boss_post_state=boss_state,
        combat_events=["Hero struck Boss for 10 DMG."],
    )
    assert log.round_number == 1
    assert len(log.combat_events) == 1


def test_match_result_and_boss_data():
    """Tests MatchResult and BossData models."""
    match = MatchResult(
        winner="Hero",
        total_rounds=3,
        hero_final_hp=65,
        boss_final_hp=0,
        rounds_log=[],
        victory_reason="Boss HP depleted.",
        difficulty=DifficultyLevel.GRANDMASTER,
    )
    assert match.winner == "Hero"
    assert match.difficulty == DifficultyLevel.GRANDMASTER

    boss = BossData(
        id="boss_test",
        name="Test Golem",
        floor=1,
        stats=FighterStats(hp=80, atk=12, **{"def": 8}, sta=40),
        public_lore="A test automaton.",
        visible_hints=["Weak to tests."],
        secret_personality_prompt="Dodge everything.",
    )
    assert boss.id == "boss_test"
    assert boss.stats.hp == 80


def test_api_models():
    """Tests SimulationRequest and ProviderOption schemas."""
    req = SimulationRequest(
        boss_id="boss_level_01",
        hero_name="Knight",
        tactical_prompt="Defend and strike.",
        hp_bonus=8,
        atk_bonus=7,
        def_bonus=5,
        sta_bonus=0,
        difficulty=DifficultyLevel.WARRIOR,
        provider="ollama",
    )
    assert req.boss_id == "boss_level_01"
    assert req.difficulty == DifficultyLevel.WARRIOR
    assert req.api_key is None
    assert req.model is None

    provider_opt = ProviderOption(
        id="ollama",
        name="Ollama Local",
        requires_api_key=False,
        default_model="llama3",
    )
    assert provider_opt.id == "ollama"
    assert provider_opt.requires_api_key is False
