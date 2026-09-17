"""
PromptJoust Deterministic Combat Rules & Mathematical Engine.

Implements pure deterministic resolution of combat actions for each round:
- Stamina verification and auto-downgrade on exhaustion
- Rock-Paper-Scissors resolution matrix:
    * HEAVY_ATTACK vs DEFEND  -> GUARD BREAK (high damage + STAGGERED status)
    * HEAVY_ATTACK vs DODGE   -> DODGE COUNTER (0 incoming dmg + 20 counter dmg)
    * ATTACK vs DODGE         -> Dodge fails, full attack damage dealt
    * DEFEND vs ATTACK        -> Damage reduced to 25% + 10 stamina recovered
    * PSYCH_WARFARE           -> Evaluates referee mind games and status infliction
- Damage scaling based on ATK, DEF, and vulnerability multipliers (STAGGERED: 1.25x)
"""

from __future__ import annotations

import math
from typing import Tuple, List, Optional
from models import (
    ActionType,
    StatusEffect,
    FighterState,
    CombatActionResolution,
    TurnDecision,
)

# Canonical stamina costs for each action
STAMINA_COSTS = {
    ActionType.ATTACK: 0,
    ActionType.HEAVY_ATTACK: 25,
    ActionType.DEFEND: 5,
    ActionType.DODGE: 15,
    ActionType.PSYCH_WARFARE: 10,
    ActionType.CONFUSED: 0,
}

# Base stamina recovered by both fighters at the end of every round
STAMINA_RECOVERY_PER_ROUND = 5


def calculate_base_damage(atk: int, def_: int) -> int:
    """
    Calculates raw unmitigated damage between an attacker and defender.
    Formula: max(10, math.ceil(atk * 1.2 - def_ * 0.5)) ensuring a dynamic damage floor.
    """
    return max(10, math.ceil(atk * 1.2 - def_ * 0.5))


