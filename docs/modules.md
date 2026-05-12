# Module Map

Карта модулей фиксирует архитектурные границы. Это не замена локальным документам в `<module>/docs/`, а индекс ownership: что где должно находиться и куда переносить код при расползании ответственности.

Связанные документы:

- [Documentation System](documentation-system.md)
- [Library Dependencies](library-dependencies.md)
- [Build System](build-system.md)

## Core Foundations

### termin-nanobind-sdk

Source of truth: [README](../termin-nanobind-sdk/README.md)

Отвечает за общую nanobind-инфраструктуру Python bindings: runtime preload, build helpers, упаковку native extension modules.

Не должен содержать доменную логику engine/render/gui. Если код знает про конкретный модуль, он должен жить в этом модуле.

### termin-base / tcbase

Source of truth: пока нет отдельного `docs/index.md`.

Базовые типы и инфраструктура, на которую могут опираться остальные модули.

Кандидаты на перенос сюда: малые общие value-типы и utilities без знания graphics/render/scene.

Не переносить сюда GPU, scene, mesh, ECS, UI и application-level код.

### termin-mesh / tmesh

Source of truth: пока нет отдельного `docs/index.md`.

Canonical mesh/data layer. `tc_mesh` относится к ядру данных движка, а не к legacy-слою.

Код, который адаптирует mesh к конкретному renderer/device, должен жить выше: например в [termin-graphics](#termin-graphics) как adapter к tgfx2 или в [termin-render](#termin-render), если он зависит от render framework.

## Graphics And Rendering

### termin-graphics / tgfx

Source of truth: [migration tgfx2](../termin-graphics/docs/migration-tgfx2.md), [Python migration](../termin-graphics/docs/migration-tgfx2-python.md)

Отвечает за backend-neutral GPU API, tgfx2 context/device/runtime, render targets, texture pools, canvas renderer facade и низкоуровневые GPU utilities.

Здесь должны жить:

- abstractions над `IRenderDevice`;
- reusable GPU helpers без знания frame graph;
- адаптеры canonical resources к tgfx2, если они не зависят от `termin-render`;
- общие render target / texture allocation pools.

Здесь не должны жить:

- frame graph debugger;
- domain-specific scene rendering;
- UI widget tree;
- application/editor logic.

### termin-render

Source of truth: пока нет отдельного `docs/index.md`.

Отвечает за render framework поверх canonical resources: render engine, frame graph, presenter/debugger, интеграцию с application-level rendering.

Здесь должны оставаться части, которые знают про frame graph, render passes, engine views и отладочную визуализацию pipeline.

Кандидаты на вынос в [termin-graphics](#termin-graphics):

- generic fullscreen texture presentation;
- generic `tc_texture` / `tc_mesh` to tgfx2 adapters;
- общие allocation/cache helpers, не знающие о frame graph.

### termin-display

Source of truth: пока нет отдельного `docs/index.md`.

Отвечает за platform/native windows и display integration. Concrete window implementations, например `SDLBackendWindow`, живут здесь.

Не должен становиться владельцем tgfx2 renderer abstractions или UI widgets.

## UI And Tools

### termin-gui / tcgui

Source of truth: [termin-gui docs](../termin-gui/docs/index.md)

Отвечает за retained widget tree, layout, input routing, dialogs, canvas/viewport widgets и Python UI API.

Рендеринг виджетов должен использовать facade из [termin-graphics](#termin-graphics), а не дублировать низкоуровневые GPU primitives.

### tcplot

Source of truth: пока нет отдельного `docs/index.md`.

Plotting library поверх tgfx/tcgui. Должен переиспользовать renderer/runtime abstractions из [termin-graphics](#termin-graphics) и host/window infrastructure из [termin-display](#termin-display), не заводя собственный низкоуровневый GPU слой.

### termin-nodegraph

Source of truth: [README](../termin-nodegraph/README.md)

Python node graph UI/tools. Должен зависеть от public UI/graphics APIs, а не от внутренних деталей render backend.

## Engine Domains

### termin-scene

Source of truth: [termin-scene docs](../termin-scene/docs/index.md)

Отвечает за scene/ECS ownership, handles, lifecycle и component storage.

Не должен зависеть от конкретного renderer или UI. Rendering-specific components/adapters должны жить в render/component modules.

### termin-inspect

Source of truth: [termin-inspect docs](../termin-inspect/docs/index.md)

Отвечает за kind/type metadata, inspection dispatch, field metadata, Python bridge.

Не должен содержать scene/render/application policy.

### termin-modules

Source of truth: [termin-modules docs](../termin-modules/docs/index.md)

Отвечает за descriptors, lifecycle, callbacks и plugin/module loading contracts.

### termin-collision

Source of truth: [termin-collision docs](../termin-collision/docs/index.md)

Отвечает за collision world, colliders, algorithms и C/Python API коллизий.

### termin-physics

Source of truth: пока нет отдельного `docs/index.md`.

Physics layer. Collision primitives должны оставаться в [termin-collision](#termin-collision), если они не требуют physics simulation state.

### termin-input

Source of truth: пока нет отдельного `docs/index.md`.

Input abstraction. UI event routing остается в [termin-gui](#termin-gui), platform windowing остается в [termin-display](#termin-display).

## Application Layer

### termin-app

Source of truth: [editor architecture](../termin-app/docs/editor-architecture.md), [flat viewport target model](../termin-app/docs/rendering-flat-viewport-target-model.md). Historical context: [tcgui migration](plans/2026-03-09-termin-app-tcgui-migration.md). The current [termin-app docs index](../termin-app/docs/index.md) is stale and should not be treated as an API reference.

Основное приложение/редактор. tcgui является primary UI. Qt поддерживается по возможности, но не должен быть основным направлением новых архитектурных решений.

Application-level code не должен протекать вниз в graphics/render/scene.

### diffusion-editor

Source of truth: [Architecture](../diffusion-editor/ARCHITECTURE.md)

Внешний consumer внутри монорепозитория. Хороший smoke-test публичности API: если diffusion-editor вынужден лезть во внутренности, вероятно граница модуля описана или реализована плохо.
