"""HTTPX ASGI client for synchronous tests that require a persistent cookie jar."""

import asyncio
from typing import Any

from httpx import ASGITransport, AsyncClient, Response


class ASGIClient:
    """Expose HTTPX's asynchronous ASGI transport to legacy synchronous tests."""

    def __init__(self, app: Any, base_url: str = "http://testserver") -> None:
        self._client = AsyncClient(transport=ASGITransport(app=app), base_url=base_url)

    @property
    def cookies(self) -> Any:
        return self._client.cookies

    def __enter__(self) -> ASGIClient:
        return self

    def __exit__(self, *_args: object) -> None:
        asyncio.run(self._client.aclose())

    def get(self, url: str, **kwargs: Any) -> Response:
        return asyncio.run(self._client.get(url, **kwargs))

    def post(self, url: str, **kwargs: Any) -> Response:
        return asyncio.run(self._client.post(url, **kwargs))

    def patch(self, url: str, **kwargs: Any) -> Response:
        return asyncio.run(self._client.patch(url, **kwargs))
