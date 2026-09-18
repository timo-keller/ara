# 026 - Build group administration UI

## Goal

Allow Owners to administer groups and group-scoped role mappings.

## Scope

- Add group create, edit, archive, and reactivate screens.
- Add role-mapping create, edit, disable, and test workflows.
- Explain JMESPath matching and show validation errors.
- Restrict routes and controls to Owners.

## Acceptance Criteria

- Owners can complete all supported group and mapping operations.
- Mapping tests show match results without persisting changes.
- Archive conflicts identify unresolved reservations.
- Non-Owners cannot navigate to administration routes.

## Dependencies

- Ticket 011
- Ticket 023
