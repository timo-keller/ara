import pytest

from ara.core.config import Settings
from ara.core.errors import DomainError
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
