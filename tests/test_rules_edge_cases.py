from __future__ import annotations

import math
import pytest
from core.types import (
    ActionType,
    StatusEffect,
    FighterState,
    HeroIntent,
    BossIntent,
    PsychWarfareEval,
    TurnDecision,
)
from core.rules import (
    calculate_base_damage,
    resolve_round_actions,
    STAMINA_COSTS,
    STAMINA_RECOVERY_PER_ROUND,
)


def make_decision(
    hero_act: ActionType,
    boss_act: ActionType,
    hero_psych: bool = False,
    boss_psych: bool = False,
) -> TurnDecision:
    return TurnDecision(
        round_number=1,
        hero_intent=HeroIntent(action=hero_act, banter="Hero shout", tactical_reasoning="Hero reason"),
        boss_intent=BossIntent(action=boss_act, banter="Boss shout", tactical_reasoning="Boss reason"),
        psych_warfare_eval=PsychWarfareEval(
            hero_psych_successful=hero_psych,
            boss_psych_successful=boss_psych,
            reasoning="Psych eval",
        ),
        referee_summary="Summary",
    )


def test_calculate_base_damage_floor():
    assert calculate_base_damage(10, 20) == 5
    assert calculate_base_damage(10, 10) == 5
    assert calculate_base_damage(30, 10) == 20


def test_defend_vs_attack_hero_defending():
    hero_state = FighterState(name="Hero", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=20, def_=10)
    boss_state = FighterState(name="Boss", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=25, def_=12)

    decision = make_decision(ActionType.DEFEND, ActionType.ATTACK)
    hero_res, boss_res, events, hero_next_status, boss_next_status = resolve_round_actions(hero_state, boss_state, decision)

    # Boss raw base = 25 - 10 = 15. Defend reduces to ceil(15 * 0.25) = 4
    assert boss_res.damage_dealt == 4
    assert hero_res.damage_dealt == 0
    assert hero_res.stamina_recovered == 10
    assert hero_res.stamina_spent == 5


def test_defend_vs_heavy_attack_guard_break_on_hero():
    hero_state = FighterState(name="Hero", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=20, def_=10)
    boss_state = FighterState(name="Boss", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=25, def_=12)

    decision = make_decision(ActionType.DEFEND, ActionType.HEAVY_ATTACK)
    hero_res, boss_res, events, hero_next_status, boss_next_status = resolve_round_actions(hero_state, boss_state, decision)

    # Boss Guard break: ceil(25 * 1.2) = 30 dmg
    assert boss_res.damage_dealt == 30
    assert hero_res.damage_dealt == 0
    assert boss_res.status_inflicted == StatusEffect.STAGGERED
    assert hero_next_status == StatusEffect.STAGGERED
    assert any("GUARD BREAK!" in ev for ev in events)


def test_dodge_vs_heavy_attack_hero_counters():
    hero_state = FighterState(name="Hero", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=20, def_=10)
    boss_state = FighterState(name="Boss", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=25, def_=12)

    decision = make_decision(ActionType.DODGE, ActionType.HEAVY_ATTACK)
    hero_res, boss_res, events, hero_next_status, boss_next_status = resolve_round_actions(hero_state, boss_state, decision)

    assert boss_res.damage_dealt == 0
    assert hero_res.damage_dealt == 20
    assert hero_res.stamina_spent == 15
    assert boss_res.stamina_spent == 25


def test_dodge_vs_attack_hero_dodge_fails():
    hero_state = FighterState(name="Hero", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=20, def_=10)
    boss_state = FighterState(name="Boss", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=25, def_=12)

    decision = make_decision(ActionType.DODGE, ActionType.ATTACK)
    hero_res, boss_res, events, hero_next_status, boss_next_status = resolve_round_actions(hero_state, boss_state, decision)

    assert hero_res.damage_dealt == 0
    assert boss_res.damage_dealt == 15  # 25 - 10 = 15
    assert hero_res.stamina_spent == 15


