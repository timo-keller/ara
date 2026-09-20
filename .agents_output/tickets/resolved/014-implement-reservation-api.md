# 014 - Implement reservation API

## Goal

Allow authorized users to create and inspect reservations.

## Scope

- Add reservation DAO, service, schemas, and REST routes.
- Support immediate and future starts and optional ends.
- Add own-reservation and asset-schedule queries.
- Enforce group access, active asset state, and conflict rules.

## Acceptance Criteria

- Authorized group members can reserve an available active asset.
- Reservations require no approval.
- Unauthorized and cross-group requests are rejected.
- API timestamps are unambiguous UTC values.
- Lists provide pagination and stable ordering.

## Dependencies

- Ticket 013
