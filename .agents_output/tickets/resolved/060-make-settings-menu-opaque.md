# 060 - Make the Settings menu opaque

## Goal

Ensure the Settings navbar dropdown has an opaque surface so its controls and
notifications remain legible over route content.

## Scope

- Diagnose the Settings dropdown popup/background styling and apply documented
  Synergy tokens, parts, or component APIs to make the visible menu surface
  opaque in normal and compact mode.
- Preserve dropdown placement, keyboard/focus behavior, gear tooltip, unread
  badge, notification actions, and responsive positioning.
- Support the configured light and dark application themes without hard-coded
  colors that reduce contrast or diverge from Synergy tokens.
- Add focused component or browser coverage that asserts an opaque computed
  menu background and verifies menu contents remain visible.

## Acceptance Criteria

- The visible Settings menu surface is opaque over route content.
- Settings and notification controls remain keyboard accessible and usable.
- The solution uses documented Synergy theming/styling mechanisms and works in
  supported themes.
- Frontend formatting, linting, unit tests, relevant browser tests, and the
  production build pass.

## Dependencies

- Ticket 047
