from __future__ import annotations

import asyncio
import os

from turbulence_api.integrations.concentrate.client import ConcentrateClient
from turbulence_api.integrations.concentrate.models import (
    ConcentrateMetadata,
    ConcentrateResponseRequest,
    JsonSchemaFormat,
    TextOptions,
)


async def main() -> None:
    api_key = os.getenv("CNAI_API_KEY")
    if not api_key:
        print("Skipping live Concentrate check because CNAI_API_KEY is not set.")
        return

    client = ConcentrateClient(
        api_key=api_key,
        base_url=os.getenv("CNAI_BASE_URL", "https://api.concentrate.ai/v1"),
        timeout_seconds=float(os.getenv("CNAI_TIMEOUT_SECONDS", "30")),
    )
    try:
        response = await client.create_response(
            ConcentrateResponseRequest(
                model=os.getenv("CNAI_TEST_MODEL", "concentrate-small"),
                input="Return a compact JSON object confirming this integration check.",
                instructions="Return only JSON matching the requested schema.",
                max_output_tokens=32,
                temperature=0,
                metadata=ConcentrateMetadata(app="turbulence", request_id="manual-check"),
                text=TextOptions(
                    format=JsonSchemaFormat(
                        name="turbulence_manual_check",
                        schema={
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "ok": {"type": "boolean"},
                                "message": {"type": "string"},
                            },
                            "required": ["ok", "message"],
                        },
                    )
                ),
                store=False,
            )
        )
        print(response.model_dump_json(exclude_none=True))
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())

