# Native nodegraph bindings

`NativeNodeGraph` is an owning `IDisposable` facade over the native authoring
graph/controller. It does not execute graphs or define application DAG policy.
Pass a managed connection validator to its constructor for domain rules; native
socket type/cardinality rules still apply. Descriptor strings use UTF-8 and
node/port IDs are separate from displayed labels.

`NativeGraphValue` owns a deep managed copy of scalar/container data. `Number`
stores a native double, `Integer` stores a signed 64-bit integer, and typed
`GetSnapshot()` / `Replace()` preserve those types and values. Snapshot values
can be passed to calculation workers without sharing the mutable native graph.
The existing native JSON path uses the legacy `nos::trent` number conversion;
use typed snapshots when exact 64-bit integer values or numeric types matter.

`NativeUiDocument` owns widgets. `NativeNodeGraphView` borrows the document and
graph and exposes its root widget, `Rebuild`, `Sync`, camera viewport and managed
events. Add its root to the document before rendering. The view invokes the
optional parameter presenter for native int/float/bool/text/enum editors.
Enum choices have distinct stored values and displayed labels. Callback values
and stable IDs are copied before returning to native code; descriptor strings
are retained until native code has copied them. Managed callback exceptions are
logged in English and surfaced through `LastCallbackError` /
`ThrowIfCallbackFailed()`.

Default socket display labels come from
`node.data.socket_labels.inputs[stableSocketId]` and
`node.data.socket_labels.outputs[stableSocketId]`. Omitted labels use the socket
ID. Changing a label never changes the connection endpoint.

`NativeDocumentRenderer` borrows a document and existing `GpuHost`. Its C ABI
adapts the existing `DocumentRenderer`; native code continues to own layout,
paint, focus, capture and widget input routing. The borrowed output texture is
RGBA16F DisplayLinear. Hosts must apply the standard presentation transfer.
Pointer coordinates use logical document pixels; metrics use framebuffer
pixels plus the DPI density scale.

WPF's reusable `NativeDocumentHost` adapts pointer/wheel/capture, key/text/focus,
cursor and clipboard to this renderer. It presents through
`Tgfx2D3D11ImageHost`, sharing the same D3D11 runtime as charts. It creates no
SDL window, event loop or Python runtime.

All graph/document/view/renderer operations, including disposal, belong to
their creating UI thread. Keep the GPU host alive and undisposed while attached.
Dispose in this order: WPF host (or renderer), view, document, graph, GPU host.
Dispose is idempotent. Explicitly dispose these objects; callback roots remain
alive until native teardown. Graph/document disposal rejects active borrowers.

## Installed SDK example

Build through the public entry point:

```powershell
task build:graphics -- --no-sdl --no-vulkan --no-opengl
```

The SDK ships the sample source and neutral fixture. With a relocated SDK at
`C:\TerminGraphicsSdk`, run:

```powershell
$sampleBuild = "C:\TerminSamples\NativeNodeGraph"
dotnet run --project C:\TerminGraphicsSdk\csharp\examples\NativeNodeGraphWpf -p:TerminSdkRoot=C:\TerminGraphicsSdk "-p:BaseOutputPath=$sampleBuild\bin\" "-p:BaseIntermediateOutputPath=$sampleBuild\obj\"
```

The sample loads 24 nodes and 31 connections, supports RU/EN labels and native
parameter editors, and logs copied managed events. It has no SignalCore runtime
dependency. Add `-- --smoke` for render/GC/resize/reopen checks. Calculation,
application persistence, toolbox/undo and inline plots remain application work.

Run binding and WPF checks with `task test -- --csharp-only`. Native bridge and
nodegraph checks are part of
`task test:cpp -- --profile graphics --no-sdl --no-vulkan --no-opengl`.
`task test:graphics:nuget` validates the production package closure and installed
package consumption, including absence of Python/SDL/Vulkan/OpenGL.
After an existing SDK build, `task test:graphics:nuget:installed` runs the same
package/consumer check without rebuilding the SDK. Automated sample outputs stay
in the checkout build directory, outside the installed SDK.
