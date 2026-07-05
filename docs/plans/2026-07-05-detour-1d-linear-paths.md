# Detour 1D Linear Paths

Date: 2026-07-05
Context: ChronoSquad ledge/climbing navigation in Termin

## Status

Preparation plan for adding first-class one-dimensional navigation primitives
to the bundled Detour fork.

This supersedes the ribbon part of
`2026-07-05-navmesh-bake-visitors-ledge-ribbon.md`. The bake visitor registry
from that plan remains useful: project code still needs a way to provide
explicit ledge/polyline data to the generic navmesh bake pipeline. The failed
part is representing a ledge as a synthetic narrow Recast surface.

## Problem

Ledges are continuous one-dimensional navigation spaces:

- an actor can enter at several access points;
- move along the ledge;
- leave at another access point;
- keep semantic movement state such as braced/hanging/climbing while doing so.

Off-mesh links alone model only point-to-point transitions. Ribbon meshes try to
force the ledge into Detour's polygon funnel model and inherit Recast's surface
assumptions. The result is fragile topology, awkward nearest-point behavior, and
path output that still needs heavy semantic repair.

The correct target is a Detour navigation graph that can contain both:

- ordinary 2D convex ground polygons;
- off-mesh transition polygons;
- explicit 1D linear segment polygons.

## Detour Representation

Add a new polygon type:

```cpp
enum dtPolyTypes
{
    DT_POLYTYPE_GROUND = 0,
    DT_POLYTYPE_OFFMESH_CONNECTION = 1,
    DT_POLYTYPE_LINEAR = 2,
};
```

`dtPoly::areaAndtype` already stores the type in the upper two bits, so the
current layout has room for two additional types. No `dtPolyRef` format change
is required: a linear segment is still addressed as a normal tile/poly ref.

A linear segment is stored as a `dtPoly` with:

- `vertCount = 2`;
- `verts[0]` and `verts[1]` pointing to the segment endpoints;
- `flags` and `area` using the existing Detour filter/cost path;
- `type = DT_POLYTYPE_LINEAR`.

The segment is not an off-mesh connection. It is a traversable graph node with
continuous positions along its own segment.

## Tile Metadata

Add an explicit metadata array for linear segments:

```cpp
struct dtLinearSegment
{
    unsigned short poly;
    unsigned int userId;
    unsigned short flags;
    unsigned short reserved;
};
```

The endpoint positions remain in `dtMeshTile::verts` through the owning `dtPoly`.
The metadata exists for stable source recovery and future per-segment options,
not for geometry duplication.

Extend `dtMeshHeader` and `dtMeshTile`:

```cpp
int linearSegmentCount;
int linearSegmentBase;
dtLinearSegment* linearSegments;
```

`linearSegmentBase` is the first polygon index occupied by linear segment polys,
similar to `offMeshBase`. Tile polygon order should be:

```text
ground polys
linear segment polys
off-mesh connection polys
```

So:

```cpp
linearSegmentBase = params->polyCount;
offMeshBase = params->polyCount + storedLinearSegmentCount;
```

Bump `DT_NAVMESH_VERSION`, because the binary tile layout changes and old baked
blobs should fail loudly during active development.

## Explicit Linear Links

Do not rely on geometric guessing inside Detour to discover linear topology.
Store explicit linear adjacency records in the tile data and rebuild `dtLink`
chains when the tile is loaded:

```cpp
struct dtLinearLink
{
    unsigned short fromPoly;
    unsigned short toPoly;
    unsigned short fromT; // 0..65535 along from segment
    unsigned short toT;   // 0..65535 along to segment
    unsigned char flags;
    unsigned char reserved[3];
};
```

For a simple polyline, the Termin builder emits links between consecutive
segments at their shared endpoints. The same representation also supports
branches and midpoint joins later.

`dtLink::edge` can keep a compact runtime hint for which endpoint/t-value owns
the link, but the persistent source of truth is the `dtLinearLink` array. This
avoids overloading `dtPoly::neis` with a graph that is not polygon-edge
adjacency.

Access between ground and a ledge should remain an explicit transition. The
first implementation can use existing off-mesh connection polygons for
ground-to-linear and linear-to-ground access, provided nearest-poly lookup can
return `DT_POLYTYPE_LINEAR` when an endpoint is snapped to a ledge segment.

## Builder API

Extend `dtNavMeshCreateParams` with linear path input:

```cpp
const float* linearSegmentVerts;          // [(ax,ay,az,bx,by,bz) * count]
const unsigned short* linearSegmentFlags; // [count]
const unsigned char* linearSegmentAreas;  // [count]
const unsigned int* linearSegmentUserID;  // [count], optional
int linearSegmentCount;

const dtLinearLink* linearLinks;          // [linearLinkCount]
int linearLinkCount;
```

Termin wraps this as a C++ data struct next to `DetourOffMeshLinkData`:

```cpp
struct DetourLinearPathData {
    std::vector<float> segment_verts;
    std::vector<unsigned char> areas;
    std::vector<unsigned short> flags;
    std::vector<unsigned int> user_ids;
    std::vector<DetourLinearLinkData> links;
};
```

The Recast step still produces only ground polygons. Linear path data is
appended directly during `dtCreateNavMeshData`, the same stage that appends
off-mesh connection polygons today.

## Query Semantics

The A* core can stay mostly graph-based because `findPath` already expands
`dtLink` chains. The type-specific work is in positions, costs, nearest points,
and straight path generation.

