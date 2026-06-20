# Module Map

Карта модулей фиксирует архитектурные границы. Это не замена локальным документам в `<module>/docs/`, а индекс ownership: что где должно находиться и куда переносить код при расползании ответственности.

Связанные документы:

- [Documentation System](documentation-system.md)
- [Library Dependencies](library-dependencies.md)
- [Build System](build-system.md)

## Core Foundations

### termin-nanobind-sdk

Source of truth: [termin-nanobind-sdk docs](../termin-nanobind-sdk/docs/index.md)

Отвечает за общую nanobind-инфраструктуру Python bindings: runtime preload, build helpers, упаковку native extension modules.

Если build/runtime helper начинает знать про конкретный domain-модуль, это повод держать его рядом с этим модулем, а не в nanobind SDK.

### termin-build-tools

Source of truth: [termin-build-tools docs](../termin-build-tools/docs/index.md)

Build-time helpers для Python packages с CMake/nanobind extensions.

### termin-base / tcbase

Source of truth: [termin-base docs](../termin-base/docs/index.md)

Базовые типы и инфраструктура, на которую могут опираться остальные модули.

Кандидаты на перенос сюда: малые общие value-типы и utilities без знания graphics/render/scene.

### termin-mesh / tmesh

Source of truth: [termin-mesh docs](../termin-mesh/docs/index.md)

Canonical mesh/data layer. `tc_mesh` относится к ядру данных движка, а не к legacy-слою.

