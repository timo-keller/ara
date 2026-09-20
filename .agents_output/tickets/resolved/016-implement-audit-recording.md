# 016 - Implement audit recording

## Goal

Record all security-relevant domain mutations atomically.

## Scope

- Add an audit DAO and service integration pattern.
- Record actor, action, group, target, timestamp, correlation ID, and changes.
- Integrate group, mapping, asset, and reservation mutations.
- Sanitize sensitive and unnecessary values from snapshots.

## Acceptance Criteria

- Domain changes and their audit event share one transaction.
- Failed mutations do not leave audit events behind.
- All required mutation types produce an event.
- Tokens, secrets, cookies, and full OIDC claims are never recorded.

## Dependencies

- Ticket 011
- Ticket 012
- Ticket 015
