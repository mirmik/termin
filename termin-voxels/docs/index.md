# termin-voxels

`termin-voxels` owns the voxel grid runtime API, serialization,
voxelization helpers, mesh conversion helpers, shader helper and
`termin.voxels._voxels_native`.

Native package ownership:
- `termin_voxels` - C registry for `TcVoxelGrid` runtime resources.
- `termin.voxels._voxels_native` - Python bindings for voxelization helpers,
  native voxel data types, `TcVoxelGrid`, and the compatibility
  `VoxelGridHandle`.

`TcVoxelGrid` is the canonical runtime identity for voxel-grid resources
(`uuid`, `name`, `source_path`, `version`). `VoxelGridHandle` remains as a
compatibility wrapper for editor/component paths that still need the legacy
Python `termin.voxels.grid.VoxelGrid` payload from `VoxelGridAsset`.

Scene/render components are shipped by `termin-components-voxels` under the
same import namespace (`termin.voxels.display_component`,
`termin.voxels.voxelizer_component`, etc.). The core package keeps
`termin.voxels` extensible so those component modules can be installed
separately.

Voxel-grid asset adapters live in `termin-default-assets` under
`termin.default_assets.voxels`.

Compatibility status:
- `termin.voxels.asset` and `termin.voxels.asset_plugin` remain temporary
  domain compatibility re-exports.
- App compatibility modules `termin.assets.voxel_grid_asset` and
  `termin.assets.voxel_grid_plugin` were removed. Use
  `termin.default_assets.voxels.*` directly.
