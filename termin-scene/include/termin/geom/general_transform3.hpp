#pragma once

#include <cstddef>
#include <cstdint>
#include <termin/geom/general_pose3.hpp>
#include "core/tc_entity_pool.h"
#include <termin/export.hpp>

namespace termin {

class Entity;

// Transform view into entity pool data. Uses an entity handle for safe access.
struct ENTITY_API GeneralTransform3 {
    tc_entity_handle _h = TC_ENTITY_HANDLE_INVALID;

    GeneralTransform3() = default;
    GeneralTransform3(tc_entity_handle h) : _h(h) {}
    GeneralTransform3(tc_entity_pool_handle pool_handle, tc_entity_id id)
        : _h(tc_entity_handle_make(pool_handle, id)) {}
    GeneralTransform3(tc_entity_pool* pool, tc_entity_id id);

    tc_entity_pool* pool_ptr() const;
    bool valid() const;
    explicit operator bool() const { return valid(); }

    GeneralPose3 local_pose() const;
    void set_local_pose(const GeneralPose3& pose);
    Vec3 local_position() const;
    void set_local_position(const Vec3& p);
    Quat local_rotation() const;
    void set_local_rotation(const Quat& q);
    Vec3 local_scale() const;
    void set_local_scale(const Vec3& s);
    Vec3 global_position() const;
    Quat global_rotation() const;
    Vec3 global_scale() const;
    void relocate(const GeneralPose3& pose);
    void relocate(const Pose3& pose);
    GeneralPose3 global_pose() const;
    void set_global_pose(const GeneralPose3& gpose);
    void relocate_global(const GeneralPose3& gpose);
    void relocate_global(const Pose3& pose);

    GeneralTransform3 parent() const;
    void set_parent(GeneralTransform3 new_parent);
    void unparent();
    size_t children_count() const;
    GeneralTransform3 child_at(size_t index) const;

    ENTITY_API Entity entity() const;
    const char* name() const;
    void mark_dirty();

    Vec3 transform_point(const Vec3& p) const;
    Vec3 transform_point_inverse(const Vec3& p) const;
    Vec3 transform_vector(const Vec3& v) const;
    Vec3 transform_vector_inverse(const Vec3& v) const;
    Vec3 transform_direction(const Vec3& d) const;
    Vec3 transform_direction_inverse(const Vec3& d) const;
    Vec3 forward(double distance = 1.0) const;
    Vec3 backward(double distance = 1.0) const;
    Vec3 up(double distance = 1.0) const;
    Vec3 down(double distance = 1.0) const;
    Vec3 right(double distance = 1.0) const;
    Vec3 left(double distance = 1.0) const;
    void world_matrix(double* m) const;

    tc_entity_handle handle() const { return _h; }
    tc_entity_pool* pool() const { return pool_ptr(); }
    tc_entity_pool_handle pool_handle() const { return _h.pool; }
    tc_entity_id id() const { return _h.id; }
};

} // namespace termin
