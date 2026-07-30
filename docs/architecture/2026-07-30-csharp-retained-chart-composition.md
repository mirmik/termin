# C# Retained Chart Composition

## Status

Intent accepted. The projection contract, retained native grid and
line/scatter series items, and value-only range/tick/text-measurement
utilities are implemented. The neutral built-in GraphicItem C ABI and typed
C# visual-scene wrappers are implemented; tcplot-specific typed wrappers and
managed chart composition remain.

The existing retained visual-scene initiative delivered the common
`tc_graphic_item` object model and a tcplot annotation vertical slice. It did
not decompose a complete chart into bindable retained parts. The current
`PlotView2D` and `PlotView2DMulti` C# surfaces remain transitional monolithic
facades.

## Intent

A C# application must be able to construct and customize a chart as an
ordinary retained `TcVisualScene` tree. It must receive typed, stable
generation-handle wrappers for the meaningful chart parts instead of calling a
growing set of layout- and style-specific methods on an opaque native
`PlotView2D`.

C# owns chart composition and layout policy:

- which chart parts exist;
- how they are nested, clipped and positioned;
- how axes, labels, legends and annotations are arranged;
- which standard parts are replaced or extended;
- how application-specific themes and interaction policies are applied.

C++ continues to own expensive data processing and rendering:

- large series storage and upload;
- persistent GPU buffers and resource lifetime;
- line expansion, point batching, tessellation and decimation;
- backend execution;
- native text measurement and glyph resources;
- native hit preparation for large data sets.

The language boundary carries handles, compact state and explicit mutations.
It does not carry per-frame draw command streams, projected point arrays,
backend contexts or managed callbacks invoked during rendering.

## Target composition

A conventional 2D chart is a composition, not a closed native widget:

```text
TcVisualScene
└── chart root (GroupItem2D)
    ├── background (RectItem2D)
    ├── title (TextItem2D)
    ├── plot area (GroupItem2D + clip)
    │   ├── plot background (RectItem2D)
    │   ├── grid (PlotGridItem2D)
    │   ├── line/scatter series (Plot*SeriesItem2D)
    │   └── retained annotations (ordinary GraphicItems)
    ├── X axis parts
    ├── Y axis parts
    └── legend and application overlays
```

This is an illustrative default composition, not a required concrete type
hierarchy. A C# composer may omit, reorder or replace parts. The renderer sees
only the common `tc_graphic_item` topology and vtable contract.

## Module boundaries

### `termin-visual-scene`

Owns reusable retained visual infrastructure and backend-neutral item types:

- `TcVisualScene`, `tc_graphic_item`, handles and topology;
- transforms, visibility, opacity, z-order and clipping;
- generic rect, path, text, image, hit-region and group items;
- generic optimized polyline, point or custom-batch items when their contract
  contains no plot-domain semantics;
- typed cross-language factories and item wrappers;
- generic paint, bounds and hit-test dispatch.

It must not know about series, axes, data ranges, tick locators, colormaps or a
chart layout policy.

### `tcplot`

Owns plot-domain state, calculations and optimized plot items:

- data ranges and data-to-visual projection;
- tick calculation and formatting policy;
- line, scatter and later surface data storage;
- native plot-specific `GraphicItem2D` implementations such as
  `PlotLineSeriesItem2D`, `PlotScatterSeriesItem2D` and `PlotGridItem2D`;
- series GPU resources, batching, decimation and hit preparation;
- retained semantic annotations and their projection;
- optional reusable native utilities for auto-range and tick generation.

Plot-specific items are adopted into an ordinary `TcVisualScene`. They use the
same handles, topology and lifetime rules as built-in visual-scene items, but
their concrete implementations remain in `tcplot`.

### C# chart composition

The managed layer owns the default chart assembly:

- `Chart2D` or an equivalent managed composer;
- named typed references to chart parts;
- layout constraints and measurement passes;
- theming and application customization;
- WPF interaction policy and host integration.

The managed composer is allowed to call explicit native measurement and
projection utilities. It must not reproduce font metrics, GPU geometry
generation or large-series rendering in managed code.

## Shared plot state

