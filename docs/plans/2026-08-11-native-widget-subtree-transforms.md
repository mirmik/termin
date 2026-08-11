# Native widget subtree transforms and scalable SceneView portals

Дата: 2026-08-11.

Статус: transform foundation, SceneView portals и termin-nodegraph migration
реализованы; остался renderer-level pixel acceptance и interactive smoke.
Проектная доска для этой работы недоступна.

Связанные документы:

- [Adaptive native UI layout](2026-07-31-adaptive-native-ui-layout-plan.md);
- [Native UIComponent migration](2026-07-30-native-ui-component-migration.md);
- [Native SceneView Bridge](../architecture/2026-07-10-native-scene-view-bridge.md);
- [Retained Visual Scene 2D](../architecture/2026-07-27-retained-visual-scene-2d.md);
- [termin-gui-native porting checklist](2026-07-09-termin-gui-native-porting-checklist.md).

## Контекст

`SceneView` умеет масштабировать retained visual scene, но native widget portal
сейчас получает уже спроецированный screen-space rectangle. Layout увеличивает
только `widget->bounds`; внутренние font size, padding, border, stepper buttons,
caret и другие метрики остаются неизменными. В результате scene labels и
portal controls принадлежат разным визуальным масштабам.

Это особенно заметно в `termin-nodegraph`: при увеличении camera zoom нода,
заголовок, подписи и сокеты растут, а текст и chrome встроенных `SpinBox`,
`ComboBox`, `TextInput` остаются screen-sized. Ограничение диапазона zoom или
ручная подстройка отдельных метрик только скрывает нарушение контракта.

Общий presentation transform из adaptive UI plan решает другую задачу:
logical document units переводятся в physical pixels с учётом DPI и
accessibility font scale. Нужен второй, композиционный уровень — inherited
uniform transform отдельного widget subtree внутри logical document space.

## Цель

Добавить в `termin-gui-native` один согласованный transform contract, чтобы
widget subtree мог масштабироваться и перемещаться как часть retained scene:

- layout и measurement выполняются в стабильных logical units;
- paint geometry, clips, icons и текст получают accumulated subtree transform;
- `FontAtlas` выбирает glyph по итоговому physical font size;
- hit testing, hover, pointer capture и pointer routing используют обратный
  transform;
- popup overlays получают преобразованный document-space anchor, но сами не
  наследуют zoom anchor widget;
- identity transform сохраняет существующую desktop-геометрию и поведение;
- `SceneView` portals перестают растягивать bounds нескейленного widget;
- `termin-nodegraph` использует обычные native controls без специальных
  per-widget zoom hacks.

## Не цели

В первый проход не входят:

- rotation, shear, perspective и non-uniform widget scaling;
- raster-to-texture как основной rendering path;
- анимационная transform system или CSS transforms;
- декларативные transform properties в UiScript;
- изменение accessibility/DPI contract из adaptive UI plan;
- автоматическое сохранение одинаковой screen-space величины inline controls;
- полноценный nodegraph LOD до завершения transform foundation.

Uniform positive scale плюс translation покрывают camera zoom/pan nodegraph и
не требуют заранее проектировать произвольную scene-graph математику в widget
ABI. Unsupported transforms должны диагностироваться явно, а не приблизительно
исправляться набором fallback-веток.

## Системы координат

Нужно различать три пространства:

```text
widget layout space (logical units)
        |
        | accumulated subtree transform: translation + uniform scale
        v
document presentation space (logical units)
        |
        | presentation metrics: density scale + font scale
        v
render target (physical pixels)
```

Обычный document widget использует identity subtree transform. Portal widget
раскладывается в scene/world logical coordinates, а camera `SceneView`
становится его subtree transform в document presentation space.

Widget bounds остаются logical и не округляются. Pixel snapping выполняется
только на render boundary после композиции subtree и presentation transforms.

### Geometry scale и font scale

Для геометрии:

```text
physical_geometry_scale = subtree_scale * density_scale
```

Для текста:

```text
physical_font_px = logical_font_size
                 * subtree_scale
                 * density_scale
                 * accessibility_font_scale
```

Subtree scale не участвует в measure/reflow: это camera presentation zoom.
Accessibility font scale участвует в measurement и может менять layout, как
зафиксировано в adaptive UI plan.

