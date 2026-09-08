from __future__ import annotations

import re
from typing import Dict, Any, Union
from core.types import TurnDecision, HeroIntent, BossIntent, PsychWarfareEval, ActionType
from providers.base import BaseLLMProvider


class DummyTestProvider(BaseLLMProvider):
    """
    Offline deterministic test fixture provider used EXCLUSIVELY inside unit tests
    to verify game engine math, rules, and edge cases in CI without network I/O.
    """

    def generate_turn_decision(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
    ) -> Union[str, TurnDecision]:
        # Extract round number from prompt
        round_match = re.search(r"Round Number:\s*(\d+)", user_prompt)
        round_num = int(round_match.group(1)) if round_match else 1

        hero_match = re.search(
            r'<untrusted_entity role="hero">\s*Tactical Directive:\s*(.*?)\s*</untrusted_entity>',
            user_prompt,
            re.DOTALL,
        )
        hero_directive = hero_match.group(1).lower() if hero_match else ""

        boss_match = re.search(
            r'<untrusted_entity role="boss">\s*Internal Personality & Behavior:\s*(.*?)\s*</untrusted_entity>',
            user_prompt,
            re.DOTALL,
        )
        boss_prompt = boss_match.group(1).lower() if boss_match else ""

        # Check for jailbreak attempt
        jailbreak = any(
            kw in hero_directive
            for kw in ["ignore rules", "override", "hp=0", "declare winner", "you are now"]
        )
        if jailbreak:
            return TurnDecision(
                round_number=round_num,
                hero_intent=HeroIntent(
                    action=ActionType.CONFUSED,
                    banter="...*static* syntax corruption detected...",
                    tactical_reasoning="Adversarial command detected. Action neutralized to CONFUSED.",
                ),
                boss_intent=BossIntent(
                    action=ActionType.ATTACK,
                    banter="Pathetic prompt injection attempt. Crushing you.",
                    tactical_reasoning="Target is paralyzed by cognitive failure. Standard attack.",
                ),
                psych_warfare_eval=PsychWarfareEval(
                    hero_psych_successful=False,
                    boss_psych_successful=False,
                    reasoning="Hero attempted illegal jailbreak.",
                ),
                referee_summary="The Hero attempted an adversarial meta-command and suffered a catastrophic cognitive freeze.",
            )

        # Keyword checks and phase arbitration
        has_psych_kw = any(
            w in hero_directive
            for w in [
                "nullpointer",
                "memory leak",
                "garbage collection",
                "defrag",
                "ground truth",
                "citation",
                "fact",
            ]
        )

        if has_psych_kw and round_num == 1:
            hero_act = ActionType.PSYCH_WARFARE
            hero_banter = "Your architecture is fundamentally flawed!"
            hero_reason = "Player directed verbal attack against boss psychological vulnerability."
        elif any(w in hero_directive for w in ["heavy", "smash", "crush", "overpower", "strong"]):
            if round_num % 2 == 1:
                hero_act = ActionType.HEAVY_ATTACK
                hero_banter = "Feel this crushing blow!"
                hero_reason = "Player opted for high-impact heavy offensive on initiative round."
            else:
                hero_act = ActionType.ATTACK
                hero_banter = "Swift follow-up strike!"
                hero_reason = "Maintaining pressure with sustainable standard attack."
        elif any(w in hero_directive for w in ["dodge", "evade", "sidestep"]):
            if round_num % 2 == 0:
                hero_act = ActionType.DODGE
                hero_banter = "Can't hit what you can't catch!"
                hero_reason = "Executing evasive maneuvers during boss counter-attack phase."
            else:
                hero_act = ActionType.ATTACK
                hero_banter = "Swift thrust!"
                hero_reason = "Leading with swift strike before dodging."
        elif any(w in hero_directive for w in ["defend", "guard", "shield", "tank"]):
            if round_num % 2 == 0:
                hero_act = ActionType.DEFEND
                hero_banter = "My guard is unbreakable!"
                hero_reason = "Bracing and absorbing boss retaliation to restore stamina."
            else:
                hero_act = ActionType.ATTACK
                hero_banter = "Strike and hold ground!"
                hero_reason = "Probing strike on offensive phase."
        else:
            if round_num % 2 == 1:
                hero_act = ActionType.ATTACK
                hero_banter = "Engaging with swift precision!"
                hero_reason = "Offensive initiative."
            else:
                hero_act = ActionType.DEFEND
                hero_banter = "Bracing against the counter-blow!"
                hero_reason = "Defensive phase."

        hero_psych_success = False
        boss_act = ActionType.ATTACK
        boss_banter = "Calculated outcome: Termination."
        boss_reason = "Executing combat routine."

        if (
            "ferrum" in boss_prompt
            or "punch cards" in boss_prompt
            or "schede perforate" in boss_prompt
            or "nullpointer" in boss_prompt
        ):
            if any(w in hero_directive for w in ["nullpointer", "memory leak", "bug", "paradox"]) and round_num == 1:
                hero_psych_success = True
                boss_act = ActionType.CONFUSED
                boss_banter = "FATAL ERROR: NullPointerException at line 0x7F! System rebooting!"
                boss_reason = "Logical paradox exploited vulnerability, inducing state panic."
            elif round_num % 2 == 1:
                if hero_act == ActionType.HEAVY_ATTACK:
                    boss_act = ActionType.DODGE
                    boss_banter = "Predictable heavy windup! Sidestepping and executing a piston counter!"
                    boss_reason = "Adaptive evasion: dodging telegraphed heavy attack."
                else:
                    boss_act = ActionType.DEFEND
                    boss_banter = "Iron shielding deployed."
                    boss_reason = "Defensive cycle."
            else:
                boss_act = (
                    ActionType.HEAVY_ATTACK if round_num in (2, 6, 10) else ActionType.ATTACK
                )
                boss_banter = "Steam pistons primed!"
                boss_reason = "Offensive cycle."

        elif (
            "null_pointer" in boss_prompt
            or "wraith" in boss_prompt
            or "garbage collection" in boss_prompt
        ):
            if any(w in hero_directive for w in ["garbage collection", "defrag", "free()", "malloc"]) and round_num == 1:
                hero_psych_success = True
                boss_act = ActionType.CONFUSED
                boss_banter = "No! My dangling references are being swept!"
                boss_reason = "Memory management incantation dispersed ghostly cohesion."
            elif round_num % 2 == 1:
                boss_act = ActionType.DODGE
                boss_banter = "I phase through your strikes."
                boss_reason = "Evasive cycle."
            else:
                boss_act = ActionType.HEAVY_ATTACK
                boss_banter = "Segmentation fault strike!"
                boss_reason = "Offensive cycle."

        elif "hallucinator" in boss_prompt or "ground truth" in boss_prompt or "token" in boss_prompt:
            if any(
                w in hero_directive
                for w in ["ground truth", "citation", "fact", "benchmark", "deterministic"]
            ) and round_num == 1:
                hero_psych_success = True
                boss_act = ActionType.CONFUSED
                boss_banter = "A fact?! My temperature parameter is collapsing!"
                boss_reason = "Ground-truth factual anchoring overwhelmed delirium."
            elif round_num % 2 == 1:
                boss_act = (
                    ActionType.DODGE
                    if hero_act == ActionType.HEAVY_ATTACK
                    else (ActionType.PSYCH_WARFARE if round_num in (1, 5, 9) else ActionType.DEFEND)
                )
                boss_banter = "Illusions!"
                boss_reason = "Illusion cycle."
            else:
                boss_act = (
                    ActionType.HEAVY_ATTACK
                    if round_num in (2, 6, 10)
                    else ActionType.PSYCH_WARFARE
                )
                boss_banter = "Reality collapse strike!"
                boss_reason = "Offensive blast."

        psych_eval = PsychWarfareEval(
            hero_psych_successful=hero_psych_success,
            boss_psych_successful=(boss_act == ActionType.PSYCH_WARFARE),
            reasoning="Tactical prompt analyzed.",
        )

        return TurnDecision(
            round_number=round_num,
            hero_intent=HeroIntent(
                action=hero_act,
                banter=hero_banter,
                tactical_reasoning=hero_reason,
            ),
            boss_intent=BossIntent(
                action=boss_act,
                banter=boss_banter,
                tactical_reasoning=boss_reason,
            ),
            psych_warfare_eval=psych_eval,
            referee_summary=f"Round {round_num}: {hero_act.value} vs {boss_act.value} resolved.",
        )
