"""The app factory. Run with: uvicorn leavedesk.api.main:create_app --factory --reload"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date

from fastapi import FastAPI

from leavedesk.api.config import Settings, get_settings
from leavedesk.api.container import build_container
from leavedesk.api.errors import register_error_handlers
from leavedesk.api.middleware import register_request_id
from leavedesk.api.routers import auth, employees, leave_requests, notifications
from leavedesk.api.seed import seed_demo_data


def create_app(
    settings: Settings | None = None, today: Callable[[], date] = date.today
) -> FastAPI:
    """Build a fresh app. Tests call this with their own settings and a fixed `today`."""
    settings = settings or get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    app = FastAPI(
        title=settings.app_name,
        version="2.0.0",
        description="LeaveDesk: apply for leave, approve it, get notified.",
    )
    app.state.settings = settings
    app.state.container = build_container(settings, today)

    if settings.seed_demo_data:
        if settings.demo_password is None:
            raise RuntimeError(
                "set LEAVEDESK_DEMO_PASSWORD or LEAVEDESK_SEED_DEMO_DATA=false"
            )
        seed_demo_data(app.state.container, settings.demo_password.get_secret_value())

    register_request_id(app)
    register_error_handlers(app)
    for module in (auth, employees, leave_requests, notifications):
        app.include_router(module.router)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
