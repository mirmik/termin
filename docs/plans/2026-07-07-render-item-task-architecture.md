# Render Item And Task Architecture

Date: 2026-07-07
Kanboard: #203, #205, #206, #207

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
  and mesh item emission from `MeshRenderer` / `SkinnedMeshRenderer`.
- 2026-07-07: `IdPass` now builds mesh draw tasks from RenderItems and uses the
  direct `Drawable` path only for non-mesh drawables that do not have a
  typed item encoder yet.
- 2026-07-07: direct `draw_tgfx2()` ownership has been removed from the live
  render path. `LineRenderer`, `WorldTextComponent`, and
  `FoliageLayerComponent` now submit typed `LINE_BATCH`, `TEXT_BATCH`, and
  `FOLIAGE_BATCH` RenderItems through registered encoders. `ColorPass`,
  `ShadowPass`, and `IdPass` no longer use C++ `Drawable` casts in their
  draw-time submit paths.
- 2026-07-08: legacy `GeometryDrawCall`, `get_geometry_draws()`,
  `draw_geometry()`, `get_mesh_for_phase()`, and `resolve_mesh_geometry()`
  were removed from the live C++/Python API. Mesh, line, world text, foliage,
  and Python drawable components now submit through `collect_render_items()`.
- 2026-07-08 audit: `ColorPass` and `ShadowPass` still duplicate collection for
  non-mesh items in some draw paths. They collect items while building draw
  calls, store the item payload only for mesh, and re-call
  `collect_render_items()` during draw by `component + geometry_id`. The next
  cleanup should make draw calls/tasks reference pass-owned collected items
  instead of re-querying mutable drawable state.
- 2026-07-08: initial C++ `RenderSceneItemCollector` helper landed in
  `termin-render`. `ColorPass` and `ShadowPass` now collect scene items once per
  pass execution and draw from collector item indices instead of re-collecting
  non-mesh items during draw.
- 2026-07-08: `ColorPass` and `ShadowPass` no longer branch between mesh and
  non-mesh submit paths. They build one `RenderItemDrawSubmitRequest` per task;
  item-kind differences are handled by the shared submission layer and
  registered encoders.
- 2026-07-08: mesh submission was moved behind the same RenderItem encoder
  registry used by line, text, and foliage. `TC_RENDER_ITEM_KIND_MESH` is now a
  built-in reserved encoder entry instead of a special dispatcher branch.
- 2026-07-08 audit: `IdPass`, `DepthPass`, `DepthOnlyPass`, and `NormalPass`
  still treat geometry collection as mesh-only. Their draw loops submit through
  `submit_render_item_draw()`, but collection filters out non-mesh RenderItems
  before task creation. This is not the old duplicated non-mesh draw path, but it
  is still incomplete coverage for foliage, line, text, and future item kinds.
- 2026-07-09 direction update: the next migration should not preserve a
  `mesh` versus `non-mesh` conceptual split. Mesh is only one built-in item
  kind with a registered encoder. Passes should build item-kind-agnostic
  `RenderTask` records from collector-owned `RenderItem` snapshots, then rely on
  encoder/pass compatibility metadata instead of hard-coded mesh filters.
- 2026-07-09: `RenderItemDrawSubmitRequest::prepare_material_resources` was
  removed. Passes now provide explicit `RenderItemResourceBinding` packets with
  material resource views plus named uniform/texture bindings. The shared submit
  path binds those resources for mesh, and non-mesh encoders can call
  `bind_render_item_common_resources()` for additional shader layouts.
- 2026-07-09: `ColorPass` and `ShadowPass` now build pass-local render task
  records before the submit loop. This is intentionally still a local
  implementation slice, not the final shared `RenderTaskList` ABI, but the draw
  loops now submit tasks instead of constructing submit requests directly from
  sorted draw-call records.
- Remaining live migration work: finish Python-facing RenderItem integration
  tests and continue replacing any historical docs/examples that still describe
  the retired geometry-side-channel model.

## Problem

Current rendering has several overlapping draw ownership models:

- Historical `GeometryDrawCall` and geometry-id discovery paths did not carry
  enough structured backend payload to be the single render protocol and have
  now been retired from live code.
- `upload_per_draw_uniforms_tgfx2()` still exists for narrow per-draw renderer
  data such as skinned mesh bone matrices; it should not grow into a replacement
  draw ownership channel.
- Direct `draw_tgfx2()` and `RenderContext::prepare_tgfx2_material_resources`
  have been removed from the live code, but old design references may still
  exist in historical notes.
