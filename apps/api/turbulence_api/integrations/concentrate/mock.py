from __future__ import annotations

import hashlib
import json
import random
from typing import Any

from turbulence_api.integrations.concentrate.models import (
    ConcentrateHealth,
    ConcentrateModel,
    ConcentrateResponseRequest,
    Cost,
    NormalizedConcentrateResponse,
    Usage,
)


class MockConcentrateClient:
    def __init__(self, *, seed: int = 0) -> None:
        self._seed = seed

    async def health_check(self) -> ConcentrateHealth:
        return ConcentrateHealth(mode="mock", status="ok", is_mock=True, configured=True)

    async def list_models(self) -> list[ConcentrateModel]:
        return [
            ConcentrateModel(id="mock-fast", name="Mock Fast", provider="mock"),
            ConcentrateModel(id="mock-reasoning", name="Mock Reasoning", provider="mock"),
        ]

    async def create_response(
        self, request: ConcentrateResponseRequest
    ) -> NormalizedConcentrateResponse:
        fingerprint = _fingerprint(
            self._seed,
            request.model,
            str(request.input),
            request.instructions,
        )
        rng = random.Random(fingerprint)
        response_id = f"mock-resp-{fingerprint[:16]}"
        assistant_text = _mock_structured_response(request) if request.text else "mock response"
        input_tokens = 8 + rng.randint(0, 12)
        output_tokens = min(request.max_output_tokens or 16, 4 + rng.randint(0, 8))

        return NormalizedConcentrateResponse(
            id=response_id,
            model=request.model,
            provider="mock",
            assistant_text=assistant_text,
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
            cost=Cost(total=0.0),
            status="completed",
            errors=[],
            is_mock=True,
        )

    async def aclose(self) -> None:
        return None


def _fingerprint(seed: int, *parts: str | None) -> str:
    digest = hashlib.sha256()
    digest.update(str(seed).encode("utf-8"))
    for part in parts:
        digest.update(b"\0")
        digest.update((part or "").encode("utf-8"))
    return digest.hexdigest()


def _mock_structured_response(request: ConcentrateResponseRequest) -> str:
    format_name = _format_name(request)
    if format_name == "support_ticket_triage_output":
        return json.dumps(_triage_payload(str(request.input)), separators=(",", ":"))
    return '{"ok": true, "mode": "mock"}'


def _format_name(request: ConcentrateResponseRequest) -> str | None:
    if not request.text or not request.text.format:
        return None
    if isinstance(request.text.format, dict):
        value = request.text.format.get("name")
        return str(value) if value else None
    return request.text.format.name


def _triage_payload(prompt: str) -> dict[str, Any]:
    text = prompt.casefold()
    if any(term in text for term in ["unknown ssh", "former employee", "exposed", "token"]):
        category = "security"
        priority = "critical"
        requires_human = True
    elif any(term in text for term in ["invoice", "charge", "refund", "billing", "card", "vat"]):
        category = "billing"
        priority = "medium"
        requires_human = True
    elif any(term in text for term in ["500", "webhook", "query timeout", "sdk", "chart"]):
        category = "technical"
        priority = (
            "high" if any(term in text for term in ["500", "checkout", "webhook"]) else "medium"
        )
        requires_human = True
    elif any(
        term in text for term in ["admin account", "account owner", "workspace", "authenticator"]
    ):
        category = "account"
        priority = "high" if "authenticator" in text else "medium"
        requires_human = True
    else:
        category = "other"
        priority = "low"
        requires_human = False

    summary = _extract_ticket_summary(prompt)
    if "query timeout" in text and "ap-south-1" in text and "charts" not in summary.casefold():
        summary = f"{summary} Multiple charts report query timeout in ap-south-1."

    return {
        "category": category,
        "priority": priority,
        "summary": summary,
        "confidence": 0.82,
        "requires_human": requires_human,
    }


def _extract_ticket_summary(prompt: str) -> str:
    marker = "Ticket:\n"
    if marker in prompt:
        return prompt.split(marker, maxsplit=1)[1].strip()
    return prompt[:200].strip()
