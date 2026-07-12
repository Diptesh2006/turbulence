from __future__ import annotations

from turbulence_api.integrations.concentrate.models import NormalizedConcentrateResponse
from turbulence_api.workloads.support_ticket_triage import (
    SUPPORT_TICKET_TRIAGE_FIXTURES,
    SupportTicketTriageWorkload,
)


def test_fixture_count_and_required_fields() -> None:
    assert len(SUPPORT_TICKET_TRIAGE_FIXTURES) == 15
    assert all(fixture.required_summary_keywords for fixture in SUPPORT_TICKET_TRIAGE_FIXTURES)


def test_seed_selection_is_deterministic() -> None:
    workload = SupportTicketTriageWorkload()

    assert workload.select_fixture(7) == workload.select_fixture(7)
    assert workload.select_fixture(8).id != ""


def test_build_request_uses_concentrate_json_schema_format() -> None:
    workload = SupportTicketTriageWorkload()
    fixture = workload.select_fixture(1)

    request = workload.build_request(fixture, model="mock-fast", max_output_tokens=64)
    payload = request.model_dump(by_alias=True, exclude_none=True)

    assert payload["max_output_tokens"] == 64
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["name"] == "support_ticket_triage_output"
    assert payload["text"]["format"]["strict"] is True
    assert "expected_category" not in payload["input"]
    assert "expected_priority" not in payload["input"]


def test_valid_output_scores_correct() -> None:
    workload = SupportTicketTriageWorkload()
    fixture = SUPPORT_TICKET_TRIAGE_FIXTURES[0]
    response = NormalizedConcentrateResponse(
        id="resp-1",
        assistant_text=(
            '{"category":"billing","priority":"medium","summary":'
            '"Invoice INV-2041 has a duplicate charge and refund request.",'
            '"confidence":0.91,"requires_human":true}'
        ),
    )

    result = workload.validate_response(fixture, response)

    assert result.errors == []
    assert result.score.schema_valid is True
    assert result.score.category_correct is True
    assert result.score.priority_correct is True
    assert result.score.summary_keyword_coverage == 1.0
    assert result.score.overall_correct is True


def test_invalid_json_output_scores_schema_invalid() -> None:
    workload = SupportTicketTriageWorkload()
    fixture = SUPPORT_TICKET_TRIAGE_FIXTURES[0]
    response = NormalizedConcentrateResponse(id="resp-1", assistant_text="not-json")

    result = workload.validate_response(fixture, response)

    assert result.score.schema_valid is False
    assert result.score.overall_correct is False
    assert result.errors


def test_incomplete_output_scores_schema_invalid() -> None:
    workload = SupportTicketTriageWorkload()
    fixture = SUPPORT_TICKET_TRIAGE_FIXTURES[0]
    response = NormalizedConcentrateResponse(
        id="resp-1",
        assistant_text='{"category":"billing","summary":"Invoice INV-2041 duplicate refund."}',
    )

    result = workload.validate_response(fixture, response)

    assert result.score.schema_valid is False
    assert result.score.overall_correct is False
    assert result.errors


def test_extra_field_output_scores_schema_invalid() -> None:
    workload = SupportTicketTriageWorkload()
    fixture = SUPPORT_TICKET_TRIAGE_FIXTURES[0]
    response = NormalizedConcentrateResponse(
        id="resp-1",
        assistant_text=(
            '{"category":"billing","priority":"medium","summary":'
            '"Invoice INV-2041 duplicate refund.","confidence":0.9,'
            '"requires_human":true,"extra":"not allowed"}'
        ),
    )

    result = workload.validate_response(fixture, response)

    assert result.score.schema_valid is False
    assert result.score.overall_correct is False
    assert result.errors


def test_summary_keyword_coverage_is_fractional_without_llm_judge() -> None:
    workload = SupportTicketTriageWorkload()
    fixture = SUPPORT_TICKET_TRIAGE_FIXTURES[0]
    response = NormalizedConcentrateResponse(
        id="resp-1",
        assistant_text=(
            '{"category":"billing","priority":"medium","summary":'
            '"Invoice INV-2041 has a duplicate charge.",'
            '"confidence":0.91,"requires_human":true}'
        ),
    )

    result = workload.validate_response(fixture, response)

    assert result.score.schema_valid is True
    assert result.score.summary_keyword_coverage == 2 / 3
    assert result.score.overall_correct is False

