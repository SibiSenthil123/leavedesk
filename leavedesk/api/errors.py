"""Turn every error into the same JSON shape: {"error": {code, message, request_id, details}}."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from leavedesk.api.schemas import ErrorDetail, ErrorResponse
from leavedesk.domain.exceptions import (
    InsufficientBalanceError,
    InvalidTransitionError,
    LeaveDeskError,
    NotFoundError,
    OverlappingLeaveError,
    PermissionDeniedError,
    PolicyViolationError,
)

log = logging.getLogger("leavedesk.api")

# Domain error -> (HTTP status, machine-readable code). The domain never imports FastAPI.
DOMAIN_ERRORS: dict[type[LeaveDeskError], tuple[int, str]] = {
    NotFoundError: (404, "NOT_FOUND"),
    PermissionDeniedError: (403, "FORBIDDEN"),
    OverlappingLeaveError: (409, "OVERLAPPING_LEAVE"),
    InvalidTransitionError: (409, "INVALID_TRANSITION"),
    InsufficientBalanceError: (422, "INSUFFICIENT_BALANCE"),
    PolicyViolationError: (422, "POLICY_VIOLATION"),
}

HTTP_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
}


def error_response(
    request: Request,
    status: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            request_id=getattr(request.state, "request_id", None),
            details=details,
        )
    )
    return JSONResponse(
        status_code=status,
        content=jsonable_encoder(body, exclude_none=True),
        headers=headers,
    )


def _clean(errors: Any) -> list[dict[str, Any]]:
    """Keep only where and what; drop echoed input so passwords never come back."""
    return [{"loc": list(e.get("loc", [])), "msg": e.get("msg", "")} for e in errors]


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(LeaveDeskError)
    async def domain_error(request: Request, exc: LeaveDeskError) -> JSONResponse:
        for error_type in type(exc).__mro__:
            if error_type in DOMAIN_ERRORS:
                status, code = DOMAIN_ERRORS[error_type]
                break
        else:
            status, code = 400, "BAD_REQUEST"
        return error_response(request, status, code, str(exc))

    @app.exception_handler(RequestValidationError)
    async def request_invalid(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return error_response(
            request, 422, "VALIDATION_ERROR", "request is invalid", _clean(exc.errors())
        )

    @app.exception_handler(ValidationError)
    async def model_invalid(request: Request, exc: ValidationError) -> JSONResponse:
        return error_response(
            request, 422, "VALIDATION_ERROR", "data is invalid", _clean(exc.errors())
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = HTTP_CODES.get(exc.status_code, "ERROR")
        return error_response(
            request,
            exc.status_code,
            code,
            str(exc.detail),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Log the details for us; tell the client nothing about our internals.
        log.exception("unhandled error")
        return error_response(request, 500, "INTERNAL_ERROR", "something went wrong")
