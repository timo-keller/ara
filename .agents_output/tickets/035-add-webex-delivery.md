# 035 - Add Webex delivery

## Status

Planned. Requirements confirmed; implementation pending.

## Goal

Deliver personal reservation reminders and scheduled-start messages through a
Webex bot, plus reservation-start and asset-return messages to group rooms.

## Scope

### Confirmed notification rules

| Event | Personal message | Group-room message |
| --- | --- | --- |
| End reminder at a configured offset | Yes | No |
| Previously scheduled future reservation begins | Yes | Yes |
| Reservation starts immediately or was requested with a past start | No | Yes |
| Asset explicitly returned | No | Yes |
| Future reservation cancelled | No | No |
| Reservation extended or scheduled end passes | No additional lifecycle message | No |

- Personal recipients use the reserving user's email from OIDC.
- Existing configurable end-reminder offsets apply (currently 60, 15, and 0
  minutes). Open-ended reservations have no end reminders.
- Personal start messages are sent when a future reservation begins, not when
  it is booked. Persist eligibility at creation using the original requested
  start and the creation operation's current time; do not infer it later from
  the normalized start timestamp. The current user creation path normalizes
  past starts to now.
- Room messages include the asset name, reserving user's display name, event
  time, and an ARA link. Use a neutral fallback if a display name is absent.
- Move the optional Webex room identifier to the group. Remove the asset field
  from the database, backend API, frontend types, and asset administration.
  Discard existing asset room IDs; do not copy them to groups.
- Add an asset checkbox, "Send group-room notifications", default true. It
  controls room messages only; personal messages remain independent.
- Add test send and basic delivery status in group administration.

### Proposed delivery design

- Read an optional bot token from a Docker secret through
  `ARA_WEBEX_BOT_TOKEN_FILE`; represent it as a redacted secret. Keep Webex
  optional so existing installations require no token or secret mount. Provide
  an opt-in Compose configuration for mounting the secret.
- Send personal messages with `toPersonEmail`, and group messages with `roomId`,
  using the existing `httpx` dependency and a bounded HTTP timeout.
- Persist an outbox with event identity, reservation/asset/group references,
  destination type and address, rendered message, scheduled time, attempt count,
  next attempt time, delivery state, safe error code, and Webex message ID.
  Distinguish pending, sending, delivered, failed, and skipped states.
- Enforce one outbox entry per event and destination. Include the reservation
  end timestamp/offset in end-reminder identities, so extensions can create new
  reminders without reusing obsolete ones.
- Queue immediate-start and explicit-return events in the reservation write
  transaction. A periodic job queues future-start events and due end reminders
  idempotently. Browser notification read state must not affect Webex delivery.
- Persist future-start processing state so restarts cannot regenerate the same
  start event. Avoid sending old historical starts on feature rollout.
- Dispatch bounded batches through APScheduler using its existing single-job
  execution defaults. Claim work durably, release the database transaction
  before HTTP calls, and recover interrupted claims after restart.
- Recheck reservation validity before dispatch: suppress cancelled/returned
  reservations' pending starts and reminders and reminders for an obsolete end
  time. Explicit-return messages remain eligible after return.
- Resolve recipients and room configuration at enqueue time and freeze them for
  retries. Suppress pending room delivery if the room was changed/cleared or
  the asset's checkbox was disabled; do not silently redirect queued messages.
- Missing email, room, or disabled asset room delivery yields a safe skipped
  outcome rather than blocking a reservation operation.
- Retry rate limits using `Retry-After` and retry transient failures with bounded
  backoff. Treat invalid recipients/rooms and permission failures as terminal;
  expose credential failures clearly rather than repeatedly sending requests.
- Local deduplication is guaranteed; exactly-once remote delivery is not.
  A timeout or crash after Webex accepts a message can cause a duplicate on
  retry. Do not promise provider idempotency without verifying API support.
- Group status shows bounded recent room deliveries and test results, pending
  and failed counts, and safe failure details. Do not expose personal-message
  bodies or recipient emails through group administration.
- Test send requires group-management authorization and CSRF protection. Test
  messages use the same delivery client and tracking as ordinary room messages.
  Audit room-setting and asset-checkbox changes using existing audit patterns.

### Implementation sequence

1. **Schema and configuration:** Alembic migration for the group room ID, asset
   checkbox, start eligibility/processing state, and outbox; remove the old
   asset setting without migration of its values. Extend settings and optional
   Docker-secret deployment documentation.
2. **Event generation:** Add transactional immediate-start/return enqueueing,
   scheduled-start detection, personal end reminders, deduplication, and stale
   event suppression.
3. **Webex delivery:** Add the HTTP client, durable dispatcher, retry handling,
   restart recovery, and safe operational logs.
4. **Administration:** Move room configuration to groups, add the asset checkbox,
   and expose protected group-room test send and delivery status.
5. **Verification:** Exercise migration, authorization, event timing, retry and
   restart behavior, and frontend flows; document setup and troubleshooting.

### Details to settle during implementation

- Define a bounded catch-up window for scheduled starts after downtime so an
  old start is not announced after the reservation has already ended.
- Define outbox retention, retry limits, and dispatcher batch/interval defaults.
- Confirm how group-room settings fit the existing group-edit authorization
  model; retain Owner access and permit responsible Group Admins only.

## Acceptance Criteria

- Browser notifications continue to work without Webex configuration.
- Personal end reminders target the OIDC email independently of room settings.
- Only reservations originally scheduled for the future receive personal start
  messages; immediate and past-requested starts do not.
- Room start messages cover immediate and future starts. Only explicit returns
  produce room return messages; cancellations and elapsed ends do not.
- Each asset's room-notification checkbox defaults true and affects only room
  messages. Groups without a configured room produce no room messages.
- Existing asset room settings are removed and discarded.
- Queueing is idempotent and delivery is retryable with the documented
  ambiguous-delivery limitation.
- Group Admins can configure rooms, send tests, and inspect room delivery status
  only for their manageable groups; unauthorized requests are rejected.
- Group administration provides test send and basic room-delivery status.
- Bot tokens and message credentials never enter asset data or logs.
- Tests cover future/immediate/past starts, returns versus cancellations,
  disabled room messages, missing OIDC email, extensions, repeated job runs,
  transaction rollback, restart recovery, rate limiting, and terminal failures.

## Dependencies

- Ticket 019
- Ticket 027
- Ticket 032
