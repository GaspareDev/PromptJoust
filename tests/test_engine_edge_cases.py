from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from core.types import (
    FighterStats,
    FighterState,
    StatusEffect,
    ActionType,
    BossData,
    TurnDecision,
    HeroIntent,
    BossIntent,
    PsychWarfareEval,
)
from core.engine import MatchEngine
from core.sanitizer import (
    validate_and_allocate_stats,
    sanitize_tactical_prompt,
    SanitizationError,
)
from core.referee import parse_and_validate_turn_decision, detect_jailbreak_keywords
from tests.test_helpers import DummyTestProvider as MockProvider


def dummy_boss(hp: int = 100, atk: int = 20, def_: int = 10, sta: int = 50) -> BossData:
    return BossData(
        id="test_boss",
        name="Dummy Boss",
        floor=1,
        stats=FighterStats(hp=hp, atk=atk, def_=def_, sta=sta),
        public_lore="sparring dummy",
        visible_hints=["Hint 1"],
        secret_personality_prompt="You are a dummy.",
    )


def test_callbacks_in_match_engine():
    pre_called = []
    round_called = []

    def on_pre(r_num: int):
        pre_called.append(r_num)

    def on_round(log):
        round_called.append(log.round_number)

    hero_stats = FighterStats(hp=100, atk=20, def_=10, sta=50)
    engine = MatchEngine(
        hero_name="Hero",
        hero_stats=hero_stats,
        hero_prompt="Attack fast.",
        boss=dummy_boss(hp=50, atk=10, def_=5),
        provider=MockProvider(),
        pre_round_callback=on_pre,
        round_callback=on_round,
    )

    result = engine.run_match()
    assert len(pre_called) == result.total_rounds
    assert len(round_called) == result.total_rounds


def test_boss_victory_outcome():
    # Boss crushes weak hero in 1 round (30 atk heavy attack guard break deals 36 dmg vs 5 hp)
    hero_stats = FighterStats(hp=5, atk=5, def_=5, sta=10)
    boss = dummy_boss(hp=100, atk=30, def_=20, sta=100)

    class CrushingProvider:
        def generate_turn_decision(self, system_prompt, user_prompt, schema):
            return TurnDecision(
                round_number=1,
                hero_intent=HeroIntent(action=ActionType.DEFEND, banter="Help!", tactical_reasoning="blocking"),
                boss_intent=BossIntent(action=ActionType.HEAVY_ATTACK, banter="Die!", tactical_reasoning="crushing"),
                psych_warfare_eval=PsychWarfareEval(hero_psych_successful=False, boss_psych_successful=False, reasoning="none"),
                referee_summary="Boss crushes hero guard",
            )

    engine = MatchEngine(
        hero_name="Hero",
        hero_stats=hero_stats,
        hero_prompt="Defend myself.",
        boss=boss,
        provider=CrushingProvider(),
    )
    result = engine.run_match()
    assert result.winner == "Boss"
    assert "overwhelmed" in result.victory_reason


def test_mutual_annihilation():
    # Both fighters deal lethal 25 dmg to each other with 5 HP
    hero_stats = FighterStats(hp=5, atk=30, def_=5, sta=50)
    boss = dummy_boss(hp=5, atk=30, def_=5, sta=50)

    class FatalClashProvider:
        def generate_turn_decision(self, system_prompt, user_prompt, schema):
            return TurnDecision(
                round_number=1,
                hero_intent=HeroIntent(action=ActionType.ATTACK, banter="All or nothing!", tactical_reasoning="strike"),
                boss_intent=BossIntent(action=ActionType.ATTACK, banter="Perish!", tactical_reasoning="strike"),
                psych_warfare_eval=PsychWarfareEval(hero_psych_successful=False, boss_psych_successful=False, reasoning="none"),
                referee_summary="Both land fatal blows.",
            )

    engine = MatchEngine(
        hero_name="Hero",
        hero_stats=hero_stats,
        hero_prompt="Attack.",
        boss=boss,
        provider=FatalClashProvider(),
    )
    result = engine.run_match()
    assert result.winner is None
    assert "Mutual annihilation" in result.victory_reason



