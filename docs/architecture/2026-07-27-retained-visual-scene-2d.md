# Retained Visual Scene 2D

## Status

Accepted direction; implementation is pending. This note is the architecture
sketch for the reusable retained 2D visual and interaction layer. The direction
is intentionally separate from world-space 2D game support.

The working public names in this note are `VisualScene2D`, `GraphicItem` and
`GraphicItemHandle`. They belong to a separate top-level
`termin-visual-scene` module and SDK package, with the canonical CMake target
`termin_visual_scene::termin_visual_scene`. The module depends on
`termin-graphics`; `termin-graphics` does not contain or own graphic-item
storage. The terminology distinguishes this retained presentation module from
computational geometry, the 3D engine scene and the 2D game runtime.

## Problem

Termin has two useful but deliberately different retained systems:

- `tc_ui_document` owns a widget tree with layout, focus, keyboard input,
  theme state and overlays;
- `tcplot` owns plot data and renders axes and large series directly through
  `termin-graphics`.

Interactive plot annotations do not fit either system by themselves. Markers,
callouts, handles and selection regions need persistent identity, arbitrary 2D
placement, paths, z-order, clipping, hit testing and pointer capture. Some
markers also expose small actions or, less commonly, embed full controls.

Putting this state directly into `PlotEngine2D` would make the already dense
plot render/input path harder to extend. Treating every annotation as a widget
would force plot-space objects into widget layout and would make standalone
`tcplot` depend on `termin-gui-native`.

`termin-gui-native` already contains `GraphicsScene`, `GraphicsItem` and
`SceneView`. They prove the usefulness of a retained tool scene, but the current
scene is GUI-bound:

- paint callbacks consume `tc_ui_paint_context`;
- embedded widgets are part of the core item type;
- item identity and topology use `shared_ptr`/`weak_ptr`;
- geometry is primarily `position + size`;
- selection and drag policy are built into the general view.

Adding a second unrelated scene implementation for plot annotations would
leave two competing retained 2D systems. The common layer should be extracted
and both GUI tools and plots should consume it.

## Decision

Introduce a reusable retained 2D visual scene module between domain models and
backend-neutral rendering:

```text
tcplot
    PlotAnnotationLayer
    data/series anchors, snapping, plot clipping and annotation semantics
                         |
                         v
termin-visual-scene
    VisualScene2D
    persistent visual nodes, topology, transforms, hit testing,
    pointer state and backend-neutral render preparation
                         |
                         v
termin-graphics
    Canvas2DRenderer, text renderers, specialized GPU batches and resources
```

`termin-gui-native` consumes the same scene through a `SceneView` adapter:

```text
tc_ui_document
    widget layout, focus, keyboard/text input, theme
        |
        +-- SceneView widget
                |
                +-- VisualScene2D
                        |
                        +-- optional GUI-owned widget portal adapter
```

The visual scene is not a widget implementation, and widgets are not built from
graphic items. Both systems may share lower-level handle-storage utilities,
math types, draw commands, text measurement and pointer event value types, but
they keep separate canonical trees and lifetime domains.

Plot annotations remain owned semantically by `tcplot`. A reusable visual scene
owns only their projected visual representation and interaction targets.

## One Rendering Vocabulary, Separate Retained Module

`VisualScene2D` is a separate module, but it is not a parallel rendering
engine. The intended dependency stack is:

```text
termin-graphics
    Canvas2DRenderer, text, images, paths, GPU batches
            ↑
            |
termin-visual-scene
    VisualScene2D, GraphicItemHandle, retained topology, hit preparation

termin-gui-native
    widget semantics and a SceneView adapter

tcplot
    plot semantics and annotation projection

termin-engine/components
    world/entity-space 2D game semantics
```

The module boundary keeps persistent item pools, topology, serialization and
interaction state out of the low-level renderer/resource package. At the same
time, domain systems and `termin-visual-scene` must not grow private copies of
the shared rendering infrastructure. In particular there is one canonical
implementation of:

- `Transform2D` and visual bounds math;
- path verbs, fill/stroke representation and tessellation;
- backend-neutral 2D draw-command vocabulary;
- text/image visual payloads and clipping execution;
- retained visual nodes in `termin-visual-scene`, used by GUI tool scenes and
  plot annotations.

