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

## Graphics And Rendering

### termin-graphics / tgfx

Source of truth: [termin-graphics docs](../termin-graphics/docs/index.md)

Отвечает за backend-neutral GPU API, tgfx2 context/device/runtime, render targets, texture pools, canvas renderer facade и низкоуровневые GPU utilities.

Ключевая граница сейчас важна из-за миграции renderer facades: generic GPU utilities без знания frame graph относятся сюда, а frame graph/debugger logic остается в [termin-render](#termin-render).

### termin-render

Source of truth: [termin-render docs](../termin-render/docs/index.md)

Отвечает за render framework поверх canonical resources: render engine, frame graph, presenter/debugger, интеграцию с application-level rendering.

Здесь должны оставаться части, которые знают про frame graph, render passes, engine views и отладочную визуализацию pipeline.

Кандидаты на вынос в [termin-graphics](#termin-graphics):

- generic fullscreen texture presentation;
- generic `tc_texture` / `tc_mesh` to tgfx2 adapters;
- общие allocation/cache helpers, не знающие о frame graph.

### termin-display

Source of truth: [termin-display docs](../termin-display/docs/index.md)

Отвечает за platform/native windows и display integration. Concrete window implementations, например `SDLBackendWindow`, живут здесь.

Concrete window implementations, например `SDLBackendWindow`, живут здесь.

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

Engine-level orchestration поверх scene/render/input/domain modules.

### termin-entity

Source of truth: [termin-entity docs](../termin-entity/docs/index.md)

Python-facing entity/component distribution layer.

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

NavMesh bindings and navigation utilities.

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

## Language Bindings

### termin-csharp

Source of truth: [termin-csharp docs](../termin-csharp/docs/index.md)

C# bindings/runtime packaging for Termin native libraries.

## Application Layer

### termin-app

Source of truth: [editor architecture](../termin-app/docs/editor-architecture.md), [flat viewport target model](../termin-app/docs/rendering-flat-viewport-target-model.md). Historical context: [tcgui migration](plans/2026-03-09-termin-app-tcgui-migration.md). The current [termin-app docs index](../termin-app/docs/index.md) is stale and should not be treated as an API reference.

Основное приложение/редактор. tcgui является primary UI. Qt поддерживается по возможности, но не должен быть основным направлением новых архитектурных решений.

Application-level code не должен протекать вниз в graphics/render/scene.

### diffusion-editor

Source of truth: [Architecture](../diffusion-editor/ARCHITECTURE.md)

Внешний consumer внутри монорепозитория. Хороший smoke-test публичности API: если diffusion-editor вынужден лезть во внутренности, вероятно граница модуля описана или реализована плохо.