`FontAtlas` не получает заранее растянутую текстуру. Renderer передаёт ему
итоговый `physical_font_px`; bitmap glyphs кешируются по quantized pixel size,
а крупный текст использует существующий SDF path. Метрики baseline/ascent для
paint должны запрашиваться в том же effective physical size.

## Целевой value contract

Минимальный language-neutral тип, условно:

```c
typedef struct tc_ui_uniform_transform {
    tc_ui_point translation;
    float scale;
} tc_ui_uniform_transform;
```

Инварианты:

- translation и scale finite;
- scale строго положительный;
- identity равен `translation = {0, 0}`, `scale = 1`;
- composition и inverse имеют общие протестированные helpers;
- accumulated transform вычисляется по widget ancestry;
- изменение transform помечает layout placement/state/paint dirty, но само по
  себе не запускает intrinsic remeasure;
- transform является runtime presentation state и в первой версии не входит в
  UiScript/document serialization;
- inspect snapshot показывает local и accumulated transform для диагностики.

Имя публичного API выбирается при реализации, но semantics должны оставаться
про transform subtree, а не про специальный `nodegraph_zoom`.

## Draw-list contract

В `tc_ui_draw_command_type` нужны well-nested commands, условно:

```text
PUSH_UNIFORM_TRANSFORM(translation, scale)
POP_TRANSFORM
```

Painter предоставляет соответствующие push/pop functions. Transform stack:

- композируется до presentation metrics;
- применяется к point, rect, radius, stroke width, polyline и texture bounds;
- применяется к clip rectangles в момент push clip;
- умножает effective font size;
- входит в transform вложенного `TC_UI_DRAW_CANVAS2D_LIST`;
- валидируется на balanced scopes в пределах draw-list batch;
- при malformed stack пишет ошибку в лог и не оставляет renderer в
  повреждённом состоянии для следующего batch.

Виджет не должен вручную умножать padding, corner radius или font size на zoom.
Он продолжает эмитить обычные команды в своём logical layout space.

## Widget traversal contract

Transform должен применяться в общих traversal boundaries, а не в каждом
конкретном widget type.

Нужны transform-aware internal helpers для:

- paint widget/subtree;
- hit test child/subtree;
- map point parent-to-child и child-to-document;
- map widget bounds to document presentation space;
- dispatch pointer event каждому route member в его coordinate space.

Containers и document roots не должны напрямую вызывать child vtable в обход
этих helpers. Прямые вызовы нужно найти, перевести и закрыть regression tests,
иначе часть widgets будет выглядеть правильно, но получать неверный input.

Key, text и focus events координат не содержат и transform не требуют. Pointer
capture хранит прежний generation-checked widget handle; на каждом следующем
event координаты переводятся через актуальный accumulated transform captured
widget. Zoom во время capture не должен оставлять stale coordinate mapping.

## Overlay contract

Document overlays остаются в document presentation space и не наследуют
transform anchor widget.

Для `ANCHOR_BELOW`, `ANCHOR_RIGHT` и `match_anchor_width` layout использует не
сырой `anchor_widget->bounds`, а transformed document bounds anchor subtree.
Это даёт ожидаемое поведение:

- закрытый `ComboBox` масштабируется вместе с нодой;
- dropdown открывается рядом с фактическим экранным control;
- dropdown сохраняет нормальный screen-space размер и читаемость;
- viewport clamping и modal/input policy остаются прежними.

Tooltip/context menu используют тот же bounds/point mapping contract. Если в
будущем понадобится zoomed overlay, он должен явно получить собственный
subtree transform, а не неявно наследовать transform anchor.

## SceneView portal contract

После foundation `SceneView` portal хранит прежнюю пару ownership handles:

```text
GraphicItemHandle anchor + tc_widget_handle widget
```

Но reconciliation/layout меняются:

1. scene item предоставляет world bounds anchor;
2. widget получает эти logical world bounds, а не camera-scaled screen bounds;
3. camera translation/zoom назначаются subtree transform portal widget;
4. paint проходит через общий transform-aware widget traversal;
5. portal hit testing переводит document point обратно в world/widget space;
6. overlay anchor mapping возвращает итоговые document bounds.

Portal widget остаётся owned `tc_ui_document`; scene item остаётся owned
`TcVisualScene`. Уничтожение, stale-handle reconciliation, z-order и clipping
сохраняют существующий ownership contract.

