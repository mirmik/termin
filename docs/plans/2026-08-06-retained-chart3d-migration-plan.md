# Retained Chart3D migration

Дата: 2026-08-06  
Статус: active

## Контекст

2D vertical slices подтвердили рабочую форму интеграции: chart composition
владеет retained scene, consumer получает typed items и named parts, renderer
заимствует scene/GPU host, а WPF controls живут в portal overlay и вызывают
обычный C# код.

Текущий `PlotEngine3D` этой форме не соответствует. Он одновременно владеет
`PlotData`, camera/input state, одним глобальным dirty bit, GPU mesh caches,
grid generation, surface policy, picking и world-text orchestration. Lines и
scatter объединяются в общие meshes, surfaces адресуются индексами, а ticks и
labels создаются непосредственно во время `render()`.

## Решение

Ввести plot-specific retained model, не создавая преждевременно универсальную
engine-wide `TcVisualScene3D`:

```text
RetainedChart3D
├── PlotScene3D
│   ├── LineSeriesItem3D
│   ├── ScatterSeriesItem3D
│   ├── SurfaceItem3D
│   ├── GridItem3D
│   └── AnnotationItem3D
├── OrbitCamera + interaction controller
├── Chart3DParts
│   ├── Grid
│   ├── Axes
│   ├── TickLabels
│   └── Marker
└── TcVisualScene2D overlay
    ├── Background / title / legend
    └── WPF / termin-gui portal anchors
```

`PlotScene3D` является публичным semantic item registry с generation handles.
Каждый data item владеет CPU data, style revision и geometry revision. GPU cache
принадлежит renderer-side item body и перестраивается только для изменившегося
item. Camera, viewport и overlay changes не инвалидируют series geometry.

## Границы модулей

### `tcplot`

- semantic `PlotScene3D` и stable handles;
- line/scatter/surface retained item bodies;
- chart parts, bounds, camera/controller, picking and annotations;
- plot-specific 3D renderer orchestration;
- C ABI.

### `termin-graphics`

- device/context, buffers, shaders, textures;
- `Text3DRenderer` and `Canvas2DRenderer`;
- backend-neutral clip-space policy.

### `termin-visual-scene`

- только screen-space overlay scene;
- title, legend, callouts, hit regions and portal anchors.

### `Termin.Native` / `Termin.Wpf`

- thin handle wrappers;
- generic color/depth texture presentation;
- WPF portal controls and input routing;
- без chart-specific projection/layout math.

## API direction

```csharp
using var chart = new RetainedChart3D(host, width, height);

SurfaceItem3D surface = chart.Scene.AddSurface(x, y, z, rows, columns);
surface.Shading = true;

chart.Parts.Grid.Replace(customGrid);
chart.Camera.Azimuth = 0.8f;
chart.Overlay.TitleText = "Surface diagnostics";

host.Attach(chart);
host.AddPortal(chart.Overlay.ToolbarAnchor, wireframeButton);
```

Consumers must not receive raw native pointers or index-based identities.

## Этап 1. Vertical retained surface slice

- [x] Ввести `PlotScene3D` generation handle pool.
- [x] Ввести independently versioned `SurfaceItem3D` и `ScatterItem3D`.
- [x] Отделить renderer-side GPU cache каждого item от semantic state.
- [x] Ввести `RetainedChart3D` с public scene, camera and named grid part.
- [x] Переиспользовать текущие surface/scatter mesh builders and shader.
- [x] Рендерить color+depth через заимствованный `GpuHost`.
- [x] Добавить C ABI и thin `Termin.Native` wrappers.
- [x] Добавить WPF example: surface + scatter, replaceable grid,
  wireframe/shading/reset-camera portal buttons with C# callbacks.

Первый slice первоначально использовал отдельный `PlotEngine3D` как временный
renderer-side body каждого retained item. Surface, scatter и grid bodies уже
удалены: immutable payload кэширует CPU draw stream по revisions, а RenderItem
encoders загружают его через transient vertex ring. Grid labels отделены в
chart-owned chrome renderer; public handles и C# API при этом не изменились.

### Интеграция с scene-neutral render core

- [x] `RetainedChart3D` владеет production `PlotScene3DRenderItemSource`.
- [x] Surface/scatter/grid публикуются как tcplot-owned render-item kinds со
  стабильной identity без fake entities/components.
- [x] Empty, multi-view и destroy/reuse snapshots проходят через общий
  `RenderItemSource::publish()` lifecycle.
- [x] Chart snapshot исполняется generic probe pipeline через общий
  `RenderEngine`.
- [x] Snapshot владеет immutable surface/scatter/grid CPU payload; geometry и
  style data разделяются между неизменившимися публикациями и заменяются по
  revision, а chart state копируется по значению. Payload не заимствует slot
  или renderer body и остаётся валиден после destroy/reuse/chart destruction.
- [x] Surface planner/encoder выбирает tcplot3d shader через общий task plan,
  рисует snapshot-owned stream через transient vertex ring, а retained
  offscreen path использует `submit_render_item_draw()` без surface
  `PlotEngine3D` body.
