# 050 - Align navbar account name and Settings gear

## Goal

Make the authenticated navbar read naturally by placing the account name before
the Settings gear and aligning it with the application name in normal mode.

## Scope

- Place the displayed authenticated account name (`Owner Developer`, for
  example) to the left of the Settings gear in the top navbar.
- Correct normal-mode layout, alignment, line height, and spacing so the
  account name is vertically aligned with the application name and Settings
  gear rather than visibly offset.
- Preserve compact-mode behavior, responsive navigation, the Settings menu,
  accessible account context, and fallback from display name to email.
- Add focused component and, where feasible, browser coverage for source
  ordering and normal-mode alignment.

## Acceptance Criteria

- At normal desktop widths, account name, application name, and Settings gear
  share a visually aligned navbar baseline.
- The account name is before the Settings gear in logical and visual order.
- Responsive and compact-mode behavior remains usable and accessible.
- Frontend formatting, linting, unit tests, relevant browser tests, and the
  production build pass.

## Dependencies

- Ticket 023
- Ticket 047
