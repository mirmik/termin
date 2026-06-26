# Linting And Static Analysis

This document tracks the intended linting direction for the repository. The
goal is to add checks in stages that catch real defects first, then broaden
coverage once the baseline is stable.

## Current State

- Python uses Ruff through `./run-lint-python.sh`.
- The Python baseline is defect-oriented and documented in
  `docs/python-linting.md`; full Bugbear `B` and full Pyflakes `F` are enabled.
- CI runs Python lint as a separate job before the heavier build jobs.
- C/C++ has an opt-in clang-tidy entry point through `./run-lint-cpp.sh`.
  It is not a mandatory CI gate yet.

## Python Next Steps

Prefer adding rules in small batches with a clean baseline for each batch.

Recommended near-term Ruff additions:

- Done: the full Bugbear `B` baseline is enabled.
- Done: the full Pyflakes `F` baseline is enabled after auditing package
  facades and intentional re-exports.

Defer until the defect-oriented baseline is clean:

- Ruff formatter and import sorting. Treat this as a separate mechanical
  change, not mixed with semantic fixes.
- `pyupgrade` style modernization.
- Type checking with mypy or pyright. This needs package-boundary cleanup and a
  clear policy for native modules, generated bindings, and editor-only imports.

## C/C++ Linting

Run the current opt-in baseline with:

```bash
./run-lint-cpp.sh
```

Focused checks can pass repository-relative path filters:

```bash
./run-lint-cpp.sh termin-render termin-graphics
```

Python/nanobind binding translation units are opt-in because they require the
Python binding build graph:

```bash
./run-lint-cpp.sh --python-bindings
./run-lint-cpp.sh --python-bindings termin-render/python
```

The script:

- configures a dedicated build directory, `build/Release-lint` by default;
- uses `build/Release-lint-python` by default for `--python-bindings`;
- passes `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`;
- keeps lint builds separate from normal SDK/test builds to avoid changing build
  semantics.
- disables unity build and PCH, because clang-tidy
  diagnostics are easier to interpret on real translation units.
- excludes `termin-thirdparty`, generated SDK outputs, bundled Python, and build
  directories.
- starts with `clang-diagnostic-*` and a narrow non-`optin`
  `clang-analyzer-*` baseline;
- treats matched clang-tidy warnings as errors;
- excludes the noisy C11 `*_s` replacement warning for ordinary
  `memcpy` / `memset` calls and `clang-analyzer-deadcode.*` until local and
  third-party header noise is audited.
- keeps clang's `nan-infinity-disabled` diagnostic enabled. Engine math,
  collision, lighting, plotting, and ray queries may rely on IEEE NaN/Inf
  semantics for sentinel values, so repository-owned runtime targets must not
  enable global fast-math flags. If a leaf numeric kernel needs fast-math, scope
  it to that target/source and add tests showing it does not observe or produce
  NaN/Inf sentinels.
- in `--python-bindings` mode only, excludes
  `clang-analyzer-core.NullDereference` from the default checks because the
  analyzer repeatedly reports false positives inside nanobind's list caster;
  explicit `--checks` overrides keep full control.

Useful options:

- `./run-lint-cpp.sh --configure-only` to generate `compile_commands.json`
  without running clang-tidy.
- `./run-lint-cpp.sh --checks 'CHECKS'` to test broader local rule sets.
- `./run-lint-cpp.sh --warnings-as-errors ''` to run an exploratory audit
  without failing on warnings.
- `CLANG_TIDY_BIN=/path/to/clang-tidy ./run-lint-cpp.sh` when multiple LLVM
  versions are installed.

Recommended next `clang-tidy` additions after the baseline is understood:

- a narrow subset of `bugprone-*`, `performance-*`, and `modernize-*`;
- selected `clang-analyzer-optin.*` checks after flags-style enum noise is
  handled;
- `clang-analyzer-deadcode.*` after third-party header diagnostics are filtered
  or otherwise isolated;
- no broad `readability-*` family until the signal/noise level is known.

Possible later additions:

- `clang-format` as a separate formatting baseline.
- `cppcheck` if it finds issues that clang-tidy misses in this codebase.
- Include-what-you-use only after include boundaries are stable enough to make
  its output actionable.

## CI Policy

Keep each lint stage separately callable and separately gated:

- Python lint is already cheap enough for every PR.
- C/C++ lint runs in PR CI through the default `./run-lint-cpp.sh` baseline.
- Source file length is gated in PR CI through
  `python3 scripts/find-long-files.py --threshold 2000 --fail .`; the check only
  scans C/C++/C#/Python source extensions.
- Keep `--python-bindings` as an opt-in/manual C++ lint mode until its runtime
  cost and nanobind analyzer noise are understood in CI.
- Expensive static analysis can remain scheduled or opt-in.
