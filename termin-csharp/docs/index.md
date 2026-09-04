# termin-csharp

`termin-csharp` contains C# bindings/runtime packaging for Termin native
libraries.

Related documents:

- [Examples README](../examples/README.md)
- [Build system](../../docs/build-system.md)
- [2D plot customization](tcplot-customization.md)
- [3D plot customization](tcplot-3d-customization.md)

## Main Areas

- Native bridge project in `Termin.Native/`.
- Test project in `Termin.Test/`.
- CMake build integration in `CMakeLists.txt`.
- Examples in `examples/`.

## Public API

C# project: `Termin.Native`.

`Termin.Native` exposes `TcVisualScene2D`, common non-owning
`GraphicItemRef2D` references and typed factories for `GroupItemRef2D`,
`RectItemRef2D`, `PathItemRef2D`, `TextItemRef2D`, `ImageItemRef2D` and
`HitRegionItemRef2D`. Each factory creates an existing native item body,
adopts it into the scene and returns a full generation-handle wrapper.

Low-level consumers may own topology, transforms and presentation policy.
Standard chart topology and layout belong to the native tcplot composer. Item
bodies, paint execution and backend resources remain native. Disposing a scene
makes all wrappers stale; wrong-type casts and stale operations fail explicitly.
User-defined C#/Python item bodies and managed paint callbacks are not part of
this surface.

Retained chart bindings build on the same base references:

- `PlotProjectionRef2D` owns an explicit generation-checked native projection;
- `PlotGridItemRef2D`, `PlotLineSeriesItemRef2D` and
  `PlotScatterSeriesItemRef2D` are non-owning typed views of scene-owned native
  items;
- large data replacement/append, nearest-point queries and GPU resources stay
  native;
- `RetainedPlotLayout2D` exposes native fit/tick/UTF-8 formatting and text
  measurement through the active `GpuHost` font.

These types are the public bodies used by tcplot's native open chart composer;
they do not introduce another renderer or an inaccessible layout tree.

`Chart2D` is a thin managed projection of native `RetainedChart2D`. The native
composer assembles a single panel into one public `TcVisualScene2D`, owns the
projection and standard layout policy, and exposes root, plot-area, series,
annotation, chrome, axis, legend, overlay and tick-label groups. Backgrounds,
grid, axes, title and axis labels are typed `ChartPart2D<T>` slots:
applications can mutate the current native item, replace it with another item
from the same scene, or remove it. Line and scatter items keep their native
handles and data across `Resize`, `PanBy`, `ZoomAt`, range and theme updates.

`AddLineSeries` and `AddScatterSeries` return generation-checked semantic
series objects. They keep name, visibility, legend participation, native data
bounds and the public scene item coherent without copying point arrays into
C#. Their style setters also refresh the chart-owned retained legend. The
lower-level `AddLine` / `AddScatter` item APIs remain available when an
application intentionally wants only raw scene-item composition.

Text measurement, tick generation, pooling, clipping and projection updates
remain native. `Chart2D` borrows its `GpuHost`, exposes its chart-owned scene
and projection through non-owning wrappers, and must be disposed before the
host. `Annotations` and `Overlay` are ordinary public groups into which callers
can insert built-in retained items. `Fit()`, `FitX()` and `FitY()` scan the
effective-visible native series without copying their data into the composer or
C#. `ChartInteraction2D` owns frontend-neutral middle-drag pan and
cursor-anchored wheel zoom state. `Chart2DWpfInteraction` only adapts WPF
framebuffer events; Ctrl+wheel selects X-only zoom and real WPF portals retain
input priority over the rendered scene. See
`examples/RetainedChartComposition` for replacement of a standard plot
background without extending the native ABI.

`MultiChart2D` is the native multi-panel coordinator over the same composer.
It owns one public scene, stable generation-checked panel handles, shared X,
independent panel Y ranges, safe dynamic panel count, fixed or distributed
panel height, virtual extent and scroll offset. Hidden panel roots do not
render or rebuild layout during shared-X updates; a panel entering the viewport
receives its deferred X range and new viewport in one native frame mutation.
For an already visible panel, shared-X uses the composer's X-only invalidation
path: projection, grid and X-axis chrome update without remeasuring text or
rebuilding Y-axis/layout geometry.
Each panel is exposed as a borrowed `Chart2D`, so customization and semantic
series APIs stay identical. `MultiChart2DWpfInteraction` maps middle drag,
wheel scrolling and Ctrl+wheel shared-X zoom without moving chart layout into
WPF. A non-owning `MultiChart2DGroup` coordinates shared X, panel count/layout,
theme and clamped scroll across separate time/frequency chart columns.
`examples/AllianceStreamingChartsExample` exercises that contract with two
15-panel columns, 60 streaming native series, synchronized navigation and a
shared external scrollbar. `RetainedChartComposition` additionally renders
the top and bottom of both 15-panel scenes through the installed-SDK D3D11
offscreen path, so the multi-chart acceptance reaches GPU execution rather
than stopping at scene construction.

