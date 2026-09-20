# 024 - Build asset catalogue UI

## Goal

Let users find and inspect assets available to their groups.

## Scope

- Add paginated asset listing and detail views.
- Add group, type, availability, and text filters.
- Show remote-access metadata without credential fields.
- Provide responsive loading, empty, and error states.

## Acceptance Criteria

- Filters map to REST API query parameters.
- Archived assets are hidden in the normal catalogue.
- Availability and upcoming reservations are understandable.
- Keyboard and small-screen usage are supported.

## Dependencies

- Ticket 012
- Ticket 022
- Ticket 023
