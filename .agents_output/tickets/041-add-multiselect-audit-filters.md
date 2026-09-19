# 041 - Add multiselect audit action and target filters

## Goal

Let administrators filter audit history by one or more known actions and
target types without guessing free-form values.

## Scope

- Define one canonical, tested vocabulary of supported audit action values and
  target types from the actions currently recorded by the backend. Do not infer
  filter choices from the current page of audit results.
- Extend the audit query schema, router, service, DAO, and tests to accept
  repeated `action` and repeated `target_type` query parameters, applying
  OR-within-a-field and AND-across-the-other existing filters.
- Keep a single supplied action or target type backward compatible with the
  current API. Reject invalid vocabulary values with the established validation
  response rather than silently ignoring them.
- Replace the Audit page Action and Target type text inputs with documented
  `syn-combobox` multiple, clearable, restricted controls backed by the
  canonical options.
- Represent multiple selections losslessly in URL query parameters, restore
  them on reload/back/forward navigation, and reset pagination when they change.
- Retain group-scope authorization and all remaining audit filters.

## Acceptance Criteria

- The UI presents every supported audit action and target type as searchable
  selectable options; arbitrary free-form values cannot be submitted.
- Selecting multiple actions/types yields exactly events matching any selected
  value in that field, while other selected filters still constrain results.
- Deep links, refresh, browser navigation, and a single legacy query value
  reproduce the same filter state.
- Owners and Group Admins retain their existing server-enforced scopes.
- Backend and frontend formatting, linting, type checks, unit/API tests,
  relevant browser tests, and production build pass.

## Dependencies

- Ticket 017
- Ticket 028