Код, который адаптирует mesh к конкретному renderer/device, должен жить выше: например в [termin-graphics](#termin-graphics) как adapter к tgfx2 или в [termin-render](#termin-render), если он зависит от render framework.

### termin-assets

Source of truth: [plugin asset system plan](./plans/2026-05-13-plugin-asset-system.md)

Shared asset runtime contracts: base asset classes, typed asset registries,
preload/watch/reload core, and entry-point based plugin discovery. It should
not own domain-specific asset classes.

### termin-default-assets

Source of truth: [termin-default-assets docs](../termin-default-assets/docs/index.md)

Default asset adapters that connect `termin-assets` to domain packages without
making those domain packages depend on the asset runtime. Standard mesh,
navmesh, voxel, audio, render, and UI asset adapters belong here; domain
packages stay focused on runtime/data APIs.

### termin-prefab

Source of truth: [termin-prefab docs](../termin-prefab/docs/index.md)

Owns prefab runtime and `.prefab` asset integration: `PrefabAsset`,
`PrefabInstanceMarker`, `PrefabRegistry`, property override paths, and prefab
import/runtime plugins. The package is separate from `termin-default-assets`
because prefab behavior is scene-composition runtime, not a thin default
adapter over a lower-level domain package.

### termin-glb

Source of truth: [termin-glb docs](../termin-glb/docs/index.md)

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

Source of truth: [termin-graphics docs](../termin-graphics/docs/index.md)

Отвечает за backend-neutral GPU API, tgfx2 context/device/runtime, render targets, texture pools, canvas renderer facade и низкоуровневые GPU utilities.

Ключевая граница сейчас важна из-за миграции renderer facades: generic GPU utilities без знания frame graph относятся сюда, а frame graph/debugger logic остается в [termin-render](#termin-render).

### termin-render

Source of truth: [termin-render docs](../termin-render/docs/index.md)

Отвечает за render framework поверх canonical resources: render engine, frame graph, presenter/debugger, scene render mount data и render-state integration helpers.

Здесь должны оставаться части, которые знают про frame graph, pass interfaces, engine views, render scene mount config (`ViewportConfig`, `RenderTargetConfig`, scene pipeline templates), render-state accessors и legacy render-state/mount migration helpers. App `_native` может оставлять compatibility bindings для этих типов, но C/C++ ownership принадлежит `termin-render`. Glue, который напрямую вызывает `termin-engine` `RenderingManager`, пока не относится к `termin-render`, чтобы не создавать обратную зависимость.

Кандидаты на вынос в [termin-graphics](#termin-graphics):

- generic fullscreen texture presentation;
- generic `tc_texture` / `tc_mesh` to tgfx2 adapters;
- общие allocation/cache helpers, не знающие о frame graph.

### termin-render-passes

Source of truth: [termin-render-passes docs](../termin-render-passes/docs/index.md)

Отвечает за concrete render pass implementations поверх `termin-render`, `termin-graphics`, `termin-materials`, render components и debug/editor pass integrations.

На 2026-06-20 сюда перенесены standard/scene/postprocess/debug passes: `PresentToScreenPass`, `DebugTrianglePass`, `GroundGridPass`, `ColliderGizmoPass`, `ImmediateDepthPass`, `UnifiedGizmoPass`, `GrayscalePass`, `TonemapPass`, `BloomPass`, `ColorPass`, `ShadowPass`, `SkyBoxPass`, `IdPass`, picking RGB/id cache helper, shadow camera helpers, shader skinning injection, material UBO apply helper и Python API `termin.render_passes`.

Оставшийся долг миграции: `SolidPrimitiveRenderer` требует отдельного решения по debug/editor ownership. App `_native` пока сохраняет compatibility bindings для некоторых перенесённых типов/functions, но они вызывают символы из `termin-render-passes`.

### termin-display

Source of truth: [termin-display docs](../termin-display/docs/index.md)

Отвечает за platform/native windows и display integration. Concrete window implementations, например `SDLBackendWindow`, живут здесь.

## UI And Tools

### termin-gui / tcgui

Source of truth: [termin-gui docs](../termin-gui/docs/index.md)

Отвечает за retained widget tree, layout, input routing, dialogs, canvas/viewport widgets и Python UI API.

Рендеринг виджетов должен использовать facade из [termin-graphics](#termin-graphics), а не дублировать низкоуровневые GPU primitives.

### tcplot

Source of truth: [tcplot docs](../tcplot/docs/index.md)

Plotting library поверх tgfx/tcgui. Должен переиспользовать renderer/runtime abstractions из [termin-graphics](#termin-graphics) и host/window infrastructure из [termin-display](#termin-display), не заводя собственный низкоуровневый GPU слой.

### termin-nodegraph

Source of truth: [termin-nodegraph docs](../termin-nodegraph/docs/index.md)

Python node graph UI/tools. Должен зависеть от public UI/graphics APIs, а не от внутренних деталей render backend.

## Engine Domains

### termin-scene

Source of truth: [termin-scene docs](../termin-scene/docs/index.md)

Отвечает за scene/ECS ownership, handles, lifecycle и component storage.

Renderer/UI integration описывается на уровне render/component/application modules.

### termin-inspect

Source of truth: [termin-inspect docs](../termin-inspect/docs/index.md)

Отвечает за kind/type metadata, inspection dispatch, field metadata, Python bridge.

Связанные scene/render/application сценарии используют inspect metadata, но policy остается в соответствующих domain modules.

### termin-modules

Source of truth: [termin-modules docs](../termin-modules/docs/index.md)

Отвечает за descriptors, lifecycle, callbacks и plugin/module loading contracts.

### termin-collision

Source of truth: [termin-collision docs](../termin-collision/docs/index.md)

Отвечает за collision world, colliders, algorithms и C/Python API коллизий.

### termin-physics

Source of truth: [termin-physics docs](../termin-physics/docs/index.md)

Physics layer. Collision primitives должны оставаться в [termin-collision](#termin-collision), если они не требуют physics simulation state.

### termin-input

Source of truth: [termin-input docs](../termin-input/docs/index.md)

Input abstraction. UI event routing остается в [termin-gui](#termin-gui), platform windowing остается в [termin-display](#termin-display).

### termin-engine

Source of truth: [termin-engine docs](../termin-engine/docs/index.md)

Engine-level orchestration поверх scene/render/input/domain modules. Владеет runtime managers, scene render lifecycle helpers, builtin scene extension registration включая collision runtime, и интеграцией project modules с live scenes (`TermModulesIntegration`).

> **termin-entity** был удалён — его биндинги мигрированы в `termin._native` (termin-app).
ECS-типы (Entity, Component, ComponentRegistry, TcScene) импортируются из `termin.scene`.

### termin-lighting

Source of truth: [termin-lighting docs](../termin-lighting/docs/index.md)

Lighting primitives and lighting-domain Python bindings.

### termin-skeleton

Source of truth: [termin-skeleton docs](../termin-skeleton/docs/index.md)

Skeleton-domain API and bindings.

### termin-animation

Source of truth: [termin-animation docs](../termin-animation/docs/index.md)

Animation-domain API and bindings.

### termin-navmesh

Source of truth: [termin-navmesh docs](../termin-navmesh/docs/index.md)

NavMesh C registry, Recast/Detour-backed scene components, `_navmesh_native`
bindings, and navigation utilities.

### termin-tween

Source of truth: [termin-tween docs](../termin-tween/docs/index.md)

Чистое ядро твининга: easing-функции, tween-классы и `TweenManager`.

Scene-компонент живёт выше, в [termin-components-tween](#component-libraries), чтобы
`termin-tween` не зависел от `termin-scene` и editor/UI-слоя.

### termin-voxels

Source of truth: [termin-voxels docs](../termin-voxels/docs/index.md)

Voxel grid runtime API, persistence, mesh voxelization helpers and
`termin.voxels._voxels_native`.

Scene/render components live in [termin-components-voxels](#component-libraries);
the native CMake target is owned and built by `termin-voxels`.

## Component Libraries

Source of truth: [termin-components docs](../termin-components/docs/index.md)

Component packages attach domain behavior/data to scene/entity objects:

- [termin-components-collision](../termin-components/termin-components-collision/docs/index.md)
- [termin-components-render](../termin-components/termin-components-render/docs/index.md)
- [termin-components-mesh](../termin-components/termin-components-mesh/docs/index.md)
- [termin-components-kinematic](../termin-components/termin-components-kinematic/docs/index.md)
- [termin-components-physics](../termin-components/termin-components-physics/docs/index.md)
- [termin-components-skeleton](../termin-components/termin-components-skeleton/docs/index.md)
- [termin-components-animation](../termin-components/termin-components-animation/docs/index.md)
- [termin-components-tween](../termin-components/termin-components-tween/docs/index.md)
- [termin-components-voxels](../termin-components/termin-components-voxels/docs/index.md)

## Language Bindings

### termin-csharp

Source of truth: [termin-csharp docs](../termin-csharp/docs/index.md)

C# bindings/runtime packaging for Termin native libraries.

## Application Layer

### termin-app

Source of truth: [termin-app docs](../termin-app/docs/index.md), [editor architecture](../termin-app/docs/editor-architecture.md), [flat viewport target model](../termin-app/docs/rendering-flat-viewport-target-model.md).

Основное приложение/редактор. tcgui является единственным поддерживаемым UI редактора; Qt/PyQt-версия удалена.

Application-level code не должен протекать вниз в graphics/render/scene. `termin-app` может держать compatibility reexports для старых импортов, но canonical ownership таких API должен жить в доменных пакетах.

### diffusion-editor

Внешний consumer в отдельном репозитории. Он подключается к Termin через SDK и wheelhouse (`sdk/wheels`) и остаётся полезным smoke-test публичности API: если diffusion-editor вынужден лезть во внутренности Termin, вероятно граница модуля описана или реализована плохо.
