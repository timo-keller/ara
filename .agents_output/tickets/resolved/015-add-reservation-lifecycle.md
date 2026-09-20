# 015 - Add reservation lifecycle operations

## Goal

Support extension, return, cancellation, and administrative termination.

## Scope

- Extend reservations only when the added interval is available.
- Let users return their active reservations.
- Let users cancel their future reservations.
- Let Owners and responsible Group Admins end or cancel reservations.

## Acceptance Criteria

- Extension uses the same conflict semantics as creation.
- A user cannot mutate another user's reservation.
- Group Admin authority is limited to the asset's group.
- Repeated lifecycle requests are safely rejected or idempotent.
- Terminal reservations cannot be extended.

## Dependencies

- Ticket 014