The widget tree, plot annotation pool and world-space entity/component model
remain separate because they express different domain state. They consume the
same graphics stack rather than becoming additional graphics engines.

## Layer Responsibilities

### `termin-graphics`

- backend-neutral drawing and resource handles;
- path tessellation and stroke/fill execution;
- text and image rendering;
- specialized batches for large polylines and plot series;
- no graphic-item pools, retained visual topology, hit state, plot annotation,
  widget or world/entity semantics.

### `termin-visual-scene`

- one lifetime domain per scene;
- generation-checked item handles;
- explicit item creation, destruction and reparenting;
- visual topology, affine transforms, ordering and clipping;
- primitive payloads and custom batch references;
- local/world bounds and geometric hit testing;
- hover, press and pointer capture expressed as handles;
- immutable render/hit snapshots or internally synchronized traversal;
- inspection and handle-free serialization records.

The scene does not own a render device, window, frame pass, plot data or UI
document.

### `tcplot`

- annotation identities and application-facing APIs;
- anchors such as `Data2D`, `SeriesPointRef`, `AxesFraction` and viewport
  positions;
- projection against the current plot frame;
- clipping policy and layer selection;
- snapping and nearest-series queries;
- semantic actions and drag constraints;
- synchronization between annotation state and visual items.

### `termin-gui-native`

- a widget host for a visual scene;
- forwarding of pointer events and invalidation;
- optional focus and keyboard integration;
- optional portals which position canonical `tc_ui_document` widgets;
- no duplicate ownership of embedded widgets.

## Lifetime and Handles

Every `VisualScene2D` owns an independent index/generation pool:

```c
typedef struct tc_graphic_item_handle {
    uint32_t index;
    uint32_t generation;
} tc_graphic_item_handle;
```

The final C prefix follows the `termin-visual-scene` public API convention. The
handle remains type-distinct from `tc_widget_handle`, entity handles and plot
annotation handles.

A graphic item handle is meaningful only when resolved by its owning scene.
There is no process-global item pool and no cross-scene reparent operation.

The scene owns every adopted item. Runtime references use handles:

- parent and ordered children;
- selection sets;
- hovered, pressed and captured targets;
- controller and annotation projections;
- language bindings and inspector references.

Stable serialization identity is separate from the runtime handle. Slot index
and generation are never persisted.

The common storage mechanism may be factored into a reusable typed generation
pool, but public APIs must not expose a universal untyped engine handle.

### Item ownership

Standard visual primitives are scene-owned records with tagged payloads.
Extensible custom items may embed a language-neutral item body and vtable and
must be adopted with exactly one creator-supplied deleter, following the common
multilanguage lifetime model.

There is no reference-counted ownership protocol. A language wrapper retains
the scene invalidation state plus a handle; it does not keep an item alive after
explicit destruction.

Failed adoption is transactional: either the item becomes reachable through a
valid scene handle or the supplied deleter is called during rollback.

### Explicit topology operations

Scene ownership and visual topology are separate concepts. Parenting does not
silently define heap ownership.

The core operations are explicit:

```text
create/adopt item
attach child
detach item
reparent item
destroy leaf
destroy subtree
clear scene
```

Destroying a non-leaf through the leaf operation is an error. Recursive
destruction requires the explicitly named subtree operation.

Before an item slot is recycled, the scene:

1. removes it from topology and ordering structures;
2. clears selection, hover, press and capture references to it;
3. invalidates prepared snapshots which reference its revision;
4. invokes lifecycle cleanup and exactly one deleter when applicable;
5. increments the slot generation, skipping the invalid zero generation.

## Item Model

A standard item record contains only state shared by all visual nodes:

```text
identity        runtime handle, optional stable id, registered type id
topology        parent, ordered children, local z/order
presentation    visible, opacity, local affine transform
clipping        none, local clip geometry or inherited clip
interaction     pointer policy, enabled state, semantic action id
diagnostics     name, revision, dirty flags
payload         tagged primitive or adopted custom body
```

Initial payload kinds:

- `Group`;
- `Rect` and `RoundedRect`;
- `Ellipse`;
- `Path`;
- `Polyline`;
- `Text`;
- `Image`;
- `HitRegion`;
- `CustomBatch`.

`CustomBatch` is required so a scene can place specialized retained GPU
geometry without decomposing it into one item per vertex or sample.