Large data items must not require C# to resend projected vertices after every
pan, zoom or resize. Plot items consume the tcplot-owned, generation-checked
native `PlotProjection2D`. It belongs to exactly one `TcVisualScene` and stores
the compact viewport, plot area, clip, data range and pixel scale required for
data-to-visual conversion. A transactional update increments one revision;
items may snapshot the state once per operation without retaining a pointer
into the projection pool.

`PlotProjection2D` creation and destruction are explicit. Destroying its owner
scene makes the projection handle stale; the owner must still release the
projection slot during deterministic teardown. Future plot items validate that
their projection belongs to their own scene. This object belongs to tcplot,
not to `termin-visual-scene`.

State propagation must be explicit and deterministic. A generic observer,
implicit cross-thread synchronization or managed callback from the renderer is
not part of the contract.

`PlotGridItem2D` is the first consumer of this contract. It is an ordinary
tcplot-owned `NativeGraphicItem2D`, adopted and destroyed by its
`TcVisualScene`. It owns copied major tick values and style, snapshots the
projection during native paint, filters ticks to the current range and emits
one backend-neutral path. Its C API accepts only scene/projection/item handles
and detached arrays or values.

`PlotLineSeriesItem2D` and `PlotScatterSeriesItem2D` own copied native data,
explicit style and a shared retained GPU body. Their C ABI supports complete
replacement, incremental line append, detached snapshots/copies and native
nearest-point queries. Paint contributes one small `DrawRetainedBatch2D`
command; the command shares the render body so a frozen draw list cannot
observe a destroyed item or double-release its buffers.

The generic retained-batch command belongs to `tgfx2`, not tcplot. It receives
the effective scene transform, opacity, viewport and rectangular clip, then
executes through `RenderContext2`. The Canvas executor flushes ordinary
geometry around it and restores its state afterwards. Arbitrary geometric
clips are deliberately rejected with an error for retained batches; chart
plot-area clips are axis-aligned rectangles and stay on the scissor fast path.
Supporting arbitrary native-batch masks requires a separate stencil/mask
contract rather than silently broadening a clip to its bounds.

Line items retain an amortized-growth point VBO. Solid, dash, dot and
colormapped ribbons remain one draw per series; append uploads only the solid
line tail. Scatter uses one persistent instance stream and one instanced draw,
replacing the former per-point Canvas loop. `PlotEngine2D` now delegates to
the same `PlotLineSeriesGpu2D` and `PlotScatterSeriesGpu2D` implementations,
so the migration does not keep a second series renderer.

The Linux Vulkan performance fixture records a steady render of one 100k-point
line plus one 100k-point scatter at 1280×720 after warm-up, including texture
allocation and `wait_idle`. The 2026-07-30 Aurora run measured 0.324 ms/frame;
the automated regression tolerance is 250 ms/frame to remain portable to slow
CI/software devices. Scene snapshot construction is separately verified to
stay O(items), not O(points): 25 snapshots of the same 200k-point line produced
14 commands each in 19 µs total on that run.

## Typed language surface

Every chart part exposed to C# has a typed handle-only wrapper:

- common tree and presentation operations come from `GraphicItemRef2D`;
- concrete wrappers expose concrete properties and mutations;
- wrappers do not own native item bodies or extend scene lifetime;
- stale or wrong-type wrappers fail explicitly;
- native and managed-created items use the same adopt/deleter contract;
- storage and rendering infrastructure contain no switch over concrete item
  types.

Factories are owned by the registered concrete type, not by a closed
`TcVisualScene.create_*` enumeration. This direction is shared with the typed
Widget/GraphicItem binding normalization work.

The chart path creates existing native item bodies only. User-defined bodies
owned by Python or C# are useful future extensibility, but their language holds
and `GCHandle` ownership are a separate concern tracked by `#1107`; they do not
block retained chart composition.

## Layout and measurement

Chart layout is a managed composition concern, but measurement remains native
where native resources determine the answer. The managed composer may request:

- text bounds for a string, font and size;
- tick values and formatted labels for a numeric range;
- preferred extents of axis tick/label items;
- local bounds of any retained item.

