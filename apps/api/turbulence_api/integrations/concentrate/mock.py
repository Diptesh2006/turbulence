from __future__ import annotations

import hashlib
import random

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
        assistant_text = '{"ok": true, "mode": "mock"}' if request.text else "mock response"
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
