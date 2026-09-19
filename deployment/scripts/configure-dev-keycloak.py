"""Idempotently configure the generated local Keycloak client via its admin API."""

import json
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


MAPPER = {
    "name": "realm roles in ID token",
    "protocol": "openid-connect",
    "protocolMapper": "oidc-usermodel-realm-role-mapper",
    "config": {
        "claim.name": "realm_access.roles",
        "jsonType.label": "String",
        "multivalued": "true",
        "access.token.claim": "true",
        "id.token.claim": "true",
        "userinfo.token.claim": "true",
    },
}


def request(
    url: str,
    token: str | None = None,
    data: object | None = None,
    method: str | None = None,
) -> object:
    body = None if data is None else json.dumps(data).encode()
    headers = {"Content-Type": "application/json"} if body else {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    # The caller constructs every URL from the loopback-only Keycloak base URL.
    with urlopen(  # noqa: S310 - loopback-only Keycloak admin API
        Request(url, body, headers, method=method),  # noqa: S310
        timeout=15,
    ) as response:
        return json.loads(response.read()) if response.length != 0 else None


def main() -> None:
    dev = Path(sys.argv[1])
    port = (
        (dev / "dev.env")
        .read_text()
        .split("ARA_DEV_KEYCLOAK_PORT=", 1)[1]
        .splitlines()[0]
    )
    admin_password = (dev / "secrets" / "keycloak_admin_password").read_text().strip()
    secret = (dev / "secrets" / "oidc_client_secret").read_text().strip()
    base = f"http://127.0.0.1:{port}"
    token_request = Request(  # noqa: S310 - fixed loopback Keycloak endpoint
        f"{base}/realms/master/protocol/openid-connect/token",
        urlencode(
            {
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": "admin",
                "password": admin_password,
            }
        ).encode(),
        {"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urlopen(token_request, timeout=15) as response:  # noqa: S310
        token = json.loads(response.read())["access_token"]
    clients = request(f"{base}/admin/realms/ara-dev/clients?clientId=ara", token)
    if not isinstance(clients, list):
        raise RuntimeError("could not list ara clients")
    # A complete matching client is retained across normal starts.  This keeps
    # service-account state and generated client identity stable.
    if len(clients) == 1 and isinstance(clients[0].get("id"), str):
        existing = request(
            f"{base}/admin/realms/ara-dev/clients/{clients[0]['id']}", token
        )
        readback = request(
            f"{base}/admin/realms/ara-dev/clients/{clients[0]['id']}/client-secret",
            token,
        )
        mappers = (
            existing.get("protocolMappers", []) if isinstance(existing, dict) else []
        )
        matching_mappers = [
            mapper for mapper in mappers if mapper.get("name") == MAPPER["name"]
        ]
        exact = (
            isinstance(existing, dict)
            and existing.get("enabled") is True
            and existing.get("publicClient") is False
            and existing.get("clientAuthenticatorType") == "client-secret"
            and existing.get("standardFlowEnabled") is True
            and existing.get("serviceAccountsEnabled") is True
            and existing.get("redirectUris") == ["https://localhost/auth/callback"]
            and existing.get("webOrigins") == ["https://localhost"]
            and {"profile", "email", "roles"}.issubset(
                existing.get("defaultClientScopes", [])
            )
            and len(matching_mappers) == 1
            and all(
                matching_mappers[0].get(key) == value for key, value in MAPPER.items()
            )
            and isinstance(readback, dict)
            and readback.get("value") == secret
        )
        if exact:
            probe = Request(  # noqa: S310 - fixed loopback Keycloak endpoint
                f"{base}/realms/ara-dev/protocol/openid-connect/token",
                urlencode(
                    {
                        "grant_type": "client_credentials",
                        "client_id": "ara",
                        "client_secret": secret,
                    }
                ).encode(),
                {"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urlopen(probe, timeout=15) as response:  # noqa: S310
                if response.status == 200:
                    return
    for client in clients:
        if not isinstance(client.get("id"), str):
            raise RuntimeError("client without an id")
        request(
            f"{base}/admin/realms/ara-dev/clients/{client['id']}",
            token,
            method="DELETE",
        )
    client = {
        "clientId": "ara",
        "enabled": True,
        "protocol": "openid-connect",
        "publicClient": False,
        "clientAuthenticatorType": "client-secret",
        "secret": secret,
        "standardFlowEnabled": True,
        "serviceAccountsEnabled": True,
        "redirectUris": ["https://localhost/auth/callback"],
        "webOrigins": ["https://localhost"],
        "defaultClientScopes": ["profile", "email", "roles"],
        "protocolMappers": [MAPPER],
    }
    request(f"{base}/admin/realms/ara-dev/clients", token, client, "POST")
    clients = request(f"{base}/admin/realms/ara-dev/clients?clientId=ara", token)
    if (
        not isinstance(clients, list)
        or len(clients) != 1
        or not isinstance(clients[0].get("id"), str)
    ):
        raise RuntimeError("expected exactly one freshly created ara client")
    client_id = clients[0]["id"]
    readback = request(
        f"{base}/admin/realms/ara-dev/clients/{client_id}/client-secret", token
    )
    if not isinstance(readback, dict) or readback.get("value") != secret:
        raise RuntimeError(
            "Keycloak client secret read-back did not match generated secret"
        )
    probe = Request(  # noqa: S310 - fixed loopback Keycloak endpoint
        f"{base}/realms/ara-dev/protocol/openid-connect/token",
        urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": "ara",
                "client_secret": secret,
            }
        ).encode(),
        {"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urlopen(probe, timeout=15) as response:  # noqa: S310
        if response.status != 200:
            raise RuntimeError("client credentials probe failed")


if __name__ == "__main__":
    main()
