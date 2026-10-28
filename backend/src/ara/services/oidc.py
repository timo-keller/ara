"""OIDC login orchestration and its local authentication transaction."""

import hmac
import re
import secrets
import time
from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from ara.core.errors import DomainError
from ara.domain.models import ApplicationSession
from ara.infrastructure.oidc import OidcClient
from ara.services.auth import AuthenticationService

STATE_TTL_SECONDS = 600


class OidcLoginService:
    """Apply OIDC login rules without coupling them to HTTP responses."""

    def __init__(self, oidc: OidcClient) -> None:
        self.oidc = oidc

    async def begin(self) -> tuple[dict[str, str], str, str, int, str]:
        """Discover the provider and generate callback-binding values."""
        return (
            await self.oidc.discover(),
            secrets.token_urlsafe(32),
            secrets.token_urlsafe(32),
            int(time.time()),
            secrets.token_urlsafe(32),
        )

    async def complete(
        self,
        session: AsyncSession,
        *,
        code: str | None,
        state: str | None,
        error: str | None,
        state_data: Mapping[str, object] | None,
    ) -> tuple[ApplicationSession, str]:
        """Validate callback state, provider claims, and create local session state."""
        stored_state = state_data.get("state") if state_data is not None else None
        nonce = state_data.get("nonce") if state_data is not None else None
        issued_at = state_data.get("issued_at") if state_data is not None else None
        code_verifier = (
            state_data.get("code_verifier") if state_data is not None else None
        )
        valid_state = (
            isinstance(stored_state, str)
            and isinstance(nonce, str)
            and isinstance(issued_at, int)
            and isinstance(code_verifier, str)
            and re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", code_verifier) is not None
            and time.time() - issued_at <= STATE_TTL_SECONDS
            and state is not None
            and hmac.compare_digest(stored_state, state)
        )
        if error or not code or not valid_state:
            raise DomainError(
                "authentication_failed", "Authentication failed", status_code=401
            )
        metadata = await self.oidc.discover()
        assert isinstance(nonce, str)
        assert isinstance(code_verifier, str)
        claims = await self.oidc.validate_id_token(
            await self.oidc.exchange_code(code, metadata, code_verifier=code_verifier),
            nonce,
            metadata,
        )
        return await AuthenticationService(session).create_oidc_session(claims)