В первой версии portal поддерживает axis-aligned world bounds и uniform camera
scale. Rotation/shear graphic-item ancestry не должны молча деформировать
widget: либо anchor трактуется как world AABB по явно документированной policy,
либо association отклоняется с логом. Конкретная policy фиксируется тестом и
обновлением Native SceneView Bridge.

## Nodegraph presentation policy после foundation

Полный zoom не отменяет необходимости LOD. После корректного transform path:

- normal/high zoom показывает полноценные inline editors;
- intermediate zoom может скрывать мелкие stepper buttons и оставлять value;
- low zoom показывает header, основные sockets и связи без неинтерактивной
  мелочи;
- popup editors и context menus остаются screen-space overlays;
- node height, title, labels и editors рассчитываются из одной таблицы rows.

LOD является nodegraph policy и не попадает в generic `SceneView` или widget
core. Пороговые значения выбираются по screenshot/input smoke после реализации
масштабирования, а не зашиваются в foundation plan заранее.

## Этапы реализации

### Этап 0. Baseline и инварианты

- [ ] Добавить headless baseline portal widget при zoom `0.5`, `1`, `2`, `4`.
- [ ] Зафиксировать текущий defect тестом: bounds масштабируются, font/chrome —
  нет.
- [x] Инвентаризировать прямые child paint/hit-test/vtable calls.
- [ ] Зафиксировать identity screenshots и pointer behavior обычных widgets.
- [ ] Измерить baseline FontAtlas pressure при wheel zoom nodegraph example.

### Этап 1. Uniform transform value и draw-list scopes

- [x] Добавить validated uniform transform C ABI/value helpers.
- [x] Добавить painter push/pop transform commands.
- [x] Реализовать stack composition в `UiDrawListRenderer`.
- [x] Применить transform ко всей geometry, clips, icons, textures и nested
  `DrawList2D`.
- [x] Включить accumulated scale в physical font size и FontAtlas lookup.
- [ ] Покрыть identity, nested composition, fractional scale, malformed scopes
  и DPI composition unit tests.

### Этап 2. Transform-aware widget traversal

- [x] Добавить runtime subtree transform widget state/API.
- [x] Централизовать root/child paint через transform-aware helper.
- [x] Перевести containers и custom/Python widgets с прямых child calls.
- [x] Добавить local/accumulated transform в inspect snapshots.
- [ ] Проверить, что identity path не меняет существующие draw commands кроме
  согласованного представления scope.

### Этап 3. Hit testing, routing и capture

- [x] Добавить inverse point mapping через widget ancestry.
- [x] Сделать root/container/portal hit testing transform-aware.
- [x] Преобразовывать pointer coordinates отдельно для каждого bubbling route
  member.
- [x] Сохранить focus, pressed, hover и capture semantics.
- [x] Проверить transform change во время active capture и deterministic cancel
  при detach/destroy.
- [ ] Покрыть checkbox, spin buttons, text selection/caret drag и nested
  transformed subtree tests.

### Этап 4. Overlay anchors

- [x] Ввести единый helper transformed widget bounds in document space.
- [x] Перевести anchored overlays и `match_anchor_width` с raw bounds.
- [ ] Проверить ComboBox dropdown, menu, tooltip и viewport edge flipping.
- [x] Оставить overlay content screen-sized, если ему явно не назначен свой
  transform.

### Этап 5. SceneView portal migration

- [x] Перевести portal layout с projected screen bounds на world logical bounds
  плюс subtree camera transform.
- [x] Сохранить portal-first input routing, z-order, clipping и lifetime.
- [x] Удалить старый bounds-only scaling path без compatibility fallback.
- [x] Обновить C++ и Python portal tests.
- [ ] Обновить Native SceneView Bridge и `termin-gui-native` README.

### Этап 6. termin-nodegraph migration

- [x] Удалить zoom-specific ограничения и metric hacks.
- [x] Свести header/socket/parameter rows к одной layout model.
- [x] Выровнять labels по shared row baseline/center contract.
- [ ] Проверить `SpinBox`, `ComboBox`, `TextInput`, checkbox и popup при всём
  поддерживаемом zoom range.
- [ ] Добавить LOD policy отдельным изменением после визуального acceptance.
- [x] Обновить native nodegraph example и screenshot smoke.

