"""HTTPX ASGI client for synchronous tests that require a persistent cookie jar."""

import asyncio
from typing import Any, cast

from httpx import ASGITransport, AsyncClient, Cookies, Response
from starlette.types import ASGIApp


class ASGIClient:
    """Expose HTTPX's asynchronous ASGI transport to legacy synchronous tests."""

    def __init__(self, app: ASGIApp, base_url: str = "http://testserver") -> None:
        self._client = AsyncClient(transport=ASGITransport(app=app), base_url=base_url)

    @property
    def cookies(self) -> Cookies:
        return self._client.cookies

    def __enter__(self) -> ASGIClient:
        return self

    def __exit__(self, *_args: object) -> None:
        asyncio.run(self._client.aclose())

    def get(self, url: str, **kwargs: object) -> Response:
        # HTTPX uses method-specific keyword unions that cannot model this
        # deliberately transparent forwarding test adapter.
        return asyncio.run(self._client.get(url, **cast(Any, kwargs)))

    def post(self, url: str, **kwargs: object) -> Response:
        # See ``get``: callers retain HTTPX's runtime keyword flexibility.
        return asyncio.run(self._client.post(url, **cast(Any, kwargs)))

    def patch(self, url: str, **kwargs: object) -> Response:
        # See ``get``: callers retain HTTPX's runtime keyword flexibility.
        return asyncio.run(self._client.patch(url, **cast(Any, kwargs)))