`RetainedChart3D` exposes a plot-specific retained scene with generation-
checked surface, scatter and grid references. Surface/scatter `SetData`
preserves item identity, style and unrelated GPU caches. `Camera.Fit()` frames
axis-scaled data without changing orbit orientation; `Camera.Reset()` also
restores the canonical orientation. `MsaaSamples` owns render-target sampling,
and `RetainedChart3DHost` renders on demand by default. Attach, resize, DPI,
visibility and camera input schedule frames automatically; consumers call
`RequestRender()` after direct data, style, camera or chrome mutations.
Animated consumers can opt into `ContinuousRendering = true`. The host also
suspends rendering while effectively invisible. See
`examples/RetainedChart3DWpfExample` for the complete D3D11 vertical slice.
The generic `RetainedScene2DHost` exposes the same MSAA policy and visibility
suspension for composed 2D scenes. It renders continuously by default for
backward compatibility. Consumers with explicitly scheduled scene mutations
can set `ContinuousRendering = false` and call `RequestRender()` after each
mutation; resize, DPI and visibility changes still invalidate automatically.
`FrameRendered` reports native paint/freeze/CPU-submit, D3DImage present and
portal-update durations without forcing GPU synchronization; submit duration
is not presented as GPU wall time.
The native host reuses draw-command storage across frames. Visual-scene order
is cached independently from mutable item content, and retained plot series
reuse their batch objects instead of allocating one during every paint.
The WPF interaction adapters request a frame after navigation. The Alliance
streaming example uses this mode for both coordinated scenes and 2x MSAA.

The SDK build path is handled by `build-sdk-csharp.sh` / `build-sdk-csharp.ps1`. For WPF plot consumers such as Alliance, use the plot-only D3D11 profile:

```powershell
task build:csharp -- --plot-d3d11 --no-sdl --no-vulkan --no-opengl
```

That profile generates only the tcplot C# bridge plus `Termin.Wpf`, copies the complete plot runtime closure (`termin.dll`, `tcplot.dll`, `termin_visual_scene.dll`, `termin_base.dll`, `termin_mesh.dll`, `termin_graphics*.dll`, `termin_graphics_binding_policy.dll`, `termin_inspect.dll`, `termin_materials.dll`, and `termin_render_core.dll`), and packages only D3D11 shader artifacts required by plots. The default `full` profile keeps the broader scene/render/component bindings for development.
Generated bindings carry an explicit profile marker. Direct `dotnet build`
uses that marker when no profile is specified and rejects an explicitly
requested profile that does not match the generated SWIG files. Switch
profiles through `build-sdk-csharp.*` (or reconfigure and build the native
CMake target) before invoking managed-only builds.

Both `full` and `plot-d3d11` profiles expose `PlotView2D` data markers.
`create_data_marker`, `update_data_marker`, `data_marker_snapshot`,
`destroy_annotation` and `take_annotation_action` exchange value-only
`PlotAnnotationHandle`, detached snapshot and polling-action objects. Managed
handle disposal releases only the SWIG value copy; the native view remains the
sole annotation owner. Cross-view and stale handles fail safely through the
complete layer/index/generation identity.

`Termin.Wpf` is Windows-only and multitargets `netcoreapp3.1` plus `net8.0-windows` through the WindowsDesktop SDK. The Windows SDK drop writes framework-specific managed assemblies under `sdk/csharp/lib/<tfm>/`; flat `sdk/csharp/lib/*.dll` copies are kept for legacy consumers and use the `netcoreapp3.1` WPF assembly. The Linux `build-sdk-csharp.sh` stage builds and packages `Termin.Native` plus Linux native `.so` runtime artifacts, but intentionally does not build `Termin.Wpf`.

WPF scene hosts use the full D3D11-only SDK:

```powershell
task build -- --no-sdl --no-vulkan --no-opengl
```

Create a `D3D11OffscreenDisplay` after acquiring `Tgfx2Host`, bind its
non-owning generation handle to `Tgfx2D3D11ImageHost`, render the display
through `RenderingManager`, then call `PresentDisplay()`. The image host
validates the display graphics-domain key before presentation and routes
DPI-scaled pointer, wheel, key, and text input through typed display calls.
Shutdown order is image host, owning display, then `Tgfx2Host`; C# finalizers
do not own native display or surface lifetime. `examples/SceneApp` is the
canonical executable reference and supports `--smoke`.

Plot customization docs are source-of-truth here and are copied into consumer
SDK drops by `VdegNexus/TerminSdk/update-sdk.ps1`.
