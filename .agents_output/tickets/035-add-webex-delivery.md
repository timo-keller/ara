# 035 - Add Webex delivery

## Status

Deferred until after the browser-notification MVP.

## Goal

Deliver reservation reminders to the Webex room configured for an asset.

## Scope

- Store and validate an optional Webex room identifier per asset.
- Read the bot token from a Docker secret.
- Persist an outbox with attempt and delivery state.
- Dispatch and retry messages through an APScheduler job.

## Acceptance Criteria

- Browser notifications continue to work without Webex configuration.
- Delivery is idempotent and retryable.
- Group Admins can configure room identifiers only for their assets.
- Bot tokens and message credentials never enter asset data or logs.

## Dependencies

- Ticket 019
- Ticket 027
- Ticket 032
