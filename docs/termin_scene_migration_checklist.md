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
