# 065 - Move account name into the Settings menu

## Goal

Remove the authenticated user name from the navbar and present it in the
Settings dropdown instead.

## Scope

- Remove the visible account name from the top navbar while retaining the
  Settings gear, tooltip, unread badge, and keyboard behavior.
- Add the current user's display name, with existing email fallback, as clear
  non-interactive account context at the top of the Settings menu.
- Preserve the account name's accessible text, compact-mode behavior,
  notification controls, menu opacity, and responsive navigation.
- Avoid exposing extra identity data beyond the name/email already visible in
  the authenticated navbar.
- Add focused component and browser coverage for navbar absence, dropdown
  presence, display-name/email fallback, keyboard access, and menu contents.

## Acceptance Criteria

- The navbar no longer displays the authenticated account name.
- Opening Settings displays the account name or email fallback clearly.
- Settings, notifications, compact mode, and the unread badge retain their
  existing behavior and accessibility.
- Frontend formatting, linting, unit tests, relevant browser tests, and the
  production build pass.

## Dependencies

- Ticket 047
- Ticket 050
- Ticket 060
