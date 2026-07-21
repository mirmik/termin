# Native Framegraph Debugger

Status: native debugger ownership and frame-local capture integration are
implemented. Python contains frontend and automation adapters only.

## Ownership

`termin::FrameGraphDebugger` is the sole owner of debugger state. It is a C++
object constructed with a `RenderingManager&`; it has no dependency on the
editor, Python, tcgui, or a particular display frontend. The manager must
outlive the debugger.

The debugger owns target selection, connection state, pass/symbol/resource
selection, capture requests, captured textures, preview parameters, diagnostic
formatting, and reconciliation after render-topology changes. It stores
generation-bearing handles and selection values, not borrowed pipeline or pass
pointers. Every refresh resolves the selected target against the current
`RenderingManager::execution_targets()` snapshot. Removing a target suspends
the connection; replacing its pipeline invalidates the old request and binds
the selection to the live pipeline.

`framegraph_debugger_model.py` and `FrameGraphDebugTarget` no longer exist.
The Python `EditorFramegraphDebuggerService` is an MCP/export adapter over the
same native debugger. The native-widget and legacy tcgui dialogs are UI
projections which create a debugger and forward widget events to its bound C++
API; they do not discover targets or mutate pipelines themselves.

## Capture lifecycle

`RenderingManager` is the authoritative source of renderable targets and the
boundary around actual pipeline execution. A `FrameGraphDebugger` registers as
a `RenderExecutionObserver`. Immediately before a matching execution the
manager asks it for a frame-local `FrameGraphCaptureRequest`; immediately after
execution the debugger consumes the resulting status. The request is never
stored in a pipeline or pass.

Between-pass resource capture is executed by `RenderEngine` after the last
scheduled writer of the selected canonical resource. External/read-only
resources are captured after execution resources have been assembled. Inside-
pass capture is exposed only through the current pass's `ExecuteContext`, so a
pass can answer `should_capture_internal()` and publish a texture with
`capture_internal()`. No debugger pass is injected into the pipeline and no
persistent debug pointer or symbol is written into `tc_pass`.

This ordering matters: a resource must be copied after its producer, while the
request must be attached before the pass executes. Connection and topology
reconciliation happen independently of either operation.

## Preview composition

`FrameGraphCapture` owns copied textures and `FrameGraphPresenter` owns preview
rendering/HDR analysis. UI frontends may create temporary sampled targets for
composition, but do not own capture state. Targets are recreated on size
changes and released when their window closes.

The native UI host renders previews during its pre-render callback, inside the
active tgfx2 frame and before `Document.paint()` records texture identities.
This prevents a recreated preview target from invalidating a handle already
referenced by the current Vulkan frame.

## Production wiring

The editor creates one native debugger through the service and shares it with
the dialog and MCP namespace. F12 opens the debugger. Opening or updating a
dialog refreshes its projection, while render executions also drive the native
observer lifecycle. `RenderingModel` is no longer part of target discovery or
capture connection.
