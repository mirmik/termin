#pragma once

#include <cstdint>
#include <stdexcept>
#include "general_pose3.hpp"
#include "core/tc_entity_pool.h"
#include "core/tc_entity_pool_registry.h"

#include "../export.hpp"
#include <tcbase/tc_log.hpp>

namespace termin {

class Entity;

// Transform view into entity pool data.
// Uses entity handle for safe access - pool may be destroyed.
// Entity.transform() and GeneralTransform3.entity() create each other on the fly.
struct GeneralTransform3 {
    tc_entity_handle _h = TC_ENTITY_HANDLE_INVALID;

    // Default constructor - invalid transform
    GeneralTransform3() = default;

    // Construct from entity handle
    GeneralTransform3(tc_entity_handle h) : _h(h) {}

    // Construct from pool handle + id
    GeneralTransform3(tc_entity_pool_handle pool_handle, tc_entity_id id)
        : _h(tc_entity_handle_make(pool_handle, id)) {}

    // Legacy: Construct from pool pointer + id
    GeneralTransform3(tc_entity_pool* pool, tc_entity_id id) {
        tc_entity_pool_handle pool_h = tc_entity_pool_registry_find(pool);
        _h = tc_entity_handle_make(pool_h, id);
    }

    // Get pool pointer (may be NULL if pool destroyed)
    tc_entity_pool* pool_ptr() const {
        return tc_entity_pool_registry_get(_h.pool);
    }

    // Check if valid
    bool valid() const {
        return tc_entity_handle_valid(_h);
    }
    explicit operator bool() const { return valid(); }

    // --- Pose accessors ---

    GeneralPose3 local_pose() const {
        GeneralPose3 pose;
        tc_entity_pool* pool = pool_ptr();
        if (!pool) return pose;
        double pos[3], rot[4], scale[3];
        tc_entity_pool_get_local_pose(pool, _h.id, pos, rot, scale);
        pose.lin = Vec3{pos[0], pos[1], pos[2]};
        pose.ang = Quat{rot[0], rot[1], rot[2], rot[3]};
        pose.scale = Vec3{scale[0], scale[1], scale[2]};
        return pose;
    }

    void set_local_pose(const GeneralPose3& pose) {
        tc_entity_pool* pool = pool_ptr();
        if (!pool) return;
        double pos[3] = {pose.lin.x, pose.lin.y, pose.lin.z};
        double rot[4] = {pose.ang.x, pose.ang.y, pose.ang.z, pose.ang.w};
        double scale[3] = {pose.scale.x, pose.scale.y, pose.scale.z};
        tc_entity_pool_set_local_pose(pool, _h.id, pos, rot, scale);
    }

    // Individual component accessors
    Vec3 local_position() const {
        tc_entity_pool* pool = pool_ptr();
        if (!pool) return Vec3{0, 0, 0};
        double pos[3];
        tc_entity_pool_get_local_position(pool, _h.id, pos);
        return Vec3{pos[0], pos[1], pos[2]};
    }

    void set_local_position(const Vec3& p) {
        tc_entity_pool* pool = pool_ptr();
        if (!pool) return;
        double pos[3] = {p.x, p.y, p.z};
        tc_entity_pool_set_local_position(pool, _h.id, pos);
    }

    Quat local_rotation() const {
        tc_entity_pool* pool = pool_ptr();
        if (!pool) return Quat{0, 0, 0, 1};
        double rot[4];
        tc_entity_pool_get_local_rotation(pool, _h.id, rot);
        return Quat{rot[0], rot[1], rot[2], rot[3]};
    }

    void set_local_rotation(const Quat& q) {
        tc_entity_pool* pool = pool_ptr();
        if (!pool) return;
        double rot[4] = {q.x, q.y, q.z, q.w};
        tc_entity_pool_set_local_rotation(pool, _h.id, rot);
    }

    Vec3 local_scale() const {
        tc_entity_pool* pool = pool_ptr();
        if (!pool) return Vec3{1, 1, 1};
        double scale[3];
        tc_entity_pool_get_local_scale(pool, _h.id, scale);
        return Vec3{scale[0], scale[1], scale[2]};
    }

    void set_local_scale(const Vec3& s) {
        tc_entity_pool* pool = pool_ptr();
        if (!pool) return;
        double scale[3] = {s.x, s.y, s.z};
        tc_entity_pool_set_local_scale(pool, _h.id, scale);
    }

    // Global (world) component accessors
    Vec3 global_position() const {
        tc_entity_pool* pool = pool_ptr();
        if (!pool) return Vec3{0, 0, 0};
        double pos[3];
        tc_entity_pool_get_global_position(pool, _h.id, pos);
        return Vec3{pos[0], pos[1], pos[2]};
    }

