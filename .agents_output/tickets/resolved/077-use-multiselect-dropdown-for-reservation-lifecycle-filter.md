# 077 - Use a multiselect dropdown for the My reservations lifecycle filter

## Goal

Replace the inline lifecycle checkbox group introduced by ticket 073 with one
compact, accessible multiselect dropdown, without changing the lifecycle
filter's API, URL representation, server classification, or result semantics.

## Scope

- In `frontend/src/app/features/reservations/`, replace the `fieldset` and its
  six native lifecycle checkboxes with the established Synergy Angular
  `SynComboboxComponent` and `SynOptionComponent`. Render a `<syn-combobox>`
  labelled `Lifecycle`, with `multiple`, `clearable`, and `restricted`, and
  with the existing ordered values: current, future, expired, returned,
  cancelled, and ended. Bind its array-valued `valueChange` output to the
  existing lifecycle filter state; do not parse its space-delimited attribute
  form manually.
- Retain the existing lifecycle option values exactly, while presenting readable
  labels (`Current`, `Future`, `Expired`, `Returned`, `Cancelled`, `Ended`).
  The visible label and its associated form control must identify the filter;
  add brief help text that explains that more than one lifecycle can be shown.
  Do not substitute a visually labelled but inaccessible custom dropdown.
- Add adjacent, real `type="button"` actions named `Select all lifecycles` and
  `Clear lifecycle`. Selecting all must select precisely every supported
  lifecycle in the stable option order; clearing must select none. The latter
  complements the Synergy clear affordance and must remain available without
  relying on a pointer-sized icon. Both actions are disabled when they would
  have no effect, are keyboard-focusable when enabled, and update the same
  lifecycle state path as selecting or removing an individual option.
- Display a text summary next to or immediately below the control: `All
  lifecycles` when all six are selected, `No lifecycle selected` when none are
  selected, otherwise `N of 6 lifecycles selected`. Keep it synchronized after
  component changes, Select all, Clear lifecycle, and browser navigation.
  Associate the summary with the combobox as descriptive text (or provide an
  equivalent accessible relationship) so screen-reader users receive the
  selected count; do not announce every render as a disruptive live update.
- Preserve normal Synergy combobox keyboard behavior: Tab reaches the labelled
  control and then the auxiliary buttons, Enter/Space opens or selects as
  provided by the component, arrow keys navigate the list, and Escape closes
  it. Do not add document-level key handlers or trap focus. Verify keyboard
  operation includes opening the dropdown, selecting/removing more than one
  option, using both auxiliary actions, and returning focus predictably.
- A lifecycle selection, Select all, or Clear lifecycle resets only `offset` to
  zero and navigates through the existing query-state helper. Continue to
  serialize one repeatable `lifecycle` query parameter per selected value in
  stable option order; omit it when no lifecycle is selected. Valid bookmarked
  URLs and back/forward navigation must restore both the selected values and
  summary. Continue discarding malformed or unsupported lifecycle query values
  safely, including duplicates (normalize them to one occurrence in option
  order).
- Keep the filter row usable at narrow widths: the combobox must not force
  horizontal page scrolling or overlap its label, tags, clear affordance,
  summary, or auxiliary buttons. It may take a full row below the other fields;
  auxiliary actions may wrap with adequate target spacing. Retain ticket 073's
  responsive reservation-table behavior unchanged.
- Do not modify backend router, service, DAO, schemas, filtering predicates, or
  lifecycle calculation. The repeated-query OR semantics, intersection with
  the other filters, captured server `now`, classification boundaries,
  privacy behavior, totals, pagination, and lifecycle mutation authorization
  delivered by ticket 073 remain authoritative and unchanged.
- Update reservation-page unit tests to cover Synergy component imports and
  markup; readable labels; array selection; Select all/Clear enabled states;
  selected-summary states; reset of offset; stable query serialization;
  malformed/duplicate query normalization; and URL/back-forward restoration.
  Update the relevant Playwright flow to operate the dropdown by keyboard,
  select multiple values, use both auxiliary actions, verify the summary and
  query state, and exercise the narrow layout. Retain the ticket 073 backend
  lifecycle/API tests unchanged as regression coverage.

## Acceptance Criteria

- My reservations has one labelled Synergy multiselect lifecycle combobox, not
  an inline group of lifecycle checkboxes, and it supports all six categories.
- Users can select and remove several lifecycle categories with keyboard or
  pointer, select all categories, and clear them. The control exposes a correct
  accessible selected summary and does not create a focus trap.
- Lifecycle updates preserve the existing repeatable query format and filter
  behavior, reset pagination offset only, and restore correctly from valid URLs
  and browser history. Invalid and duplicate query values cannot create invalid
  UI selections.
- The filter is usable without horizontal overflow on a narrow viewport, and
  all ticket 073 backend lifecycle semantics, visibility/privacy rules,
  pagination, and action authorization remain unchanged.
- Frontend format, lint, unit tests, relevant Playwright tests, and production
  build pass.

## Dependencies

- Ticket 073
