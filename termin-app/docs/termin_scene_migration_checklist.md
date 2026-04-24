# Migration Checklist: `termin` -> `termin-scene`

Дата среза: **March 3, 2026**.

## Цель

Вынести `tc_scene`, `tc_entity` (entity pool/handles), `tc_component` и минимально необходимые зависимости в отдельную библиотеку `termin-scene`, чтобы:

- `termin-scene` содержал ядро ECS/lifecycle;
- `termin` подключал это ядро как внешнюю зависимость;
- subsystem-specific runtime state (render/collision/editor) жил в extension-ах и/или в `termin`.

## Текущее состояние (факт)

- `termin-scene` инициализирован и собирается как отдельная C-библиотека.
- В `termin-scene` уже перенесен базовый scene-core набор (`tc_scene`, `tc_entity_pool`, `tc_component`, `tc_type_registry`, `tc_archetype`, `tc_hash_map`, `tc_scene_extension`).
- `tc_types`/`tc_value`/`tc_dlist` вынесены в `termin-base`; в `termin` и `termin-scene` оставлены совместимые thin-wrapper заголовки.
- В перенесенной версии `tc_scene` удалены прямые зависимости на render/collision shim API.
- В `termin` extension-инфраструктура уже реализована (`tc_scene_ext_*`).
- В `termin/core_c` пока остается legacy-реализация до переключения `termin` на внешний `termin-scene`.

## Definition of Done (миграция завершена)

1. `termin-scene` собирается и ставится как отдельная библиотека.
2. `termin` не содержит исходников `tc_scene/tc_entity_pool/tc_component` (берет их из `termin-scene`).
3. В публичном API scene-core нет subsystem-specific API (collision/render shims).
4. `termin` проходит сборку и smoke-тесты со внешним `termin-scene`.
5. Legacy fallback-десериализация удалена только после перевода потребителей.

## Этап 0. Bootstrap `termin-scene`

- [x] Инициализировать репозиторий `termin-scene` рабочим содержимым (не пустой gitdir).
- [x] Добавить `CMakeLists.txt` для сборки `termin_scene`.
- [x] Добавить install/export (`termin_sceneConfig.cmake`) по аналогии с `termin-base`/`termin-graphics`.
- [x] Подключить `termin-scene` в верхнеуровневые скрипты окружения (`build-and-install.sh` и Windows-скрипт).

Критерий готовности:

- `rg --files /home/mirmik/project/termin-env/termin-scene` возвращает исходники/заголовки.

## Этап 1. Выделить минимальный scene-core набор

Переносимый минимум (из `termin/core_c`):

- [x] `tc_scene.[ch]`
- [x] `tc_scene_pool.h`
- [x] `tc_entity_pool.[ch]`
- [x] `tc_entity_pool_registry.[ch]`
- [x] `tc_component.[ch]`
- [x] `tc_type_registry.[ch]`
- [x] `tc_archetype.[ch]`
- [x] `tc_hash_map.[ch]` (или зависимость на `termin-base`, см. decision gate ниже)
- [x] `tc_types.h` (или эквивалентный shared base import)

Что уходит в `termin-base`:

- [x] `tc_value.[ch]` (общий контейнерный тип для C API; вынесен в `termin-base`)
- [x] `tc_dlist.h` (общая intrusive list utility; вынесена в `termin-base`)

Минимальные внешние зависимости:

- [x] `tcbase` (`tc_log`, `tc_binding_types`)
- [x] `tgfx/tc_resource_map` (нужно для type maps в `scene` и `type_registry`)

Decision gate по `tc_hash_map`:

- [x] Оценить абстрактность `tc_hash_map`:
  - если API и семантика общие (не scene-specific), переносим в `termin-base`;
  - если есть привязка к ECS/scene данным, оставляем в `termin-scene`.
- [x] Зафиксировать решение и обновить зависимости в CMake.
  - Решение: пока оставляем `tc_hash_map` в `termin-scene` до отдельного выноса утилит в `termin-base`.