- The C drawable ABI exposes `collect_render_items()` and no longer has a
  geometry-draw side channel.

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
- `RenderItem` is a per-collection snapshot. A drawable may cache expensive
  representation data, but it must not own the submitted `RenderItem` as mutable
  draw state shared by multiple passes.

Expected initial item kinds:

```text
Mesh
LineBatch
TextBatch
FoliageBatch
```

The exact list can evolve, but the model must avoid reintroducing
drawable-owned `draw_tgfx2()` paths for non-mesh renderers.

#### Drawable Caches Versus RenderItem Ownership

Avoid moving `RenderItem` ownership into drawables just to reduce repeated field
initialization. Most item fields are cheap descriptors: handles, submesh
indices, material phase references, transforms, and small flags. The expensive
data should be cached below the item level:

```text
Drawable/component cache:
  generated line meshes or point buffers
  text layout and font atlas state
  foliage data handles and instance buffers
  resolved resource handles and generation counters

Per-pass/per-frame RenderItem:
  phase/material selection
  model snapshot
  item kind and payload handle/view
  copied short strings or arena-owned borrowed payloads when needed
```

The pass-owned snapshot prevents drift between collection and draw. An encoder
may resolve stable handles carried by the item, but it should not read mutable
component fields to recover data that should have been captured in the item
payload.

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

### RenderSceneItemCollector

Scene-oriented passes should share a collector helper instead of each pass
hand-rolling scene iteration, item validation, lifetime storage, material phase
resolution, and task indexing.

Responsibilities:

- iterate scene drawables with the caller's visibility, layer, and category
  filters;
- build a `tc_render_item_collect_context` from pass inputs;
- collect each drawable exactly once per requested phase/context;
- validate and copy item payloads into collector-owned frame/pass storage;
- expose stable item references or indices for pass task builders;
- optionally resolve common material phase references and entity/component
  metadata;
- log malformed items and invalid collection requests with pass/component
  context.

Non-responsibilities:

- selecting final pass membership beyond caller-provided generic filters;
- sorting or batching tasks as a semantic pass decision;
- binding resources or issuing backend draw calls;
- hiding mutable backend services inside the collection context.

The important ownership rule is:

```text
Drawable emits into the collector.
Collector owns copied item storage for the pass/frame.
Pass tasks reference collector item indices.
Draw code consumes the referenced item snapshot.
```

This avoids the current `component + geometry_id` re-collection pattern and also
handles cases where one component emits multiple items for the same geometry id
or material phase.

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

### Pass Compatibility

Pass membership must be based on explicit compatibility between the pass
contract and the item encoder, not on a hard-coded `Mesh` versus `NonMesh` split.

Important cases:

- `FoliageBatch` should participate in `ColorPass` and `ShadowPass`, and should
  eventually participate in `IdPass`, `DepthPass`, `DepthOnlyPass`, and
  `NormalPass` once those passes declare matching foliage vertex-transform
  contracts and built-in shader templates.
- `LineBatch` and `TextBatch` can be meaningful in `IdPass` when the pass supplies
  an override pick color through the draw context.
- `LineBatch` and `TextBatch` are not automatically meaningful in `DepthPass` or
  `NormalPass`: a color/text/line encoder can submit backend commands, but that
  does not imply it writes encoded depth or normal values with the pass ABI.

The migration rule is:

```text
Collect all drawable RenderItems requested by the phase.
Build tasks only for item/pass combinations with declared support.
Log unsupported combinations when they indicate a missing migration or asset bug.
Do not silently equate "not mesh" with "not renderable".
```

## Item-Kind-Agnostic Task Model

The next architectural target is to remove `mesh` / `non-mesh` as a pass-level
branching concept. A render pass should not ask "is this a mesh?" before it can
build a task. It should ask whether the collected item kind has an encoder that
declares support for the pass contract and resource policy.

The target flow is:

```text
Drawable/component emits RenderItem
RenderSceneItemCollector owns copied RenderItem snapshots
Pass builds RenderTask records from compatible items
Pass sorts/orders RenderTask records
Shared submit layer binds common resources and dispatches encoder
Encoder interprets only its item-kind payload and emits backend draws
```

`TC_RENDER_ITEM_KIND_MESH` should remain a built-in ABI kind, but it should not
receive special pass architecture. It should be registered and queried through
the same encoder/compatibility route as `LINE_BATCH`, `TEXT_BATCH`,
`FOLIAGE_BATCH`, and future kinds.

### RenderTask Shape

`RenderTask` is the pass-owned unit. It should be the only thing the draw loop
submits after sorting. It can start as a C++ internal structure and later become
a C ABI packet if needed.

