# Retained Visual Scene 2D

## Status

Accepted direction; the shared visual-scene foundation, GUI adapters and both
example gates are implemented. Plot integration is underway: `tcplot` now
publishes detached `PlotFrame2D` projection snapshots and has explicit render
phase boundaries. Retained semantic plot annotations are the next layer. This
direction is intentionally separate from world-space 2D game support.

The shared-foundation refinement is also accepted: no new generic "2D base"
module is introduced. Exact 2D value math belongs to `termin-base`;
backend-neutral path, paint and draw-command values belong to
`termin-graphics`; retained identity and interaction belong to
`termin-visual-scene`.

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

Before the shared-scene migration, `termin-gui-native` contained
`GraphicsScene`, `GraphicsItem` and `SceneView`. They proved the usefulness of
a retained tool scene, but that prototype was GUI-bound:

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
    Path2f, paint values, DrawList2D, Canvas2DRenderer,
    text renderers, specialized GPU batches and resources
                         |
                         v
termin-base
    Affine2f and canonical float 2D geometry values
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
termin-visual-scene
    VisualScene2D, GraphicItemHandle, retained topology, hit preparation
            |
            v
termin-graphics
    Path2f, paint values, DrawList2D, Canvas2DRenderer,
    text, images and specialized GPU batches
            |
            v
termin-base
    Affine2f, Vec2f, Size2f, Rect2f and Bounds2f

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

- exact `Affine2f` composition and visual bounds math in `termin-base`;
- `Path2f`, fill/stroke representation and tessellation in `termin-graphics`;
- backend-neutral `DrawList2D` / `DrawCommand2D` vocabulary in
  `termin-graphics`;
- runtime text/image draw commands and clipping execution in
  `termin-graphics`;
- retained visual nodes in `termin-visual-scene`, used by GUI tool scenes and
  plot annotations.

The widget tree, plot annotation pool and world-space entity/component model
remain separate because they express different domain state. They consume the
same graphics stack rather than becoming additional graphics engines.

## Shared 2D Foundation

The common foundation is a set of contracts in existing lower-level modules,
not another retained scene or product package.

### Exact affine math in `termin-base`

`Affine2f` is the canonical screen/tool-space composition value. Its public C
layout contains six floats and uses one documented column-vector convention:

```text
x' = m00 * x + m01 * y + tx
y' = m10 * x + m11 * y + ty
```

The contract includes identity, translation, rotation, scale, shear and TRS
constructors; exact composition; point/vector transforms; determinant; finite
validation; and an explicitly fallible inverse. A singular transform is never
silently replaced by identity.

`Vec2f`, `Size2f`, `Rect2f` and `Bounds2f` are the canonical float geometry
values used by the C and C++ public surfaces. Existing definitions should be
reused or migrated rather than copied into GUI, Canvas or visual-scene APIs.
`Rect2f` remains local origin/size geometry. Transforming it with an arbitrary
affine value may produce a parallelogram; `Bounds2f` is the axis-aligned box
computed from all transformed corners.

`Pose2` remains the rigid angle-plus-translation value. It can construct an
`Affine2f`, but it is not the scale/shear hierarchy composition type. A general
`Mat33f` is likewise not the public affine contract: it stores redundant
projective coefficients and cannot substitute a fallible affine inverse with
an identity fallback.

The visual scene initially uses float affine values because its geometry,
Canvas execution and GUI coordinates are float. Plot-domain values and ranges
may remain double, and nonlinear plot projection remains a `PlotFrame2D`
responsibility rather than being forced into `Affine2f`.

The separate `GeneralPose3` versus `Affine3d` decision follows the same
honesty principle but is not a prerequisite for this 2D contract.

### Paths, paint and draw commands in `termin-graphics`

`Path2f` is an owned, backend-neutral verb/point value. Canonical paint values
include color, fill rule and stroke width/join/cap/dash policy. Bounds,
flattening/tolerance and fill/stroke geometric preparation are shared by
rendering and hit preparation so those consumers cannot disagree about path
semantics.

`DrawList2D` is a build-then-freeze backend-neutral command value. It uses the
canonical geometry, `Affine2f`, path and paint contracts and covers transforms,
opacity, clips, standard primitives, text, images and custom batches.
`Canvas2DRenderer` executes this vocabulary. Immediate convenience calls may
remain only as thin adapters over the same commands.

A canonical clip is transformed geometry, not a device scissor rectangle.
Execution may use a scissor for an axis-aligned effective clip, but a rotated or
sheared clip must retain its geometry.

Persistent scene text/image payloads and runtime draw commands have different
lifetime contracts. The scene stores serializable stable resource references.
Render preparation resolves them through an explicit host-supplied resolver;
the resulting draw commands carry runtime font/texture handles. Persistent
items never retain a raw `FontAtlas*`, render context or owning GPU resource.
This lowering boundary is not a second visual vocabulary.

## Layer Responsibilities

### `termin-base`

- ABI-safe float 2D geometry values and exact `Affine2f` algebra;
- no drawing, resource, retained-scene, GUI or plot dependencies;
- explicit failure for singular affine inverse.

### `termin-graphics`

