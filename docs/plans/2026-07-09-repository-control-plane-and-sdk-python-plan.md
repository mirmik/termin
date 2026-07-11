# Repository control plane and SDK-backed Python test environment

Date: 2026-07-09.

## Status and scope

This plan turns the findings from
[the repository control-plane audit](../analysis/2026-07-09-repository-control-plane-audit.md)
into one migration direction for repository metadata, tests, CI, SDK Python
development, policy gates, and published documentation.

The immediate risks are false-green repository checks and duplicated Python
environments. The goal is not a universal test runner or one oversized manifest.
The goal is a small repository control plane that derives executable plans from
shared declarative inventories and fails closed when repository-owned content is
not classified.

Existing tracking:

- Kanboard #141: `[sdk/python] Сделать SDK dev/test Python environment`;
- Kanboard #262: `[qa/ci] Make Python test discovery manifest-driven`;
- Kanboard #263: `[repo/qa] Build manifest-driven repository control plane`
  (umbrella for this plan).

## Current state

### Repository inventories disagree

- `build-system/packages.json` contains the canonical order and native-extension
  mapping for 53 Python distributions.
- `run-tests-python.sh` contains a separate manual list of roughly 20 pytest
  roots.
- `./run-tests.sh --full` changes marker and editor-smoke selection but does not
  discover additional Python test roots.
- GitHub Actions contains different manual pytest lists and therefore does not
  close the local runner's coverage gap.
- CTest is the correct source of concrete native test registrations, but native
  tests have no consistent module/tier/capability labels and a module omitted
  from the top-level CMake graph can still disappear silently.
- The Pages workflow publishes a manually maintained subset of module-local
  documentation.

This is fail-open behavior: adding a test or document does not necessarily add
it to a repository gate.

### Python runtime and test environments are duplicated

`./build-sdk.sh` installs a bundled Python runtime, runtime dependencies, Termin
packages, and native bindings into the SDK. `./setup-test-venv.sh` then creates a
second environment, installs runtime and test dependencies again, and performs
editable installs of all Termin packages.

Consequences:

- rebuilt bindings require an additional `setup-test-venv --force` synchronization;
- local tests and editor/player can observe different Python installations;
- an editable test run does not prove that installed SDK packages work;
- runtime requirements and test tools are not represented as separate dependency
  sets;
- local setup and CI repeat dependency knowledge in shell/YAML.

The SDK already bundles the Python stdlib and `site-packages`. Windows also gets
`sdk/python/python.exe`; Linux currently bundles the stdlib and `libpython` but
does not expose an equivalent standalone SDK Python CLI.

### SDK Python construction is not yet hermetic

The investigation in
[SDK Python host environment leakage](../analysis/2026-06-08-sdk-python-host-environment-leakage.md)
remains relevant. SDK population still uses the host interpreter and can inspect
or copy packages from host `site-packages`. A fresh Linux build on 2026-07-09
reported resolver conflicts against unrelated host tools including `aider-chat`,
`open-interpreter`, and `simple-lama-inpainting`. Making the SDK the base of all
tests must not make host leakage the base of all tests too.

The same verification found that `pip --target --force-reinstall` leaves files
removed by a newer distribution version in place. SDK target refresh now removes
files owned by the previous wheel `RECORD` before reinstalling, with path-escape
protection and regression tests. This closes stale-file replacement for known
distributions; it does not replace the remaining hermetic population work.

### A declared repository policy is currently red

The source-size CI command fails on the current tree. A permanently failing or
non-required gate is not useful evidence. Repository policy checks need explicit,
reviewable exceptions or a clean zero baseline.

## Design principles

1. **One identity catalog, several focused manifests.** Module identity is
   shared, while Python packaging, test suites, documentation, and policy
   exceptions remain separate schemas.
2. **One planner, specialized executors.** Pytest, CTest, editor processes, and
   device/manual gates remain different executors. The planner only classifies,
   selects, validates, and reports them consistently.
3. **Fail closed.** Repository-owned tests and public docs must be classified or
   explicitly excluded with a reason.
4. **SDK is an artifact; overlays are developer state.** Editable paths and
   test-only packages must not mutate the distributable SDK contract.
5. **Source and installed modes prove different things.** Fast source-overlay
   tests do not replace tests against installed SDK packages.
6. **Correctness before selection optimization.** Change-based test selection,
   sharding, and caching come only after the full inventory is trustworthy.
7. **Local scripts and CI consume the same plan.** Workflow YAML must not contain
   a second list of suites.

