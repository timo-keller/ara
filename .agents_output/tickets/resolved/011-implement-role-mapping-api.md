# 011 - Implement role mapping API

## Goal

Allow Owners to manage and test OIDC claim-to-group mappings.

## Scope

- Add role-mapping DAO, service, schemas, and REST routes.
- Support create, list, update, disable, and archive operations.
- Add an endpoint that tests an expression against the Owner's safe claims.
- Validate JMESPath syntax and boolean match behavior.

## Acceptance Criteria

- Only Owners can access mapping administration.
- Each mapping targets one group and either User or Group Admin.
- Testing a mapping does not persist it.
- API responses never expose claims unrelated to mapping evaluation.

## Dependencies

- Ticket 009
- Ticket 010
