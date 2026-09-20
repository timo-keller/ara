# 058 - Separate asset administration pane scrolling

## Goal

Keep the managed-assets column usable while a long selected-asset editor scrolls
independently, and remove redundant guidance below the type filter.

## Scope

- At desktop widths, make the managed-assets left pane and right editor pane
  independently scrollable within the available route viewport. Scrolling the
  editor must not move the managed-assets list, and scrolling the list must not
  move the editor.
- Retain responsive narrow layouts with normal, usable stacked document
  scrolling; do not create nested scroll traps on small viewports.
- Preserve the selected state, keyboard access, filters, Create asset action,
  archive/reactivate controls, and independent application-shell rail behavior.
- Remove the descriptive help text beneath `Filter by asset type`; keep its
  accessible label, clearable dropdown behavior, and filter functionality.
- Add focused component and browser coverage for independent desktop scrolling,
  narrow layout behavior, and absence of the removed help text.

## Acceptance Criteria

- At desktop widths, the asset-list and editor panes scroll independently.
- At narrow widths, the layout remains accessible with normal stacked scrolling.
- The asset-type filter has no visible description beneath it and remains
  labeled, clearable, and functional.
- Frontend formatting, linting, unit tests, relevant browser tests, and the
  production build pass.

## Dependencies

- Ticket 044
- Ticket 051
