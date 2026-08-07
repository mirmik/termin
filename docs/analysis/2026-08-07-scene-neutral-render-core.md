# Scene-neutral render core для retained 3D composition

Дата: 2026-08-07  
Статус: принято к поэтапной реализации; umbrella #1358, завершены slices
#1359–#1366 и surface encoder slice #1368

## Контекст

`TcVisualScene2D` позволяет собирать chart из retained items и
кастомизировать meaningful parts через interop boundary. Для 3D chart уже
существует первый retained vertical slice: `RetainedChart3D`, `PlotScene3D`,
generation handles и typed C# wrappers для surface, scatter и grid.

Первоначальное направление предполагало plot-specific retained renderer,
чтобы не вводить преждевременно универсальный engine-wide
`TcVisualScene3D`. Однако есть более фундаментальная возможность: отделить
существующий framegraph и render execution от игровой `tc_scene` semantics,
после чего использовать один renderer как для engine scene, так и для
retained chart scene.

Эта записка фиксирует принятое направление миграции, но не заменяет
[`Retained Chart3D migration`](../plans/2026-08-06-retained-chart3d-migration-plan.md).

## Краткий вывод

Обобщение существующего render engine выглядит сильнее, чем развитие второго
3D renderer для chart. Но одного физического переноса `tc_frame_graph.c` в
нижний модуль недостаточно. Нужна инверсия зависимости: generic render
execution должен принимать произвольный источник render items, а интеграция с
`tc_scene`, entities, components, camera и lights должна стать адаптером над
ним.

`PlotScene3D` при этом не исчезает. Она остаётся лёгкой retained object model,
которая отвечает за identity, lifetime, topology, typed state и interop.
Generic renderer отвечает только за resource scheduling, pass execution и GPU
submission.

Целевая формула:

```text
C# / Python
    |
    v
PlotScene3D -- retained handles, items and mutations
    |
    v
PlotScene3DRenderItemSource
    |
    v
scene-neutral RenderEngine -- framegraph -- tgfx2
```

## Что уже универсально

Runtime `tc_frame_graph` является почти чистым C scheduler. Он знает только о:

- passes;
- named reads and writes;
- inplace aliases;
- dependency edges;
- topological schedule;
- canonical resource names.

Он не использует camera, lighting, entities, components или scene traversal.
Основная привязка возникает косвенно: graph строится над `tc_pipeline` и
`tc_pass`, а их публичные контракты уже находятся внутри большого
`termin-render` domain.

Существующий typed submission path также даёт хорошую основу для обобщения:

- `tc_render_item` представляет mesh, line batch, text batch, foliage batch и
  world quad;
- `RenderItemCollection` может владеть immutable adapter payload до
  invalidation snapshot;
- `RenderItemTask` отделяет planning от submission;
- draw encoders регистрируются по item kind;
- material/shader resource binding выполняется до backend draw commands.

Surface chart может быть generic mesh item с chart material либо отдельным
зарегистрированным item kind. Scatter, lines, world text и overlays также
могут идти через общий RenderItem/encoder contract.

## Где сейчас находится игровая связанность

`termin-render` в одном target совмещает несколько разных уровней:

1. Framegraph DAG и runtime pipeline storage.
2. Resource allocation, pass execution и render-target orchestration.
3. Material/shader planning и RenderItem submission.
4. `tc_scene` traversal и component drawable capabilities.
5. Camera, lights, shadows, internal entities и engine render policy.
6. Authoring graph compiler, inspection and Python bindings.

Конкретные coupling points:

- scene adapter и generic executor пока физически находятся в одном
  `termin-render` target, хотя их публичные контракты уже разделены;
- `TcSceneRenderItemSource` реализует общий source contract через
  `tc_scene_foreach_drawable()`, но пока физически собирается в том же target;
- `RenderTask` содержит `Entity`, `tc_component*` и entity name;
- `tc_render_item` содержит source `tc_component*`;
- scene shader discovery всё ещё обходит passes и scene перед исполнением,
  но вынесен из generic `CxxFramePass` в отдельную capability
  `SceneShaderUsageProvider`;
- generic resource allocation больше не знает о shadow types: non-texture
  resources создаются через `FrameGraphResourceTypeDescriptor`, а конкретный
  `shadow_map_array` и его sampled preview принадлежат `termin-render-passes`;
- `termin-render` публично зависит одновременно от `termin-graphics`,
  `termin-scene`, `termin-materials`, `termin-lighting` и `termin-inspect`.

Поэтому перемещение только framegraph scheduler не позволит chart использовать
текущий `RenderEngine` без подключения игровой логики.

## Предлагаемая граница модулей