def test_heavy_attack_vs_heavy_attack():
    hero_state = FighterState(name="Hero", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=20, def_=10)
    boss_state = FighterState(name="Boss", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=25, def_=12)

    decision = make_decision(ActionType.HEAVY_ATTACK, ActionType.HEAVY_ATTACK)
    hero_res, boss_res, events, hero_next_status, boss_next_status = resolve_round_actions(hero_state, boss_state, decision)

    # ceil(20 * 1.8) = 36 dmg, ceil(25 * 1.8) = 45 dmg
    assert hero_res.damage_dealt == 36
    assert boss_res.damage_dealt == 45
    assert any("Titanic Collision!" in ev for ev in events)


def test_heavy_attack_vs_attack_and_vice_versa():
    hero_state = FighterState(name="Hero", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=20, def_=10)
    boss_state = FighterState(name="Boss", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=25, def_=12)

    # 1. Hero Heavy, Boss Attack
    d1 = make_decision(ActionType.HEAVY_ATTACK, ActionType.ATTACK)
    h1, b1, ev1, _, _ = resolve_round_actions(hero_state, boss_state, d1)
    assert h1.damage_dealt == 36
    assert b1.damage_dealt == 15

    # 2. Hero Attack, Boss Heavy
    d2 = make_decision(ActionType.ATTACK, ActionType.HEAVY_ATTACK)
    h2, b2, ev2, _, _ = resolve_round_actions(hero_state, boss_state, d2)
    assert h2.damage_dealt == 8  # 20 - 12
    assert b2.damage_dealt == 45  # ceil(25 * 1.8)


def test_defend_and_dodge_neutral_matchups():
    hero_state = FighterState(name="Hero", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=20, def_=10)
    boss_state = FighterState(name="Boss", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=25, def_=12)

    # DEFEND vs DEFEND
    d_dd = make_decision(ActionType.DEFEND, ActionType.DEFEND)
    h_res, b_res, ev, _, _ = resolve_round_actions(hero_state, boss_state, d_dd)
    assert h_res.damage_dealt == 0 and b_res.damage_dealt == 0
    assert any("Both fighters hold defensive stances" in e for e in ev)

    # DODGE vs DODGE
    d_ev = make_decision(ActionType.DODGE, ActionType.DODGE)
    h_res, b_res, ev, _, _ = resolve_round_actions(hero_state, boss_state, d_ev)
    assert h_res.damage_dealt == 0 and b_res.damage_dealt == 0
    assert any("synchronized evasive maneuvers" in e for e in ev)

    # DEFEND vs DODGE
    d_df_dg = make_decision(ActionType.DEFEND, ActionType.DODGE)
    h_res, b_res, ev, _, _ = resolve_round_actions(hero_state, boss_state, d_df_dg)
    assert any("braces for impact" in e for e in ev)

    # DODGE vs DEFEND
    d_dg_df = make_decision(ActionType.DODGE, ActionType.DEFEND)
    h_res, b_res, ev, _, _ = resolve_round_actions(hero_state, boss_state, d_dg_df)
    assert any("dances away cautiously" in e for e in ev)


