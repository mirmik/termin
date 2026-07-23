# Native GUI Application Host

## Status

Accepted target model for #593. This decision refines the standalone host
implemented by #616 and applies the canonical graphics ownership established
by #703 in
[Graphics Host and Window Session](2026-07-21-graphics-host-and-window-session.md).

The shared presentation-neutral frame implementation and isolated/offscreen
composition are refined further in
[Native GUI Windowed and Headless Host](2026-07-23-native-gui-windowed-headless-host.md).
In this document, ownership attributed to `GuiWindowHost` includes resources
owned by its composed `GuiApplicationHost`; the window wrapper itself remains
the platform adapter.

## Problem

`termin-gui-native` now provides a public C++ `ApplicationHost` that is useful
for a small one-window program: it creates a native graphics session and
window, routes input into a `Document`, paints the document into a resizable
color target and presents it. The same object currently also owns an injected
`WindowedGraphicsSession` and configures process-global shader runtime state.

That combined ownership is not a valid integration boundary for the editor or
other multi-window applications:

- one application must have exactly one canonical `tgfx::GraphicsHost`;
- one `WindowedGraphicsSession` must outlive every window and GPU consumer;
- editor, Frame Profiler and Framegraph Debugger windows must share that
  graphics domain;
- a per-window UI adapter must not create, adopt, reconfigure or destroy the
  application device;
- Python must project the same native lifetime model rather than introduce a
  second host architecture.

## Decision

The final public model has three distinct roles:

1. `tgfx::GraphicsHost` is the sole owner of the application graphics domain.
2. `WindowedGraphicsSession` is the application-level composition holder for
   one `GraphicsHost` and one platform window system.
3. `GuiWindowHost` is a per-window native-UI adapter that borrows the session's
   graphics domain and owns only resources belonging to its window.

The current `ApplicationHost` is split accordingly. The reusable per-window
type is named `GuiWindowHost`. A separate `StandaloneGuiApplication` provides
the convenient one-window composition previously supplied by
`ApplicationHost`.

No additional `ApplicationRuntime`, GUI-owned device holder or borrowed-device
wrapper is introduced.

## Ownership model

```text
application composition root
└── WindowedGraphicsSession
    ├── BackendWindowSystem
    ├── tgfx::GraphicsHost
    │   ├── IRenderDevice
    │   ├── PipelineCache
    │   ├── RenderContext2
    │   ├── ShaderArtifactResolver
    │   └── application interop claim
    │
    ├── BackendWindow
    │   └── GuiWindowHost
    │       ├── borrowed Document
    │       ├── UI draw list and renderer
    │       └── window color target
    │
    └── BackendWindow
        └── GuiWindowHost
            ├── borrowed Document
            ├── UI draw list and renderer
            └── window color target
```

The application composition root owns `WindowedGraphicsSession`.
`GuiWindowHost` borrows the session or its `GraphicsHost`, owns one
`BackendWindow`, and borrows one `Document`. The session and document must both
outlive the window host. Bindings enforce those relationships with typed
references and keep-alive edges; raw device/context pointers are not part of
the public contract.

One `Document` may be bound to exactly one live `GuiWindowHost`: the host
services stored by the document (text measurement, clipboard and cursor) are
per-window. `Document::close()` and move operations reject a live binding, so
an active host cannot retain a stale object address. Distinct
windows use distinct documents even when they share one graphics domain.

`GuiWindowHost` owns:

- one presentation window;
- event routing between that window and its `Document`;
- text input, clipboard and cursor bridges for the document;
- the UI draw list, paint context and renderer;
- the resizable per-window color target;
- layout, paint, frame submission and presentation for that window;
- repaint state and owner-thread deferred work;
- host-created UI GPU resources and their deterministic release.

`GuiWindowHost` does not own:

- `IRenderDevice`, `PipelineCache`, `RenderContext2` or `GraphicsHost`;
- `WindowedGraphicsSession` or platform bootstrap state;
- the supplied `Document` or application controller;
- editor policy, MCP, screenshots, project services or debug-tool semantics;
- process-global shader configuration.

## Construction APIs

The primary C++ construction path accepts the existing application session and
creates one compatible window:

```cpp
auto session = termin::create_native_windowed_graphics();
termin::gui_native::Document document;

termin::gui_native::GuiWindowHost host(
    *session,
    document,
    termin::gui_native::GuiWindowConfig{
        .window = {"Tool", 900, 700},
        .font_path = font_path,
    });
```

A lower-level injected constructor may accept `GraphicsHost&` and an owned
`BackendWindowPtr` for tests and established composition roots. It must verify
that the window belongs to the same graphics domain and must not adopt or close
the host.

The standalone convenience layer owns the objects in the required order:

```text
StandaloneGuiApplication
├── WindowedGraphicsSession
├── Document
└── GuiWindowHost
```

It is a composition convenience, not a second runtime abstraction. Its
`document()` accessor lets the application build its widget tree without
taking document ownership. Its destructor closes `GuiWindowHost`, destroys the
document and only then closes the session.

## Shader configuration

Shader artifact and compiler configuration is established once by the
application composition root while creating/configuring `GraphicsHost`.
Per-window hosts consume the configured host and never call global
`tgfx2_set_shader_*` functions or mutate shader-related environment variables.

`StandaloneGuiApplication` may resolve SDK defaults before constructing its
session, because it is the composition root for that standalone process. The
resolved configuration is applied to the canonical `GraphicsHost`, not retained
as independent mutable state on each window.

Font selection remains per-window UI configuration because it belongs to the
UI renderer rather than the graphics domain.

## Multi-window execution

There is no primary/secondary graphics ownership distinction. Every
`GuiWindowHost` uses the same `GraphicsHost`; each owns an equal presentation
window and independent document/render target.

The application loop owns the collection of window hosts. It drains/routes
platform events and ticks requested windows sequentially on the graphics owner
thread. Recording or presenting two windows concurrently, nesting
`RenderContext2` frames, or updating a window host from a background thread is
outside this contract.

Deferred work may be submitted from another thread, but it is executed only on
the owner thread at a documented point before the next frame. Failures are
logged and propagated; a failed callback is not silently ignored.

## Extension boundary

The public host supports narrow native extensions without absorbing editor
policy. An extension may participate in documented frame stages through a
typed C++ interface and may request repaint or host-owned GPU services. It does
not receive ownership of the graphics host.

The initial stages are:

1. `before_ui_frame` for synchronizing host-side surfaces and application
   render results before document paint;
2. normal document layout/paint and UI submission owned by `GuiWindowHost`;
3. `after_ui_frame` for bounded diagnostics/readback scheduling that must not
   start a nested frame;
4. `detach` before window resources are destroyed.

Extensions are installed as host-owned `GuiWindowFrameExtension` objects.
Their frame object exposes the host, canonical graphics identity, device and
the host-owned color target dimensions, but deliberately does not expose
`RenderContext2`. Removal and host shutdown call `detach` exactly once.

Editor screenshot/MCP routing, project services, viewport policy and debug-tool
commands remain in `termin-app`. They may be implemented as application-owned
extensions, but they are not methods on the generic host.

Arbitrary Python callbacks do not receive a raw `RenderContext2`. Python uses
bound native extensions and host services. This keeps frame nesting, device
identity and shutdown enforceable.

## Dynamic texture leases

Host-side image surfaces use an explicit lease bound to the canonical
`GraphicsHost` identity. The lease API required by #596 supports two mutually
exclusive modes:

- owned RGBA8 texture: created and destroyed by the lease;
- borrowed texture: referenced for presentation but never destroyed by the
  lease.

Create, full update, rectangular update, resize/recreate, clear and release run
on the graphics owner thread. Each operation checks host liveness and graphics
domain identity. Updating a visible lease requests repaint. Device mismatch,
stale widget handles and use after host shutdown are diagnosed errors.

The core `Canvas` widget continues to store a non-owning `TextureHandle`; it
does not acquire GPU ownership or a Python/numpy dependency.

The public C++ surface is `DynamicTextureLease(GuiWindowHost&)`. An owned lease
accepts tightly packed RGBA8 bytes through `set_rgba8()` and
`update_region_rgba8()`. A same-size full update preserves the handle; a size
change creates and uploads the replacement before destroying the old texture,
then updates every bound Canvas. `clear()` returns the lease to reusable
`Empty` state, while idempotent `release()` permanently detaches it.

Borrowing requires both `GraphicsHost& texture_owner` and `TextureHandle`.
`TextureHandle` contains only a device-local integer and cannot prove its
graphics domain by itself, so accepting a bare handle would make mismatch
detection impossible. The lease compares the typed owner with the window
host's canonical graphics identity and verifies that the handle denotes a live
sampled texture. It never destroys a borrowed texture.

Canvas bindings are stored as document widget handles, not raw Canvas
pointers. Every update resolves and type-checks those handles before touching
GPU state. Destruction or resize refreshes the Canvas's non-owning texture id,
and stale Canvas bindings fail with a logged error. Host shutdown invalidates
all leases and destroys every remaining owned texture exactly once before
renderer/device teardown.

The Python projection accepts C-contiguous `uint8[height, width, 4]` arrays:

```python
lease = DynamicTextureLease(window)
lease.bind_canvas(canvas)
lease.set_rgba8(image)
lease.update_region_rgba8(x, y, changed_pixels)
```

