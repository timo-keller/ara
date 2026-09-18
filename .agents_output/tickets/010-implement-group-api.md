# 010 - Implement group API

## Goal

Allow Owners to manage ARA groups without deleting historical records.

## Scope

- Add group DAO, service, schemas, and REST routes.
- Support create, list, read, update, archive, and reactivate operations.
- Reject archival while unresolved reservations exist.
- Add pagination and archived-state filtering.

## Acceptance Criteria

- Only Owners can mutate groups.
- Group Admins and Users can read only their effective groups.
- Archive operations preserve the group and its relationships.
- Mutations are ready to participate in atomic audit recording.

## Dependencies

- Ticket 009
