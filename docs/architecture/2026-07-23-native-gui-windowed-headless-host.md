# Native GUI Windowed and Headless Host

## Status

Historical implementation model for #741. The presentation/input/readback
mechanics implemented by #742–#744 remain migration foundation, but sharing a
`GuiApplicationHost` between windowed and headless execution is no longer the
target architecture. The current decision is
[Framework-Neutral Window Management](2026-07-23-framework-neutral-window-management.md):
windowed applications use the framework-neutral `termin-window` manager and an
optional GUI adapter, while headless execution uses document/rendering
primitives without `termin-window` or an application host.

Implementation is split into #742, #743, #744, #745 and #746. The shared frame
core (#742) and typed input/platform boundaries (#743) are implemented. The
owning offscreen composition begins at #744. The virtual-display E2E path
remains separate in #623.

## Problem

`GuiWindowHost` already borrows the canonical `tgfx::GraphicsHost`, owns native
UI frame resources and provides the correct extension, repaint and deferred
work contracts. It still obtains framebuffer size and events directly from
`BackendWindow`, uses that window for clipboard, cursor and text input, and
calls `BackendWindow::present()` at the end of every rendered frame.

The current injection test proves that an isolated Vulkan `GraphicsHost` can
render native UI without a platform graphics session. It has to represent the
offscreen target as a fake `BackendWindow`, however, and implement window
operations as no-ops. Turning that test double into a production headless path
would preserve the wrong abstraction:

- offscreen execution is not a native window;
- a no-op `present()` does not describe where a completed frame goes;
- synthetic input and in-memory clipboard are real services, not incomplete
  SDL behavior;
- editor and engine bootstrap must not be copied merely to select a different
  presentation endpoint.

The required result is one application frame path with explicit environment
adapters, not separate windowed and headless engines.

## Decision

The reusable frame implementation is a presentation-neutral
`GuiApplicationHost`. It owns all native GUI work that must remain identical
between environments:

- the borrowed `GraphicsHost` and `Document` relationships;
- draw list, paint context, renderer and color target;
- layout, paint and GPU frame recording;
- typed frame extensions;
- repaint and owner-thread deferred work;
- dynamic texture leases;
- deterministic release of host-owned GPU resources.

Environment behavior is supplied through typed boundaries:

1. A frame endpoint supplies the current pixel extent and consumes the
   completed color texture.
2. An input source supplies ordered `WindowEvent` values and close requests.
3. Platform services provide text-input state, clipboard and cursor behavior.

These roles are implemented as the typed `GuiFrameEndpoint`, `GuiInputSource`
and `GuiPlatformServices` contracts. Missing mandatory behavior is diagnosed;
the production offscreen path does not inherit `BackendWindow` and does not
fill window methods with no-ops.

`GuiWindowHost` remains the windowed convenience composition and preserves its
existing API. It combines the shared `GuiApplicationHost` with adapters backed
by one owned `BackendWindow`.

`OffscreenGuiApplication` is the owning headless composition. It combines the
same `GuiApplicationHost` with an isolated graphics host, a fixed or explicitly
resized frame endpoint, a queued input source and in-memory platform services.
It does not initialize SDL or create a window system.

## Ownership

Windowed execution:

```text
application composition root
└── WindowedGraphicsSession
    ├── BackendWindowSystem
    ├── GraphicsHost
    └── BackendWindow
        └── GuiWindowHost
            ├── BackendWindow adapters
            └── GuiApplicationHost
                ├── borrowed GraphicsHost
                ├── borrowed Document
                ├── renderer / draw list
                ├── color target
                └── frame extensions / texture leases
```

Headless execution:

```text
OffscreenGuiApplication
├── GraphicsHost::create_isolated(...)
├── Document
├── queued input and in-memory platform services
├── offscreen frame endpoint
└── GuiApplicationHost
    ├── borrowed GraphicsHost
    ├── borrowed Document
    ├── renderer / draw list
    ├── color target
    └── frame extensions / texture leases
```

Both modes therefore install the exact same graphics identity into
`RenderEngine`, native UI extensions and application consumers. There is no
second device, render context, `RenderingManager`, widget tree or editor
controller for headless execution.

## Frame contract

One owner-thread tick has the same ordering in both modes:

1. drain ordered events from the input source and dispatch them to `Document`;
2. execute the current batch of deferred callbacks;
3. stop if the input source or application requested close;
4. skip rendering unless continuous rendering or repaint state requires it;
5. read the current physical pixel extent from the frame endpoint;
6. allocate or resize the host-owned color target;
7. run `before_ui_frame` extensions;
8. layout and paint the `Document`;
9. record and submit the native UI frame through the canonical
   `RenderContext2`;
10. run `after_ui_frame` extensions;
11. publish the completed color texture to the frame endpoint.

The windowed frame endpoint publishes by presenting into its `BackendWindow`.
The offscreen endpoint publishes a generation, color texture and the physical
extent captured for that generation. A later resize changes the next render
extent but does not reinterpret the preceding publication. Explicit blocking
RGBA-float readback waits for the host device and reads that published
texture; MCP capture and streaming can build on the same publication rather
than a disguised no-op presentation.

Frame extensions continue to receive the same `GuiWindowFrame`-equivalent
typed view of graphics identity, device, output texture and extent. They do not
receive `RenderContext2` and cannot create nested frames.

## Input and platform services

The common host consumes backend-neutral `WindowEvent` values. A windowed
source polls its `BackendWindow`; a headless source owns an ordered,
owner-thread-drained queue populated by tests, MCP or automation.

Synthetic events follow the same coordinate and focus rules as window events.
They are not direct mutations of widget internals. Pointer coordinates use
physical pixels with a top-left origin, matching the display input contract.

The offscreen composition provides meaningful platform services:

- clipboard data is stored in an explicit in-memory clipboard;
- cursor changes update observable cursor intent state;
- text-input enablement updates observable input state;
- close requests update the common application close state.

Unsupported optional integration must be represented as an explicit
capability result. Mandatory services fail construction with a logged
diagnostic rather than silently doing nothing.

## Editor composition

The native editor bootstrap is divided at the application composition root:

```text
shared editor bootstrap
├── project / scene / resource services
├── RenderingManager and RenderEngine
├── native editor Document and shell
├── editor frame extensions
└── selected GUI composition
    ├── windowed: WindowedGraphicsSession + GuiWindowHost
    └── headless: OffscreenGuiApplication
```

Backend selection does not fork editor policy. Project loading, Play/Stop,
selection, Diffusion Editor integration, dynamic textures, frame profiler,
framegraph debugger and MCP commands use the same controllers and native
widget tree.

The selected composition installs its one canonical `GraphicsHost` into the
render engine before GPU consumers are created. Shutdown always stops frame
production and destroys editor/render/UI GPU consumers before closing the
graphics host.

## Virtual display is a separate layer

Xvfb or another virtual compositor remains useful for validating SDL window
creation, native event polling, clipboard integration and physical
presentation. It is not the headless renderer architecture and is not required
by offscreen tests.

The supported test matrix is:

| Layer | Graphics path | Window system | Purpose |
| --- | --- | --- | --- |
| Native GUI contract | isolated Vulkan/D3D11 | none | deterministic layout, rendering, input and readback |
| Editor MCP headless smoke | isolated Vulkan | none | project/editor automation on a server |
| Virtual-display E2E | Mesa OpenGL | Xvfb | SDL/window lifecycle and presentation |
| Desktop smoke | platform default | real desktop | production interaction and driver behavior |

`VK_EXT_headless_surface` is not required for the isolated path because the
common host renders into ordinary textures and does not create a swapchain.

## Migration

1. #742 extracted the presentation-neutral frame core while keeping
   `GuiWindowHost` as the reference consumer.
2. #743 separated input and platform services. `GuiApplicationHost` now owns
   the common event/deferred/render tick; `QueuedGuiInputSource` and
   `InMemoryGuiPlatformServices` exercise pointer, key, text, close, clipboard,
   cursor and text-input behavior without a window.
3. #744 added the owning isolated/offscreen composition and C++/Python API,
   including resizable publication, synthetic input, observable in-memory
   services and explicit pixel readback without SDL or `DISPLAY`.
4. #737 migrated the production editor, secondary tool windows and launcher to
   the shared host contract. Python retains editor policy adapters, while
   `GuiApplicationHost` owns event dispatch, deferred work, frame recording,
   render-target lifetime and presentation.
5. #745 selects windowed or offscreen composition around one shared editor
   bootstrap.
6. #746 adds the no-display editor MCP/readback smoke.
7. #623 keeps the virtual-display window-system E2E documented and automated.

Each step must leave the ordinary windowed path working. Temporary duplication
inside a short-lived refactor is acceptable only within one card; no duplicate
render loop, editor bootstrap or public headless widget hierarchy may remain
at a card boundary.

## Completion gate

The migration is complete when:

- `GuiApplicationHost` contains the only native GUI layout/paint/frame loop;
- `GuiWindowHost` is a thin BackendWindow-backed composition;
- offscreen execution uses `GraphicsHost::create_isolated()` without a fake
  `BackendWindow`;
- windowed and offscreen modes use identical frame extension, repaint,
  deferred-work, dynamic-texture and shutdown contracts;
- the native editor selects only its environment composition, not a second
  bootstrap or engine;
- an automated MCP smoke renders and captures a real editor frame without
  `DISPLAY` or `WAYLAND_DISPLAY`;
- virtual-display testing remains an independent window-system gate.