Widget portals are not a core payload kind because that would introduce a
dependency on `termin-gui-native`. A GUI adapter may register a host-specific
portal payload or maintain a side table from `GraphicItemHandle` to
`WidgetHandle`.

### Paths

The canonical path contract is owned by `termin-graphics`.
`termin-visual-scene` stores or copies that public path value in a `Path`
payload and uses the same type for bounds, hit preparation and rendering. If
the contract lacks a required verb or stroke property, extend it in
`termin-graphics`; do not introduce a scene-private path representation.

The shared path contract should define, rather than infer from a backend:

- `move_to`, `line_to`, quadratic and cubic curves, and `close`;
- non-zero and even-odd fill rules;
- stroke width, join, cap and dash policy;
- local bounds and hit-test tolerance;
- ownership of copied path data;
- deterministic tessellation failure reporting.

Large plot series remain specialized batches. They are not represented as one
path item per series sample.

## Coordinates and Transforms

The scene owns ordinary local-to-parent affine 2D transforms. A view supplies
the scene-to-viewport transform and clip rectangle.

Plot coordinate systems do not become generic scene coordinate systems.
`PlotAnnotationLayer` resolves a domain anchor through an immutable
`PlotFrame2D`:

```text
Data2D / SeriesPointRef / AxesFraction
                |
                v
           PlotFrame2D
                |
                v
       viewport-space item anchor
```

This supports the common mixed-space marker:

- its anchor follows a data point;
- its bubble and action icons keep a stable pixel size;
- its leader line joins the projected anchor to the pixel-sized bubble.

`PlotFrame2D` contains at least the viewport rectangle, plot-area rectangle,
data ranges, axis transforms, clipping rectangle and pixel scale. It is a value
snapshot, not a back-reference to a mutable `PlotEngine2D`.

## Rendering

Scene traversal prepares backend-neutral drawing commands or a render snapshot.
It does not call a backend directly and does not retain a render context.

The plot render pipeline exposes explicit phases:

```text
plot background and grid
underlay annotations
large series and scatter batches
overlay annotations
unclipped callouts and plot chrome
```

Each annotation selects a phase and clipping policy explicitly. Draw order is
stable for equal z values and derives from canonical child/root order.

Dirty revisions distinguish:

- topology changes;
- transform/bounds changes;
- visual payload changes;
- interaction-only state changes.

Spatial indexing, subtree command caching and partial redraw are later
optimizations. The initial implementation may use linear traversal, but its API
must not expose linear storage order as identity.

## Interaction

Hit testing traverses the effective visual order from front to back and returns
the deepest eligible target. A node may use its visual geometry, an explicit
`HitRegion`, or a custom prepared hit shape.

The scene interaction state uses handles, never borrowed item pointers:

```text
hovered item
pressed item per pointer/button
captured item per pointer
selected items when a controller enables selection
```

Selection, dragging and pan/zoom are controllers or host policies, not
unconditional behavior baked into every scene. Node-graph tools and plots can
therefore share storage and hit testing while using different gestures.

Small marker controls use semantic actions:

```text
visual icon + HitRegion(action_id)
    -> ActionEvent(target, action_id)
```

They are not full widgets. Full widget portals are reserved for controls which
need widget layout, focus, Tab traversal, keyboard/text input, theme semantics
or accessibility.

Input routing for a plot is ordered:

1. captured annotation interaction;
2. front-to-back annotation hit testing;
3. plot pan/zoom if no annotation consumed the event.

## Widget Integration

`SceneView` remains a regular widget. It participates in widget layout, receives
a computed rectangle and forwards relevant events to a visual scene.

An embedded widget remains canonically owned and parented by
`tc_ui_document`. A portal stores only a foreign `WidgetHandle` association and
positions that widget from the corresponding graphic item's projected bounds.

Destroying a portal does not implicitly destroy the widget. Destroying a widget
invalidates or detaches its portal association. Neither object belongs to two
owning trees.

Widgets continue to paint directly into the UI draw list. Building all widgets
from graphic items would create duplicate canonical bounds, visibility,
clipping, hit-test and lifetime state and is explicitly out of scope.

## Plot Annotation Model

`tcplot` owns a separate annotation handle pool. Annotation handles and graphic
item handles are not interchangeable:

