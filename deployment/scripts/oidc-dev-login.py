"""Minimal real authorization-code browser simulation for ``run-dev.sh test``."""

import http.cookiejar
import json
import ssl
import sys
import uuid
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener


class LoginForm(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.action = ""
        self.values: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "form" and attributes.get("id") == "kc-form-login":
            self.action = attributes.get("action", "")
        if tag == "input" and attributes.get("type") == "hidden":
            name, value = attributes.get("name"), attributes.get("value")
            if name and value is not None:
                self.values[name] = value


class LocalhostCookiePolicy(http.cookiejar.DefaultCookiePolicy):
    """Only relax Secure's localhost transport rule; keep normal path/domain checks."""

    def return_ok(self, cookie: http.cookiejar.Cookie, request: Request) -> bool:
        if super().return_ok(cookie, request):
            return True
        return (
            cookie.secure
            and request.host.split(":", 1)[0] == "localhost"
            # CookieJar canonicalizes a host-only localhost cookie this way.
            and cookie.domain in ("", "localhost", "localhost.local")
            and request.full_url.startswith("http://localhost:")
            and request.selector.startswith(cookie.path)
        )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def api_request(
    opener: object,
    path: str,
    csrf: str,
    payload: dict[str, str] | None = None,
) -> object:
    data = None if payload is None else json.dumps(payload).encode()
    request = Request(  # noqa: S310 - fixed localhost API endpoint
        f"https://localhost/api{path}",
        data=data,
        method="GET" if data is None else "POST",
        headers={"Content-Type": "application/json", "X-CSRF-Token": csrf},
    )
    return opener.open(request, timeout=20)  # type: ignore[union-attr]


def main() -> None:
    username, password, email, expected_role = sys.argv[1:]
    cookies = http.cookiejar.CookieJar(policy=LocalhostCookiePolicy())
    opener = build_opener(
        HTTPCookieProcessor(cookies),
        # The local launcher creates this CA certificate for localhost.
        __import__("urllib.request", fromlist=["HTTPSHandler"]).HTTPSHandler(
            context=ssl.create_default_context(cafile=".dev/certificates/tls.crt")
        ),
    )
    page = opener.open("https://localhost/auth/login", timeout=20)
    form = LoginForm()
    form.feed(page.read().decode())
    if not form.action:
        raise RuntimeError("Keycloak login form was not returned")
    form.values.update({"username": username, "password": password})
    response = opener.open(
        Request(  # noqa: S310 - Keycloak supplies this form action on localhost
            urljoin(page.geturl(), form.action),
            data=urlencode(form.values).encode(),
            method="POST",
        ),
        timeout=20,
    )
    response.read()
    session = json.loads(
        opener.open("https://localhost/auth/session", timeout=20).read()
    )
    if session["authenticated"] is not True:
        # Safe failure context for CI/local diagnosis: never print cookie values.
        title = ""
        try:
            import re

            title = re.search(
                r"<title>(.*?)</title>", response.read().decode(), re.S
            ).group(1)  # type: ignore[union-attr]
        except (AttributeError, UnicodeDecodeError):
            pass
        print(
            f"OIDC login failed: final_url={response.geturl()} status={response.status} "
            f"title={title!r} cookies={[cookie.name for cookie in cookies]}",
            file=sys.stderr,
        )
    require(session["authenticated"] is True, "session was not authenticated")
    require(session["user"]["email"] == email, "session email did not match")
    require(
        session["roles"]["is_owner"] is (expected_role == "owner"),
        "session Owner role did not match",
    )
    roles = session["roles"]["group_roles"].values()
    if expected_role == "group_admin":
        require("group_admin" in roles, "group-admin role was not resolved")
    elif expected_role == "user":
        require("user" in roles, "user role was not resolved")
    csrf = next(cookie.value for cookie in cookies if cookie.name == "ara_csrf")
    if expected_role == "owner":
        require(
            api_request(opener, "/role-mappings", csrf).status == 200,
            "Owner-only role mappings API was not available",
        )
    else:
        groups = json.loads(api_request(opener, "/groups", csrf).read())
        require(
            groups["total"] == 1 and groups["items"][0]["name"] == "ARA Development",
            "expected exactly one resolved ARA Development group",
        )
        asset = {
            "group_id": groups["items"][0]["id"],
            "name": f"OIDC development check {uuid.uuid4()}",
            "asset_type": "development-check",
        }
        if expected_role == "group_admin":
            created = api_request(opener, "/assets", csrf, asset)
            require(created.status == 201, "group-admin could not create an asset")
            asset_id = json.loads(created.read())["id"]
            require(
                api_request(opener, f"/assets/{asset_id}/archive", csrf, {}).status
                == 200,
                "group-admin could not archive its test asset",
            )
        else:
            from urllib.error import HTTPError

            try:
                api_request(opener, "/assets", csrf, asset)
            except HTTPError as error:
                require(
                    error.code == 403, "user asset creation was not denied with 403"
                )
            else:
                raise RuntimeError("user unexpectedly created an asset")
    logout = opener.open(
        Request(
            "https://localhost/auth/logout",
            data=b"",
            method="POST",
            headers={"X-CSRF-Token": csrf},
        ),
        timeout=20,
    )
    require(logout.status == 204, "logout did not return 204")
    require(
        json.loads(opener.open("https://localhost/auth/session", timeout=20).read())[
            "authenticated"
        ]
        is False,
        "session remained authenticated after logout",
    )


if __name__ == "__main__":
    main()
