# 029 - Build notification UI

## Goal

Display persisted reminders and optionally raise browser notifications.

## Scope

- Poll or refresh the current user's notification endpoint.
- Add unread count, notification list, and mark-read interactions.
- Request browser Notification API permission only after user interaction.
- Raise browser notifications while the application is running.

## Acceptance Criteria

- Denied browser permission does not break in-application notifications.
- A notification is not raised repeatedly by the same browser session.
- Users can mark individual or all notifications as read.
- Open-ended reservations do not show false expiry reminders.

## Dependencies

- Ticket 019
- Ticket 023