Candidate common fields:

```text
item_index
item_kind
component/entity/debug identity
sort_key
final_shader
material_phase / material handle / phase index
pass contract view
draw context view
pass resource packet
pass-local draw payload reference
encoder compatibility result
```

Pass-specific payloads should be explicit side records referenced from the task,
not hidden in callbacks:

```text
ColorPass:
  model/draw data
  lighting and shadow resource packet
  extra texture resource packet

ShadowPass:
  light-space draw data
  shadow map/cascade resource packet

IdPass:
  pick id / override color packet

Depth/Normal:
  pass draw uniform packet and contract-specific output resources
```

The task builder can skip incompatible item/pass pairs, but it must do so through
declared compatibility rather than item-kind name checks. For example, foliage
support in depth/normal should be enabled when the foliage encoder declares a
matching vertex transform contract and shader template, not because the pass was
changed from `if mesh` to `if mesh or foliage`.

### Encoder Metadata

The encoder registry needs more than an `encode` function if passes are to avoid
mesh-specific branches.

Minimum metadata/hooks:

```text
item_kind
debug_name
supported pass contract features
required material phase policy
supported vertex transform kinds
supported pass outputs or semantic roles
optional task validation hook
optional shader usage hook
encode hook
```

The exact ABI can start conservative. A simple first slice can expose a C++
`RenderItemEncoderCapabilities` helper inside `termin-render` while keeping the
C-facing payload ABI stable. The important rule is that passes query the encoder
capability table instead of hard-coding built-in item kinds.

### Resource Binding Without Callbacks

`RenderItemDrawSubmitRequest::prepare_material_resources` is the main remaining
leak from pass-owned resource binding into item encoders. It should be removed,
but not by pushing resource binding into every encoder.

Target ownership:

```text
Pass:
  creates explicit pass resource packets and per-task draw payload packets

Shared submit layer:
  resolves shader layout
  binds material/pass/draw resources from explicit packets
  exposes a small binder helper for encoders that need multiple shader layouts

Encoder:
  binds item-kind-specific buffers and payload resources
  may call the shared binder with an explicit packet and shader layout
  does not call a pass-provided callback
```

For line tube body/cap shaders and foliage instancing, the encoder may need to
bind common resources against more than one shader layout. That should be an
explicit binder operation:

```text
bind_render_task_common_resources(ctx, shader_layout, task.resource_packet)
```

not:

```text
request.prepare_material_resources(ctx, shader_layout, phase)
```

This lines up with #207: once the callback is gone, the resource packet can be
flattened into C-like runtime data contracts with ptr/count arrays and stable
handles.

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

## Custom Passes And Escape Hatches

The encoder registry is not intended to be the whole user pass API. It is the
standard item-kind backend ABI for scene drawable work.

Supported paths:

```text
Scene drawable rendering:
  collect RenderItems
  build pass-owned RenderTasks
  submit tasks through the shared submission layer and registered encoders

Special/manual pass rendering:
  pass uses tgfx2/backend APIs directly for fullscreen, blit, procedural,
  compute-like, editor overlay, or other non-scene-drawable work
```

A custom pass may draw directly when it owns the geometry and resource policy.
If it wants to render ordinary scene drawables, the expected path is
`collect_render_items()` plus shared submission. Bypassing encoders for scene
drawables is an advanced escape hatch: the pass then owns material binding,
shader variants, skinning, item-kind payload interpretation, diagnostics, and
compatibility with future item kinds.

The pass plugin API should therefore sit above encoders:

```text
custom pass chooses phase/filter/contract/resources
RenderSceneItemCollector gathers item snapshots
pass builds and sorts tasks
submit layer dispatches item-kind encoders
```

This keeps user passes flexible without making every custom pass know how to
draw mesh, line, text, foliage, and future item kinds by hand.

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

## Storage Layout Direction

Keep `tc_render_item` as an AoS C ABI record. It is the emission and submission
unit crossing C, C++, and Python boundaries, and a full SoA ABI would make union
payloads, borrowed strings, and third-party item kinds much harder to extend.

Use SoA selectively inside pass-owned implementation details:

```text
RenderSceneItemCollector:
  may store common fields and typed payload buckets internally
  keeps C ABI emission as tc_render_item

RenderTaskList:
  good candidate for SoA
  item_index[]
  sort_key[]
  final_shader[]
  resolved_phase[]
  pass_local_payload_index[]
```

