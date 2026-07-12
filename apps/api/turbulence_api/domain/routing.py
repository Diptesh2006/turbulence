from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

RoutingMetric = Literal["cost", "performance", "p50_latency", "uptime"]
RoutingProfileType = Literal["single_provider", "gateway_auto", "resilient_route"]


class RouteTarget(BaseModel):
    model: str
    provider: str | None = None


class RoutingAttempt(BaseModel):
    index: int = Field(ge=0)
    model: str
    provider: str | None = None
    simulator_managed_fallback: bool = False
    label: str


class GatewayRoutingHint(BaseModel):
    metric: RoutingMetric


class RoutingProfile(BaseModel):
    id: str
    type: RoutingProfileType
    routes: list[RouteTarget] = Field(default_factory=list)
    metric: RoutingMetric | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> RoutingProfile:
        if self.type == "single_provider":
            if len(self.routes) != 1:
                raise ValueError("single_provider requires exactly one ordered route")
            if self.metric is not None:
                raise ValueError("single_provider does not use a routing metric")
        elif self.type == "gateway_auto":
            if self.routes:
                raise ValueError("gateway_auto must not declare client-side routes")
            if self.metric is None:
                raise ValueError("gateway_auto requires a routing metric")
        elif self.type == "resilient_route":
            if len(self.routes) < 2:
                raise ValueError("resilient_route requires primary and fallback routes")
            if self.metric is not None:
                raise ValueError("resilient_route uses ordered routes, not a gateway metric")
        return self

    @classmethod
    def single_provider(cls, *, id: str, route: RouteTarget) -> RoutingProfile:
        return cls(id=id, type="single_provider", routes=[route])

    @classmethod
    def gateway_auto(cls, *, id: str, metric: RoutingMetric) -> RoutingProfile:
        return cls(id=id, type="gateway_auto", metric=metric)

    @classmethod
    def resilient_route(cls, *, id: str, routes: list[RouteTarget]) -> RoutingProfile:
        return cls(id=id, type="resilient_route", routes=routes)

    def initial_attempt(self) -> RoutingAttempt:
        if self.type == "gateway_auto":
            return RoutingAttempt(
                index=0,
                model="auto",
                provider=None,
                simulator_managed_fallback=False,
                label="gateway native auto routing",
            )

        route = self.routes[0]
        return RoutingAttempt(
            index=0,
            model=route.model,
            provider=route.provider,
            simulator_managed_fallback=False,
            label="single ordered route" if self.type == "single_provider" else "primary route",
        )

    def next_attempt_after_failure(self, previous_attempt: RoutingAttempt) -> RoutingAttempt | None:
        if self.type != "resilient_route":
            return None

        next_index = previous_attempt.index + 1
        if next_index >= len(self.routes):
            return None

        route = self.routes[next_index]
        return RoutingAttempt(
            index=next_index,
            model=route.model,
            provider=route.provider,
            simulator_managed_fallback=True,
            label="simulator-managed deterministic fallback",
        )

    def gateway_routing_hint(self) -> GatewayRoutingHint | None:
        if self.type != "gateway_auto" or self.metric is None:
            return None
        return GatewayRoutingHint(metric=self.metric)

