# 009 - Implement role resolution

## Goal

Resolve global Owner and group-scoped roles from OIDC claims.

## Scope

- Read the bootstrap Owner subject allowlist from its Docker secret.
- Evaluate enabled role mappings with JMESPath.
- Produce deterministic effective roles for the authenticated user.
- Add reusable Owner, Group Admin, and User authorization checks.

## Acceptance Criteria

- A bootstrap subject receives global Owner access.
- Valid matching expressions grant only their configured group role.
- Invalid expressions cannot be persisted or evaluated silently.
- Backend authorization tests cover cross-group access denial.

## Dependencies

- Ticket 005
- Ticket 008
