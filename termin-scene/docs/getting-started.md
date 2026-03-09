# Быстрый старт

Минимальный поток: создать сцену, добавить сущность с компонентом, выполнить update и корректно освободить ресурсы.

## 1. Создать сцену и получить пул сущностей

```c
tc_scene_handle scene = tc_scene_new_named("Main");
tc_entity_pool* pool = tc_scene_entity_pool(scene);
```

## 2. Создать сущность

```c
tc_entity_id e = tc_entity_pool_alloc(pool, "Player");
```

## 3. Создать и добавить компонент

```c
// c должен быть корректно инициализирован
// (vtable, ref_vtable и другие поля по контракту вашего типа компонента)
tc_entity_pool_add_component(pool, e, c);
```

При добавлении:

1. Устанавливается `c->owner`.
2. Вызывается `retain` (если `factory_retained == false`).
3. Вызываются `on_added_to_entity` и `on_added`.

Подробнее: [Lifecycle](lifecycle.md).

## 4. Выполнить update кадра

```c
tc_scene_update(scene, dt);          // start -> fixed_update -> update
tc_scene_before_render(scene);       // before_render для компонентов и extensions
```

## 5. Освобождение

```c
tc_scene_free(scene);
```

При освобождении сцены удаляются все сущности и вызывается `release` для каждого компонента.

## Что важно помнить

- Все `handle/id` в ядре generational: после `free` старые значения становятся невалидными.
- `tc_scene_update` выполняет `start` (для новых компонентов), затем `fixed_update`, затем `update`.
- При удалении сцены освобождаются компоненты по ref-count контракту (`retain/release`).

## Что дальше

- [Философия](philosophy.md) — зачем так устроено.
- [Архитектура](architecture.md) — слои, модули, поток кадра.
- [Handles](handles.md) — как работают generational идентификаторы.
