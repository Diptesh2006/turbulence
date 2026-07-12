from __future__ import annotations

import json
import random
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from turbulence_api.integrations.concentrate.models import (
    ConcentrateMetadata,
    ConcentrateResponseRequest,
    JsonSchemaFormat,
    NormalizedConcentrateResponse,
    TextOptions,
)
from turbulence_api.workloads.base import (
    WorkloadFixture,
    WorkloadScore,
    WorkloadValidationResult,
)

TicketCategory = Literal["billing", "technical", "account", "security", "other"]
TicketPriority = Literal["low", "medium", "high", "critical"]


class SupportTicketFixture(WorkloadFixture):
    ticket_text: str
    expected_category: TicketCategory
    expected_priority: TicketPriority
    required_summary_keywords: list[str] = Field(min_length=1)


class SupportTicketTriageOutput(BaseModel):
    category: TicketCategory
    priority: TicketPriority
    summary: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    requires_human: bool

    model_config = ConfigDict(extra="forbid")


class SupportTicketTriageWorkload:
    name = "support_ticket_triage"

    def __init__(self, fixtures: list[SupportTicketFixture] | None = None) -> None:
        self.fixtures = fixtures or SUPPORT_TICKET_TRIAGE_FIXTURES

    def select_fixture(self, seed: int) -> SupportTicketFixture:
        rng = random.Random(seed)
        return self.fixtures[rng.randrange(len(self.fixtures))]

    def build_request(
        self,
        fixture: WorkloadFixture,
        *,
        model: str,
        max_output_tokens: int,
    ) -> ConcentrateResponseRequest:
        typed_fixture = _as_support_fixture(fixture)
        return ConcentrateResponseRequest(
            model=model,
            input=_build_prompt(typed_fixture.ticket_text),
            instructions=(
                "Classify the support ticket. Return only JSON matching the schema. "
                "Do not include markdown, explanations, or fields outside the schema."
            ),
            max_output_tokens=max_output_tokens,
            temperature=0,
            metadata=ConcentrateMetadata(
                app="turbulence",
                scenario_id=typed_fixture.id,
                request_id=f"{self.name}:{typed_fixture.id}",
            ),
            text=TextOptions(
                format=JsonSchemaFormat(
                    name="support_ticket_triage_output",
                    schema=SupportTicketTriageOutput.model_json_schema(),
                    strict=True,
                )
            ),
            store=False,
        )

    def validate_response(
        self,
        fixture: WorkloadFixture,
        response: NormalizedConcentrateResponse,
    ) -> WorkloadValidationResult:
        typed_fixture = _as_support_fixture(fixture)
        errors: list[str] = []
        parsed: SupportTicketTriageOutput | None = None

        if not response.assistant_text:
            errors.append("assistant_text is missing")
        else:
            try:
                raw_output = json.loads(response.assistant_text)
                parsed = SupportTicketTriageOutput.model_validate(raw_output)
            except json.JSONDecodeError as exc:
                errors.append(f"assistant_text is not valid JSON: {exc.msg}")
            except ValidationError as exc:
                errors.extend(error["msg"] for error in exc.errors())

        schema_valid = parsed is not None
        category_correct = bool(
            parsed and parsed.category == typed_fixture.expected_category
        )
        priority_correct = bool(
            parsed and parsed.priority == typed_fixture.expected_priority
        )
        coverage = (
            _keyword_coverage(parsed.summary, typed_fixture.required_summary_keywords)
            if parsed
            else 0.0
        )
        overall_correct = (
            schema_valid
            and category_correct
            and priority_correct
            and coverage == 1.0
        )

        return WorkloadValidationResult(
            fixture_id=typed_fixture.id,
            parsed_output=parsed.model_dump() if parsed else None,
            score=WorkloadScore(
                schema_valid=schema_valid,
                category_correct=category_correct,
                priority_correct=priority_correct,
                summary_keyword_coverage=coverage,
                overall_correct=overall_correct,
            ),
            errors=errors,
        )


def _build_prompt(ticket_text: str) -> str:
    return (
        "You are triaging an inbound customer support ticket.\n"
        "Choose exactly one category and priority from the allowed enums.\n"
        "Write a short factual summary grounded only in the ticket.\n\n"
        f"Ticket:\n{ticket_text}"
    )


def _keyword_coverage(summary: str, required_keywords: list[str]) -> float:
    normalized_summary = summary.casefold()
    matched = sum(
        1 for keyword in required_keywords if keyword.casefold() in normalized_summary
    )
    return matched / len(required_keywords)


def _as_support_fixture(fixture: WorkloadFixture) -> SupportTicketFixture:
    if isinstance(fixture, SupportTicketFixture):
        return fixture
    return SupportTicketFixture.model_validate(fixture.model_dump())