- [x] Scatter planner/encoder сохраняет legacy three-axis cross semantics,
  планируется тем же retained task loop и больше не использует per-item
  `PlotEngine3D` body.
- [x] Grid planner/encoder строит bounds-aware line stream; tick/axis labels
  использует отдельный chart-owned chrome renderer, последний per-item
  `PlotEngine3D` body удалён.
- [x] Добавить chart framegraph output поверх этих kinds: tcplot-owned geometry
  и chrome passes исполняются общим `RenderEngine`, используют external
  color/depth/MSAA target и публикуют pass/resource boundaries для framegraph
  diagnostics/capture.

### Hardening первого slice

- [x] Style mutation заменяет только item-local immutable render data и
  encoder-ready stream, не меняя stable item identity и unrelated items.
- [x] Повторная установка идентичного style является no-op по revisions.
- [x] Style mutation инвалидирует только GPU revision изменённого item.
- [x] `release_gpu()` инвалидирует item GPU revisions, а следующий render
  детерминированно восстанавливает meshes и render targets.
- [x] Ошибочные shading/light/axis-scale значения наблюдаемы через C ABI и
  преобразуются thin C# wrapper в managed exceptions.
- [x] `SurfaceItem3D` и `ScatterItem3D` поддерживают transactional `SetData`
  без замены generation handle; geometry и GPU revisions меняются локально.
- [x] Camera fit/reset учитывает visual axis scale, а отдельный `Fit()`
  сохраняет текущую orbit orientation.
- [x] Retained 3D render target и generic 2D scene renderer поддерживают
  настраиваемый MSAA с детерминированным пересозданием attachments.
- [x] WPF retained hosts приостанавливают `CompositionTarget.Rendering` при
  effective invisibility, включая `Collapsed` ancestor.
- [x] Цвет разреженной data-grid поверхности входит в typed retained style и
  больше не зашит в renderer body.
- [x] Добавлен Vulkan lifecycle/invalidation test для generation handles,
  cross-scene isolation, camera/resize/style/release/render transitions.
- [x] Linux SDK build, central C++/Python test entrypoints и `Termin.Native`
  build подтверждены.
- [ ] Выполнить ручной WPF/D3D11 smoke на Windows.

## Этап 2. Complete series model

- [x] Добавить retained line item со stable handle, transactional data/style
  mutation и generic line-list encoder. Толщина пока входит в typed style и
  revisions, но backend-neutral wide-line rendering остаётся частью доведения
  line series.
- [ ] Дополнить готовые `SetData`/style mutations append API для line/scatter.
- [ ] Добавить bounded streaming/ring-buffer policy.
- [ ] Реализовать visibility/order/removal without global mesh rebuild.
- [ ] Перевести data bounds на incremental scene aggregation.

## Этап 3. Open chart chrome

- [ ] Вынести grid/axes/ticks в named replaceable parts.
- [ ] Сделать world text retained semantic annotations.
- [ ] Вынести title/legend в `TcVisualScene2D` overlay.
- [ ] Добавить projected 3D anchors for callouts and portals.
- [ ] Убрать hard-coded label colors and font sizes из render loop.

## Этап 4. Interaction

- [ ] Разделить camera controller, picking and selection state.
- [ ] Реализовать item-aware picking with stable handles.
- [ ] Исключить полный O(all points) scan там, где нужен spatial index.
- [ ] Маршрутизировать WPF/termin-gui input через общий controller contract.

## Этап 5. Compatibility cutover

- [ ] Перевести `PlotView3D` на `RetainedChart3D` compatibility facade.
- [x] Перевести Python `Plot3D` и `tcplot/examples/demo_3d_*` на detached
  `RetainedChart3D`: данные принимаются до появления GPU, а canonical
  `GraphicsHost` и font atlas присоединяются лениво при первом render.
- [x] Добавить отдельный C# `RetainedChart3DWpfExample`.
- [ ] Перевести оставшиеся C# `PlotDemoApp` 3D examples вместе с legacy
  `PlotView3D` facade.
- [ ] Сопоставить surface colormap, grid, shading, marker and axis scaling.
- [ ] Удалить legacy global dirty mesh state and index-based surface mutation.

## Проверка

- [x] item handle invalidation after removal, slot reuse and cross-scene use;
- [x] changing one surface does not invalidate unrelated items;
- [x] camera orbit does not rebuild geometry;
- [ ] D3D11/Vulkan/OpenGL orientation parity;
- [x] color+depth target resize and deterministic GPU teardown/recovery;
- [x] C# retained wrapper compiles with scene access and part replacement API;
- [ ] portal callbacks and screenshot smoke with asymmetric surface, scatter
  and world labels on Windows/D3D11.

## Первый completion gate

Первый этап считается подтверждённым, когда C# WPF example показывает surface
и scatter, consumer меняет retained surface/grid/camera через typed wrappers,
а три WPF buttons вызывают C# handlers. Camera/style changes не должны
перестраивать неизменившуюся CPU geometry и не должны требовать chart-specific
логики на WPF стороне. Автоматизированная Linux/Vulkan часть gate подтверждена;
для полного закрытия остаётся ручной Windows/D3D11 WPF smoke.
