#pragma once

#include <termin/geom/general_pose3.hpp>
#include <termin/geom/pose3.hpp>
#include <termin/geom/vec3.hpp>
#include <termin/navmesh/termin_navmesh_components_api.hpp>

namespace termin {

inline Pose3 navmesh_bake_frame_from_pose(const GeneralPose3& base_pose) {
    return Pose3{base_pose.ang, base_pose.lin};
}

inline Vec3 navmesh_world_to_bake_point(const Pose3& bake_frame, const Vec3& world_point) {
    return bake_frame.inverse_transform_point(world_point);
}

inline Vec3 navmesh_bake_to_world_point(const Pose3& bake_frame, const Vec3& bake_point) {
    return bake_frame.transform_point(bake_point);
}

inline Vec3 navmesh_bake_to_world_vector(const Pose3& bake_frame, const Vec3& bake_vector) {
    return bake_frame.transform_vector(bake_vector);
}

inline Vec3f navmesh_world_to_bake_point(
    const Pose3& bake_frame,
    const Vec3f& world_point)
{
    const Vec3 bake = navmesh_world_to_bake_point(
        bake_frame,
        Vec3{world_point[0], world_point[1], world_point[2]});
    return {
        static_cast<float>(bake.x),
        static_cast<float>(bake.y),
        static_cast<float>(bake.z),
    };
}

inline Vec3f navmesh_bake_to_world_point(
    const Pose3& bake_frame,
    const Vec3f& bake_point)
{
    const Vec3 world = navmesh_bake_to_world_point(
        bake_frame,
        Vec3{bake_point[0], bake_point[1], bake_point[2]});
    return {
        static_cast<float>(world.x),
        static_cast<float>(world.y),
        static_cast<float>(world.z),
    };
}

inline Vec3f navmesh_bake_to_world_vector(
    const Pose3& bake_frame,
    const Vec3f& bake_vector)
{
    const Vec3 world = navmesh_bake_to_world_vector(
        bake_frame,
        Vec3{bake_vector[0], bake_vector[1], bake_vector[2]});
    return {
        static_cast<float>(world.x),
        static_cast<float>(world.y),
        static_cast<float>(world.z),
    };
}

} // namespace termin
