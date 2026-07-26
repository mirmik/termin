# Foundation for 2D game support

Date: 2026-07-27

## Context

Termin is primarily a 3D engine, but most of its scene, asset, input, audio,
animation and rendering infrastructure is also useful for 2D games. The 2D
feature set should therefore extend the existing engine instead of introducing
a parallel scene model.

The repository already provides several relevant building blocks:

- `CameraComponent` supports orthographic projection and `ortho_size`;
- textures are integrated into the asset and runtime-package pipelines;
- `Canvas2DRenderer` provides batched immediate drawing in pixel coordinates,
  including textured quads, solid primitives, text, clipping and nearest or
  linear sampling;
- the engine already has entity transforms, render-item submission, input,
  audio, tweening, animation assets and UI overlays.

What is missing is a scene-level 2D model: sprite assets and components,
world-space 2D batching and sorting, tile maps, sprite animation, 2D physics,
and the corresponding editor workflow.

`Canvas2DRenderer` is useful low-level infrastructure but must not become the
scene representation for 2D games. It is an immediate, screen-space renderer
and does not provide entity lifecycle, world transforms, scene culling,
picking or persistent render ordering.

## Coordinate-system contract

Termin uses Z-up world coordinates. The canonical 2D world plane should
therefore be XZ rather than XY:

- world X is the horizontal 2D axis;
- world Z is the vertical 2D axis;
- world Y is depth;
- a canonical 2D camera is on the negative-Y side and looks along positive Y;
- the camera sees positive X to the right and positive Z upward;
- a sprite's canonical front normal is negative Y;
- positive 2D rotation is counter-clockwise as seen by that camera, and maps
  to a right-handed world rotation around negative Y;
- downward 2D gravity maps to negative world Z.

The mapping is:

```text
2D position (x, y) -> world position (x, depth, y)
2D angle           -> world rotation around -Y
2D gravity (0, -g) -> world gravity (0, 0, -g)
```

This contract is implemented by the header-only `termin::world2d` helpers in
`termin-base/include/termin/geom/world2d.hpp`.

A canonical quad is authored counter-clockwise when viewed from the canonical
camera, so its front normal is negative Y. Sprite `flip_x` and `flip_y` should
flip UVs instead of applying a negative transform scale; this preserves
geometry winding. An explicitly mirrored entity or parent transform retains
the ordinary 3D mesh semantics and may reverse winding when face culling is
enabled. The sprite renderer's default culling policy belongs to the separate
render-state and batching decision.

Public 2D APIs should still use `Vec2(x, y)`, where `y` means the vertical 2D
coordinate. The mapping to XZ must live in a small explicit adapter layer.
Gameplay code should not need to manually scatter reads and writes to
`Transform.position.z`.

Screen-space UI remains in pixel XY coordinates, normally with its existing
top-left/downward convention. World 2D and screen UI may share lower-level
rendering primitives, but they are different coordinate systems and different
component lifecycles.

The first implementation should support one canonical world plane. A
configurable arbitrary `Plane2D` would complicate physics, editor gizmos,
camera tooling and batching. It may be introduced later if concrete use cases,
such as 2D gameplay embedded on arbitrary surfaces, justify the complexity.
Top-down gameplay integrated with a 3D ground plane is such a possible future
case: in a Z-up 3D world that plane naturally uses XY and is viewed along Z.

## Architectural principles

### Reuse the existing scene and transform model

There should be no independent `Scene2D`, `Entity2D` or transform hierarchy.
Ordinary entities and the existing 3D transform remain authoritative. This
keeps mixed 2D/3D scenes possible and avoids duplicating serialization,
hierarchy, lifecycle and editor behavior.

A separate `Transform2D` component is not required. A typed adapter or helper
API may expose 2D position, angle and depth while mapping them to the ordinary
transform.

### Separate world 2D from immediate canvas rendering

World sprites must participate in the normal drawable/render-item pipeline.
They need stable entity ownership, culling, picking, material phases and
framegraph integration. `Canvas2DRenderer` remains appropriate for overlays,
debug visuals and retained UI composition.

The two paths should reuse low-level textured-quad batching where practical,
but a shared internal primitive is preferable to forcing scene rendering
through the public immediate-canvas facade.