Не следует переносить весь render framework непосредственно в
`termin-graphics`. Этот модуль должен оставаться GPU substrate: device,
context, resources, shaders, backend binding и command execution. Framegraph,
material routing и RenderItems являются более высокой render policy.

Предпочтительная зависимость:

```text
termin-graphics
device, context, buffers, textures, shaders
             ^
             |
termin-render-core
framegraph, pipeline execution, resource tables,
RenderItem/RenderTask, generic draw encoders
          ^                         ^
          |                         |
termin-render                    tcplot
TcScene adapter                  PlotScene3D adapter
camera/lights/components         chart camera/items/picking
```

`termin_render_core` реализован в #1364 как один физический target и отдельный
CMake package. Дальнейшее дробление на `termin-framegraph` и другие мелкие
библиотеки не требуется до появления отдельной доказанной границы повторного
использования.

## Generic execution contract

Текущий entry point следует обобщить от scene execution к render execution.
Логически входной пакет должен содержать:

```text
RenderExecution
├── pipeline
├── output targets and external resources
├── render extent
├── view constants
├── RenderItemSource / immutable item snapshot
└── optional typed services or capabilities
```

Core `ExecuteContext` должен содержать только:

- `RenderContext2`;
- resolved read/write resource tables;
- color/depth attachment views;
- render extent;
- frame/pass diagnostics and capture hooks;
- scene-neutral view constants;
- immutable RenderItem snapshot;
- явно запрошенные typed services.

Игровой адаптер может дополнять execution:

```text
SceneRenderServices
├── TcSceneRef
├── lights and shadows
├── layer/category filtering
└── internal entities
```

Chart adapter предоставляет другой набор:

```text
Chart3DRenderServices
├── PlotScene3D snapshot
├── OrbitCamera matrices
├── plot bounds and axis scale
├── chart picking/index data
└── annotation projection state
```

Generic passes не должны видеть ни один из этих наборов. Scene-specific или
chart-specific pass явно объявляет требуемую capability. Не следует заменять
явный контракт одним неструктурированным `void* user_context`.

## Render item sources

Нужна общая абстракция источника immutable frame snapshot:

```text
TcSceneRenderItemSource
    traverses tc_scene components
             |
             v
        RenderItems
             ^
             |
PlotScene3DRenderItemSource
    traverses retained chart items
```

Нынешний `RenderSceneItemCollector` скрыт за `TcSceneRenderItemSource` и больше
не является обязательной частью execution contract. `PlotScene3D` сможет
перечислять stable retained items и создавать snapshot без entities или
components. Оба источника после collection используют одинаковые task
planning, phase routing, shader/material binding и submission.

Source identity в generic `tc_render_item` не должна быть выражена только как
`tc_component*`. Нужен нейтральный source handle/debug identity либо optional
adapter-owned metadata. Game adapter по-прежнему сможет связать item с
component/entity для инспекции, но chart не будет создавать фиктивные
components.

Первый vertical slice реализует эту границу как
`tc_render_item_source { domain_id, namespace_id, object_id, generation,
subobject_id, adapter_data }`. Первые пять полей составляют стабильную
adapter-owned identity. `adapter_data` живёт только в пределах immutable
frame/view snapshot и не интерпретируется generic render code. Для `tc_scene`
адаптер кладёт туда `tc_component*`; scene-specific passes получают его через
явный `render_scene_item_component()`. Retained chart сможет назначить свой
domain и не создавать component/entity.

В #1366 `RenderItemCollection` получил type-erased ownership для adapter
payload. Это отличает payload pointer от обычного borrowed metadata: source
удерживает `shared_ptr<const Payload>` в storage, а `adapter_data` ссылается на
него до invalidation snapshot. `PlotScene3D` использует эту границу для
immutable geometry/style/chart-state values; retained slot и временный
`PlotEngine3D` body в snapshot не попадают.

`RenderItemCollection`, `RenderItemSnapshot` и `RenderItemSource` теперь
являются нейтральными контрактами. `RenderItemSource::publish()` владеет единым
атомарным lifecycle: очищает storage, вызывает source implementation, публикует
полный snapshot либо инвалидирует частичный результат с логом. Mutable
`begin_collection()`/`finish_collection()` закрыты от внешнего кода, поэтому
contract нельзя обойти. Обход `tc_scene`
остался внутри `TcSceneRenderItemSource`/`RenderSceneItemCollector`. Phase
buckets и ownership borrowed payloads нейтральны, а storage lifetime явно
остаётся у caller на всё время execution.

## Роль `PlotScene3D`

Общий renderer не заменяет retained scene. Через interop всё ещё необходимы:

- generation-checked item handles;
- deterministic ownership and destruction;
- stable typed wrappers;
- visibility, ordering and replacement;
- item-local geometry/style revisions;
- bulk `SetData`/append operations;
- named chart parts;
- camera and interaction state;
- item-aware picking identity.

