# Build system refactor

Дата: 2026-06-07

Статус: основные фазы миграции выполнены для Linux SDK build path. Phase 0-5
доведены до рабочего состояния и проверены полным
`./build-sdk.sh --wheels --no-parallel`: manifest стал source of truth для
порядка пакетов и native extension declarations, Linux/PowerShell
`build-sdk.*` переведены в wrappers на `termin_build.sdk`, bindings stage
генерирует `termin-artifacts.json`, а `setup.py` пакетов с native bindings
читают extensions из manifest через `termin_build.setup_helpers`.
Wheelhouse stage также перенесен в Python orchestrator; `build-sdk-wheels.sh`
оставлен совместимым wrapper. Python package install stage перенесен в
`termin_build.sdk install-packages`; `install-pip-packages.sh` и
`install-pip-packages.ps1` также оставлены совместимыми wrappers.

Ограничение проверки: Windows scripts обновлены статически, но runtime smoke
в текущем Linux окружении не выполнен, потому что `pwsh` отсутствует. Для
этого добавлен CI job `smoke-build-system-windows` на `windows-latest`; CI
запускается на `push`, `pull_request` и вручную через `workflow_dispatch`.

## Цель

Упростить и стабилизировать сборку Termin SDK без большого переписывания
CMake-графа. Текущая форма уже работает, но политика сборки размазана между
Bash, PowerShell, CMake и множеством `setup.py`. Из-за этого платформенные
правки легко расходятся: недавний пример - Windows preflight для submodule'ей
не имел Linux-аналога, и Linux wheel stage упал только на позднем поиске
`_navmesh_native`.

Целевая форма:

- CMake остается единственным producer native targets и SDK install tree.
- Один manifest описывает Python packages, native extensions, feature gates и
  порядок установки.
- Один кроссплатформенный Python orchestrator управляет preflight, CMake
  стадиями, pip install, wheelhouse и проверками SDK.
- `.sh` и `.ps1` остаются совместимыми entrypoints, но становятся тонкими
  wrappers.

## Текущая проблема

### Несколько источников правды

- `scripts/termin-python-packages.sh`
- `scripts/termin-python-packages.ps1`
- `setup.py` в каждом Python-пакете
- CMake targets и install destinations
- Bash/PowerShell preflight submodule'ей
- `termin_build.cmake_ext` эвристики поиска prebuilt bindings

Сейчас эти источники должны совпадать вручную.

### Поздние ошибки

Часть ошибок обнаруживается только в pip stage:

- CMake может не создать optional target.
- `setup.py` все равно объявляет extension.
- `cmake_ext.py` ищет `.so/.pyd` по эвристикам и падает в wheel build.

Правильная ошибка должна появляться до CMake configure или сразу после CMake
install, с указанием feature/submodule/target, который нарушил контракт.

### Дублирование Linux/Windows orchestration

Bash и PowerShell независимо повторяют:

- список пакетов;
- required submodules;
- SDK/Python layout;
- режимы Vulkan/SDL/OpenGL;
- стадии SDK build/install/wheelhouse.

Эта часть должна быть общей.

## Не-цели

- Не переписывать весь CMake-граф за один шаг.
- Не удалять публичные `.sh`/`.ps1` entrypoints до появления совместимого
  orchestrator'а.
- Не пытаться сразу заменить setuptools/PEP 517 backend во всех пакетах.
- Не делать optional feature fallback'и там, где пакет фактически обязателен.

## Целевая архитектура

```text
build-system/
  packages.json              # source of truth for Python package order/extensions

termin-build-tools/termin_build/
  package_manifest.py        # load/validate manifest
  sdk.py                     # orchestrator CLI

scripts/*.sh, *.ps1
  compatibility wrappers

CMake
  builds and installs native artifacts
  emits sdk/termin-artifacts.json through termin_build.sdk write-artifacts
```

## Phases

### Phase 0: document and introduce manifest

Goal: create a shared contract without changing build behavior.

Status 2026-06-07: done. Added `build-system/packages.json` and
`termin_build.package_manifest`.

Tasks:

- Add this plan.
- Add `build-system/packages.json`.
- Add a manifest loader/validator in `termin-build-tools`.
- Validate manifest against current `scripts/termin-python-packages.sh`.
- Validate declared native extensions against package `setup.py` files.

Verification:

