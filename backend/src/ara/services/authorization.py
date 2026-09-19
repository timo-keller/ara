"""Role resolution and service-layer authorization checks."""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import jmespath
from jmespath.exceptions import JMESPathError
from sqlalchemy.ext.asyncio import AsyncSession

from ara.core.errors import DomainError
from ara.daos.role_mappings import RoleMappingDAO
from ara.domain.models import ApplicationSession, GroupRole, User


def validate_role_expression(expression: str) -> jmespath.parser.ParsedResult:
    """Compile an expression or return a safe validation error to callers."""
    if not expression.strip():
        raise DomainError(
            "invalid_role_mapping_expression",
            "Role mapping expression is invalid",
        )
    try:
        return jmespath.compile(expression)
    except JMESPathError as error:
        raise DomainError(
            "invalid_role_mapping_expression",
            "Role mapping expression is invalid",
        ) from error


def parse_owner_subjects(value: str) -> frozenset[str]:
    """Parse the newline/comma-separated bootstrap-owner secret."""
    subjects = value.replace(",", "\n").splitlines()
    return frozenset(subject.strip() for subject in subjects if subject.strip())


@dataclass(frozen=True)
class EffectiveRoles:
    """The resolved global and group-scoped access for one authenticated user."""

    is_owner: bool
    group_roles: Mapping[uuid.UUID, GroupRole]
    actor_id: uuid.UUID | None = None

    def is_group_admin(self, group_id: uuid.UUID) -> bool:
        return self.is_owner or self.group_roles.get(group_id) is GroupRole.GROUP_ADMIN

    def is_group_user(self, group_id: uuid.UUID) -> bool:
        return self.is_owner or group_id in self.group_roles


class RoleResolutionService:
    """Resolve OIDC claims into stable ARA roles without exposing the claims."""

    def __init__(
        self,
        session: AsyncSession,
        owner_subjects: str,
        owner_claim_expression: str | None = None,
    ) -> None:
        self.mappings = RoleMappingDAO(session)
        self.owner_subjects = parse_owner_subjects(owner_subjects)
        self.owner_claim_expression = (
            validate_role_expression(owner_claim_expression)
            if owner_claim_expression is not None
            else None
        )

    async def resolve(self, user: User, claims: Mapping[str, Any]) -> EffectiveRoles:
        """Evaluate all enabled mappings in priority/identifier order.

        Group Admin wins over User when several mappings match the same group.
        This makes the result independent of incidental database row order.
        """
        is_owner = user.oidc_subject in self.owner_subjects
        if self.owner_claim_expression is not None:
            try:
                is_owner = (
                    is_owner or self.owner_claim_expression.search(claims) is True
                )
            except JMESPathError:
                pass
        group_roles: dict[uuid.UUID, GroupRole] = {}
        for mapping in await self.mappings.list_enabled():
            expression = validate_role_expression(mapping.expression)
            try:
                matches = expression.search(claims)
            except JMESPathError:
                # A valid expression can receive an absent or differently typed
                # optional claim (for example, ``contains(groups, ...)`` when
                # this provider did not emit ``groups``). That is a non-match,
                # not an invalid persisted expression.
                matches = False
            if matches is True:
                current = group_roles.get(mapping.group_id)
                if current is not GroupRole.GROUP_ADMIN:
                    group_roles[mapping.group_id] = mapping.role
        return EffectiveRoles(
            is_owner=is_owner, group_roles=group_roles, actor_id=user.id
        )

    async def resolve_session(
        self, application_session: ApplicationSession
    ) -> EffectiveRoles:
        """Resolve roles from claims retained only in server-side session state."""
        return await self.resolve(
            application_session.user, application_session.oidc_claims
        )


class AuthorizationService:
    """Reusable backend checks for services that act on global or group data."""

    @staticmethod
    def require_owner(roles: EffectiveRoles) -> None:
        if not roles.is_owner:
            _forbidden()

    @staticmethod
    def require_group_admin(roles: EffectiveRoles, group_id: uuid.UUID) -> None:
        if not roles.is_group_admin(group_id):
            _forbidden()

    @staticmethod
    def require_group_user(roles: EffectiveRoles, group_id: uuid.UUID) -> None:
        if not roles.is_group_user(group_id):
            _forbidden()


def _forbidden() -> None:
    raise DomainError("authorization_denied", "Authorization denied", status_code=403)
