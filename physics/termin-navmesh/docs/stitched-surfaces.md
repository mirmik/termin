# Stitched navigation surfaces

Ordinary walking uses one graph of planar convex facets. Detour tiles remain
in their original bake frames; detail triangles provide the geometric surface.
Facet identity includes the surface instance, its runtime generation and original
Detour polygon reference. Linear and off-mesh polygons remain typed transitions.

## Boundary extension

A seam explicitly names two surface boundaries. Its declaration certifies that
the strip between these boundaries is supporting, obstacle-free geometry for the
baked agent. A distance threshold alone never declares a walkable connection.
The maximum extension is a length in metres, independently of query snap radius.
The author must exclude walls and missing floor from the declared interval.

For intersecting facet planes, extend both boundary polygons in their planes to
the plane-intersection line. For coincident planes, use the internal bisector of
the two supporting boundary lines: the line between them, equidistant from both.
For parallel boundary lines this is their midline. Only overlapping finite
intervals survive; separately baked boundary subdivisions and disconnected open
intervals remain separate portals. Tangential obstacle clearance is preserved.
Extensions become explicit convex facets, with the original surface identity,
so path reconstruction follows each side of the fold rather than a 3D chord.
Invalid, inward, excessive, or ambiguous extensions fail with a diagnostic.

## Queries and lifecycle

A* returns an ordered facet/portal corridor. Straightening develops only that
corridor into a plane and respects portal occurrence order even when the
development overlaps itself. Reconstructed paths include every crossed facet.
The selected graph corridor is approximate; global shortest geodesics over all
alternative corridors are not promised.

Resource replacement invalidates cached geometry even when its UUID is unchanged.
Common rigid motion preserves topology. Relative surface motion requires seam
revalidation. Scale changes require rebuilding the baked geometry.

Implementation and validation are tracked by #2515, #2516 and #2517. Public
PathfindingWorld uses this graph; the old point-link walking planner is removed.
Consumers must use each result span's supporting surface and normal instead of
inferring them again from proximity to an original, unextended bake boundary.

## Implementation and numerical checks

The straightener uses an ordered visibility graph of portal endpoint occurrences
in the developed corridor. A visible chord must cross every intervening portal
in sequence; coincident coordinates never merge different occurrences. Because
faces are convex, these chords stay within each traversed face. Bends occur at
portal endpoints. A direct visible route takes linear time; the general endpoint
DAG has cubic worst-case time. This deliberately handles overlap and vertex
cases without assuming the development is a simple planar polygon.

All geometry operations use double precision in a common surface-relative rigid
frame. Boundary matching uses 0.1 mm, the straightener uses 0.1 micrometre for
predicates and 1 micrometre for supporting-plane checks. Facets are detail
triangles or validated convex extension strips. Native Detour height steps are
represented by explicit risers limited by the baked walkable climb. Parallel
but offset planes and inward or excessive seam extensions are rejected.

Release measurement on this machine (2026-09-20), excluding fixture creation:
200 straight faces: 0.060 ms / 38 allocations / 65,448 allocated bytes;
1,000 straight faces: 0.303 ms / 46 allocations / 262,056 bytes;
64 faces with seven hairpins: 0.232 ms / 64 allocations / 26,912 bytes;
96 overlapping fan faces: 0.179 ms / 39 allocations / 35,808 bytes.
These are observations, not performance thresholds. Tests print current values.
Actual RingStation assets: initial graph plus first query approximately 35 ms;
130 requests approximately 0.7 ms average including that initial build.

Component query extents still bound endpoint snapping. The unified graph uses
its own dynamically sized corridor rather than local Detour fixed-buffer limits.
`navmesh_precast` is retained in the public options for source compatibility;
both settings snap endpoints to the same unified navigable geometry.

## Per-query traversal policy

`PathfindingWorldQueryOptions::traversal` is a `SurfaceTraversalPolicy`:
`area_mask` permits any of the 64 Detour areas, and `area_costs[area]` gives
relative travel time per unit distance. Defaults permit all areas at cost 1,
preserving existing callers. All costs must be finite and strictly positive;
invalid policies fail with an error log. A zero mask permits no endpoints.
The policy is also an optional last argument of `find_surface_corridor`.

Endpoint support is selected geometrically within existing query extents before
permissions are checked. If the nearest surface is excluded, the query fails:
a click on an unclimbable wall is never redirected onto a farther floor.
Excluded intermediate faces are never expanded; an unreachable permitted goal
can still return the existing partial corridor on permitted faces.

A* weights each center-to-portal half-edge by its face's area cost; its distance
heuristic is scaled by the minimum permitted cost (including values below 1).
This chooses a corridor using the existing center/portal approximation, not an
exact global minimum-time path. Straightening remains geometric inside the
selected corridor; it does not solve refraction at unequal-cost boundaries.
Traversal policy does not enter the geometry cache or mutate shared surfaces.

Python exposes `SurfaceTraversalPolicy` and the optional `traversal=` argument of
`PathfindingWorld.find_detailed_path_world`. `area_costs` is a copied 64-element
sequence: assign the modified sequence back to the property after editing it.
