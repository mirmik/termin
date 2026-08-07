# Canonical LineRenderer Contract

Дата: 2026-08-07

Статус: Accepted

## Контекст

`LineRenderer` одновременно публикует пять режимов: `WorldBillboard`,
`ScreenSpace`, `WorldMesh`, `RawLines` и `WorldTube`, а также отдельный
совместимый флаг `raw_lines`. За ними стоят четыре разных способа построения
геометрии и два конкурирующих shader contracts.

Direct GPU modes самостоятельно выбирают встроенные vertex shaders и передают
им одну `view_projection`. В Vulkan multiview один draw исполняется для двух
слоёв, поэтому оба глаза получают representative/left-eye transform вместо
выбора через `SV_ViewID`. Ручные fragment/body/cap variants лишь частично
учитывают `MaterialPipelinePassContract` и обходят pass-owned
`VertexOutputAdapter`.

`WorldMesh` проходит через обычный mesh path, но пересобирает CPU mesh при
динамическом обновлении. Его штатный authored line shader также содержит
собственный mono vertex stage и может обойти multiview assembly.

## Решение

Публичный scene-level `LineRenderer` поддерживает один production geometry
contract: объёмную world-space tube с шириной в мировых единицах.

- Tube body и cap используют один line-specific vertex transform provider и
  один собранный shader. Provider строит world-space position и material world semantics, но не применяет
  view/projection.
- Clip-space output принадлежит pass-owned `VertexOutputAdapter`. Mono pass
  использует обычный adapter, multiview pass выбирает per-view frame block по
  `SV_ViewID`.
- Material fragment, surface consumer, depth, ID и shadow composition проходят
  через общий material-pipeline assembler. Line renderer не поддерживает
  параллельный cache или fragment-only shader pipeline.
- Encoder использует запланированные shaders и reflected resource layouts,
  связывает общие material/pass resources и добавляет только line geometry
  streams и line-specific draw resources.
- Неподдерживаемое сочетание pass/contract отклоняется task planner с явной
  диагностикой.

Из публичного component API удаляются `WorldBillboard`, `ScreenSpace`,
`WorldMesh`, `RawLines`, `raw_lines` и `up_hint`. `tube_sides` сохраняется как
параметр качества геометрии единственного contract, а не как выбор renderer-а.

Low-level `ScreenSpaceLineRenderer` и `WorldSpaceLineRenderer` могут оставаться
в `termin-graphics` как unlit debug/overlay primitives. Они не являются
material-bearing scene renderers и не обещают XR multiview. CPU
`line_mesh_builder` остаётся reference/CAD utility. Эти utilities не должны
самостоятельно расширять публичный `LineRenderer` enum.

## Обоснование

Tube geometry не зависит от наблюдателя: одна world-space поверхность
физически согласована для обоих глаз, света и теней. Поэтому существующая
граница `VertexTransformProvider -> VertexOutputAdapter` выражает её без
XR-specific исключений.

Camera-facing billboard технически совместим с final-color/unlit material в
mono pass, но его normal вращается вслед за камерой. Lit/PBR и shadow semantics
получаются нефизичными, а per-eye billboarding требует view-dependent world
geometry, которую текущий provider/adapter ABI намеренно не выражает.
Сохранение billboard как production mode создало бы узкий набор исключений
рядом с каноническим material contract.

`ScreenSpace` является post-projection stroke и по назначению ближе к
debug/overlay rendering. `RawLines` не даёт переносимого wide-line contract.
`WorldMesh` дублирует tube как пользовательский mode и не подходит для
динамического XR ray из-за CPU/resource churn.

## Рассмотренные альтернативы

### Сохранить WorldBillboard только для mono

Отвергнуто для scene-level component. Такой режим пришлось бы ограничить
unlit final-color passes, запретить multiview и shadows и сохранить отдельную
геометрию caps/joins. Low-level debug utility покрывает допустимые применения
без расширения production contract.

### Оставить World и ScreenPixels как два публичных width modes

Отложено за пределы `LineRenderer`. Screen-space displacement зависит от
конкретного view и требует отдельного post-projection contract. При появлении
реального scene-level consumer он должен получить отдельный явно названный
component/API.

### Использовать WorldMesh как канонический путь

Отвергнуто. Обычный mesh pipeline архитектурно корректен для статической
ленты, но динамические сегменты пересоздают mesh, а плоская поверхность зависит
от `up_hint` и может быть видна ребром.

### Сохранить все режимы и добавить multiview variants

Отвергнуто. Это закрепило бы несколько renderer-local shader ABI и размножило
mono/multiview/material/depth/ID/shadow variants вместо одного pass contract.

## Последствия и риски

- Старые сцены с числовым `render_mode` требуют явной миграции; неизвестные
  значения нельзя молча перенаправлять в tube.
- Body и cap остаются отдельными draw calls, но используют один shader usage;
  runtime package должен перечислять его полный closure.
- Quest acceptance требует проверки двух различающихся view matrices, а не
  только layered draw completion.
- Удаление старых enum values является намеренным разрывом active-development
  API.
- Authored static shaders нельзя оставлять неизменными, если pass требует
  несовместимый output adapter, в частности multiview.

## Последующая работа

- Реализовано: tube body/cap используют единый material-pipeline provider и
  один final shader; renderer-local shader variants удалены.
- Реализовано: component/Python API и Quest XR ray переведены на единственный
  tube contract; runtime source closure содержит provider и pass adapters.
- Реализовано: mono/multiview contract tests и Vulkan ID-pass smoke.
- Остаётся аппаратный Quest regression capture с различающимися матрицами
  левого и правого глаз; общий runtime packaging аудит продолжается в #1373.

## Ссылки

- Kanboard: #1376, #1373, #189, #160.
- `termin-components/termin-components-render/src/line_renderer.cpp`.
- `termin-render/src/material_pipeline.cpp`.
- `termin-render-passes/src/color_pass.cpp`.
- `docs/architecture/xr-multiview-rendering.md`.
