# Module Map

Карта модулей фиксирует архитектурные границы. Это не замена локальным документам в `<module>/docs/`, а индекс ownership: что где должно находиться и куда переносить код при расползании ответственности.

Связанные документы:

- [Documentation System](documentation-system.md)
- [Library Dependencies](library-dependencies.md)
- [Build System](build-system.md)

## Core Foundations

### termin-nanobind-sdk

Source of truth: [termin-nanobind-sdk docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-nanobind-sdk/docs/index.md)

Отвечает за общую nanobind-инфраструктуру Python bindings: runtime preload, build helpers, упаковку native extension modules.

Если build/runtime helper начинает знать про конкретный domain-модуль, это повод держать его рядом с этим модулем, а не в nanobind SDK.

### termin-build-tools

Source of truth: [termin-build-tools docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-build-tools/docs/index.md)

Build-time helpers для Python packages с CMake/nanobind extensions.

### termin-base / tcbase

Source of truth: [termin-base docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-base/docs/index.md)

Базовые типы и инфраструктура, на которую могут опираться остальные модули.

Кандидаты на перенос сюда: малые общие value-типы и utilities без знания graphics/render/scene.

### termin-mesh / tmesh

Source of truth: [termin-mesh docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-mesh/docs/index.md)

Canonical mesh/data layer. `tc_mesh` относится к ядру данных движка, а не к legacy-слою.

