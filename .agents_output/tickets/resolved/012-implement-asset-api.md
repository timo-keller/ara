# 012 - Implement asset API

## Goal

Provide group-scoped asset catalogue and administration endpoints.

## Scope

- Add asset DAO, service, schemas, and REST routes.
- Support asset types and remote-access metadata without secrets.
- Support create, list, read, update, archive, and reactivate operations.
- Add pagination, group, type, text, and archive filters.

## Acceptance Criteria

- Owners can manage all assets.
- Group Admins can manage assets only in their groups.
- Users can read active assets only in their groups.
- Archived assets are excluded by default and cannot be reserved.
- Credential-like fields are not accepted by the API.

## Dependencies

- Ticket 010