Критерий готовности:

- Сборка `termin-scene` успешна без линковки на `render`, `physics`, `editor` модули.

## Этап 2. Убрать subsystem-specific связность из `tc_scene`

Обязательные изменения перед/во время выноса:

- [x] Убрать из `tc_scene.c` прямые include:
  - `core/tc_scene_render_mount.h`
  - `core/tc_scene_render_state.h`
  - `physics/tc_collision_world.h`
- [x] Убрать прямую инициализацию built-in extension-ов из `tc_scene_pool_init()`.
- [x] Убрать auto-attach built-in extension-ов из `tc_scene_pool_alloc()`.
- [x] Удалить legacy shim API:
  - `tc_scene_get_collision_world`
  - `tc_scene_set_collision_world`

Критерий готовности:

- Команды ниже не находят совпадений:

```bash
rg -n "tc_scene_render_mount|tc_scene_render_state|tc_collision_world" core_c/src/tc_scene.c
rg -n "tc_scene_get_collision_world|tc_scene_set_collision_world" core_c/include/core/tc_scene.h core_c/src/tc_scene.c
```

## Этап 3. Инициализация extension-ов переносится в `termin`

После удаления из scene-core:

- [ ] Регистрация built-in extension-типов (`render_mount`, `render_state`, `collision_world`) выполняется в `termin` startup слое.
- [ ] Attach нужных extension-ов при создании сцены выполняется в `termin` (C++/scene manager слой), а не в scene-core.

Критерий готовности:

- Scene-core не знает о конкретных extension type id.

## Этап 4. Подключить `termin` к внешнему `termin-scene`

- [x] В `termin/cpp/CMakeLists.txt` убрать `add_subdirectory(${TERMIN_ROOT}/core_c ...)` для перенесенных модулей.
  - Реализовано через `TC_USE_EXTERNAL_SCENE=ON`: `termin_core` собирается без scene-core исходников и линкуется с внешним `termin_scene`.
- [x] Линковать `termin` на установленный пакет `termin_scene`.
- [x] Поправить include paths/exports для заголовков scene-core.

Критерий готовности:

- `termin/build.sh --clean` проходит, и бинарники используют внешнюю `termin_scene` библиотеку.

## Этап 5. ABI/Bindings cleanup

