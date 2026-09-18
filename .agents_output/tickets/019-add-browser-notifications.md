# 019 - Add browser notifications

## Goal

Create persistent reservation reminders for display by the browser.

## Scope

- Generate due reminders idempotently from reservation end times.
- Add APIs to list and mark the current user's notifications as read.
- Configure reminder offsets on the backend.
- Exclude open-ended and terminal reservations from future reminders.

## Acceptance Criteria

- Repeated scheduler runs do not create duplicate reminders.
- Users can access only their own notifications.
- Returned, cancelled, and administratively ended reservations are handled.
- Reminder generation recovers after process downtime.

## Dependencies

- Ticket 015
- Ticket 018
