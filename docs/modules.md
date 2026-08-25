# Module Capability Map

Эта карта группирует packages по возможностям и фиксирует их локальные
контракты. Она не является реестром физического ownership: один semantic
раздел может содержать packages из нескольких districts. Канонический владелец
определяется [картой районов](districts/index.md) и
`build-system/districts.json`.

Локальные документы в `<district>/<package>/docs/` остаются source of truth для
API и lifecycle. Эта страница отвечает на вопрос «с какими механизмами связан
модуль», а district guide — «кто имеет право им владеть».

Связанные документы:

- [Documentation System](documentation-system.md)
- [Districts and ownership](districts/index.md)
- [Library Dependencies](library-dependencies.md)
- [Build System](build-system.md)

## Foundations, Data And Infrastructure

### termin-nanobind-sdk

Source of truth: [termin-nanobind-sdk docs](https://github.com/mirmik/termin/blob/master/core/termin-nanobind-sdk/docs/index.md)

Отвечает за общую nanobind-инфраструктуру Python bindings: runtime preload, build helpers, упаковку native extension modules.

Если build/runtime helper начинает знать про конкретный domain-модуль, это повод держать его рядом с этим модулем, а не в nanobind SDK.

### termin-build-tools

Source of truth: [termin-build-tools docs](https://github.com/mirmik/termin/blob/master/core/termin-build-tools/docs/index.md)

Build-time helpers для Python packages с CMake/nanobind extensions.

### termin-base / tcbase

Source of truth: [termin-base docs](https://github.com/mirmik/termin/blob/master/core/termin-base/docs/index.md)

Базовые типы и инфраструктура, на которую могут опираться остальные модули.

Кандидаты на перенос сюда: малые общие value-типы и utilities без знания graphics/render/scene.

### termin-dispatch

Source of truth: [termin-dispatch docs](https://github.com/mirmik/termin/blob/master/core/termin-dispatch/docs/index.md)

Optional language-neutral deferred-execution primitive для application
composition. Канонический C ABI, C++ wrapper и Python binding используют одну
native очередь. Модуль не создаёт потоков, не назначает owner thread и
исполняет callbacks только при явном `drain` вызывающей программой.

`termin-dispatch` не является engine scheduler, UI host или window event loop и
не интегрируется автоматически в приложения Termin. Host-specific wakeup и
выбор фазы обслуживания остаются ответственностью embedding application.

### termin-profiler-remote

Source of truth: [remote profiler architecture](analysis/2026-07-30-remote-profiler-network-android.md)

Опциональный нативный слой удалённого профайлера над `termin-base`. Владеет
версионированным endian-independent wire protocol, общими жёсткими лимитами и
target-side транспортом. Codec не знает о сокетах, editor, Android host и
process-global profiler singleton; эти зависимости появляются только в
отдельных service/host adapters.

Editor-side источник и UI остаются в `termin-app`, а включение listener и его
security policy принадлежат конкретному host. `termin-runtime` не получает
обязательный diagnostics server.

### termin-framegraph-remote

Source of truth: [termin-framegraph-remote docs](https://github.com/mirmik/termin/blob/master/engine/termin-framegraph-remote/docs/index.md)

Опциональный нативный versioned contract сетевого Framegraph Debugger. Модуль
описывает topology revisions, session-scoped target/pass identity, команды
Snapshot/Live Preview/Burst, hard limits и chunked capture blobs. Codec не
зависит от editor, Python, sockets, RenderingManager или graphics backend;
target/client services подключаются отдельными слоями.

### termin-framegraph-remote-target

Source of truth: [remote Framegraph target service](https://github.com/mirmik/termin/blob/master/engine/termin-framegraph-remote-target/docs/index.md)

Опциональный native target-side слой над `termin-framegraph-remote` и
`termin-engine`. Сетевой поток владеет loopback TCP transport и handshake, а
render-thread pump — единственный код сервиса, который обращается к
`FrameGraphDebugger`. Между ними находятся bounded очереди команд и immutable
topology/status сообщений. Process-scoped host может держать loopback listener
при пересоздании render runtime и явно attach/detach новый debugger; detached
состояние публикуется как новая пустая topology без удержания GPU objects.

### termin-framegraph-remote-client

Source of truth: [remote Framegraph client](https://github.com/mirmik/termin/blob/master/engine/termin-framegraph-remote-client/docs/index.md)

Опциональный desktop transport над `termin-framegraph-remote`, не зависящий от
editor, Python, engine или GPU. Network thread обслуживает loopback TCP,
handshake и reconnect, а bounded SPSC очередь принимает session-scoped команды
с editor thread и отбрасывает их при разрыве соединения.

### termin-mesh / tmesh

Source of truth: [termin-mesh docs](https://github.com/mirmik/termin/blob/master/graphics/termin-mesh/docs/index.md)

Canonical mesh/data layer. `tc_mesh` относится к ядру данных движка, а не к legacy-слою.

Код, который адаптирует mesh к конкретному renderer/device, должен жить выше: например в [termin-graphics](#termin-graphics--tgfx) как adapter к tgfx2 или в [termin-render](#termin-render), если он зависит от render framework.

### termin-assets

Source of truth: [plugin asset system plan](./plans/2026-05-13-plugin-asset-system.md)

Shared asset runtime contracts: base asset classes, typed asset registries,
preload/watch/reload core, and entry-point based plugin discovery. It should
not own domain-specific asset classes.

### termin-default-assets

Source of truth: [termin-default-assets docs](https://github.com/mirmik/termin/blob/master/engine/termin-default-assets/docs/index.md)

Default asset adapters that connect `termin-assets` to domain packages without
making those domain packages depend on the asset runtime. Standard mesh,
navmesh, voxel, audio, render, and UI asset adapters belong here; domain
packages stay focused on runtime/data APIs.

### termin-prefab

Source of truth: [termin-prefab docs](https://github.com/mirmik/termin/blob/master/engine/termin-prefab/docs/index.md)

Owns prefab runtime and `.prefab` asset integration: native `PrefabDocument`,
`PrefabInstantiator`, `PrefabInstanceState` and the versioned tagged
`PrefabOverrideValue` codec, scene-owned live-instance queries, the
authoring-side `PrefabAsset`, property override paths, and prefab import/runtime
plugins. The package is separate from `termin-default-assets`
because prefab behavior is scene-composition runtime, not a thin default
adapter over a lower-level domain package.

### termin-glb

Source of truth: [termin-glb docs](https://github.com/mirmik/termin/blob/master/graphics/termin-glb/docs/index.md)

The `termin-glb-native` distribution owns the minimal `termin.glb.native`
cgltf document and `build_mesh` API. It depends only on the native mesh/runtime
binding layer and can be installed without the asset system, default assets, or
legacy GUI packages.

The high-level `termin-glb` distribution owns portable Python GLB/glTF parsing,
scene data, loading and extraction helpers. It may publish mesh,
texture/material, skeleton and animation data without acquiring the Engine
asset runtime or ECS.

`editor/termin-glb-adapters` owns `GLBAsset`, resource plugins, Entity
instantiation and serialized-scene repair for Termin projects. These adapters
must not leak back into the portable Graphics package.

Editor drag/drop, inspectors, and project-browser commands stay in
`termin-app`; they call the explicit GLB adapter surface instead of owning
portable decoding logic.

## Graphics And Rendering

### termin-graphics / tgfx

Source of truth: [termin-graphics docs](https://github.com/mirmik/termin/blob/master/graphics/termin-graphics/docs/index.md)

Отвечает за backend-neutral GPU API, tgfx2 context/device/runtime, render targets, texture pools, canvas renderer facade и низкоуровневые GPU utilities. Это канонический GPU substrate для render framework; использование `tgfx`/`tgfx2` типов в render-facing API само по себе не является нарушением границы.

Ключевая граница важна из-за миграции renderer facades: generic GPU utilities
без знания frame graph относятся сюда. Scene-neutral frame graph execution
остаётся render-policy слоем над `termin-graphics` и с #1364 физически живёт в
`termin_render_core`, а не в GPU substrate.

### termin-graphics-mcp

Source of truth: `termin-graphics-mcp/`.

Graphics-owned MCP adapters for backend-neutral surface/texture readback and
PNG screenshot production. The package extends the Core-owned `termin-mcp`
transport but owns all dependencies on `tgfx`, `termin-image` and NumPy.
Editor and player select their domain surfaces; this package performs only the
graphics operation.

### termin-visual-scene

Source of truth: [termin-visual-scene docs](https://github.com/mirmik/termin/blob/master/graphics/termin-visual-scene/docs/index.md)

Отвечает за retained 2D visual identity, generation-checked item handles,
topology, transforms, hit preparation и pointer interaction. Модуль зависит от
канонических geometry/path/draw values в `termin-base` и `termin-graphics`, но
не владеет GPU context, widget tree, plot data или world/entity semantics.
Обратной зависимости из `termin-graphics` нет.

### termin-render

Source of truth: [termin-render docs](https://github.com/mirmik/termin/blob/master/engine/termin-render/docs/index.md)

Render framework разделён на два физических target. `termin_render_core`
владеет render engine, runtime frame graph/pipeline, generic resources,
immutable snapshots, `RenderItemSource`, task planning и draw encoder registry;
его transitive interface не содержит `termin_scene` или `termin_lighting`.
`termin_render` зависит от core и владеет `tc_scene` adapter, component
capabilities, scene render mount/state helpers и graph authoring policy. Scene
path через `TcSceneRenderItemSource` заранее публикует snapshots/services и
вызывает тот же core executor.

`termin-render` не обязан инкапсулировать `termin-graphics` как implementation detail. Публичная зависимость от `tgfx`/`tgfx2` допустима для API, которые непосредственно описывают GPU execution, frame graph, render contexts, texture handles или bridge к graphics device. Граница проходит не по факту include-а `tgfx`, а по смыслу контракта: scene/asset/build/editor policy не должны случайно зависеть от backend-specific деталей, если они не являются render-facing API.

Здесь должны оставаться части, которые знают про frame graph, pass interfaces, engine views, render scene mount config (`ViewportConfig`, `RenderTargetConfig`, scene pipeline templates), render-state accessors и legacy render-state/mount migration helpers. Python bindings для `ViewportConfig` и `RenderTargetConfig` также принадлежат `termin.render`. Glue, который напрямую вызывает `termin-engine` `RenderingManager`, пока не относится к `termin-render`, чтобы не создавать обратную зависимость.

Кандидаты на вынос в [termin-graphics](#termin-graphics--tgfx):

- generic fullscreen texture presentation;
- generic `tc_texture` / `tc_mesh` to tgfx2 adapters, если они не знают о frame graph/pass contracts;
- общие allocation/cache helpers, не знающие о frame graph.

### termin-render-passes

Source of truth: [termin-render-passes docs](https://github.com/mirmik/termin/blob/master/engine/termin-render-passes/docs/index.md)

Отвечает за concrete render pass implementations поверх `termin-render`, `termin-graphics`, `termin-materials`, render components и debug/editor pass integrations.

На 2026-07-30 сюда перенесены standard/scene/postprocess/debug passes:
`PresentToScreenPass`, `DebugTrianglePass`, `GroundGridPass`,
`DebugGeometryPass`, `ImmediateDepthPass`, `UnifiedGizmoPass`,
`GrayscalePass`, `TonemapPass`, `BloomPass`, `ColorPass`, `ShadowPass`,
`SkyBoxPass`, `IdPass` и единый native `UIWidgetPass` для desktop, Android и
OpenXR. Модуль также владеет `ShadowMapArrayResource` и регистрацией его
framegraph factory/sampled preview, picking RGB/id cache helper, shadow camera
helpers, shader skinning injection, material UBO apply helper и Python API
`termin.render_passes`.

Цветовое преобразование физического выхода не является authored render pass:
`PipelineColorExport` задаёт семантику результата, а render executor выбирает
копирование либо общий programmable output transform с transfer-функцией и
дизерингом под формат caller-owned target.

`SolidPrimitiveRenderer` сейчас живет в editor-private native surface `termin.editor._editor_native`; публичные render-pass helpers импортируются из `termin.render_passes`.

### termin-display

Source of truth: [termin-display docs](https://github.com/mirmik/termin/blob/master/engine/termin-display/docs/index.md)

Отвечает за logical displays, viewport layout, display-level input routing и
backend-neutral offscreen output surfaces. Целевой `tc_render_surface` является
узким C ABI для texture output одного `tc_display`; window, event polling,
presentation и OpenGL context operations в этот контракт не входят. Миграция
описана в [Display render surface contract](architecture/2026-07-19-display-render-surface-contract.md).

### termin-window

Source of truth: [termin-window docs](https://github.com/mirmik/termin/blob/master/graphics/termin-window/docs/index.md)

Lightweight boundary для native windows, portable window events и физической
презентации tgfx texture. Concrete implementation `SDLBackendWindow` живёт
здесь. Модуль не зависит от scene, engine display/input routing, render или
materials.

Framework-neutral `WindowManager` владеет коллекцией `BackendWindow`,
generational handles, единым process-global event pump, per-window event
batches и deterministic close order. Он не хранит UI objects/controllers, не
задаёт main/secondary роли, render scheduling или application-exit policy.
Application composition связывает `WindowHandle` с выбранным UI framework,
raw renderer или другим содержимым. Целевой контракт описан в
[Framework-neutral window management](architecture/2026-07-23-framework-neutral-window-management.md).

## UI And Tools

### termin-gui-native

Source of truth: [termin-gui-native README](https://github.com/mirmik/termin/blob/master/graphics/termin-gui-native/README.md)

`termin-gui-native` — единственный поддерживаемый retained UI toolkit Termin.
Он владеет C ABI/C++ document и widget core, layout, input routing, dialogs,
canvas/viewport widgets и Python-проекцией тех же native handles. Удалённый
Python toolkit `termin-gui`/`tcgui` не является compatibility dependency.

Рендеринг виджетов использует facade из [termin-graphics](#termin-graphics--tgfx),
а не дублирует низкоуровневые GPU primitives.

Native widget/document core не владеет OS windows, `WindowedGraphicsSession`,
application loop или main/secondary policy. Необязательный leaf adapter может
зависеть от `termin-window` для перевода `WindowEvent`, clipboard/cursor/text
input и presentation integration; обратной зависимости из `termin-window` в
UI нет. Headless composition использует document/rendering primitives без
`termin-window`.

### tcplot

Source of truth: [tcplot docs](https://github.com/mirmik/termin/blob/master/graphics/tcplot/docs/index.md)

Toolkit-neutral plotting library поверх tgfx. Переиспользует GPU abstractions из
[termin-graphics](#termin-graphics--tgfx), scene-neutral framegraph/execution из
`termin_render_core` и host/window infrastructure из
[termin-display](#termin-display), не заводя собственный низкоуровневый GPU
слой. `PlotScene3DRenderItemSource` публикует retained 3D identities в общий
render core без зависимости на `termin_scene` или `termin_lighting`.

Маркеры, подписи, callouts, legends и интерактивные handles графиков живут как
retained plot annotation model внутри `tcplot`, а не в UI toolkit; см.
[UI storage and plot annotations](architecture/2026-07-07-ui-storage-and-plot-annotations.md).

Целевая C#-композиция chart описана в
[C# Retained Chart Composition](architecture/2026-07-30-csharp-retained-chart-composition.md).
Plot-domain data, projection, ticks и оптимизированные series items остаются в
`tcplot`, но реализуют общий `tc_graphic_item` contract и собираются managed
кодом в одну `TcVisualScene`. `termin-visual-scene` не должен приобретать
знание о series, axes, data ranges или chart layout.

Необязательный leaf-модуль `tcplot-gui-native` зависит одновременно от
`tcplot` и `termin-gui-native` и предоставляет готовый runtime-виджет
`termin.gui.Plot2D`, а также интерактивный texture-backed
`termin.gui.Plot3D`. Последний оборачивает `RetainedChart3D` и поддерживает
обычную widget-tree и portal-композицию, в том числе внутри nodegraph body. Эти
виджеты нужны там, где полная ручная композиция chart parts не оправдана.
Обратных зависимостей из plot и UI core на этот bridge нет.

### termin-nodegraph

Source of truth: [termin-nodegraph docs](https://github.com/mirmik/termin/blob/master/graphics/termin-nodegraph/docs/index.md)

Python node graph UI/tools. Должен зависеть от public UI/graphics APIs, а не от внутренних деталей render backend.

## Runtime Domains

### termin-scene

Source of truth: [termin-scene docs](https://github.com/mirmik/termin/blob/master/engine/termin-scene/docs/index.md)

Отвечает за scene/ECS ownership, handles, lifecycle и component storage.

Renderer/UI integration описывается на уровне render/component/application modules.

### termin-inspect

Source of truth: [termin-inspect docs](https://github.com/mirmik/termin/blob/master/core/termin-inspect/docs/index.md)

Отвечает за kind/type metadata, inspection dispatch, field metadata, Python bridge.

Связанные scene/render/application сценарии используют inspect metadata, но policy остается в соответствующих domain modules.

### termin-modules

Source of truth: [termin-modules docs](https://github.com/mirmik/termin/blob/master/engine/termin-modules/docs/index.md)

Отвечает за descriptors, lifecycle, callbacks и plugin/module loading contracts.

### termin-collision

Source of truth: [termin-collision docs](https://github.com/mirmik/termin/blob/master/physics/termin-collision/docs/index.md)

Отвечает за collision world, colliders, algorithms и C/Python API коллизий.

### termin-physics

Source of truth: [termin-physics docs](https://github.com/mirmik/termin/blob/master/physics/termin-physics/docs/index.md)

C++ rigid-body physics layer. Collision primitives должны оставаться в [termin-collision](#termin-collision), если они не требуют physics simulation state. Contribution-based FEM scene integration живёт в [termin-physics-fem](https://github.com/mirmik/termin/blob/master/physics/termin-physics-fem/docs/index.md), not in `termin.physics`.

### termin-physics-fem

Source of truth: [termin-physics-fem docs](https://github.com/mirmik/termin/blob/master/physics/termin-physics-fem/docs/index.md)

Native scene integration over the contribution-based `termin-qopt` dynamics
API. Runtime components link the C++ solver/model and do not require NumPy or a
project Python module. The bundled `termin.physics_fem` package remains a
reference-only projection of the former experimental API; `termin-physics`
must stay independent from both stacks.

### termin-input

Source of truth: [termin-input docs](https://github.com/mirmik/termin/blob/master/engine/termin-input/docs/index.md)

Input abstraction. UI event routing принадлежит
[termin-gui-native](#termin-gui-native), platform windowing —
[termin-display](#termin-display).

### termin-engine

Source of truth: [termin-engine docs](https://github.com/mirmik/termin/blob/master/engine/termin-engine/docs/index.md)

Engine-level orchestration поверх scene/render/input/domain modules. Владеет runtime managers, scene render lifecycle helpers, builtin scene extension registration включая collision runtime, и интеграцией project modules с live scenes (`TermModulesIntegration`).

> **termin-entity** был удалён — ECS-биндинги перенесены в `termin-scene`.
ECS-типы (`Entity`, `Component`, `ComponentRegistry`, `TcScene`) импортируются из `termin.scene`.

### termin-lighting

Source of truth: [termin-lighting docs](https://github.com/mirmik/termin/blob/master/engine/termin-lighting/docs/index.md)

Lighting primitives and lighting-domain Python bindings.

### termin-skeleton

Source of truth: [termin-skeleton docs](https://github.com/mirmik/termin/blob/master/graphics/termin-skeleton/docs/index.md)

Skeleton-domain API and bindings.

### termin-animation

Source of truth: [termin-animation docs](https://github.com/mirmik/termin/blob/master/graphics/termin-animation/docs/index.md)

Animation-domain API and bindings.

### termin-navmesh

Source of truth: [termin-navmesh docs](https://github.com/mirmik/termin/blob/master/physics/termin-navmesh/docs/index.md)

NavMesh C registry, Recast/Detour-backed scene components, `_navmesh_native`
bindings, and navigation utilities.

### termin-tween

Source of truth: [termin-tween docs](https://github.com/mirmik/termin/blob/master/graphics/termin-tween/docs/index.md)

Чистое ядро твининга: easing-функции, tween-классы и `TweenManager`.

Scene-компонент живёт выше, в [termin-components-tween](#component-libraries), чтобы
`termin-tween` не зависел от `termin-scene` и editor/UI-слоя.

### termin-voxels

Source of truth: [termin-voxels docs](https://github.com/mirmik/termin/blob/master/engine/termin-voxels/docs/index.md)

Voxel grid runtime API, persistence, mesh voxelization helpers and
`termin.voxels._voxels_native`.

Scene/render components live in [termin-components-voxels](#component-libraries);
the native CMake target is owned and built by `termin-voxels`.

## Component Libraries

Source of truth: [termin-components docs](https://github.com/mirmik/termin/blob/master/engine/termin-components/docs/index.md)

Component packages attach domain behavior/data to scene/entity objects:

- [termin-components-collision](https://github.com/mirmik/termin/blob/master/engine/termin-components/termin-components-collision/docs/index.md)
- [termin-components-render](https://github.com/mirmik/termin/blob/master/engine/termin-components/termin-components-render/docs/index.md)
- [termin-components-mesh](https://github.com/mirmik/termin/blob/master/engine/termin-components/termin-components-mesh/docs/index.md)
- [termin-components-kinematic](https://github.com/mirmik/termin/blob/master/engine/termin-components/termin-components-kinematic/docs/index.md)
- [termin-components-physics](https://github.com/mirmik/termin/blob/master/engine/termin-components/termin-components-physics/docs/index.md)
- [termin-components-skeleton](https://github.com/mirmik/termin/blob/master/engine/termin-components/termin-components-skeleton/docs/index.md)
- [termin-components-animation](https://github.com/mirmik/termin/blob/master/engine/termin-components/termin-components-animation/docs/index.md)
- [termin-components-tween](https://github.com/mirmik/termin/blob/master/engine/termin-components/termin-components-tween/docs/index.md)
- [termin-components-ui](https://github.com/mirmik/termin/blob/master/engine/termin-components/termin-components-ui/docs/index.md)
- [termin-components-voxels](https://github.com/mirmik/termin/blob/master/engine/termin-components/termin-components-voxels/docs/index.md)

## Language Bindings

### termin-csharp

Source of truth: [termin-csharp docs](https://github.com/mirmik/termin/blob/master/termin-csharp/docs/index.md)

C# bindings/runtime packaging for Termin native libraries.

## Tooling And Application Layer

### termin-shader-runtime

Source of truth: `termin-shader-runtime/`.

Shared shader tool resolution and source-project shader runtime helpers consumed by build tooling, editor and player.

### termin-mcp

Source of truth: `termin-mcp/`.

Shared MCP transport/executor helpers consumed by editor and player. Process-specific MCP tools live in their owning application packages.

### termin-player

Source of truth: `termin-player/`.

Standalone/source/headless player runtime and native `termin_player` executable. `termin-app` may consume player commands/APIs, but player code must not depend on `termin-app`.

### termin-model-viewer

Source of truth: `editor/termin-model-viewer/`.

Projectless static GLB viewer used by `termin show`. It composes portable GLB
data into the retained 3D graphics scene and owns the native window and orbit
camera interaction without depending on editor or project runtime state.

### termin-cli

Source of truth: `termin-cli/`.

SDK command entrypoint layer. Owns native command wrappers such as `termin`,
`termin_builder`, `termin_runner`, `termin_modules_cli`, and `termin_stdlib`.
Domain behavior remains in the owning packages (`termin-project-build`,
`termin-player`, `termin-model-viewer`, `termin-project-modules`,
`termin-stdlib`); `termin-cli`
only resolves profiles, configures the SDK Python environment, and dispatches
to the owning package entrypoints.

### termin-app

Source of truth: [termin-app docs](https://github.com/mirmik/termin/blob/master/editor/termin-app/docs/index.md), [editor architecture](https://github.com/mirmik/termin/blob/master/editor/termin-app/docs/editor-architecture.md), [flat viewport target model](https://github.com/mirmik/termin/blob/master/editor/termin-app/docs/rendering-flat-viewport-target-model.md).

Основное приложение/редактор. Архитектурно это C++ executable product и
application composition root, а не independently installable Python library.
Editor-specific Python modules и `termin.editor._editor_native` являются
внутренним payload приложения. Их явные source roots задаёт
`build-system/application-python-payloads.json`; Stage 3 устанавливает их в SDK
после library wheels и проверяет отдельно от distribution metadata. У
`termin-app` больше нет `setup.py`, wheel или записи в общем package manifest.
Host-derived bundle pipeline также удалён в #681: проверенное SDK tree является
единственным editor runtime artifact, а его переносимость проверяет общий
Linux/Windows relocated-SDK smoke. Граница зафиксирована в
[протоколе архитектурного совета](architecture-council/2026-07-19-termin-app-product-boundary.md).

Native UI является единственным поддерживаемым UI редактора, scene UI, CSG,
nodegraph и внешних toolkit consumers. Старые tcgui и Qt/PyQt
frontend-проекции, Python `UIComponent`, Python `UIWidgetPass` и пакет
`termin-gui` удалены.

Application-level code не должен протекать вниз в graphics/render/scene. Старые app-level compatibility reexports для доменных API разбираются в пользу canonical imports из owning packages; новые re-export слои в `termin-app` добавлять не следует.

### diffusion-editor

Внешний consumer в отдельном репозитории. Он подключается к Termin через SDK и wheelhouse (`sdk/wheels`) без установки editor application и остаётся обязательным smoke-test публичности API. `tcbase`, `tgfx`, `termin-display`, `termin-gui-native` и другие осмысленные library subsets сохраняют самостоятельные distributions и правдивую dependency closure. Если diffusion-editor вынужден устанавливать `termin-app` или лезть во внутренности Termin, граница модуля описана или реализована плохо.
