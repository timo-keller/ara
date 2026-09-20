# 070 - Reduce Audit history card header spacing

## Goal

Remove the excess vertical space above and below Audit history card titles
caused by the default margins of the `h2` placed in each `syn-card` header.

## Scope

- Inspect the Audit event card markup in
  `frontend/src/app/features/audit/audit.page.html` and its scoped styles in
  `audit.page.scss`. Apply a focused, token-based reset or component-supported
  header styling so the `h2` retains its semantic heading level but does not
  add unintended block margins inside the card header slot.
- Reduce only the extra top/bottom title spacing; preserve deliberate Synergy
  card padding, card-to-card spacing, title readability, wrapping, and the
  spacing between the header and event details.
- Keep changes scoped to Audit history card headers. Do not globally reset
  heading margins or change Group administration/asset card headers as a side
  effect.
- Verify compact mode, long action/target labels, details expansion, and
  narrow-screen cards remain readable and accessible. Add focused component or
  browser coverage that detects the intended header spacing and guards against
  a global heading-style regression.

## Acceptance Criteria

- Audit event card headers have no unintended `h2` top or bottom margin while
  retaining semantic, readable titles and normal card padding.
- Event details, card spacing, compact mode, and responsive layouts remain
  usable.
- No non-Audit card header spacing changes as a side effect.
- Frontend formatting, linting, unit tests, relevant browser tests, and the
  production build pass.

## Dependencies

- Ticket 028
- Ticket 064