Код, который адаптирует mesh к конкретному renderer/device, должен жить выше: например в [termin-graphics](#termin-graphics) как adapter к tgfx2 или в [termin-render](#termin-render), если он зависит от render framework.

### termin-assets

Source of truth: [plugin asset system plan](./plans/2026-05-13-plugin-asset-system.md)

Shared asset runtime contracts: base asset classes, typed asset registries,
preload/watch/reload core, and entry-point based plugin discovery. It should
not own domain-specific asset classes.

### termin-default-assets

Source of truth: [termin-default-assets docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-default-assets/docs/index.md)

Default asset adapters that connect `termin-assets` to domain packages without
making those domain packages depend on the asset runtime. Standard mesh,
navmesh, voxel, audio, render, and UI asset adapters belong here; domain
packages stay focused on runtime/data APIs.

### termin-prefab

Source of truth: [termin-prefab docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-prefab/docs/index.md)

Owns prefab runtime and `.prefab` asset integration: native `PrefabDocument`,
`PrefabInstantiator` and `PrefabInstanceState`, scene-owned live-instance
queries, the authoring-side `PrefabAsset`, property override paths, and prefab
import/runtime plugins. The package is separate from `termin-default-assets`
because prefab behavior is scene-composition runtime, not a thin default
adapter over a lower-level domain package.

### termin-glb

Source of truth: [termin-glb docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-glb/docs/index.md)

Owns GLB/glTF parsing, `GLBAsset`, GLB import/runtime plugin entry points,
runtime scene instantiation, and extraction helpers. GLB is a multi-domain
importer: it may create mesh, texture/material, skeleton, animation, and scene
hierarchy data, so it belongs in an explicit importer package rather than in
`termin-mesh` or `termin-default-assets`.

Editor drag/drop, inspectors, and project-browser commands stay in
`termin-app`; they should call `termin.glb.*` APIs instead of owning importer
logic.

## Graphics And Rendering

### termin-graphics / tgfx

Source of truth: [termin-graphics docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-graphics/docs/index.md)

Отвечает за backend-neutral GPU API, tgfx2 context/device/runtime, render targets, texture pools, canvas renderer facade и низкоуровневые GPU utilities. Это канонический GPU substrate для render framework; использование `tgfx`/`tgfx2` типов в render-facing API само по себе не является нарушением границы.

Ключевая граница сейчас важна из-за миграции renderer facades: generic GPU utilities без знания frame graph относятся сюда, а frame graph/debugger logic остается в [termin-render](#termin-render).

### termin-render

Source of truth: [termin-render docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-render/docs/index.md)

Отвечает за render framework поверх canonical resources и `termin-graphics`: render engine, frame graph, presenter/debugger, scene render mount data и render-state integration helpers.

`termin-render` не обязан инкапсулировать `termin-graphics` как implementation detail. Публичная зависимость от `tgfx`/`tgfx2` допустима для API, которые непосредственно описывают GPU execution, frame graph, render contexts, texture handles или bridge к graphics device. Граница проходит не по факту include-а `tgfx`, а по смыслу контракта: scene/asset/build/editor policy не должны случайно зависеть от backend-specific деталей, если они не являются render-facing API.

Здесь должны оставаться части, которые знают про frame graph, pass interfaces, engine views, render scene mount config (`ViewportConfig`, `RenderTargetConfig`, scene pipeline templates), render-state accessors и legacy render-state/mount migration helpers. Python bindings для `ViewportConfig` и `RenderTargetConfig` также принадлежат `termin.render`. Glue, который напрямую вызывает `termin-engine` `RenderingManager`, пока не относится к `termin-render`, чтобы не создавать обратную зависимость.

Кандидаты на вынос в [termin-graphics](#termin-graphics):

- generic fullscreen texture presentation;
- generic `tc_texture` / `tc_mesh` to tgfx2 adapters, если они не знают о frame graph/pass contracts;
- общие allocation/cache helpers, не знающие о frame graph.

### termin-render-passes

Source of truth: [termin-render-passes docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-render-passes/docs/index.md)

Отвечает за concrete render pass implementations поверх `termin-render`, `termin-graphics`, `termin-materials`, render components и debug/editor pass integrations.

На 2026-06-20 сюда перенесены standard/scene/postprocess/debug passes: `PresentToScreenPass`, `DebugTrianglePass`, `GroundGridPass`, `ColliderGizmoPass`, `ImmediateDepthPass`, `UnifiedGizmoPass`, `GrayscalePass`, `TonemapPass`, `BloomPass`, `ColorPass`, `ShadowPass`, `SkyBoxPass`, `IdPass`, picking RGB/id cache helper, shadow camera helpers, shader skinning injection, material UBO apply helper и Python API `termin.render_passes`.

`SolidPrimitiveRenderer` сейчас живет в editor-private native surface `termin.editor._editor_native`; публичные render-pass helpers импортируются из `termin.render_passes`.

### termin-display

Source of truth: [termin-display docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-display/docs/index.md)

Отвечает за platform/native windows и display integration. Concrete window implementations, например `SDLBackendWindow`, живут здесь.

## UI And Tools

### termin-gui / tcgui

Source of truth: [termin-gui docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-gui/docs/index.md)

Отвечает за retained widget tree, layout, input routing, dialogs, canvas/viewport widgets и Python UI API.

Целевая C++-миграция должна использовать явный storage/document ownership с handle-based references; см. [UI storage and plot annotations](architecture/2026-07-07-ui-storage-and-plot-annotations.md).

Рендеринг виджетов должен использовать facade из [termin-graphics](#termin-graphics), а не дублировать низкоуровневые GPU primitives.

`termin-gui-native` — экспериментальный C ABI/C++ прототип будущего native UI document; он не заменяет текущий Python `termin-gui`, пока контракт владения, handles и polyglot widget vtable не будет проверен на базовых виджетах.

### tcplot

Source of truth: [tcplot docs](https://github.com/mirmik/termin-monorepo/blob/master/tcplot/docs/index.md)

Plotting library поверх tgfx/tcgui. Должен переиспользовать renderer/runtime abstractions из [termin-graphics](#termin-graphics) и host/window infrastructure из [termin-display](#termin-display), не заводя собственный низкоуровневый GPU слой.

Маркеры, подписи, callouts, legends и интерактивные handles графиков должны жить как retained plot annotation model внутри `tcplot`, а не как виджеты `termin-gui`; см. [UI storage and plot annotations](architecture/2026-07-07-ui-storage-and-plot-annotations.md).

### termin-nodegraph

Source of truth: [termin-nodegraph docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-nodegraph/docs/index.md)

Python node graph UI/tools. Должен зависеть от public UI/graphics APIs, а не от внутренних деталей render backend.

## Engine Domains

### termin-scene

Source of truth: [termin-scene docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-scene/docs/index.md)

Отвечает за scene/ECS ownership, handles, lifecycle и component storage.

Renderer/UI integration описывается на уровне render/component/application modules.

### termin-inspect

Source of truth: [termin-inspect docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-inspect/docs/index.md)

Отвечает за kind/type metadata, inspection dispatch, field metadata, Python bridge.

Связанные scene/render/application сценарии используют inspect metadata, но policy остается в соответствующих domain modules.

### termin-modules

Source of truth: [termin-modules docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-modules/docs/index.md)

Отвечает за descriptors, lifecycle, callbacks и plugin/module loading contracts.

### termin-collision

Source of truth: [termin-collision docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-collision/docs/index.md)

Отвечает за collision world, colliders, algorithms и C/Python API коллизий.

### termin-physics

Source of truth: [termin-physics docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-physics/docs/index.md)

C++ rigid-body physics layer. Collision primitives должны оставаться в [termin-collision](#termin-collision), если они не требуют physics simulation state. Experimental FEM scene components live in [termin-physics-fem](https://github.com/mirmik/termin-monorepo/blob/master/termin-physics-fem/docs/index.md), not in `termin.physics`.

### termin-physics-fem

Source of truth: [termin-physics-fem docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-physics-fem/docs/index.md)

Experimental Python FEM scene components over `termin-qopt`. This package may depend on the Python optimization stack; `termin-physics` must stay independent from it.

### termin-input

Source of truth: [termin-input docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-input/docs/index.md)

Input abstraction. UI event routing остается в [termin-gui](#termin-gui), platform windowing остается в [termin-display](#termin-display).

### termin-engine

Source of truth: [termin-engine docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-engine/docs/index.md)

Engine-level orchestration поверх scene/render/input/domain modules. Владеет runtime managers, scene render lifecycle helpers, builtin scene extension registration включая collision runtime, и интеграцией project modules с live scenes (`TermModulesIntegration`).

> **termin-entity** был удалён — ECS-биндинги перенесены в `termin-scene`.
ECS-типы (`Entity`, `Component`, `ComponentRegistry`, `TcScene`) импортируются из `termin.scene`.

### termin-lighting

Source of truth: [termin-lighting docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-lighting/docs/index.md)

Lighting primitives and lighting-domain Python bindings.

### termin-skeleton

Source of truth: [termin-skeleton docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-skeleton/docs/index.md)

Skeleton-domain API and bindings.

### termin-animation

Source of truth: [termin-animation docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-animation/docs/index.md)

Animation-domain API and bindings.

### termin-navmesh

Source of truth: [termin-navmesh docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-navmesh/docs/index.md)

NavMesh C registry, Recast/Detour-backed scene components, `_navmesh_native`
bindings, and navigation utilities.

### termin-tween

Source of truth: [termin-tween docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-tween/docs/index.md)

Чистое ядро твининга: easing-функции, tween-классы и `TweenManager`.

Scene-компонент живёт выше, в [termin-components-tween](#component-libraries), чтобы
`termin-tween` не зависел от `termin-scene` и editor/UI-слоя.

### termin-voxels

Source of truth: [termin-voxels docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-voxels/docs/index.md)

Voxel grid runtime API, persistence, mesh voxelization helpers and
`termin.voxels._voxels_native`.

Scene/render components live in [termin-components-voxels](#component-libraries);
the native CMake target is owned and built by `termin-voxels`.

## Component Libraries

Source of truth: [termin-components docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-components/docs/index.md)

Component packages attach domain behavior/data to scene/entity objects:

- [termin-components-collision](https://github.com/mirmik/termin-monorepo/blob/master/termin-components/termin-components-collision/docs/index.md)
- [termin-components-render](https://github.com/mirmik/termin-monorepo/blob/master/termin-components/termin-components-render/docs/index.md)
- [termin-components-mesh](https://github.com/mirmik/termin-monorepo/blob/master/termin-components/termin-components-mesh/docs/index.md)
- [termin-components-kinematic](https://github.com/mirmik/termin-monorepo/blob/master/termin-components/termin-components-kinematic/docs/index.md)
- [termin-components-physics](https://github.com/mirmik/termin-monorepo/blob/master/termin-components/termin-components-physics/docs/index.md)
- [termin-components-skeleton](https://github.com/mirmik/termin-monorepo/blob/master/termin-components/termin-components-skeleton/docs/index.md)
- [termin-components-animation](https://github.com/mirmik/termin-monorepo/blob/master/termin-components/termin-components-animation/docs/index.md)
- [termin-components-tween](https://github.com/mirmik/termin-monorepo/blob/master/termin-components/termin-components-tween/docs/index.md)
- [termin-components-voxels](https://github.com/mirmik/termin-monorepo/blob/master/termin-components/termin-components-voxels/docs/index.md)

## Language Bindings

### termin-csharp

Source of truth: [termin-csharp docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-csharp/docs/index.md)

C# bindings/runtime packaging for Termin native libraries.

## Application Layer

### termin-shader-runtime

Source of truth: `termin-shader-runtime/`.

Shared shader tool resolution and source-project shader runtime helpers consumed by build tooling, editor and player.

### termin-mcp

Source of truth: `termin-mcp/`.

Shared MCP transport/executor helpers consumed by editor and player. Process-specific MCP tools live in their owning application packages.

### termin-player

Source of truth: `termin-player/`.

Standalone/source/headless player runtime and native `termin_player` executable. `termin-app` may consume player commands/APIs, but player code must not depend on `termin-app`.

### termin-cli

Source of truth: `termin-cli/`.

SDK command entrypoint layer. Owns native command wrappers such as `termin`,
`termin_builder`, `termin_runner`, `termin_modules_cli`, and `termin_stdlib`.
Domain behavior remains in the owning packages (`termin-project-build`,
`termin-player`, `termin-project-modules`, `termin-stdlib`); `termin-cli`
only resolves profiles, configures the SDK Python environment, and dispatches
to the owning package entrypoints.

### termin-app

Source of truth: [termin-app docs](https://github.com/mirmik/termin-monorepo/blob/master/termin-app/docs/index.md), [editor architecture](https://github.com/mirmik/termin-monorepo/blob/master/termin-app/docs/editor-architecture.md), [flat viewport target model](https://github.com/mirmik/termin-monorepo/blob/master/termin-app/docs/rendering-flat-viewport-target-model.md).

Основное приложение/редактор. tcgui является единственным поддерживаемым UI редактора; Qt/PyQt-версия удалена.

Application-level code не должен протекать вниз в graphics/render/scene. Старые app-level compatibility reexports для доменных API разбираются в пользу canonical imports из owning packages; новые re-export слои в `termin-app` добавлять не следует.

### diffusion-editor

Внешний consumer в отдельном репозитории. Он подключается к Termin через SDK и wheelhouse (`sdk/wheels`) и остаётся полезным smoke-test публичности API: если diffusion-editor вынужден лезть во внутренности Termin, вероятно граница модуля описана или реализована плохо.
