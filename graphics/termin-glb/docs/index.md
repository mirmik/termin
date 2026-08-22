# termin-glb

`termin-glb` owns portable GLB/glTF decoding and runtime resource publication.

The package contains:

- `termin.glb.loader` for parsing `.glb` and JSON `.gltf` files into GLB scene
  data.
- `termin.glb.native` for compact cgltf-backed discovery and transactional
  mesh, skeleton and animation publication.
- `termin.glb.extractor` for editor/tooling extraction of meshes, textures, and
  animations.

The wheel has no dependency on `termin-assets`, scene/ECS, default assets or
engine components. `termin-glb-adapters` owns `GLBAsset`, resource plugins,
Entity instantiation and serialized-scene repair for Termin consumers.

## Native importer migration

The accepted [Native cgltf Importer decision](../../../docs/architecture-council/2026-08-09-native-cgltf-importer.md)
defines the migration of the heavy GLB data path to a pinned cgltf backend.
The runtime asset contract remains sequential: native parsing and CPU resource
preparation are followed by deterministic publication into declared embedded
resources. This migration does not add concurrent `Asset.ensure_loaded()`.

The explicit `NativeGLBDocument` backend keeps mapped GLB storage alive while
cgltf accessors refer to it, publishes static and skinned Termin meshes without
Python per-index processing, and exposes encoded images, materials, nodes,
skins, and exact animation tensors through compact discovery/bulk boundaries.
`GLBAsset` now selects this backend by default for binary `.glb` sources; JSON
`.gltf` sources use the portable Python decoder. Both paths publish the same
exact animation-track contract, preserving source node indices, interpolation,
non-uniform vec3 scale, morph weights, and full CUBICSPLINE tuples.

The pinned dependency revision and fork policy are documented in
[`native-cgltf.md`](native-cgltf.md).
