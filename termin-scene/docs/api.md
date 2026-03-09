# API Reference

## Точка входа

- `include/termin_scene/termin_scene.h`
- Экспортирует: `termin_scene_version_int()`

## Core API

| Заголовок | Ответственность |
|-----------|----------------|
| `include/core/tc_scene.h` | Сцена, lifecycle, итерации компонентов, metadata |
| `include/core/tc_scene_pool.h` | Pool сцен и scene handles |
| `include/core/tc_entity_pool.h` | Сущности, transform, hierarchy, components, SoA API |
| `include/core/tc_entity_pool_registry.h` | Registry pool handles |
| `include/core/tc_component.h` | Базовая структура компонента, vtable, component registry |
| `include/core/tc_archetype.h` | SoA type registry, archetype storage, query |
| `include/core/tc_scene_extension.h` | Scene extensions |

## Utility API

| Заголовок | Ответственность |
|-----------|----------------|
| `include/tc_type_registry.h` | Type registry и instance tracking |
| `include/tc_hash_map.h` | `str/u32/u64` hash maps |

## Как читать API

Для каждой функции проверяйте:

- **Preconditions** — какие handle/id должны быть валидны.
- **Ownership** — кто владеет объектом до и после вызова.
- **Side effects** — какие внутренние списки/реестры обновляются.
- **Fail-soft** — что возвращается на невалидных входах.
