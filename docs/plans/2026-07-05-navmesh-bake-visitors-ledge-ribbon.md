# NavMesh Bake Visitors And Ledge Ribbon Sources

Date: 2026-07-05
Context: ChronoSquad ledge/climbing migration from Unity to Termin

## Status

Design note and motivation for a future Termin implementation session.

This is not a detailed task checklist. It records why ChronoSquad needs a more
general navmesh bake-source architecture in Termin, what shape that architecture
should probably take, and how the ledge/climbing use case should drive the
design without hard-coding ChronoSquad concepts into the generic navmesh module.

Update 2026-07-05: the bake visitor registry direction remains valid, but the
synthetic ribbon representation has been rejected after testing. The replacement
path is first-class 1D Detour linear polygons, tracked in
`2026-07-05-detour-1d-linear-paths.md`.

## Problem

ChronoSquad needs climbable ledges that behave like navigable one-dimensional
or narrow two-dimensional spaces:

- an actor can enter a ledge from several places;
- move along a long ledge;
- leave it through several top/bottom/drop points;
- keep gameplay-specific braced poses and animations while doing so.

Representing this as off-mesh links between every possible enter/exit pair is
the wrong graph. With `N` access points it trends toward all-to-all authoring and
query behavior. It also hides the real topology: a ledge is a continuous path,
not a pile of teleports.

The old Unity implementation worked around Unity NavMesh constraints with
`CommonClimbingBlock`, generated climbing surfaces, special NavMeshLink areas,
and per-link `BracedCoordinates`. The useful part of that design is the semantic
path output:

```text
NavMesh result
  -> semantic UnitPathPointType
  -> BracedCoordinates
  -> ChronoCore animatronics
```

The Unity-specific part, especially generated helper surfaces and nearest-block
lookup, should not be copied literally into Termin.

## Desired Ledge Model

A ledge should be explicitly authored as project/gameplay data:

```text
LedgeComponent
  points/polyline
  outward/up frame data
  ribbon width and offsets
  ledge area id
  access point definitions
```

Editor tooling can help place points by raycasting onto scene meshes and
snapping to nearby mesh edges, but the result should be visible, editable data,
not implicit geometry analysis that only exists during bake.

Access points can be authored separately or as child records:

```text
LedgeAccess
  ledge segment + t
  enter/exit/drop kind
  top/bottom probe rule
  off-mesh area id
```

At navmesh bake time the ledge produces:

- a synthetic narrow ribbon mesh along the ledge polyline, with a dedicated
  area such as `LEDGE_AREA`;
- off-mesh links from normal walkable navmesh to the ribbon, or from the ribbon
  to drop/top/bottom endpoints;
- enough stable metadata for ChronoSquad to recover braced coordinates from
  Detour path points.

This keeps Detour responsible for finding paths along the ledge. ChronoSquad
then translates `LEDGE_AREA` path segments and ledge off-mesh areas into
semantic movement points such as `BRACED_HANG`, `DOWN_TO_BRACED`,
`BRACED_TO_UP`, and `JUMP_DOWN`.

## Why Synthetic Ribbon Geometry

The ribbon is not meant to be real render or collision geometry. It is a
pathfinding representation.

Trying to make Recast discover ledges from physical meshes is fragile:

- Recast filters ledge spans;
- agent radius erosion can delete narrow surfaces;
- vertical wall/edge topology is not the same as walkable surface topology;
- the gameplay pose is not the same as the pathfinding point.

A generated ribbon gives stable topology while leaving gameplay pose generation
to ChronoSquad-specific code.

## Builder Integration Problem

The current Recast builder mostly collects `MeshComponent` geometry from an
entity/subtree and separately collects `OffMeshLinkComponent` instances. That is
too concrete for this use case.

We need the builder to collect navmesh input from multiple component kinds:

```text
ordinary mesh sources
procedural/synthetic geometry sources
off-mesh link sources
project-specific metadata sources
```

But `MeshComponent` must not be polluted with pathfinding knowledge. A render or
asset component should remain useful in projects that do not use navmesh at all.

## Proposed Architecture: Bake Visitor Registry

Use a navmesh-owned visitor/adapter registry rather than inheritance from a
generic `NavMeshBakeSource` interface on every component.

Conceptually:

```cpp
struct NavMeshBakeContext {
    Entity builder_entity;
    Mat44 world_to_bake;
    std::string agent_type_name;
    float agent_radius;
    float agent_height;
    float agent_max_climb;
    // area registry/settings as needed
};

struct NavMeshGeometrySink {
    void add_triangles(..., int area_id, Entity source, const char* debug_name);
};

struct OffMeshLinkSink {
    void add_link(..., int area_id, unsigned int stable_user_id, Entity source);
};
```

And registration:

```cpp
register_navmesh_geometry_visitor("MeshComponent", collect_mesh_component);
register_navmesh_link_visitor("OffMeshLinkComponent", collect_off_mesh_link);
register_navmesh_geometry_visitor("LedgeComponent", collect_ledge_ribbon);
register_navmesh_link_visitor("LedgeComponent", collect_ledge_access_links);
```

The builder scans components in its configured scope and asks the registry
whether a visitor exists for each component type. If yes, the visitor receives
the raw component pointer plus bake context and emits geometry or links.

Visitor registrations are module-owned. A project module that registers
`LedgeComponent` bake visitors must do it inside a navmesh visitor registration
owner scope, and module unload must call owner cleanup before the shared library
is unloaded. Otherwise a global `std::function` can keep a callable pointing into
unloaded code. The registry therefore needs:

```cpp
set_navmesh_bake_visitor_registration_owner(module_id);
register_navmesh_geometry_visitor("LedgeComponent", collect_ledge_ribbon);
register_navmesh_link_visitor("LedgeComponent", collect_ledge_access_links);
unregister_navmesh_bake_visitor_owner(module_id);
```

Python bindings can expose this cleanup, but automatic project-module cleanup
should not force every module import to load navmesh native code. C++/Python
module integration should either call the navmesh cleanup explicitly from module
close code or grow a generic module-registration lifecycle hook so optional
systems like navmesh can participate without forcing `termin_engine` to link or
import every extension library.

This keeps dependencies pointed the right way:

- `termin-navmesh` may know how to read a mesh for navmesh purposes;
- `MeshComponent` does not know about navmesh;
- ChronoSquad can register ledge visitors from its own module;
- the generic builder does not need to include ChronoSquad headers.

## Builder Scope And Sources

Do not add a new navmesh source component just to opt meshes into the bake.

The existing builder scope remains the source selection mechanism:

```text
CurrentMesh      -> inspect components on the builder entity
AllDescendants   -> inspect components on the builder entity and descendants
```

For each entity selected by that scope, the bake collector scans components and
invokes visitors for registered component types. `termin-navmesh` registers the
built-in mesh visitor for `MeshComponent`; `MeshComponent` itself does not know
about navmesh. Other sources, such as ledge ribbons, must register their own
geometry/link visitors during their module bootstrap.

## Area Ownership

The builder must preserve area ids per triangle or per geometry batch.

Current Detour output that paints all Recast polygons with one builder area id
is not enough for ledges. The generated ribbon must remain distinguishable from
ordinary walkable geometry after Recast/Detour build.

Target requirement:

```text
NavMeshGeometryInput
  vertices
  triangles
  triangle_area_ids or batch_area_id
```

The Recast pipeline should rasterize triangles with their provided area ids and
the Detour tile build should pass through `pmesh->areas` instead of replacing
all non-null polygons with a single global area.

## Stable Off-Mesh Identity

ChronoSquad currently often resolves off-mesh links through Detour user ids and
scene entities. Ordering-based ids are fragile.

The visitor-based sink should make stable source identity explicit:

```text
OffMeshLinkRecord
  source entity/component
  stable local id
  Detour user id
```

At query time, ChronoSquad needs to recover the source ledge/access record in
order to compute or read `BracedCoordinates`. This should not depend on scene
iteration order.

## Path Query Result Expectations

Termin/Detour should return enough information for project code to classify
path segments by area and off-mesh source.

ChronoSquad then owns semantic conversion:

```text
Detour point on LEDGE_AREA
  -> BRACED_HANG path segment

off-mesh ledge enter from bottom
  -> DOWN_TO_BRACED

off-mesh ledge exit to top
  -> BRACED_TO_UP

off-mesh ledge drop
  -> JUMP_DOWN
```

The Termin navmesh layer should not know ChronoCore animation names or
`BracedCoordinates` semantics. It should only preserve area/source metadata.

## Non-Goals

- Do not hack Detour first to support true one-dimensional path primitives.
  Synthetic ribbon geometry is less invasive and fits Detour's polygon model.
- Do not add pathfinding methods to `MeshComponent`.
- Do not create hidden render mesh entities just so Recast can see ledges.
  Ledge debug drawing can exist, but navmesh bake input should be generated
  directly through the visitor.
- Do not hard-code ChronoSquad ledge concepts in generic Termin navmesh code.
- Do not normalize broad fallbacks. If a component claims it can provide
  navmesh input but produces invalid data, log a concrete error.

## Implementation Shape

A sensible first implementation pass:

1. Add navmesh bake input structs and visitor registry inside `termin-navmesh`.
2. Replace the builder's hard-coded mesh/off-mesh collection with registry
   collection.
3. Add a built-in `MeshComponent` geometry visitor registered by navmesh.
4. Convert `OffMeshLinkComponent` collection into a built-in link visitor.
5. Preserve per-triangle or per-batch area ids through Recast and Detour tile
   build.
6. Add tests for mixed geometry areas and visitor collection.
7. Let ChronoSquad add `LedgeComponent` and its visitors in a separate module.

ChronoSquad-side follow-up:

1. Implement the ledge authoring component and editor point-placement tool.
2. Generate ribbon triangles from ledge polylines.
3. Generate access off-mesh links from explicit access records.
4. Extend path conversion to map `LEDGE_AREA` and ledge link metadata into
   ChronoCore semantic path points.
5. Add debug visualization for authored ledges, generated ribbon, and access
   links.

## Risks And Open Questions

- Recast area propagation needs auditing. The current builder path likely
  collapses areas too aggressively.
- Detour path results may need area ids for ordinary points, not just off-mesh
  user ids.
- Multi-agent support should be part of the visitor context from the start.
  Different agents may need different ribbon widths or may be disallowed.
- Generated ledge ribbon may need special cost tuning so walking and climbing
  routes compare sensibly.
- Moving platforms/frames need a clear bake-space story. The visitor context
  should make builder frame conversion explicit and not rely on global
  coordinates.
- Python-authored components may need a C vtable/ops layer later. A C++ visitor
  registry is enough for the first step, but the design should not block C/Python
  visitors.

## Summary

The target is a generic Termin navmesh bake-source visitor system. It lets the
builder consume ordinary mesh geometry, synthetic procedural geometry, and
off-mesh links without making unrelated components depend on pathfinding.

ChronoSquad ledges are the motivating case: explicit authored ledge polylines
produce synthetic ribbon navmesh plus access links, Detour solves path topology,
and ChronoSquad converts the resulting areas/links into its existing braced
movement semantics.
