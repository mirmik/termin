#include "core/tc_entity_pool_registry.h"
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <tcbase/tc_log.h>
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

void GeneralTransform3::set_global_position(const Vec3& position) {
    auto* p = pool_ptr();
    if (!p)
        return;
    auto parent_id = tc_entity_pool_parent(p, _h.id);
    if (!tc_entity_id_valid(parent_id)) {
        set_local_position(position);
        return;
    }
    Affine3d parent_affine;
    tc_entity_pool_get_world_affine(p, parent_id, &parent_affine);
    Affine3d inverse;
    if (!parent_affine.try_inverse(inverse)) {
        tc_log_error(
            "[GeneralTransform3] cannot set global position for '%s': "
            "parent world transform is singular",
            name());
        throw std::runtime_error(
            "Cannot set global position through a singular parent transform");
    }
    set_local_position(inverse.transform_point(position));
}

void GeneralTransform3::set_global_orientation(const Quat& orientation) {
    auto* p = pool_ptr();
    if (!p)
        return;
    auto parent_id = tc_entity_pool_parent(p, _h.id);
    if (!tc_entity_id_valid(parent_id)) {
        set_local_rotation(orientation.normalized());
        return;
    }
    double parent_xyzw[4];
    tc_entity_pool_get_global_rotation(p, parent_id, parent_xyzw);
    const Quat parent_orientation{
        parent_xyzw[0], parent_xyzw[1], parent_xyzw[2], parent_xyzw[3]};
    set_local_rotation(
        (parent_orientation.inverse() * orientation).normalized());
}

TransformKind GeneralTransform3::kind() const {
    auto* p = pool_ptr();
    if (!p)
        return TransformKind::Rigid;
    return static_cast<TransformKind>(
        tc_entity_pool_get_world_transform_kind(p, _h.id));
}

Basis3d GeneralTransform3::linear_basis() const {
    Basis3d basis = Basis3d::identity();
    auto* p = pool_ptr();
    if (p)
        tc_entity_pool_get_world_basis(p, _h.id, &basis);
    return basis;
}

Affine3d GeneralTransform3::global_affine() const {
    Affine3d affine = Affine3d::identity();
    auto* p = pool_ptr();
    if (p)
        tc_entity_pool_get_world_affine(p, _h.id, &affine);
    return affine;
}

std::optional<Vec3> GeneralTransform3::decomposed_global_scale() const {
    auto* p = pool_ptr();
    if (!p)
        return Vec3{1.0, 1.0, 1.0};
    double scale[3];
    if (!tc_entity_pool_try_get_global_scale(p, _h.id, scale))
        return std::nullopt;
    return Vec3{scale[0], scale[1], scale[2]};
}

Vec3 GeneralTransform3::basis_axis_lengths() const {
    const Basis3d basis = linear_basis();
    return {basis.x.norm(), basis.y.norm(), basis.z.norm()};
}

