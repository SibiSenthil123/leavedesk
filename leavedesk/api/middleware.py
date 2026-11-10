"""Give every request an id, return it as X-Request-ID, and log one line per request."""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

log = logging.getLogger("leavedesk.api")

# Accept a caller's id only if it looks harmless (stops log injection).
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def register_request_id(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("X-Request-ID", "")
        rid = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex[:12]
        request.state.request_id = rid
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = rid
        log.info(
            "rid=%s %s %s -> %s (%.1f ms)",
            rid,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response
