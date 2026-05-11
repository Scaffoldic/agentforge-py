"""Tests for `modules.guardrails` + top-level `guardrail_policy`
config schema (feat-018 chunk 1)."""

from __future__ import annotations

from agentforge_core.config.schema import (
    AgentForgeConfig,
    GuardrailEntry,
    GuardrailPolicy,
    GuardrailsConfig,
    ModulesConfig,
)


def test_guardrails_defaults_to_empty_lists_and_defaults_on() -> None:
    cfg = AgentForgeConfig()
    assert cfg.modules.guardrails.defaults is True
    assert cfg.modules.guardrails.input == []
    assert cfg.modules.guardrails.output == []
    assert cfg.modules.guardrails.tool_gates == []


def test_guardrails_explicit_entries() -> None:
    cfg = AgentForgeConfig(
        modules=ModulesConfig(
            guardrails=GuardrailsConfig(
                input=[GuardrailEntry(name="prompt_injection_basic")],
                output=[
                    GuardrailEntry(
                        name="presidio",
                        config={"entities": ["EMAIL_ADDRESS"], "score_threshold": 0.5},
                    ),
                ],
                tool_gates=[GuardrailEntry(name="capability_check")],
            )
        ),
    )
    assert cfg.modules.guardrails.input[0].name == "prompt_injection_basic"
    assert cfg.modules.guardrails.output[0].config["entities"] == ["EMAIL_ADDRESS"]
    assert cfg.modules.guardrails.tool_gates[0].name == "capability_check"


def test_guardrail_policy_at_top_level() -> None:
    cfg = AgentForgeConfig(
        guardrail_policy=GuardrailPolicy(on_output_violation="block"),
    )
    assert cfg.guardrail_policy.on_output_violation == "block"
    assert cfg.guardrail_policy.on_input_violation == "block"


def test_defaults_disable_is_explicit() -> None:
    cfg = AgentForgeConfig(
        modules=ModulesConfig(guardrails=GuardrailsConfig(defaults=False)),
    )
    assert cfg.modules.guardrails.defaults is False
