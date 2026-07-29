#pragma once

#include <termin/entity/entity.hpp>
#include <termin/navmesh/navmesh_query_space.hpp>

namespace termin {

inline Mat44 recast_navmesh_builder_frame_inverse(Entity builder_entity) {
    Pose3 base_frame =
        navmesh_bake_frame_from_transform(builder_entity.transform());
    return base_frame.inverse().as_mat44();
}

} // namespace termin
