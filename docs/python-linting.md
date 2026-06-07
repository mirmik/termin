# Python Linting

Python linting is provided by Ruff and configured at the repository root in
`ruff.toml`.

Run it with:

```bash
./run-lint-python.sh
```

Specific paths can be checked during focused work:

```bash
./run-lint-python.sh termin-csg termin-app/tests
```

`./setup-test-venv.sh` installs Ruff into the shared test venv.

## Current Baseline

The initial rule set is deliberately narrow:

- `E9` for syntax and parser-level failures.
- `F63` and `F7` for Pyflakes checks that usually indicate broken code.
- `F822` and `F823` for unresolved exports and local-variable-before-assignment
  cases.

`F821` is not enabled yet. The current codebase has many unresolved forward
reference annotations (`"UIRenderer"`, `"Entity"`, and similar names), so
enabling `F821` globally would turn the first lint step into a broad typing
migration. Prefer enabling it module by module after those annotations are
cleaned up or moved behind `TYPE_CHECKING` imports.

Formatting is also not enabled yet. A repository-wide format pass should be a
separate mechanical change after the lint baseline is stable.
