# termin-voxels

`termin-voxels` owns the voxel grid runtime API, serialization,
voxelization helpers, mesh conversion helpers, shader helper and
`termin.voxels._voxels_native`.

Native package ownership:
- `termin_voxels` - C registry for `TcVoxelGrid` runtime resources.
- `termin.voxels._voxels_native` - Python bindings for voxelization helpers,
  native voxel data types, and `TcVoxelGrid`.

`TcVoxelGrid` is the canonical runtime identity for voxel-grid resources
(`uuid`, `name`, `source_path`, `version`) and owns the native `VoxelGrid`
payload through the core registry. `VoxelGridHandle` is only a compatibility
alias for `TcVoxelGrid`, matching the `TcMeshHandle = TcMesh` pattern.

Scene/render components are shipped by `termin-components-voxels` under the
separate `termin_voxel_components` package. `termin.voxels` keeps lazy
top-level re-exports for the component classes, but the component package does
not install modules inside the core `termin.voxels` namespace.

Voxel-grid asset adapters live in `termin-default-assets` under
`termin.default_assets.voxels`.

Compatibility status:
- Domain compatibility re-exports `termin.voxels.asset` and
  `termin.voxels.asset_plugin` were removed. Use
  `termin.default_assets.voxels.*` directly.
- App compatibility modules `termin.assets.voxel_grid_asset` and
  `termin.assets.voxel_grid_plugin` were removed. Use
  `termin.default_assets.voxels.*` directly.
