# 072 - Show current asset reservation holders

## Goal

Show the identity of the user who currently holds a reserved asset wherever the
viewer is authorized to see that asset. Do not present a future reservation as
a current holder, and do not disclose identities through unavailable or
archived-asset paths.

## Scope

- Extend the authorized asset catalogue response (`GET /api/assets`) with an
  optional, display-safe current-holder field (for example,
  `reserved_by_display_name`). It must be populated only for the single active
  reservation whose half-open interval contains the server's UTC `now`:
  `starts_at <= now` and (`ends_at IS NULL` or `ends_at > now`). Use the same
  `now` reference for the existing `availability` value and holder lookup so a
  row cannot be `available` while naming a holder, or `reserved` without the
  available holder identity.
- Implement the lookup in the asset DAO/service/schema path rather than making
  one reservation request per catalogue row. Join the reservation owner only
  after the existing asset/group visibility policy has admitted the asset. Use
  the local `User.display_name` as the identity shown to other authorized group
  members; if it is null or blank, use that user's email; if neither is present,
  return a neutral non-identifying fallback such as `Unknown user`. Do not add
  OIDC subject, issuer, email when a display name exists, or any other claims
  to asset or reservation responses.
- Preserve the current availability semantics exactly: terminal reservations,
  reservations ending exactly at `now`, and future active reservations do not
  make an asset currently reserved and must have a null current-holder field.
  An open-ended current reservation does. Existing conflict/adjacency rules
  guarantee at most one current active holder; treat an unexpected duplicate
  defensively rather than producing duplicate asset rows.
- Add the holder to the Asset catalogue UI and its TypeScript model in
  `frontend/src/app/features/assets/`. In the existing responsive table, show
  it as part of the availability cell/label (for example, `Reserved by Ada
  Lovelace`); show only `Available` when there is no current holder. Keep the
  existing availability filtering, table headers, keyboard detail navigation,
  compact layout, and accessible labels usable.
- The holder is authorized asset metadata, not public reservation information:
  non-members must continue to receive no asset row/detail/schedule for another
  group; members may see holders only in their own active groups; Owners retain
  their existing all-group access; and Group Admins retain their existing
  scoped access. Do not expose holder identity through `/api/reservations/mine`
  for an asset the caller can no longer see.
- Archived assets remain excluded from the normal catalogue and therefore from
  this display. Preserve the existing API rule that only an Owner or responsible
  Group Admin can list archived assets; if that administrative list renders the
  same catalogue data, it may show a holder only under that already-authorized
  access. An asset with only a future reservation remains available now and
  must not show that future user's identity as its current holder.
- Add focused DAO/service/API tests for a named holder, display-name fallback,
  available asset, future-only reservation, terminal/ended-at-now reservation,
  and open-ended current reservation. Cover Owner, Group Admin, member, and
  cross-group denial/absence to prove identity does not leak. Add frontend unit
  coverage for the rendered labels and update the relevant Playwright catalogue
  workflow to cover desktop and narrow responsive output without table overflow.

## Acceptance Criteria

- A currently reserved, visible asset identifies its current reservation holder
  by the permitted display-safe identity; an available or future-only asset
  does not identify a holder.
- Holder and `availability` agree at the same UTC boundary, including bounded,
  open-ended, terminal, and adjacent reservations.
- Asset and group authorization, archival behavior, pagination/filter totals,
  and reservation privacy remain intact; no OIDC claims or unpermitted user
  identity data are exposed.
- The catalogue clearly distinguishes `Available` from `Reserved by …` in both
  responsive table modes and remains accessible by keyboard and screen reader.
- Backend formatting/linting/type checks and relevant backend tests, plus
  frontend formatting/linting/unit tests, relevant Playwright tests, and the
  production build pass.

## Dependencies

- Ticket 066
