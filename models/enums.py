"""
PromptJoust Canonical Enumerations.

Defines ActionType, StatusEffect, and DifficultyLevel enums.
"""

from enum import Enum


class ActionType(str, Enum):
    """
    Canonical combat actions available to both Hero and Boss fighters.
    Follows a Rock-Paper-Scissors combat dynamic:
    - HEAVY_ATTACK shatters DEFEND (Guard Break)
    - DODGE evades and counters HEAVY_ATTACK (Dodge Counter)
    - ATTACK catches DODGE for full damage
    - DEFEND mitigates ATTACK and restores stamina
    """
    ATTACK = "ATTACK"
    HEAVY_ATTACK = "HEAVY_ATTACK"
    DEFEND = "DEFEND"
    DODGE = "DODGE"
    PSYCH_WARFARE = "PSYCH_WARFARE"
    CONFUSED = "CONFUSED"  # Triggered when prompt injection or cognitive breakdown occurs


class StatusEffect(str, Enum):
    """
    Temporary combat status effects applied to fighters.
    """
    NORMAL = "NORMAL"
    STAGGERED = "STAGGERED"  # Takes +25% increased damage (e.g. from Guard Break or Psych exploit)
    ENRAGED = "ENRAGED"      # High offensive power with reduced defensive vigilance
    CONFUSED = "CONFUSED"    # Stumbles and wastes the active combat turn


class DifficultyLevel(str, Enum):
    """
    Combat difficulty tiers for the Grand Tournament Arena.
    - APPRENTICE: Generous 25 valor points, weakened boss stats (-15% HP & ATK).
    - WARRIOR: Standard tournament baseline (20 valor points, 100% stats).
    - GRANDMASTER: Strict 15 valor points, amplified boss stats (+20% HP & ATK, +10% DEF), +8 STA/round recovery, and max 200 prompt runes.
    """
    APPRENTICE = "apprentice"
    WARRIOR = "warrior"
    GRANDMASTER = "grandmaster"
