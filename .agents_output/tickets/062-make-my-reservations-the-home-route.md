# 062 - Make My reservations the home route

## Goal

Replace the unhelpful Home destination with My reservations as the authenticated
user's primary landing page.

## Scope

- Redirect the authenticated application root/Home route to My reservations and
  make `My reservations` the primary corresponding navigation destination.
- Remove the visible `Home` navigation entry and avoid leaving a redundant Home
  page reachable through normal authenticated navigation.
- Preserve anonymous login behavior, deep links, route guards, browser history,
  active navigation state, and reservation authorization.
- Decide and test a safe compatibility behavior for existing `/home` bookmarks
  (for example, redirect them to `/reservations`).
- Add focused route/component and relevant browser coverage for authenticated
  landing, legacy Home navigation, and active navigation state.

## Acceptance Criteria

- An authenticated visit to the application root lands on My reservations.
- `Home` is not presented as a normal navigation destination.
- Existing `/home` links resolve safely to My reservations.
- Frontend formatting, linting, unit tests, relevant browser tests, and the
  production build pass.

## Dependencies

- Ticket 023
- Ticket 025
