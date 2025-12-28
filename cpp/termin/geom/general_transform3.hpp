#pragma once

#include <cstdint>
#include "general_pose3.hpp"
#include "../../../core_c/include/tc_entity_pool.h"

// DLL export/import macros for Windows
#ifdef _WIN32
    #ifdef ENTITY_LIB_EXPORTS
        #define ENTITY_API __declspec(dllexport)
    #else
        #define ENTITY_API __declspec(dllimport)
    #endif
#else
    #define ENTITY_API
#endif

namespace termin {

class Entity;

// Transform view into entity pool data.
// Same pool + id as Entity, but provides transform-specific methods.
// Entity.transform() and GeneralTransform3.entity() create each other on the fly.
struct GeneralTransform3 {
    tc_entity_pool* _pool = nullptr;
    tc_entity_id _id = TC_ENTITY_ID_INVALID;

    // Default constructor - invalid transform
    GeneralTransform3() = default;

    // Construct from pool + id
    GeneralTransform3(tc_entity_pool* pool, tc_entity_id id) : _pool(pool), _id(id) {}

    // Check if valid
    bool valid() const { return _pool && tc_entity_pool_alive(_pool, _id); }
    explicit operator bool() const { return valid(); }

    // --- Pose accessors ---

    GeneralPose3 local_pose() const {
        GeneralPose3 pose;
        double pos[3], rot[4], scale[3];
        tc_entity_pool_get_local_position(_pool, _id, pos);
        tc_entity_pool_get_local_rotation(_pool, _id, rot);
        tc_entity_pool_get_local_scale(_pool, _id, scale);
        pose.lin = Vec3{pos[0], pos[1], pos[2]};
        pose.ang = Quat{rot[0], rot[1], rot[2], rot[3]};
        pose.scale = Vec3{scale[0], scale[1], scale[2]};
        return pose;
    }

    void set_local_pose(const GeneralPose3& pose) {
        double pos[3] = {pose.lin.x, pose.lin.y, pose.lin.z};
        double rot[4] = {pose.ang.x, pose.ang.y, pose.ang.z, pose.ang.w};
        double scale[3] = {pose.scale.x, pose.scale.y, pose.scale.z};
        tc_entity_pool_set_local_position(_pool, _id, pos);
        tc_entity_pool_set_local_rotation(_pool, _id, rot);
        tc_entity_pool_set_local_scale(_pool, _id, scale);
    }

    void relocate(const GeneralPose3& pose) {
        set_local_pose(pose);
    }

    void relocate(const Pose3& pose) {
        GeneralPose3 gp = local_pose();
        gp.ang = pose.ang;
        gp.lin = pose.lin;
        set_local_pose(gp);
    }

    GeneralPose3 global_pose() const {
        // TODO: need to ensure transforms are updated first
        // For now, trigger update and get world data
        GeneralPose3 pose;
        double pos[3];
        tc_entity_pool_get_world_position(_pool, _id, pos);
        pose.lin = Vec3{pos[0], pos[1], pos[2]};
        // TODO: world rotation and scale not yet exposed in pool API
        // For now, return local as approximation
        double rot[4], scale[3];
        tc_entity_pool_get_local_rotation(_pool, _id, rot);
        tc_entity_pool_get_local_scale(_pool, _id, scale);
        pose.ang = Quat{rot[0], rot[1], rot[2], rot[3]};
        pose.scale = Vec3{scale[0], scale[1], scale[2]};
        return pose;
    }

    void set_global_pose(const GeneralPose3& pose) {
        // TODO: proper global-to-local conversion with parent
        set_local_pose(pose);
    }

    void relocate_global(const GeneralPose3& gpose) {
        set_global_pose(gpose);
    }

    void relocate_global(const Pose3& pose) {
        Vec3 current_scale = global_pose().scale;
        GeneralPose3 gp(pose.ang, pose.lin, current_scale);
        set_global_pose(gp);
    }

    // --- Hierarchy ---

    GeneralTransform3 parent() const {
        tc_entity_id parent_id = tc_entity_pool_parent(_pool, _id);
        if (!tc_entity_id_valid(parent_id)) return GeneralTransform3();
        return GeneralTransform3(_pool, parent_id);
    }

    void set_parent(GeneralTransform3 new_parent) {
        tc_entity_pool_set_parent(_pool, _id, new_parent._id);
    }

    void unparent() {
        tc_entity_pool_set_parent(_pool, _id, TC_ENTITY_ID_INVALID);
    }

    size_t children_count() const {
        return tc_entity_pool_children_count(_pool, _id);
    }

    GeneralTransform3 child_at(size_t index) const {
        tc_entity_id child_id = tc_entity_pool_child_at(_pool, _id, index);
        if (!tc_entity_id_valid(child_id)) return GeneralTransform3();
        return GeneralTransform3(_pool, child_id);
    }

    // --- Entity (creates Entity view on same data) ---

    ENTITY_API Entity entity() const;

    // --- Name (from entity) ---

    const char* name() const {
        return tc_entity_pool_name(_pool, _id);
    }

    // --- Dirty tracking ---

    void mark_dirty() {
        tc_entity_pool_mark_dirty(_pool, _id);
    }

    // --- Transformations ---

    Vec3 transform_point(const Vec3& p) const {
        return global_pose().transform_point(p);
    }

    Vec3 transform_point_inverse(const Vec3& p) const {
        return global_pose().inverse_transform_point(p);
    }

    Vec3 transform_vector(const Vec3& v) const {
        return global_pose().transform_vector(v);
    }

    Vec3 transform_vector_inverse(const Vec3& v) const {
        return global_pose().inverse_transform_vector(v);
    }

    // --- Direction helpers (Y-forward convention) ---

    Vec3 forward(double distance = 1.0) const {
        return transform_vector(Vec3{0.0, distance, 0.0});
    }

    Vec3 backward(double distance = 1.0) const {
        return transform_vector(Vec3{0.0, -distance, 0.0});
    }

    Vec3 up(double distance = 1.0) const {
        return transform_vector(Vec3{0.0, 0.0, distance});
    }

    Vec3 down(double distance = 1.0) const {
        return transform_vector(Vec3{0.0, 0.0, -distance});
    }

    Vec3 right(double distance = 1.0) const {
        return transform_vector(Vec3{distance, 0.0, 0.0});
    }

    Vec3 left(double distance = 1.0) const {
        return transform_vector(Vec3{-distance, 0.0, 0.0});
    }

    // --- Matrix ---

    void world_matrix(double* m) const {
        tc_entity_pool_get_world_matrix(_pool, _id, m);
    }

    // --- Pool/ID access ---

    tc_entity_pool* pool() const { return _pool; }
    tc_entity_id id() const { return _id; }
};

} // namespace termin