- `python3 -m termin_build.package_manifest --repo-root . --check`
- Existing `./build-sdk.sh` behavior unchanged.

### Phase 1: package list source of truth

Goal: stop maintaining independent package order lists.

Status 2026-06-07: done. `scripts/termin-python-packages.sh` and
`scripts/termin-python-packages.ps1` now read `build-system/packages.json`,
while keeping the old exported variable/function names for existing callers.
`install-pip-packages.sh`, `install-pip-packages.ps1`, and
`build-sdk-wheels.sh` delegate to the Python orchestrator, which reads the
same manifest directly.

Tasks:

- Generate or read Bash package order from manifest.
- Generate or read PowerShell package order from manifest.
- Update `install-pip-packages.sh`, `build-sdk-wheels.sh`,
  `install-pip-packages.ps1` to consume the same order.
- Keep old `scripts/termin-python-packages.*` as compatibility shims during
  the transition.

Verification:

- `./install-pip-packages.sh --target <tmpdir>`
- `./build-sdk-wheels.sh --wheel-dir <tmpdir>`
- PowerShell equivalent on Windows.

### Phase 2: build doctor

Goal: move preflight checks into one cross-platform implementation.

Status 2026-06-07: done. Added `termin_build.sdk doctor` profiles for
`sdk`, `sdk-cpp`, `sdk-bindings`, and `cpp-tests`. The full `sdk` profile
checks git, cmake, nanobind, pip, POSIX copy backend, required submodules,
SDK prefix writability, and pip-cache warnings. Linux `build-sdk-cpp.sh`,
`build-sdk-bindings.sh`, and `run-tests-cpp.sh` call the Python doctor.
PowerShell bindings stage also calls the Python doctor. Compatibility
`ensure-thirdparty-submodules` wrappers delegate to the same Python backend.

Tasks:

- Add `python -m termin_build.sdk doctor`.
- Check required tools: git, cmake, Python, nanobind, pip, rsync/copy backend.
- Check required submodules by feature set.
- Check SDK layout and writable paths.
- Check pip cache warning condition and report it as non-fatal.

Verification:

- done: `python3 -m termin_build.sdk doctor --profile sdk --sdk-prefix sdk`
- done: `python3 -m termin_build.sdk doctor --profile sdk-cpp --sdk-prefix sdk`
- done: `python3 -m termin_build.sdk doctor --profile sdk-bindings --sdk-prefix sdk`
- done: `python3 -m termin_build.sdk doctor --profile cpp-tests --vulkan OFF --sdk-prefix sdk`
- done: `build-sdk-bindings.sh` and `.ps1` call doctor before CMake configure.

### Phase 3: artifact manifest

Goal: replace native artifact path guessing with a producer/consumer contract.

Status 2026-06-07: done. Added `termin_build.sdk write-artifacts`, wired it
after Linux and PowerShell bindings CMake install, and taught
`TerminCMakeBuildExt` to prefer `sdk/termin-artifacts.json` when locating a
native extension. Artifact entries record build path, install path, runtime
library dependencies and feature gates. Legacy directory search remains as
fallback for stale or portable SDK layouts.

Tasks:

- After CMake install, produce `sdk/termin-artifacts.json`.
- Record native extension name, CMake target, build path, install path,
  runtime library dependencies and feature gate.
- Teach `TerminCMakeBuildExt` to prefer artifact manifest over directory
  heuristics.
- Keep old heuristics as temporary compatibility fallback, with warning.

Verification:

- done: `termin-navmesh` wheel fails early if `_navmesh_native` target is missing.
- done: `termin-artifacts.json` records `install_path` and `runtime_dependencies`
  for `termin.navmesh._navmesh_native`.
- done: wheel build can run from SDK artifact manifest without scanning unrelated
  directories.

### Phase 4: Python SDK orchestrator

Goal: make `build-sdk.sh` and `build-sdk.ps1` wrappers.

Status 2026-06-07: done for the shared orchestration layer. Added
`termin_build.sdk build`, `install-python`, `install-packages`, `wheels`, and
`verify-sdk`.
`build-sdk.sh` is a thin wrapper. `build-sdk.ps1` is a thin wrapper and keeps
the historical Windows default of skipping wheelhouse unless `--wheels` is
explicitly requested. The orchestrator selects Bash stage scripts on POSIX and
PowerShell stage scripts on Windows. `build-sdk-wheels.sh` now delegates to
the Python `wheels` command; the wheelhouse loop itself is cross-platform
Python code. `install-pip-packages.sh` and `.ps1` now delegate to
`install-packages`; host install remains sequential, while `--target` install
remains one pip invocation to preserve namespace package merge behavior.