Таким образом, `PlotScene3D` перестаёт быть альтернативным движком и становится
retained composition/model layer над общим renderer. Универсальное имя
`VisualScene3D` имеет смысл только если тот же object model потребуется
нескольким независимым non-chart consumers. До этого plot-specific boundary
остаётся честнее и проще.

## Что происходит с текущим `RetainedChart3D`

Первый retained slice хранил отдельный `PlotEngine3D` как renderer-side body
каждого item. В #1368 surface body удалён, но scatter/grid пока сохраняют этот
временный путь. Он позволил быстро подтвердить stable handles, per-item
revisions и C# API, однако не должен становиться конечной архитектурой:

- каждый item получает тяжёлый engine body;
- дублируются camera, shader и text state;
- порядок surface/grid/scatter зашит в chart render loop;
- grid строится через временную legacy engine model;
- старые global dirty paths остаются внутри каждого body.

После появления scene-neutral core retained items должны создавать generic
RenderItems либо специализированные renderer bodies/encoders. Один pipeline и
один executor обслуживают весь chart. `PlotEngine3D` на item после этого
удаляется без изменения public handles и typed interop API.

## Предлагаемый порядок миграции

### Этап 1. Зафиксировать neutral contracts

- Разделить `ExecuteContext` на scene-neutral core и adapter services.
- Убрать обязательные `TcSceneRef`, `Light`, `Entity` и component identity из
  generic execution/submission contract.
- Ввести нейтральную source identity и immutable RenderItem snapshot boundary.
- Сохранить нынешний scene path через адаптер без параллельного renderer.

Текущее состояние этапа: neutral source identity и immutable snapshot boundary
реализованы в #1359. Удалён неиспользуемый legacy C `tc_execute_context`,
который протаскивал scene/entity types в низкоуровневый pass header.

В #1360 C++ `ExecuteContext` разделён на нейтральный execution context и
явную capability `SceneRenderServices`. Камера и stereo views представлены
нейтральным `RenderViewState`; scene, internal entities, lights и маски
доступны только scene passes через проверяемый service contract. Отсутствующая
capability диагностируется в логе. Scene shader discovery вынесен из
`CxxFramePass` в отдельный `SceneShaderUsageProvider`, поэтому generic pass
interface больше не принимает `tc_scene_handle`.

В #1361 добавлен единый `RenderEngine::execute_pipeline(RenderExecution)`.
Его request содержит только pipeline, targets, заранее опубликованные immutable
snapshots и type-safe `RenderExecutionCapabilities`. Concrete services хранятся
через polymorphic marker contract; неструктурированного `void*` context нет.

`render_scene_pipeline_offscreen()` теперь является отдельным `tc_scene`
adapter: он до входа в executor собирает по одному snapshot и
`SceneRenderServices` на target, удерживает их lifetime до конца execution и
затем вызывает общий executor. Ленивый scene traversal из geometry passes
удалён; pass может только потребовать уже опубликованный snapshot. Generic
executor header не содержит scene, entity или light APIs и покрыт исполнением
probe pipeline без создания сцены.

В #1362 введён явный scene-neutral `RenderItemSource` contract с нейтральными
view/layer/category inputs. `TcSceneRenderItemSource` стал первой production
implementation, а in-memory non-scene source в тесте публикует пустой и
заполненный snapshots для того же `RenderExecution`. Partial publication
инвалидируется и диагностируется. Свободный compatibility helper удалён.

В #1363 `ExecuteContext`, `PipelineRenderCache` и `RenderEngine` переведены с
отдельного `ShadowArrayMap` на общую таблицу `FrameGraphResource`. Cold-path
registry создаёт non-texture resource по явному type descriptor, отклоняет
неизвестные/дублирующиеся kinds и опционально публикует sampled texture для
обычных pass/debugger consumers. `ShadowMapArrayResource`, его factory и
preview callback теперь принадлежат `termin-render-passes`; только
`ShadowPass`/`ColorPass` выполняют typed access.

В #1364 runtime framegraph, pipeline execution, resource tables,
`RenderItemSource`/snapshot/submission и generic task planning получили одного
канонического владельца `termin_render_core`. Его link closure содержит base,
graphics, inspect и materials, но не scene/lighting. `termin_render` теперь
зависит от core и владеет scene traversal, component capabilities, scene
services/execution и graph authoring policy. Заодно из `RenderContext` и
`RenderTask` удалены неиспользуемые `TcSceneRef`/camera/entity/component поля,
которые физически протаскивали scene headers через generic API.

### Этап 2. Выделить `termin-render-core`

- Выполнено в #1364: runtime framegraph, executor, resource tables,
  RenderItem/RenderTask planning и encoder registry находятся в
  `termin_render_core`.
