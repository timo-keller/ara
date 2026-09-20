# 059 - Restore compact-mode sizing

## Goal

Make enabling compact mode visibly apply small documented sizes to supported
controls again.

## Scope

- Diagnose and correct the compact-mode application lifecycle so toggling the
  setting immediately updates currently rendered supported controls and a saved
  preference applies after reload/navigation.
- Preserve ticket 049: the Settings gear trigger must remain at normal size in
  compact mode.
- Continue to use only documented Synergy `size="small"` APIs; do not replace
  component sizing with CSS transforms or unsupported attributes.
- Preserve normal-mode restoration, local preference validation, notification
  controls, keyboard interaction, and responsive behavior.
- Add focused tests for toggling, reload, navigation/render changes, normal
  restoration, and Settings-gear exemption.

## Acceptance Criteria

- Enabling compact mode immediately makes representative supported controls
  small.
- Compact mode remains effective after reload and route changes.
- Disabling it restores normal sizing, while the Settings gear is normal in
  both modes.
- Frontend formatting, linting, unit tests, relevant browser tests, and the
  production build pass.

## Dependencies

- Ticket 047
- Ticket 049