Tasks:

- Add `python -m termin_build.sdk build`.
- Implement stages:
  - bindings/CMake;
  - C#;
  - bundled Python runtime;
  - Python package install;
  - wheelhouse;
  - duplicate/stale artifact checks.
- Preserve current CLI flags.
- Move shared behavior out of shell scripts incrementally.

Verification:

- done: `./build-sdk.sh --wheels --no-parallel`
- done: `./build-sdk.sh --no-wheels --no-parallel`
- done: `python3 -m termin_build.sdk --repo-root . build --no-wheels --no-parallel --dry-run`
- done: `python3 -m termin_build.sdk --repo-root . install-python`
- done: `./install-pip-packages.sh --force --target /tmp/termin-sdk-install-python-native`
- done: `python3 -m termin_build.sdk --repo-root . wheels --wheel-dir /tmp/termin-sdk-wheels-orchestrator`
- done: `./build-sdk-wheels.sh --wheel-dir /tmp/termin-sdk-wheels-python-native`
- done: `python3 -m termin_build.sdk --repo-root . verify-sdk`
- done: `PYTHONPATH=termin-build-tools python3 -m pytest termin-build-tools/tests/ -v` (13 tests, including negative `doctor` coverage for missing pip/copy backend, missing required native artifact, Windows `.pyd` artifact layout, and SDK duplicate-library rules)
- done: `./run-tests-python.sh --no-venv termin-build-tools/tests/`
- done: `PYTHONPATH=termin-build-tools python3 -m termin_build.package_manifest --repo-root . --check`
- done: `python3 -m py_compile termin-build-tools/termin_build/sdk.py termin-build-tools/termin_build/setup_helpers.py termin-build-tools/termin_build/package_manifest.py termin-build-tools/termin_build/cmake_ext.py termin-build-tools/tests/test_sdk_orchestrator.py`
- done: `.github/workflows/ci.yml` parses as YAML.
- done: `git diff --check`
- added CI gate: `smoke-build-system-windows` runs manifest validation,
  build-tools tests, and `.\build-sdk.ps1 --no-wheels --no-parallel --dry-run`
  on `windows-latest`; workflow can run on PRs and via `workflow_dispatch`.
- pending external result: next GitHub Actions run must confirm the Windows
  smoke job.

### Phase 5: setup.py simplification

Goal: remove duplicated native extension declarations.

Status 2026-06-07: done for packages currently listed in
`build-system/packages.json`. Added `termin_build.setup_helpers` and migrated
all setup.py files with native bindings to `native_extensions_for_source(_DIR)`.
`termin-display` optional `_platform_native` is now controlled by manifest
metadata plus artifact presence instead of local setup.py search code.

Tasks:

- Add helper around `setup(...)` that reads manifest package entry.
- Replace per-package `BuildExt.module_names` and `Extension(...)` repetition
  gradually.
- Keep package-specific metadata local while extension mapping comes from
  manifest.

Verification:

- done: all wheels still build through `termin_build.sdk wheels`.
- done: bundled SDK install still works through `termin_build.sdk install-python`.
- done: validator accepts helper-backed setup.py files and still validates
  package order/native extension coverage.

## Feature model

Initial feature gates:

- `recast`: required by `termin-navmesh` and `_navmesh_native`.
- `sdl`: controls `termin.display._platform_native`.
- `vulkan`: controls Vulkan-dependent CMake targets and thirdparty VMA.
- `opengl`: currently required for C# native bindings.

Rule: if a package is listed in the required Python package set, its required
features must be present. Optional native extensions may be skipped only when
the package explicitly declares them optional.

## Current risks

- Windows layout differs intentionally (`sdk/python/Lib` vs Linux
  `sdk/lib/pythonX.Y`), so path normalization must remain explicit.
- C# and Android SDK layouts have legitimate duplicate native libraries; SDK
  duplicate checks must keep these exceptions narrow.
- Windows runtime verification still needs to run on an actual Windows host or
  CI worker. Current Linux environment has no `pwsh`; CI now contains a
  dedicated `windows-latest` smoke job for this.
