# Project build contract gate plan

Дата: 2026-06-19

Связанные задачи:

- Kanboard #53 - `[build] Сделать runtime package validation фатальным gate`
- Kanboard #32 - `[assets] Довести runtime package asset graph до desktop build needs`
- Kanboard #39 - `[build] Оформить include policy для dynamic from_name ресурсов`
- Kanboard #40 - `[assets] Завершить вынос asset runtime из termin-app`

Связанные документы:

- `docs/plans/2026-06-17-build-system-target-architecture.md`
- `docs/plans/2026-06-18-project-build-pipeline-execution-plan.md`

## Goal 1: build gate + profile policy

Цель:

Привести `termin.project_build` к строгому contract-gate поведению:
ошибки runtime package validation останавливают target packaging и дают
non-zero CLI exit; `configuration`/`resource_policy` из build profile становятся
частью нормализованного build context; fallback artifacts разрешены только
явной dev/smoke policy; тесты и документация обновлены.

### 1. Сделать validation фатальным gate

- Ввести исключение или результат уровня pipeline для fatal diagnostics.
- Если `validate_runtime_package()` вернул diagnostic с `level == "error"`, не
  вызывать `package_target`.
- Обновить `termin-app/tests/test_project_build_pipeline.py`: validation error
  должен останавливать pipeline до target packaging.
- Сохранить aggregation diagnostics так, чтобы UI/CLI могли показать все
  найденные ошибки.

### 2. Сделать CLI exit code честным

- `termin.project_build.profile_build.build_profile()` должен возвращать
  non-zero, если result diagnostics содержат `level == "error"`.
- Diagnostics при этом должны продолжать печататься в существующем
  human-readable формате.
- Добавить tests для desktop/android/quest fake result с error diagnostics.

### 3. Нормализовать profile policy

- Добавить в `BuildContext` явные поля для profile policy, например:
  `configuration` и `resource_policy`.
- Парсить эти поля в `normalize_profile_build_request()`.
- Ввести небольшой валидатор допустимых значений. Начальный набор:
  - `configuration`: `dev`, `debug`, `release`
  - `resource_policy`: `dev`, `dev_smoke`, `strict`
- Не оставлять эти поля только "разрешенными ключами" profile schema без
  влияния на build behavior.

### 4. Подключить policy к exporter

- Передавать policy из pipeline в `export_runtime_package(...)`.
- Разрешать fallback mesh/material только при явном `resource_policy:
  dev_smoke` или другой согласованной dev-only policy.
- В strict/default production-like режимах missing mesh/material должен давать
  error diagnostic или исключение, но не placeholder artifact.
- Обновить tests, которые сейчас ожидают fallback warning всегда.

### 5. Обновить документацию контракта

- Зафиксировать фактическое поведение:
  - validation является gate перед target packaging;
  - profile CLI возвращает non-zero при build/export/validation errors;
  - `configuration` и `resource_policy` имеют определенную семантику;
  - placeholder/fallback resources являются explicit dev-only режимом.
- Обновить `docs/plans/2026-06-17-build-system-target-architecture.md` или
  добавить короткую актуальную секцию в `docs/build-system.md`.

### 6. Прогнать focused tests

Минимальный набор:

```bash
./run-tests-python.sh termin-app/tests/test_project_build_pipeline.py
./run-tests-python.sh termin-app/tests/test_project_build_profile_backend.py
./run-tests-python.sh termin-app/tests/test_runtime_package_exporter.py
./run-tests-python.sh termin-app/tests/test_runtime_package_validator.py
```

Если изменения заденут wrapper behavior шире:

```bash
./run-tests-python.sh termin-app/tests/test_project_build_*.py
```

## Goal 2: build-safe asset graph

Это отдельный следующий goal, не часть первой итерации.

Цель:

Начать вынос runtime package build graph из live `ResourceManager`/preloader
path: выделить build-safe graph/analyze слой, заменить эвристический
preload/export path хотя бы для scene/material/mesh/shader/pipeline ресурсов,
сохранить текущие fallback/dev paths только за explicit policy.

Ориентиры:

- Заменить `preload_project_resources(...)` dependency на build-safe
  graph/analyze API.
- Перестать использовать live singleton registries как источник истины для
  packaged build.
- Добавить explicit include policy для dynamic resources.
- Расширять package coverage итеративно: textures, fonts/UI, audio,
  navmesh/voxels/foliage, Python/C++ module descriptors.

Этот goal связан с Kanboard #32, #39 и #40 и должен опираться на gates/policy,
сделанные в Goal 1.
