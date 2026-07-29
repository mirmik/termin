# Native UIComponent migration

Дата: 2026-07-30.

Статус: план.

Связанный umbrella доски: `#244 [ui/native] Add native UI manager parity layer`.

## Цель

Сделать `termin-gui-native` единственной реализацией scene UI:

- `UIComponent` является нативным C++ scene component и работает в runtime без
  Python;
- UI document, widget tree, layout, paint и input routing принадлежат
  `termin-gui-native`;
- `UIWidgetPass` является одним нативным pass на desktop, Android и OpenXR и
  действительно рисует scene UI;
- `.uiscript` загружается и материализуется нативно;
- UI assets экспортируются в runtime package и создают независимый document
  instance для каждого компонента;
- Python API, если он нужен инструментам, является тонким binding над теми же
  C++ объектами, а не второй реализацией;
- старые `tcgui`-реализации `UIComponent`, `UIAsset`, `UIHandle` и
  `UIWidgetPass` удалены после cutover.

Физическое удаление всего `termin-gui/tcgui` не входит в этот план: у него
остаются отдельные consumers — CSG, tcplot/nodegraph adapters и внешний
Diffusion Editor. Здесь закрывается именно scene UI path.

## Текущее состояние

### Что уже готово

`termin-gui-native` уже содержит:

- `tc_ui_document` и generation handles;
- нативное retained tree, layout, focus, capture, overlays и input routing;
- широкий каталог C++ widgets и эквивалентные typed Python bindings;
- backend-neutral draw list и `UiDrawListRenderer`;
- registered widget factories и versioned document serialization;
- transactional restore, inspect snapshots и owner hot reload;
- headless/offscreen и windowed rendering paths.

Это достаточная основа. Общие задачи accessibility, DPI и IME важны для
зрелости toolkit, но не должны блокировать первый scene UI cutover. IME и
полноценный text-input являются отдельным acceptance gate для текстовых
контролов, а не для pointer-driven HUD.

### Что остаётся Python или является заглушкой

- `termin.ui_components.UIComponent` наследуется от `PythonComponent`;
- `UIComponent` создаёт `tcgui.widgets.UI`, владеет Python widget tree и
  обрабатывает mouse events в Python;
- desktop `UIWidgetPass` является `PythonFramePass`;
- Android `UIWidgetPass` только делает `blit(input, output)` и не рисует UI;
- `UIAsset` хранит живой `tcgui.Widget`, а `UIHandle` возвращает Python object;
- `UIImportPlugin` и `UIRuntimePlugin` создают Python asset;
- native `UiScriptLoader` версии 1 сам написан на Python и поддерживает только
  небольшой editor-camera subset;
- `DocumentRenderer` рассчитан на composition root: он владеет color target и
  сам вызывает `begin_frame/end_frame`. Его нельзя вызывать из открытого
  engine framegraph pass.

## Целевые инварианты

### Один runtime object graph

Scene UI использует только `tc_ui_document` и `tc_widget`. Не допускаются:

- параллельные `tcgui.Widget` и native widget trees;
- adapter, зеркалирующий изменения между двумя деревьями;
- Android fallback на пустой pass;
- автоматическое возвращение к Python loader при неизвестном widget type.

Неизвестный или недоступный runtime widget type должен давать
диагностическую build/load error.

### Владение

```text
UiDocumentAsset
    immutable validated document recipe
    UUID + version + dependency list
            |
            | instantiate transactionally
            v
UIComponent (scene, CPU ownership)
    owns tc_ui_document
    owns instantiated roots and stable named bindings
    owns asset reference, priority and input policy
            |
            | borrowed document capability
            v
SceneUiCompositor (termin-render-passes, GPU ownership)
    owns font atlas / draw-list renderer / device caches
    borrows RenderContext2 and framegraph output
            |
            | uses toolkit renderer without scene/framegraph dependency
            v
NativeDocumentPainter (termin-gui-native)
            |
            v
native UIWidgetPass
```

`UIComponent` не владеет `GraphicsHost`, render device, framegraph texture или
application loop. GPU resources принадлежат compositor/render domain и
освобождаются до shutdown устройства.

UI asset не хранит уже созданный widget tree. Один asset может использоваться
несколькими компонентами; каждый компонент получает независимый document
instance с независимыми focus, hover, values и lifetime.

### Граница между component и pass

В `termin-components-ui` вводится component capability, например
`scene_ui_document`. Capability предоставляет:

- borrowed `tc_ui_document_handle`;
- render priority;
- current asset/document revision;
- enabled/visibility и stable component identity;
- notification/invalidation contract для уничтожения и reload.

`UIWidgetPass` и input routing работают по capability, а не делают
`dynamic_cast<UIComponent>` и не зависят от Python registry.

