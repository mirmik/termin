# Adaptive native UI layout

Дата: 2026-07-31.

Статус: рабочий план.

Связанные карточки доски:

- `#244 [ui/native] Add native UI manager parity layer`;
- `#1136 [ui/native/layout] Deliver adaptive cross-platform layout` —
  authoritative umbrella;
- `#868 [ui/native/metrics] Define presentation metrics and logical document
  space`;
- `#1138 [ui/native/layout] Add generic widget layout spec`.

Связанный runtime contract:

- [Native widget subtree transforms and scalable SceneView portals](2026-08-11-native-widget-subtree-transforms.md)
  добавляет inherited transform внутри logical document space. Это
  отдельный слой от document-wide density/font presentation metrics.

## Цель

Сделать `termin-gui-native` пригодным для одного декларативного UI на desktop,
Android и других плотностях/размерах экрана:

- authoring/layout работают в логических единицах, а не framebuffer pixels;
- плотность дисплея, пользовательский font scale и safe area доходят до UI
  через явный platform-neutral contract;
- layout, text measurement, paint, clips и input используют взаимно обратимые
  logical/physical transforms;
- UiScript выражает ограничения размеров, padding/margin, flex/grid/scroll,
  перенос и ограниченный responsive layout без C++-кода на каждый экран;
- изменение размера, orientation, DPI или font scale вызывает
  детерминированный relayout без stale bounds;
- Android reference UI проверяется в portrait/landscape и при нескольких
  density/font-scale конфигурациях;
- desktop при scale `1.0` сохраняет текущую геометрию, а fractional DPI не
  ломает hit testing, clips и pixel snapping.

План не вводит второй mobile-only widget tree и не масштабирует каждый widget
вручную. Существующие числовые размеры становятся logical UI units; перевод в
physical pixels происходит на presentation boundary.

## Текущее состояние

### Готовая основа

В toolkit уже есть:

- `min/preferred/max` size у `tc_widget`;
- measure/layout split;
- `BoxLayout` с fixed/preferred/flex/stretch, grow/shrink и extent limits;
- `GridLayout` с track policies, limits и spans;
- `OverlayLayout` с fill и corner anchors;
- `ScrollArea`, wrapped `RichTextView`, responsive virtualized file grid;
- `NativeDocumentPainter`, который перед каждым paint раскладывает документы
  по текущему viewport extent;
- один viewport-local input path через `UIComponent`;
- нативный UiScript v2 с registered type facets и транзакционной
  materialization.

Это позволяет развивать существующий layout engine. Отдельный Android UI
toolkit или замена retained document model не нужны.

### Ограничения

Сейчас:

- painter передаёт document физический framebuffer extent;
- UI input приходит в viewport-local physical pixels;
- theme, widget defaults, font sizes, offsets и UiScript `size` трактуются как
  pixel constants;
- platform density, font scale и safe insets отсутствуют в общем display/UI
  contract;
- UiScript v2 поддерживает только небольшой набор widget types и свойств;
- Box/Grid измеряют детей преимущественно unconstrained, после чего сжимают
  готовые extents; текст получает clipping вместо width-dependent reflow;
- отсутствуют generic margin/padding/alignment/length values, flow/wrap layout
  и responsive selectors;
- runtime resize меняет физический viewport, но не logical environment.

На Android это проявляется как корректно нарисованный, но физически слишком
маленький UI.

## Целевые инварианты

### Одна система координат внутри document

Внутри widget tree используются logical UI units.

```text
platform surface and pointer coordinates (physical px)
                         |
                         | presentation metrics
                         v
document layout, bounds, clips and hit testing (logical units)
                         |
                         | density + pixel snapping
                         v
render target (physical px)
```

Desktop scale `1.0` является identity transform. Widget implementations не
знают об Android и не умножают свои константы на density.

Camera/game input продолжает получать исходные physical viewport coordinates.
Обратное преобразование выполняется только на входе в конкретный
`UIComponent`/document presentation, после общего display/viewport routing.

### Presentation-local metrics