- backend-neutral `Path2f`, paint, `DrawList2D` and resource-handle values;
- path geometry preparation, tessellation and stroke/fill execution;
- text and image rendering;
- `Canvas2DRenderer` execution of the canonical draw-command vocabulary;
- specialized batches for large polylines and plot series;
- no graphic-item pools, retained visual topology, hit state, plot annotation,
  widget or world/entity semantics.

### `termin-visual-scene`

- one lifetime domain per scene;
- generation-checked item handles;
- explicit item creation, destruction and reparenting;
- visual topology, exact local/world `Affine2f`, ordering and geometric
  clipping;
- primitive payloads and custom batch references;
- local/world bounds and geometric hit testing;
- hover, press and pointer capture expressed as handles;
- immutable render/hit snapshots lowered to canonical `DrawList2D` values;
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
presentation    visible, opacity, local Affine2f
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

The canonical `Path2f` contract is owned by `termin-graphics`.
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

Text and image payloads store serializable stable resource references. They do
not retain a `FontAtlas*`, texture owner or render context. Snapshot preparation
resolves these references to the runtime handles carried by `DrawList2D`.

## Coordinates and Transforms

The scene owns local-to-parent `Affine2f` values and composes exact world
`Affine2f` values. It does not decompose hierarchy results into position,
angle and component scale, so rotated non-uniform scale and shear remain
representable. A view supplies the scene-to-viewport `Affine2f` and clip
geometry.

Inverse-dependent operations are explicit about singular transforms. A node
whose effective transform cannot be inverted is not hittable; the invalid
state is diagnosed at mutation or preparation boundaries instead of replacing
the inverse with identity or emitting one error per pointer event.

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

The implemented C++ snapshot is returned by `PlotEngine2D::plot_frame()`.
Projection and inverse projection operate only on the captured values, so a
frame remains valid after later pan, zoom, resize or shared-X synchronization.

## Rendering

Scene traversal prepares an immutable revisioned snapshot and lowers its
standard payloads to a frozen `DrawList2D`. It does not call a backend directly
and does not retain a render context. A host-supplied resolver converts stable
text/image resource references to runtime handles before the snapshot is
published; a resolution or tessellation failure is logged and cannot publish a
partial list.

Effective clips remain transformed geometry in the snapshot and draw list.
`Canvas2DRenderer` may execute an axis-aligned case with a device scissor, but
rotation or shear must not be discarded to obtain one.

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

The C surface consumes the canonical ABI-safe float geometry and
`tc_affine2f` values from `termin-base`; it does not substitute
`tc_ui_point`/`tc_ui_rect` or introduce module-private layout-compatible
copies.

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

That GUI-native scene was a prototype and migration source, not a second
permanent scene API.

As of the `SceneView` migration, the GUI-facing `GraphicsScene` name denotes
only a metadata/invalidation adapter which owns one `VisualScene2D`.
`GraphicItemRef` is a non-owning scene-plus-generation-handle value; the old
`shared_ptr<GraphicsItem>` tree and paint/hit callback API no longer exist.

The readiness sequence through GUI composition is now implemented:

1. add exact ABI-safe `Affine2f` and canonical float 2D geometry values to
   `termin-base`;
2. add canonical `Path2f` and paint values to `termin-graphics`;
3. add canonical `DrawList2D` and make `Canvas2DRenderer` its executor;
4. in parallel with the foundation branch, add the independent
   `termin-visual-scene` module and its handle-based `VisualScene2D` storage
   core, depending on `termin-graphics`;
5. join those branches in retained item payloads, exact affine hierarchy
   composition, render snapshots, hit testing and pointer controllers, then
   validate the public core with a standalone
   `termin-visual-scene/examples` scene containing draggable primitive items;
6. implement GUI-native `SceneView` as an adapter over the shared scene and
   port node-graph consumers and embedded widget positioning;
7. validate widget/scene composition with the focused
   `termin-gui-native/examples` application which renders and interacts with
   ordinary widgets and `GraphicItemRef` values in one document, including the
   separate document-owned widget portal;
8. only after both examples pass, expose `PlotFrame2D`, add retained tcplot
   annotations and implement the interactive marker/callout vertical slice;
9. language bindings use scene-plus-handle wrappers and the old
   `shared_ptr<GraphicsItem>` storage and callback API has been removed after
   repository consumers moved.

Steps 1–7 and 9 are complete. The `PlotFrame2D` and render-phase portion of
step 8 is complete; retained annotation projection and the marker/callout
vertical slice remain. The two example gates no longer block this work.

Active development does not require a long-lived compatibility fallback. A
short build-breaking migration is preferable to maintaining two canonical
scene trees.

## Non-goals

- introducing a new generic "2D base" product/module instead of extending
  `termin-base` and `termin-graphics`;
- using position/angle/component-scale decomposition as the world transform
  algebra;
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

- one ABI-safe exact `Affine2f` contract is shared across the float 2D stack,
  including explicit singular-inverse behavior;
- one canonical `Path2f`/paint and `DrawList2D` vocabulary is consumed by
  `Canvas2DRenderer` and `termin-visual-scene`;
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
- headless tests cover handle invalidation, topology, affine composition,
  singular transforms, transformed clips, rendering, hit testing, capture and
  annotation projection;
- documentation and bindings expose one canonical lifetime model.
