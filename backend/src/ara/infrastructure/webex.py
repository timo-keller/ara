"""Small outbound-only Webex client with sanitized failure categories."""

import asyncio
import base64
import binascii
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from ara.core.errors import DomainError


def space_uuid(room_id: str) -> uuid.UUID | None:
    """Read the UUID from Webex's opaque, possibly regional, room URN."""
    try:
        urn = base64.b64decode(
            room_id + "=" * (-len(room_id) % 4), validate=True
        ).decode()
        prefix, identifier = urn.rsplit("/", 1)
        # Webex wraps both legacy regions and regional TEAM URNs in the
        # ciscospark scheme. The returned ID itself remains opaque for delivery.
        if not prefix.startswith("ciscospark://") or not prefix.endswith("/ROOM"):
            return None
        return uuid.UUID(identifier)
    except ValueError, UnicodeError, binascii.Error:
        return None


def resolution_error(code: str) -> DomainError:
    messages = {
        "missing_bot_token": "Configure the ARA Notification Bot token on the server.",
        "invalid_bot_token": (
            "The ARA Notification Bot token is invalid. Ask an Owner to update it."
        ),
        "space_not_visible": (
            "Space is not visible to the bot. "
            "Add ARA Notification Bot to the space and try again."
        ),
        "direct_space": "Choose a group Webex space, not a private conversation.",
        "rate_limited": "Webex is rate limiting requests. Try again later.",
        "webex_unavailable": "Webex is unavailable. Try again later.",
        "request_rejected": (
            "Webex rejected the lookup. Check the bot configuration and try again."
        ),
    }
    return DomainError(
        code,
        messages[code],
        status_code=503
        if code in ("missing_bot_token", "rate_limited", "webex_unavailable")
        else 422,
    )


@dataclass(frozen=True)
class SendResult:
    message_id: str | None = None
    error_code: str | None = None
    retry_after: float | None = None


class WebexClient:
    def __init__(
        self, token: str, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.http = httpx.AsyncClient(
            base_url="https://webexapis.com/v1/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
            transport=transport,
        )

    async def close(self) -> None:
        await self.http.aclose()

    async def resolve_space(self, identifier: uuid.UUID) -> str:
        """Bound lookups to 20 pages and 30 seconds, with no untrusted URLs."""
        try:
            async with asyncio.timeout(30):
                return await self._resolve_space(identifier)
        except httpx.RequestError, TimeoutError:
            raise resolution_error("webex_unavailable") from None

    async def _resolve_space(self, identifier: uuid.UUID) -> str:
        url = httpx.URL("https://webexapis.com/v1/rooms?max=100")
        seen: set[str] = set()
        for _ in range(20):
            if (
                url.scheme != "https"
                or url.host != "webexapis.com"
                or url.port not in (None, 443)
                or url.path != "/v1/rooms"
                or url.userinfo
                or url.fragment
                or str(url) in seen
            ):
                raise resolution_error("webex_unavailable")
            seen.add(str(url))
            response = await self.http.get(url)
            if response.status_code != 200:
                code = {
                    401: "invalid_bot_token",
                    403: "request_rejected",
                    429: "rate_limited",
                }.get(
                    response.status_code,
                    "webex_unavailable"
                    if response.status_code >= 500 or response.status_code == 408
                    else "request_rejected",
                )
                raise resolution_error(code)
            try:
                items = response.json()["items"]
                if not isinstance(items, list):
                    raise ValueError
                for room in items:
                    room_id = room.get("id")
                    if isinstance(room_id, str) and space_uuid(room_id) == identifier:
                        if room.get("type") != "group":
                            raise resolution_error("direct_space")
                        if len(room_id) > 255:
                            raise ValueError
                        return room_id
            except ValueError, KeyError, AttributeError, TypeError:
                raise resolution_error("webex_unavailable") from None
            next_url = response.links.get("next", {}).get("url")
            if not next_url:
                raise resolution_error("space_not_visible")
            try:
                url = response.url.join(next_url)
            except httpx.InvalidURL, ValueError:
                raise resolution_error("webex_unavailable") from None
        raise resolution_error("webex_unavailable")

    async def send(
        self,
        destination_type: str,
        destination: str,
        text: str,
        *,
        markdown: str | None = None,
    ) -> SendResult:
        field = "roomId" if destination_type == "room" else "toPersonEmail"
        payload = {field: destination, "text": text}
        if markdown is not None:
            payload["markdown"] = markdown
        try:
            response = await self.http.post("messages", json=payload)
        except httpx.RequestError:
            return SendResult(error_code="network_error", retry_after=30)
        if response.status_code in (200, 201):
            try:
                message_id = response.json().get("id")
            except ValueError, AttributeError:
                message_id = None
            # A successful POST must not be retried just because its body is odd.
            return SendResult(
                message_id=message_id if isinstance(message_id, str) else None
            )
        if response.status_code == 429:
            retry_after = 60.0
            value = response.headers.get("Retry-After", "60")
            try:
                retry_after = float(value)
            except ValueError:
                try:
                    retry_after = (
                        parsedate_to_datetime(value) - datetime.now(UTC)
                    ).total_seconds()
                except ValueError, TypeError, OverflowError:
                    pass
            return SendResult(
                error_code="rate_limited", retry_after=max(1, min(retry_after, 86400))
            )
        if response.status_code >= 500 or response.status_code == 408:
            return SendResult(error_code="webex_unavailable", retry_after=30)
        codes = {
            401: "invalid_bot_token",
            403: "permission_denied",
            404: "recipient_not_found",
            400: "invalid_destination",
        }
        return SendResult(
            error_code=codes.get(response.status_code, "request_rejected")
        )