Нужен language-neutral value type, условно `tc_ui_presentation_metrics`:

```c
typedef struct tc_ui_presentation_metrics {
    float density_scale;
    float font_scale;
    tc_ui_size physical_extent;
    tc_ui_insets physical_safe_insets;
} tc_ui_presentation_metrics;
```

Из него вычисляются:

- logical viewport extent;
- logical safe rect;
- physical geometry scale;
- physical font size;
- physical/logical pointer transforms.

Metrics принадлежат presentation/viewport, а не являются process-global
настройкой. Один document instance раскладывается для одной presentation
metrics configuration за кадр. Если один asset нужен одновременно в двух
viewport с разными metrics, consumers создают независимые document instances,
что соответствует существующему `UiDocumentAsset` contract.

Некорректные scale/extent/insets отклоняются с логом. Silent fallback на
произвольную density не допускается; desktop host явно использует scale `1.0`.

### Geometry и font scale различаются

Для logical font size:

```text
physical_font_px = logical_font_size * density_scale * font_scale
```

Text measurer измеряет glyphs в physical font pixels и возвращает document
метрики в logical geometry units. Поэтому увеличение accessibility font scale
реально увеличивает занимаемое текстом место и запускает reflow, а не только
растягивает glyphs поверх старых bounds.

Font atlas продолжает растрировать в physical pixels. Cache identity должен
учитывать effective physical size и не создавать новый atlas на каждый кадр.

### Safe area является layout policy

Platform публикует physical safe insets. Presentation преобразует их в logical
safe rect.

Document/root может выбрать:

- `safe_area: respect` — root получает safe rect;
- `safe_area: ignore` — root получает полный logical viewport.

Это позволяет HUD-фону занимать весь экран, а controls размещать внутри safe
area. Android-specific inset arithmetic не попадает в widgets или UiScript
loader.

### Pixel snapping выполняется на render boundary

Logical bounds не округляются во время layout. Final draw geometry, clips и
stroke widths переводятся в physical coordinates одним transform и
согласованно pixel-snapped.

Hit testing использует исходные logical bounds. Render и input transforms
должны быть взаимно обратимы с явно задокументированным правилом rounding для
fractional scales.

## Layout model

### Generic widget layout spec

У `tc_widget` появляется общий layout spec, одинаковый для C, C++ и Python:

- width/height;
- min/max width/height;
- margin;
- alignment по cross axis;
- optional aspect ratio;
- minimum touch target policy.

Length values:

- `auto`;
- logical fixed value;
- `fill`;
- percentage от definite parent extent.

Percentage не участвует в циклическом intrinsic measurement: если parent extent
ещё не определён, значение ведёт себя как `auto`; после появления definite
extent применяется во время constrained measure/layout.

Container-specific padding остаётся свойством container. Box child policy
задаётся на child placement:

- basis/fixed/preferred;
- grow;
- shrink;
- min/max primary extent;
- align self.

UiScript child properties уже передаются parent facet при materialization,
поэтому placement metadata должна храниться у container, а не дублироваться в
widget state.

### Constrained measurement

Layout переходит к последовательности:

1. container получает constraints от parent;
2. definite cross/primary extents передаются детям;
3. width-dependent children измеряются с доступной шириной;
4. grow/shrink распределяет остаток;
5. дети, чья ширина изменилась, получают финальное remeasure по этой ширине;
6. container вычисляет итоговый dependent extent и выполняет layout.

Алгоритм должен быть ограничен фиксированным числом детерминированных проходов,
а не сходиться в неограниченном цикле.

Для scale `1.0` и unwrapped content существующие desktop bounds должны
сохраниться либо измениться только там, где старое поведение было clipping bug.

### Declarative containers

UiScript получает native facets для:

- generic `BoxLayout`/`HStack`/`VStack`;
- `GridLayout`;
- `ScrollArea`;
- width-constrained `Label`;
- `WrapLayout` для flow controls.

Сначала добавляется functional layout contract. Полный визуальный CSS-like
style language в эту работу не входит.

### Responsive variants