The first optimization target should be the task list, not the public item ABI.
Sorting and draw loops mostly read task keys, shader handles, material refs, and
item indices; they do not need to move whole item payloads around. If profiling
shows pressure from item storage, the collector can add typed per-kind buckets
or arenas without changing the drawable-facing ABI.

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
3. Teach `MeshRenderer` and `SkinnedMeshRenderer` to emit mesh items.
4. Add a shared mesh task submission path in `termin-render`.
5. Convert `GeometryPassBase` and the core geometry passes to collect items,
   build tasks, order tasks, and submit them one at a time.
6. Remove draw-time C++ `Drawable` casts from converted pass paths.
7. Convert one non-mesh direct path, preferably `LineRenderer` or
   `WorldTextComponent`, to a typed item and encoder.
8. Remove `RenderContext::prepare_tgfx2_material_resources` once direct paths no
   longer need pass-owned callbacks. Done for the live C++ render path.
9. Remove legacy geometry-side-channel APIs. `GeometryDrawCall`,
   `get_geometry_draws()`, `draw_geometry()`, `get_mesh_for_phase()`,
   `resolve_mesh_geometry()`, `get_geometry_ids_for_phase()`,
   `supports_direct_tgfx2_draw()`, and `draw_tgfx2()` have been removed from
   the live C++/Python render API.
10. Keep `upload_per_draw_uniforms_tgfx2()` narrow and renderer-owned until
    skinned mesh bone data has a typed RenderItem payload/resource path.
11. Add `RenderSceneItemCollector` and make `ColorPass` / `ShadowPass` draw
    calls reference collected item indices instead of re-collecting non-mesh
    items during draw. Initial C++ helper and pass conversion are done; broader
    pass-family adoption remains.
12. Move common task-list construction toward pass-owned `RenderTaskList`
    storage, with SoA task arrays where useful for sort/draw hot paths.
13. Remove remaining pass-level mesh/non-mesh submit branches. Done for
    `ColorPass` and `ShadowPass`; mesh submission now also goes through the
    RenderItem encoder registry as a built-in reserved encoder.
14. Replace mesh-only filters in `GeometryPassBase` and `DepthOnlyPass` with
    pass/item compatibility checks. Foliage should be enabled for id, depth,
    depth-only, and normal only after matching foliage pass contracts and shader
    templates exist. Line/text should be enabled per pass only where their
    encoder produces the pass ABI, not merely because a draw encoder exists.
15. Introduce a pass-owned `RenderTask` or `RenderTaskList` used by Color and
    Shadow first, then by Id/Depth/DepthOnly/Normal. Done as a pass-local
    implementation slice for Color and Shadow; still needed for the
    Id/Depth/DepthOnly/Normal family and for a shared task shape if duplication
    starts to matter.
16. Add encoder capability metadata and move pass membership decisions to
    pass-contract/item-kind compatibility checks. Mesh must use the same route
    as line, text, foliage, and future item kinds.
17. Remove `RenderItemDrawSubmitRequest::prepare_material_resources`. Done:
    `RenderItemResourceBinding` now carries explicit pass resource packets, and
    `bind_render_item_common_resources()` can bind them for any shader layout.
18. Convert ColorPass, ShadowPass, IdPass, DepthPass, DepthOnlyPass, and
    NormalPass to build resource packets without lambdas. Done for resource
    binding; task construction still needs to move away from direct item-kind
    branching where passes remain mesh-only.
19. Move the encoder registry out of global static storage when module
    bootstrap/hot-reload ownership is ready. Until then, keep registration
    explicit and documented.
20. Update `docs/render-phase-semantics.md` and live render docs after the
    item-kind-agnostic task contract becomes the implementation contract.

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
- typed line, text, and foliage item paths render without `draw_tgfx2()`;
- mesh, line, text, and foliage all pass through the same task/submission
  contract without a pass-level mesh/non-mesh branch;
- pass ordering remains pass-owned;
- material phase shader override still works through the task submission path;
- unsupported item/contract combinations log useful errors and do not silently
  fall back.
- geometry-pass coverage tests for foliage id/depth/normal once foliage pass
  contracts and shader templates are added;
- line/text picking tests if `IdPass` support is enabled through override-color
  draw context.
- resource binding tests proving non-mesh encoders no longer depend on
  `RenderItemDrawSubmitRequest::prepare_material_resources`.

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
- How skinned mesh bone data should move from `upload_per_draw_uniforms_tgfx2()`
  into an explicit typed payload/resource path.
- Exact public shape of `RenderSceneItemCollector`: C-only helper, C++ helper
  over C sinks, or both.
- Whether task storage becomes a shared SoA `RenderTaskList` type or remains a
  private optimization inside concrete pass families.

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
