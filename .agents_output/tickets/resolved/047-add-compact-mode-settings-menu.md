# 047 - Add compact-mode settings menu

## Goal

Give authenticated users a discoverable settings menu in the top navigation
that combines the existing notification controls with a compact-mode preference
for denser UI controls.

## Scope

- Add a gear-icon button to the authenticated top navigation with the visible
  tooltip text `Settings`.
- Open a documented Synergy dropdown/menu from that button. Move the current
  notification control and its existing behavior into this menu; do not remove
  notification functionality or alter its permission, browser-support, or
  error handling behavior.
- Add a compact-mode setting in the same menu. When enabled, apply Synergy's
  documented small-size API to applicable interactive UI elements; when
  disabled, retain the current default sizing.
- Apply compact sizing consistently to controls rendered in authenticated
  routes, including navigation actions, form controls, buttons, selects,
  comboboxes, pagination, and notification controls where their documented
  APIs support a small size. Do not use unsupported attributes or CSS scaling
  to imitate component sizing.
- Make the selected setting persist for the current browser and restore it
  safely on reload. Default existing users to normal sizing. A stored malformed
  value must fall back safely to normal sizing.
- Keep the menu keyboard accessible: its trigger has an accessible name,
  tooltip, focus behavior, and menu controls work with keyboard interaction.
- Add focused frontend tests for the trigger/tooltip, moving and retaining the
  notification control, toggling and restoring compact mode, and representative
  small-size rendering. Add relevant browser coverage if the existing e2e
  suite can exercise the settings menu.

## Acceptance Criteria

- The authenticated top navigation presents a gear icon whose tooltip reads
  `Settings`.
- Notification controls remain available and function from the settings menu.
- Compact mode is clearly labelled, changes supported controls to the
  documented small size, and can be returned to normal sizing.
- Reloading preserves a valid compact-mode choice without affecting users with
  no saved preference or invalid saved data.
- The menu and its controls are accessible by keyboard and screen reader.
- Frontend formatting, linting, unit tests, relevant browser tests, and the
  production build pass.

## Dependencies

- Ticket 022
- Ticket 023
- Ticket 029
