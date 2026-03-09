# Lifecycle

Порядок вызовов для object-компонентов (`tc_component`) в сцене.

## Добавление компонента

При `tc_entity_pool_add_component(pool, entity, c)`:

1. Устанавливается `c->owner`.
2. Вызывается `retain`, если `factory_retained == false`.
3. Компонент регистрируется в scene-списках (`pending_start`, `update`, `fixed_update`, `before_render`).
4. Вызывается `on_added_to_entity`.
5. Вызывается `on_added`.

## Основной update-цикл

`tc_scene_update(scene, dt)`:

1. **start** — для компонентов из `pending_start` (с учётом `enabled`).
2. **fixed_update** — в цикле по `accumulated_time` и `fixed_timestep`.
3. **update** — обычный кадровый update.
4. **extensions** — `tc_scene_ext_on_scene_update`.

Компонент обновляется только если:

- `component.enabled == true`
- владеющая сущность либо невалидна, либо `entity.enabled == true`

## Editor update-цикл

`tc_scene_editor_update(scene, dt)` работает как обычный update, но добавляет фильтр `active_in_editor == true` для `start`, `fixed_update`, `update`.

## Before render

`tc_scene_before_render(scene)`:

1. `before_render` у зарегистрированных компонентов.
2. `tc_scene_ext_on_scene_before_render` у extensions.

## Удаление компонента

При `tc_entity_pool_remove_component(pool, entity, c)`:

1. Вызывается `on_removed`.
2. Unregister из scene-списков.
3. Вызывается `on_removed_from_entity`.
4. `owner` сбрасывается в `TC_ENTITY_HANDLE_INVALID`.
5. Вызывается `release`.

## Массовые нотификации

Сцена поддерживает массовые проходы по компонентам:

| Нотификация | Когда |
|------------|-------|
| `on_editor_start` | Запуск editor mode |
| `on_scene_inactive` / `on_scene_active` | Активация/деактивация сцены |
| `on_render_attach` / `on_render_detach` | Подключение/отключение рендера |
