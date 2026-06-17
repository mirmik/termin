# termin-voxels

`termin-voxels` owns the voxel grid runtime API, serialization,
voxelization helpers, mesh conversion helpers, shader helper and
`termin.voxels._voxels_native`.

Scene/render components are shipped by `termin-components-voxels` under the
same import namespace (`termin.voxels.display_component`,
`termin.voxels.voxelizer_component`, etc.). The core package keeps
`termin.voxels` extensible so those component modules can be installed
separately.
