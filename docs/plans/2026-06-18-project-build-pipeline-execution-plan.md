# Project Build Pipeline Execution Plan

Date: 2026-06-18

Status: active execution plan

Primary architecture reference:

- `docs/plans/2026-06-17-build-system-target-architecture.md`

Related context:

- `docs/analysis/2026-06-17-build-runtime-system-audit.md`
- `docs/plans/2026-06-07-build-system-refactor.md`
- `docs/plans/2026-05-20-termin-runtime-package-loader.md`
- `docs/plans/2026-05-20-android-scene-build-export.md`
- `docs/plans/2026-05-20-quest-openxr-foundation.md`

Related Kanboard tasks:

- #27-#33 - desktop standalone runtime bundle
- #39 - include policy for dynamic resources
- #40 - asset runtime split
- #41 - profile target dispatch for `android`/`quest_openxr`

## Goal Statement

Implement a unified Termin project build pipeline for desktop, Android and
Quest/OpenXR:

```text
BuildContext + structured diagnostics + project/target preflight
  -> runtime package export
  -> runtime package validation
  -> target packaging
```

The goal is not to finish every future feature. The goal is to make the build
system shape explicit enough that future target, capability, resource and
runtime contract work lands in clear modules instead of accumulating in ad-hoc
wrappers.

Recommended Codex goal prompt:

```text
Execute docs/plans/2026-06-18-project-build-pipeline-execution-plan.md:
bring Termin project build to a unified preflight/analyze/export/validate/package
pipeline for desktop, Android and Quest/OpenXR, with tests, documentation and
Kanboard updates after each completed phase.
```

## Scope

In scope:

- Python `termin.project_build` project build layer.
- Build profile loading and dispatch.
- Desktop, Android and Quest/OpenXR project build wrappers.
- Runtime package export/validation integration.
- Structured diagnostics for project build failures.
- Focused tests for every behavior change.
- Documentation and Kanboard updates after each phase.

Out of scope:

- Full CMake/SDK build graph rewrite.
- Deep runtime loader rewrite.
- Android Python gameplay runtime.
- Release-grade dependency solving.
- Removing legacy project-copy build paths before their call sites are mapped.

## Current Baseline

As of 2026-06-18:

- `build_profiles.json` schema is versioned with `version: 1`.
- Runtime package validation exists as
  `termin.project_build.runtime_package_validator.validate_runtime_package`.
- Desktop, Android and Quest/OpenXR wrappers run runtime package validation
  after `export_runtime_package(...)`.
- Android and Quest/OpenXR wrappers use `target_build_common` for shared target
  helper behavior.
- Android and Quest/OpenXR target preflight exists in
  `termin.project_build.target_preflight`.
- Shared project-context preflight exists for desktop, Android and Quest/OpenXR:
  project root, entry scene containment/existence and output directory safety.
- Quest/OpenXR preflight checks Android SDK root, ABI lib dir and OpenXR CMake
  package.
- Architecture status is tracked in
  `2026-06-17-build-system-target-architecture.md`.

Known remaining shape problems:

- Wrappers still own most pipeline sequencing.
- Diagnostics reuse `RuntimePackageExportDiagnostic` outside runtime package
  export.
- Profile backend dispatches directly to wrappers instead of producing a single
  normalized build request/context.
- SDK capability checks are still mostly filesystem checks.
- Legacy `termin.project_builder` broad-copy path is not fully isolated from
  packaged build terminology.

## Target Module Shape

Short-term target under `termin-app/termin/project_build/`:

```text
diagnostics.py             # shared BuildDiagnostic and formatting
build_context.py           # BuildContext / normalized request
target_preflight.py        # project and target environment preflight
runtime_package_exporter.py
runtime_package_validator.py
pipeline.py                # preflight -> export -> validate -> package
desktop_build.py           # desktop target packager
android_build.py           # Android target packager
quest_openxr_build.py      # Quest/OpenXR target packager
profile_build.py           # profile -> normalized request -> pipeline
```

Long-term ownership may move out of `termin-app`, but this execution plan keeps
the implementation in the current Python package until the pipeline is stable.

## Execution Phases

### Phase 1: Build Diagnostics

Objective:

- Stop using `RuntimePackageExportDiagnostic` as the generic build diagnostic
  type.

Steps:

- Add `termin.project_build.diagnostics.BuildDiagnostic`.
- Provide helpers for error/warning creation and formatting.
- Keep conversion compatibility with existing export diagnostics.
- Update `TargetPreflightError` to carry `BuildDiagnostic`.
- Update tests to assert generic diagnostics where appropriate.

Acceptance:

- Preflight diagnostics no longer import from `runtime_package_exporter`.
- Exporter can still return its current diagnostics until later cleanup.
- Existing result objects remain source-compatible where feasible.

Tests:

```bash
.venv/bin/python -m pytest termin-app/tests/test_project_build_target_preflight.py -q
.venv/bin/python -m pytest termin-app/tests/test_runtime_package_exporter.py -q
```

### Phase 2: BuildContext And Normalized Request

Objective:

- Introduce one normalized object that describes a project build before target
  packaging starts.

Steps:

- Add `build_context.py`.
- Define `BuildContext` with:
  - project root;
  - project name;
  - target;
  - entry scene;
  - output/dist dir;
  - package dir;
  - logs dir;
  - target options.
- Move shared project-context preflight to produce or validate this context.
- Keep wrapper public APIs stable while internally constructing `BuildContext`.

Acceptance:

- Desktop, Android and Quest/OpenXR wrappers use the same context shape.
- Entry scene and output path logic is not duplicated across wrappers.
- Existing wrapper tests still pass.

Tests:

```bash
.venv/bin/python -m pytest termin-app/tests/test_project_build_target_preflight.py -q
.venv/bin/python -m pytest termin-app/tests/test_runtime_package_exporter.py -q
```

### Phase 3: Profile Backend Normalization

Objective:

- Make profiles produce a normalized build request/context instead of directly
  spreading target-specific keyword arguments.

Steps:

- Split profile parsing from build execution.
- Add normalized profile request tests for desktop, Android and Quest/OpenXR.
- Validate target options before wrapper invocation:
  - unknown target;
  - missing entry scene;
  - unsafe output;
  - unsupported target option blocks.
- Preserve CLI behavior.

Acceptance:

- `profile_build.py` has one obvious path from profile to build context.
- Target-specific options are explicit and tested.
- Invalid profile failures are structured and deterministic.

Tests:

```bash
.venv/bin/python -m pytest termin-app/tests/test_project_build_profile_backend.py -q
.venv/bin/python -m pytest termin-app/tests/test_project_build_target_preflight.py -q
```

### Phase 4: Pipeline Orchestrator

Objective:

- Move sequencing out of target wrappers:

```text
preflight -> export runtime package -> validate runtime package -> package target
```

Steps:

- Add `pipeline.py`.
- Define target packager protocol or lightweight callable contract.
- Convert desktop wrapper first, then Android, then Quest/OpenXR.
- Keep public `build_desktop_project`, `build_android_project` and
  `build_quest_openxr_project` APIs as compatibility entry points.

Acceptance:

- Runtime package export and validation are called from one pipeline path.
- Target wrappers/package functions no longer decide pipeline phase ordering.
- Tests prove all three targets still package from the same runtime package
  contract.

Tests:

```bash
.venv/bin/python -m pytest termin-app/tests/test_runtime_package_exporter.py -q
.venv/bin/python -m pytest termin-app/tests/test_project_build_profile_backend.py -q
```

### Phase 5: SDK Capability Layer

Objective:

- Replace scattered filesystem guesses with a Python-readable SDK capability
  model.

Steps:

- Define initial `SDKCapabilities` model.
- Add loader that can read a manifest if present and synthesize conservative
  capabilities from the current SDK layout if not present.
- Cover:
  - shader compiler;
  - desktop player/runtime files;
  - Python runtime availability;
  - Android SDK root/ABI;
  - OpenXR CMake package.
- Route Android/Quest SDK checks through capabilities.

Acceptance:

- Target preflight asks capabilities questions instead of open-coding every file.
- Missing SDK/OpenXR/Python runtime failures remain explicit.
- Capability manifest format is documented.

Tests:

```bash
.venv/bin/python -m pytest termin-app/tests/test_project_build_target_preflight.py -q
.venv/bin/python -m pytest termin-app/tests/test_runtime_package_exporter.py -q
```

### Phase 6: Runtime Package Contract Hardening

Objective:

- Strengthen validation of packaged output before target packaging.

Steps:

- Extend runtime package validator with:
  - material phase references;
  - shader/material/pipeline compatibility;
  - scene resource references;
  - target capability requirements.
- Add tests with intentionally broken package manifests/specs.
- Decide whether runtime loader should run defensive validation or consume a
  generated validation report.

Acceptance:

- Missing package resources fail before APK/bundle packaging.
- Shader artifact/material graph issues are structured diagnostics.
- Desktop/Android/Quest still share the same package contract.

Tests:

```bash
.venv/bin/python -m pytest termin-app/tests/test_runtime_package_validator.py -q
.venv/bin/python -m pytest termin-app/tests/test_runtime_package_exporter.py -q
```

### Phase 7: Legacy Build Path Isolation

Objective:

- Make the old broad-copy project build path clearly legacy/dev-only.

Steps:

- Audit imports and CLI/editor call sites for `termin.project_builder`.
- Decide whether to rename it to `dev_export`, document it, or remove unused
  paths.
- Ensure packaged build commands route through the new pipeline.
- Update CLI docs.

Acceptance:

- `termin build` packaged targets no longer depend on broad-copy semantics.
- Legacy/dev path is named and documented if still needed.
- Tests cover target dispatch and CLI-visible behavior.

Tests:

```bash
.venv/bin/python -m pytest termin-app/tests/test_project_build_profile_backend.py -q
.venv/bin/python -m pytest termin-app/tests/test_runtime_package_exporter.py -q
```

## Validation Matrix

Run focused tests after each phase:

```bash
.venv/bin/python -m pytest \
  termin-app/tests/test_project_build_target_common.py \
  termin-app/tests/test_project_build_target_preflight.py \
  termin-app/tests/test_runtime_package_exporter.py \
  termin-app/tests/test_runtime_package_validator.py \
  termin-app/tests/test_project_build_profile_backend.py \
  -q
```

Run full Python tests before marking the goal complete:

```bash
./run-tests.sh
```

If bindings or SDK artifacts change, follow repository instructions:

```bash
./build-sdk.sh --no-wheels
./setup-test-venv.sh --force
./run-tests.sh
```

## Progress Tracking

Update this checklist as phases land.

- [ ] Phase 1: shared build diagnostics
- [ ] Phase 2: BuildContext and normalized request
- [ ] Phase 3: profile backend normalization
- [ ] Phase 4: pipeline orchestrator
- [ ] Phase 5: SDK capability layer
- [ ] Phase 6: runtime package contract hardening
- [ ] Phase 7: legacy build path isolation
- [ ] Documentation and Kanboard reflect final state

## Risks And Decisions

Diagnostics:

- Decision needed: keep a compatibility alias for `RuntimePackageExportDiagnostic`
  or migrate tests and result types to `BuildDiagnostic` in one larger step.

Pipeline migration:

- Move one target at a time. Desktop is the safest first target because it has
  runtime package, Python packaging and runtime bundle steps in one place.

SDK capabilities:

- Do not over-design the manifest up front. Start with fields required by
  existing preflight checks and let tests drive expansion.

Legacy path:

- Do not remove `termin.project_builder` until CLI/editor references are mapped.
  First make it explicit whether it is dev export, old play-mode artifact or
  unused code.

## Definition Of Done

The goal is complete when:

- Desktop, Android and Quest/OpenXR builds go through one explicit pipeline
  shape.
- Build context and target preflight are shared across targets.
- Structured diagnostics cover profile/context/environment failures.
- Runtime package export and validation are shared pipeline phases.
- Profile backend normalizes profile data before build execution.
- SDK capability checks have a documented initial model.
- Legacy broad-copy build path is isolated or clearly documented.
- Focused tests and full `./run-tests.sh` pass, or any remaining failures are
  documented with concrete blockers.
- `docs/plans/2026-06-17-build-system-target-architecture.md`, this execution
  plan and Kanboard tasks reflect the final state.