def resolve_round_actions(
    hero_state: FighterState,
    boss_state: FighterState,
    turn_decision: TurnDecision,
) -> Tuple[CombatActionResolution, CombatActionResolution, List[str], Optional[StatusEffect], Optional[StatusEffect]]:
    """
    Deterministically resolves combat mathematics and state updates for a single round.

    Args:
        hero_state: Live state of the Hero before this round.
        boss_state: Live state of the Boss before this round.
        turn_decision: Validated TurnDecision containing intents from both fighters.

    Returns:
        hero_res: CombatActionResolution for Hero (damage dealt, stamina spent/recovered, notes).
        boss_res: CombatActionResolution for Boss (damage dealt, stamina spent/recovered, notes).
        events: Human-readable combat event log lines for the round.
        hero_next_status: StatusEffect to apply to Hero for the next round (if any).
        boss_next_status: StatusEffect to apply to Boss for the next round (if any).
    """
    events: List[str] = []

    hero_action = turn_decision.hero_intent.action
    boss_action = turn_decision.boss_intent.action

    # Check for stamina exhaustion and adjust action if needed
    hero_cost = STAMINA_COSTS.get(hero_action, 0)
    boss_cost = STAMINA_COSTS.get(boss_action, 0)

    if hero_state.current_sta < hero_cost:
        events.append(f"[EXHAUSTION] {hero_state.name} lacks stamina for {hero_action.value} (has {hero_state.current_sta}/{hero_cost})! Action downgraded to standard ATTACK.")
        hero_action = ActionType.ATTACK
        hero_cost = 0

    if boss_state.current_sta < boss_cost:
        events.append(f"[EXHAUSTION] {boss_state.name} lacks stamina for {boss_action.value} (has {boss_state.current_sta}/{boss_cost})! Action downgraded to standard ATTACK.")
        boss_action = ActionType.ATTACK
        boss_cost = 0

    hero_damage_dealt = 0
    boss_damage_dealt = 0
    hero_sta_recovered = 0
    boss_sta_recovered = 0

    hero_inflicted_status: Optional[StatusEffect] = None
    boss_inflicted_status: Optional[StatusEffect] = None

    hero_notes = ""
    boss_notes = ""

    # Stagger status damage multiplier (+25% extra incoming damage)
    hero_vuln = 1.25 if hero_state.status == StatusEffect.STAGGERED else 1.0
    boss_vuln = 1.25 if boss_state.status == StatusEffect.STAGGERED else 1.0

    # Base damages
    hero_raw_base = calculate_base_damage(hero_state.atk, boss_state.def_)
    boss_raw_base = calculate_base_damage(boss_state.atk, hero_state.def_)

    # 1. ATTACK vs ATTACK
    if hero_action == ActionType.ATTACK and boss_action == ActionType.ATTACK:
        hero_damage_dealt = math.ceil(hero_raw_base * boss_vuln)
        boss_damage_dealt = math.ceil(boss_raw_base * hero_vuln)
        events.append(f"Clash! Both fighters exchange standard blows. {hero_state.name} deals {hero_damage_dealt}, {boss_state.name} deals {boss_damage_dealt}.")

    # 2. ATTACK vs DEFEND
    elif hero_action == ActionType.ATTACK and boss_action == ActionType.DEFEND:
        hero_damage_dealt = max(4, math.ceil(hero_raw_base * 0.35 * boss_vuln))
        boss_damage_dealt = 0
        boss_sta_recovered = 10
        boss_notes = "Defended attack: gained +10 STA"
        events.append(f"{boss_state.name} blocks {hero_state.name}'s strike! Damage reduced to {hero_damage_dealt} and recovers +10 STA.")

    elif hero_action == ActionType.DEFEND and boss_action == ActionType.ATTACK:
        boss_damage_dealt = max(4, math.ceil(boss_raw_base * 0.25 * hero_vuln))
        hero_damage_dealt = 0
        hero_sta_recovered = 10
        hero_notes = "Defended attack: gained +10 STA"
        events.append(f"{hero_state.name} blocks {boss_state.name}'s strike! Damage reduced to {boss_damage_dealt} and recovers +10 STA.")

    # 3. HEAVY_ATTACK vs DEFEND (Guard Break)
    elif hero_action == ActionType.HEAVY_ATTACK and boss_action == ActionType.DEFEND:
        hero_damage_dealt = math.ceil(hero_state.atk * 1.5 * boss_vuln)
        boss_damage_dealt = 0
        hero_inflicted_status = StatusEffect.STAGGERED
        hero_notes = "GUARD BREAK! Inflicted STAGGERED"
        events.append(f"GUARD BREAK! {hero_state.name}'s Heavy Attack shatters {boss_state.name}'s guard for {hero_damage_dealt} dmg! {boss_state.name} is STAGGERED!")

    elif hero_action == ActionType.DEFEND and boss_action == ActionType.HEAVY_ATTACK:
        boss_damage_dealt = math.ceil(boss_state.atk * 1.5 * hero_vuln)
        hero_damage_dealt = 0
        boss_inflicted_status = StatusEffect.STAGGERED
        boss_notes = "GUARD BREAK! Inflicted STAGGERED"
        events.append(f"GUARD BREAK! {boss_state.name}'s Heavy Attack shatters {hero_state.name}'s guard for {boss_damage_dealt} dmg! {hero_state.name} is STAGGERED!")

    # 4. HEAVY_ATTACK vs DODGE (Elusion + Counter-Attack)
    elif hero_action == ActionType.HEAVY_ATTACK and boss_action == ActionType.DODGE:
        hero_damage_dealt = 0
        boss_damage_dealt = 25  # Deterministic counter
        boss_notes = "Dodged Heavy Attack! Countered for 25 dmg"
        events.append(f"{boss_state.name} dodges {hero_state.name}'s heavy windup completely and executes a counter-thrust for 25 dmg!")

    elif hero_action == ActionType.DODGE and boss_action == ActionType.HEAVY_ATTACK:
        boss_damage_dealt = 0
        hero_damage_dealt = 25  # Deterministic counter
        hero_notes = "Dodged Heavy Attack! Countered for 25 dmg"
        events.append(f"{hero_state.name} dodges {boss_state.name}'s heavy windup completely and executes a counter-thrust for 25 dmg!")

    # 5. ATTACK vs DODGE (Dodge fails on quick attack)
    elif hero_action == ActionType.ATTACK and boss_action == ActionType.DODGE:
        hero_damage_dealt = math.ceil(hero_raw_base * boss_vuln)
        boss_damage_dealt = 0
        events.append(f"{boss_state.name} attempts to dodge, but {hero_state.name}'s swift strike catches them for {hero_damage_dealt} full dmg!")

    elif hero_action == ActionType.DODGE and boss_action == ActionType.ATTACK:
        boss_damage_dealt = math.ceil(boss_raw_base * hero_vuln)
        hero_damage_dealt = 0
        events.append(f"{hero_state.name} attempts to dodge, but {boss_state.name}'s swift strike catches them for {boss_damage_dealt} full dmg!")

    # 6. HEAVY_ATTACK vs HEAVY_ATTACK
    elif hero_action == ActionType.HEAVY_ATTACK and boss_action == ActionType.HEAVY_ATTACK:
        hero_damage_dealt = math.ceil(hero_state.atk * 2.0 * boss_vuln)
        boss_damage_dealt = math.ceil(boss_state.atk * 2.0 * hero_vuln)
        events.append(f"Titanic Collision! Both unleash Heavy Attacks simultaneously! {hero_state.name} deals {hero_damage_dealt}, {boss_state.name} deals {boss_damage_dealt}.")

    # 7. HEAVY_ATTACK vs ATTACK
    elif hero_action == ActionType.HEAVY_ATTACK and boss_action == ActionType.ATTACK:
        hero_damage_dealt = math.ceil(hero_state.atk * 1.6 * boss_vuln)
        boss_damage_dealt = math.ceil(boss_raw_base * hero_vuln)
        events.append(f"{hero_state.name} powers through with a crushing Heavy Attack ({hero_damage_dealt} dmg) while taking a swift blow ({boss_damage_dealt} dmg).")

    elif hero_action == ActionType.ATTACK and boss_action == ActionType.HEAVY_ATTACK:
        hero_damage_dealt = math.ceil(hero_raw_base * boss_vuln)
        boss_damage_dealt = math.ceil(boss_state.atk * 1.6 * hero_vuln)
        events.append(f"{boss_state.name} powers through with a crushing Heavy Attack ({boss_damage_dealt} dmg) while taking a swift blow ({hero_damage_dealt} dmg).")

    # 8. DEFEND vs DEFEND
    elif hero_action == ActionType.DEFEND and boss_action == ActionType.DEFEND:
        events.append("Both fighters hold defensive stances, observing each other carefully.")

    # 9. DODGE vs DODGE
    elif hero_action == ActionType.DODGE and boss_action == ActionType.DODGE:
        events.append("Both combatants dart across the arena in synchronized evasive maneuvers.")

    # 10. DEFEND vs DODGE
    elif hero_action == ActionType.DEFEND and boss_action == ActionType.DODGE:
        events.append(f"{hero_state.name} braces for impact while {boss_state.name} dances away cautiously.")

    elif hero_action == ActionType.DODGE and boss_action == ActionType.DEFEND:
        events.append(f"{hero_state.name} dances away cautiously while {boss_state.name} braces for impact.")

    # 11. PSYCH_WARFARE Interactions
    if hero_action == ActionType.PSYCH_WARFARE:
        if turn_decision.psych_warfare_eval.hero_psych_successful:
            hero_inflicted_status = StatusEffect.STAGGERED
            hero_notes = "Psych warfare successful! Inflicted STAGGERED next round."
            events.append(f"[PSYCH EXPLOIT] {hero_state.name}'s tactical taunt strikes a nerve! {boss_state.name} will be STAGGERED next round.")
        else:
            events.append(f"[PSYCH DEFLECTED] {hero_state.name}'s taunt failed to rattle {boss_state.name}.")

        if boss_action == ActionType.ATTACK:
            boss_damage_dealt = math.ceil(boss_raw_base * hero_vuln)
            events.append(f"{boss_state.name} punishes {hero_state.name}'s mind games with a direct strike for {boss_damage_dealt} dmg.")
        elif boss_action == ActionType.HEAVY_ATTACK:
            boss_damage_dealt = math.ceil(boss_state.atk * 1.6 * hero_vuln)
            events.append(f"{boss_state.name} retaliates against the taunt with a devastating Heavy Strike for {boss_damage_dealt} dmg!")

    if boss_action == ActionType.PSYCH_WARFARE:
        if turn_decision.psych_warfare_eval.boss_psych_successful:
            boss_inflicted_status = StatusEffect.CONFUSED
            boss_notes = "Psych warfare successful! Inflicted CONFUSED next round."
            events.append(f"[PSYCH EXPLOIT] {boss_state.name}'s sinister mind game confuses {hero_state.name}! {hero_state.name} will be CONFUSED next round.")
        else:
            events.append(f"[PSYCH DEFLECTED] {boss_state.name}'s psychological pressure was resisted.")

        if hero_action == ActionType.ATTACK:
            hero_damage_dealt = math.ceil(hero_raw_base * boss_vuln)
            events.append(f"{hero_state.name} punishes {boss_state.name}'s mind games with a direct strike for {hero_damage_dealt} dmg.")
        elif hero_action == ActionType.HEAVY_ATTACK:
            hero_damage_dealt = math.ceil(hero_state.atk * 1.6 * boss_vuln)
            events.append(f"{hero_state.name} retaliates against the taunt with a devastating Heavy Strike for {hero_damage_dealt} dmg!")

    # 12. CONFUSED Actions
    if hero_action == ActionType.CONFUSED and boss_action != ActionType.CONFUSED:
        hero_notes = "Fighter is CONFUSED (Turn wasted)"
        events.append(f"[CONFUSED] {hero_state.name} stumbles in disorientation, failing to execute an effective action!")
        if boss_action == ActionType.ATTACK:
            boss_damage_dealt = math.ceil(boss_raw_base * hero_vuln)
            events.append(f"{boss_state.name} exploits {hero_state.name}'s confusion with a direct strike for {boss_damage_dealt} dmg.")
        elif boss_action == ActionType.HEAVY_ATTACK:
            boss_damage_dealt = math.ceil(boss_state.atk * 1.6 * hero_vuln)
            events.append(f"{boss_state.name} punishes {hero_state.name}'s confusion with a crushing Heavy Attack for {boss_damage_dealt} dmg!")

    elif boss_action == ActionType.CONFUSED and hero_action != ActionType.CONFUSED:
        boss_notes = "Fighter is CONFUSED (Turn wasted)"
        events.append(f"[CONFUSED] {boss_state.name} stumbles in disorientation, failing to execute an effective action!")
        if hero_action == ActionType.ATTACK:
            hero_damage_dealt = math.ceil(hero_raw_base * boss_vuln)
            events.append(f"{hero_state.name} exploits {boss_state.name}'s confusion with a direct strike for {hero_damage_dealt} dmg.")
        elif hero_action == ActionType.HEAVY_ATTACK:
            hero_damage_dealt = math.ceil(hero_state.atk * 1.6 * boss_vuln)
            events.append(f"{hero_state.name} punishes {boss_state.name}'s confusion with a crushing Heavy Attack for {hero_damage_dealt} dmg!")

    elif hero_action == ActionType.CONFUSED and boss_action == ActionType.CONFUSED:
        hero_notes = "Fighter is CONFUSED (Turn wasted)"
        boss_notes = "Fighter is CONFUSED (Turn wasted)"
        events.append("[CONFUSED] Both fighters stumble in mutual disorientation, failing to act!")

    hero_res = CombatActionResolution(
        actor=hero_state.name,
        action=hero_action,
        stamina_spent=hero_cost,
        damage_dealt=hero_damage_dealt,
        stamina_recovered=hero_sta_recovered,
        status_inflicted=hero_inflicted_status,
        notes=hero_notes,
    )

    boss_res = CombatActionResolution(
        actor=boss_state.name,
        action=boss_action,
        stamina_spent=boss_cost,
        damage_dealt=boss_damage_dealt,
        stamina_recovered=boss_sta_recovered,
        status_inflicted=boss_inflicted_status,
        notes=boss_notes,
    )

    hero_next_status = boss_inflicted_status
    boss_next_status = hero_inflicted_status

    return hero_res, boss_res, events, hero_next_status, boss_next_status