### Make sprite identity an asset concern

A sprite is not merely a texture stored on a component. `SpriteAsset` should
identify a texture region and carry the information required for consistent
rendering and authoring:

- texture asset UUID;
- atlas rectangle or normalized UV region;
- source pixel dimensions;
- pivot;
- pixels per world unit;
- optional nine-slice border;
- relevant sampling/import metadata.

Components should reference sprite assets by stable asset identity. Sprite
animation, tile sets and editor tooling can then reference the same regions
without copying UV coordinates and pivots.

### Use explicit render ordering

The primary ordering contract should be:

```text
render phase
-> sorting layer
-> order in layer
-> optional spatial-depth policy
-> stable tie-breaker
-> submission index fallback
```

The render phase selects an ordering domain before this comparison; items from
different phases are not interleaved by the 2D comparator. World Y remains
genuine spatial depth and may participate through an explicit back-to-front or
front-to-back policy, but it is ignored by the default policy and must not be
overloaded as an implicit integer draw-order field. Explicit `sorting_layer`
and `order_in_layer` make authoring, serialization and debugging deterministic.
The collector supplies a stable entity/geometry-derived tie-breaker, with the
snapshot submission index as the final collision fallback.

The allocation-free ordering primitive is owned by `termin-render` and lives
in `termin/render/world2d_ordering.hpp`. It deliberately does not extend the
general `ColorPass` sort key: that path currently groups ordinary 3D items by
shader and distance, while transparent 2D compositing must not be reordered by
texture, material or shader.

Batch construction happens only after sorting. The world-quad renderer may
merge a maximal adjacent run of submissions with compatible pipeline, render
state, material, texture/atlas and sampler state. It may never move a later
compatible item across an incompatible item to make a larger batch.

The default world-sprite state is alpha blending enabled, depth test enabled,
depth writes disabled and face culling disabled. This allows opaque 3D depth
already present in the target to occlude sprites while explicit 2D order
controls sprite-to-sprite compositing. Alternative materials may opt into
different states, forming separate adjacent batch runs.

## Core components and assets

### Sprite rendering foundation

`SpriteRenderer2D` is the central scene component. Its initial inspectable
surface should cover:

- `sprite`;
- tint/color;
- horizontal and vertical flipping;
- sorting layer and order in layer;
- material override;
- visibility;
- simple, tiled and sliced draw modes where supported.

The renderer should submit scene render items and batch compatible sprites by
phase, material, texture/atlas and sampling state without violating ordering.
It also needs:

- camera culling;
- entity picking;
- editor bounds and pivot visualization;
- correct alpha blending;
- nearest and linear sampling;
- protection against texture-atlas bleeding;
- runtime-package export of required assets and built-in shaders.

Pixel-art correctness is a system contract, not an optional polish item.
Nearest filtering, pixel snapping, atlas padding and integer-scale behavior
must be tested together.

### 2D camera profile

The existing `CameraComponent` already supplies orthographic projection and
screen-ray functionality. A `Camera2D` profile or a focused
`PixelPerfectCamera2D` companion should configure and extend it instead of
duplicating camera math.

Expected capabilities:

- canonical orientation from negative Y toward positive Y;
- world/screen coordinate conversion on the XZ plane;
- pixels-per-unit configuration;
- pixel-perfect snapping;
- fixed world-height, fixed logical-resolution and integer-scaling modes;
- viewport/aspect handling;
- optional camera-follow and bounds behavior, either here or in later helper
  components.

### Sprite animation

`SpriteAnimationClip` should contain an ordered sequence of sprite references
with per-frame duration and optional frame events.

`SpriteAnimator2D` should own playback state and drive `SpriteRenderer2D`:

- autoplay and initial clip;
- play, pause and stop;
- speed;
- looping;
- current time/frame;
- frame events.

The implementation may integrate with the existing animation asset/runtime
infrastructure, but flipbook identity should remain expressed as sprite frames
rather than raw animated UV numbers.

### Tile maps

Tile-map support should consist of:

- `TileSetAsset` for sprite references, collision shapes and tile metadata;
- `TileMapAsset` for layers and chunked tile data;
- `TileMapRenderer2D` for chunk building, culling and rendering;
- editor painting tools.

