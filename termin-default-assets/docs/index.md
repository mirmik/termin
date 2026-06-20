# termin-default-assets

Default asset adapters for Termin SDK.

This package owns the standard `termin-assets` integrations for domain data
packages. Domain packages such as `tmesh` should remain usable without the
project asset runtime.

Current adapters:

- `termin.default_assets.mesh`: `MeshAsset`, mesh import/runtime plugins,
  mesh import specs and OBJ/STL loaders.
- `termin.default_assets.navmesh`: `NavMeshAsset`, navmesh import/runtime
  plugins, and `NavMeshHandle` as a compatibility alias for `TcNavMesh`.
- `termin.default_assets.voxels`: `VoxelGridAsset`, voxel-grid import/runtime
  plugins.
- `termin.default_assets.audio`: `AudioClipAsset`, `AudioClipHandle`,
  audio-clip import/runtime plugins.
- `termin.default_assets.render`: texture, GLSL, material, shader, pipeline
  and scene-pipeline asset adapters/plugins plus render asset helper modules.
- `termin.default_assets.ui`: `UIAsset`, `UIHandle`, and UI import/runtime
  plugins for `.uiscript` layouts backed by `tcgui`.

Compatibility paths:

- `termin.default_assets.prefab`: compatibility re-exports for prefab classes
  that now live in `termin.prefab`.
