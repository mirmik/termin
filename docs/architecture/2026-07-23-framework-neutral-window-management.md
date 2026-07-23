# Framework-Neutral Window Management

## Status

Accepted target model for #553, #593 and #741. The first implementation
slice is #755–#760.

This decision supersedes the ownership and module-placement parts of
[Native GUI Application Host](2026-07-23-native-gui-application-host.md) and
[Native GUI Windowed and Headless Host](2026-07-23-native-gui-windowed-headless-host.md).
Their implemented shared-graphics, normalized-input, offscreen-rendering and
lifetime work remains valid migration foundation.

## Problem

The native UI migration combined several independent responsibilities in
`GuiApplicationHost`, `GuiWindowHost`, `StandaloneGuiApplication` and
`NativeUiWindowManager`:

- OS-window ownership and process-global event routing;
- native-widget input and platform-service adaptation;
- document layout, paint and GPU rendering;
- frame scheduling and application close policy;
- standalone and offscreen application composition.

That composition works, but it makes the native widget toolkit appear to own
applications and windows. It also makes a collection of `GuiWindowHost`
objects the natural multi-window API, which prevents one application from
using another UI framework or raw rendering in selected windows.

The older `termin-gui` integration had the more useful dependency direction:
a framework-neutral window bag lived below the application, while the editor
attached `tcgui.UI` objects as application-owned window content. The target C++
model keeps that separation and replaces untyped `host_data` and duplicated
SDL translation with typed handles and portable events.

## Decision

Four layers have distinct ownership:

1. `termin-graphics` owns the canonical graphics domain.
2. `termin-window` owns native-window infrastructure and a framework-neutral
   collection of presentation windows.
3. `termin-gui-native` owns the native retained widget/document toolkit.
4. The application composition root chooses the content/controller attached
   to each window and owns render scheduling and process policy.

Optional integration targets may depend on two lower layers. In particular, a
`termin-gui-native` window adapter may depend on `termin-window`; this does
not make the widget/document core depend on the window system.

```text
                         termin-graphics
                           GraphicsHost
                               ▲
                               │ borrowed
termin-window                  │
  WindowedGraphicsSession ─────┘
  WindowManager
  BackendWindow[0..N]
         ▲
         │ handles, events and platform services
         │
application composition root
  WindowSlot[0..N]
    ├── native-widget adapter ─────► termin-gui-native
    ├── another UI adapter
    └── raw renderer/controller
```

There is no universal GUI application host and no UI-specific window manager.

## Module boundaries

### `termin-graphics`

`tgfx::GraphicsHost` remains the sole owner of `IRenderDevice`,
`PipelineCache`, `RenderContext2`, shader configuration and the application
interop claim. It neither owns nor enumerates OS windows.

### `termin-window`

`termin-window` owns:

- `BackendWindowSystem` and platform bootstrap state;
- portable `WindowEvent` values;
- `BackendWindow` creation, platform services and presentation;
- `WindowedGraphicsSession`, which aggregates the window system and canonical
  graphics host in the required shutdown order;
- a framework-neutral C++ `WindowManager`.

It must not depend on:

- `termin-gui-native`, another UI framework or widget types;
- `termin-display`, scene, render framework or editor code;
- an application `WindowSlot`, controller or renderer interface.

### `termin-gui-native`

The core target owns:

- `Document` and widget lifetime;
- retained widget trees, layout, interaction, focus/capture and overlays;
- normalized document input;
- paint commands and native-widget rendering primitives.

It does not own:

- an OS window or collection of windows;
- `WindowedGraphicsSession`;
- the application event loop or process exit policy;
- primary/secondary window roles.

An optional installed adapter target may depend on both the core target and
`termin-window`. The dependency direction is:

```text
termin_gui_native::window_adapter
    ├── termin_gui_native::termin_gui_native
    └── termin_window::termin_window
```

`termin-window` never depends on this adapter. Consumers that use another UI
framework do not link it.

### Application composition

The application owns:

- the `WindowedGraphicsSession` and `WindowManager`;
- the mapping from `WindowHandle` to application content/controller;
- main-window and process-exit policy;
- render scheduling and sequential access to the shared graphics context;
- editor policy, project services, MCP and tool semantics.

The mapping may use variants, type erasure or application-specific registries.
`termin-window` does not define an `IWindowClient::render_frame()` contract:
not every window has the same update model, and some windows may not render at
all.

## `WindowManager` contract

`WindowManager` borrows one live `WindowedGraphicsSession` and owns every
`BackendWindow` created through it. The session and all application GPU
consumers outlive the manager.

The public identity is a small generational `WindowHandle`, not a pointer:

```cpp
struct WindowHandle {
    uint32_t slot;
    uint32_t generation;
};
```

The exact integer widths are an ABI choice for #756, but these semantics are
required:

- default/zero and stale handles are invalid;
- destroying a window increments its slot generation before reuse;
- equality and hashing do not expose backend-native window IDs;
- `BackendWindow&` access is short-lived and validated through a handle.

The manager provides these operations:

- create a window from `WindowConfig`;
- explicitly destroy one window;
- enumerate a stable snapshot of live handles;
- resolve a live handle to its `BackendWindow`;
- pump the platform source and append ordered events to per-window queues;
- take/drain one window's pending event batch;
- close all windows deterministically in reverse creation order.

Pumping is lossless. Polling one window must not consume another window's
events, and an application that has not yet taken a batch does not lose it on
the next pump. A global quit remains a portable event delivered according to
the backend's broadcast contract; the manager does not translate it into
"close the main window".

