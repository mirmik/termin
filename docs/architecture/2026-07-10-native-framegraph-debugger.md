# Native Framegraph Debugger

Status: native debugger ownership, frame-local capture integration and the
production native-widget view are implemented in C++. Python contains window
bootstrap and automation adapters only.

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
same native debugger. `FrameGraphDebuggerView` is the production C++ widget
projection: it builds the complete tree in an application-owned `TcDocument`,
owns callbacks and selection synchronization, and presents both captures. The
legacy tcgui dialog remains a compatibility frontend; it does not discover
targets or mutate pipelines itself.

## Frontend source boundary

`IFrameGraphDebuggerSource` is the only debugger interface consumed by
`FrameGraphDebuggerView`. It publishes immutable value snapshots containing
topology, selection, status, formatted diagnostics, and capture-image
descriptors, and accepts selection/session commands. `LocalFrameGraphDebuggerSource`
projects the sole `FrameGraphDebugger` into that contract; it neither owns nor
duplicates native debugger state.

Image descriptors contain dimensions, format, depth classification, and a
source-local generation, but no transport identity or remote GPU handle. The
source is responsible for rendering its image into a client-local preview
target and for depth readback. Consequently a remote implementation can upload
decoded bytes into a local texture while the view follows exactly the same
path as an in-process capture. Transport, reconnect, and packet handling do not
belong in the view or in Python.

`RemoteFrameGraphDebuggerSource` implements that boundary for topology-only
sessions. `termin-framegraph-remote-client` owns loopback TCP, authentication,
framing and reconnect on a network thread; callbacks publish copied immutable
snapshots under a mutex and never touch widgets or rendering objects. Commands
cross a bounded SPSC queue from the editor thread and are discarded at a
session boundary. A disconnect retains the latest bounded topology but marks
it `stale`, while a new session clears session-scoped target/pass identities.

The production view contains explicit port/token Connect, Disconnect, Use
Local, Start/Stop Live and Burst controls, including FPS, long-edge and burst
count limits. The token is launch-scoped input and is not persisted. Source
switching replaces only the source behind the existing widget tree; no second
debugger UI or Python data plane is created. Topology refresh is rate-limited,
stale-revision responses schedule reconciliation, and remote errors/drop counts
are surfaced in the existing status bar.

Exact remote snapshots reuse the same frame-local capture instrumentation as
the local debugger. The target render thread performs capture and bounded
readback, then hands an immutable CPU blob to the network thread for chunking
and transmission; graphics handles never cross that boundary. The remote
source assembles chunks in order under a memory budget and publishes a shared
immutable CPU capture. Incomplete, duplicate or out-of-order transfers are
rejected visibly rather than exposed as partial images. The source lazily
uploads completed bytes into the debugger window's own graphics domain and
uses the existing `FrameGraphPresenter`, so Canvas fit/zoom, channel selection,
HDR highlighting and depth inspection follow the local path. Selection starts
one exact request, Pause cancels pending work, and disconnect/source switch
release both the CPU blob and source-owned local texture deterministically.

Remote mode also offers bounded Live Preview and exact Burst. Preview applies
its long-edge bound while copying into the target-owned capture texture, so
readback sees only the reduced image, converts it to RGBA8, and observes the
requested FPS ceiling. Its cross-thread handoff is a single latest-wins slot:
one frame may be in network transfer and only one newer frame can wait. Burst
captures 2--16 exact frames with one graph revision and explicit ordered
indices. Revision changes, cancellation and disconnect terminate either mode;
drops become protocol gaps instead of latent queued video.

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
rendering/HDR analysis. `FrameGraphDebuggerView` creates the temporary sampled
targets in the window's existing graphics domain, recreates them on size
changes and releases them on window deactivation or close. It does not own
capture state or create a device/session.

The native UI host renders previews during its pre-render callback, inside the
active tgfx2 frame and before `Document.paint()` records texture identities.
This prevents a recreated preview target from invalidating a handle already
referenced by the current Vulkan frame.

## Production wiring

The editor creates one native debugger through the service and shares it with
the C++ view and MCP namespace. F12 opens the debugger. Python only creates the
secondary window, attaches the C++ pre-render callback and forwards the editor
update loop. `RenderingModel` is no longer part of target discovery or capture
connection.
