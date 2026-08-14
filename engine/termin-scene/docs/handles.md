# Handles и валидность

В ядре используется generational-модель идентификаторов. Это защита от висячих ссылок при удалении и переиспользовании слотов.

## Типы идентификаторов

| Тип | Назначение | Структура |
|-----|-----------|-----------|
| `tc_scene_handle` | Идентификатор сцены | generational handle |
| `tc_entity_pool_handle` | Идентификатор пула сущностей | generational handle |
| `tc_entity_id` | Сущность внутри пула | `{ index, generation }` |
| `tc_entity_handle` | Сущность глобально | `{ pool_handle, entity_id }` |

## Базовый инвариант

После `free/destroy` generation увеличивается. Старые handle/id становятся невалидными, даже если тот же `index` позже переиспользован.

```
alloc  → { index=5, gen=1 }  ← валиден
free   → gen для slot 5 становится 2
alloc  → { index=5, gen=2 }  ← новый handle
                               старый { index=5, gen=1 } уже невалиден
```

## Проверка валидности

| Функция | Что проверяет |
|---------|--------------|
| `tc_scene_alive(h)` | Сцена жива |
| `tc_entity_pool_registry_alive(h)` | Pool handle жив |
| `tc_entity_pool_alive(pool, id)` | Сущность жива в конкретном пуле |
| `tc_entity_handle_valid(h)` | Сущность жива (pool registry + entity pool) |

## Поведение API на невалидных ссылках

Большинство публичных функций работают в fail-soft режиме:

- Возвращают `NULL`, `0` или `INVALID`.
- Выполняют no-op для `set/remove/update` операций.
- Часть entity-функций дополнительно пишет warning в лог (`WARN_DEAD_ENTITY`).

Рекомендация: проверяйте валидность handle перед использованием, если handle мог устареть между кадрами.
