# 057 - Enforce Ruff annotation rules

## Goal

Require complete Python function annotations through Ruff's `ANN` rule family
and address all violations in the backend.

## Scope

- Add `ANN` to the backend Ruff lint selection without disabling individual
  annotation rules or suppressing findings through broad per-file ignores.
- Add accurate parameter and return annotations to every newly reported backend
  function, fixture, callback, and helper.
- Preserve behavior, dependency injection, FastAPI route signatures, pytest
  fixture behavior, and runtime annotations required by Pydantic or SQLAlchemy.
- Use narrowly scoped existing type-ignore comments only when a third-party API
  genuinely cannot be expressed safely; document the reason near the ignore.
- Add or adjust tests only when an annotation-driven refactor requires it.

## Acceptance Criteria

- Ruff's configured lint selection contains `ANN`.
- `uv run ruff check .` passes with no `ANN` violations.
- Ruff formatting, ty type checking, and the full backend test suite pass.
- No broad lint suppressions or behavior changes are introduced solely to avoid
  annotation findings.

## Dependencies

- Ticket 036
