from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConcentrateMetadata(BaseModel):
    app: str = "turbulence"
    run_id: str | None = None
    request_id: str | None = None
    scenario_id: str | None = None

    model_config = ConfigDict(extra="allow")


class JsonSchemaFormat(BaseModel):
    type: Literal["json_schema"] = "json_schema"
    name: str
    schema_: dict[str, Any] = Field(alias="schema")
    strict: bool = True


class TextOptions(BaseModel):
    format: JsonSchemaFormat | dict[str, Any] | None = None


class ConcentrateResponseRequest(BaseModel):
    model: str
    input: str | list[dict[str, Any]]
    instructions: str | None = None
    max_output_tokens: int | None = None
    temperature: float | None = None
    metadata: ConcentrateMetadata = Field(default_factory=ConcentrateMetadata)
    routing: dict[str, Any] | None = None
    text: TextOptions | None = None
    store: bool | None = None


class Usage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class Cost(BaseModel):
    total: float | None = None


class NormalizedConcentrateResponse(BaseModel):
    id: str
    model: str | None = None
    provider: str | None = None
    assistant_text: str | None = None
    usage: Usage | None = None
    cost: Cost | None = None
    status: str | None = None
    errors: list[str] = Field(default_factory=list)
    is_mock: bool = False


class ConcentrateHealth(BaseModel):
    mode: Literal["mock", "live"]
    status: str
    is_mock: bool
    configured: bool


class ConcentrateModel(BaseModel):
    id: str
    name: str | None = None
    provider: str | None = None
