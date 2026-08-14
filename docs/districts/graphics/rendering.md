# Рендер без сцены

Renderer часто погибает не от нехватки abstractions, а от переизбытка власти.
Он начинает загружать assets, обходить active scene, угадывать application
lifecycle — и через несколько месяцев уже никто не понимает, где заканчивается
GPU и начинается государственное управление.

Graphics проводит границу раньше.

## Слои исполнения

```text
portable data: image / mesh / skeleton / animation / GLB
                              |
                              v
termin-graphics: GraphicsHost + tgfx2 device/context/resources
                              |
                 materials + shader contracts
                              |
                              v
termin-render-core: framegraph + pipelines + immutable render items
                              |
                 explicit targets and capabilities
                              |
                              v
host output / offscreen composition / upper-domain adapter

engine/termin-render: scene traversal, components and Engine policy
```

Последняя строка физически находится за границей Graphics. Она потребляет
render core; render core не вызывает её обратно.

## Один GraphicsHost

`tgfx::GraphicsHost` — канонический владелец application graphics domain:

- `IRenderDevice`;
- `PipelineCache`;
- `RenderContext2`;
- shader resolver;
- interop claim и связанный lifecycle.

Window, WPF, Android или OpenXR adapter может по-разному подготовить platform
device, но передаёт его в один host. Параллельный bundle из ещё одного device,
cache и context — не изоляция, а раздвоение личности приложения.

Standalone и headless tools используют явно названные application/isolated
factories. Consumers получают ссылку на существующий host и не создают
скрытого process-global graphics state.

## Render core принимает снимки, а не мир

`termin-render-core` владеет:

- framegraph execution;
- render pipelines;
- immutable `RenderItemSource` snapshots;
- render-task planning и draw encoder registry;
- material/pipeline contracts;
- shader ABI validation.

Caller публикует neutral render items, передаёт targets и type-safe execution
capabilities. Core executor не обходит `tc_scene`, не ищет entities, не
загружает project и не решает lighting policy.

Unknown resource kinds и невалидные contracts логируются как validation
errors. Они не превращаются молча в framebuffer resource только потому, что
кадру очень хочется закончиться.

## Retained composition рядом, но не внутри

`termin-visual-scene` хранит маленькие retained 2D/3D trees, transforms,
generation handles, painting и hit testing. Он не является ECS и не зависит от
render core. Host может превратить его paint output в draw list или
render-item publication, не добавляя scene semantics в саму visual scene.

`termin-gui-native` владеет widget tree, layout и input routing. Он может
рисоваться offscreen, а optional adapters связывают его с `termin-window`.
Window manager, UI document и application loop остаются тремя разными
владельцами.

`tcplot` и `termin-nodegraph` используют эти primitives как доменные
инструменты. Plot не становится частью GUI core; nodegraph model не становится
виджетом по праву рождения.

## Координаты и capabilities

CPU row 0 и shader `v=0` считаются верхом изображения для всех backend-ов.
Backend исправляет собственные upload/sampling/readback различия внутри
реализации.

Код, которому нужен feature contract, спрашивает
`IRenderDevice::capabilities()` или typed Python capabilities. Диагностическая
строка backend-а годится для лога; она не годится на должность главного
архитектора rendering decisions.

## Где начинается Engine

Если код:

- обходит engine scene;
- знает entities или components;
- выбирает authored scene pipeline;
- связывает render state с assets или lighting;
- решает editor/debug application policy,

то это adapter в `engine/termin-render`, `engine/termin-render-passes` или ещё
выше. Наличие GPU types в public render-facing API не нарушает границу; знание
верхнего мира внутри нижнего executor-а — нарушает.
