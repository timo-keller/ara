# 068 - Keep Audit history background fixed while entries scroll

## Goal

Keep the desktop Audit history route within the white application-main surface
while its long result list scrolls, instead of allowing the white main surface
to scroll away and expose the muted shell background behind audit entries.

## Scope

- Inspect the desktop Appshell sizing in `frontend/src/app/app.scss` and the
  Audit history structure/styles in
  `frontend/src/app/features/audit/audit.page.{html,scss}`. Correct the
  relevant flex/min-height/overflow ownership so the white `.appshell-main`
  surface stays fixed within its margins and does not move out of view.
- Make the Audit history entry region the desktop scroll owner inside that
  surface. Keep the route heading, introduction, filters, result-state
  feedback, and pagination usable; audit cards must scroll without moving the
  shell rail or revealing the muted background behind the entries.
- Do not regress the documented Appshell rail/footer viewport behavior, audit
  filter URL state, pagination, card details expansion, focus visibility, or
  the independent Asset administration panes.
- At narrow widths, retain normal document/route scrolling and avoid nested
  scroll traps or clipped audit controls.
- Add focused component and browser regression coverage with enough audit rows
  to overflow a desktop viewport, verifying the fixed white surface, audit-list
  scroll ownership, stationary rail, and narrow-layout fallback.

## Acceptance Criteria

- On desktop, scrolling a long Audit history list leaves audit entries on the
  white application-main background and keeps the navigation rail in view.
- Audit history entries—not the outer main surface or browser document—provide
  the required desktop vertical scrolling.
- Filters, pagination, details, keyboard access, and narrow-screen scrolling
  remain usable.
- Frontend formatting, linting, unit tests, relevant browser tests, and the
  production build pass.

## Dependencies

- Ticket 023
- Ticket 028
- Ticket 040
- Ticket 064
