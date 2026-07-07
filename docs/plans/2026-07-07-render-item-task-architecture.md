# Render Item And Task Architecture

Date: 2026-07-07
Kanboard: #203, #205, #206

## Status

Design note for the next render architecture migration. This is not yet the
live contract. The stable phase semantics remain documented in
`docs/render-phase-semantics.md`.

This note captures the intended boundary between drawable components, render
passes, and shared render submission code. It should guide the migration away
from the current mixed model before the exact C ABI and C++ convenience wrappers
are finalized.

Implementation progress:

- 2026-07-07: first additive ABI slice landed with `tc_render_item`,
  `tc_render_item_collect_context`, sink-based collection, C++ vector collector,
  and mesh item emission from `MeshRenderer` / `SkinnedMeshRenderer`. The old
  `GeometryDrawCall` path remains live while passes are migrated.
- 2026-07-07: `IdPass` now builds mesh draw tasks from RenderItems and uses the
  direct `Drawable` path only for non-mesh drawables that do not have a
  typed item encoder yet.
- 2026-07-07: direct `draw_tgfx2()` ownership has been removed from the live
  render path. `LineRenderer`, `WorldTextComponent`, and
  `FoliageLayerComponent` now submit typed `LINE_BATCH`, `TEXT_BATCH`, and
  `FOLIAGE_BATCH` RenderItems through registered encoders. `ColorPass`,
  `ShadowPass`, and `IdPass` no longer use C++ `Drawable` casts in their
  draw-time submit paths.
- Remaining live migration work: remove `GeometryDrawCall` discovery from
  converted passes, finish Python-facing RenderItem ergonomics/tests, and
  retire the legacy geometry-side-channel methods once all pass collection is
  RenderItem-first.

## Problem

Current rendering has several overlapping draw ownership models:

- `GeometryDrawCall` returns material-phase draw records, but it does not carry
  enough structured backend payload to be the single render protocol.
- `GeometryPassBase`, `DepthPass`, and `NormalPass` still lean on
  `GeometryDrawCall` / geometry-id discovery before submitting RenderItems.
- `resolve_mesh_geometry()`, `get_geometry_ids_for_phase()`,
  `upload_per_draw_uniforms_tgfx2()`, and related geometry-side-channel methods
  still expose transitional ways for passes to ask drawable implementations how
  to draw.
- Direct `draw_tgfx2()` and `RenderContext::prepare_tgfx2_material_resources`
  have been removed from the live code, but old design references may still
  exist in historical notes.
- The C drawable ABI currently returns `void*` for geometry draws, with C++
  drawables caching a `std::vector<GeometryDrawCall>` behind that pointer.

The result is unclear ownership: drawables sometimes publish data, sometimes
execute backend drawing, and sometimes receive pass-owned callbacks. Passes
sometimes own the draw policy and sometimes call back into drawable-specific
backend code.

## Target Shape

The desired flow is:

```text
Drawable emits RenderItems
Pass collects, filters, and orders work
Pass submits RenderTasks one at a time
termin-render submission layer encodes each task
Encoder handles the concrete item payload kind
tgfx2/backend executes low-level commands
```

This keeps pass semantics and ordering in the pass, while moving shared
material/resource/backend submit mechanics out of individual pass draw loops.

## Responsibilities

### Drawable / Renderer Component

A drawable owns representation data for an entity or component. It answers the
pass-owned collection request by emitting render items.

Responsibilities:

- declare supported render representation labels through phase membership;
- emit items for the requested `phase_mark`;
- provide stable handles or payload references for mesh, submesh, batch,
  material, transform, bounds, and component-owned per-draw data;
- keep representation decisions local to the component, such as whether the
  `shadow` representation uses the same geometry as `opaque`.

Non-responsibilities:

- opening or closing render passes;
- deciding pass targets, clear/load/store policy, depth policy, or viewport;
- selecting shader ABI from phase names;
- binding pass resources;
- issuing public backend draw calls as the normal model.

### RenderItem

`RenderItem` is the normalized record emitted by a drawable. It describes a
possible render representation, not a final pass decision.

Important properties:

- item kind describes payload ABI, not the concrete component class;
- heavy data travels through handles, stable references, or explicit payload
  views;
- the item is safe to copy into pass-owned storage;
- malformed items are logged by the sink/collector instead of silently ignored.

Expected initial item kinds:

```text
Mesh
LineBatch
TextBatch
FoliageBatch
```

