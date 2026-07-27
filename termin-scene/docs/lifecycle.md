# Lifecycle

Порядок вызовов для object-компонентов (`tc_component`) в сцене.

## Добавление компонента

При `tc_entity_pool_add_component(pool, entity, c)`:

1. Устанавливается `c->owner`.
2. Вызывается `retain`, если `factory_retained == false`.
3. Компонент регистрируется в scene-списках (`pending_start`, `update`, `fixed_update`, `late_update`, `before_render`).
4. Вызывается `on_added_to_entity`.
5. Вызывается `on_added`.

Набор scheduler-фаз изменяется через
`tc_component_set_lifecycle_capabilities`. Для уже добавленного компонента
операция синхронно обновляет все четыре scene index (`update`, `fixed_update`,
`late_update`, `before_render`). Прямое изменение флагов после регистрации не является частью
публичного контракта.

## Основной update-цикл

`tc_scene_update(scene, dt)`:

1. **start** — для компонентов из `pending_start` (с учётом `enabled`).
2. **fixed_update** — в цикле по `accumulated_time` и `fixed_timestep`.
3. **update** — обычный кадровый update.
4. **extensions** — `tc_scene_ext_on_scene_update`.
5. **late_update** — зависимые кадровые вычисления после всех обычных
   component/extension updates.

Компонент обновляется только если:

- `component.enabled == true`
- владеющая сущность либо невалидна, либо `entity.enabled == true`

При включённом hierarchical profiling scheduler создаёт устойчивое дерево
`Start / Fixed Update / Update / Extensions / Late Update`. В component-фазах каждый
вызванный экземпляр компонента получает дочернюю секцию вида
`TypeName @ EntityName [source]`. Повторные вызовы того же экземпляра в
`fixed_update` объединяются профайлером и отражаются в `call_count`.

Имена и число секций ограничены native-профайлером
(`TC_PROFILER_MAX_NAME_LEN`, `TC_PROFILER_MAX_SECTIONS`). При выключенном
profiling scheduler не строит имена секций и не выделяет для них память.

## Editor update-цикл

`tc_scene_editor_update(scene, dt)` работает как обычный update, но добавляет
фильтр `active_in_editor == true` для `start`, `fixed_update`, `update` и
`late_update`.

Очередь `pending_start` не сканируется повторно в steady state. Регистрация
компонента и переходы через `tc_component_set_enabled` /
`tc_component_set_active_in_editor` увеличивают scheduler revision; editor и
runtime проходы независимо обрабатывают только новые revision. Поэтому
изменение этих полей напрямую после регистрации не поддерживается: runtime
переходы должны идти через setter API.

`start` исполняется по снимку очереди. Регистрация или удаление компонентов из
callback безопасны и будят следующий проход, не расширяя текущую итерацию.

## Before render

`late_update` является частью simulation update и выполняется даже в headless
режиме или когда кадр не будет отрисован. Авторитетное состояние сцены и
зависимые вычисления, нужные игровому коду, должны завершаться здесь.

`tc_scene_before_render(scene)`:

1. `before_render` у зарегистрированных компонентов.
2. `tc_scene_ext_on_scene_before_render` у extensions.

`before_render` предназначен только для render-facing подготовки и может не
вызываться, если host пропускает рендер.

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
