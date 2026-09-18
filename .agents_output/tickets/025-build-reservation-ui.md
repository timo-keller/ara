# 025 - Build reservation UI

## Goal

Support creation and lifecycle management of user reservations.

## Scope

- Add date-time inputs for now and future reservations.
- Allow an optional end time.
- Add own-reservation listing, extension, return, and cancellation actions.
- Present conflict responses with actionable schedule information.

## Acceptance Criteria

- Local date-time input is converted to unambiguous UTC API values.
- Open-ended reservations are clearly identified before confirmation.
- Actions require confirmation where data loss or disruption is possible.
- The UI refreshes availability after successful mutations.

## Dependencies

- Ticket 015
- Ticket 024