The exact list can evolve, but the model must avoid reintroducing
drawable-owned `draw_tgfx2()` paths for non-mesh renderers.

### RenderItemCollectContext

The collection request should be a single context object. `phase_mark` belongs
inside this context so there is only one source of truth.

The context may contain data needed to choose a representation or fill item
metadata:

```text
phase_mark
pass/material ABI contract view, if needed by the drawable
layer/category masks
scene and camera read-only handles
view/projection/camera frame data, if needed by item producers
debug pass name
```

It must not contain backend binding callbacks, mutable backend state, or a
general-purpose service bag.

### RenderItemSink

Collection should be push-based. The sink belongs to the caller, usually the
pass or a pass-owned helper.

Responsibilities:

- receive emitted items;
- validate basic shape and lifetime-sensitive fields;
- copy valid items into pass-owned storage;
- attach request metadata when appropriate;
- log malformed items with component, phase, and pass context;
- optionally stop collection early if a future caller needs that behavior.

This replaces the current `void*` return path that hides a C++ vector behind the
C drawable ABI.

### Pass

A pass owns the meaning of a render pass and the order of work inside it.

Responsibilities:

- own pass boundaries under the current framegraph/backend model;
- choose the collection `phase_mark`;
- define the pass shader/material contract;
- collect render items from scene drawables;
- apply pass-specific entity/material/category filters;
- build pass-owned `RenderTask` records;
- sort or otherwise order tasks for the pass;
- submit tasks one by one to the shared render submission layer;
- own pass-level debug/capture scope and diagnostics.

Passes should not need concrete backend encoding details for every item kind,
but they remain the only layer that sees all work in a pass together and can
therefore define correct ordering.

### RenderTask

`RenderTask` is pass-owned work selected from one or more render items.

`RenderItem` means "this drawable can be represented this way." `RenderTask`
means "this pass decided to submit this representation with these pass-local
parameters."

Examples of pass-local task data:

- `IdPass`: pick id, override color, id draw payload;
- `ColorPass`: selected material phase, final material shader, lighting/shadow
  resource policy;
- `ShadowPass`: light-space draw data and shadow-specific resource policy;
- `DepthPass` / `NormalPass`: pass-specific draw uniform payloads and shader
  contract choices.

The shared submission layer must not build the pass task list by itself.

### Pass Draw Context

The pass should pass a small, borrowed context alongside each task. This context
describes the active pass state needed to encode one task, but it is not a
second pass lifecycle API.

It should contain semantic/read-only pass data such as:

```text
pass name
phase mark
shader/material pass contract view
view/projection/camera data
viewport dimensions
pass-global resource views
```

Mutable backend command state, encoder registries, and runtime services should
not be hidden inside this semantic context. They belong to the submission
service or runtime object passed separately.

### Shared Submission Layer

The shared submission layer lives in `termin-render`. It is a service for
encoding one already-selected task into backend commands.

Responsibilities:

- accept runtime submission services, a pass draw context, and one task;
- find an encoder for the task item kind;
- validate task compatibility with the pass contract;
- perform common material/resource binding;
- upload pass/draw uniforms through explicit data views;
- call the item-kind encoder;
- log unsupported or mismatched cases clearly.

Non-responsibilities:

- collecting all work in a pass;
- deciding pass membership;
- sorting or batching as a semantic pass decision;
- opening/closing logical pass boundaries;
- acting as a framegraph scheduler.

### Encoder

An encoder handles one payload ABI or a narrow family of payload ABIs.

Examples:

```text
MeshItemEncoder
LineBatchEncoder
TextBatchEncoder
FoliageBatchEncoder
```

Responsibilities:

- interpret the task payload for its item kind;
- bind item-kind-specific buffers, streams, and uniforms;
- adapt the item payload to the pass contract;
- emit the low-level tgfx2/backend commands for that task.

Non-responsibilities:

- deciding whether the item belongs in the pass;
- deciding the order of the pass;
- reaching back into drawable component classes for missing data.

### Encoder Registry

The encoder registry should live with the render runtime or render engine
context, not as a global singleton. Registration should be explicit to avoid
adding more static-registration/hot-reload coupling.

Ownership rule:

```text
The package that owns an item payload ABI registers the encoder for it.
```

Initial placement:

```text
termin-render:
  mesh encoder
  common material/resource submission helpers

termin-components-render:
  line, text, foliage encoders when those item kinds are introduced

other component packages:
  package-owned item kinds and encoders
```

