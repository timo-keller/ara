"""Operational health rules."""

from ara.daos.health import DatabaseHealthDAO
from ara.infrastructure.database import get_engine


class HealthService:
    """Turn database probe outcomes into the readiness business result."""

    def __init__(self, database: DatabaseHealthDAO) -> None:
        self.database = database

    async def is_ready(self) -> bool:
        """Return false rather than exposing persistence errors to HTTP clients."""
        try:
            await self.database.ping()
        except Exception:
            return False
        return True


def get_health_service() -> HealthService:
    """Build the service used by the request-scoped router dependency."""
    return HealthService(DatabaseHealthDAO(get_engine()))
