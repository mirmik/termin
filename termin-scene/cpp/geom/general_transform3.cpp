#include "core/tc_entity_pool_registry.h"
#include <stdexcept>
#include <termin/entity/entity.hpp>
#include <termin/geom/general_transform3.hpp>

namespace termin {

GeneralTransform3::GeneralTransform3(tc_entity_pool *pool, tc_entity_id id) {
    tc_entity_pool_handle pool_h = tc_entity_pool_registry_find(pool);
    _h = tc_entity_handle_make(pool_h, id);
}

tc_entity_pool *GeneralTransform3::pool_ptr() const { return tc_entity_pool_registry_get(_h.pool); }

bool GeneralTransform3::valid() const { return tc_entity_handle_valid(_h); }

GeneralPose3 GeneralTransform3::local_pose() const {
    GeneralPose3 pose;
    tc_entity_pool *pool = pool_ptr();
    if (!pool)
        return pose;
    double pos[3], rot[4], scale[3];
    tc_entity_pool_get_local_pose(pool, _h.id, pos, rot, scale);
    pose.lin = Vec3{pos[0], pos[1], pos[2]};
    pose.ang = Quat{rot[0], rot[1], rot[2], rot[3]};
    pose.scale = Vec3{scale[0], scale[1], scale[2]};
    return pose;
}

void GeneralTransform3::set_local_pose(const GeneralPose3 &pose) {
    tc_entity_pool *pool = pool_ptr();
    if (!pool)
        return;
    double pos[3] = {pose.lin.x, pose.lin.y, pose.lin.z};
    double rot[4] = {pose.ang.x, pose.ang.y, pose.ang.z, pose.ang.w};
    double scale[3] = {pose.scale.x, pose.scale.y, pose.scale.z};
    tc_entity_pool_set_local_pose(pool, _h.id, pos, rot, scale);
}

Vec3 GeneralTransform3::local_position() const {
    auto *p = pool_ptr();
    if (!p)
        return {0, 0, 0};
    double v[3];
    tc_entity_pool_get_local_position(p, _h.id, v);
    return {v[0], v[1], v[2]};
}
void GeneralTransform3::set_local_position(const Vec3 &v) {
    auto *p = pool_ptr();
    if (p) {
        double a[3] = {v.x, v.y, v.z};
        tc_entity_pool_set_local_position(p, _h.id, a);
    }
}
Quat GeneralTransform3::local_rotation() const {
    auto *p = pool_ptr();
    if (!p)
        return {0, 0, 0, 1};
    double v[4];
    tc_entity_pool_get_local_rotation(p, _h.id, v);
    return {v[0], v[1], v[2], v[3]};
}
void GeneralTransform3::set_local_rotation(const Quat &v) {
    auto *p = pool_ptr();
    if (p) {
        double a[4] = {v.x, v.y, v.z, v.w};
        tc_entity_pool_set_local_rotation(p, _h.id, a);
    }
}
Vec3 GeneralTransform3::local_scale() const {
    auto *p = pool_ptr();
    if (!p)
        return {1, 1, 1};
    double v[3];
    tc_entity_pool_get_local_scale(p, _h.id, v);
    return {v[0], v[1], v[2]};
}
void GeneralTransform3::set_local_scale(const Vec3 &v) {
    auto *p = pool_ptr();
    if (p) {
        double a[3] = {v.x, v.y, v.z};
        tc_entity_pool_set_local_scale(p, _h.id, a);
    }
}
Vec3 GeneralTransform3::global_position() const {
    auto *p = pool_ptr();
    if (!p)
        return {0, 0, 0};
    double v[3];
    tc_entity_pool_get_global_position(p, _h.id, v);
    return {v[0], v[1], v[2]};
}
Quat GeneralTransform3::global_rotation() const {
    auto *p = pool_ptr();
    if (!p)
        return {0, 0, 0, 1};
    double v[4];
    tc_entity_pool_get_global_rotation(p, _h.id, v);
    return {v[0], v[1], v[2], v[3]};
}
Vec3 GeneralTransform3::global_scale() const {
    auto *p = pool_ptr();
    if (!p)
        return {1, 1, 1};
    double v[3];
    tc_entity_pool_get_global_scale(p, _h.id, v);
    return {v[0], v[1], v[2]};
}

void GeneralTransform3::relocate(const GeneralPose3 &pose) { set_local_pose(pose); }
void GeneralTransform3::relocate(const Pose3 &pose) {
    auto gp = local_pose();
    gp.ang = pose.ang;
    gp.lin = pose.lin;
    set_local_pose(gp);
}

GeneralPose3 GeneralTransform3::global_pose() const {
    GeneralPose3 pose;
    auto *p = pool_ptr();
    if (!p)
        return pose;
    double a[3], b[4], c[3];
    tc_entity_pool_get_global_pose(p, _h.id, a, b, c);
    pose.lin = {a[0], a[1], a[2]};
    pose.ang = {b[0], b[1], b[2], b[3]};
    pose.scale = {c[0], c[1], c[2]};
    return pose;
}
void GeneralTransform3::set_global_pose(const GeneralPose3 &g) {
    auto *p = pool_ptr();
    if (!p)
        return;
    auto parent_id = tc_entity_pool_parent(p, _h.id);
    if (!tc_entity_id_valid(parent_id)) {
        set_local_pose(g);
        return;
    }
    double pp[3], pr[4], ps[3];
    tc_entity_pool_get_global_pose(p, parent_id, pp, pr, ps);
    Quat r{pr[0], pr[1], pr[2], pr[3]};
    Vec3 pos{pp[0], pp[1], pp[2]}, sc{ps[0], ps[1], ps[2]};
    Quat inv = r.inverse();
    Vec3 lp = inv.rotate(g.lin - pos);
    lp.x /= sc.x;
    lp.y /= sc.y;
    lp.z /= sc.z;
    set_local_pose(
        GeneralPose3{inv * g.ang, lp, {g.scale.x / sc.x, g.scale.y / sc.y, g.scale.z / sc.z}});
}
void GeneralTransform3::relocate_global(const GeneralPose3 &pose) { set_global_pose(pose); }
void GeneralTransform3::relocate_global(const Pose3 &pose) {
    auto s = global_pose().scale;
    set_global_pose(GeneralPose3{pose.ang, pose.lin, s});
}

GeneralTransform3 GeneralTransform3::parent() const {
    auto *p = pool_ptr();
    if (!p)
        return {};
    auto id = tc_entity_pool_parent(p, _h.id);
    return tc_entity_id_valid(id) ? GeneralTransform3(_h.pool, id) : GeneralTransform3();
}
void GeneralTransform3::set_parent(GeneralTransform3 n) {
    auto *p = pool_ptr();
    if (!p)
        return;
    if (n.valid() && !tc_entity_pool_handle_eq(n._h.pool, _h.pool))
        throw std::runtime_error("Cannot set parent: transforms must be in the same pool");
    tc_entity_pool_set_parent(p, _h.id, n._h.id);
}
void GeneralTransform3::unparent() {
    auto *p = pool_ptr();
    if (p)
        tc_entity_pool_set_parent(p, _h.id, TC_ENTITY_ID_INVALID);
}
size_t GeneralTransform3::children_count() const {
    auto *p = pool_ptr();
    return p ? tc_entity_pool_children_count(p, _h.id) : 0;
}
GeneralTransform3 GeneralTransform3::child_at(size_t i) const {
    auto *p = pool_ptr();
    if (!p)
        return {};
    auto id = tc_entity_pool_child_at(p, _h.id, i);
    return tc_entity_id_valid(id) ? GeneralTransform3(_h.pool, id) : GeneralTransform3();
}

const char *GeneralTransform3::name() const {
    auto *p = pool_ptr();
    return p ? tc_entity_pool_name(p, _h.id) : "";
}
void GeneralTransform3::mark_dirty() {
    auto *p = pool_ptr();
    if (p)
        tc_entity_pool_mark_dirty(p, _h.id);
}
Vec3 GeneralTransform3::transform_point(const Vec3 &v) const {
    return global_pose().transform_point(v);
}
Vec3 GeneralTransform3::transform_point_inverse(const Vec3 &v) const {
    return global_pose().inverse_transform_point(v);
}
Vec3 GeneralTransform3::transform_vector(const Vec3 &v) const {
    return global_pose().transform_vector(v);
}
Vec3 GeneralTransform3::transform_vector_inverse(const Vec3 &v) const {
    return global_pose().inverse_transform_vector(v);
}
Vec3 GeneralTransform3::transform_direction(const Vec3 &v) const {
    return global_pose().transform_direction(v);
}
Vec3 GeneralTransform3::transform_direction_inverse(const Vec3 &v) const {
    return global_pose().inverse_transform_direction(v);
}
Vec3 GeneralTransform3::forward(double d) const { return transform_direction({0, d, 0}); }
Vec3 GeneralTransform3::backward(double d) const { return transform_direction({0, -d, 0}); }
Vec3 GeneralTransform3::up(double d) const { return transform_direction({0, 0, d}); }
Vec3 GeneralTransform3::down(double d) const { return transform_direction({0, 0, -d}); }
Vec3 GeneralTransform3::right(double d) const { return transform_direction({d, 0, 0}); }
Vec3 GeneralTransform3::left(double d) const { return transform_direction({-d, 0, 0}); }
void GeneralTransform3::world_matrix(double *m) const {
    auto *p = pool_ptr();
    if (p)
        tc_entity_pool_get_world_matrix(p, _h.id, m);
    else
        tc_entity_default_world_matrix(m);
}

Entity GeneralTransform3::entity() const { return Entity(_h); }

} // namespace termin
