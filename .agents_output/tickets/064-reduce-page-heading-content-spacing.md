# 064 - Reduce page heading-to-content spacing

## Goal

Make page content feel denser by reducing the vertical gap between a route
heading/introduction and its first actionable content or entries by half.

## Scope

- Audit authenticated frontend pages, including Audit history, Asset
  administration/Create asset, catalogue, reservations, administration, and
  other route pages with comparable heading-to-content spacing.
- Identify the shared or page-specific spacing rule responsible for the gap and
  reduce that heading-to-first-content gap by approximately 50% consistently.
- Preserve spacing inside forms, cards, lists, alerts, section headings,
  responsive layouts, focus visibility, and the independently scrolling Asset
  administration panes.
- Prefer documented Synergy spacing tokens and shared route styles over
  scattered hard-coded margins; add page-specific overrides only where layout
  structure genuinely differs.
- Add focused visual/layout component or browser tests for Audit history and
  Asset administration plus regression coverage for representative other pages.

## Acceptance Criteria

- Audit history and Create asset show approximately half their prior heading to
  first-content gap.
- Comparable authenticated route pages use the same denser heading/content
  rhythm without cramped internal control spacing.
- Responsive layouts, scrolling containers, and accessibility behavior remain
  intact.
- Frontend formatting, linting, unit tests, relevant browser tests, and the
  production build pass.

## Dependencies

- Ticket 023
- Ticket 028
- Ticket 044
