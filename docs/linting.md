# Linting And Static Analysis

This document tracks the intended linting direction for the repository. The
goal is to add checks in stages that catch real defects first, then broaden
coverage once the baseline is stable.

## Current State

- Python uses Ruff through `./run-lint-python.sh`.
- The Python baseline is intentionally narrow and documented in
  `docs/python-linting.md`.
- CI runs Python lint as a separate job before the heavier build jobs.
- C/C++ currently has no repository-owned lint or static-analysis entry point.

## Python Next Steps

Prefer adding rules in small batches with a clean baseline for each batch.

Recommended near-term Ruff additions:

- Done: a narrow low-noise Bugbear baseline is enabled (`B006`, `B009`, `B010`,
  `B011`, `B012`, `B018`).
- Full Pyflakes `F` after auditing import-contract noise in `__init__.py`
  files. This would add unused imports, star-import ambiguity, unused
  variables, duplicate arguments, and related checks.
- More targeted Bugbear rules for likely runtime bugs, especially function calls
  in defaults, missing exception chaining, and accidental non-strict `zip`.
- `F541` and similar low-noise correctness checks can be enabled early if they
  do not create migration noise.

Defer until the defect-oriented baseline is clean:

- Ruff formatter and import sorting. Treat this as a separate mechanical
  change, not mixed with semantic fixes.
- `pyupgrade` style modernization.
- Type checking with mypy or pyright. This needs package-boundary cleanup and a
  clear policy for native modules, generated bindings, and editor-only imports.

## C/C++ Linting Direction

The first C/C++ milestone should be an opt-in script, not a mandatory CI gate:

```bash
./run-lint-cpp.sh
```

Suggested behavior:

- Configure a dedicated build directory, for example `build/Release-lint`.
- Pass `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`.
- Keep lint builds separate from normal SDK/test builds to avoid changing build
  semantics.
- Disable unity build and preferably PCH for lint runs, because clang-tidy
  diagnostics are easier to interpret on real translation units.
- Exclude `termin-thirdparty`, generated SDK outputs, bundled Python, and build
  directories.

Recommended first `clang-tidy` baseline:

- `clang-diagnostic-*` and `clang-analyzer-*` for compiler-backed diagnostics
  and path-sensitive static analysis.
- A narrow subset of `bugprone-*`, `performance-*`, and `modernize-*` after an
  initial dry run. Do not enable broad style families before seeing the noise
  level on the current codebase.
- `readability-*` should stay mostly off at first; it tends to produce style
  churn rather than defect signal.

Possible later additions:

- `clang-format` as a separate formatting baseline.
- `cppcheck` if it finds issues that clang-tidy misses in this codebase.
- Include-what-you-use only after include boundaries are stable enough to make
  its output actionable.

## CI Policy

Keep each lint stage separately callable and separately gated:

- Python lint is already cheap enough for every PR.
- C/C++ lint should start as manual or scheduled CI until the baseline is clean.
- Once clean, promote a small stable C/C++ rule set to PR CI.
- Expensive static analysis can remain scheduled or opt-in.