Numpy conversion and shape validation live exclusively in the binding. The
C++ lease and Canvas have no numpy dependency.

## Python projection

Python exposes the same hierarchy:

```python
session = WindowedGraphicsSession.create_native()
document = Document()
try:
    with GuiWindowHost(
        session,
        document,
        title="Diffusion Editor",
        width=1280,
        height=720,
    ) as window:
        while window.tick():
            update_application_state()
finally:
    document.close()
    session.close()
```

The binding:

- keeps the session and document alive while a window host exists;
- exposes deterministic `close()` and context-manager support;
- never treats Python GC as the authority for device/session lifetime;
- logs a lifetime violation if an object reaches finalization while still
  active;
- exposes typed host services and leases instead of raw device addresses.

Tools that do not inject an application-owned graphics session can use
`StandaloneGuiApplication(...)` as a context manager. Its `document` and
`window_host` properties are the same public Python types and remain borrowed
views of the C++ standalone composition; closing the application invalidates
both views in host/document/session order.

Python may remain the application bootstrap and policy layer. It does not own a
parallel renderer/event/lifetime implementation.

## Editor and tool composition

The editor owns one `WindowedGraphicsSession`. Its main window, Frame Profiler
and Framegraph Debugger are peer GUI windows in the same graphics domain:

```text
EditorSession
├── WindowedGraphicsSession
├── EditorMainWindow
│   ├── editor controller/view state
│   ├── Document
│   └── GuiWindowHost
├── FrameProfilerWindow
│   ├── FrameProfilerController
│   ├── Document
│   └── GuiWindowHost
└── FramegraphDebuggerWindow
    ├── FrameGraphDebugger controller/view
    ├── Document
    └── GuiWindowHost
```

Frame Profiler and Framegraph Debugger UI construction moves to C++. Python is
limited to bootstrap/menu composition while those paths remain Python-hosted.
Debug preview textures borrow resources from the same graphics domain and never
create a separate device or session.

## Shutdown

Shutdown is explicit and ordered:

1. stop producing frames and reject new deferred work;
2. detach extensions and release owned leases/resources;
3. wait for outstanding host GPU work where required;
4. close every `GuiWindowHost`, clearing callbacks from its borrowed document;
5. destroy window controllers and documents;
6. close remaining application GPU consumers;
7. close `WindowedGraphicsSession`, which closes `GraphicsHost` and platform
   state in canonical order.

Closing a session with live window hosts remains an error. A window-host
destructor must log lifecycle violations; it must not hide them by dropping
borrowed pointers or pretending the session was closed successfully.

## Migration

1. Introduce `GuiWindowHost` with a borrowed session/graphics contract and
   focused injected-window tests.
2. Move shader configuration out of the current per-window `ApplicationHost`
   and into standalone/application composition.
3. Rebuild the current standalone behavior as `StandaloneGuiApplication` and
   migrate Tally/showcase without regressing the installed SDK consumer.
4. Publish Python bindings with keep-alive and deterministic-close tests.
5. Replace Python `NativeUiHost` rendering/event ownership with the public
   window host while keeping editor-only policy as extensions/adapters.
6. Move Frame Profiler and Framegraph Debugger document/view composition to
   C++ window objects using the same host.
7. Add the dynamic texture lease from #596 and migrate one-shot editor preview
   uploads to it.
8. Remove the old Python host implementation after no production consumer owns
   rendering or window lifecycle through it.

## Card consequences

- #616 remains the standalone-host foundation and requires its Windows
  installed-consumer verification; its ownership shape is refined here.
- #593 is the migration umbrella for this decision.
- #735 implements the borrowed `GuiWindowHost`, typed native extensions and
  standalone composition.
- #736 publishes the Python lifetime projection after #735.
- #737 migrates production editor/multi-window hosting after #735 and #736.
- #738 moves Frame Profiler view/window composition to C++ after #737.
- #596 implements the graphics-domain-bound dynamic texture lease after #735
  and #736.
- #722 moves Framegraph Debugger controller/view composition into C++ on the
  public window host; it does not add a debugger-specific graphics runtime.
- #741–#746 reuse the same frame implementation for isolated/offscreen editor
  execution; they do not introduce another GUI or engine runtime.

## Non-goals

- replacing `GraphicsHost` or `WindowedGraphicsSession`;
- introducing a second application graphics domain for tools or windows;
- making `termin-gui-native` depend on `termin-app`;
- moving editor policy, MCP transport or project services into the generic
  host;
- concurrent `RenderContext2` recording across windows;
- making `Canvas` own textures or depend on numpy;
- preserving the current Python `NativeUiHost` as a permanent compatibility
  architecture.
