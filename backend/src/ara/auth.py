"""OIDC Authorization Code login and signed browser sessions."""

import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from collections.abc import Mapping
from typing import Annotated, Any
from urllib.parse import urlencode

import httpx
from authlib.jose import JoseError, JsonWebKey, jwt
from fastapi import Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ara.api import auth_router
from ara.config import Settings, get_settings
from ara.database import get_session
from ara.errors import DomainError
from ara.models import User, utc_now

STATE_COOKIE = "ara_oidc_state"
SESSION_COOKIE = "ara_session"
STATE_TTL_SECONDS = 600
SESSION_TTL_SECONDS = 8 * 60 * 60
ALLOWED_ID_TOKEN_ALGORITHMS = {
    "RS256",
    "RS384",
    "RS512",
    "PS256",
    "PS384",
    "PS512",
    "ES256",
    "ES384",
    "ES512",
    "EdDSA",
}


class OidcClient:
    """Small generic OIDC client that keeps all provider credentials server-side."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def redirect_uri(self) -> str:
        return f"{str(self.settings.public_url).rstrip('/')}/auth/callback"

    async def discover(self) -> dict[str, str]:
        issuer = str(self.settings.oidc_issuer_url).rstrip("/")
        metadata_url = f"{issuer}/.well-known/openid-configuration"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(metadata_url)
                response.raise_for_status()
                metadata = response.json()
        except (httpx.HTTPError, ValueError):
            raise DomainError(
                "authentication_unavailable",
                "The identity provider is unavailable",
                status_code=503,
            ) from None

        required = ("issuer", "authorization_endpoint", "token_endpoint", "jwks_uri")
        if not isinstance(metadata, dict) or any(
            not isinstance(metadata.get(key), str) or not metadata[key]
            for key in required
        ):
            raise DomainError(
                "authentication_unavailable",
                "The identity provider is unavailable",
                status_code=503,
            )
        if metadata["issuer"].rstrip("/") != issuer:
            raise DomainError(
                "authentication_unavailable",
                "The identity provider is unavailable",
                status_code=503,
            )
        return {key: metadata[key] for key in required}

    async def exchange_code(self, code: str, metadata: Mapping[str, str]) -> str:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    metadata["token_endpoint"],
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": self.redirect_uri,
                    },
                    auth=(
                        self.settings.oidc_client_id,
                        self.settings.oidc_client_secret.get_secret_value(),
                    ),
                )
                response.raise_for_status()
                tokens = response.json()
        except (httpx.HTTPError, ValueError):
            raise DomainError(
                "authentication_failed", "Authentication failed", status_code=401
            ) from None
        id_token = tokens.get("id_token") if isinstance(tokens, dict) else None
        if not isinstance(id_token, str) or not id_token:
            raise DomainError(
                "authentication_failed", "Authentication failed", status_code=401
            )
        return id_token

    async def validate_id_token(
        self, id_token: str, nonce: str, metadata: Mapping[str, str]
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(metadata["jwks_uri"])
                response.raise_for_status()
                keys = response.json()
            claims = jwt.decode(id_token, JsonWebKey.import_key_set(keys))
            claims.validate(leeway=30)
        except (httpx.HTTPError, JoseError, ValueError, TypeError):
            raise DomainError(
                "authentication_failed", "Authentication failed", status_code=401
            ) from None

        issuer = claims.get("iss")
        audience = claims.get("aud")
        if isinstance(audience, str):
            valid_audience = audience == self.settings.oidc_client_id
        elif isinstance(audience, list):
            valid_audience = self.settings.oidc_client_id in audience and (
                len(audience) == 1 or claims.get("azp") == self.settings.oidc_client_id
            )
        else:
            valid_audience = False
        if (
            claims.header.get("alg") not in ALLOWED_ID_TOKEN_ALGORITHMS
            or not isinstance(issuer, str)
            or issuer.rstrip("/") != str(self.settings.oidc_issuer_url).rstrip("/")
            or not valid_audience
            or not isinstance(claims.get("nonce"), str)
            or not hmac.compare_digest(claims["nonce"], nonce)
            or not isinstance(claims.get("sub"), str)
            or not claims["sub"]
            or not isinstance(claims.get("exp"), (int, float))
        ):
            raise DomainError(
                "authentication_failed", "Authentication failed", status_code=401
            )
        return dict(claims)


def get_oidc_client(request: Request) -> OidcClient:
    """Allow tests to supply a mock provider client without exposing credentials."""
    client = getattr(request.app.state, "oidc_client", None)
    return client if isinstance(client, OidcClient) else OidcClient(get_settings())


def _encode(payload: Mapping[str, Any], secret: str) -> str:
    body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).rstrip(b"=")
    signature = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    return f"{body.decode()}.{encoded_signature}"


def _decode(value: str | None, secret: str) -> dict[str, Any] | None:
    if not value or "." not in value:
        return None
    body, signature = value.split(".", 1)
    expected = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        padded_body = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded_body))
    except (ValueError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _set_cookie(response: Response, key: str, value: str, max_age: int) -> None:
    response.set_cookie(
        key,
        value,
        max_age=max_age,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


def _clear_cookie(response: Response, key: str) -> None:
    response.delete_cookie(
        key, httponly=True, secure=True, samesite="lax", path="/"
    )


def _safe_profile(claims: Mapping[str, Any]) -> tuple[str | None, str | None]:
    """Keep only bounded, display-safe provider profile values."""
    name = claims.get("name") or claims.get("preferred_username")
    email = claims.get("email")
    display_name = (
        name.strip()[:255] if isinstance(name, str) and name.strip() else None
    )
    safe_email = (
        email.strip()[:320] if isinstance(email, str) and email.strip() else None
    )
    return display_name, safe_email


async def _upsert_user(session: AsyncSession, claims: Mapping[str, Any]) -> User:
    issuer = str(claims["iss"]).rstrip("/")
    subject = str(claims["sub"])
    user = await session.scalar(
        select(User).where(User.oidc_issuer == issuer, User.oidc_subject == subject)
    )
    display_name, email = _safe_profile(claims)
    if user is None:
        user = User(
            oidc_issuer=issuer,
            oidc_subject=subject,
            display_name=display_name,
            email=email,
            last_login_at=utc_now(),
        )
        session.add(user)
    else:
        user.display_name = display_name
        user.email = email
        user.last_login_at = utc_now()
    await session.commit()
    await session.refresh(user)
    return user


@auth_router.get("/login")
async def login(
    oidc: Annotated[OidcClient, Depends(get_oidc_client)],
) -> RedirectResponse:
    """Start Authorization Code login, binding the callback to state and nonce."""
    metadata = await oidc.discover()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    state_cookie = _encode(
        {"state": state, "nonce": nonce, "issued_at": int(time.time())},
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
    _set_cookie(response, STATE_COOKIE, state_cookie, STATE_TTL_SECONDS)
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
    """Validate the provider callback and issue a signed application session."""
    state_data = _decode(
        request.cookies.get(STATE_COOKIE),
        oidc.settings.session_secret.get_secret_value(),
    )
    valid_state = (
        state_data is not None
        and isinstance(state_data.get("state"), str)
        and isinstance(state_data.get("nonce"), str)
        and isinstance(state_data.get("issued_at"), int)
        and time.time() - state_data["issued_at"] <= STATE_TTL_SECONDS
        and state is not None
        and hmac.compare_digest(state_data["state"], state)
    )
    if error or not code or not valid_state:
        raise DomainError(
            "authentication_failed", "Authentication failed", status_code=401
        )

    metadata = await oidc.discover()
    token = await oidc.exchange_code(code, metadata)
    claims = await oidc.validate_id_token(token, state_data["nonce"], metadata)
    user = await _upsert_user(session, claims)
    session_value = _encode(
        {"user_id": str(user.id), "issued_at": int(time.time())},
        oidc.settings.session_secret.get_secret_value(),
    )
    response = RedirectResponse(str(oidc.settings.public_url), 302)
    _set_cookie(response, SESSION_COOKIE, session_value, SESSION_TTL_SECONDS)
    _clear_cookie(response, STATE_COOKIE)
    return response


@auth_router.get("/session")
async def current_session(
    request: Request, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    """Return the current local user without exposing OIDC tokens or claims."""
    settings = get_settings()
    payload = _decode(
        request.cookies.get(SESSION_COOKIE), settings.session_secret.get_secret_value()
    )
    if payload is None or not isinstance(payload.get("issued_at"), int):
        return {"authenticated": False}
    if time.time() - payload["issued_at"] > SESSION_TTL_SECONDS:
        return {"authenticated": False}
    try:
        user_id = uuid.UUID(str(payload["user_id"]))
    except (KeyError, ValueError):
        return {"authenticated": False}
    user = await session.get(User, user_id)
    if user is None:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "user": {
            "id": str(user.id),
            "display_name": user.display_name,
            "email": user.email,
        },
    }


@auth_router.post("/logout", status_code=204)
async def logout() -> Response:
    """Invalidate the browser's application session by removing its cookie."""
    response = Response(status_code=204)
    _clear_cookie(response, SESSION_COOKIE)
    _clear_cookie(response, STATE_COOKIE)
    return response
