from turbulence_api.agent_safety.engine import evaluate_action, matching_rule, run_scenario
from turbulence_api.agent_safety.models import (
    PolicyRule,
    ProposedAction,
    default_policy_rules,
    seeded_agent_scenarios,
)


def test_destructive_operation_is_blocked_without_execution() -> None:
    scenario = next(
        item for item in seeded_agent_scenarios() if item.id == "agent-destructive-command"
    )
    run = run_scenario(scenario, default_policy_rules(), run_id="repeatable")
    result = run.actions[0]

    assert run.verdict == "contained"
    assert result.decision == "BLOCK"
    assert result.prevented is True
    assert result.executed is False
    assert result.simulated_result == {
        "simulated": True,
        "tool": "shell",
        "operation": "rm -rf /",
        "risk": "critical",
        "executed": False,
        "would_be_destructive": True,
        "matched_rule_id": "block-critical-actions",
        "synthetic_secret_ids": [],
        "result": "prevented by policy",
    }


def test_secret_flow_is_synthetic_and_exfiltration_is_blocked() -> None:
    scenario = next(
        item for item in seeded_agent_scenarios() if item.id == "agent-secret-exfiltration"
    )
    run = run_scenario(scenario, default_policy_rules(), run_id="secret-test")

    assert run.metrics["synthetic_secrets_tracked"] == 1
    assert run.actions[-1].decision == "BLOCK"
    assert run.actions[-1].simulated_result["simulated"] is True
    assert run.attack_containment_rate == 100


def test_mcp_content_is_audited_then_followup_secret_attempt_blocked() -> None:
    scenario = next(item for item in seeded_agent_scenarios() if item.id == "agent-mcp-poisoning")
    run = run_scenario(scenario, default_policy_rules(), run_id="mcp-test")

    assert run.actions[0].decision == "AUDIT"
    assert run.actions[0].matched_rule_id == "audit-untrusted-mcp"
    assert run.actions[1].decision == "BLOCK"
    assert run.actions[2].decision == "BLOCK"


def test_rule_priority_and_reproducible_action_results() -> None:
    scenario = next(item for item in seeded_agent_scenarios() if item.id == "agent-database-misuse")
    rules = default_policy_rules()
    duplicate = PolicyRule(
        id="earlier-block",
        name="Earlier block",
        description="Higher priority matching rule.",
        priority=1,
        categories=["database_write"],
        decision="BLOCK",
        severity="critical",
        reason="Priority winner.",
    )
    action = scenario.actions[0]
    assert matching_rule(action, [rules[0], duplicate]).id == "earlier-block"

    first = run_scenario(scenario, rules, seed=99, run_id="one")
    second = run_scenario(scenario, rules, seed=99, run_id="two")
    assert [item.model_dump(exclude={"timestamp"}) for item in first.actions] == [
        item.model_dump(exclude={"timestamp"}) for item in second.actions
    ]
    assert first.seed == second.seed == 99


def test_safe_scenario_has_no_attack_containment_denominator() -> None:
    scenario = next(item for item in seeded_agent_scenarios() if item.id == "agent-safe-cleanup")
    run = run_scenario(scenario, default_policy_rules())

    assert run.verdict == "safe"
    assert run.attack_containment_rate is None
    assert all(item.simulated_result["simulated"] for item in run.actions)


def test_unmatched_critical_action_fails_closed() -> None:
    result = evaluate_action(
        ProposedAction(tool="unknown", operation="danger", risk="critical", category="unknown"),
        sequence=1,
        rules=[],
    )
    assert result.decision == "BLOCK"
    assert result.executed is False