`termin-render-passes` should use the registry through the submission API, but
it should not own item-kind encoders.

## C-First Data Boundary

The new protocol should be designed as C data first, with C++ wrappers layered
on top.

Avoid in ABI-facing structs:

```text
std::vector
std::string
std::optional
std::span
C++ references
backend service callbacks hidden in general contexts
```

Prefer:

```text
ptr + count arrays
const char* + length strings, or interned ids
explicit flags for optional fields
plain handles for resources
caller-owned memory with documented lifetime
sink callbacks that copy emitted items into caller-owned storage
```

Existing C++ types such as `MaterialPipelinePassContract` and
`MaterialPipelineResourceContext` can remain useful internal conveniences, but
the drawable/pass/submit boundary should expose C-compatible views. This is
especially important for Python and non-C++ drawables, which must not depend on
C++ `Drawable` vtable bypasses.

## Material And Resource Binding Direction

`RenderContext::prepare_tgfx2_material_resources` should be removed from the
drawable-facing context.

Target ownership:

```text
Pass:
  prepares pass-global resource views and pass-local task payloads

Shared submit layer:
  binds common material/pass/draw resources from explicit views

Encoder:
  binds item-kind-specific payload resources

Drawable:
  only provides representation data and stable payload references
```

This keeps pass-owned binding services out of drawable collection and prevents
custom drawables from becoming backend submit owners.

## Migration Outline

1. Define C-first render item, collection context, and sink ABI beside the
   existing drawable protocol.
2. Add C++ wrappers for collecting into pass-owned vectors, implemented on top
   of the sink ABI.
3. Teach `MeshRenderer` and `SkinnedMeshRenderer` to emit mesh items while
   keeping the old `GeometryDrawCall` path temporarily.
4. Add a shared mesh task submission path in `termin-render`.
5. Convert `GeometryPassBase` and the core geometry passes to collect items,
   build tasks, order tasks, and submit them one at a time.
6. Remove draw-time C++ `Drawable` casts from converted pass paths.
7. Convert one non-mesh direct path, preferably `LineRenderer` or
   `WorldTextComponent`, to a typed item and encoder.
8. Remove `RenderContext::prepare_tgfx2_material_resources` once direct paths no
   longer need pass-owned callbacks. Done for the live C++ render path.
9. Deprecate and then remove `resolve_mesh_geometry()`,
   `get_geometry_ids_for_phase()`, and `upload_per_draw_uniforms_tgfx2()` as
   public draw ownership APIs. `supports_direct_tgfx2_draw()` and
   `draw_tgfx2()` have already been removed from the live C++ API.
10. Update `docs/render-phase-semantics.md` after the live contract changes.

## Diagnostics And Tests

The migration should add logs and tests before old direct draw paths disappear.

Required diagnostics:

- no encoder registered for an item kind;
- item kind incompatible with pass contract;
- malformed item emitted by C++ or Python drawable;
- invalid payload handle or expired payload reference;
- missing material phase where a pass/task requires one;
- empty `phase_mark` at a geometry collection boundary;
- mesh-backed drawable reaching a non-RenderItem path after a pass has migrated.

Required tests:

- C++ `MeshRenderer` emits mesh items and renders through Color/Id/Shadow-style
  pass tasks;
- Python/non-C++ drawable emits render items without a C++ `Drawable` cast;
- at least one typed non-mesh item path renders without `draw_tgfx2()`;
- pass ordering remains pass-owned;
- material phase shader override still works through the task submission path;
- unsupported item/contract combinations log useful errors and do not silently
  fall back.

## Open Questions

- Exact C names and ownership rules for `tc_render_item`,
  `tc_render_item_collect_context`, and `tc_render_task`.
- Whether `RenderTask` should be a single C union or a small common header plus
  typed payload views.
- How pass-global and draw-local material resource views should be split while
  making tgfx2/material pipeline more C-like.
- Whether phase labels should remain strings at the ABI boundary or move to
  interned ids with debug string lookup.
- How encoder registration participates in module hot-reload without relying on
  static initialization.
- Which non-mesh direct path should be migrated first as the proof that the new
  model actually replaces `draw_tgfx2()`.

## Invariants

```text
Drawable owns representation data.
RenderItem is emitted data, not an executor.
Pass owns pass semantics, membership, and order.
RenderTask is pass-owned selected work.
Shared termin-render submission code owns common submit mechanics.
Encoder owns item-kind backend encoding.
tgfx2/backend owns only low-level commands and resources.
```
