# Lifecycle

Порядок вызовов для object-компонентов (`tc_component`) в сцене.

## Добавление компонента

При `tc_entity_pool_add_component(pool, entity, c)`:

1. Устанавливается `c->owner`.
2. Вызывается `retain`, если `factory_retained == false`.
3. Компонент регистрируется в scene-списках (`pending_start`, `update`, `fixed_update`, `late_update`) и capability-индексах.
4. Вызывается `on_added_to_entity`.
5. Вызывается `on_added`.

Набор scheduler-фаз изменяется через
`tc_component_set_lifecycle_capabilities`. Для уже добавленного компонента
операция синхронно обновляет три scene index (`update`, `fixed_update`,
`late_update`). Прямое изменение флагов после регистрации не является частью
публичного контракта.

Каждый `tc_component` независимо хранит три числовых scheduler priority:
`update_priority`, `fixed_update_priority` и `late_update_priority`. Это
свойства компонента, а не владеющей `Entity`:
компоненты на одной entity могут исполняться в разном порядке. Внутри каждой
фазы большее значение исполняется раньше, default равен `0`, а равные значения
сохраняют детерминированный порядок регистрации. Setter выполняет live reindex
только соответствующего scene index. Изменение priority одной фазы не влияет на
остальные.

Константы `EARLY = 100`, `DEFAULT = 0`, `LATE = -100` являются именованными
точками числового порядка, но не создают дополнительных lifecycle-фаз.
Подсистемы могут давать им более предметные имена, например `FixedControl`,
`FixedPhysics` и `FixedPostPhysics`.

В C++ этот базовый fixed-step контракт доступен как
`fixed_update_priority::control`, `fixed_update_priority::physics` и
`fixed_update_priority::post_physics`. Это лишь удобные точки на числовой
шкале: компоненты могут выбирать любые целочисленные значения между ними и за
их пределами.

Период fixed-цикла хранится в сериализуемом свойстве сцены
`fixed_timestep`. Редактор показывает обратную величину как `Fixed Update, Hz`
в `Scene → Scene Properties`. Таким образом, частота относится к конкретной
сцене, а не к отдельному physics-компоненту.

Сериализуемое свойство `time_scale` масштабирует runtime-время всей сцены до
накопления fixed-шагов. Значение `0` приостанавливает simulation time, а
положительные дробные значения растягивают симуляцию по wall time, не меняя
сам `fixed_timestep`: каждый `fixed_update` по-прежнему получает полный
фиксированный шаг. Тем же масштабированным `dt` пользуются runtime `update`,
scene extensions и `late_update`. Служебный `tc_scene_editor_update` намеренно
остаётся на немасштабированном wall time, чтобы time scale сцены не замедлял
редакторские инструменты.

## Основной update-цикл

`tc_scene_update(scene, wall_dt)` сначала вычисляет
`dt = wall_dt * time_scale`, после чего исполняет:

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

## Render lifecycle

`late_update` является частью simulation update и выполняется даже в headless
режиме или когда кадр не будет отрисован. Авторитетное состояние сцены и
зависимые вычисления, нужные игровому коду, должны завершаться здесь.

Render lifecycle не является частью `termin-scene`. Его предоставляет
`termin-render` через capability `render_lifecycle`, а runtime хранится в уже
существующем scene extension `render_mount`.

Контракт участника состоит из `on_render_attach`, `prepare_render` и
`on_render_detach`. `attach` приходит после создания live topology,
`prepare_render` — один раз перед первой фактической render job этой сцены в
кадре, `detach` — до уничтожения pipelines и targets. Добавленный в уже
подключённую сцену участник сразу получает `attach`; удаляемый сначала получает
`detach`. Disabled component/entity не получает attach/prepare, но уже
подключённый участник всегда получает балансирующий detach.

В C++ контракт объявляется через `RenderLifecycle`, в Python — через
`RenderLifecycleComponent`. Порядок `prepare_render` задаётся capability
priority и не расширяет simulation scheduler.

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
