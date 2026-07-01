#pragma once

#include <termin/entity/entity.hpp>
#include <termin/geom/pose3.hpp>

namespace termin {

inline Mat44 recast_navmesh_builder_frame_inverse(Entity builder_entity) {
    GeneralPose3 base_pose = builder_entity.transform().global_pose();
    Pose3 base_frame{base_pose.ang, base_pose.lin};
    return base_frame.inverse().as_mat44();
}

} // namespace termin
