from datetime import UTC, datetime, timedelta

import pytest
from joserfc import jwk, jwt

from ara.core.config import Settings
from ara.core.errors import DomainError
from ara.infrastructure import oidc
from ara.infrastructure.oidc import OidcClient


def settings() -> Settings:
    return Settings.from_environment(
        {
            "ARA_PUBLIC_URL": "https://localhost",
            "ARA_OIDC_ISSUER_URL": "http://localhost:8080/realms/ara-dev",
            "ARA_OIDC_BACKCHANNEL_URL": "http://host.docker.internal:8080/realms/ara-dev",
            "ARA_OIDC_CLIENT_ID": "ara",
            "ARA_OIDC_CLIENT_SECRET": "secret",
            "ARA_SESSION_SECRET": "secret",
            "ARA_OWNER_SUBJECTS": "subject",
        }
    )


def test_backchannel_rewrites_only_public_issuer_relative_endpoints() -> None:
    client = OidcClient(settings())
    assert (
        client._backchannel_endpoint(  # noqa: SLF001
            "http://localhost:8080/realms/ara-dev/protocol/openid-connect/certs"
        )
        == "http://host.docker.internal:8080/realms/ara-dev/protocol/openid-connect/certs"
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://169.254.169.254/latest/meta-data",
        "http://localhost:8080/admin",
        "http://localhost:8080/realms/ara-dev/protocol/openid-connect/certs?x=1",
    ],
)
def test_backchannel_rejects_untrusted_metadata_endpoints(endpoint: str) -> None:
    with pytest.raises(DomainError, match="identity provider is unavailable"):
        OidcClient(settings())._backchannel_endpoint(endpoint)  # noqa: SLF001


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://169.254.169.254/latest/meta-data",
        "http://localhost:8080/admin/realms/ara-dev/logout",
        "http://host.docker.internal:8080/realms/ara-dev/protocol/openid-connect/logout",
        "http://localhost:8080/realms/ara-dev/protocol/openid-connect/logout#fragment",
    ],
)
def test_public_browser_endpoint_rejects_non_public_or_non_issuer_relative_urls(
    endpoint: str,
) -> None:
    with pytest.raises(DomainError, match="identity provider is unavailable"):
        OidcClient(settings())._public_browser_endpoint(endpoint)  # noqa: SLF001


def test_public_browser_endpoint_is_not_rewritten_to_the_backchannel() -> None:
    endpoint = "http://localhost:8080/realms/ara-dev/protocol/openid-connect/logout"
    assert OidcClient(settings())._public_browser_endpoint(endpoint) == endpoint  # noqa: SLF001


class _JwksResponse:
    def __init__(self, keys: dict[str, object]) -> None:
        self.keys = keys

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, object]:
        return self.keys


class _JwksClient:
    def __init__(self, keys: dict[str, object], **_kwargs: object) -> None:
        self.keys = keys

    async def __aenter__(self) -> _JwksClient:
        return self

    async def __aexit__(self, *_args: object) -> None:
        pass

    async def get(self, _url: str) -> _JwksResponse:
        return _JwksResponse(self.keys)


@pytest.mark.asyncio
async def test_validate_id_token_accepts_a_real_signed_token(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    key = jwk.RSAKey.generate_key(auto_kid=True)
    now = datetime.now(UTC)
    token = jwt.encode(
        {"alg": "RS256", "kid": key.kid},
        {
            "iss": str(settings().oidc_issuer_url),
            "sub": "subject",
            "aud": "ara",
            "nonce": "nonce",
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        },
        key,
    )
    monkeypatch.setattr(
        oidc.httpx,
        "AsyncClient",
        lambda **kwargs: _JwksClient({"keys": [key.as_dict()]}, **kwargs),
    )

    claims = await OidcClient(settings()).validate_id_token(
        token, "nonce", {"jwks_uri": "https://id.example.test/keys"}
    )

    assert claims["sub"] == "subject"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("claims", "header", "nonce", "wrong_key"),
    [
        ({"iss": "https://wrong.example", "aud": "ara"}, {}, "nonce", False),
        (
            {"iss": "http://localhost:8080/realms/ara-dev", "aud": "wrong"},
            {},
            "nonce",
            False,
        ),
        (
            {"iss": "http://localhost:8080/realms/ara-dev", "aud": ["ara", "other"]},
            {},
            "nonce",
            False,
        ),
        (
            {"iss": "http://localhost:8080/realms/ara-dev", "aud": "ara"},
            {},
            "wrong",
            False,
        ),
        (
            {"iss": "http://localhost:8080/realms/ara-dev", "aud": "ara"},
            {"alg": "HS256"},
            "nonce",
            False,
        ),
        (
            {"iss": "http://localhost:8080/realms/ara-dev", "aud": "ara", "exp": 0},
            {},
            "nonce",
            False,
        ),
        (
            {"iss": "http://localhost:8080/realms/ara-dev", "aud": "ara"},
            {},
            "nonce",
            True,
        ),
    ],
)
async def test_validate_id_token_rejects_invalid_signed_claims(
    monkeypatch,
    claims,
    header,
    nonce: str,
    wrong_key: bool,  # type: ignore[no-untyped-def]
) -> None:
    signing_key = (
        jwk.OctKey.import_key("test-secret-with-sufficient-length")
        if header.get("alg") == "HS256"
        else jwk.RSAKey.generate_key(auto_kid=True)
    )
    jwks_key = jwk.RSAKey.generate_key(auto_kid=True) if wrong_key else signing_key
    full_claims = {
        "sub": "subject",
        "nonce": "nonce",
        "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp()),
        **claims,
    }
    token = jwt.encode(
        {
            "alg": "RS256",
            **({"kid": signing_key.kid} if signing_key.kid else {}),
            **header,
        },
        full_claims,
        signing_key,
        algorithms=[header.get("alg", "RS256")],
    )
    monkeypatch.setattr(
        oidc.httpx,
        "AsyncClient",
        lambda **kwargs: _JwksClient({"keys": [jwks_key.as_dict()]}, **kwargs),
    )

    with pytest.raises(DomainError, match="Authentication failed"):
        await OidcClient(settings()).validate_id_token(
            token, nonce, {"jwks_uri": "https://id.example.test/keys"}
        )
