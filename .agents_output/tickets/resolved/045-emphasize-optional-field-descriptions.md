# 045 - Emphasize optional field descriptions

## Goal

Make optional inputs unmistakable by rendering the word “Optional” in bold in
their visible descriptions.

## Scope

- Audit all user-editable optional fields in the frontend, including the
  asset-administration detail editor, and update their visible description or
  help-text slot so the literal word `Optional` is bold.
- Do not add “Optional” to fields that are required or conditionally required.
- Use documented Synergy label/help-text slots where markup is required; do not
  rely on HTML embedded in a string-valued component attribute.
- Preserve the existing descriptive guidance, validation, accessible names,
  and screen-reader association of every affected field.
- Add focused tests proving optional fields render the emphasized marker and
  required fields do not.

## Acceptance Criteria

- Every optional input has visible descriptive text containing bold
  “Optional”.
- Required input labels and validation behavior are unchanged.
- Help text remains accessible and retains existing security guidance such as
  the prohibition on credentials in remote-access fields.
- Frontend formatting, linting, unit tests, and production build pass.

## Dependencies

- Ticket 026
- Ticket 044
