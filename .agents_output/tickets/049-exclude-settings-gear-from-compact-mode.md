# 049 - Keep the Settings gear at normal size in compact mode

## Goal

Keep the top-navigation Settings gear easy to discover and target when compact
mode reduces the size of other supported controls.

## Scope

- Exclude only the authenticated Settings gear trigger from compact-mode size
  application; it must retain its normal documented Synergy size whether
  compact mode is enabled or disabled.
- Keep the compact-mode setting itself, notification actions, and all other
  supported compact-mode controls behaving as they do today.
- Preserve the gear trigger's tooltip, accessible name, unread badge, keyboard
  behavior, and dropdown wiring.
- Add focused tests for normal and compact states, including a representative
  non-gear control that still becomes small.

## Acceptance Criteria

- The Settings gear remains normal size in compact mode.
- Compact mode continues to size other supported controls small and remains
  persisted across reloads.
- The Settings menu remains keyboard accessible and notification behavior is
  unchanged.
- Frontend formatting, linting, unit tests, relevant browser tests, and the
  production build pass.

## Dependencies

- Ticket 047
