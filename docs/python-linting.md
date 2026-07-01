# Python Linting

Python linting is provided by Ruff and configured at the repository root in
`ruff.toml`.

Run it with:

```bash
./run-lint-python.sh
```

The default `./run-tests-python.sh` flow also runs the repo-wide Ruff check
before pytest. Explicit pytest-target runs skip the repo-wide lint pass so
focused test commands stay focused.

Specific paths can be checked during focused work:

```bash
./run-lint-python.sh termin-csg termin-app/tests
```

`./setup-test-venv.sh` installs Ruff into the shared test venv.

## Current Baseline

The current rule set focuses on likely defects and avoids broad style churn:

- `B` for Bugbear checks that catch likely runtime bugs and ambiguous behavior:
  mutable defaults, function calls in defaults, late-bound loop variables in
  closures, missing exception chaining, non-explicit `zip()` strictness, and
  related hazards.
- `F` for the full Pyflakes rule family: undefined names, unresolved exports,
  unused imports, ambiguous star imports, unused local variables, duplicate
  arguments, and related correctness checks.
- Ruff parser diagnostics for syntax and parser-level failures. These are
  emitted before rule selection and are therefore active even though the
  resolved `E9` lint rule is currently only `E902`.
- `E902` for I/O errors while reading Python sources.

Forward reference annotations should be backed by `TYPE_CHECKING` imports when
the referenced type is intentionally type-only. Avoid runtime imports that
introduce circular dependencies just to satisfy the linter.

Formatting is also not enabled yet. A repository-wide format pass should be a
separate mechanical change after the lint baseline is stable.
