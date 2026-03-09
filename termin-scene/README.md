# termin-scene

Scene-core библиотека для движка **Termin**.

Реализует управление сценой, сущностями, компонентами и SoA-архетипами на C.
Предоставляет стабильный низкоуровневый API для интеграции через FFI (C++, Python, C#).

## Возможности

- **Сцена и entity pool** — создание сцен, аллокация сущностей, иерархия parent/child.
- **Object-компоненты** — lifecycle-хуки (`start`, `update`, `fixed_update`, `before_render`), retain/release владение.
- **SoA-архетипы** — плотное хранение data-only компонентов, chunk-итерация по маскам типов.
- **Generational handles** — безопасные ссылки с защитой от use-after-free.
- **Scene extensions** — stateful-модули с attach/detach/update/serialize без изменения core.

## Быстрый старт

```c
tc_scene_handle scene = tc_scene_new_named("Main");
tc_entity_pool* pool = tc_scene_entity_pool(scene);

tc_entity_id e = tc_entity_pool_alloc(pool, "Player");
tc_entity_pool_add_component(pool, e, my_component);

tc_scene_update(scene, dt);
tc_scene_before_render(scene);

tc_scene_free(scene);
```

## Сборка

```bash
cmake -S . -B build
cmake --build build -j$(nproc)
ctest --test-dir build --output-on-failure
```

## Документация

Документация собирается через MkDocs (GitHub Pages).

- Исходники: [`docs/`](docs/)
- Конфигурация: [`mkdocs.yml`](mkdocs.yml)

Локальный просмотр:

```bash
pip install mkdocs mkdocs-material
mkdocs serve
```

## Структура проекта

```
include/
  core/           # Публичные заголовки: tc_scene, tc_entity_pool, tc_component, ...
  termin_scene/    # Точка входа: termin_scene.h
src/               # Реализация
docs/              # Документация (MkDocs)
tests/             # Тесты
```
