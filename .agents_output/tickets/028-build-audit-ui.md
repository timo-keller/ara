# 028 - Build audit UI

## Goal

Provide searchable audit history to authorized administrators.

## Scope

- Add paginated reverse-chronological audit listing.
- Add group, actor, action, target, and time filters.
- Render sanitized before and after changes clearly.
- Restrict routes to Owners and Group Admins.

## Acceptance Criteria

- Owners can query across groups.
- Group Admins see only selectable groups in their scope.
- Filter state is reproducible through URL query parameters.
- Large change payloads remain usable and accessible.

## Dependencies

- Ticket 017
- Ticket 023
