# termin-voxels

`termin-voxels` owns the voxel grid runtime API, serialization,
voxelization helpers, mesh conversion helpers, shader helper and
`termin.voxels._voxels_native`.

Scene/render components are shipped by `termin-components-voxels` under the
same import namespace (`termin.voxels.display_component`,
`termin.voxels.voxelizer_component`, etc.). The core package keeps
`termin.voxels` extensible so those component modules can be installed
separately.

Voxel-grid asset adapters live in `termin-default-assets` under
`termin.default_assets.voxels`.

Compatibility status:
- `termin.voxels.asset`, `termin.voxels.asset_plugin`, and
  `termin.assets.voxel_grid_asset` remain temporary compatibility re-exports.
- `termin.assets.voxel_grid_plugin` was removed on 2026-06-18. Use
  `termin.default_assets.voxels.asset_plugin` directly.
