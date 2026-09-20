# Navigation surface seams

Ordinary walking across baked surfaces uses `WorldNavMeshSeamComponent` and the
unified polygon graph. See [the geometry contract](docs/stitched-surfaces.md).

Each declaration names `start_surface` and `end_surface`, plus finite boundary
segments `start_a`/`start_b` and `end_a`/`end_b` in the respective entity's local
coordinates. `max_extension` limits the permitted boundary continuation in metres;
`bidirectional` controls traversal direction. Declaration intervals certify the
supporting, obstacle-free strip for the baked agent. Exposed baked boundary
intervals retain tangential obstacle clearance.

Intersecting planes meet on their intersection line. Coincident planes meet on
the internal bisector of their boundary lines (the midline for parallel edges).
Explicit extension facets connect the old boundaries to this common edge.

`PathfindingWorld.find_detailed_path_world` uses the same graph for a single flat
surface and stitched folded surfaces. It returns complete or partial paths with
all facet crossings, typed linear/off-mesh metadata and surface-owned spans.
Each span's indices are inclusive and neighbouring spans share their crossing
point. Spans carry `poly_ref`, `generation` and world-space supporting `normal`;
poly refs are scoped to the span's mesh. Point metadata describes the outgoing
segment, so off-mesh actions are emitted only at their departure point.

Common rigid motion reuses topology. Relative surface motion and changed asset
versions rebuild the graph. Unsupported seams emit a diagnostic and remain
unconnected; there is no point-link fallback.

`WorldNavMeshLinkComponent` is retained only to identify obsolete scene data with
a diagnostic. Its former point-to-point walking planner has been removed. Replace
these declarations with finite boundary seams. Gameplay off-mesh actions remain
separate typed transitions.
