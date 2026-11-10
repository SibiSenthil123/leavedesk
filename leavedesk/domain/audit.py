"""Cross-cutting helpers: an @audit decorator and a timing context manager."""

from __future__ import annotations

import functools
import inspect
import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, TypeVar
from uuid import UUID

log = logging.getLogger("leavedesk.audit")

F = TypeVar("F", bound=Callable[..., Any])


def audit(func: F) -> F:
    """Log every call: name, arguments and outcome. Works on sync and async functions."""

    def short(value: Any) -> str:
        """Keep log lines readable: models show as Type(id), UUIDs as their first 8 chars."""
        if isinstance(value, UUID):
            return str(value)[:8]
        if hasattr(value, "id") and isinstance(value.id, UUID):
            return f"{type(value).__name__}({str(value.id)[:8]})"
        return repr(value)

    def describe(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
        shown = args[1:] if args and hasattr(args[0], "__dict__") else args  # skip self
        parts = [short(a) for a in shown] + [
            f"{k}={short(v)}" for k, v in kwargs.items()
        ]
        return "(" + ", ".join(parts) + ")"

    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            log.info("CALL %s%s", func.__name__, describe(args, kwargs))
            try:
                result = await func(*args, **kwargs)
            except Exception as exc:
                log.warning("FAIL %s -> %s: %s", func.__name__, type(exc).__name__, exc)
                raise  # never swallow: the caller still needs the error
            log.info("OK   %s", func.__name__)
            return result

        return async_wrapper  # type: ignore[return-value]

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        log.info("CALL %s%s", func.__name__, describe(args, kwargs))
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            log.warning("FAIL %s -> %s: %s", func.__name__, type(exc).__name__, exc)
            raise
        log.info("OK   %s", func.__name__)
        return result

    return sync_wrapper  # type: ignore[return-value]


@contextmanager
def timed(label: str) -> Iterator[None]:
    """Log how long the `with` block took, even if it raised."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        log.info("TIME %s took %.1f ms", label, elapsed_ms)