The first version should support an orthogonal grid, multiple layers,
tile flip/rotation, sorting controls and incremental rebuilding of changed
chunks. Brush, erase, fill and tile picker are required for the feature to be
practical. Isometric and hexagonal grids should wait until the orthogonal
contract is stable.

### 2D physics

Constraining the existing 3D solver to a plane is not a sufficient replacement
for native 2D physics. A dedicated 2D backend should expose:

- `PhysicsWorld2D`;
- `RigidBody2D` with static, kinematic and dynamic modes;
- box, circle, capsule, polygon and chain/edge colliders;
- triggers or `Area2D`;
- collision layers and masks;
- ray casts, shape casts and overlap queries;
- common joints such as revolute, distance and prismatic joints.

The physics API should use abstract 2D coordinates and synchronize through the
canonical XZ adapter. A mature Box2D-like backend is preferable to maintaining
a second solver model inside the current 3D physics implementation.

The first physics milestone can be limited to world/body lifecycle, box and
circle colliders, triggers, contact events and ray/overlap queries. More
colliders and joints can follow without changing the core component contract.

## Reusable existing systems

The following systems should remain shared:

- entity and scene lifecycle;
- transforms and hierarchy;
- asset identity and runtime packaging;
- `InputComponent` and viewport input routing;
- `AudioSource` and `AudioListener`;
- tweening;
- UI overlay components;
- framegraph, render targets and viewport management.

Additional scene-level components can be added after the foundation:

- `TextRenderer2D`;
- `ShapeRenderer2D`;
- `ParticleSystem2D`;
- `ParallaxLayer2D`;
- `NineSliceRenderer2D`;
- `CameraFollow2D`;
- optional 2D lighting and occluders.

These are not prerequisites for the first playable 2D project.

## Delivery milestones

### 1. Sprite asset and rendering foundation

Define the coordinate, asset, sorting and batching contracts; implement
`SpriteAsset` and `SpriteRenderer2D`; integrate culling, picking, serialization,
runtime packaging and the editor inspector.

Closing condition: a scene with many textured entities renders deterministically
through the normal framegraph on supported graphics backends, can be selected
in the editor and survives save/load and runtime packaging.

### 2. 2D camera and editor workflow

Add canonical XZ camera setup, screen/world conversion, pixel-perfect scaling,
2D-oriented viewport controls and sprite gizmos.

Closing condition: an author can create, position, select and preview a
pixel-stable XZ 2D scene without manually configuring 3D camera orientation or
editing raw Z coordinates.

### 3. Sprite animation

Add clip assets, import/authoring support and animator playback with frame
events.

Closing condition: an entity can play serialized flipbook clips in both editor
preview and runtime builds with deterministic timing.

### 4. Tile-map runtime and authoring

Add tile-set and chunked tile-map assets, renderer, collision metadata and
orthogonal-grid editing tools.

Closing condition: a non-trivial multi-layer map can be painted, saved,
incrementally edited, culled and packaged without rebuilding or drawing the
entire map every frame.

### 5. Native 2D physics

Integrate a dedicated backend with the XZ transform adapter, initial body and
collider components, triggers, queries and collision events.

Closing condition: a small platformer-style scene runs stable fixed-step
simulation with dynamic bodies, static terrain, contacts and trigger events,
and produces the same behavior after scene reload and runtime packaging.

### 6. Playable reference project and hardening

Build a small reference project that combines sprites, animation, camera,
input, physics, audio and UI. Use it for backend smokes, performance budgets
and documentation.

Closing condition: the reference project builds through the standard SDK and
project packaging workflows and demonstrates a complete playable loop on the
primary desktop backends.

## Risks and deferred decisions

- A common internal quad-batching primitive may require careful placement
  between `termin-graphics`, `termin-render` and component packages.
- Sorting correctness and batching efficiency conflict unless the ordering
  contract explicitly defines when reordering is legal.
- Texture import settings currently cover general textures but not a complete
  sprite/atlas authoring model.
- Editor interaction is currently strongly 3D-oriented; merely adding runtime
  components would leave 2D support impractical.
- Arbitrary 2D planes, isometric/hex tile maps, advanced joints, 2D lights and
  normal-mapped sprites are intentionally deferred until the basic XZ path is
  proven.
