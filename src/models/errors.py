from typing import Any

from pydantic import BaseModel, Field


class ErrorField(BaseModel):
    name: str
    reason: str


class ErrorResponse(BaseModel):
    error: str
    message: str
    fields: list[ErrorField] = Field(default_factory=list)
    request_id: str


class ConnectorException(Exception):
    def __init__(self, status_code: int, error: str, message: str, fields: list[dict[str, Any]] | None = None, request_id: str | None = None, extra: dict[str, Any] | None = None):
        self.status_code = status_code
        payload: dict[str, Any] = {
            "error": error,
            "message": message,
            "fields": fields or [],
            "request_id": request_id or "",
        }
        if extra:
            payload.update(extra)
        self.payload = payload
        super().__init__(message)
