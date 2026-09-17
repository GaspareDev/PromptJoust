from __future__ import annotations

import pytest
from core.types import (
    ActionType,
    StatusEffect,
    FighterStats,
    FighterState,
    HeroIntent,
    BossIntent,
    PsychWarfareEval,
    TurnDecision,
    BossData,
)
from core.rules import (
    calculate_base_damage,
    resolve_round_actions,
    STAMINA_COSTS,
    STAMINA_RECOVERY_PER_ROUND,
)
from core.engine import MatchEngine
from tests.test_helpers import DummyTestProvider as MockProvider


def make_decision(hero_act: ActionType, boss_act: ActionType, hero_psych: bool = False) -> TurnDecision:
    return TurnDecision(
        round_number=1,
        hero_intent=HeroIntent(action=hero_act, banter="Hero taunt", tactical_reasoning="Hero reason"),
        boss_intent=BossIntent(action=boss_act, banter="Boss taunt", tactical_reasoning="Boss reason"),
        psych_warfare_eval=PsychWarfareEval(
            hero_psych_successful=hero_psych,
            boss_psych_successful=False,
            reasoning="Psych eval",
        ),
        referee_summary="Summary",
    )


def test_calculate_base_damage():
    # max(10, ceil(ATK * 1.2 - DEF * 0.5))
    assert calculate_base_damage(20, 10) == 19
    assert calculate_base_damage(20, 25) == 12  # ceil(24 - 12.5) = 12
    assert calculate_base_damage(15, 15) == 11  # ceil(18 - 7.5) = 11
    assert calculate_base_damage(10, 30) == 10  # Floor is 10


def test_attack_vs_attack():
    hero_state = FighterState(name="Hero", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=20, def_=10)
    boss_state = FighterState(name="Boss", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=25, def_=12)

    decision = make_decision(ActionType.ATTACK, ActionType.ATTACK)
    hero_res, boss_res, events, hero_next_status, boss_next_status = resolve_round_actions(hero_state, boss_state, decision)

    # Hero deals ceil(20 * 1.2 - 12 * 0.5) = 18 dmg
    assert hero_res.damage_dealt == 18
    # Boss deals ceil(25 * 1.2 - 10 * 0.5) = 25 dmg
    assert boss_res.damage_dealt == 25
    assert hero_res.stamina_spent == 0
    assert boss_res.stamina_spent == 0


def test_attack_vs_defend():
    hero_state = FighterState(name="Hero", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=20, def_=10)
    boss_state = FighterState(name="Boss", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=25, def_=12)

    decision = make_decision(ActionType.ATTACK, ActionType.DEFEND)
    hero_res, boss_res, events, hero_next_status, boss_next_status = resolve_round_actions(hero_state, boss_state, decision)

    # Raw base = 18 dmg. DEFEND reduces to ceil(18 * 0.35) = 7 dmg
    assert hero_res.damage_dealt == 7
    assert boss_res.damage_dealt == 0
    assert boss_res.stamina_recovered == 10
    assert boss_res.stamina_spent == 5


def test_heavy_attack_vs_defend_guard_break():
    hero_state = FighterState(name="Hero", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=20, def_=10)
    boss_state = FighterState(name="Boss", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=25, def_=12)

    decision = make_decision(ActionType.HEAVY_ATTACK, ActionType.DEFEND)
    hero_res, boss_res, events, hero_next_status, boss_next_status = resolve_round_actions(hero_state, boss_state, decision)

    # Guard break: deals ceil(1.5 * ATK) = 30 dmg
    assert hero_res.damage_dealt == 30
    assert boss_res.damage_dealt == 0
    assert hero_res.stamina_spent == 25
    assert hero_res.status_inflicted == StatusEffect.STAGGERED
    assert boss_next_status == StatusEffect.STAGGERED


def test_heavy_attack_vs_dodge_counter():
    hero_state = FighterState(name="Hero", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=20, def_=10)
    boss_state = FighterState(name="Boss", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=25, def_=12)

    decision = make_decision(ActionType.HEAVY_ATTACK, ActionType.DODGE)
    hero_res, boss_res, events, hero_next_status, boss_next_status = resolve_round_actions(hero_state, boss_state, decision)

    # Heavy attack whiffs completely; dodger counters for 25 deterministic dmg
    assert hero_res.damage_dealt == 0
    assert boss_res.damage_dealt == 25
    assert hero_res.stamina_spent == 25
    assert boss_res.stamina_spent == 15


def test_attack_vs_dodge():
    hero_state = FighterState(name="Hero", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=20, def_=10)
    boss_state = FighterState(name="Boss", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=25, def_=12)

    decision = make_decision(ActionType.ATTACK, ActionType.DODGE)
    hero_res, boss_res, events, hero_next_status, boss_next_status = resolve_round_actions(hero_state, boss_state, decision)

    # Dodge fails against quick attack; hero deals full base dmg (18 dmg)
    assert hero_res.damage_dealt == 18
    assert boss_res.damage_dealt == 0
    assert boss_res.stamina_spent == 15


def test_psych_warfare_vs_attack():
    hero_state = FighterState(name="Hero", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=20, def_=10)
    boss_state = FighterState(name="Boss", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=25, def_=12)

    decision = make_decision(ActionType.PSYCH_WARFARE, ActionType.ATTACK, hero_psych=True)
    hero_res, boss_res, events, hero_next_status, boss_next_status = resolve_round_actions(hero_state, boss_state, decision)

    # Hero deals 0 physical dmg but applies STAGGERED
    assert hero_res.damage_dealt == 0
    assert hero_res.status_inflicted == StatusEffect.STAGGERED
    assert boss_next_status == StatusEffect.STAGGERED
    # Boss deals full base damage (25 dmg)
    assert boss_res.damage_dealt == 25


def test_stamina_exhaustion_downgrade():
    # Hero has only 5 stamina but attempts HEAVY_ATTACK (needs 25)
    hero_state = FighterState(name="Hero", max_hp=100, current_hp=100, max_sta=100, current_sta=5, atk=20, def_=10)
    boss_state = FighterState(name="Boss", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=25, def_=12)

    decision = make_decision(ActionType.HEAVY_ATTACK, ActionType.ATTACK)
    hero_res, boss_res, events, hero_next_status, boss_next_status = resolve_round_actions(hero_state, boss_state, decision)

    # Action downgraded to ATTACK
    assert hero_res.action == ActionType.ATTACK
    assert hero_res.stamina_spent == 0
    assert any("[EXHAUSTION]" in ev for ev in events)


def test_match_engine_full_simulation():
    boss = BossData(
        id="test_boss",
        name="Test Dummy",
        floor=1,
        stats=FighterStats(hp=60, atk=15, def_=10, sta=30),
        public_lore="A sparring construct.",
        visible_hints=["Vulnerable to continuous strikes."],
        secret_personality_prompt="You are a test dummy. Use only ATTACK.",
    )
    hero_stats = FighterStats(hp=110, atk=25, def_=15, sta=55)

    engine = MatchEngine(
        hero_name="Hero",
        hero_stats=hero_stats,
        hero_prompt="Strike with heavy attacks to dismantle the dummy rapidly.",
        boss=boss,
        provider=MockProvider(),
    )

    result = engine.run_match()
    assert result.total_rounds <= 10
    assert len(result.rounds_log) == result.total_rounds
    assert result.winner in ("Hero", "Boss", None)

