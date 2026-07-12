from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = Field(default="turbulence-api", validation_alias="SERVICE_NAME")
    version: str = Field(default="0.1.0", validation_alias="APP_VERSION")
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    simulation_mode: str = Field(default="disabled", validation_alias="SIMULATION_MODE")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./turbulence.db",
        validation_alias="DATABASE_URL",
    )
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"],
        validation_alias="CORS_ORIGINS",
    )
    cnai_api_key: str | None = Field(default=None, validation_alias="CNAI_API_KEY")
    cnai_base_url: str = Field(
        default="https://api.concentrate.ai/v1",
        validation_alias="CNAI_BASE_URL",
    )
    cnai_timeout_seconds: float = Field(default=30.0, validation_alias="CNAI_TIMEOUT_SECONDS")
    cnai_mode: str = Field(default="mock", validation_alias="CNAI_MODE")
    workload_max_output_tokens: int = Field(
        default=128,
        validation_alias="WORKLOAD_MAX_OUTPUT_TOKENS",
    )
    max_simulation_requests: int = Field(default=100, validation_alias="MAX_SIMULATION_REQUESTS")
    max_simulation_concurrency: int = Field(
        default=10,
        validation_alias="MAX_SIMULATION_CONCURRENCY",
    )
    openai_model_id: str = Field(default="gpt-4.1-mini", validation_alias="OPENAI_MODEL_ID")
    anthropic_model_id: str = Field(
        default="claude-3-5-haiku-latest",
        validation_alias="ANTHROPIC_MODEL_ID",
    )
    google_model_id: str = Field(
        default="gemini-1.5-flash",
        validation_alias="GOOGLE_MODEL_ID",
    )
    mock_model_id: str = Field(default="mock-fast", validation_alias="MOCK_MODEL_ID")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("cnai_mode")
    @classmethod
    def validate_concentrate_mode(cls, value: str) -> str:
        mode = value.lower()
        if mode not in {"mock", "live"}:
            raise ValueError("CNAI_MODE must be either 'mock' or 'live'")
        return mode


@lru_cache
def get_settings() -> Settings:
    return Settings()
