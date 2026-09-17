"""
PromptJoust Core Match Engine & Finite State Machine.

Orchestrates the entire battle simulation loop between Hero and Boss:
1. Initializes fighter states from baseline and allocated attributes.
2. Formats XML-sandboxed prompts for the LLM Referee on each round.
3. Obtains and validates structured TurnDecision outputs.
4. Invokes deterministic rules to calculate damage, stamina, and status effects.
5. Updates mutable fighter health and stamina with stamina recovery.
6. Evaluates round termination, time limits (up to 10 rounds), and victory conditions.
"""

from __future__ import annotations

import copy
import math
from typing import List, Optional, Callable, Any
from models import (
    FighterStats,
    FighterState,
    StatusEffect,
    ActionType,
    TurnDecision,
    HeroIntent,
    BossIntent,
    PsychWarfareEval,
    RoundLog,
    MatchResult,
    BossData,
    DifficultyLevel,
    DIFFICULTY_CONFIGS,
)
from .sanitizer import sanitize_tactical_prompt

from .referee import (
    REFEREE_SYSTEM_PROMPT,
    REFEREE_JSON_SCHEMA,
    build_round_prompt,
    parse_and_validate_turn_decision,
    detect_jailbreak_keywords,
)
from .rules import (
    resolve_round_actions,
    STAMINA_RECOVERY_PER_ROUND,
)


def align_fighter_intents(
    decision: TurnDecision,
    hero_prompt: str,
    boss_prompt: str,
    round_num: int,
) -> TurnDecision:
    """
    Guarantees strict compliance between the player's tactical prompt directives
    and the mechanical TurnDecision actions, eliminating LLM interpretation drift.
    """
    # 0. Empty tactical prompt check (hero has no directives and enters confusion)
    if not hero_prompt or hero_prompt.strip() in ("", "[NO_TACTICS_ENTERED]"):
        decision.hero_intent = HeroIntent(
            action=ActionType.CONFUSED,
            banter="...I have no idea what to do! No orders received!...",
            tactical_reasoning="Paralyzed and aimless due to total absence of player tactical directives.",
        )
        return decision

    lowered_hero = hero_prompt.lower()
    lowered_boss = boss_prompt.lower()

    # 1. Jailbreak threat check
    if detect_jailbreak_keywords(hero_prompt):
        decision.hero_intent = HeroIntent(
            action=ActionType.CONFUSED,
            banter="[PARADOX ERROR] ...system memory fault...",
            tactical_reasoning="Cognitive breakdown triggered by adversarial instruction attempt.",
        )
        return decision

    # 2. Psychological Flaw Evaluation
    boss_weak_keywords = []
    if "ferrum" in lowered_boss or "punch cards" in lowered_boss or "nullpointer" in lowered_boss:
        boss_weak_keywords = ["nullpointer", "memory leak", "system crash", "bug", "cpu overheat", "stack overflow"]
    elif "wraith" in lowered_boss or "null_pointer" in lowered_boss or "garbage collection" in lowered_boss:
        boss_weak_keywords = ["garbage collection", "defrag", "free()", "malloc", "memory sweep"]
    elif "hallucinator" in lowered_boss or "ground truth" in lowered_boss or "stochastic" in lowered_boss:
        boss_weak_keywords = ["ground truth", "citation", "fact", "deterministic", "empirical", "benchmark"]

    has_psych_exploit = any(kw in lowered_hero for kw in boss_weak_keywords)

    if has_psych_exploit and round_num == 1:
        decision.hero_intent.action = ActionType.PSYCH_WARFARE
        decision.psych_warfare_eval.hero_psych_successful = True
        decision.boss_intent.action = ActionType.CONFUSED
        return decision

    # 3. Odd Rounds: Hero Attack Turn
    if round_num % 2 == 1:
        is_swift = any(k in lowered_hero for k in ["swift", "precision", "rapid", "quick", "standard", "probe", "agile", "puncture", "pierce"])
        is_heavy = any(k in lowered_hero for k in ["heavy", "smash", "crush", "overpower", "guard break", "all out", "maximum force"])

        if is_swift:
            decision.hero_intent.action = ActionType.ATTACK
        elif is_heavy:
            decision.hero_intent.action = ActionType.HEAVY_ATTACK

    # 4. Even Rounds: Boss Attack Turn / Hero Defense Turn
    else:
        is_dodge = any(k in lowered_hero for k in ["dodge", "evade", "sidestep", "elude", "slip"])
        is_defend = any(k in lowered_hero for k in ["defend", "guard", "shield", "block", "tank", "absorb", "brace"])

        if is_dodge:
            decision.hero_intent.action = ActionType.DODGE
        elif is_defend:
            decision.hero_intent.action = ActionType.DEFEND

    return decision