```text
PlotAnnotationHandle
    stable plot-domain object and public API identity

GraphicItemHandle
    projected visual node identity inside one VisualScene2D
```

One annotation may project to several graphic items. For example, a callout may
own a leader path, bubble background, text item, close action and drag region.
The annotation controller maintains those handles and recreates or updates
them when its representation changes.

The initial vertical slice should cover:

- a data-anchored marker with pixel-sized geometry;
- a leader and callout text;
- hover state;
- captured dragging with data-space update;
- at least one semantic marker action;
- plot clipping and unclipped callout behavior;
- headless hit/render snapshot tests.

Legends, arbitrary rich marker layout, 3D annotations and full widget portals
are follow-up capabilities built on the same boundary.

## C ABI, C++ and Language Bindings

The storage, lifecycle and event contract should have a language-neutral C
core. C++ provides typed RAII facades for scene access without changing scene
ownership. Python and C# wrappers carry scene invalidation state plus
generation handles.

Bindings must not expose:

- owning raw pointers to items;
- `shared_ptr` as the lifetime protocol;
- callbacks that silently retain the scene;
- slot indices without their generation;
- backend render contexts in persistent item state.

Inspection snapshots and serialization use detached values and record indices.
Transient hover, press, capture and dirty state are not serialized.

## Concurrency

The visual scene must not impose creator-, UI- or render-thread affinity.
Public operations are callable from arbitrary threads in accordance with the
engine-wide no-owner-thread rule.

The implementation owns synchronization. Rendering consumes an immutable
prepared snapshot or an equivalently safe internally synchronized view.
Mutation publishes a new revision atomically. Item destruction coordinates
with in-flight preparation or interaction leases before invoking the item
deleter.

Signals and custom lifecycle callbacks must not run while the scene storage
mutex is held. Errors describe invalid handles, topology or resource failures;
they must not report a wrong-thread condition.

## Migration from `termin-gui-native::GraphicsScene`

The current GUI-native scene is a prototype and migration source, not a second
permanent scene API.

Migration proceeds as follows:

1. add the independent `termin-visual-scene` module and its handle-based
   `VisualScene2D` core, depending on `termin-graphics`;
2. finish primitive payloads, render snapshots, hit testing and pointer
   controllers, then validate the public core with a standalone
   `termin-visual-scene/examples` scene containing draggable primitive items;
3. implement GUI-native `SceneView` as an adapter over the shared scene and
   port node-graph consumers and embedded widget positioning;
4. validate widget/scene composition with a focused
   `termin-gui-native/examples` application which renders and interacts with
   ordinary widgets and `GraphicItem` values in one document;
5. only after both examples pass, expose `PlotFrame2D`, add retained tcplot
   annotations and implement the interactive marker/callout vertical slice;
6. migrate language bindings to scene-plus-handle wrappers;
7. remove the old `shared_ptr<GraphicsItem>` storage and callback API after all
   repository consumers move.

Active development does not require a long-lived compatibility fallback. A
short build-breaking migration is preferable to maintaining two canonical
scene trees.

## Non-goals

- replacing `tc_ui_document` or implementing widgets as graphic items;
- implementing another renderer, tessellator, path vocabulary or GPU resource
  layer inside `termin-visual-scene`;
- world-space 2D games, sprite components, tile maps or 2D physics;
- representing every plot sample as a scene item;
- owning windows, render devices, frame passes or application state;
- making plot-domain coordinate systems part of the generic scene;
- making full widget layout a requirement for lightweight marker actions;
- introducing thread affinity to simplify scene mutation.

## Acceptance of the Architecture Direction

The direction is implemented when:

- one generation-handle `termin-visual-scene` module is shared by GUI tools and
  plot annotations;
- a standalone primitive-scene example demonstrates public item creation,
  rendering, hit testing and captured dragging without GUI or tcplot
  dependencies;
- a GUI-native example demonstrates widgets and graphic items rendering and
  receiving input together before tcplot integration begins;
- the old GUI-native `shared_ptr<GraphicsItem>` storage is removed;
- `tcplot` exposes plot-frame snapshots and retained semantic annotations
  without depending on `termin-gui-native`;
- an interactive data-anchored marker works through the shared scene;
- headless tests cover handle invalidation, topology, transforms, rendering,
  hit testing, capture and annotation projection;
- documentation and bindings expose one canonical lifetime model.