The native value boundary is now represented by `fit_plot_range2d()`,
`make_plot_ticks2d()` and `measure_plot_text2d()`. Logical tick spacing and font
size are converted with `pixel_scale`; results own their values and strings.
Ticks must be recomputed after range, plot-area extent or pixel-scale changes.
Text metrics must be recomputed after text, font, logical size or pixel-scale
changes. The legacy `PlotEngine2D` consumes the same helpers so it remains a
useful parity reference during migration.

The managed side uses these results to set transforms, clips and sizes on the
scene tree. There is no ABI method such as `set_panel_margins` whose only
purpose is to alter hidden native layout. Convenience APIs may exist in the C#
composer, but they update visible chart parts and managed layout state.

## Rendering and interaction

Painting remains synchronous and native:

1. the host asks the scene to paint;
2. generic traversal invokes each item's native vtable;
3. plot series items append optimized native draw work;
4. the native backend executes the resulting draw list and native batches.

Managed code is not called from paint, tessellation or GPU submission.

Pointer events may be routed through the common visual-scene hit-test and
capture model. Managed application policy may respond after native routing,
then update compact plot state or item properties. Large-series picking and
nearest-point queries remain native operations exposed through typed items.

## Migration

The migration is intentionally allowed to break the transitional API during
active development. It must not preserve two permanent chart implementations.

1. Complete neutral GraphicItem factories and full typed C# wrappers for
   existing native items. **Implemented for visual-scene built-ins; tcplot
   wrappers follow in `#1100`.**
2. Extract optimized native series/grid render bodies from `PlotEngine2D` into
   plot-specific `GraphicItem2D` classes without regressing the persistent-VBO
   path. **Implemented.**
3. Expose native plot projection, tick and measurement utilities needed by a
   managed composer.
4. Implement a C# single-panel `Chart2D` composition over one
   `TcVisualScene`.
5. Add legends, annotations and multi-panel/shared-axis composition using the
   same parts.
6. Move WPF hosting to the composed scene path.
7. Remove native hidden chart layout and the layout/style RPC surface from
   `PlotView2D` and `PlotView2DMulti`.

A thin native convenience composer may remain only if it builds the same
public item model and exposes the resulting parts. It must not retain a second
renderer or inaccessible layout tree.

## Acceptance

The direction is complete when:

- a WPF application constructs a working chart from typed retained parts;
- C# can access, reorder, style, replace and remove the meaningful chart
  elements through stable handles;
- layout-specific customization does not require adding native forwarding
  methods;
- large line and scatter data remain native and use measured optimized GPU
  paths comparable to the current renderer;
- pan, zoom and resize update compact state rather than crossing projected
  data or draw commands through the ABI;
- annotations are ordinary participants in the same scene tree;
- single-panel and multi-panel reference charts pass visual parity scenarios;
- renderer execution performs no managed callbacks;
- the old monolithic hidden-layout implementation and its transitional
  setter surface are removed.

## Verification direction

- Linux `./build-sdk.sh` and `./run-tests.sh`;
- focused native item lifetime, projection, rendering and performance tests;
- C# handle, wrong-type, stale-wrapper and teardown tests;
- Windows D3D11 WPF single- and multi-panel visual/interaction smoke;
- before/after measurements for representative large line and scatter data;
- an installed-SDK C# example that replaces at least one standard chart part
  without changing native bindings.

## Tracking

Umbrella: `#1095 [tcplot/composition] Build C# retained chart composition`.

Implementation sequence:

- `#1096` retained plot projection contract;
- `#1097` retained native line/scatter series items;
- `#1098` retained native grid item;
- `#1099` native tick and measurement utilities;
- `#1100` typed retained plot item C# bindings;
- `#1101` managed single-panel `Chart2D` composer;
- `#1102` managed multi-panel charts and overlays;
- `#1103` WPF D3D11 retained-chart host;
- `#1104` removal of monolithic hidden chart layout;
- `#1105` final parity and performance gate.

Existing `#1025` supplies the polyglot GraphicItem factory/lifetime foundation
for `#1100`. Existing `#1032` is a later cross-family binding normalization
pass and does not block the functional retained chart path.