Responsive behavior остаётся ограниченным и детерминированным. UiScript не
получает произвольные выражения или platform-specific script callbacks.

Разрешённые selectors:

- min/max logical width;
- min/max logical height;
- portrait/landscape;
- optional compact/medium/expanded width class, вычисленная из logical width.

Variant может переопределять:

- visibility;
- generic layout spec;
- box direction/spacing/padding;
- grid placement;
- safe-area policy.

Base tree остаётся тем же. Variant не уничтожает и не пересоздаёт stateful
widgets при rotation. Для существенно разных композиций допускается
`ResponsiveLayout` с заранее материализованными named branches, из которых
ровно одна участвует в layout/focus/input.

## Platform integration

### Android

`TerminActivity` публикует через JNI:

- `density`;
- `scaledDensity` или нормализованный `font_scale`;
- актуальные `WindowInsets`/display cutout;
- surface extent;
- изменения configuration/insets во время жизни Activity.

Metrics обновляются независимо от surface recreation. Изменение metrics
помечает documents layout-dirty и отменяет stale pointer interaction, если
старый physical/logical transform больше не применим.

Android bootstrap не изменяет координаты camera/game handlers. UI transform
применяется в scene UI presentation/input boundary.

### Desktop

Window adapter получает per-window content scale из `termin-window`, а не из
глобальной environment variable. Moving window между мониторами обновляет
metrics, relayout roots/overlays и font raster sizes.

Linux и Windows являются обязательным baseline. macOS-specific scale source
может быть отдельным follow-up, если backend не предоставляет его в общем
window contract.

### OpenXR

Этот план не определяет физический angular-size UI contract для XR layers.
OpenXR scene UI продолжает использовать явную presentation scale `1.0`, пока
не появится отдельная модель world/angular UI. Общие logical layout и UiScript
возможности при этом доступны без platform fork.

## Этапы

### 1. Metrics и logical document space

- добавить ABI value type и validation;
- передавать metrics в native painter/document layout;
- вычислять logical viewport и safe rect;
- преобразовывать draw commands/clips/text в physical target;
- преобразовывать physical UI input в logical coordinates;
- покрыть scale `1.0`, `1.5`, `2.0`, `3.0`, invalid metrics и rounding.

### 2. Platform metrics bridges

- Android density/font scale/insets/configuration updates;
- desktop per-window content scale и runtime monitor changes;
- lifecycle/resize/focus-cancel tests;
- явный `1.0` contract для hosts без scale source.

### 3. Generic layout spec и UiScript properties

- общий length/layout value model;
- width/height/min/max/margin/alignment;
- container padding;
- box placement grow/shrink/basis/limits;
- parser, compiled asset, reload и C++/Python parity tests.

### 4. Declarative containers

- GridLayout tracks/items/spans;
- ScrollArea content/policies;
- Box orientation и align;
- native width-constrained Label;
- WrapLayout;
- strict diagnostics для некорректных combinations.

### 5. Constrained reflow

- Box/Grid constrained child measurement;
- bounded remeasure после allocation;
- text height from final width;
- scroll content extent after reflow;
- regression tests старых desktop layouts.

Этапы 4 и 5 могут частично выполняться вместе, но wrapped text acceptance не
закрывается до constrained reflow.

### 6. Responsive variants

- deterministic selectors;
- cached active variant from logical metrics;
- property/layout overrides без потери widget state;
- optional ResponsiveLayout branches;
- focus/capture cleanup при смене participating branch.

### 7. Reference migration и gates

- перевести `android-render-showcase` HUD на logical/safe/adaptive properties;
- portrait/landscape phone;
- compact и tablet-like logical widths;
- density `1x/2x/3x`;
- font scale `1.0/1.3/1.5`;
- safe inset/cutout;
- desktop `1.0` geometry compatibility;
- fractional desktop DPI pixel/input smoke;
- package/install/device scenario.

## Порядок зависимостей

