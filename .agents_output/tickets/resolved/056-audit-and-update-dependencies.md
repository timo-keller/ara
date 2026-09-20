# 056 - Audit and update dependencies

## Goal

Identify known vulnerable backend dependencies with `uv audit` and update the
affected libraries to safe compatible releases.

## Scope

- Run `uv audit` against the locked backend environment and record the initial
  findings in the implementation notes or commit body; do not suppress or
  ignore findings without documented justification.
- Update only dependencies required to resolve reported advisories, including
  direct constraints when necessary, through the repository's uv workflow.
- Regenerate `backend/uv.lock`; do not manually edit package resolutions.
- Re-run `uv audit` after the update and ensure no resolvable known advisories
  remain.
- Run backend formatting, linting, type checks, and the full test suite.
- Do not broaden this ticket into unrelated dependency modernization.

## Acceptance Criteria

- `uv audit` has been run before and after the dependency update.
- Reported vulnerabilities are resolved through minimal compatible updates, or
  any unavoidable finding is explicitly documented with a reason and follow-up.
- Dependency declarations and `uv.lock` are reproducible through uv.
- Ruff formatting/linting, ty type checks, and the backend test suite pass.

## Dependencies

- Ticket 036