## Target architecture

```text
build-system/modules.json
        |
        +-- build-system/packages.json
        +-- build-system/test-suites.json
        +-- docs publication metadata
        +-- repository policy exceptions
                         |
                    repo planner
                  /      |       \
             local CLI   CI    repo doctor
                  |       |       |
             pytest / CTest / editor / device executors

SDK bundled Python runtime
        +-- installed runtime packages and native artifacts
        +-- cross-platform termin-python launcher
        +-- SDK artifact/capability manifests
                         |
                checkout-local overlays
                +-- source mapping
                +-- pytest/ruff/test extras
                +-- SDK fingerprint and Python ABI
```

### Module catalog

Add `build-system/modules.json` as the machine-readable identity catalog for
repository modules, including modules that are C/C++-only or documentation-only.
It should not replace `packages.json`.

Minimum module fields:

```json
{
  "id": "termin-render",
  "path": "termin-render",
  "kinds": ["cmake", "python"],
  "python_distribution": "termin-render",
  "docs": {"root": "termin-render/docs", "visibility": "public"}
}
```

Validation must reject duplicate ids/paths, missing roots, unknown distribution
references, and public docs roots that have no publication policy.

### Test suite manifest

Add `build-system/test-suites.json`. A suite is a scheduling and environment
unit, not necessarily one test file.

Minimum fields:

- stable suite id and owning module id;
- executor (`pytest`, `ctest`, `process-smoke`, `device`, or `manual`);
- roots or executor selector;
- profiles/tiers;
- required SDK capabilities and native artifacts;
- supported platforms/backends;
- environment profile;
- isolation, timeout, and optional sharding metadata;
- an explicit reason for any non-automatic classification.

Concrete native test names remain owned by CMake. Native tests should receive
consistent CTest labels for module, tier, backend, and window/device requirements.
The repository doctor consumes CTest JSON and verifies it against module/test
metadata instead of duplicating each `add_test()` in JSON.

### Test profiles

Replace the ambiguous boolean meaning of `working/full` with named profiles:

- `check`: schemas, orphan detection, lint, and architecture/policy gates;
- `pr`: deterministic headless suites for the primary CI platform;
- `linux-full`: all automatic Linux suites;
- `windows-d3d11`: Windows and D3D11-specific suites;
- `editor-smoke`: isolated editor-process tests;
- `device-android` and `device-quest`: build/deploy/runtime device gates;
- `manual`: explicitly recorded human gates.

No single machine is expected to execute a universal `full` profile. Completeness
is the union of declared profiles, and the planner must be able to report that
union without executing it.

### Planner and execution report

Implement the planner in `termin-build-tools`, alongside the existing SDK
orchestrator and package manifest support. The exact module name may be chosen
during implementation; the public operations should cover:

```text
check                 validate schemas and find orphaned content
list                  list modules, suites, profiles, and requirements
plan PROFILE          emit the suites selected for a concrete environment
run PROFILE           execute or dispatch the plan locally
report                write/read the execution manifest
```

The planner should emit stable JSON suitable for a GitHub Actions matrix. Every
CI run should preserve an execution manifest containing selected, executed,
skipped/inapplicable, and failed suites with reasons. A green job without a
known executed inventory is insufficient evidence.

## SDK-backed Python environments

### Roles

Keep the following roles distinct:

1. **Bootstrap host Python** starts the SDK orchestrator only.
2. **Isolated build environment** provides pip/build/nanobind tooling and must not
   read global or user `site-packages`.
3. **Bundled SDK Python runtime** contains the reproducible runtime stdlib,
   dependencies, installed Termin packages, and native bindings.
4. **Checkout-local dev/test overlay** contains only source mapping, test tools,
   test extras, and metadata binding it to a specific SDK build.

### SDK Python launcher

Expose a cross-platform SDK command such as `sdk/bin/termin-python` or
`sdk/bin/termin python`.

- On Windows it should use the existing bundled `sdk/python/python.exe` runtime.
- On Linux it should launch the bundled stdlib and `libpython` with SDK-relative
  paths and no dependency on the user's active environment.
- It must clear or deliberately control `PYTHONHOME`, `PYTHONPATH`, user-site,
  and library search paths.
- It should report SDK root, Python ABI, runtime manifest, and active overlay for
  diagnostics.

Prefer a native, SDK-relative launcher over platform shell wrappers. Embedded
Python configuration should use the modern `PyConfig` API when the launcher is
implemented or adjacent existing hosts are touched.