```text
UiMetrics contract
        |
        +----> logical painter/text/input transform
                      |
                      +----> Android metrics bridge
                      +----> desktop DPI bridge

generic layout spec
        |
        +----> Box/Grid/Scroll UiScript facets
        +----> constrained measurement
                         |
                         +----> wrapped Label + WrapLayout

UiMetrics + layout properties + reflow
        |
        +----> responsive variants
                         |
                         +----> reference migration and QA matrix
```

Metrics и generic layout spec могут разрабатываться независимо. Android и
desktop bridges не блокируют layout engine unit work.

## Декомпозиция на доске

Umbrella `#1136` остаётся в Backlog. Непосредственно исполняемые корневые
задачи находятся в Ready:

- `#868` — presentation metrics и logical document space;
- `#1138` — общий layout spec для widgets.

Остальные карточки связаны типизированными зависимостями:

- `#1137` — logical scale для painter, text и input, после `#868`;
- `#1139` — Android density, font scale и safe insets, после `#1137`;
- `#1140` — desktop per-window display scale, после `#1137`;
- `#1141` — UiScript Box flex/padding/alignment, после `#1138`;
- `#1142` — UiScript GridLayout и ScrollArea, после `#1138`;
- `#1143` — constrained reflow для Box/Grid, после `#1138`;
- `#1144` — wrapped Label и WrapLayout, после `#1143`;
- `#1145` — responsive variants, после `#868`, `#1141` и `#1144`;
- `#1146` — adaptive HUD в `android-render-showcase`, после `#1139` и
  `#1145`;
- `#1147` — итоговая regression matrix, после platform/layout/reference
  implementation.

## Проверка

### Unit и headless

- logical/physical point, rect, clip и inset transforms;
- text metrics при geometry/font scale;
- hit testing при fractional scale;
- Box/Grid grow/shrink/min/max и constrained remeasure;
- percentage только при definite parent extent;
- wrapped text и ScrollArea content extent;
- variant selection на boundary values;
- state/focus preservation при смене variant;
- malformed UiScript diagnostics.

### Integration

- `NativeDocumentPainter` pixel tests при `1.0`, `1.5`, `2.0`;
- window adapter runtime scale change;
- scene `UIComponent` input consumption после transform;
- Android surface resize отдельно от metrics/insets update;
- package asset round-trip новых UiScript properties;
- Linux SDK и центральный test runner.

### Device/manual

- Android portrait/landscape;
- system font scale;
- navigation/status/cutout insets;
- button touch target и camera coexistence;
- screenshot comparison минимум для phone portrait и landscape.

## Не входит в scope

- semantic screen-reader tree и AT-SPI/UI Automation bridges (`#862`);
- IME preedit/composition и grapheme editing (`#863`);
- simultaneous multi-touch widget gestures;
- CSS cascade/selectors/animations;
- отдельный Android View hierarchy;
- XR angular-size/world-space UI policy;
- автоматическая миграция сторонних UiScript без диагностики;
- legacy fallback на physical-pixel layout.

## Оценка

Для одного разработчика:

- metrics/logical transforms: 5–8 рабочих дней;
- Android/desktop platform bridges: 4–7 дней;
- generic layout spec и UiScript: 5–8 дней;
- constrained reflow и declarative containers: 7–12 дней;
- responsive variants: 4–7 дней;
- migration/QA/docs: 3–5 дней.

Полный scope: примерно 28–47 рабочих дней с учётом platform regressions.
Первый полезный Android milestone — logical units, font scale, safe area и
базовые UiScript layout properties — ожидается после 12–18 рабочих дней.

## Критерий завершения

План закрыт, когда:

- production hosts передают явные presentation metrics;
- layout/paint/input используют logical coordinates и согласованный transform;
- Android density/font scale/safe insets работают без widget-specific hacks;
- UiScript выражает adaptive Box/Grid/Scroll/wrapped layouts;
- responsive variants меняются без потери widget state;
- reference Android HUD проходит portrait/landscape/density/font-scale gates;
- desktop scale `1.0` и fractional DPI tests проходят;
- документация больше не описывает scene UI coordinates как безусловные
  physical viewport pixels.
