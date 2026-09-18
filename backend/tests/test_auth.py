import asyncio
from collections.abc import AsyncIterator, Iterator, Mapping
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import ara.auth as auth
from ara.config import Settings
from ara.database import Base, create_engine, create_session_factory
from ara.main import create_app


def settings() -> Settings:
    return Settings.from_environment(
        {
            "ARA_PUBLIC_URL": "https://ara.example.test",
            "ARA_OIDC_ISSUER_URL": "https://id.example.test/realm",
            "ARA_OIDC_CLIENT_ID": "ara",
            "ARA_OIDC_CLIENT_SECRET": "provider-client-secret",
            "ARA_SESSION_SECRET": "application-session-secret",
            "ARA_OWNER_SUBJECTS": "owner",
        }
    )


class MockProvider(auth.OidcClient):
    """A mocked provider which records only non-secret protocol inputs."""

    def __init__(self, configured_settings: Settings) -> None:
        super().__init__(configured_settings)
        self.nonce: str | None = None

    async def discover(self) -> dict[str, str]:
        return {
            "issuer": "https://id.example.test/realm",
            "authorization_endpoint": "https://id.example.test/authorize",
            "token_endpoint": "https://id.example.test/token",
            "jwks_uri": "https://id.example.test/keys",
        }

    async def exchange_code(self, code: str, metadata: Mapping[str, str]) -> str:
        assert code == "authorization-code"
        assert metadata["token_endpoint"] == "https://id.example.test/token"
        return "provider-id-token"

    async def validate_id_token(
        self, id_token: str, nonce: str, metadata: Mapping[str, str]
    ) -> dict[str, Any]:
        assert id_token == "provider-id-token"
        assert metadata["jwks_uri"] == "https://id.example.test/keys"
        self.nonce = nonce
        return {
            "iss": "https://id.example.test/realm",
            "sub": "stable-subject",
            "name": "Ada Lovelace",
            "email": "ada@example.test",
        }


@pytest.fixture
def authenticated_client(  # type: ignore[no-untyped-def]
    tmp_path, monkeypatch
) -> Iterator[tuple[TestClient, MockProvider]]:
    configured_settings = settings()
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'ara.db'}")
    session_factory = create_session_factory(engine)

    async def initialise() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(initialise())
    app = create_app()
    provider = MockProvider(configured_settings)
    app.state.oidc_client = provider
    app.dependency_overrides[auth.get_session] = session_dependency(session_factory)
    monkeypatch.setattr(auth, "get_settings", lambda: configured_settings)
    with TestClient(app, base_url="https://ara.example.test") as client:
        yield client, provider
    asyncio.run(engine.dispose())


def session_dependency(
    factory: async_sessionmaker[AsyncSession],
) -> Any:
    async def get_test_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    return get_test_session


def test_oidc_login_callback_session_and_logout(
    authenticated_client: tuple[TestClient, MockProvider],
) -> None:
    client, provider = authenticated_client

    login = client.get("/auth/login", follow_redirects=False)

    assert login.status_code == 302
    assert "HttpOnly" in login.headers["set-cookie"]
    assert "Secure" in login.headers["set-cookie"]
    assert "SameSite=lax" in login.headers["set-cookie"]
    query = parse_qs(urlparse(login.headers["location"]).query)
    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["ara"]
    assert query["redirect_uri"] == ["https://ara.example.test/auth/callback"]

    callback = client.get(
        "/auth/callback",
        params={"code": "authorization-code", "state": query["state"][0]},
        follow_redirects=False,
    )

    assert callback.status_code == 302
    assert provider.nonce is not None
    assert "ara_session=" in callback.headers["set-cookie"]
    assert "provider-id-token" not in callback.text
    assert "provider-client-secret" not in callback.text
    current_session = client.get("/auth/session").json()
    assert current_session == {
        "authenticated": True,
        "user": {
            "id": current_session["user"]["id"],
            "display_name": "Ada Lovelace",
            "email": "ada@example.test",
        },
    }

    logout = client.post("/auth/logout")
    assert logout.status_code == 204
    assert "ara_session=\"\"" in logout.headers["set-cookie"]
    assert client.get("/auth/session").json() == {"authenticated": False}


def test_callback_failure_is_safe_and_does_not_leak_provider_values(
    authenticated_client: tuple[TestClient, MockProvider], monkeypatch
) -> None:
    client, provider = authenticated_client
    login = client.get("/auth/login", follow_redirects=False)
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]

    class UnavailableProviderHttpClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> UnavailableProviderHttpClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def post(self, *args: object, **kwargs: object) -> None:
            raise auth.httpx.ConnectError(
                "provider-id-token and provider-client-secret"
            )

    failing_client = auth.OidcClient(provider.settings)
    monkeypatch.setattr(auth.httpx, "AsyncClient", UnavailableProviderHttpClient)

    async def failed_exchange(code: str, metadata: Mapping[str, str]) -> str:
        return await failing_client.exchange_code(code, metadata)

    monkeypatch.setattr(provider, "exchange_code", failed_exchange)
    response = client.get(
        "/auth/callback", params={"code": "authorization-code", "state": state}
    )

    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "authentication_failed",
        "message": "Authentication failed",
    }
    assert "provider-id-token" not in response.text
    assert "provider-client-secret" not in response.text