- Scene traversal, component capabilities и scene services остаются в
  `termin_render`; lighting/shadows и concrete engine passes — выше, в
  `termin-render-passes` и component modules.
- Runtime pass inspection adapter остаётся в core как часть pipeline
  deserialization; graph authoring/compiler policy остаётся в `termin_render`.

### Этап 3. Подключить два item source

- `TcSceneRenderItemSource` поверх текущего collector реализован в #1362.
- В #1365 `RetainedChart3D` получил принадлежащий ему
  `PlotScene3DRenderItemSource` без `tc_scene`, entities и components. Source
  публикует tcplot-owned item kinds и value identity из scene id, slot index и
  generation; mutable slot pointers в snapshot не попадают.
- Generic probe pipeline исполняется тем же `RenderEngine::execute_pipeline()`
  над chart snapshot. GPU encoders остаются отдельным этапом 4.
- Lifecycle coverage включает empty source, populated source, slot
  destroy/reuse и два независимо живущих view snapshots.

### Этап 4. Перенести Chart3D rendering

- В #1366 подготовлены snapshot-owned immutable geometry/style/chart-state
  payloads. Тесты подтверждают, что старые snapshots переживают mutation,
  slot reuse и уничтожение source chart без dangling pointers.
- В #1368 surface получил tcplot-owned task shader planner и draw encoder.
  Retained offscreen path планирует surface через `plan_render_item_task()` и
  отправляет через `submit_render_item_draw()`; immutable CPU stream загружается
  общим transient vertex ring, а per-slot surface `PlotEngine3D` удалён.
- Ввести scatter, line, grid and world-text item encoders.
- Переиспользовать существующие shader/material/resource-binding paths.
- Сохранить per-item GPU cache and revision invalidation.
- Добавить chart-specific passes только там, где generic material pass
  недостаточен.
- Подключить color/depth/MSAA и framegraph capture через общий executor.

### Этап 5. Удалить временную архитектуру

- Удалить `PlotEngine3D` renderer body из retained slots.
- Перевести legacy `PlotView3D` на `RetainedChart3D` facade.
- Удалить global dirty meshes и index-based mutation.
- Не сохранять fallback на второй renderer после cutover.

## Риски и ограничения

### Слишком широкий core

Если просто переместить текущий `termin-render` вниз, новый модуль унаследует
scene, inspect, materials, lighting, shadows и Python concerns. Это будет смена
имени, а не улучшение архитектуры.

### Универсальный context через `void*`

Неструктурированный context быстро превратится в скрытую зависимость passes от
конкретного host. Нужны явные capabilities и наблюдаемая ошибка при отсутствии
обязательного service.

### Абстракция только ради chart

Нельзя сначала спроектировать полностью универсальный renderer, а затем
попытаться встроить реальные consumers. Миграцию следует вести двумя
вертикальными slices: существующая engine scene и retained surface chart.

### Потеря specialized performance

Generic RenderItem не означает одинаковую геометрию или один универсальный
shader. Surface/large scatter могут иметь специализированные persistent GPU
bodies и encoders. Общими должны быть lifetime, scheduling и submission
contracts, а не все алгоритмы построения meshes.

### Авторский graph и runtime framegraph

В репозитории есть authoring `GraphCompiler::topological_sort()` и отдельный
runtime `tc_frame_graph` scheduler. Они решают разные задачи, но граница должна
быть явно названа: первый компилирует редакторское graph description в
pipeline template, второй строит runtime resource schedule. Их не следует
случайно объединять в один mutable graph object.

## Критерии успешной границы

Направление можно считать подтверждённым, когда:

- framegraph и generic execution собираются без зависимости на `termin-scene`;
- engine scene продолжает рендериться через адаптер без функциональной
  регрессии;
- retained Chart3D использует тот же executor, resource tables и graphics
  domain;
- chart не создаёт фиктивные entities/components;
- generic passes не получают `TcSceneRef` или lights без явного требования;
- surface/scatter style mutation инвалидирует только соответствующий item;
- camera/viewport changes не перестраивают неизменившуюся geometry;
- framegraph capture/debugger работает для engine scene и chart pipeline;
- временный per-item `PlotEngine3D` удалён;
- через interop по-прежнему доступны stable typed chart parts.

## Итог

Перенос framegraph в более низкий scene-neutral render layer является хорошим
enabler, но не самостоятельным решением. Архитектурно значимый шаг — сделать
существующий renderer потребителем generic RenderItem source, а игровую
`tc_scene` превратить в одного из providers.

В этой модели Termin получает один render framework и несколько retained или
engine-domain object models. `PlotScene3D` обеспечивает удобную поэлементную
interop composition, но не дублирует framegraph, resource management или GPU
renderer.
