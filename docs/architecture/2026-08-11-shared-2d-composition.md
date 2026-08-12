# Shared 2D Composition

## Status

Accepted architecture under implementation. The common affine values,
`DrawList2D` and the value-level `CompositionEvaluator2D` now exist;
`SceneView`, widget portals and the two semantic trees still need consolidation
behind that evaluator and a reusable projection bridge under Kanboard #1519.

The decision rationale is recorded in the
[architecture council protocol](../architecture-council/2026-08-11-shared-2d-composition-boundary.md).

## System boundary

Termin has one 2D composition ecosystem with two retained semantic trees:

```text
termin-gui-native Widget tree       termin-visual-scene GraphicItem tree
measure/layout/style/input          affine geometry/z/opacity/hit shapes
                 \                   /
                  \                 /
             shared value-level composition
             transform/clip/bounds mapping
                         |
                tgfx::DrawList2D executor
```

The trees remain separate systems of ownership:

- `tc_ui_document` owns widgets and generation-checks `tc_widget_handle`;
- `tc_visual_scene` owns graphic items and generation-checks
  `tc_graphic_item_handle`;
- neither owner adopts, destroys or serializes the other's objects;
- no common `Node`, object vtable, pool or universal scene document is
  introduced.

## Layer ownership

### `termin-base`

Owns exact C/C++ affine and geometry values and stateless primitive operations:
composition, finite validation, fallible inverse, point/vector mapping and
transformed bounds. `tc_affine2f`/`Affine2f` are the canonical interchange
values at composition boundaries.

### `termin-graphics`

Owns paths, paints, draw commands, `DrawList2D` and the non-owning 2D
`CompositionEvaluator2D`. The evaluator operates on values and scoped effective
state:

- accumulated affine and fallible inverse;
- effective visibility and opacity;
- inherited clip state;
- point and bounds conversion;
- well-nested transform/opacity/clip lowering into `DrawList2D`.

It does not own object topology, generation handles, invalidation, event
controllers, factories or serialization. Semantic owners traverse their own
trees and feed local values into the evaluator.

### `termin-visual-scene`

Owns retained graphic items, arbitrary affine local placement, stable visual
ordering, geometric hit shapes and optional interaction policies. Its paint,
bounds and hit-test traversal uses the shared evaluator while retaining the
existing item vtable and scene handle lifetime.

### `termin-gui-native`

Owns widget constraint layout, focus, keyboard/text routing, style,
accessibility, overlays and UI presentation metrics. Layout produces logical
bounds. A later composition phase maps an already measured widget subtree into
document presentation space.

The public widget subtree transform may intentionally remain translation plus
positive uniform scale. At the shared boundary it is converted exactly to
`tc_affine2f`; this restriction must not weaken visual-scene affine semantics.

## Rendering contract

`tgfx::DrawList2D` is the single backend-neutral execution vocabulary.
Visual-scene already emits it directly. `tc_ui_draw_list` remains permitted as
a language-neutral widget paint frontend, especially for UI text and host
resources, but transform, clip and nested-scene commands lower through the
same `termin-graphics` composition semantics.

There must not be two independent definitions of transform order, clip
inheritance, opacity composition or malformed scope recovery. Renderer errors
are logged and do not leak damaged stack state into the next batch.

## Layout versus placement

Layout and placement are separate phases:

1. Widget measure/layout resolves intrinsic sizes and constraints in stable
   logical units.
2. Composition accumulates subtree placement, camera transform, density and
   clipping at paint/input boundaries.
3. Pixel snapping happens only at the render boundary.

Camera zoom does not cause widget intrinsic reflow. Density and accessibility
font scale remain explicit UI inputs and may affect measurement. The renderer
uses the accumulated geometric scale when selecting physical glyph size.

Graphic items have no implicit widget layout. Their local bounds come from the
item implementation and their world bounds are exact affine projections.

## Hit testing and input

Paint and hit testing use the same accumulated transform and clip semantics.
Each semantic owner keeps its own traversal order and event policy, but point
conversion comes from the common evaluated placement.

- singular transforms are non-hittable and diagnosed according to the owner
  contract;
- a pointer route maps coordinates into every receiver's local space;
- capture stores the existing generation handle and maps each later event
  through current placement;
- path clips are tested geometrically; an AABB is not a substitute for the
  exact clip contract.

A migration is complete only when paint, bounds, hit testing and pointer
mapping agree. A paint-only adapter is not a supported intermediate public
contract.

## Cross-tree projections and portals

Cross-tree composition is represented by a non-owning projection bridge:

```text
source anchor handle + target root handle + placement policy
```

The bridge resolves both handles for each reconciliation/layout/interaction
cycle. Stale source detaches the projection; stale target removes the bridge
entry. Neither handle keeps its owner alive.

`SceneView` is the canonical visual-scene-inside-widget projection. A widget
portal is the inverse presentation: a `GraphicItemHandle` anchors a
document-owned widget subtree. The portal receives scene/world logical bounds
and a camera-derived subtree transform; it does not become a graphic item or
transfer widget ownership to the scene.

The reusable bridge belongs to the GUI-facing adapter/composition layer.
`termin-visual-scene` contains no Widget knowledge and has no reverse
dependency on `termin-gui-native`.

Projection policies explicitly define:

- source bounds and supported transform grade;
- ordering relative to source primitives and sibling portals;
- clip boundary;
- input precedence and coordinate conversion;
- invalidation and stale-handle reconciliation;
- overlay anchoring behavior.

Unsupported rotation, shear or non-uniform widget projection is rejected with
a diagnostic until an explicit widget contract supports it. It is never
silently approximated by stretched bounds.

## Migration rules

- Reuse `tc_affine2f`; do not introduce another general transform type.
- Do not move Widget or GraphicItem storage into the common layer.
- Do not add compatibility fallback traversal after a consumer is migrated.
- Preserve generation-handle lifetime and exactly-once destruction.
- Keep domain selection/drag/LOD policies above the common evaluator.
- Verify identity output before removing old paths, then cover nested affine,
  clips, opacity, DPI/font scale, pointer capture and stale portals.
- A new top-level composition package requires a separate architecture
  decision; the initial common implementation belongs in existing
  `termin-base` and `termin-graphics` layers.

## Tracking

Kanboard #1519 is the implementation umbrella:

- #1520 — common `termin-graphics` composition evaluator (implemented);
- #1521 — visual-scene traversal migration;
- #1522 — GUI render/lowering migration;
- #1523 — GUI bounds and pointer-mapping migration;
- #1524 — reusable widget-scene projection bridge;
- #1525 — cross-tree verification and removal of obsolete paths.
