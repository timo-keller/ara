"""Database connectivity probe without transaction control."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class DatabaseHealthDAO:
    """Execute the minimal database connectivity query."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def ping(self) -> None:
        """Verify that a connection can execute a trivial read query."""
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