`WindowManager` does not store `void*`, `std::any`, Python objects, documents
or callbacks owned by a UI framework. Application content is keyed by the
same `WindowHandle` in the application layer.

## Window/content integration

A native-widget window adapter is a borrowed binding, not a host. It may:

- translate a batch of `WindowEvent` values into `Document` input;
- connect clipboard, cursor and text-input services;
- expose framebuffer extent to document layout/rendering;
- turn document invalidation into an application-visible repaint request;
- render/present when explicitly asked by the application.

It must not:

- create, destroy or retain ownership of a `BackendWindow`;
- own or close `WindowManager`, `WindowedGraphicsSession` or `GraphicsHost`;
- enumerate other windows;
- choose main/secondary roles or terminate the application;
- own a process event loop.

The adapter stores validated borrowed relationships. Teardown detaches
document/platform services and releases adapter-owned GUI GPU resources before
the application destroys the corresponding window.

## Windowed execution

A representative application loop is:

```cpp
windows.pump_events();

for (WindowHandle handle : windows.handles()) {
    WindowContent& content = application_content.at(handle);
    content.consume(windows.take_events(handle));

    if (content.needs_render()) {
        content.render_and_present(windows.window(handle));
    }
}
```

`WindowContent` above is application notation, not a `termin-window` type.
The UI layer imposes no creator/owner-thread affinity and provides no deferred
callback queue. Callers may update documents, adapters and renderer state from
their current thread; applications coordinate genuinely concurrent recording
against a shared graphics context. Closing a secondary window removes only
that handle and its application-owned content; it does not affect the graphics
session or other windows.

## Headless execution

Headless UI does not create a `WindowManager`, `BackendWindowSystem` or fake
window. It composes:

```text
application/test
├── GraphicsHost::create_isolated(...)
├── termin-gui-native Document
├── document renderer and output texture
├── queued normalized input
└── in-memory clipboard/cursor/text-input services
```

Windowed and headless paths share document, interaction, paint and renderer
primitives. They do not share an object that owns an application loop.
Offscreen publication, resize, explicit readback and synthetic input from
#742–#744 remain supported, but the owning helper is not named or specified
as an `ApplicationHost`.

Virtual-display testing remains separate: Xvfb validates the real SDL/window
path, while isolated rendering validates no-display execution.

## Current host responsibility mapping

| Current responsibility | Target owner |
| --- | --- |
| `BackendWindow` collection and close order | `termin-window::WindowManager` |
| process-global event pump and per-window batches | `termin-window::WindowManager` |
| window ID to application content mapping | application composition |
| `WindowEvent` to `Document` translation | optional native-widget window adapter |
| clipboard/cursor/text-input bridge | optional native-widget window adapter |
| document tree, interaction and invalidation | `termin-gui-native` core |
| document paint and GUI GPU resources | native-widget renderer primitives |
| frame/update scheduling | application composition |
| OS-window presentation | `BackendWindow` invoked by selected content adapter |
| isolated output publication/readback | offscreen document composition |
| main/secondary and exit policy | application composition |
| shader/runtime setup | graphics/application composition root |

`GuiApplicationHost`, `GuiWindowHost` and `StandaloneGuiApplication` are
transitional compatibility APIs. `WindowManager`, `OffscreenGuiComposition`,
`DocumentRenderer` and `GuiWindowAdapter` are the implemented target
contracts. Python binds these native types and their methods directly; it must
not introduce binding-only proxy classes or framework facades over them.
The editor's `EditorWindowRegistry` is application policy: it maps native
handles to application-selected content and does not replace `WindowManager`
or `GuiWindowAdapter`. `OffscreenGuiApplication` remains only a compatibility
alias until #760.

## Lifetime and shutdown

Windowed shutdown is explicit:

1. stop scheduling new application work and frames;
2. detach each window's application content and framework adapter;
3. release document/renderer and other per-window GPU resources;
4. destroy all manager-owned windows in reverse creation order;
5. destroy remaining application GPU consumers;
6. wait for and close `WindowedGraphicsSession`.

Destroying a manager with live windows performs step 4 and logs any failure.
Destroying or closing its borrowed session first is a diagnosed lifetime
violation. A failed close is never silently converted into success.

Headless shutdown releases document/render/output resources and application GPU
consumers before closing its isolated `GraphicsHost`; it has no window phase.

## Migration

1. **#755:** record this decision and mark the former host ownership model as
   historical.
2. **#756:** implement the installed framework-neutral `WindowManager` and
   handle/event/lifetime tests in `termin-window`.
3. **#757:** extract the optional native-widget window adapter while making the
   widget/document core independently consumable.
4. **#758:** recompose offscreen execution around document/rendering contracts,
   without application/window host ownership.
5. **#759:** migrate the editor to application-owned `EditorWindowSlot`
   records and remove Python `NativeUiWindowManager`.
6. **#745/#746:** connect and verify no-display editor execution.
7. **#760:** migrate remaining consumers and remove the compatibility host API.

The shared graphics-domain and normalized event work from #616, #703,
#735–#744 is retained. Migration changes ownership and packaging rather than
reintroducing devices, renderer loops or platform event translation.

## Completion gate

The migration is complete when:

- `termin-window` provides the only generic OS-window collection and has no UI
  dependency;
- `termin-gui-native` core is usable without `termin-window`;
- a single manager can mix multiple content/framework kinds;
- the editor owns window-content and exit policy outside the manager;
- headless execution links no `termin-window` and uses no fake window;
- the public application/window host ownership classes and Python manager are
  removed;
- lifecycle, event routing, installed consumers, editor multi-window and
  no-display smokes pass.
