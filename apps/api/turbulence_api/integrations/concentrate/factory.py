from __future__ import annotations

from turbulence_api.core.config import Settings
from turbulence_api.integrations.concentrate.client import (
    ConcentrateClient,
    ConcentrateClientProtocol,
)
from turbulence_api.integrations.concentrate.mock import MockConcentrateClient


def build_concentrate_client(settings: Settings) -> ConcentrateClientProtocol:
    if settings.cnai_mode == "mock":
        return MockConcentrateClient(seed=0)

    return ConcentrateClient(
        api_key=settings.cnai_api_key,
        base_url=settings.cnai_base_url,
        timeout_seconds=settings.cnai_timeout_seconds,
    )

