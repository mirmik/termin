# Links between navigation surfaces

`WorldNavMeshLinkComponent` connects two independently baked Detour surfaces with
an explicit walkable seam. It is a runtime component; it is not baked into either
asset and does not use off-mesh gameplay actions such as jumping or climbing.

Fields:

- `start_surface`, `end_surface`: entity references owning Detour components.
- `start_local`, `end_local`: endpoint coordinates **local to the respective
  surface entity**, not to the entity carrying the link.
- `snap_radius`: maximum world distance from each endpoint to its surface (0.5).
- `bidirectional`: allow the reverse crossing (true).

Normal component/entity enabled state applies. Live endpoint and bake transforms
are read for every query, so a common parent can rotate or translate without
rebaking. An endpoint uses the closest enabled Detour component on its referenced
entity; equally close components are ambiguous and the link is rejected with a
warning. Missing surfaces and endpoints outside the snap radius are also rejected.
The author is responsible for placing the explicit seam over traversable geometry;
this component does not invent connections between nearby surfaces.

`PathfindingWorld.find_detailed_path_world` finds nearest physical start/end
surfaces and routes over seam endpoints. Dijkstra weights include actual Detour
path lengths. Directed intra-surface legs are cached for the query; partial legs
cannot connect seams. A complete linked route takes priority over the historical
single-surface result. If no complete route exists, the historical partial path
may still be returned; a projection onto a more distant origin or destination surface is
marked partial. Worlds without these links retain their existing query behavior.

The result's `path` is a concatenated world-space polyline; seam points are ordinary
walk points. `candidate` remains the initial surface for compatibility. `spans`
identifies each leg by `entity`, `component`, `bake_frame`, and inclusive
`point_begin`/`point_end` indices. A seam span belongs to its starting surface;
the following intra-surface span belongs to the destination surface. Poly refs
are local to their span's Detour mesh, not globally unique. Consumers must use the
spans when assigning reference frames to a route crossing different moving roots.
