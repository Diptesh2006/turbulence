from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    service: str
    status: str
    version: str
    environment: str
    simulation_mode: str

    model_config = ConfigDict(json_schema_extra={"examples": [{"service": "turbulence-api"}]})

