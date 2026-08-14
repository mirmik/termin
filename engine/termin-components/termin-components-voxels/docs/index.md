# termin-components-voxels

`termin-components-voxels` contains scene/render components for voxel grids:

- `termin_voxel_components.component.VoxelGridComponent`
- `termin_voxel_components.display_component.VoxelDisplayComponent`
- `termin_voxel_components.visualization.VoxelVisualizer`
- `termin_voxel_components.voxelizer_component.VoxelizerComponent`

The package depends on `termin-voxels` for voxel data and algorithms, on
`termin-navmesh` for its explicit navmesh build/debug integration, and on
scene/render/material packages for runtime component behavior. Shared contour
ribbon geometry is consumed through the public
`termin.navmesh.ribbon_geometry` module; component code must not import
private helpers from navmesh display components.
