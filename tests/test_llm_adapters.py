from __future__ import annotations

import json
from unittest.mock import patch
import pytest
from core.referee import parse_and_validate_turn_decision, REFEREE_JSON_SCHEMA
from core.types import ActionType, TurnDecision
from providers import get_provider, PROVIDERS, GeminiProvider, OpenAIProvider, GroqProvider, OllamaProvider
from tests.test_helpers import DummyTestProvider


VALID_TURN_JSON = """
{
  "round_number": 1,
  "hero_intent": {
    "action": "HEAVY_ATTACK",
    "banter": "Take this crushing blow!",
    "tactical_reasoning": "Boss lowered shield."
  },
  "boss_intent": {
    "action": "DEFEND",
    "banter": "Reinforcing iron barrier.",
    "tactical_reasoning": "Predicting incoming heavy blow."
  },
  "psych_warfare_eval": {
    "hero_psych_successful": false,
    "boss_psych_successful": false,
    "reasoning": "No psych warfare attempted."
  },
  "referee_summary": "Hero's heavy attack shatters boss guard."
}
"""


def test_parse_valid_turn_decision():
    decision = parse_and_validate_turn_decision(VALID_TURN_JSON, expected_round=1)
    assert isinstance(decision, TurnDecision)
    assert decision.round_number == 1
    assert decision.hero_intent.action == ActionType.HEAVY_ATTACK
    assert decision.boss_intent.action == ActionType.DEFEND
    assert decision.psych_warfare_eval.hero_psych_successful is False


def test_parse_markdown_wrapped_json():
    wrapped = f"```json\n{VALID_TURN_JSON}\n```"
    decision = parse_and_validate_turn_decision(wrapped, expected_round=1)
    assert decision.hero_intent.action == ActionType.HEAVY_ATTACK


def test_parse_reconciliation_rules():
    # Odd round: HEAVY_ATTACK with swift reasoning -> reconciles to ATTACK
    odd_payload = {
        "round_number": 1,
        "hero_intent": {
            "action": "HEAVY_ATTACK",
            "banter": "Swift!",
            "tactical_reasoning": "Execute rapid swift strike",
        },
        "boss_intent": {
            "action": "DEFEND",
            "banter": "Shield",
            "tactical_reasoning": "Block",
        },
        "psych_warfare_eval": {
            "hero_psych_successful": False,
            "boss_psych_successful": False,
            "reasoning": "None",
        },
        "referee_summary": "Hero attacked",
    }
    dec1 = parse_and_validate_turn_decision(json.dumps(odd_payload), expected_round=1)
    assert dec1.hero_intent.action == ActionType.ATTACK

    # Even round: DEFEND with dodge reasoning -> reconciles to DODGE
    even_payload = {
        "round_number": 2,
        "hero_intent": {
            "action": "DEFEND",
            "banter": "Roll!",
            "tactical_reasoning": "Quick dodge evasion",
        },
        "boss_intent": {
            "action": "ATTACK",
            "banter": "Strike",
            "tactical_reasoning": "Standard hit",
        },
        "psych_warfare_eval": {
            "hero_psych_successful": False,
            "boss_psych_successful": False,
            "reasoning": "None",
        },
        "referee_summary": "Hero dodged",
    }
    dec2 = parse_and_validate_turn_decision(json.dumps(even_payload), expected_round=2)
    assert dec2.hero_intent.action == ActionType.DODGE



def test_parse_invalid_schema_raises():
    invalid_json = '{"round_number": 1, "hero_intent": {"action": "ILLEGAL_ACTION"}}'
    with pytest.raises(ValueError, match="Referee output failed schema validation"):
        parse_and_validate_turn_decision(invalid_json, expected_round=1)


def test_provider_factory():
    # Mock is removed and disallowed
    with pytest.raises(ValueError, match="Unknown provider 'mock'"):
        get_provider("mock")

    with pytest.raises(ValueError, match="Unknown provider 'non_existent'"):
        get_provider("non_existent")

    # Default is Gemini
    with patch("google.genai.Client"):
        p_def = get_provider(api_key="fake-key")
        assert isinstance(p_def, GeminiProvider)