### Hermetic SDK population

Before the SDK becomes the test base:

- create/use an isolated build environment for SDK Python population;
- stop copying external packages from host `site-packages`;
- resolve runtime packages from explicit requirements plus constraints/lock;
- move toward a controlled wheelhouse and offline installation;
- make Linux and Windows package population use the same logical pipeline;
- record Python ABI, inputs, installed distributions, and hashes in an SDK Python
  runtime manifest;
- add a doctor gate rejecting undeclared distributions in bundled
  `site-packages`.

### Checkout-local overlay

The overlay should live under a disposable build-state path such as
`build/python-envs/test`, not in the distributable SDK and not as a second
independent root `.venv`.

It contains:

- pytest, Ruff, and profile-specific test-only dependencies;
- a generated source mapping derived from package/module metadata;
- a reference to `sdk/termin-artifacts.json` for native extension resolution;
- the SDK fingerprint and Python ABI it was created against.

The source overlay must have explicit precedence over installed SDK Python
sources, while native modules resolve from the matching SDK artifact manifest.
Do not rely on ambient `PYTHONPATH` ordering. Do not copy native extensions into
source package directories as the steady-state synchronization mechanism.

The implementation may use a small generated import finder, path configuration,
or another explicit overlay mechanism. It must have tests for regular packages,
shared `termin.*` namespaces, native submodules, Windows file locking, stale SDK
fingerprints, and multiple checkouts sharing one installed SDK.

### Two required Python execution modes

`sdk-source-overlay` is the normal development mode:

- Python sources come from the checkout;
- native extensions and runtime dependencies come from the SDK;
- source edits are visible without reinstalling Termin packages;
- rebuilt bindings become visible after the normal SDK build, without a second
  editable-install synchronization pass.

`sdk-installed` is the SDK acceptance mode:

- no checkout source overlay is active;
- imports come only from installed SDK packages;
- tests prove that the SDK consumed by editor/player is coherent and
  self-contained;
- source-tree leakage is an error.

Both modes are required. Passing source-overlay tests does not prove packaging,
and passing installed-mode smoke tests does not provide a productive edit/test
loop.

## CI, documentation, and policy integration

### CI

GitHub Actions should:

1. validate manifests and generate a JSON execution matrix;
2. build or download the required SDK artifact;
3. create the declared overlay/environment profile;
4. execute planner-selected suites without roots embedded in YAML;
5. upload JUnit, logs, and the execution manifest.

CI path filters may be generated from the module catalog. Change-based suite
selection is a later optimization and must always have a safe, explicit fallback
to a declared complete profile.

### Documentation

Use module docs metadata to generate or validate MkDocs navigation, publication
roots, and workflow triggers. The docs gate should fail when a public module docs
root is not published, or when a docs root is neither public nor explicitly
internal.

### Repository policies

Policy checks such as source-size limits remain separate from test suites but are
selected by the `check` profile. Exceptions, if truly needed, must include file,
owner/module, reason, limit, and review/expiry date. The preferred initial state
for the current source-size gate is to split the four current offenders and
return to a zero-exception baseline.

## Migration phases

### Phase 0: Restore honest signals

- Fix the current source-size gate or add tightly scoped temporary exceptions.
- Stop describing the current Python `--full` run as repository-complete.
- Preserve the audit and current omitted-suite inventory as migration fixtures.

Close when declared required gates pass on the main branch and their names match
their real coverage.

### Phase 1: Catalog and read-only planner

Foundation status, 2026-07-09: implemented under Kanboard #268. The repository
now has `build-system/modules.json` for non-Python module identities while
deriving Python-backed identities from canonical `packages.json`, an initial
`build-system/test-suites.json`, and `termin_build.repository_control`
`check`/`list`/`plan` operations with stable JSON output. Cross-manifest module,
profile, executor, platform, root-path, and filesystem references are validated.
Suite population and orphan-test enforcement remain the separate #262 stream.

Python inventory status, 2026-07-09: #262 now declares 46 pytest suites owning
all 212 repository test files matching `test_*.py` or `*_test.py`. Discovery
exclusions and executor defaults are manifest data. `check` fails on orphaned or
multiply-owned tests. Linux and PowerShell runners obtain their default suite
plans from `termin_build.repository_control`; the old root lists were deleted.
The Linux full profile, import smoke, and Ruff pass. Inventory expansion exposed
and fixed binding, dependency, packaging, and test-contract defects, including
an editable namespace collision between `termin-tween` and
`termin-components-tween`. PowerShell parser/runtime verification remains
required on Windows before #262 can close.

