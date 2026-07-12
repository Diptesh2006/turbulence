from __future__ import annotations


class ServiceError(Exception):
    status_code = 500
    title = "Internal Server Error"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(ServiceError):
    status_code = 404
    title = "Not Found"


class ConflictError(ServiceError):
    status_code = 409
    title = "Conflict"


class ValidationServiceError(ServiceError):
    status_code = 422
    title = "Validation Error"