def test_stalemate_equal_hp_at_round_5():
    hero_stats = FighterStats(hp=100, atk=15, def_=10, sta=50)
    boss = dummy_boss(hp=100, atk=15, def_=10, sta=50)

    class PassiveProvider:
        def generate_turn_decision(self, system_prompt, user_prompt, schema):
            return TurnDecision(
                round_number=1,
                hero_intent=HeroIntent(action=ActionType.DEFEND, banter="Pacing", tactical_reasoning="defending"),
                boss_intent=BossIntent(action=ActionType.DEFEND, banter="Watching", tactical_reasoning="defending"),
                psych_warfare_eval=PsychWarfareEval(hero_psych_successful=False, boss_psych_successful=False, reasoning="none"),
                referee_summary="Both wait.",
            )

    engine = MatchEngine(
        hero_name="Hero",
        hero_stats=hero_stats,
        hero_prompt="Wait and observe.",
        boss=boss,
        provider=PassiveProvider(),
    )
    result = engine.run_match()
    assert result.total_rounds == 10
    assert result.winner is None
    assert "Stalemate draw" in result.victory_reason



def test_provider_exception_fallback():
    hero_stats = FighterStats(hp=100, atk=20, def_=10, sta=50)
    boss = dummy_boss(hp=100, atk=20, def_=10, sta=50)

    class FaultyProvider:
        def generate_turn_decision(self, system_prompt, user_prompt, schema):
            raise RuntimeError("API Connection timeout 504")

    engine = MatchEngine(
        hero_name="Hero",
        hero_stats=hero_stats,
        hero_prompt="Advance.",
        boss=boss,
        provider=FaultyProvider(),
    )
    # Should safely fallback to TurnDecision without crashing the match
    result = engine.run_match()
    assert result.total_rounds >= 1
    assert "arbitration error" in result.rounds_log[0].turn_decision.hero_intent.tactical_reasoning


def test_sanitizer_validation_bounds():
    with pytest.raises(SanitizationError, match="must be a non-negative integer"):
        validate_and_allocate_stats(hp_bonus=20, atk_bonus=-1, def_bonus=0, sta_bonus=1)

    with pytest.raises(SanitizationError, match="cannot be empty"):
        sanitize_tactical_prompt(None)

    with pytest.raises(SanitizationError, match="cannot be empty"):
        sanitize_tactical_prompt(12345)


def test_referee_regex_extraction_and_empty_banters():
    # Messy response with text wrapping the json and empty banters
    messy_response = """
    Here is the arbitration result:
    {
        "round_number": 2,
        "hero_intent": {
            "action": "DODGE",
            "banter": "",
            "tactical_reasoning": "Evading heavy strike"
        },
        "boss_intent": {
            "action": "HEAVY_ATTACK",
            "banter": "   ",
            "tactical_reasoning": "Smashing down"
        },
        "psych_warfare_eval": {
            "hero_psych_successful": false,
            "boss_psych_successful": false,
            "reasoning": "none"
        },
        "referee_summary": "Hero attempts dodge"
    }
    Hope this helps!
    """
    decision = parse_and_validate_turn_decision(messy_response, expected_round=2)
    assert decision.round_number == 2
    assert decision.hero_intent.action == ActionType.DODGE
    # Banters were filled with defaults
    assert len(decision.hero_intent.banter) > 0
    assert len(decision.boss_intent.banter) > 0


def test_hero_victory_on_round_5_timeout():
    # Hero has higher HP at the end of 5 rounds
    hero_stats = FighterStats(hp=120, atk=15, def_=10, sta=50)
    boss = dummy_boss(hp=80, atk=15, def_=10, sta=50)

    class PassiveProvider:
        def generate_turn_decision(self, system_prompt, user_prompt, schema):
            return TurnDecision(
                round_number=1,
                hero_intent=HeroIntent(action=ActionType.DEFEND, banter="Guarding", tactical_reasoning="defending"),
                boss_intent=BossIntent(action=ActionType.DEFEND, banter="Guarding", tactical_reasoning="defending"),
                psych_warfare_eval=PsychWarfareEval(hero_psych_successful=False, boss_psych_successful=False, reasoning="none"),
                referee_summary="Defensive standoff.",
            )

    engine = MatchEngine(
        hero_name="Hero",
        hero_stats=hero_stats,
        hero_prompt="Hold the line.",
        boss=boss,
        provider=PassiveProvider(),
    )
    result = engine.run_match()
    assert result.total_rounds == 10
    assert result.winner == "Hero"
    assert "tactical decision" in result.victory_reason