Required linear behavior:

- `closestPointOnPoly` clamps to the segment and sets `posOverPoly = true` only
  when the projected point is within linear snap tolerance.
- `getPolyHeight` interpolates endpoint height along the segment.
- `findNearestPoly` and tile BV queries include linear segment AABBs.
- `getEdgeMidPoint` uses the link t-values for linear links instead of polygon
  edge portals.
- `getPortalPoints` returns point portals for off-mesh/linear transitions and
  should not pretend a 1D segment has a polygon-width portal.
- `findStraightPath` detects corridors containing linear polys and emits an
  ordered point path through linear entry/exit positions rather than running the
  funnel across degenerate portals.

The first implementation should focus on:

- `findNearestPoly`;
- `closestPointOnPoly`;
- `findPath`;
- `findStraightPath`;
- `getPolyHeight`.

Other APIs such as `raycast`, `moveAlongSurface`, random point queries, and
local-neighbourhood queries should either explicitly skip linear polys or return
`DT_FAILURE | DT_INVALID_PARAM` for unsupported linear starts until they get
deliberate semantics.

## Straight Path Output

Add a straight-path flag for linear traversal:

```cpp
DT_STRAIGHTPATH_LINEAR = 0x08
```

Termin path points should expose:

- Detour poly type;
- area id;
- linear user id when the point belongs to `DT_POLYTYPE_LINEAR`;
- off-mesh user id when the point belongs to `DT_POLYTYPE_OFFMESH_CONNECTION`.

ChronoSquad can then map linear points back to ledge segment/t and produce
braced coordinates without guessing from ribbon area polygons.

## File Touch Points

Detour core:

- `DetourNavMesh.h`: add poly type, tile/header fields, `dtLinearSegment`,
  `dtLinearLink`, straight-path flag.
- `DetourNavMeshBuilder.h`: add create params for linear segments and links.
- `DetourNavMeshBuilder.cpp`: append linear verts/polys/metadata/link metadata,
  count link capacity, include line AABBs in BV tree and off-mesh endpoint
  classification bounds, endian swap new data.
- `DetourNavMesh.cpp`: parse new tile sections, reset pointers on remove,
  connect linear links on load, handle nearest point and height.
- `DetourNavMeshQuery.cpp`: add linear-aware closest boundary, portal/midpoint,
  path cost positions, and straight-path emission.

Termin integration:

- `termin-navmesh/include/termin/navmesh/detour_navmesh_build.hpp`: add
  `DetourLinearPathData`.
- `termin-navmesh/src/detour_navmesh_build.cpp`: pass linear data into
  `dtNavMeshCreateParams`.
- `termin-navmesh/include/termin/navmesh/navmesh_bake_source.hpp`: add a linear
  path sink/source record to the visitor-collected bake input.
- `termin-navmesh/src/navmesh_bake_source.cpp`: collect registered linear path
  providers.
- `termin-navmesh/src/recast_navmesh_builder_component.cpp`: carry linear data
  from bake input to Detour build.
- `termin-navmesh/src/detour_query_session.cpp`: expose/log poly type and linear
  user id in detailed path results.
- `termin-navmesh/python/bindings/navmesh_module.cpp`: expose linear path fields
  and detailed path metadata.

## First Test Slice

Start with a low-level Detour test before touching project-specific ledge code:

1. Build a single-tile navmesh with one normal ground polygon.
2. Append one linear segment as `DT_POLYTYPE_LINEAR`.
3. Add two off-mesh access transitions between the ground polygon and two
   points on the segment.
4. Query ground point to ledge point and ledge point to ground point.
5. Assert that:
   - nearest-poly can select the linear segment;
   - the corridor includes the linear poly;
   - straight path contains a `DT_STRAIGHTPATH_LINEAR` point;
   - Termin detailed path exposes the linear user id and area.

Only after that should Termin bake visitors grow project-facing linear path
sources.

## Risks

- The funnel is the biggest trap. Degenerate portals must not be allowed to pass
  through the existing polygon funnel as if they were narrow surfaces.
- BV tree generation currently counts only Recast polys. If linear AABBs are not
  indexed, starts and ends placed directly on a ledge will fail nearest-poly
  lookup.
- Existing off-mesh connection code assumes land polygons are ordinary surfaces.
  It needs tests where an off-mesh endpoint lands on a linear segment.
- Off-mesh endpoint classification currently derives height bounds from the
  Recast mesh/detail mesh. Linear segment bounds must participate, otherwise
  access links to ledges above or below the ground mesh can be discarded before
  linking.
- Tile serialization changes affect every baked navmesh asset. Version bump and
  loud load failure are preferred over compatibility shims during this migration.
- Detour is third-party code in-tree. Keep changes narrow, documented, and
  covered by tests so future upstream merges are still understandable.

## Migration From Ribbon Plan

Keep:

- bake visitor registry;
- explicit project-owned ledge/polyline data;
- stable user ids and source metadata;
- off-mesh access records for enter/exit/drop transitions.

Drop:

- synthetic ribbon triangles as the primary ledge representation;
- Recast erosion/region tuning for ledge topology;
- area-only interpretation of ledge movement.

The target path is:

```text
Project LedgeComponent or equivalent
  -> navmesh bake visitor emits linear segments and access links
  -> Detour tile contains ground polys, linear polys, off-mesh transitions
  -> Detour query returns typed path points
  -> ChronoSquad maps linear user ids to braced coordinates
```
