# 040 - Keep the Appshell rail in the viewport

## Goal

Use the complete browser viewport for the authenticated shell while keeping
the left navigation rail visible when page content, such as Administration,
is taller than the viewport.

## Scope

- Correct the authenticated Appshell flex and overflow sizing so it occupies
  the viewport height without creating document-level overflow from its layout.
- Make the main content area the scroll container on desktop; the rail must
  remain within the viewport while that content scrolls.
- Ensure the rail footer (Log out) remains reachable without scrolling the
  browser document, following the Synergy Rail Navigation pattern.
- Preserve the documented responsive/tablet behavior of `syn-side-nav` and
  retain normal page scrolling on narrow viewports where the rail is overlaid
  or otherwise changes form.
- Add component or browser-level regression coverage for a page taller than
  the viewport, including Administration.

## Acceptance Criteria

- At desktop widths, the navigation rail and its footer fit in the viewport
  while long route content scrolls independently.
- The browser document has no layout-induced vertical scrollbar for the
  authenticated Appshell.
- Keyboard navigation, focus visibility, responsive navigation, and existing
  routes continue to work.
- Frontend formatting, linting, unit tests, relevant browser tests, and
  production build pass.

## Dependencies

- Ticket 023