def test_psych_warfare_all_branches():
    hero_state = FighterState(name="Hero", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=20, def_=10)
    boss_state = FighterState(name="Boss", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=25, def_=12)

    # Hero psych failed against boss heavy attack
    d1 = make_decision(ActionType.PSYCH_WARFARE, ActionType.HEAVY_ATTACK, hero_psych=False)
    h1, b1, ev1, _, _ = resolve_round_actions(hero_state, boss_state, d1)
    assert b1.damage_dealt == 45
    assert any("PSYCH DEFLECTED" in e for e in ev1)

    # Boss psych success against hero defend
    d2 = make_decision(ActionType.DEFEND, ActionType.PSYCH_WARFARE, boss_psych=True)
    h2, b2, ev2, hero_next, boss_next = resolve_round_actions(hero_state, boss_state, d2)
    assert hero_next == StatusEffect.CONFUSED
    assert any("CONFUSED next round" in e for e in ev2)

    # Boss psych failed against hero attack
    d3 = make_decision(ActionType.ATTACK, ActionType.PSYCH_WARFARE, boss_psych=False)
    h3, b3, ev3, _, _ = resolve_round_actions(hero_state, boss_state, d3)
    assert h3.damage_dealt == 8
    assert any("PSYCH DEFLECTED" in e for e in ev3)

    # Boss psych against hero heavy attack
    d4 = make_decision(ActionType.HEAVY_ATTACK, ActionType.PSYCH_WARFARE, boss_psych=False)
    h4, b4, ev4, _, _ = resolve_round_actions(hero_state, boss_state, d4)
    assert h4.damage_dealt == 36


def test_confused_states_and_boss_exhaustion():
    hero_state = FighterState(name="Hero", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=20, def_=10)
    # Boss has only 10 stamina and tries HEAVY_ATTACK (needs 20)
    boss_state = FighterState(name="Boss", max_hp=100, current_hp=100, max_sta=100, current_sta=10, atk=25, def_=12)

    # Boss exhaustion downgrade
    d1 = make_decision(ActionType.ATTACK, ActionType.HEAVY_ATTACK)
    h1, b1, ev1, _, _ = resolve_round_actions(hero_state, boss_state, d1)
    assert b1.action == ActionType.ATTACK
    assert any("[EXHAUSTION]" in e for e in ev1)

    # Hero & Boss both CONFUSED
    d2 = make_decision(ActionType.CONFUSED, ActionType.CONFUSED)
    h2, b2, ev2, _, _ = resolve_round_actions(hero_state, boss_state, d2)
    assert h2.damage_dealt == 0
    assert b2.damage_dealt == 0
    assert any("[CONFUSED]" in e for e in ev2)

    # Hero CONFUSED vs Boss ATTACK
    d_ca = make_decision(ActionType.CONFUSED, ActionType.ATTACK)
    h_ca, b_ca, ev_ca, _, _ = resolve_round_actions(hero_state, boss_state, d_ca)
    assert b_ca.damage_dealt == (25 - 10)

    # Hero CONFUSED vs Boss HEAVY_ATTACK
    boss_state.current_sta = 50
    d3 = make_decision(ActionType.CONFUSED, ActionType.HEAVY_ATTACK)
    h3, b3, ev3, _, _ = resolve_round_actions(hero_state, boss_state, d3)
    assert b3.damage_dealt == math.ceil(25 * 1.8)
    assert b3.action == ActionType.HEAVY_ATTACK


    # Boss CONFUSED vs Hero ATTACK
    d4 = make_decision(ActionType.ATTACK, ActionType.CONFUSED)
    h4, b4, ev4, _, _ = resolve_round_actions(hero_state, boss_state, d4)
    assert h4.damage_dealt > 0

    # Boss CONFUSED vs Hero HEAVY_ATTACK
    d5 = make_decision(ActionType.HEAVY_ATTACK, ActionType.CONFUSED)
    h5, b5, ev5, _, _ = resolve_round_actions(hero_state, boss_state, d5)
    assert h5.damage_dealt > 0



def test_staggered_damage_multiplier():
    # Staggered hero takes 25% extra damage
    hero_state = FighterState(name="Hero", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=20, def_=10, status=StatusEffect.STAGGERED)
    boss_state = FighterState(name="Boss", max_hp=100, current_hp=100, max_sta=100, current_sta=50, atk=25, def_=12)

    decision = make_decision(ActionType.ATTACK, ActionType.ATTACK)
    hero_res, boss_res, events, _, _ = resolve_round_actions(hero_state, boss_state, decision)

    # Base damage: 25 - 10 = 15. Staggered multiplier: ceil(15 * 1.25) = 19
    assert boss_res.damage_dealt == 19