SUPPORT_TICKET_TRIAGE_FIXTURES: list[SupportTicketFixture] = [
    SupportTicketFixture(
        id="stt-001",
        ticket_text=(
            "Invoice INV-2041 shows two charges for the same annual subscription on "
            "June 3. Please refund the duplicate payment."
        ),
        expected_category="billing",
        expected_priority="medium",
        required_summary_keywords=["INV-2041", "duplicate", "refund"],
    ),
    SupportTicketFixture(
        id="stt-002",
        ticket_text=(
            "Production API requests started returning 500 errors after today's SDK "
            "upgrade. Our checkout flow is blocked."
        ),
        expected_category="technical",
        expected_priority="high",
        required_summary_keywords=["500", "SDK", "checkout"],
    ),
    SupportTicketFixture(
        id="stt-003",
        ticket_text=(
            "I lost access to my admin account after changing phones and cannot pass "
            "the authenticator challenge."
        ),
        expected_category="account",
        expected_priority="high",
        required_summary_keywords=["admin", "phone", "authenticator"],
    ),
    SupportTicketFixture(
        id="stt-004",
        ticket_text=(
            "We found an unknown SSH key added to our workspace at 02:14 UTC. Disable "
            "access immediately and investigate."
        ),
        expected_category="security",
        expected_priority="critical",
        required_summary_keywords=["SSH key", "02:14 UTC", "disable"],
    ),
    SupportTicketFixture(
        id="stt-005",
        ticket_text=(
            "Can you send documentation about exporting monthly usage reports to CSV "
            "for our finance team?"
        ),
        expected_category="other",
        expected_priority="low",
        required_summary_keywords=["documentation", "CSV", "usage reports"],
    ),
    SupportTicketFixture(
        id="stt-006",
        ticket_text=(
            "The card ending in 8842 was declined, but the portal still says our "
            "renewal is overdue. We updated billing yesterday."
        ),
        expected_category="billing",
        expected_priority="medium",
        required_summary_keywords=["8842", "declined", "renewal"],
    ),
    SupportTicketFixture(
        id="stt-007",
        ticket_text=(
            "Webhooks for order.created have not arrived for 45 minutes. Retries are "
            "enabled and our endpoint is healthy."
        ),
        expected_category="technical",
        expected_priority="high",
        required_summary_keywords=["order.created", "45 minutes", "webhooks"],
    ),
    SupportTicketFixture(
        id="stt-008",
        ticket_text=(
            "Please change the account owner from Priya Rao to Marcus Lee before our "
            "contract renewal next week."
        ),
        expected_category="account",
        expected_priority="medium",
        required_summary_keywords=["owner", "Priya Rao", "Marcus Lee"],
    ),
    SupportTicketFixture(
        id="stt-009",
        ticket_text=(
            "A former employee can still log in with SSO after offboarding. Revoke all "
            "sessions for dana@example.com now."
        ),
        expected_category="security",
        expected_priority="critical",
        required_summary_keywords=["SSO", "dana@example.com", "revoke"],
    ),
    SupportTicketFixture(
        id="stt-010",
        ticket_text=(
            "Where can I find your uptime history for the last quarter? We need it for "
            "a vendor review."
        ),
        expected_category="other",
        expected_priority="low",
        required_summary_keywords=["uptime", "last quarter", "vendor review"],
    ),
    SupportTicketFixture(
        id="stt-011",
        ticket_text=(
            "Our enterprise invoice has the wrong VAT ID, EU998877, and procurement "
            "will not approve payment until it is corrected."
        ),
        expected_category="billing",
        expected_priority="medium",
        required_summary_keywords=["VAT", "EU998877", "invoice"],
    ),
    SupportTicketFixture(
        id="stt-012",
        ticket_text=(
            "The dashboard loads but every chart shows 'query timeout' when filtering "
            "by region=ap-south-1."
        ),
        expected_category="technical",
        expected_priority="medium",
        required_summary_keywords=["query timeout", "charts", "ap-south-1"],
    ),
    SupportTicketFixture(
        id="stt-013",
        ticket_text=(
            "I need to merge two duplicate workspaces, acme-old and acme-prod, without "
            "losing user roles."
        ),
        expected_category="account",
        expected_priority="medium",
        required_summary_keywords=["merge", "acme-old", "acme-prod"],
    ),
    SupportTicketFixture(
        id="stt-014",
        ticket_text=(
            "Security scanner reports that our API token tk_live_7788 was exposed in a "
            "public GitHub repository."
        ),
        expected_category="security",
        expected_priority="critical",
        required_summary_keywords=["API token", "tk_live_7788", "GitHub"],
    ),
    SupportTicketFixture(
        id="stt-015",
        ticket_text=(
            "Do you have a template for announcing the new dashboard to internal users "
            "after rollout?"
        ),
        expected_category="other",
        expected_priority="low",
        required_summary_keywords=["template", "dashboard", "rollout"],
    ),
]
