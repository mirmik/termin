# Open retained chart composer

Дата: 2026-08-06.

Статус: рабочий план, принят для реализации без проектной доски.

Связанные документы:

- [C# Retained Chart Composition](../architecture/2026-07-30-csharp-retained-chart-composition.md);
- [Retained Visual Scene 2D](../architecture/2026-07-27-retained-visual-scene-2d.md);
- [Native SceneView Bridge](../architecture/2026-07-10-native-scene-view-bridge.md);
- [tcplot documentation](https://github.com/mirmik/termin/blob/master/tcplot/docs/index.md);
- [C# tcplot customization](https://github.com/mirmik/termin/blob/master/termin-csharp/docs/tcplot-customization.md).

Этот план уточняет решение от 2026-07-30. Retained chart primitives и
типизированная C#-проекция остаются правильной основой, но стандартная
single/multi-panel композиция и layout не должны существовать только в C#.
Один открытый native composer должен обслуживать C++, C#, WPF и
`termin-gui-native`.

## Цель

Превратить существующие `tcplot` charts из закрытых `PlotView2D` /
`PlotView2DMulti` в открытую retained-композицию:

- `tcplot` предоставляет качественный chart из коробки;
- chart строится как публичное дерево `TcVisualScene`;
- фон, plot area, grid, axes, labels, series, annotations, legend и overlays
  доступны через generation-checked handles;
- потребитель может скрывать, переставлять, заменять и дополнять части без
  расширения setter/RPC API;
- стандартный layout, fit, multi-panel/shared-axis policy и interaction не
  переносятся в Alliance или другой продукт;
- WPF и `termin-gui-native` показывают одну и ту же chart scene через свои
  generic hosts;
- полноценные frontend controls связываются с graphic-item anchors через
  portals и не становятся plot-specific graphic items;
- существующие native GPU series bodies, projection и annotations остаются
  единственным rendering path.

Reference consumer — WPF-приложение Alliance. Миграция считается практически
доказанной только после замены его одиночных trajectory/signal charts и двух
колонок multi-panel telemetry без переноса chart framework в приложение.

## Почему прежний план уточняется

Managed `Termin.Native.Chart2D` доказал, что текущих retained primitives и C ABI
достаточно для сборки полноценного chart. Однако default composer, написанный
только на C#, создаёт две проблемы:

1. C++/UiScript frontend не может переиспользовать его и вынужден писать второй
   layout/composer. Так появился `tcplot-gui-native::Plot2D`.
2. Multi-panel, shared axes, fit, legends, stable series semantics и portal
   hosting рискуют оказаться продуктовым кодом Alliance.

Цель не в возвращении к непрозрачному native `PlotView2D`. Native composer
обязан открыть созданную scene и meaningful parts. C# сохраняет полный доступ
к primitives, но обычный потребитель не реализует chart layout самостоятельно.

## Текущее состояние

### Готовая основа

В `tcplot` и `termin-visual-scene` уже реализованы:

- `TcVisualScene`, generic tree, transforms, clips, opacity, visibility,
  z-order, bounds и hit testing;
- `RectItem2D`, `PathItem2D`, `TextItem2D`, `ImageItem2D`,
  `HitRegionItem2D`, groups и custom retained batches;
- `PlotProjection2D` с compact transactional update;
- `PlotGridItem2D`;
- `PlotLineSeriesItem2D` и `PlotScatterSeriesItem2D`;
- native copied data, incremental append, nearest-point query и persistent GPU
  buffers;
- solid/dash/dot lines, scalar colormaps и scatter rendering;
- `fit_plot_range2d`, tick generation/formatting и native text measurement;
- retained semantic annotations and data markers;
- typed C# wrappers для visual-scene и plot items;
- native open single-panel `RetainedChart2D`, публичные parts и thin C#
  `Chart2D` facade;
- pooled native tick labels без allocation churn при range/layout updates;
- `SceneView` и widget portals в `termin-gui-native`;
- generic WPF retained-scene host, portals и D3D11 texture presentation через
  `Tgfx2D3D11ImageHost`.

`PlotEngine2D` уже использует те же series GPU bodies, что retained items.
Новый renderer для этой миграции не нужен.

### Незавершённые и дублирующиеся пути

- `PlotView2D` и `PlotView2DMulti` остаются monolithic facade с hidden layout и
  offscreen ownership;
- у retained series нет managed/native semantic identity с name, legend и
  data bounds;
- `Chart2D` предоставляет native `Fit`/`FitX`/`FitY`, но ещё не предоставляет
  retained legend и multi-panel composition;
- `tcplot-gui-native::Plot2D` является отдельным упрощённым composer с
  hard-coded layout и immediate chrome;
- `tcplot-gui-native::Plot2D` рисует scene напрямую, минует `SceneView` и не
  поддерживает widget portals;

## Целевые границы модулей

### `termin-visual-scene`

Остаётся plot-neutral:

- scene ownership и graphic-item topology;
- generic items, paint, bounds и hit testing;
- generic scene rendering в draw list/offscreen target;
- никаких series, axes, ticks, fit или chart layout.

### `tcplot`

Владеет plot domain и стандартной открытой композицией:

- retained plot primitives и GPU bodies;
- semantic series model;
- single-panel `RetainedChart2D`;
- reusable internal panel composer;
- `RetainedMultiChart2D` с shared-axis и scrolling policy;
- layout, fit, ticks, labels, legend и chart interaction controller;
- публичная scene и handles meaningful parts.

### `Termin.Native`

Предоставляет тонкую типизированную C#-проекцию:

- lifetime-safe wrappers над native chart/composition handles;
- idiomatic properties и collections;
- доступ к `TcVisualScene2D`, chart parts, series и annotations;
- без второй реализации layout, tick generation или panel composition.

Low-level ручная сборка из `GraphicItemRef2D` остаётся доступна для
нестандартных consumers и тестов primitives.

### `Termin.Wpf`

Владеет frontend hosting:

- generic retained-scene D3D11 control;
- resize/DPI/presentation lifecycle;
- pointer/key forwarding в chart interaction controller;
- WPF portal layer `GraphicItemHandle -> FrameworkElement`;
- focus, capture и WPF control lifetime.

WPF host не знает о line/scatter/ticks и не реализует chart layout.

### `termin-gui-native`

Использует существующий generic `SceneView`:

- chart scene отображается как обычная visual scene;
- `SceneView` widget portals размещают `Button`, `Checkbox`, `ComboBox` и
  другие полноценные widgets по graphic-item anchors;
- portal hit testing имеет приоритет над chart navigation;
- UI core не приобретает зависимости от `tcplot`.

### Product code, включая Alliance

В продукте остаются только:

- выбор и подготовка данных;
- domain names и localization;
- theme tokens;
- выбор стандартной chart policy;
- команды и реакции frontend controls.

Product code не рассчитывает ticks/margins, не синхронизирует projections, не
строит panel virtualization и не ведёт параллельный chart object model.

## Целевая object model

### Scene ownership

`RetainedChart2D` владеет одной публичной `TcVisualScene` и projection.
`RetainedMultiChart2D` также владеет одной scene; панели являются внутренними
композициями в этой scene, а не отдельными offscreen charts.

Scene уничтожает graphic items. Chart deterministic teardown освобождает
projection/series resources и затем scene. Borrowed item/series wrappers не
продлевают lifetime chart.

### Meaningful parts

Минимальный публичный набор:

```text
RetainedChart2D
└── Scene
    └── Parts.Root
        ├── Parts.Background
        ├── Parts.Title
        ├── Parts.PlotArea
        │   ├── Parts.PlotBackground
        │   ├── Parts.Grid
        │   ├── Parts.SeriesRoot
        │   └── Parts.AnnotationsRoot
        ├── Parts.XAxisRoot
        ├── Parts.YAxisRoot
        ├── Parts.LegendRoot
        ├── Parts.ChromeRoot
        └── Parts.OverlayRoot
```

Standard roots и одиночные standard parts имеют stable generation handles на
протяжении lifetime chart. Variable tick-label instances могут использовать
внутренний pool; их identity не является публичным долгоживущим контрактом.

Потребитель может:

- изменить generic presentation properties любого part;
- заменить standard leaf совместимым graphic item;
- удалить необязательный part;
- добавить произвольный item в публичный root;
- изменить порядок и clipping;
- создать portal anchor в overlay/annotation subtree.

Composer не содержит switch по пользовательским concrete item types.

### Semantic series

Raw item handle недостаточен для product-facing API. Нужен стабильный
`ChartSeriesHandle2D` и detached snapshot минимум с:

- stable key/id;
- display name;
- kind: line/scatter;
- visibility;
- style;
- data bounds и revision;
- graphic-item handle;
- legend participation/order.

Series data по-прежнему хранится native. `set_data` и `append` принимают
detached arrays/spans. Pan, zoom, resize, legend toggle и theme update не
переносят точки через ABI.

### Layout and interaction

Standard composer предоставляет:

- explicit range и `fit()` по видимым series;
- `fit_x`, `fit_y` и per-panel fit;
- resize и pixel scale;
- pan/zoom с compact projection update;
- configurable logical padding, fonts и tick spacing;
- legend placement and visibility;
- stable overlay anchor helpers;
- pointer routing/picking, не вызывающий managed callbacks из render path.

Frontend сначала маршрутизирует event в portal/widget layer. Необработанное
событие передаётся chart interaction controller. Rendering остаётся полностью
синхронным native и не вызывает C#/Python.

### Multi-panel

`RetainedMultiChart2D` переиспользует тот же panel composer и series model:

- динамический panel count без unsafe positional access;
- stable panel handles;
- shared X range и independent Y ranges;
- common/individual labels и titles;
- fixed/stretch panel height;
- virtual content extent и scroll offset;
- один scene traversal и один presentation target;
- отсутствие отдельного GPU host/context на панель;
- согласованный layout двух внешних chart instances через shared range/scroll
  state, если продукт показывает time/frequency columns рядом.

## Предлагаемый C# API

Обычный consumer должен оставаться на высоком уровне:

```csharp
using var chart = new RetainedChart2D(host);
chart.Title = "Trajectory";
chart.XAxis.Label = "X";
chart.YAxis.Label = "Z";

var trajectory = chart.Series.AddLine(
    "trajectory", x, z,
    scalar: altitude,
    style: PlotLineStyle2D.Colormapped(PlotColorMap2D.Jet));
var navigation = chart.Series.AddLine(
    "navigation", nx, nz,
    style: PlotLineStyle2D.Dashed(color));
chart.Series.AddScatter("start", startX, startZ, markerStyle);
chart.Fit();

chart.Parts.Grid.Visible = false;
chart.Parts.OverlayRoot.Add(customItem);
```

Portal остаётся API host, а не chart:

```csharp
var anchor = chart.CreateOverlayAnchor(ChartAnchor.TopRight, width: 28, height: 28);
chartHost.AttachPortal(anchor, resetZoomButton);
```

Это illustrative API, не обязательные имена типов. Контракт важнее spelling.

## Этапы реализации

### Этап 0. Зафиксировать baseline и прекратить расхождение

- [ ] Не добавлять новые chart features в `tcplot-gui-native::Plot2D`.
- [ ] Зафиксировать parity inventory `PlotView2D`, `PlotView2DMulti`, managed
  `Chart2D` и Alliance consumers.
- [ ] Зафиксировать performance baselines для large line/scatter и
  multi-panel telemetry.
- [ ] Определить migration/deprecation policy для старых facade API без
  бессрочных fallbacks.

### Этап 1. Native open single-panel composer

- [x] Ввести `RetainedChart2D` и `ChartParts2D` в `tcplot`.
- [x] Собрать standard chart только из public `TcVisualScene` items.
- [x] Перенести managed reference layout в общий native implementation,
  переиспользовав существующие tick/text utilities.
- [x] Представить background, axes, tick marks, labels и title retained items,
  исключив hidden immediate chrome.
- [x] Обеспечить stable handles standard parts.
- [x] Добавить theme/layout value descriptors без закрытого setter explosion.
- [x] Добавить explicit resize/range/pixel-scale mutation.

### Этап 2. Semantic series and fit

- [x] Ввести stable `ChartSeriesHandle2D`.
- [x] Добавить name, visibility, legend policy, item handle и data bounds.
- [x] Реализовать `fit`, `fit_x`, `fit_y` по native bounds видимых series.
- [x] Сохранить `set_data`, `append`, style mutation и nearest query без
  пересоздания item/GPU body.
- [x] Добавить retained legend composition в public `LegendRoot`.
- [x] Не хранить отдельную копию large series data в composer или C#.

### Этап 3. Interaction and annotations

- [x] Отделить reusable `ChartInteraction2D` от WPF/SDL event classes.
- [x] Реализовать pan, anchored zoom и fit/reset через compact chart
  mutations.
- [ ] Реализовать nearest selection через compact chart mutations.
- [ ] Подключить существующие retained annotations к public
  `AnnotationsRoot`.
- [ ] Добавить overlay anchor helpers на основе generic hit-region/group items.
- [x] Гарантировать portal-first input routing в WPF host.

### Этап 4. Thin C# projection

- [x] Экспортировать chart/parts/series C ABI с generation handles.
- [x] Добавить idiomatic wrappers в `Termin.Native`.
- [x] Сохранить доступ к raw `TcVisualScene2D` и typed item wrappers.
- [x] Перевести текущий managed `Chart2D` на native composer либо заменить его
  новым wrapper после migration window.
- [x] Удалить вторую C# реализацию layout/ticks/panel composition.
- [x] Добавить C# example с заменой part и custom overlay
  (`RetainedChartWpfExample`; installed-SDK packaging ещё проверить после
  стабилизации native composer ABI).

### Этап 5. Generic WPF retained-scene host and portals

- [x] Добавить в `Termin.Wpf` control для произвольной retained scene.
- [x] Переиспользовать `Tgfx2Host` и `Tgfx2D3D11ImageHost` presentation path.
- [x] Реализовать resize/DPI и deterministic GPU teardown.
- [x] Маршрутизировать pointer/wheel events в chart interaction controller.
- [ ] Добавить chart-level keyboard shortcuts после определения общего
  frontend-neutral command contract.
- [x] Добавить overlay layer и portal mapping
  `GraphicItemRef2D -> FrameworkElement`.
- [x] Обновлять portal bounds из world bounds после layout/camera changes.
- [x] Сохранять WPF focus/capture/lifetime независимо от graphic-item lifetime.

### Этап 6. Native multi-panel composer

Managed vertical prototype готов в `AllianceStreamingChartsExample`: четыре
компонуемых `Chart2D` используют borrowed shared scene, один renderer/texture,
общий moving X window, независимые Y ranges и WPF portals. Он доказывает
контракт, включая middle-drag pan, cursor-anchored zoom, shared X и
отключаемый follow-latest mode, но не заменяет перечисленный ниже native
composer. Перед Alliance
нужно также отделить дешёвое обновление projection от полного layout/tick-label
rebuild и добавить bounded native streaming/ring-buffer policy.

- [ ] Ввести `RetainedMultiChart2D` поверх общего panel composer.
- [ ] Реализовать stable panel handles и safe dynamic reconfiguration.
- [ ] Реализовать shared X и independent Y ranges.
- [ ] Реализовать panel height, virtual extent и scroll offset.
- [ ] Исключить per-panel offscreen textures/contexts.
- [ ] Добавить coordinated state для двух рядом стоящих charts без product-side
  projection math.

### Этап 7. `termin-gui-native` integration

- [ ] Показывать chart scene через generic `SceneView`.
- [ ] Подключить `Button` и `Checkbox` к chart overlay anchors существующим
  widget portal API.
- [ ] Проверить layout, clipping, z-order, hit testing, focus и destruction.
- [ ] Перевести FEM servo HUD с `termin.gui.Plot2D` на общий retained chart.
- [ ] После удаления последнего consumer удалить
  `tcplot-gui-native::Plot2D`.
- [ ] Если `tcplot-gui-native` после этого не содержит самостоятельной
  необходимой integration policy, удалить модуль целиком; не сохранять пустую
  compatibility shell.

### Этап 8. Legacy facade cutover

- [ ] Перевести `PlotView2D` на `RetainedChart2D` как временный compatibility
  facade.
- [ ] Перевести `PlotView2DMulti` на `RetainedMultiChart2D`.
- [ ] Убедиться, что facade не создаёт второй scene/layout/renderer.
- [ ] Мигрировать first-party examples и tests на новый public model.
- [ ] После migration window удалить hidden-layout setter surface,
  `PlotEngine2D` composition ownership и старые facade types.

### Этап 9. Alliance reference migration

Миграция выполняется после installed-SDK acceptance и не должна использовать
checkout-private headers или DLL.

- [ ] Заменить простой transmitter `PulsePlot` как первый WPF vertical slice.
- [ ] Заменить trajectory charts с colormap, dash, scatter, theme и localized
  labels.
- [ ] Перевести legend toggles на stable series visibility без clear/replot.
- [ ] Добавить хотя бы одну WPF portal button, например reset/fit.
- [ ] Заменить две telemetry columns с 15 panels, shared X, independent Y и
  synchronized scroll.
- [ ] Удалить Alliance-local `Plot2DControl` / `MultiPlot2DControl` chart
  framework code либо свести его к product-specific styling wrapper.
- [ ] Проверить, что Alliance не рассчитывает ticks, plot margins, projection
  или virtual panel layout.

### Этап 10. Документация и удаление переходных решений

- [ ] Обновить архитектурную заметку 2026-07-30: default composition native,
  C# projection thin, manual managed composition optional.
- [ ] Обновить `tcplot`, `termin-csharp`, `Termin.Wpf` и
  `termin-gui-native` live documentation.
- [ ] Удалить документацию старого setter-based API после удаления facade.
- [ ] Перенести итоговые инварианты из этого плана в architecture/module docs.
- [ ] Отметить план завершённым только после Alliance multi-panel cutover.

## Проверки

### Native unit/integration

- lifecycle и stale handles для chart, parts, panels и series;
- replace/remove/reparent standard parts;
- scene/series/projection ownership и cross-scene rejection;
- stable handles после resize, theme, fit, pan и zoom;
- data bounds с empty/NaN/Inf/constant series;
- legend identity и visibility;
- multi-panel shared X, independent Y, reconfigure и scroll;
- portal anchor bounds и destruction;
- отсутствие managed callbacks в paint/GPU execution.

### Rendering and performance

- visual parity для single line, colormap trajectory, scatter и annotations;
- D3D11 WPF pixel/interaction smoke;
- Vulkan/Linux retained scene smoke;
- один 100k line + один 100k scatter без regression относительно текущего
  retained-series baseline;
- append загружает tail, а не полный buffer, где это поддерживается;
- scene snapshot остаётся O(items), не O(points);
- multi-panel resize/scroll не пересоздаёт GPU bodies и не создаёт context на
  панель;
- tick labels reuse/pooling не даёт неограниченного allocation churn.

### Штатные команды

После завершения конфликтующих локальных сборок:

```powershell
.\build-sdk.ps1 --no-sdl --no-vulkan --no-opengl
.\run-tests.ps1
```

Windows C# acceptance использует D3D11-oriented профиль. Linux verification
выполняется штатными `./build-sdk.sh` и `./run-tests.sh`. Ручное копирование
native DLL/.so в source tree не допускается.

## Критерии завершения

План завершён, когда одновременно выполнено следующее:

- один native retained composer является source of truth для standard
  single/multi-panel chart composition;
- C++, C# WPF и `termin-gui-native` используют одну public scene/parts model;
- Alliance не содержит собственной реализации chart layout, ticks,
  projections или panel virtualization;
- meaningful chart parts доступны и заменяемы через stable handles;
- series имеют stable semantic identity, native bounds и legend policy;
- WPF и native GUI controls размещаются через host-owned portals;
- large-series rendering и append performance не регрессировали;
- старые hidden-layout `PlotView2D` / `PlotView2DMulti` удалены;
- отдельный `tcplot-gui-native::Plot2D` удалён;
- переходная managed реализация standard layout удалена;
- live documentation описывает итоговую модель, а не migration state.

## Явно не входит в план

- новый GPU renderer для line/scatter;
- перенос series data или projected vertices в managed memory на каждый frame;
- превращение `Button`/`Checkbox` в plot-specific `GraphicItem`;
- зависимость `tcplot` от WPF или `termin-gui-native`;
- зависимость UI core от `tcplot`;
- бессрочное сохранение двух chart composers ради compatibility;
- автоматический fallback на старый `PlotView2D` при ошибке нового path;
- 3D chart composition; она требует отдельного решения после 2D cutover.
