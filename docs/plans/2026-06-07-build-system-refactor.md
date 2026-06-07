# Build system refactor

Дата: 2026-06-07

Статус: начато. Phase 0 выполнена: добавлен первый машинно-читаемый manifest
Python-пакетов и валидатор. Phase 1 начата: совместимые Bash/PowerShell
package-list shim'ы читают порядок пакетов из manifest.

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
  sdk.py                     # future orchestrator CLI

scripts/*.sh, *.ps1
  compatibility wrappers

CMake
  builds and installs native artifacts
  future: emits sdk/termin-artifacts.json
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

Status 2026-06-07: started. `scripts/termin-python-packages.sh` and
`scripts/termin-python-packages.ps1` now read `build-system/packages.json`,
while keeping the old exported variable/function names for existing callers.

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

Tasks:

- Add `python -m termin_build.sdk doctor`.
- Check required tools: git, cmake, Python, nanobind, pip, rsync/copy backend.
- Check required submodules by feature set.
- Check SDK layout and writable paths.
- Check pip cache warning condition and report it as non-fatal.

Verification:

- `python3 -m termin_build.sdk doctor --profile sdk`
- `build-sdk-bindings.sh` and `.ps1` call doctor before CMake configure.

### Phase 3: artifact manifest

Goal: replace native artifact path guessing with a producer/consumer contract.

Tasks:

- After CMake install, produce `sdk/termin-artifacts.json`.
- Record native extension name, CMake target, build path, install path,
  runtime library dependencies and feature gate.
- Teach `TerminCMakeBuildExt` to prefer artifact manifest over directory
  heuristics.
- Keep old heuristics as temporary compatibility fallback, with warning.

Verification:

- `termin-navmesh` wheel fails early if `_navmesh_native` target is missing.
- Wheel build can run from SDK artifact manifest without scanning unrelated
  directories.

### Phase 4: Python SDK orchestrator

Goal: make `build-sdk.sh` and `build-sdk.ps1` wrappers.

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

- `./build-sdk.sh --no-wheels`
- `./build-sdk.ps1 -NoWheels` or equivalent final spelling
- CI matrix for Linux and Windows.

### Phase 5: setup.py simplification

Goal: remove duplicated native extension declarations.

Tasks:

- Add helper around `setup(...)` that reads manifest package entry.
- Replace per-package `BuildExt.module_names` and `Extension(...)` repetition
  gradually.
- Keep package-specific metadata local while extension mapping comes from
  manifest.

Verification:

- All wheels still build.
- Validator rejects a manifest/setup mismatch.

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

- The manifest can drift if it is not wired into scripts soon.
- `setup.py` files contain dynamic logic such as optional `_platform_native`;
  the validator must understand optional entries before it becomes strict.
- Windows layout differs intentionally (`sdk/python/Lib` vs Linux
  `sdk/lib/pythonX.Y`), so path normalization must remain explicit.
- C# and Android SDK layouts have legitimate duplicate native libraries; SDK
  duplicate checks must keep these exceptions narrow.
