# 069 - Keep Group administration background fixed while content scrolls

## Goal

Keep the desktop Group administration route within the white application-main
surface while its long administration content scrolls, instead of allowing the
white surface to scroll away and expose the muted shell background.

## Scope

- Inspect the desktop Appshell sizing in `frontend/src/app/app.scss` and the
  Group administration structure/styles in
  `frontend/src/app/features/administration/administration.page.{html,scss}`.
  Correct flex/min-height/overflow ownership so `.appshell-main` remains a
  fixed white surface within its margins for this route.
- Make the Group administration content area the desktop scroll owner inside
  that white surface. Long Groups and Role mappings lists must remain usable
  without moving the shell rail or leaving entries displayed over the muted
  shell background; retain accessible access to the create/edit forms, alerts,
  and list actions.
- Preserve Owner-only routing and controls, group/mapping create/edit/archive/
  reactivate/disable/test behavior, archive-conflict feedback, keyboard focus,
  and the documented rail footer viewport behavior. Do not alter the existing
  Asset administration independent-pane behavior.
- At narrow widths, retain normal document/route scrolling and avoid nested
  scroll traps, clipped forms, or inaccessible actions.
- Add focused component and browser regression coverage with enough groups and
  mappings to overflow a desktop viewport, verifying the fixed white surface,
  administration-content scrolling, stationary rail, and narrow-layout
  fallback.

## Acceptance Criteria

- On desktop, long Group administration content scrolls within the fixed white
  application-main surface; it never appears over the muted shell background.
- The navigation rail remains in the viewport while administration content
  scrolls, and all existing administration workflows remain usable.
- Narrow layouts retain normal accessible scrolling without nested-scroll
  regressions.
- Frontend formatting, linting, unit tests, relevant browser tests, and the
  production build pass.

## Dependencies

- Ticket 023
- Ticket 026
- Ticket 040
- Ticket 064
