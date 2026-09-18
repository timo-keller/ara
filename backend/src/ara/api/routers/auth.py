"""OIDC and session HTTP transport endpoints."""

import base64
import hashlib
import hmac
import json
import uuid
from collections.abc import Mapping
from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ara.api.routers import auth_router
from ara.api.schemas.auth import SessionSchema, SessionUserSchema
from ara.core.config import get_settings
from ara.core.errors import DomainError
from ara.domain.models import ApplicationSession, User
from ara.infrastructure.database import get_session
from ara.infrastructure.oidc import OidcClient
from ara.services.auth import (
    SESSION_TTL_SECONDS,
    AuthenticationService,
    csrf_token_hash,
)
from ara.services.oidc import STATE_TTL_SECONDS, OidcLoginService

STATE_COOKIE, SESSION_COOKIE, CSRF_COOKIE, CSRF_HEADER = (
    "ara_oidc_state",
    "ara_session",
    "ara_csrf",
    "X-CSRF-Token",
)


def get_oidc_client(request: Request) -> OidcClient:
    client = getattr(request.app.state, "oidc_client", None)
    return client if isinstance(client, OidcClient) else OidcClient(get_settings())


def _encode(payload: Mapping[str, Any], secret: str) -> str:
    body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).rstrip(b"=")
    signature = (
        base64.urlsafe_b64encode(
            hmac.new(secret.encode(), body, hashlib.sha256).digest()
        )
        .rstrip(b"=")
        .decode()
    )
    return f"{body.decode()}.{signature}"


def _decode(value: str | None, secret: str) -> dict[str, Any] | None:
    if not value or "." not in value:
        return None
    body, signature = value.split(".", 1)
    expected = (
        base64.urlsafe_b64encode(
            hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
        )
        .rstrip(b"=")
        .decode()
    )
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except ValueError, json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _set_cookie(
    response: Response, key: str, value: str, max_age: int, *, httponly: bool = True
) -> None:
    response.set_cookie(
        key,
        value,
        max_age=max_age,
        httponly=httponly,
        secure=True,
        samesite="lax",
        path="/",
    )


def _clear_cookie(response: Response, key: str) -> None:
    response.delete_cookie(key, httponly=True, secure=True, samesite="lax", path="/")


def _session_cookie_value(session_id: uuid.UUID, secret: str) -> str:
    return _encode({"session_id": str(session_id)}, secret)


async def get_current_application_session(
    request: Request, response: Response, session: AsyncSession = Depends(get_session)
) -> ApplicationSession:
    """Transport dependency that loads the service-validated live session."""
    settings = get_settings()
    payload = _decode(
        request.cookies.get(SESSION_COOKIE), settings.session_secret.get_secret_value()
    )
    try:
        session_id = uuid.UUID(str(payload["session_id"])) if payload else None
    except KeyError, ValueError:
        session_id = None
    if session_id is None:
        raise DomainError(
            "authentication_required", "Authentication required", status_code=401
        )
    application_session, renewed = await AuthenticationService(
        session
    ).get_live_session(session_id)
    if application_session is None:
        raise DomainError(
            "authentication_required", "Authentication required", status_code=401
        )
    if renewed:
        _set_cookie(
            response,
            SESSION_COOKIE,
            _session_cookie_value(
                application_session.id, settings.session_secret.get_secret_value()
            ),
            SESSION_TTL_SECONDS,
        )
        _set_cookie(
            response,
            CSRF_COOKIE,
            request.cookies.get(CSRF_COOKIE, ""),
            SESSION_TTL_SECONDS,
            httponly=False,
        )
    return application_session


async def require_authenticated_user(
    application_session: ApplicationSession = Depends(get_current_application_session),
) -> User:
    """Reusable dependency for protected REST routes."""
    return application_session.user


async def require_csrf(
    request: Request,
    application_session: ApplicationSession = Depends(get_current_application_session),
) -> None:
    """Reusable dependency for unsafe authenticated REST routes."""
    cookie, header = request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER)
    if not (
        isinstance(cookie, str)
        and isinstance(header, str)
        and hmac.compare_digest(cookie, header)
        and hmac.compare_digest(
            csrf_token_hash(header), application_session.csrf_token_hash
        )
    ):
        raise DomainError(
            "csrf_validation_failed", "CSRF validation failed", status_code=403
        )


@auth_router.get("/login")
async def login(
    oidc: Annotated[OidcClient, Depends(get_oidc_client)],
) -> RedirectResponse:
    metadata, state, nonce, issued_at = await OidcLoginService(oidc).begin()
    cookie = _encode(
        {"state": state, "nonce": nonce, "issued_at": issued_at},
        oidc.settings.session_secret.get_secret_value(),
    )
    query = urlencode(
        {
            "response_type": "code",
            "client_id": oidc.settings.oidc_client_id,
            "redirect_uri": oidc.redirect_uri,
            "scope": " ".join(oidc.settings.oidc_scopes),
            "state": state,
            "nonce": nonce,
        }
    )
    response = RedirectResponse(f"{metadata['authorization_endpoint']}?{query}", 302)
    _set_cookie(response, STATE_COOKIE, cookie, STATE_TTL_SECONDS)
    return response


@auth_router.get("/callback")
async def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    oidc: OidcClient = Depends(get_oidc_client),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    state_data = _decode(
        request.cookies.get(STATE_COOKIE),
        oidc.settings.session_secret.get_secret_value(),
    )
    application_session, csrf_token = await OidcLoginService(oidc).complete(
        session, code=code, state=state, error=error, state_data=state_data
    )
    response = RedirectResponse(str(oidc.settings.public_url), 302)
    _set_cookie(
        response,
        SESSION_COOKIE,
        _session_cookie_value(
            application_session.id, oidc.settings.session_secret.get_secret_value()
        ),
        SESSION_TTL_SECONDS,
    )
    _set_cookie(response, CSRF_COOKIE, csrf_token, SESSION_TTL_SECONDS, httponly=False)
    _clear_cookie(response, STATE_COOKIE)
    return response


@auth_router.get(
    "/session", response_model=SessionSchema, response_model_exclude_none=True
)
async def current_session(
    request: Request, response: Response, session: AsyncSession = Depends(get_session)
) -> SessionSchema:
    try:
        application_session = await get_current_application_session(
            request, response, session
        )
    except DomainError:
        return SessionSchema(authenticated=False)
    user = application_session.user
    return SessionSchema(
        authenticated=True,
        user=SessionUserSchema(
            id=str(user.id), display_name=user.display_name, email=user.email
        ),
    )


@auth_router.post("/logout", status_code=204)
async def logout(
    application_session: ApplicationSession = Depends(get_current_application_session),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await AuthenticationService(session).revoke_session(application_session)
    response = Response(status_code=204)
    for key in (SESSION_COOKIE, STATE_COOKIE, CSRF_COOKIE):
        _clear_cookie(response, key)
    return response
