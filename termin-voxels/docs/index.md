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
`termin.default_assets.voxels`. Old `termin.voxels.asset`,
`termin.voxels.asset_plugin`, `termin.assets.voxel_grid_asset`, and
`termin.assets.voxel_grid_plugin` paths remain compatibility re-exports.