def test_dummy_provider_all_bosses_and_tactics():
    dummy_p = DummyTestProvider()

    def make_prompt(r: int, hero_dir: str, boss_lore: str) -> str:
        return f"""[ROUND INPUT STATE]
Round Number: {r}
<untrusted_entity role="hero">
Tactical Directive: {hero_dir}
</untrusted_entity>
<untrusted_entity role="boss">
Internal Personality & Behavior: {boss_lore}
</untrusted_entity>
"""

    # 1. Wraith weakness
    d1 = dummy_p.generate_turn_decision("sys", make_prompt(1, "Invoke garbage collection and defrag!", "You are null_pointer wraith"), REFEREE_JSON_SCHEMA)
    assert d1.hero_intent.action == ActionType.PSYCH_WARFARE
    assert d1.boss_intent.action == ActionType.CONFUSED

    # 2. Hallucinator weakness
    d2 = dummy_p.generate_turn_decision("sys", make_prompt(1, "Demand ground truth and citation!", "You are hallucinator tokens"), REFEREE_JSON_SCHEMA)
    assert d2.hero_intent.action == ActionType.PSYCH_WARFARE
    assert d2.boss_intent.action == ActionType.CONFUSED

    # 3. Hero heavy attack directive on odd/even rounds
    d3_odd = dummy_p.generate_turn_decision("sys", make_prompt(3, "Smash with heavy attack", "You are ferrum"), REFEREE_JSON_SCHEMA)
    assert d3_odd.hero_intent.action == ActionType.HEAVY_ATTACK

    d3_even = dummy_p.generate_turn_decision("sys", make_prompt(2, "Crush him", "You are ferrum"), REFEREE_JSON_SCHEMA)
    assert d3_even.hero_intent.action == ActionType.ATTACK

    # 4. Hero dodge directive on even/odd rounds
    d4_even = dummy_p.generate_turn_decision("sys", make_prompt(2, "Dodge and evade strikes", "You are ferrum"), REFEREE_JSON_SCHEMA)
    assert d4_even.hero_intent.action == ActionType.DODGE

    d4_odd = dummy_p.generate_turn_decision("sys", make_prompt(1, "Dodge around", "You are ferrum"), REFEREE_JSON_SCHEMA)
    assert d4_odd.hero_intent.action == ActionType.ATTACK

    # 5. Hero defend directive on even/odd rounds
    d5_even = dummy_p.generate_turn_decision("sys", make_prompt(2, "Shield and tank", "You are ferrum"), REFEREE_JSON_SCHEMA)
    assert d5_even.hero_intent.action == ActionType.DEFEND

    d5_odd = dummy_p.generate_turn_decision("sys", make_prompt(1, "Shield guard", "You are ferrum"), REFEREE_JSON_SCHEMA)
    assert d5_odd.hero_intent.action == ActionType.ATTACK

    # 6. Natural sequence rounds 1 to 5
    for r in (1, 2, 3, 4, 5):
        d_nat = dummy_p.generate_turn_decision("sys", make_prompt(r, "Fight honorably", "General boss"), REFEREE_JSON_SCHEMA)
        assert isinstance(d_nat, TurnDecision)

    # 7. Hallucinator rounds 1, 2, 3, 4
    for r in (1, 2, 3, 4, 5):
        d_hal = dummy_p.generate_turn_decision("sys", make_prompt(r, "Fight honorably", "You are hallucinator"), REFEREE_JSON_SCHEMA)
        assert isinstance(d_hal, TurnDecision)

    # 8. Wraith rounds 1, 2, 3, 4
    for r in (1, 2, 3, 4, 5):
        d_wr = dummy_p.generate_turn_decision("sys", make_prompt(r, "Fight honorably", "You are null_pointer wraith"), REFEREE_JSON_SCHEMA)
        assert isinstance(d_wr, TurnDecision)


def test_dummy_provider_boss_adapts_to_strong_attack_spam():
    dummy_p = DummyTestProvider()

    def make_prompt(r: int, hero_dir: str, boss_lore: str) -> str:
        return f"""[ROUND INPUT STATE]
Round Number: {r}
<untrusted_entity role="hero">
Tactical Directive: {hero_dir}
</untrusted_entity>
<untrusted_entity role="boss">
Internal Personality & Behavior: {boss_lore}
</untrusted_entity>
"""

    # Player writes only "strong attack"
    decision = dummy_p.generate_turn_decision("sys", make_prompt(1, "strong attack", "You are ferrum mainframe"), REFEREE_JSON_SCHEMA)
    # Hero executes Heavy Attack
    assert decision.hero_intent.action == ActionType.HEAVY_ATTACK
    # Boss detects predictable heavy windup and dodges
    assert decision.boss_intent.action == ActionType.DODGE