### Этап 7. Cleanup и acceptance

- [ ] Удалить временные portal/layout обходы и stale comments.
- [x] Обновить adaptive UI plan ссылкой на subtree transform distinction.
- [ ] Выполнить центральные native/Python tests и SDK build.
- [ ] Провести Windows interactive nodegraph smoke.
- [x] Зафиксировать итоговый transform contract в живой architecture docs.

## Проверка

### Unit

- composition/inverse uniform transforms;
- invalid, zero, negative и non-finite scale diagnostics;
- point/rect/clip/stroke/radius transforms;
- physical font size при combinations subtree zoom, density и font scale;
- balanced/unbalanced draw transform scopes;
- transformed nested widget hit testing;
- bubbling coordinates в coordinate space каждого handler;
- capture после transform update;
- transformed overlay anchor bounds.

### Integration и pixel tests

- portal `Checkbox`, `SpinBox`, `ComboBox`, `TextInput` при zoom
  `0.5`, `1`, `1.5`, `2`, `4`;
- DPI `1`, `1.5`, `2` в сочетании с portal zoom;
- sharp text после settled frame без raster-texture blur;
- glyph availability и repaint после первого on-demand atlas upload;
- clip portal на границе `SceneView`;
- ComboBox popup у всех viewport edges;
- nested `TC_UI_DRAW_CANVAS2D_LIST` под active widget transform;
- identity screenshots обычного showcase.

### Manual

- wheel zoom под курсором без прыжка portal controls;
- click/drag spin buttons на увеличенной и уменьшенной ноде;
- text caret, selection, submit и focus traversal;
- открыть/выбрать/закрыть ComboBox после pan и zoom;
- zoom во время focused editor и active capture;
- collapsed/LOD node behavior;
- проверка отсутствия title/label/editor overlap.

## Производительность и font-atlas pressure

Основной path остаётся retained redraw, а не texture scaling. До оптимизаций
нужно измерить:

- число реально запрошенных bitmap font sizes при wheel zoom;
- atlas occupancy и upload count;
- CPU time glyph bake и draw-list lowering;
- settled-frame sharpness и latency.

`FontAtlas` уже quantizes display size до integer pixels и переводит крупный
текст на SDF. Если реальные traces покажут чрезмерное заполнение atlas,
следующим отдельным решением может стать ограниченное size bucketing, более
ранний SDF path для transformed text или краткоживущий gesture cache. Нельзя
заранее превращать raster-to-texture в основной rendering contract.

## Риски

### Частичная transform-awareness

Самый опасный результат — widget рисуется масштабированным, но hit testing,
capture или popup остаются в старых координатах. Поэтому paint-only этап не
считается consumer-ready и не подключается к nodegraph до завершения этапов
3–5.

### Смешение presentation и subtree scale

DPI/font-scale меняют presentation и accessibility layout; camera zoom не
должен запускать reflow. Эти scale factors хранятся и тестируются раздельно,
композируясь только на render/input boundaries.

### Прямые vtable calls

Существующие containers или custom widgets могут обходить общий traversal.
Инвентаризация и запрет таких вызовов являются обязательной частью foundation,
иначе transform будет зависеть от concrete widget type.

### Overlay regressions

Anchored overlays сейчас читают raw widget bounds. Миграция должна быть общей;
специальный ComboBox workaround оставит tooltip/menu с тем же дефектом.

### Atlas churn и первый кадр

Новые physical font sizes создаются lazily. Нужны измерения, bounded policy при
доказанной проблеме и гарантированный repaint после atlas update. Нельзя
замалчивать missing glyph или принимать второй случайный кадр как контракт.

## Точка завершения

План считается выполненным, когда:

- `termin-gui-native` имеет документированный uniform subtree transform;
- identity widgets проходят прежние layout/input/pixel tests;
- portal controls визуально и интерактивно совпадают с scene anchor при zoom
  `0.5–4` и DPI `1–2`;
- text glyph выбирается по composed physical size и остаётся резким в settled
  frame;
- ComboBox popup правильно привязан и остаётся screen-space;
- `termin-nodegraph` не содержит zoom clamp или per-control scaling hacks;
- header, labels и editors не перекрываются в native example;
- центральные тесты, SDK build и Windows interactive smoke пройдены;
- живые architecture docs описывают новое итоговое состояние.
