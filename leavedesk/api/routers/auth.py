"""POST /auth/login returns a JWT; GET /auth/me says who the token belongs to."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from leavedesk.api.config import Settings
from leavedesk.api.deps import (
    ContainerDep,
    CurrentUser,
    direct_report_ids,
    get_settings,
)
from leavedesk.api.schemas import ErrorResponse, Me, Token
from leavedesk.api.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# Used when the email is unknown, so a wrong email takes as long as a wrong password
# (otherwise response time would reveal which emails exist).
_DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password")


@router.post("/login", response_model=Token, responses={401: {"model": ErrorResponse}})
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    container: ContainerDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Token:
    """Send `username` (your email) and `password` as form fields."""
    account = container.users.find_by_email(form.username)
    password_ok = verify_password(
        form.password, account.password_hash if account else _DUMMY_HASH
    )
    if account is None or not password_ok:
        # Same message for both cases: never reveal whether the email exists.
        raise HTTPException(
            status_code=401,
            detail="invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(
        access_token=create_access_token(account.employee_id, settings),
        expires_in=settings.access_token_minutes * 60,
    )


@router.get("/me", response_model=Me, responses={401: {"model": ErrorResponse}})
def me(user: CurrentUser, container: ContainerDep) -> Me:
    return Me(
        id=user.id,
        name=user.name,
        email=user.email,
        manager_id=user.manager_id,
        is_manager=bool(direct_report_ids(container, user)),
    )
