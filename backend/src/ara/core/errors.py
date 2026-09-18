"""Safe errors shared by API routers and services."""

from typing import Any


class DomainError(Exception):
    """An expected business-rule failure that can safely be returned to clients."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
