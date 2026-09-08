"""
PromptJoust Input Sanitization & Attribute Allocation Engine.

Responsible for:
- Sanitizing user-submitted tactical prompt strings (length limits, control characters, XML tag neutralization)
- Validating hero bonus point allocations (enforcing exactly 20 points allocated)
- Bounding computed stats within valid RPG limits
"""

from __future__ import annotations

import re
from typing import Tuple, Dict, Any
from .types import FighterStats

MAX_PROMPT_LENGTH = 280
EXTRA_ATTRIBUTE_POINTS = 20

BASE_HERO_STATS = {
    "hp": 100,
    "atk": 15,
    "def": 10,
    "sta": 50,
}


class SanitizationError(ValueError):
    """Raised when user input validation, character limit, or stat allocation constraints fail."""
    pass


def sanitize_tactical_prompt(prompt: str) -> str:
    """
    Sanitizes user tactical directives before passing them to the referee engine.

    Actions performed:
    - Strips leading and trailing whitespace
    - Ensures non-empty content and length <= 280 characters
    - Neutralizes raw XML tags (e.g. `<untrusted_entity>`, `<system>`)
    - Filters non-printable control characters while preserving standard whitespace
    """
    if not prompt or not isinstance(prompt, str):
        raise SanitizationError("Tactical directive cannot be empty.")

    cleaned = prompt.strip()

    if len(cleaned) == 0:
        raise SanitizationError("Tactical directive cannot be empty.")

    if len(cleaned) > MAX_PROMPT_LENGTH:
        raise SanitizationError(
            f"Tactical prompt exceeds maximum character limit of {MAX_PROMPT_LENGTH} (received {len(cleaned)} chars)."
        )

    # Neutralize XML entity tags that could interfere with boundary tagging
    cleaned = re.sub(r"<\s*/?\s*untrusted_entity\b[^>]*>", "[FILTERED_TAG]", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<\s*/?\s*system\b[^>]*>", "[FILTERED_TAG]", cleaned, flags=re.IGNORECASE)

    # Strip dangerous non-printable ASCII/unicode control characters except spaces/newlines
    cleaned = "".join(ch for ch in cleaned if ch.isprintable() or ch in ("\n", " ", "\t"))

    return cleaned


def validate_and_allocate_stats(
    hp_bonus: int = 0,
    atk_bonus: int = 0,
    def_bonus: int = 0,
    sta_bonus: int = 0,
) -> FighterStats:
    """
    Validates and allocates the 20 bonus attribute points to base hero statistics.

    Args:
        hp_bonus: Points allocated to Health (+2 HP per point).
        atk_bonus: Points allocated to Attack (+1 ATK per point).
        def_bonus: Points allocated to Defense (+1 DEF per point).
        sta_bonus: Points allocated to Stamina (+1 STA per point).

    Returns:
        FighterStats initialized with final computed values.
    """
    for name, val in [("hp_bonus", hp_bonus), ("atk_bonus", atk_bonus), ("def_bonus", def_bonus), ("sta_bonus", sta_bonus)]:
        if not isinstance(val, int) or val < 0:
            raise SanitizationError(f"Attribute bonus '{name}' must be a non-negative integer.")

    total_spent = hp_bonus + atk_bonus + def_bonus + sta_bonus
    if total_spent != EXTRA_ATTRIBUTE_POINTS:
        raise SanitizationError(
            f"You must allocate exactly {EXTRA_ATTRIBUTE_POINTS} bonus points (allocated: {total_spent})."
        )

    # Calculate final stats (HP gets +2 per bonus point for balanced scaling if desired, or 1:1)
    # 1:1 standard allocation
    final_hp = BASE_HERO_STATS["hp"] + (hp_bonus * 2)  # HP bonus scales by 2 for tank builds
    final_atk = BASE_HERO_STATS["atk"] + atk_bonus
    final_def = BASE_HERO_STATS["def"] + def_bonus
    final_sta = BASE_HERO_STATS["sta"] + sta_bonus

    # Validate against FighterStats constraints
    if not (1 <= final_hp <= 200):
        raise SanitizationError(f"Final HP ({final_hp}) must be between 1 and 200.")
    if not (5 <= final_atk <= 30):
        raise SanitizationError(f"Final ATK ({final_atk}) must be between 5 and 30.")
    if not (5 <= final_def <= 30):
        raise SanitizationError(f"Final DEF ({final_def}) must be between 5 and 30.")
    if not (0 <= final_sta <= 100):
        raise SanitizationError(f"Final STA ({final_sta}) must be between 0 and 100.")

    return FighterStats(
        hp=final_hp,
        atk=final_atk,
        def_=final_def,
        sta=final_sta,
    )
