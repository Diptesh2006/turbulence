from __future__ import annotations


class ConcentrateError(Exception):
    default_message = "Concentrate gateway error"

    def __init__(self, message: str | None = None, *, status_code: int | None = None) -> None:
        super().__init__(message or self.default_message)
        self.status_code = status_code


class ConcentrateConfigurationError(ConcentrateError):
    default_message = "Concentrate configuration error"


class ConcentrateAuthenticationError(ConcentrateError):
    default_message = "Concentrate authentication failed"


class ConcentrateInsufficientCreditsError(ConcentrateError):
    default_message = "Concentrate account has insufficient credits"


class ConcentrateProviderDependencyError(ConcentrateError):
    default_message = "Concentrate provider dependency failed"


class ConcentrateRateLimitError(ConcentrateError):
    default_message = "Concentrate rate limit exceeded"


class ConcentrateTimeoutError(ConcentrateError):
    default_message = "Concentrate request timed out"


class ConcentrateMalformedResponseError(ConcentrateError):
    default_message = "Concentrate returned a malformed response"


class ConcentrateGatewayError(ConcentrateError):
    default_message = "Concentrate gateway request failed"

