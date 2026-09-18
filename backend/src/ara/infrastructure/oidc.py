"""Generic OIDC provider adapter; credentials never leave the backend."""

import hmac
from collections.abc import Mapping
from typing import Any

import httpx
from authlib.jose import JoseError, JsonWebKey, jwt

from ara.core.config import Settings
from ara.core.errors import DomainError

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
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{issuer}/.well-known/openid-configuration"
                )
                response.raise_for_status()
                metadata = response.json()
        except httpx.HTTPError, ValueError:
            raise DomainError(
                "authentication_unavailable",
                "The identity provider is unavailable",
                status_code=503,
            ) from None
        required = ("issuer", "authorization_endpoint", "token_endpoint", "jwks_uri")
        if (
            not isinstance(metadata, dict)
            or any(
                not isinstance(metadata.get(key), str) or not metadata[key]
                for key in required
            )
            or metadata["issuer"].rstrip("/") != issuer
        ):
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
        except httpx.HTTPError, ValueError:
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
        except httpx.HTTPError, JoseError, ValueError, TypeError:
            raise DomainError(
                "authentication_failed", "Authentication failed", status_code=401
            ) from None
        audience = claims.get("aud")
        valid_audience = (
            audience == self.settings.oidc_client_id
            if isinstance(audience, str)
            else isinstance(audience, list)
            and self.settings.oidc_client_id in audience
            and (
                len(audience) == 1 or claims.get("azp") == self.settings.oidc_client_id
            )
        )
        if (
            claims.header.get("alg") not in ALLOWED_ID_TOKEN_ALGORITHMS
            or not isinstance(claims.get("iss"), str)
            or claims["iss"].rstrip("/")
            != str(self.settings.oidc_issuer_url).rstrip("/")
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