def test_boss_victory_on_round_10_timeout():
    # Boss has higher HP at the end of 10 rounds
    hero_stats = FighterStats(hp=60, atk=15, def_=10, sta=50)
    boss = dummy_boss(hp=120, atk=15, def_=10, sta=50)

    class PassiveProvider:
        def generate_turn_decision(self, system_prompt, user_prompt, schema):
            return TurnDecision(
                round_number=1,
                hero_intent=HeroIntent(action=ActionType.DEFEND, banter="Guarding", tactical_reasoning="defending"),
                boss_intent=BossIntent(action=ActionType.DEFEND, banter="Guarding", tactical_reasoning="defending"),
                psych_warfare_eval=PsychWarfareEval(hero_psych_successful=False, boss_psych_successful=False, reasoning="none"),
                referee_summary="Defensive standoff.",
            )

    engine = MatchEngine(
        hero_name="Hero",
        hero_stats=hero_stats,
        hero_prompt="Hold the line.",
        boss=boss,
        provider=PassiveProvider(),
    )
    result = engine.run_match()
    assert result.total_rounds == 10
    assert result.winner == "Boss"
    assert "defended the floor" in result.victory_reason



def test_status_duration_decay():
    hero_stats = FighterStats(hp=100, atk=20, def_=10, sta=50)
    boss = dummy_boss(hp=100, atk=20, def_=10, sta=50)

    class StaggerProvider:
        def generate_turn_decision(self, system_prompt, user_prompt, schema):
            # Round 1 applies Heavy vs Defend -> Boss is Staggered
            return TurnDecision(
                round_number=1,
                hero_intent=HeroIntent(action=ActionType.HEAVY_ATTACK, banter="Heavy!", tactical_reasoning="smash"),
                boss_intent=BossIntent(action=ActionType.DEFEND, banter="Block", tactical_reasoning="defend"),
                psych_warfare_eval=PsychWarfareEval(hero_psych_successful=False, boss_psych_successful=False, reasoning="none"),
                referee_summary="Guard broken",
            )

    engine = MatchEngine(
        hero_name="Hero",
        hero_stats=hero_stats,
        hero_prompt="Smash.",
        boss=boss,
        provider=StaggerProvider(),
    )
    # Execute 1 round -> boss gets STAGGERED
    log1 = engine._execute_round(1)
    assert engine.boss_state.status == StatusEffect.STAGGERED
    assert engine.boss_state.status_duration == 1

    # Execute round 2 where both defend -> status duration decrements and clears to NORMAL
    class DefendProvider:
        def generate_turn_decision(self, system_prompt, user_prompt, schema):
            return TurnDecision(
                round_number=2,
                hero_intent=HeroIntent(action=ActionType.DEFEND, banter="Wait", tactical_reasoning="wait"),
                boss_intent=BossIntent(action=ActionType.DEFEND, banter="Wait", tactical_reasoning="wait"),
                psych_warfare_eval=PsychWarfareEval(hero_psych_successful=False, boss_psych_successful=False, reasoning="none"),
                referee_summary="Wait",
            )
    engine.provider = DefendProvider()
    log2 = engine._execute_round(2)
    assert engine.boss_state.status == StatusEffect.NORMAL
    assert engine.boss_state.status_duration == 0


def test_provider_returns_json_string():
    import json
    hero_stats = FighterStats(hp=100, atk=20, def_=10, sta=50)
    boss = dummy_boss(hp=50, atk=10, def_=5)

    class JsonStringProvider:
        def generate_turn_decision(self, system_prompt, user_prompt, schema):
            return json.dumps({
                "round_number": 1,
                "hero_intent": {"action": "ATTACK", "banter": "Strike!", "tactical_reasoning": "Standard"},
                "boss_intent": {"action": "DEFEND", "banter": "Shield!", "tactical_reasoning": "Block"},
                "psych_warfare_eval": {"hero_psych_successful": False, "boss_psych_successful": False, "reasoning": "none"},
                "referee_summary": "Hero strikes boss shield",
            })

    engine = MatchEngine(
        hero_name="Hero",
        hero_stats=hero_stats,
        hero_prompt="Attack.",
        boss=boss,
        provider=JsonStringProvider(),
    )
    result = engine.run_match()
    assert result.total_rounds >= 1