- Add module and test-suite schemas.
- Populate the initial module catalog from current package, CMake, and docs data.
- Implement `check`, `list`, and `plan` without changing existing runners.
- Add orphan Python test detection.
- Add unit tests for invalid references, profiles, platforms, and exclusions.

Close when every repository-owned Python test file is classified and adding an
unclassified test fails the check profile.

### Phase 2: Hermetic SDK Python foundation

Linux implementation status, 2026-07-09: #141 now provides a native
SDK-relative `termin_python` launcher based on `PyConfig`, hostile-environment
verification in the SDK doctor, and a bundled `libpython` restoration step after
bindings staging. Runtime and build dependencies now have separate exact locks.
A disposable pinned build environment materializes external and Termin wheels;
SDK population then runs offline with `--no-index --no-deps`. The generated
`sdk/python-runtime-manifest.json` records ABI, lock hash, distributions and
RECORD hashes, and the SDK doctor rejects undeclared, missing or modified
payload. Linux offline population and installed import smoke pass. Windows
launcher/population acceptance remains to be run on Windows.

- Isolate SDK Python population from host packages.
- Introduce runtime constraints/lock and installed-distribution manifest.
- Add the cross-platform SDK Python launcher.
- Add doctor checks for Python ABI, runtime paths, and undeclared packages.

Close when the SDK Python launcher runs an installed-package import smoke on
Linux and Windows from a clean environment.

### Phase 3: Source overlay and test tooling

Linux implementation status, 2026-07-09: the test runner now uses
`build/python-envs/test` with pinned test-only dependencies and a generated,
fingerprinted source overlay. Exact source mappings take precedence for `.py`
modules while package search paths prefer installed SDK directories for native
extensions. `run-tests-python.sh`, repository-control child runs, and Ruff use
the same launcher arguments. The old setup entry point is now only a wrapper.
PowerShell runtime acceptance and removal of legacy native copies from existing
developer checkouts remain before the old workflow can be deleted.

- Implement checkout-local overlay creation/synchronization.
- Separate runtime, build, lint, and test dependency profiles.
- Add `sdk-source-overlay` and `sdk-installed` test environments.
- Preserve and improve Windows native-lock diagnostics.
- Migrate `run-tests-python.*` to use the SDK launcher and overlay.
- Remove the need to reinstall all Termin packages after binding rebuilds.

Close when Python source edits and rebuilt bindings are both picked up by the
intended paths, and installed-mode tests reject checkout leakage.

### Phase 4: Native/process inventories and local runner

Initial native inventory status, 2026-07-10: `test-suites.json` now owns every
repository-native C/C++ test translation unit and its CTest module suite.
Configured CTest registrations receive stable `termin:module`, `termin:tier`,
and `termin:capability` labels. `termin_build.repository_control check-ctest`
validates CTest JSON plus `compile_commands.json`; an unclassified source that
does not reach the configured CMake graph is an error. Sources conditional on
windowing, D3D11, or Python bindings have explicit profile/capability/reason
classifications, so a headless PR configuration may omit only declared
inapplicable sources. `run-tests-cpp.sh` runs this gate after configuring CMake.
The Linux `pr` and `linux-full` configurations have passed the inventory gate.
Graphics, display, render-pass, and Python-binding CTest registrations carry
their specific backend/window capability labels in addition to the common
module/tier labels. The two editor reload smokes are now declared
`process-smoke` suites and `run-tests.sh --full` dispatches them through the
planner rather than carrying a second script list. Android, Quest/OpenXR, and
manual smoke procedures are explicitly classified with requirements and
reasons; device/manual dispatch remains intentionally unsupported by the local
automatic runner until it can report real deployment and human-verification
results. run-tests-cpp.sh now asks the planner for a concrete CTest
registration selection, executes only that selection, and writes a JSON
execution manifest with selected/executed/skipped/failed registrations from
CTest JUnit output. Windows CTest-profile acceptance and device runtime
executors remain before this phase can close.

- Add consistent CTest labels and CTest JSON validation.
- Detect native test sources/modules omitted from the top-level CMake graph.
- Classify editor-process, device, and manual gates.
- Make `run-tests.*` thin compatibility entry points over named planner profiles,
  then retire obsolete flags rather than maintaining two policy models.

Close when the planner can report the complete cross-platform suite union and
local profiles execute only their declared inventories.

### Phase 5: CI consumes the planner

