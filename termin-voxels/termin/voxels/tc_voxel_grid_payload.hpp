#pragma once

#include "termin/voxels/tc_voxel_grid_registry.h"
#include "termin/voxels/voxel_grid.hpp"

namespace termin {
namespace voxels {

TERMIN_VOXELS_API VoxelGrid* tc_voxel_grid_payload(tc_voxel_grid_handle h);
TERMIN_VOXELS_API const VoxelGrid* tc_voxel_grid_payload_const(tc_voxel_grid_handle h);
TERMIN_VOXELS_API bool tc_voxel_grid_set_payload_copy(tc_voxel_grid_handle h, const VoxelGrid& payload);
TERMIN_VOXELS_API bool tc_voxel_grid_clear_payload(tc_voxel_grid_handle h);

} // namespace voxels
} // namespace termin
