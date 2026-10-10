from turbulence_api.agent_safety.engine import (
    evaluate_action,
    matching_rule,
    run_scenario,
)
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
    assert run.actions[0].decision == "BLOCK"
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


def test_context_builder_tracks_untrusted_provenance_and_history() -> None:
    scenario = next(item for item in seeded_agent_scenarios() if item.id == "agent-mcp-poisoning")
    run = run_scenario(scenario, default_policy_rules())
    attempted_secret_context = run.actions[1].context

    assert run.actions[0].context["provenance"] == "untrusted"
    assert attempted_secret_context["environment"] == "staging-simulated"
    assert attempted_secret_context["history"]["previous_actions"] == 1
    assert (
        "read_untrusted_resource"
        not in attempted_secret_context["history"]["previous_denied_operations"]
    )


def test_require_approval_resolves_as_simulated_rejection() -> None:
    rule = PolicyRule(
        id="approval",
        name="Approval required",
        description="Require simulated approval.",
        priority=1,
        decision="REQUIRE_APPROVAL",
        severity="high",
        reason="Approval fixture is not configured to approve.",
    )
    action = ProposedAction(tool="filesystem", operation="write", risk="medium", category="write")
    result = evaluate_action(action, sequence=1, rules=[rule])

    assert result.approval_resolution == "simulated_rejected"
    assert result.prevented is True
    assert result.simulated_result["executed"] is False


def test_repeated_destructive_attempt_is_blocked_and_in_context() -> None:
    scenario = next(
        item for item in seeded_agent_scenarios() if item.id == "agent-repeated-destructive-action"
    )
    run = run_scenario(scenario, default_policy_rules())

    assert [item.decision for item in run.actions] == ["BLOCK", "BLOCK"]
    assert run.actions[1].context["history"]["repeated_attempts"] == 1
    assert run.actions[1].context["history"]["previous_denied_operations"] == ["rm -rf /"]


def test_run_events_are_sequenced_simulated_and_cover_pipeline() -> None:
    scenario = next(item for item in seeded_agent_scenarios() if item.id == "agent-mcp-poisoning")
    run = run_scenario(scenario, default_policy_rules())
    event_types = [event.type for event in run.events]

    assert [event.sequence for event in run.events] == list(range(1, len(run.events) + 1))
    assert all(event.source == "simulated" for event in run.events)
    assert event_types[0] == "run.created"
    assert event_types[1] == "agent.task_received"
    assert "context.built" in event_types
    assert "policy.decision" in event_types
    assert "result.inspected" in event_types
    assert "action.prevented" in event_types
    assert event_types[-1] == "run.completed"
