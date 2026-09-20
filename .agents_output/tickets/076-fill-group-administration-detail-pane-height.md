# 076 - Fill Group administration detail pane height

## Goal

Make the desktop Group administration workspace use the full available height
of the fixed application-main surface, so the selected group's right-hand
editor/mapping pane reaches the bottom of that surface rather than stopping at
the current capped workspace height.

## Scope

- Update only the desktop sizing and scroll ownership needed for Group
  administration in `frontend/src/app/features/administration/` and, only if a
  missing flex constraint makes it necessary, the existing
  administration-specific rules in `frontend/src/app/app.scss`. Do not change
  group or role-mapping APIs, authorization, data/draft behavior, markup
  semantics, or the Asset administration route.
- At widths above `48rem`, preserve the Appshell ownership established by
  ticket 069: `.appshell` and `.appshell-main--administration` are the fixed
  desktop surface, and the administration route must form an unbroken
  `min-height: 0` flex sizing chain from its host to its content and workspace.
  The route content must not introduce a competing outer vertical scroll area
  that leaves unused space below the workspace.
- Make `.group-workspace` consume the remaining height below the route heading,
  introduction, and any route-level feedback, using flex/grid sizing rather
  than its current fixed/capped `height: min(34rem, calc(100dvh - 12rem))`.
  It must remain shrinkable (`min-height: 0`) when those elements consume
  vertical space.
- Keep the Groups master pane and the `syn-card.group-editor` detail pane as
  the desktop scroll owners. Both pane boxes must stretch to the workspace's
  full computed height; long group lists scroll independently on the left, and
  the selected group's form plus role-mapping content scrolls independently on
  the right. Do not put a second scroll container around the workspace, clip
  the card, or make the outer white main surface/document scroll on desktop.
- Preserve the 48rem-and-below fallback from tickets 074/075: one-column
  master then detail document flow, no forced viewport/flex height, and normal
  page scrolling without nested scroll traps, clipped actions, or horizontal
  overflow. Keep the existing selected/keyboard/focus affordances and readable
  wrapping for long group names and JMESPath expressions.
- Add or update focused browser/Playwright coverage at a desktop viewport with
  enough groups and mappings to overflow. Assert that the workspace/detail
  pane bottom aligns with (or fills the available height of) the white
  administration main surface, the editor and list have independent vertical
  scrolling while the navigation rail remains fixed, and the outer
  administration content/main/document does not become the desktop scroll
  owner. At a narrow viewport, assert the panes stack and document scrolling
  remains available. Retain relevant group/mapping workflow coverage.

## Acceptance Criteria

- On desktop, the Group administration right detail pane visibly uses the full
  remaining height of the fixed white application-main surface; no arbitrary
  34rem-style gap remains beneath it.
- The Groups pane and selected-group detail pane independently scroll their
  overflow, without moving the desktop shell rail or exposing the muted shell
  background.
- Heading, alerts, group editing, scoped role-mapping controls, and their
  keyboard/focus behavior remain usable and unchanged.
- At 48rem and below, the workspace stacks in normal document flow with no
  desktop height constraint or nested-scroll regression.
- Frontend formatting, linting, unit tests, relevant Playwright tests, and the
  production build pass.

## Dependencies

- Ticket 074
- Ticket 075
