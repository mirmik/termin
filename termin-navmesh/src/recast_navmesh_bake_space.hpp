#pragma once

#include <termin/entity/entity.hpp>
#include <termin/navmesh/navmesh_query_space.hpp>

namespace termin {

inline Mat44 recast_navmesh_builder_frame_inverse(Entity builder_entity) {
    GeneralPose3 base_pose = builder_entity.transform().global_pose();
    Pose3 base_frame = navmesh_bake_frame_from_pose(base_pose);
    return base_frame.inverse().as_mat44();
}

} // namespace termin
