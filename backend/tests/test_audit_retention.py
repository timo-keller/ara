from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ara.domain.models import AuditEvent
from ara.infrastructure.database import Base, create_engine, create_session_factory
from ara.services.audit import AuditRetentionService


@pytest.fixture
async def database_session(tmp_path) -> AsyncIterator[AsyncSession]:  # type: ignore[no-untyped-def]
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'ara.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session:
        yield session
    await engine.dispose()


def audit_event(created_at: datetime) -> AuditEvent:
    return AuditEvent(
        action="test.event",
        target_type="test",
        target_id="test",
        created_at=created_at,
    )


async def test_retention_deletes_only_events_strictly_before_cutoff_in_batches(
    database_session: AsyncSession,
) -> None:
    cutoff = datetime(2025, 1, 1, tzinfo=UTC)
    expired = [
        audit_event(cutoff - timedelta(days=3)),
        audit_event(cutoff - timedelta(days=2)),
        audit_event(cutoff - timedelta(days=1)),
    ]
    retained_at_cutoff = audit_event(cutoff)
    retained_newer = audit_event(cutoff + timedelta(microseconds=1))
    database_session.add_all([*expired, retained_at_cutoff, retained_newer])
    await database_session.commit()

    result = await AuditRetentionService(database_session).delete_expired_events(
        cutoff=cutoff, batch_size=2
    )

    remaining = list(
        await database_session.scalars(
            select(AuditEvent).order_by(AuditEvent.created_at)
        )
    )
    assert result.deleted_count == 3
    assert result.batches == 2
    assert result.cutoff == cutoff
    assert [event.id for event in remaining] == [
        retained_at_cutoff.id,
        retained_newer.id,
    ]

    repeated = await AuditRetentionService(database_session).delete_expired_events(
        cutoff=cutoff, batch_size=2
    )

    assert repeated.deleted_count == 0
    assert repeated.batches == 0


@pytest.mark.parametrize("batch_size", [0, -1])
async def test_retention_rejects_invalid_batch_size(
    database_session: AsyncSession, batch_size: int
) -> None:
    with pytest.raises(ValueError, match="batch_size must be greater than zero"):
        await AuditRetentionService(database_session).delete_expired_events(
            cutoff=datetime.now(UTC), batch_size=batch_size
        )
