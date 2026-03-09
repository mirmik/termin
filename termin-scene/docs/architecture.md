# Архитектура

## Общая схема

Архитектура разделена на четыре слоя:

```
┌──────────────────────────────────────────────────┐
│  Scene Extensions (tc_scene_extension)           │
│  Stateful-модули: attach/detach/update/serialize │
├──────────────────────────────────────────────────┤
│  Scene (tc_scene)                                │
│  Контейнер сущностей, lifecycle-цикл             │
├──────────────────────────────────────────────────┤
│  Entity (tc_entity_pool)                         │
│  Хранение сущностей, иерархия, transform, флаги │
├──────────────┬───────────────────────────────────┤
│  Component   │  SoA (tc_archetype)               │
│  (tc_component + tc_type_registry)               │
│  Lifecycle-хуки, фабрики  │  Плотные данные,     │
│                           │  chunk-итерация      │
└───────────────────────────┴──────────────────────┘
```

## Ответственность модулей

| Модуль | Ответственность |
|--------|----------------|
| `src/tc_scene.c` | Scene pool, списки lifecycle-компонентов, update-проходы |
| `src/tc_entity_pool.c` | Сущности (SoA/AoS поля), parent/child, component arrays, UUID/pick lookup |
| `src/tc_component.c` | Реестр компонентных типов, фабрики, type flags, привязка к type entry |
| `src/tc_type_registry.c` | Унифицированный type registry: регистрация, версионирование, иерархия типов |
| `src/tc_archetype.c` | SoA-типы, архетипы, миграции строк, query chunks |
| `src/tc_scene_extension.c` | Registry типов расширений и экземпляров на сценах |

## Модель данных

- Сцена владеет `tc_entity_pool`.
- Сущность хранит базовое состояние и список object-компонентов (`tc_component*`).
- SoA-часть сущности задаётся `type_mask`; данные лежат в соответствующем архетипе.
- Безопасность ссылок обеспечивается generational id/handle моделью.

## Поток кадра

`tc_scene_update(scene, dt)`:

1. **pending_start** — `start` для новых компонентов.
2. **fixed_update** — в цикле по accumulator и `fixed_timestep`.
3. **update** — обычный кадровый update.
4. **extensions** — `on_scene_update` для scene extensions.

`tc_scene_before_render(scene)`:

1. **before_render** у компонентов.
2. **on_scene_before_render** у scene extensions.

## Границы API

- Публичный surface распределён по заголовкам из `include/core/` и `include/`.
- Большинство функций работают в fail-soft режиме: на невалидном handle/id возвращают `NULL/0/INVALID` или делают no-op.
- Контракты владения компонентами основаны на `retain/release` через `ref_vtable`.
