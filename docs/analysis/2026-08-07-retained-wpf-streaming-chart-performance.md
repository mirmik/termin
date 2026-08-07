# Производительность retained WPF streaming charts

Дата: 2026-08-07

## Контекст

`AllianceStreamingChartsExample` моделирует целевую нагрузку Alliance:

- две колонки `MultiChart2D` по 15 панелей;
- 60 streaming line series, включая styled/dashed линии;
- две native retained scenes, два offscreen render target и два WPF
  `D3DImage` presentation path;
- общий moving X, независимые Y, синхронный scroll и WPF portal controls;
- период данных 40 мс (25 Гц), MSAA x2.

Цель анализа — убрать заметные задержки UI, не перенося chart layout,
projection math или GPU ownership в Alliance/C#.

## Уже реализовано

### Streaming и scheduling

- Solid и styled line append загружают только изменившийся GPU tail.
- `RetainedScene2DHost` поддерживает opt-in on-demand rendering через
  `ContinuousRendering = false` и `RequestRender()`.
- WPF interaction adapters запрашивают кадр после navigation/scroll.
- Пример рендерится с MSAA x2.

### Moving X

Для видимых multi-chart panels добавлена X-only invalidation. Moving X
обновляет projection, grid, X axis и X labels, но не повторяет полный layout,
измерение текста, Y chrome, legend и background geometry.

Измеренный managed update после начала moving window:

- до 20 секунд: примерно 0,2–0,3 мс/tick;
- после 20 секунд: примерно 0,6–0,8 мс/tick.

Следовательно, `Append + SetSharedX` не является основным источником UI lag.

### Render telemetry

Добавлена раздельная телеметрия:

- managed append;
- shared-X update;
- native scene paint;
- draw-list freeze;
- CPU command submission (`submit`, не GPU timestamp);
- D3DImage present;
- WPF portal update;
- total per host и приблизительный total пары.

До оптимизации visual-scene traversal наблюдались:

```text
paint 6.00 ms/host
freeze 0.00 ms/host
submit 3.86 ms/host
present 4.32 ms/host
total 14.28 ms/host
pair 28.17 ms
```

### Visual-scene paint path

Реализованы:

- order revision, изменяющаяся только при
  adopt/replace/destroy/reparent/z-order mutation;
- кэш отсортированного дерева roots/children между кадрами;
- отсутствие draw commands для identity transform и unit opacity;
- повторное использование command-list storage renderer-ом;
- постоянные retained batch objects у line/scatter series вместо per-frame
  allocations.

После этих изменений WPF telemetry показывает:

```text
paint 0.10 ms/host
submit 3.94 ms/host
total 7.66 ms/host
pair 15.10 ms
```

`paint` уменьшился примерно в 60 раз, а парный render time — почти вдвое.
Субъективно UI стал явно лучше, но небольшая рваность сохранилась.

## Текущий диагноз

Средняя CPU-стоимость пары теперь укладывается в 40-миллисекундный data tick,
однако остаются две причины визуальной неровности.

### Несогласованный cadence

25 Гц не делятся на типичные 60 Гц display composition. Кадры данных попадают
на display с чередованием интервалов около 33 и 50 мс. Даже при нулевой
стоимости renderer это выглядит как неравномерное продвижение moving window.

### Малый запас внутри одного display frame

`pair ≈ 15,1 ms` близко к бюджету одного 60-Hz frame (`16,67 ms`). Небольшой
spike в submit/present, GC, WPF layout или input способен пропустить vsync.
Среднее значение этого не показывает.

Почти вся оставшаяся стоимость находится в CPU command submission и двух
D3DImage presents; `paint`, `freeze` и portals теперь несущественны.

## План дальнейшего улучшения

### 1. Composition-aligned 30 Гц

Заменить synthetic `DispatcherTimer` на composition clock:

- слушать `CompositionTarget.Rendering`;
- использовать фактический `RenderingTime`, а не прибавлять фиксированные
  `0.04`;
- обновлять synthetic data и moving X каждый второй composition frame;
- не допускать двух update/render за один composition timestamp;
- сохранить on-demand rendering hosts.

Цель — стабильные 30 Гц на 60-Hz display без паттерна 33/50 мс. Это изменение
относится к example scheduling; production consumer должен отделять cadence
поступления данных от cadence представления.

### 2. Tail latency telemetry

Средних значений недостаточно. Для каждого секундного окна добавить:

- p50, p95 и max для submit, present и total;
- число composition frames;
- число фактически отрисованных пар;
- число missed/late frames относительно текущего display interval;
- разницу frame counts левого и правого hosts.

Сбор статистики должен использовать bounded preallocated storage либо online
quantile estimator и не создавать per-frame GC pressure.

### 3. Проверка scheduling результата

Acceptance для шага cadence:

- визуально равномерное продвижение wave/window;
- p95 пары уверенно ниже одного display interval;
- отсутствие систематической разницы frame count между колонками;
- input остаётся отзывчивым во время streaming и scroll;
- MSAA остаётся x2.

### 4. Один render/present для coordinated charts

Если 30 Гц и tail telemetry подтвердят submit/present bottleneck, спроектировать
group renderer/host:

- несколько retained scenes рисуются в один shared render target;
- для пары выполняется один begin/end frame и один D3DImage present;
- каждой сцене задаётся собственный viewport/clip;
- public scene ownership и customization остаются независимыми;
- WPF portals получают mapping из scene-local framebuffer coordinates в общий
  host;
- `MultiChart2DGroup` не превращается в chart-specific WPF layout layer.

Ожидаемый эффект — убрать один D3DImage present и часть повторного command
submission/state setup. Это архитектурное изменение, поэтому его следует
делать только после измерения p95/max.

### 5. Submit-path profiling

Если command submission останется дорогим даже при одном present:

- посчитать commands/draw calls/state changes/text batches на frame;
- измерить Canvas2D vertex/index uploads;
- проверить batching соседних solid/path/text commands;
- отделить CPU recording от driver wait в `end_frame`;
- при необходимости добавить D3D11 timestamp/disjoint queries для настоящего
  GPU time без выдачи CPU submit за GPU duration.

### 6. Native bounded streaming buffer

Независимый performance tail остаётся в data lifetime:

- текущий пример хранит 3000–6000 managed points на series;
- одновременная compaction всех 60 series вызывает `RemoveRange + ToArray +
  SetData` и потенциальный периодический spike;
- production path нужен native bounded/ring buffer с сохранением tail-upload.

Этот шаг не объясняет текущую постоянную рваность на коротком запуске, но нужен
до Alliance cutover для стабильной длительной работы.

## Не делать без измерений

- Не отключать MSAA x2 как постоянный workaround.
- Не переносить layout/projection/ticks в C#.
- Не вводить continuous 60-Hz rendering двух hosts: текущие ~15 мс на пару
  оставляют слишком мало запаса на 60 Гц.
- Не кэшировать вслепую весь draw list без корректной content invalidation:
  X chrome и built-in text/path commands владеют snapshot-данными.
- Не называть CPU submit настоящим GPU time.

## Состояние проверки

На 2026-08-07 собраны `termin_graphics2`, `termin_visual_scene`, `tcplot`, C#
plot-D3D11 SDK и WPF example. Headless D3D 2x15 smoke и контрольный запуск WPF
прошли. Полный test suite намеренно не запускался параллельно другой работе над
сборкой.
