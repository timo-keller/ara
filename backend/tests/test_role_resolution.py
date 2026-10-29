import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ara.core.errors import DomainError
from ara.domain.models import Group, GroupRole, RoleMapping, User
from ara.infrastructure.database import Base, create_engine, create_session_factory
from ara.services.authorization import (
    AuthorizationService,
    EffectiveRoles,
    RoleResolutionService,
    parse_owner_subjects,
    validate_role_expression,
)
from ara.services.role_mappings import RoleMappingService


@pytest.fixture
async def database_session(tmp_path: Path) -> AsyncIterator[AsyncSession]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'ara.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session:
        yield session
    await engine.dispose()


async def test_bootstrap_owner_and_enabled_mappings_resolve_deterministically(
    database_session: AsyncSession,
) -> None:
    user = User(oidc_issuer="https://issuer.example", oidc_subject="member")
    first, second = Group(name="First"), Group(name="Second")
    database_session.add_all([user, first, second])
    await database_session.flush()
    database_session.add_all(
        [
            RoleMapping(
                group_id=first.id,
                expression="contains(groups, 'first-users')",
                role=GroupRole.USER,
                priority=10,
            ),
            RoleMapping(
                group_id=first.id,
                expression="contains(groups, 'first-admins')",
                role=GroupRole.GROUP_ADMIN,
                priority=0,
            ),
            RoleMapping(
                group_id=second.id,
                expression="contains(groups, 'second-users')",
                role=GroupRole.USER,
                enabled=False,
            ),
        ]
    )
    await database_session.commit()

    resolver = RoleResolutionService(database_session, "other,\n bootstrap\n")
    roles = await resolver.resolve(
        user, {"groups": ["first-users", "first-admins", "second-users"]}
    )

    assert roles.is_owner is False
    assert roles.group_roles == {first.id: GroupRole.GROUP_ADMIN}
    assert roles.is_group_user(first.id) is True
    assert roles.is_group_user(second.id) is False

    bootstrap_user = User(
        oidc_issuer="https://issuer.example", oidc_subject="bootstrap"
    )
    assert (await resolver.resolve(bootstrap_user, {})).is_owner is True


async def test_group_authorization_denies_cross_group_access(
    database_session: AsyncSession,
) -> None:
    first, second = uuid.uuid4(), uuid.uuid4()
    roles = EffectiveRoles(is_owner=False, group_roles={first: GroupRole.GROUP_ADMIN})

    AuthorizationService.require_group_admin(roles, first)
    AuthorizationService.require_group_user(roles, first)
    with pytest.raises(DomainError, match="Authorization denied") as error:
        AuthorizationService.require_group_admin(roles, second)
    assert error.value.status_code == 403
    with pytest.raises(DomainError, match="Authorization denied"):
        AuthorizationService.require_group_user(roles, second)
    with pytest.raises(DomainError, match="Authorization denied"):
        AuthorizationService.require_owner(roles)


async def test_invalid_role_expression_is_rejected_before_persistence(
    database_session: AsyncSession,
) -> None:
    with pytest.raises(DomainError, match="Role mapping expression is invalid"):
        validate_role_expression("contains(groups,")

    group = Group(name="Group")
    database_session.add(group)
    await database_session.commit()
    with pytest.raises(DomainError, match="Role mapping expression is invalid"):
        await RoleMappingService(database_session).create(
            EffectiveRoles(is_owner=True, group_roles={}),
            group_id=group.id,
            expression="contains(groups,",
            role=GroupRole.USER,
        )
    assert not database_session.new


def test_owner_allowlist_accepts_newlines_and_commas() -> None:
    assert parse_owner_subjects(" one, two\n three \n") == {"one", "two", "three"}


async def test_owner_claim_expression_grants_owner(
    database_session: AsyncSession,
) -> None:
    user = User(oidc_issuer="https://issuer.example", oidc_subject="not-allowlisted")
    database_session.add(user)
    await database_session.commit()
    roles = await RoleResolutionService(
        database_session, "other", "contains(realm_access.roles, 'ara-owner')"
    ).resolve(user, {"realm_access": {"roles": ["ara-owner"]}})
    assert roles.is_owner is True


@pytest.mark.parametrize(
    ("claims", "expected_owner"),
    [
        ({"roles": ["ara-owner"]}, True),
        ({"roles": ["ara-user"]}, False),
        ({"roles": []}, False),
        ({}, False),
        ({"roles": None}, False),
    ],
)
async def test_top_level_owner_role_claim(
    database_session: AsyncSession,
    claims: dict[str, object],
    expected_owner: bool,
) -> None:
    user = User(oidc_issuer="https://issuer.example", oidc_subject="not-allowlisted")
    database_session.add(user)
    await database_session.commit()
    roles = await RoleResolutionService(
        database_session, "no-local-bootstrap-owner", "contains(roles, 'ara-owner')"
    ).resolve(user, claims)
    assert roles.is_owner is expected_owner