Initial Linux PR migration status, 2026-07-11: CI has a dedicated planner job
that validates manifests and publishes the pr/Linux plan JSON. The C++ and
Python test jobs download that artifact and pass it to planner-backed runners.
CTest uploads its selection, JUnit, and execution manifest; the Python runner
writes the corresponding suite execution manifest.
The verify-pr-linux-plan job consumes both manifests and fails if the PR plan
has an unaccounted Python suite or native module, or if either executor reports
a failed entry. Execution verification is fail-closed on schema, profile, and
platform identity and rejects suites/modules not present in the planner
artifact, preventing stale or cross-profile reports from satisfying coverage.
The termin-app installed-bundle acceptance is also declared as a separate
sdk-installed process-smoke suite, preserving its distinct import contract
without a pytest root list in workflow YAML. Process-smoke jobs verify their
selected/executed/failed suite manifest against the exact planner artifact
before publishing it, using the same fail-closed identity contract.
The focused D3D11 Windows smoke is likewise a declared Windows process-smoke
suite; CI consumes its Windows plan artifact and publishes a suite execution
manifest. Runtime acceptance still depends on the Windows runner.

- Generate CI matrices from planner JSON.
- Remove pytest/CTest root lists from workflow YAML.
- Store execution manifests and test reports as artifacts.
- Add both source-overlay suites and installed-SDK acceptance smoke.

Close when local and CI selection for the same profile is identical and verified
by tests.

### Phase 6: Docs and broader repository doctor

- Generate/validate docs publication from module metadata.
- Add orphan docs and broken-link gates.
- Consolidate package, suite, docs, and policy validation under the check profile.
- Only then consider affected-test selection, sharding, and result caching.

## Compatibility and deletion policy

This repository is under active development. Avoid indefinite compatibility
fallbacks:

- existing shell/PowerShell entry points may remain temporarily as thin wrappers;
- old hardcoded suite lists must be deleted when planner-backed equivalents land;
- root `.venv`, editable native copies, and `setup-test-venv.*` should be removed
  once the SDK overlay workflow satisfies Linux and Windows acceptance;
- stale overlays must fail with an actionable SDK fingerprint diagnostic rather
  than silently rebuilding against a different ABI;
- manifest exclusions without a current reason are schema errors.

## Risks and mitigations

### Source overlay shadows native packages incorrectly

Shared `termin.*` package roots and regular packages can behave differently under
plain path injection. Use an explicit, tested mapping and resolve native modules
through the SDK artifact manifest.

### Tests pass only because checkout files leak into installed mode

Installed mode must sanitize import paths and assert the resolved origins of a
representative package/native-extension matrix.

### SDK Python becomes mutable developer state

Install test-only tools and editable metadata only into the checkout overlay.
Treat SDK runtime manifests and site-packages as build products.

### One manifest becomes a new monolith

Keep identity, packaging, suites, and policies in focused schemas joined by
stable module ids. Generate views instead of copying lists.

### Migration makes the default run prohibitively slow

Profiles remain explicit scheduling units. First guarantee classification and
completeness; then measure and shard. Do not hide slow suites by leaving them
unclassified.

## Acceptance criteria

The migration is complete when:

- every repository-owned automatic test belongs to a declared suite and profile;
- every non-automatic test/gate has an explicit classification and reason;
- local and CI runs consume the same planner output;
- CI artifacts state exactly what was and was not executed;
- `./build-sdk.sh --no-wheels` produces a hermetic SDK Python runtime and launcher;
- source-overlay tests need no second installation of Termin runtime packages;
- rebuilt native bindings need no `setup-test-venv --force` synchronization;
- installed-SDK acceptance tests run without checkout source leakage;
- the root `.venv` and `setup-test-venv.*` workflow are retired;
- public module docs are published from catalog metadata;
- required policy gates are green and have no unexplained exceptions.

## Tracking decomposition

Use one umbrella card for this plan. Keep the following as separate, closeable
work streams:

- #268: repository module catalog and read-only planner;
- #262: Python suite inventory and orphan-test gate;
- #141: hermetic SDK Python runtime, launcher, and checkout overlay;
- #264: CTest/process/device inventory and profile classification;
- #265: planner-driven CI and execution reports;
- #266: manifest-driven docs publication and orphan-doc checks;
- #267: restoration of honest repository policy gates.

The umbrella should remain in Backlog until the first implementation stream is
taken. Child cards should move independently and close as soon as their own
acceptance criteria pass.
