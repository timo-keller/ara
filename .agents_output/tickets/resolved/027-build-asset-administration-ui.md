# 027 - Build asset administration UI

## Goal

Allow authorized administrators to manage assets in their scope.

## Scope

- Add create, edit, archive, and reactivate forms.
- Support asset type and remote-access metadata.
- Apply Owner and Group Admin group constraints.
- Add an optional future Webex room identifier field only when supported.

## Acceptance Criteria

- Group Admins can mutate assets only in their groups.
- Owners can select any active group.
- Forms do not request passwords, keys, or remote credentials.
- Archive and reactivation state is visible to administrators.

## Dependencies

- Ticket 012
- Ticket 023
- Ticket 024
