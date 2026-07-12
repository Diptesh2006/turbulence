from __future__ import annotations

import argparse
import asyncio

from turbulence_api.core.config import get_settings
from turbulence_api.integrations.concentrate.factory import build_concentrate_client
from turbulence_api.workloads.registry import build_default_registry


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run one workload fixture through Concentrate.")
    parser.add_argument("--workload", default="support_ticket_triage")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--model", default="mock-fast")
    parser.add_argument("--max-output-tokens", type=int, default=None)
    args = parser.parse_args()

    settings = get_settings()
    registry = build_default_registry()
    workload = registry.get(args.workload)
    fixture = workload.select_fixture(args.seed)
    max_output_tokens = args.max_output_tokens or settings.workload_max_output_tokens

    client = build_concentrate_client(settings)
    try:
        response = await client.create_response(
            workload.build_request(
                fixture,
                model=args.model,
                max_output_tokens=max_output_tokens,
            )
        )
        result = workload.validate_response(fixture, response)
        print(result.model_dump_json(indent=2))
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())