- [ ] Проверить внешние ABI-слои (в т.ч. C# P/Invoke), что нет ссылок на удаленный legacy API.
- [ ] Проверить Python/C++ биндинги на отсутствие прямой зависимости от удаленных shim-функций.

Критерий готовности:

```bash
rg -n "tc_scene_get_collision_world|tc_scene_set_collision_world" /home/mirmik/project/termin-env
```

должен вернуть 0 совпадений.

## Этап 6. Удаление legacy fallback в десериализации

Только после полного перевода потребителей:

- [ ] Удалить fallback чтение legacy top-level полей в `TcSceneRef::load_from_data()`:
  - `viewport_configs` / `scene_pipelines`
  - `background_color`, `ambient_*`, `shadow_settings`, `skybox_*`

Критерий готовности:

- Scene JSON использует только `extensions.*` для subsystem state.

## Быстрый pre-flight перед началом фактического переноса

- [ ] Зафиксировать текущий baseline сборки `termin`.
- [ ] Добавить smoke-тест: создать сцену, добавить сущность и компонент, прогнать `update()/before_render()`.
- [ ] Прогнать сериализацию/десериализацию сцены с `extensions`.

---

## Дополнение: План выноса `tc_inspect` / `tc_kind` / component runtime

Контекст: для полезного `termin-scene` недостаточно только C scene-core. Нужны:
- `CxxComponent` / `PythonComponent`;
- сериализация/десериализация через `tc_inspect` + `tc_kind`;
- регистрация компонентных фабрик.

### Наблюдаемая граница (по состоянию на March 4, 2026)

Уже scene-core и переносимо в `termin-scene`:
- `core_c/include/inspect/tc_inspect.h`, `core_c/src/tc_inspect.c` (C dispatcher)
- `core_c/include/inspect/tc_kind.h`, `core_c/src/tc_kind.c` (C dispatcher)
- `termin-scene` C registry/factory (`tc_component_registry_*`) уже вынесен.

Сейчас смешано с `termin` runtime:
- `core_c/src/tc_inspect_instance.cpp` тянет `CxxComponent`, `CxxFramePass`, mesh/material и C++ runtime.
- `cpp/termin/inspect/tc_kind_cpp.cpp` регистрирует `tc_mesh` и `tc_material` через `TcMesh/TcMaterial`.
- Python kind/inspect bridge (`bindings/inspect/*`) завязан на nanobind и модули `termin.*`.

### Решение по границе

Что уходит в `termin-scene`:
- `tc_inspect`/`tc_kind` C dispatcher;
- C++ inspect/kind scene-level registry (`InspectRegistry`, `KindRegistryCpp`);
- `CxxComponent` / `tc_component_python` runtime;
- scene-level component factory flow (C++/Python компоненты, без render/editor pass API).

Что остается в `termin`:
- pass-specific inspect (`tc_pass_inspect_*`);
- render/editor-specific kinds (`tc_mesh`, `tc_material`, и т.п.) как extension registration;
- C#-specific glue (если не переносится отдельным шагом).

### Этап 7. Разрезать inspect API на scene-level и pass-level

- [ ] Убрать `tc_pass_inspect_get/set` из переносимого `tc_inspect` API (оставить в `termin`-слое).
- [ ] Оставить в `termin-scene` только inspect API, относящийся к компонентам/типам сцены.

Критерий:
- `termin-scene` не содержит зависимостей на `tc_pass`/render frame pass.

### Этап 8. Перенос `tc_inspect`/`tc_kind` (C dispatcher) в `termin-scene`

- [ ] Перенести `tc_inspect.[ch]`, `tc_kind.[ch]` в `termin-scene`.
- [ ] Подключить в `termin-scene/CMakeLists.txt`, install/export.
- [ ] Удалить дубли/старые копии в `termin/core_c`.

Критерий:
- `termin-scene` собирает inspect/kind dispatcher без зависимостей на `termin/cpp`.

### Этап 9. Перенос C++ inspect/kind registry в `termin-scene`

- [ ] Перенести `tc_inspect_cpp.hpp` и C++ реализацию registry.
- [ ] Перенести `tc_kind_cpp.*` в `termin-scene` C++ слой.
- [ ] Убрать из core-инициализации auto-registration `tc_mesh`/`tc_material`; перенести их регистрацию в `termin`.

Критерий:
- `KindRegistryCpp` и `InspectRegistry` доступны из `termin-scene` без include на `termin/mesh` и `termin/material`.

### Этап 10. Перенос `CxxComponent` / `PythonComponent` runtime

- [ ] Перенести `entity/component.[hc]pp` и `tc_component_python.*` в `termin-scene`.
- [ ] Перенести/адаптировать `ComponentRegistry` bridge на новую границу.
- [ ] Для Python class resolution ввести callback/resolver (убрать hardcoded import списки из scene-core).

Критерий:
- базовый жизненный цикл C++/Python компонентов работает при линковке только с `termin-scene`.

### Этап 11. Тесты для inspect/kind/component runtime

- [ ] Добавить C тесты:
  - `tc_kind_parse`,
  - `tc_kind_*` dispatcher (mock lang registries),
  - `tc_inspect_serialize/deserialize` через mock vtable.
- [ ] Добавить C++ тесты:
  - roundtrip для `InspectRegistry + KindRegistryCpp` (int/float/string/vec3).
- [ ] Добавить Python smoke:
  - регистрация `PythonComponent`,
  - фабричное создание через registry,
  - serialize/deserialize поля через inspect.

Критерий:
- тесты переехавших слоев запускаются в CI `termin-scene`.