    Quat global_rotation() const {
        tc_entity_pool* pool = pool_ptr();
        if (!pool) return Quat{0, 0, 0, 1};
        double rot[4];
        tc_entity_pool_get_global_rotation(pool, _h.id, rot);
        return Quat{rot[0], rot[1], rot[2], rot[3]};
    }

    Vec3 global_scale() const {
        tc_entity_pool* pool = pool_ptr();
        if (!pool) return Vec3{1, 1, 1};
        double scale[3];
        tc_entity_pool_get_global_scale(pool, _h.id, scale);
        return Vec3{scale[0], scale[1], scale[2]};
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
        GeneralPose3 pose;
        tc_entity_pool* pool = pool_ptr();
        if (!pool) return pose;
        double pos[3], rot[4], scale[3];
        tc_entity_pool_get_global_pose(pool, _h.id, pos, rot, scale);
        pose.lin = Vec3{pos[0], pos[1], pos[2]};
        pose.ang = Quat{rot[0], rot[1], rot[2], rot[3]};
        pose.scale = Vec3{scale[0], scale[1], scale[2]};
        return pose;
    }

    void set_global_pose(const GeneralPose3& gpose) {
        tc_entity_pool* pool = pool_ptr();
        if (!pool) return;
        tc_entity_id parent_id = tc_entity_pool_parent(pool, _h.id);
        if (!tc_entity_id_valid(parent_id)) {
            set_local_pose(gpose);
            return;
        }

        double ppos[3], prot[4], pscale[3];
        tc_entity_pool_get_global_pose(pool, parent_id, ppos, prot, pscale);

        Quat parent_rot{prot[0], prot[1], prot[2], prot[3]};
        Vec3 parent_pos{ppos[0], ppos[1], ppos[2]};
        Vec3 parent_scale{pscale[0], pscale[1], pscale[2]};

        Quat inv_parent_rot = parent_rot.inverse();

        Vec3 delta = gpose.lin - parent_pos;
        Vec3 local_pos = inv_parent_rot.rotate(delta);
        local_pos.x /= parent_scale.x;
        local_pos.y /= parent_scale.y;
        local_pos.z /= parent_scale.z;

        Quat local_rot = inv_parent_rot * gpose.ang;

        Vec3 local_scale{
            gpose.scale.x / parent_scale.x,
            gpose.scale.y / parent_scale.y,
            gpose.scale.z / parent_scale.z
        };

        set_local_pose(GeneralPose3{local_rot, local_pos, local_scale});
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
        tc_entity_pool* pool = pool_ptr();
        if (!pool) return GeneralTransform3();
        tc_entity_id parent_id = tc_entity_pool_parent(pool, _h.id);
        if (!tc_entity_id_valid(parent_id)) return GeneralTransform3();
        return GeneralTransform3(_h.pool, parent_id);
    }

    void set_parent(GeneralTransform3 new_parent) {
        tc_entity_pool* pool = pool_ptr();
        if (!pool) return;
        if (new_parent.valid() && !tc_entity_pool_handle_eq(new_parent._h.pool, _h.pool)) {
            throw std::runtime_error("Cannot set parent: transforms must be in the same pool");
        }
        tc_entity_pool_set_parent(pool, _h.id, new_parent._h.id);
    }

    void unparent() {
        tc_entity_pool* pool = pool_ptr();
        if (!pool) return;
        tc_entity_pool_set_parent(pool, _h.id, TC_ENTITY_ID_INVALID);
    }

    size_t children_count() const {
        tc_entity_pool* pool = pool_ptr();
        if (!pool) return 0;
        return tc_entity_pool_children_count(pool, _h.id);
    }

    GeneralTransform3 child_at(size_t index) const {
        tc_entity_pool* pool = pool_ptr();
        if (!pool) return GeneralTransform3();
        tc_entity_id child_id = tc_entity_pool_child_at(pool, _h.id, index);
        if (!tc_entity_id_valid(child_id)) return GeneralTransform3();
        return GeneralTransform3(_h.pool, child_id);
    }

    // --- Entity (creates Entity view on same data) ---

    ENTITY_API Entity entity() const;

    // --- Name (from entity) ---

    const char* name() const {
        tc_entity_pool* pool = pool_ptr();
        if (!pool) return "";
        return tc_entity_pool_name(pool, _h.id);
    }

    // --- Dirty tracking ---

    void mark_dirty() {
        tc_entity_pool* pool = pool_ptr();
        if (!pool) return;
        tc_entity_pool_mark_dirty(pool, _h.id);
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
        tc_entity_pool* pool = pool_ptr();
        if (!pool) return;
        tc_entity_pool_get_world_matrix(pool, _h.id, m);
    }

    // --- Handle/Pool/ID access ---

    tc_entity_handle handle() const { return _h; }
    tc_entity_pool* pool() const { return pool_ptr(); }
    tc_entity_pool_handle pool_handle() const { return _h.pool; }
    tc_entity_id id() const { return _h.id; }
};

} // namespace termin