### Формат UI asset

`.uiscript` остаётся authoring format, но получает нативный parser и
материализатор на `tc::trent`/native YAML parser.

Нужно выбрать один versioned schema и не поддерживать два похожих DSL:

- расширить native `uiscript` до версии 2;
- типы разрешаются через registered native widget factories;
- common properties задаются общим schema;
- widget-specific properties задаются registered metadata/state hooks;
- source validation происходит до создания widgets;
- materialization и reload транзакционны;
- compiled runtime payload содержит нормализованный document recipe и список
  widget type dependencies.

Существующий ограниченный `uiscript: 1` либо мигрируется явным converter, либо
отклоняется после однократной миграции repository assets. Долгий silent
compatibility fallback не нужен.

Python-defined widgets остаются допустимы для Python-enabled tool documents,
но runtime package для Android/OpenXR обязан отклонять asset, содержащий
Python widget factory. Cross-platform scene UI baseline состоит только из
нативно зарегистрированных types.

### Рендеринг внутри framegraph

Из `DocumentRenderer`/`UiDrawListRenderer` выделяется presentation-neutral
операция `NativeDocumentPainter`, принадлежащая `termin-gui-native`:

```cpp
paint_documents(
    RenderContext2& context,
    int width,
    int height,
    span<UiDocumentSubmission> documents
);
```

Она:

- не вызывает `begin_frame/end_frame`;
- не знает о framegraph и не создаёт presentation target;
- рисует в уже открытый caller-owned render pass;
- выполняет layout и paint документов в размере viewport;
- сортирует documents по priority и стабильному component identity;
- логирует и пропускает только конкретный невалидный document, не скрывая
  системную ошибку pass;
- хранит GPU caches в render domain и сбрасывает их при смене устройства.

`SceneUiCompositor` в `termin-render-passes` адаптирует эту операцию к
framegraph: выбирает attachment/load semantics, при необходимости переносит
distinct input в output и не делает лишний `blit` для inplace alias. Таким
образом `termin-gui-native` не получает зависимость от scene или framegraph.

`DocumentRenderer` для standalone/windowed UI должен использовать ту же
низкоуровневую compose primitive, чтобы scene path не стал второй
реализацией renderer.

### Input

Нативный `UIComponent` реализует `InputHandler` и принимает нормализованные
viewport events:

- pointer id, device kind, down/move/up/cancel и click count;
- mouse compatibility events;
- wheel;
- key и committed text;
- focus/capture loss.

Координаты переводятся из display/viewport space в document-local space один
раз. Routing использует native document focus/capture model. `handled`
возвращается в общий Termin input pipeline, чтобы UI с большим priority
останавливал camera/game controller.

Clipboard, cursor и text-input activation идут через platform services,
заимствованные у display/input manager. `UIComponent` не обращается к SDL или
Android API напрямую.

Текущий `tc_input_vtable` не несёт committed text и IME composition. Pointer,
wheel и key routing можно завершить независимо; полная поддержка
`TextInput`/`TextArea` требует расширения общего input ABI и связана с #863.

## Этапы

### 1. Нативный UiScript и immutable asset recipe

Перенести parser, validation registry и materialization из
`termin.gui_native.uiscript` в C++.

Результат:

- native `UiScriptDescription`/recipe;
- schema v2 для общего и type-specific state;
- native parse/load API и тонкие Python bindings;
- deterministic structural diagnostics;
- transactional materialization;
- тесты malformed input, duplicate names, unknown types, rollback и
  независимых instances.

Python loader удаляется после перевода editor camera script и UI asset tests.

### 2. Нативный UI asset и runtime package

Добавить `UiDocumentAsset` и generation-safe handle/registry:

- UUID, source identity, version, compiled recipe и widget dependencies;
- editor import/reload;
- package exporter и manifest entry;
- native runtime loader до scene deserialization;
- строгая проверка доступности native widget factories;
- component inspect kind для выбора asset.

Hot reload сначала строит новый document целиком и только затем атомарно
заменяет старый instance. Ошибка сохраняет прежний работающий document.

### 3. Встраиваемый native compositor

Выделить общую compose primitive, которая рисует native document в borrowed
`RenderContext2`/framegraph target.

Проверить:

- inplace и distinct input/output;
- несколько документов и стабильный priority;
- resize/layout;
- font and texture commands;
- OpenGL, Vulkan и D3D11 headless/pixel smoke;
- отсутствие собственного frame lifecycle;
- deterministic GPU cleanup.

### 4. C++ UIComponent

Превратить `termin-components-ui` в полноценный CMake module:

- `UIComponent : CxxComponent, InputHandler`;
- native type registration под существующим именем `UIComponent`;
- inspect fields `ui_layout`, `priority` и input source policy;
- CPU-only document ownership;
- asset instantiation/reload;
- scene UI capability;
- deterministic destroy/removal;
- Python binding с asset/document handles, но без `tcgui.Widget`.

Прямое присваивание произвольного Python widget в `component.root` не
сохраняется как cross-platform API. Tool-only Python widgets добавляются в
document через официальный multilingual native contract.

### 5. Один native UIWidgetPass

Сделать C++ `UIWidgetPass` общим для всех платформ:

- убрать `#if __ANDROID__` и placeholder semantics;
- собирать scene UI capabilities;
- применять enabled/layer/internal-entity filtering;
- стабильно сортировать submissions;
- вызывать compositor;
- регистрировать один и тот же pass type на desktop/Android/OpenXR.

После этого удалить Python `UIWidgetPass` и его bootstrap registration.

### 6. Viewport input bridge

Подключить native component к выбранному viewport input manager:

- pointer/touch/cancel/capture;
- mouse, wheel и key;
- корректные viewport-local coordinates;
- priority и handled propagation;
- focus cleanup при component/scene/display teardown;
- clipboard/cursor/text-input platform services.

Отдельный подпункт расширяет common input ABI для committed text и затем IME.
До него pointer-driven HUD считается поддержанным, но текстовые редакторы не
объявляются полностью готовыми.

### 7. Editor workflow и asset migration

Перевести:

- UI asset inspector и picker;
- scene component inspector;
- native preview/debug snapshot;
- save/load и undo/redo asset reference;
- file watcher и transactional live reload;
- существующие repository `.uiscript`.

Editor должен показывать parse/type/materialization diagnostics с source path,
а не оставлять пустой UI.

### 8. Android/OpenXR и packaged-runtime gate

Добавить reference HUD в Android render showcase:

- native `.uiscript`;
- button/label/overlay;
- touch hit, handled propagation и camera coexistence;
- rotation/resize;
- build/package/install smoke.

Runtime package validation должна падать до запуска при Python-only widget
type, отсутствующем native factory или неэкспортированном UI asset.

OpenXR использует тот же component/pass/compositor; platform-specific
устройства дают только normalized pointer/ray events.

### 9. Cutover и удаление legacy path

После desktop и Android gates удалить:

- Python implementation `termin.ui_components.component`;
- Python `UIWidgetPass`;
- Android blit placeholder;
- `tcgui`-based `UIAsset`/`UIHandle` implementation;
- зависимость `termin-components-ui -> tcgui`;
- `tcgui` dependencies из package closure, которые существовали только ради
  scene UI;
- compatibility tests старой object-tree семантики.

Оставшийся `termin.ui_components` Python namespace может экспортировать только
native bindings. Никакой runtime fallback на legacy loader/pass не остаётся.

## Порядок зависимостей

```text
native UiScript + asset recipe ──> native UIComponent ──┐
                                                       ├─> native UIWidgetPass
embedded compositor ────────────────────────────────────┘

native UIComponent ──> viewport input bridge

asset recipe + component ──> editor workflow

pass + input + package assets ──> Android/OpenXR gate

all gates ──> legacy deletion
```

Этапы 1 и 3 можно выполнять независимо. Нельзя начинать legacy deletion до
прохождения packaged native runtime.

## Проверка

### Unit/contract

- C++ UiScript parse/validation/materialization and rollback;
- asset instance independence and hot-reload rollback;
- component registration/serialization/lifetime;
- scene UI capability iteration and stable ordering;
- input coordinate conversion, capture cancellation and handled propagation;
- compositor draw-list and target-load semantics.

### Integration

- native player loads scene + UI asset without importing `tcgui`;
- desktop framegraph renders two UIComponents in priority order;
- resize updates layout;
- UI consumes pointer before OrbitCameraController;
- component removal releases document state, render shutdown releases GPU
  state;
- package validator rejects Python-only widget dependencies.

### Platform

- Linux Vulkan and OpenGL pixel/headless smoke;
- Windows D3D11 build and pixel smoke;
- Android arm64 build/install/manual touch smoke;
- OpenXR smoke when the same scene UI path is enabled.

## Definition of done

- `UIComponent` и `UIWidgetPass` не являются Python classes;
- packaged Android runtime отображает и принимает input для native scene UI;
- scene UI source/asset materialization не импортирует Python;
- desktop, Android и OpenXR используют один component/pass contract;
- `termin-components-ui` не зависит от `tcgui`;
- поиск по production-коду не находит legacy scene UI imports;
- старый Python path удалён, а не оставлен fallback;
- документация modules/architecture/runtime package обновлена;
- umbrella #244 ссылается на завершённые migration cards и больше не считает
  `UIComponent` живым consumer `termin-gui`.
