# 079 - Resolve Webex space links in group administration

## Status

Resolved. Implemented and verified.

## Goal

Let Owners and responsible Group Admins configure group-room notifications using
a Webex space link instead of finding and copying the opaque Webex API room ID.
The backend resolves the link through the ARA bot's Webex access and saves the
canonical room identifier used for delivery.

## Scope

### Group administration

- Replace the primary "Webex room identifier" input with "Webex space link".
- Show clear setup instructions next to the input:
  1. Add **ARA Notification Bot** to the intended Webex space.
  2. Copy that space's link from Webex.
  3. Paste the link here and save it.
  4. Send a test message to verify delivery.
- Accept links in the form
  `webexteams://im?space=c149af1a-71e9-4955-a2b0-9ca8b423b129`.
- Provide saving/resolution feedback. A failure should tell the administrator
  whether the link is invalid, Webex is unavailable, the bot token is missing or
  invalid, or the space is not visible to the bot. For an inaccessible space,
  instruct them to add ARA Notification Bot and try again.
- Preserve test send and delivery status. Tests target the saved configuration.
- Retain the saved link for display after reload, either through explicit
  persistence or reliable reconstruction from the resolved API identifier.
- Existing groups with saved API room IDs remain usable without reconfiguration.
  Clearing the space link disables room notifications and clears its saved ID.

### Backend resolution and persistence

- Parse and validate the supported deep-link scheme, action, and `space` UUID.
  Reject missing, malformed, or ambiguous/duplicate `space` parameters.
- Authorize the actor for the target group before contacting Webex. Preserve
  CSRF protection, archive restrictions, and the existing audit boundary.
- Use the configured ARA bot token to find the matching space through Webex's
  room API. Handle pagination so resolution also works beyond the first page.
- Compare the supplied space UUID with the identifier of rooms visible to the
  bot. Require a group space, rather than a private direct-message conversation.
- Save the **actual canonical room ID returned by Webex**. Do not manufacture an
  ID by assuming a region or prefix: IDs may contain regional forms such as
  `urn:TEAM:eu-central-1_k`.
- Store the room ID only after successful resolution. Invalid links, missing
  membership, rate limits, network failures, and rejected Webex requests must
  leave the previously saved configuration intact.
- Keep network calls bounded with timeouts and a documented pagination limit.
  Resolution must not hold SQLite's write lock while waiting on Webex.
- Send credentials only to the trusted Webex API endpoint, never to a URL from
  the submitted link. Validate any pagination destination before following it.
- Do not expose bot tokens or raw sensitive Webex responses in errors or logs.
- Continue using the resolved group room ID for the existing delivery outbox;
  retain its stale-room suppression when configuration changes.
- Update backend/deployment documentation to describe the space-link workflow.

## Acceptance Criteria

- An Owner or responsible Group Admin can follow the instructions, add the bot,
  paste a supported space link, save it, and send a room test without handling
  an API room ID manually.
- The saved room ID equals the canonical ID returned by Webex for the linked
  group space, including region-specific identifier formats.
- Valid spaces found on later API pages resolve successfully.
- The saved space link remains visible after reloading group administration.
- An inaccessible space produces actionable "add the bot" guidance.
- Invalid links and failed lookups preserve the previous room configuration.
- Clearing the link disables group-room notifications; personal messages remain
  independent.
- Existing room-ID configurations continue delivering without a forced reset.
- Ordinary Users and administrators of another group cannot change the setting
  or trigger Webex lookups; unsafe requests still require CSRF protection.
- Tests cover valid and malformed links, duplicate parameters, regional IDs,
  pagination, direct-space rejection, bot membership, missing credentials,
  rate limits/network failures, unchanged settings on failure, clearing,
  authorization, and the frontend setup/save/test flow.

## Dependencies

- Ticket 035 - Add Webex delivery

## Implementation and verification

- Added strict deep-link validation and bot-visible room resolution, preserving
  Webex's canonical regional room IDs. Pagination is restricted to the trusted
  rooms endpoint, limited to 20 pages with a 30-second total deadline.
- Added migration 0006 to persist normalized links alongside room identifiers.
  Existing room-ID configuration remains supported. Failed lookups preserve
  configuration; clearing removes both fields.
- Resolution occurs outside the database transaction and archive state is
  checked again before the audited update. Authorization and CSRF precede lookup.
- Group administration includes bot setup instructions, resolution feedback,
  saved-link display, legacy configuration guidance, saved-room tests, and status.
- Updated backend, deployment, and architecture documentation.
- Verification: 144 backend tests, Ruff formatting/lint, and ty checks passed;
  90 frontend tests, lint, changed-file formatting, development/production builds,
  and the targeted Group Admin Playwright workflow passed.
- Repository-wide frontend formatting reports unrelated existing formatting
  issues in angular.json, reservations.page.spec.ts, and generated test reports.
  Production build reports an initial-bundle budget warning (511.22 kB / 500 kB).

### Room identifier format correction

- A live read-only lookup exposed that decoded room IDs include the
  `ciscospark://` scheme before either `us` or a regional `urn:TEAM:...` authority.
  Corrected UUID extraction and fixtures to match the actual API format.
- All 55 Webex tests, Ruff lint, and ty checks passed. Rebuilt the running backend
  and verified that the reported space resolves successfully without sending a
  message or changing its saved configuration.