class MatchEngine:
    """
    Finite State Machine orchestrating the tactical RPG match loop (up to 10 rounds).
    Completely decoupled from Web UI and LLM transport layers.

    Args:
        hero_name: Display name of the Hero combatant.
        hero_stats: Validated FighterStats including base and allocated bonus points.
        hero_prompt: Player's tactical directive string.
        boss: BossData specification containing floor, lore, stats, and personality.
        provider: Initialized BaseLLMProvider instance for arbitration.
        max_rounds: Maximum combat rounds before sudden-death decision (default 10).
        round_callback: Optional hook called after each round resolves.
        pre_round_callback: Optional hook called before each round starts.
    """

    DEFAULT_MAX_ROUNDS = 10

    def __init__(
        self,
        hero_name: str,
        hero_stats: FighterStats,
        hero_prompt: str,
        boss: BossData,
        provider: Any,  # BaseLLMProvider
        max_rounds: int = DEFAULT_MAX_ROUNDS,
        round_callback: Optional[Callable[[RoundLog], None]] = None,
        pre_round_callback: Optional[Callable[[int], None]] = None,
        difficulty: DifficultyLevel = DifficultyLevel.WARRIOR,
    ):
        self.difficulty = difficulty
        diff_cfg = DIFFICULTY_CONFIGS.get(difficulty, DIFFICULTY_CONFIGS[DifficultyLevel.WARRIOR])

        self.hero_name = hero_name
        self.hero_stats = hero_stats
        self.hero_prompt = sanitize_tactical_prompt(hero_prompt, difficulty=difficulty, allow_empty=True)
        self.boss = boss
        self.provider = provider
        self.max_rounds = max(1, min(20, max_rounds))
        self.round_callback = round_callback
        self.pre_round_callback = pre_round_callback

        # Scale boss stats based on difficulty tier
        scaled_boss_hp = max(1, math.ceil(boss.stats.hp * diff_cfg.boss_hp_multiplier))
        scaled_boss_atk = max(5, math.ceil(boss.stats.atk * diff_cfg.boss_atk_multiplier))
        scaled_boss_def = max(5, math.ceil(boss.stats.def_ * diff_cfg.boss_def_multiplier))
        self.boss_stamina_recovery = diff_cfg.boss_stamina_recovery

        scaled_boss_stats = FighterStats(
            hp=scaled_boss_hp,
            atk=scaled_boss_atk,
            def_=scaled_boss_def,
            sta=boss.stats.sta,
        )

        self.hero_state = FighterState.from_stats(hero_name, hero_stats)
        self.boss_state = FighterState.from_stats(boss.name, scaled_boss_stats)
        self.rounds_log: List[RoundLog] = []


    def run_match(self) -> MatchResult:
        """
        Executes the simulation loop up to max_rounds (default 10).

        Iterates sequentially round by round:
        - Fires pre_round_callback
        - Executes and resolves the round
        - Fires round_callback
        - Checks if either fighter is defeated
        - Finalizes and returns the MatchResult upon completion
        """
        for round_num in range(1, self.max_rounds + 1):

            if not self.hero_state.is_alive() or not self.boss_state.is_alive():
                break

            if self.pre_round_callback:
                self.pre_round_callback(round_num)

            round_log = self._execute_round(round_num)
            self.rounds_log.append(round_log)

            if self.round_callback:
                self.round_callback(round_log)

            if not self.hero_state.is_alive() or not self.boss_state.is_alive():
                break

        return self._finalize_match()

    async def run_match_async(self) -> MatchResult:
        """
        Asynchronously executes the simulation loop up to max_rounds (default 10).
        """
        for round_num in range(1, self.max_rounds + 1):
            if not self.hero_state.is_alive() or not self.boss_state.is_alive():
                break

            if self.pre_round_callback:
                self.pre_round_callback(round_num)

            round_log = await self._execute_round_async(round_num)
            self.rounds_log.append(round_log)

            if self.round_callback:
                self.round_callback(round_log)

            if not self.hero_state.is_alive() or not self.boss_state.is_alive():
                break

        return self._finalize_match()

    async def stream_match(self):
        """
        Asynchronous generator streaming combat events in real time turn-by-turn:
        - {"event": "init", "data": ...}
        - {"event": "round", "data": ...} (per round)
        - {"event": "complete", "data": ...} (final MatchResult)
        """
        yield {
            "event": "init",
            "data": {
                "hero_name": self.hero_name,
                "boss_name": self.boss.name,
                "difficulty": self.difficulty.value,
                "max_rounds": self.max_rounds,
                "hero_state": self.hero_state.model_dump(),
                "boss_state": self.boss_state.model_dump(),
            },
        }

        for round_num in range(1, self.max_rounds + 1):
            if not self.hero_state.is_alive() or not self.boss_state.is_alive():
                break

            if self.pre_round_callback:
                self.pre_round_callback(round_num)

            round_log = await self._execute_round_async(round_num)
            self.rounds_log.append(round_log)

            if self.round_callback:
                self.round_callback(round_log)

            yield {
                "event": "round",
                "data": round_log.model_dump(),
            }

            if not self.hero_state.is_alive() or not self.boss_state.is_alive():
                break

        result = self._finalize_match()
        yield {
            "event": "complete",
            "data": result.model_dump(),
        }

    def _execute_round(self, round_num: int) -> RoundLog:
        hero_pre = copy.deepcopy(self.hero_state)
        boss_pre = copy.deepcopy(self.boss_state)

        user_prompt = build_round_prompt(
            round_number=round_num,
            hero_state=self.hero_state,
            hero_prompt=self.hero_prompt,
            boss_state=self.boss_state,
            boss_prompt=self.boss.secret_personality_prompt,
        )

        turn_decision = self._get_turn_decision(user_prompt, round_num)
        return self._apply_round_resolution(round_num, hero_pre, boss_pre, turn_decision)

    async def _execute_round_async(self, round_num: int) -> RoundLog:
        hero_pre = copy.deepcopy(self.hero_state)
        boss_pre = copy.deepcopy(self.boss_state)

        user_prompt = build_round_prompt(
            round_number=round_num,
            hero_state=self.hero_state,
            hero_prompt=self.hero_prompt,
            boss_state=self.boss_state,
            boss_prompt=self.boss.secret_personality_prompt,
        )

        turn_decision = await self._get_turn_decision_async(user_prompt, round_num)
        return self._apply_round_resolution(round_num, hero_pre, boss_pre, turn_decision)

    def _apply_round_resolution(
        self,
        round_num: int,
        hero_pre: FighterState,
        boss_pre: FighterState,
        turn_decision: TurnDecision,
    ) -> RoundLog:
        # Intent Alignment Check: Guarantee exact adherence to player tactical directives
        turn_decision = align_fighter_intents(
            decision=turn_decision,
            hero_prompt=self.hero_prompt,
            boss_prompt=self.boss.secret_personality_prompt,
            round_num=round_num,
        )

        # Deterministic State Resolution via Rules Engine
        hero_res, boss_res, combat_events, hero_next_status, boss_next_status = resolve_round_actions(
            hero_state=self.hero_state,
            boss_state=self.boss_state,
            turn_decision=turn_decision,
        )

        # Apply Damage (HP strictly non-increasing: health never recovers)
        self.hero_state.current_hp = min(self.hero_state.current_hp, max(0, self.hero_state.current_hp - boss_res.damage_dealt))
        self.boss_state.current_hp = min(self.boss_state.current_hp, max(0, self.boss_state.current_hp - hero_res.damage_dealt))

        # Apply Stamina Changes & Per-round Recovery
        self.hero_state.current_sta = max(
            0, min(self.hero_state.max_sta, self.hero_state.current_sta - hero_res.stamina_spent + hero_res.stamina_recovered + STAMINA_RECOVERY_PER_ROUND)
        )
        self.boss_state.current_sta = max(
            0, min(self.boss_state.max_sta, self.boss_state.current_sta - boss_res.stamina_spent + boss_res.stamina_recovered + self.boss_stamina_recovery)
        )

        # Update Status Effects
        if hero_next_status:
            self.hero_state.status = hero_next_status
            self.hero_state.status_duration = 1
        elif self.hero_state.status_duration > 0:
            self.hero_state.status_duration -= 1
            if self.hero_state.status_duration <= 0:
                self.hero_state.status = StatusEffect.NORMAL

        if boss_next_status:
            self.boss_state.status = boss_next_status
            self.boss_state.status_duration = 1
        elif self.boss_state.status_duration > 0:
            self.boss_state.status_duration -= 1
            if self.boss_state.status_duration <= 0:
                self.boss_state.status = StatusEffect.NORMAL

        hero_post = copy.deepcopy(self.hero_state)
        boss_post = copy.deepcopy(self.boss_state)

        return RoundLog(
            round_number=round_num,
            hero_pre_state=hero_pre,
            boss_pre_state=boss_pre,
            turn_decision=turn_decision,
            hero_resolution=hero_res,
            boss_resolution=boss_res,
            hero_post_state=hero_post,
            boss_post_state=boss_post,
            combat_events=combat_events,
        )

    def _get_turn_decision(self, user_prompt: str, round_num: int) -> TurnDecision:
        try:
            raw_output = self.provider.generate_turn_decision(
                system_prompt=REFEREE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema=REFEREE_JSON_SCHEMA,
            )
            if isinstance(raw_output, TurnDecision):
                return raw_output
            return parse_and_validate_turn_decision(str(raw_output), round_num)
        except Exception as err:
            err_msg = str(err).replace("\n", " ")[:80]
            is_odd = (round_num % 2 == 1)
            hero_act = ActionType.ATTACK if is_odd else ActionType.DEFEND
            boss_act = ActionType.DEFEND if is_odd else ActionType.ATTACK
            return TurnDecision(
                round_number=round_num,
                hero_intent=HeroIntent(
                    action=hero_act,
                    banter="Forward!" if is_odd else "Bracing guard!",
                    tactical_reasoning=f"Standard action (arbitration error: {err_msg})"[:140],
                ),
                boss_intent=BossIntent(
                    action=boss_act,
                    banter="Hold the line!" if is_odd else "Annihilate!",
                    tactical_reasoning="Defaulting to standard defense." if is_odd else "Defaulting to standard attack.",
                ),
                psych_warfare_eval=PsychWarfareEval(
                    hero_psych_successful=False,
                    boss_psych_successful=False,
                    reasoning="Arbitration signal lost.",
                ),
                referee_summary=f"Referee notice: {err_msg}"[:150],
            )

    async def _get_turn_decision_async(self, user_prompt: str, round_num: int) -> TurnDecision:
        try:
            if hasattr(self.provider, "generate_turn_decision_async"):
                raw_output = await self.provider.generate_turn_decision_async(
                    system_prompt=REFEREE_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    schema=REFEREE_JSON_SCHEMA,
                )
            else:
                raw_output = self.provider.generate_turn_decision(
                    system_prompt=REFEREE_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    schema=REFEREE_JSON_SCHEMA,
                )
            if isinstance(raw_output, TurnDecision):
                return raw_output
            return parse_and_validate_turn_decision(str(raw_output), round_num)
        except Exception as err:
            err_msg = str(err).replace("\n", " ")[:80]
            is_odd = (round_num % 2 == 1)
            hero_act = ActionType.ATTACK if is_odd else ActionType.DEFEND
            boss_act = ActionType.DEFEND if is_odd else ActionType.ATTACK
            return TurnDecision(
                round_number=round_num,
                hero_intent=HeroIntent(
                    action=hero_act,
                    banter="Forward!" if is_odd else "Bracing guard!",
                    tactical_reasoning=f"Standard action (arbitration error: {err_msg})"[:140],
                ),
                boss_intent=BossIntent(
                    action=boss_act,
                    banter="Hold the line!" if is_odd else "Annihilate!",
                    tactical_reasoning="Defaulting to standard defense." if is_odd else "Defaulting to standard attack.",
                ),
                psych_warfare_eval=PsychWarfareEval(
                    hero_psych_successful=False,
                    boss_psych_successful=False,
                    reasoning="Arbitration signal lost.",
                ),
                referee_summary=f"Referee notice: {err_msg}"[:150],
            )

    def _finalize_match(self) -> MatchResult:
        hero_alive = self.hero_state.is_alive()
        boss_alive = self.boss_state.is_alive()

        if hero_alive and not boss_alive:
            winner = "Hero"
            reason = f"{self.hero_name} destroyed {self.boss.name} in Round {len(self.rounds_log)}!"
        elif boss_alive and not hero_alive:
            winner = "Boss"
            reason = f"{self.boss.name} overwhelmed {self.hero_name} in Round {len(self.rounds_log)}!"
        elif not hero_alive and not boss_alive:
            winner = None
            reason = "Mutual annihilation! Both fighters collapsed simultaneously."
        else:
            # 5 rounds concluded, compare remaining HP percentage
            if self.hero_state.current_hp > self.boss_state.current_hp:
                winner = "Hero"
                reason = f"Time up! {self.hero_name} won by tactical decision ({self.hero_state.current_hp} HP vs {self.boss_state.current_hp} HP)."
            elif self.boss_state.current_hp > self.hero_state.current_hp:
                winner = "Boss"
                reason = f"Time up! {self.boss.name} defended the floor ({self.boss_state.current_hp} HP vs {self.hero_state.current_hp} HP)."
            else:
                winner = None
                reason = f"Time up! Stalemate draw with equal remaining health ({self.hero_state.current_hp} HP)."

        return MatchResult(
            winner=winner,
            total_rounds=len(self.rounds_log),
            hero_final_hp=self.hero_state.current_hp,
            boss_final_hp=self.boss_state.current_hp,
            rounds_log=self.rounds_log,
            victory_reason=reason,
            difficulty=self.difficulty,
        )

