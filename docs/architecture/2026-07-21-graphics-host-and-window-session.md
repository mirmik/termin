# Graphics Host and Window Session

## Status

Accepted and implemented by #703.

## Decision

`tgfx::GraphicsHost` is the one canonical owner of an application graphics
domain. It owns exactly one `IRenderDevice`, one `PipelineCache`, one
`RenderContext2`, shader artifact configuration, and the legacy C interop
claim. It is owning-only: code that needs graphics receives `GraphicsHost&` or
a typed context derived from it and must not construct another host around a
borrowed device.

`BackendWindowSystem` is a platform presentation service, not a graphics
runtime. It prepares a platform-compatible device, creates equal
`BackendWindow` presentation targets on a supplied `GraphicsHost`, routes
native events, and owns platform bootstrap state such as the SDL OpenGL
context. It exposes no device/context accessors.

`WindowedGraphicsSession` is the standard composition holder used by windowed
applications. It combines one window system with one `GraphicsHost`, exposes
the host through `graphics()`, and centralizes the required close ordering. It
does not reproduce the graphics API.

## Ownership

```text
application composition root
└── WindowedGraphicsSession
    ├── BackendWindowSystem
    │   └── SDL/platform bootstrap state
    └── tgfx::GraphicsHost
        ├── IRenderDevice
        ├── PipelineCache
        ├── RenderContext2
        └── application interop claim

application composition root
└── BackendWindow[0..N]
    └── native window + per-window surface/swapchain/event queue
```

The session must outlive all windows and GPU consumers. Shutdown is:

1. stop frame production and destroy engine/UI/plot GPU resources;
2. wait for the graphics host to become idle;
3. close all windows and their swapchains/surfaces;
4. close `GraphicsHost` and release context/cache/device/interop;
5. destroy the window system platform bootstrap.

Closing the session while windows remain is a diagnosed error. Destructors log
lifetime violations; they do not hide them by zeroing window counts or
pretending dangling presentation objects are safe.

## Consumers

- `RenderEngine` receives the exact `GraphicsHost` explicitly. It may create
  an application host itself only for a standalone/headless workflow where no
  application graphics domain is installed.
- Python receives the typed host from `WindowedGraphicsSession.graphics` and
  constructs `Tgfx2Context` with `from_runtime()`. Binding keep-alive links the
  renderer context and windows back to the session; raw `uintptr_t`
  device/context handshakes are not part of the public API.
- `tcplot::GpuHost` may own a standalone `GraphicsHost` or borrow an injected
  application host; it is a plot-resource bundle, not another graphics domain.
- Android and OpenXR must adopt their platform-created devices into
  `GraphicsHost` rather than claiming interop independently.

## Multi-window presentation

There is no primary/secondary window distinction. Vulkan and D3D11 allocate a
surface/swapchain per window. SDL/OpenGL keeps one platform-owned context and
makes it current against the target compatible window. Presentation and the
shared `RenderContext2` remain sequential facilities until a separate
concurrency design is accepted. This ordering does not impose thread identity
checks on callers.
