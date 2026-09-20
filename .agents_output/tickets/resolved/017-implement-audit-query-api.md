# 017 - Implement audit query API

## Goal

Expose authorized, filterable access to audit history.

## Scope

- Add paginated audit query routes.
- Filter by group, actor, action, target, and time range.
- Enforce global Owner and group-scoped Group Admin visibility.
- Provide stable reverse-chronological ordering.

## Acceptance Criteria

- Owners can query all audit events.
- Group Admins can query only events for their groups.
- Users cannot access the audit API.
- Cross-group records cannot leak through filters or direct identifiers.

## Dependencies

- Ticket 016
