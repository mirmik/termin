# Lifecycle

Порядок вызовов для object-компонентов (`tc_component`) в сцене.

## Добавление компонента

При `tc_entity_pool_add_component(pool, entity, c)`:

1. Устанавливается `c->owner`.
2. Вызывается `retain`, если `factory_retained == false`.
3. Компонент регистрируется в scene-списках (`pending_start`, `update`, `fixed_update`, `before_render`).
4. Вызывается `on_added_to_entity`.
5. Вызывается `on_added`.

Набор scheduler-фаз изменяется через
`tc_component_set_lifecycle_capabilities`. Для уже добавленного компонента
операция синхронно обновляет все три scene index (`update`, `fixed_update`,
`before_render`). Прямое изменение флагов после регистрации не является частью
публичного контракта.

## Основной update-цикл

`tc_scene_update(scene, dt)`:

1. **start** — для компонентов из `pending_start` (с учётом `enabled`).
2. **fixed_update** — в цикле по `accumulated_time` и `fixed_timestep`.
3. **update** — обычный кадровый update.
4. **extensions** — `tc_scene_ext_on_scene_update`.

Компонент обновляется только если:

- `component.enabled == true`
- владеющая сущность либо невалидна, либо `entity.enabled == true`

При включённом hierarchical profiling scheduler создаёт устойчивое дерево
`Start / Fixed Update / Update / Extensions`. В первых трёх фазах каждый
вызванный экземпляр компонента получает дочернюю секцию вида
`TypeName @ EntityName [source]`. Повторные вызовы того же экземпляра в
`fixed_update` объединяются профайлером и отражаются в `call_count`.

Имена и число секций ограничены native-профайлером
(`TC_PROFILER_MAX_NAME_LEN`, `TC_PROFILER_MAX_SECTIONS`). При выключенном
profiling scheduler не строит имена секций и не выделяет для них память.

## Editor update-цикл

`tc_scene_editor_update(scene, dt)` работает как обычный update, но добавляет фильтр `active_in_editor == true` для `start`, `fixed_update`, `update`.

## Before render

`tc_scene_before_render(scene)`:

1. `before_render` у зарегистрированных компонентов.
2. `tc_scene_ext_on_scene_before_render` у extensions.

`PythonComponent` участвует только в тех scheduler-фазах, методы которых
переопределены. После замены Python-класса вызывается
`refresh_lifecycle_capabilities()`, чтобы повторно вычислить override-набор и
переиндексировать attached-компонент.

## Удаление компонента

При `tc_entity_pool_remove_component(pool, entity, c)`:

1. Компонент удаляется из scene-списков и type/capability индексов.
2. Вызывается `on_removed`.
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

Обе render-нотификации получают `RenderAttachmentContext`. Это временный
scene-scoped view живых targets и pipelines; сохранять ссылку на него после
возврата из callback нельзя. `termin-scene` только транспортирует opaque
context, а его API и lifetime принадлежат `termin-engine`.