std::optional<Pose3> GeneralTransform3::try_rigid_pose() const {
    if (kind() != TransformKind::Rigid)
        return std::nullopt;
    return Pose3{global_rotation(), global_position()};
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
    Affine3d parent_affine;
    tc_entity_pool_get_world_affine(p, parent_id, &parent_affine);
    Affine3d parent_inverse;
    if (!parent_affine.try_inverse(parent_inverse)) {
        tc_log_error(
            "[GeneralTransform3] cannot set global pose for '%s': "
            "parent world transform is singular",
            name());
        throw std::runtime_error(
            "Cannot set global pose through a singular parent transform");
    }

    double parent_xyzw[4];
    tc_entity_pool_get_global_rotation(p, parent_id, parent_xyzw);
    const Quat parent_orientation{
        parent_xyzw[0], parent_xyzw[1], parent_xyzw[2], parent_xyzw[3]};
    const Quat local_orientation =
        (parent_orientation.inverse() * g.ang).normalized();
    const Affine3d local_affine =
        parent_inverse * Affine3d::trs(g.lin, g.ang.normalized(), g.scale);
    const Basis3d rotation_basis = Basis3d::from_quat(local_orientation);

    const Vec3 local_scale{
        rotation_basis.x.dot(local_affine.basis.x),
        rotation_basis.y.dot(local_affine.basis.y),
        rotation_basis.z.dot(local_affine.basis.z),
    };
    const Basis3d representable_basis{
        rotation_basis.x * local_scale.x,
        rotation_basis.y * local_scale.y,
        rotation_basis.z * local_scale.z,
    };
    const double tolerance = 1.0e-10;
    const auto column_matches = [tolerance](const Vec3& actual, const Vec3& expected) {
        return (actual - expected).norm() <=
            tolerance * std::max(1.0, actual.norm());
    };
    if (!column_matches(local_affine.basis.x, representable_basis.x) ||
        !column_matches(local_affine.basis.y, representable_basis.y) ||
        !column_matches(local_affine.basis.z, representable_basis.z)) {
        tc_log_error(
            "[GeneralTransform3] cannot set global pose for '%s': requested "
            "world TRS requires shear in the local transform",
            name());
        throw std::runtime_error(
            "Requested global pose is not representable by the local TRS transform");
    }
    set_local_pose(GeneralPose3{
        local_orientation,
        local_affine.translation,
        local_scale,
    });
}
void GeneralTransform3::relocate_global(const GeneralPose3 &pose) { set_global_pose(pose); }
void GeneralTransform3::relocate_global(const Pose3 &pose) {
    const std::optional<Vec3> scale = decomposed_global_scale();
    if (!scale) {
        tc_log_error(
            "[GeneralTransform3] cannot relocate global rigid pose for '%s': "
            "current affine world transform has no exact decomposed scale",
            name());
        throw std::runtime_error(
            "Cannot preserve scale while relocating an affine world transform");
    }
    set_global_pose(GeneralPose3{pose.ang, pose.lin, *scale});
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
    return global_affine().transform_point(v);
}
Vec3 GeneralTransform3::transform_point_inverse(const Vec3 &v) const {
    Affine3d inverse;
    if (!try_inverse_world_affine(inverse)) {
        tc_log_error(
            "[GeneralTransform3] cannot inverse-transform point for '%s': "
            "world transform is singular",
            name());
        throw std::runtime_error(
            "Cannot inverse-transform point through a singular world transform");
    }
    return inverse.transform_point(v);
}
Vec3 GeneralTransform3::transform_vector(const Vec3 &v) const {
    return linear_basis().transform_vector(v);
}
Vec3 GeneralTransform3::transform_vector_inverse(const Vec3 &v) const {
    Basis3d inverse;
    if (!linear_basis().try_inverse(inverse)) {
        tc_log_error(
            "[GeneralTransform3] cannot inverse-transform vector for '%s': "
            "world basis is singular",
            name());
        throw std::runtime_error(
            "Cannot inverse-transform vector through a singular world basis");
    }
    return inverse.transform_vector(v);
}
Vec3 GeneralTransform3::transform_direction(const Vec3 &v) const {
    return global_rotation().rotate(v);
}
Vec3 GeneralTransform3::transform_direction_inverse(const Vec3 &v) const {
    return global_rotation().inverse().rotate(v);
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

bool GeneralTransform3::try_inverse_world_affine(
    Affine3d& inverse,
    double epsilon) const {
    return global_affine().try_inverse(inverse, epsilon);
}

void GeneralTransform3::inverse_world_matrix(double* m, double epsilon) const {
    Affine3d inverse;
    if (!try_inverse_world_affine(inverse, epsilon)) {
        tc_log_error(
            "[GeneralTransform3] cannot build inverse world matrix for '%s': "
            "world transform is singular",
            name());
        throw std::runtime_error(
            "Cannot build inverse world matrix for a singular transform");
    }
    inverse.matrix4(m);
}

Entity GeneralTransform3::entity() const { return Entity(_h); }

} // namespace termin
