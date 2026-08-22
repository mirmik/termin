#include <cmath>
#include <iostream>
#include <stdexcept>

#include <termin/entity/entity.hpp>
#include <termin/geom/general_transform3.hpp>

#define CHECK(condition)                                                                                               \
    do {                                                                                                               \
        if (!(condition)) {                                                                                            \
            std::cerr << "CHECK failed at " << __FILE__ << ":" << __LINE__ << ": " #condition << "\n";                 \
            return 1;                                                                                                  \
        }                                                                                                              \
    } while (0)

namespace {

    bool near(double actual, double expected, double epsilon = 1.0e-10) {
        return std::abs(actual - expected) <= epsilon;
    }

    bool vec_near(const termin::Vec3& actual, const termin::Vec3& expected, double epsilon = 1.0e-10) {
        return near(actual.x, expected.x, epsilon) && near(actual.y, expected.y, epsilon) &&
               near(actual.z, expected.z, epsilon);
    }

    bool affine_near(const termin::Affine3d& actual, const termin::Affine3d& expected, double epsilon = 1.0e-10) {
        return vec_near(actual.translation, expected.translation, epsilon) &&
               vec_near(actual.basis.x, expected.basis.x, epsilon) &&
               vec_near(actual.basis.y, expected.basis.y, epsilon) &&
               vec_near(actual.basis.z, expected.basis.z, epsilon);
    }

    termin::Quat rotation_z(double radians) {
        const double half = radians * 0.5;
        return {0.0, 0.0, std::sin(half), std::cos(half)};
    }

} // namespace

int main() {
    const tc_entity_pool_handle pool_handle = tc_entity_pool_registry_create(32);
    CHECK(tc_entity_pool_handle_valid(pool_handle));

    termin::Entity parent = termin::Entity::create(pool_handle, "parent");
    termin::Entity child = parent.create_child("child");
    CHECK(parent.valid());
    CHECK(child.valid());

    parent.transform().set_local_pose(termin::GeneralPose3{
        termin::Quat{0.0, 0.0, 0.0, 1.0},
        termin::Vec3{3.0, 4.0, 5.0},
        termin::Vec3{2.0, 1.0, 0.5},
    });
    child.transform().set_local_pose(termin::GeneralPose3{
        rotation_z(0.5 * std::acos(-1.0)),
        termin::Vec3{1.0, 2.0, 3.0},
        termin::Vec3{1.0, 3.0, 1.0},
    });

    const termin::GeneralTransform3 transform = child.transform();
    CHECK(transform.kind() == termin::TransformKind::Affine);
    CHECK(!transform.decomposed_global_scale().has_value());
    CHECK(!transform.try_rigid_pose().has_value());

    const termin::Affine3d expected =
        termin::Affine3d::trs({3.0, 4.0, 5.0}, {0.0, 0.0, 0.0, 1.0}, {2.0, 1.0, 0.5}) *
        termin::Affine3d::trs({1.0, 2.0, 3.0}, rotation_z(0.5 * std::acos(-1.0)), {1.0, 3.0, 1.0});
    const termin::Vec3 local_point{2.0, -1.0, 4.0};
    const termin::Vec3 world_point = expected.transform_point(local_point);
    CHECK(vec_near(transform.transform_point(local_point), world_point));
    CHECK(vec_near(transform.transform_point_inverse(world_point), local_point));

    const termin::Vec3 local_vector{2.0, -1.0, 4.0};
    const termin::Vec3 world_vector = expected.transform_vector(local_vector);
    CHECK(vec_near(transform.transform_vector(local_vector), world_vector));
    CHECK(vec_near(transform.transform_vector_inverse(world_vector), local_vector));
    const termin::Vec3 world_normal = transform.transform_normal({0.0, 0.0, 1.0});
    CHECK(near(world_normal.dot(transform.transform_vector({1.0, 0.0, 0.0})), 0.0));
    CHECK(near(world_normal.dot(transform.transform_vector({0.0, 1.0, 0.0})), 0.0));

    // Directions and editor axes intentionally follow the logical quaternion,
    // not the sheared geometric basis.
    CHECK(vec_near(transform.right(), {0.0, 1.0, 0.0}));
    const termin::Vec3 axis_lengths = transform.basis_axis_lengths();
    CHECK(vec_near(axis_lengths,
                   {
                       expected.basis.x.norm(),
                       expected.basis.y.norm(),
                       expected.basis.z.norm(),
                   }));
    CHECK(vec_near(transform.lossy_scale(), axis_lengths));
    const termin::GeneralPose3 lossy_pose = transform.lossy_global_pose();
    CHECK(vec_near(lossy_pose.lin, transform.global_position()));
    CHECK(vec_near(lossy_pose.scale, axis_lengths));
    const termin::Quat logical_rotation = transform.global_rotation();
    CHECK(near(std::abs(lossy_pose.ang.x * logical_rotation.x + lossy_pose.ang.y * logical_rotation.y +
                        lossy_pose.ang.z * logical_rotation.z + lossy_pose.ang.w * logical_rotation.w),
               1.0));

    double world_matrix[16];
    double inverse_matrix[16];
    transform.world_matrix(world_matrix);
    transform.inverse_world_matrix(inverse_matrix);
    for (int row = 0; row < 4; ++row) {
        for (int col = 0; col < 4; ++col) {
            double value = 0.0;
            for (int k = 0; k < 4; ++k) {
                value += world_matrix[k * 4 + row] * inverse_matrix[col * 4 + k];
            }
            CHECK(near(value, row == col ? 1.0 : 0.0));
        }
    }

    const termin::Vec3 requested_position{11.0, -7.0, 2.5};
    child.transform().set_global_position(requested_position);
    CHECK(vec_near(child.transform().global_position(), requested_position));

    const termin::Quat requested_orientation = rotation_z(0.25);
    child.transform().set_global_orientation(requested_orientation);
    const termin::Quat actual_orientation = child.transform().global_rotation();
    CHECK(
        near(std::abs(requested_orientation.x * actual_orientation.x + requested_orientation.y * actual_orientation.y +
                      requested_orientation.z * actual_orientation.z + requested_orientation.w * actual_orientation.w),
             1.0));

    const termin::Vec3 authored_scale = child.transform().local_scale();
    const termin::Pose3 requested_pose{
        rotation_z(-0.4),
        {-3.0, 8.0, 1.25},
    };
    child.transform().set_global_pose(requested_pose);
    const termin::Pose3 actual_pose = child.transform().global_pose();
    CHECK(vec_near(actual_pose.lin, requested_pose.lin));
    CHECK(near(std::abs(requested_pose.ang.x * actual_pose.ang.x + requested_pose.ang.y * actual_pose.ang.y +
                        requested_pose.ang.z * actual_pose.ang.z + requested_pose.ang.w * actual_pose.ang.w),
               1.0));
    CHECK(vec_near(child.transform().local_scale(), authored_scale));

    termin::Entity rigid = termin::Entity::create(pool_handle, "rigid");
    rigid.transform().set_local_position({1.0, 2.0, 3.0});
    CHECK(rigid.transform().kind() == termin::TransformKind::Rigid);
    CHECK(rigid.transform().try_rigid_pose().has_value());

    termin::Entity singular = termin::Entity::create(pool_handle, "singular");
    singular.transform().set_local_scale({1.0, 0.0, 1.0});
    termin::Affine3d unused_inverse;
    CHECK(!singular.transform().try_inverse_world_affine(unused_inverse));
    bool inverse_threw = false;
    try {
        singular.transform().transform_point_inverse({1.0, 2.0, 3.0});
    } catch (const std::runtime_error&) {
        inverse_threw = true;
    }
    CHECK(inverse_threw);

    bool normal_threw = false;
    try {
        singular.transform().transform_normal({0.0, 0.0, 1.0});
    } catch (const std::runtime_error&) {
        normal_threw = true;
    }
    CHECK(normal_threw);

    // Exact world-preserving reparenting accepts a representable local TRS.
    termin::Entity scaled_parent = termin::Entity::create(pool_handle, "scaled-parent");
    scaled_parent.transform().set_local_scale({2.0, 3.0, 4.0});
    termin::Entity reparented = termin::Entity::create(pool_handle, "reparented");
    reparented.transform().set_local_pose(termin::GeneralPose3{
        termin::Quat::identity(),
        {6.0, -2.0, 1.0},
        {1.0, 1.0, 1.0},
    });
    const termin::Affine3d rigid_world = reparented.transform().global_affine();
    CHECK(reparented.transform().try_reparent_preserve_world(scaled_parent.transform()));
    CHECK(reparented.parent() == scaled_parent);
    CHECK(affine_near(reparented.transform().global_affine(), rigid_world));

    // Two affine parents with the same exact basis can still admit an exact
    // local TRS reparent.
    termin::Entity affine_a = scaled_parent.create_child("affine-a");
    termin::Entity affine_b = scaled_parent.create_child("affine-b");
    affine_a.transform().set_local_pose(termin::GeneralPose3{
        rotation_z(0.5),
        {1.0, 0.0, 0.0},
        {1.0, 1.0, 1.0},
    });
    affine_b.transform().set_local_pose(termin::GeneralPose3{
        rotation_z(0.5),
        {-3.0, 2.0, 0.0},
        {1.0, 1.0, 1.0},
    });
    CHECK(affine_a.transform().kind() == termin::TransformKind::Affine);
    CHECK(affine_b.transform().kind() == termin::TransformKind::Affine);
    termin::Entity affine_child = affine_a.create_child("affine-child");
    affine_child.transform().set_local_position({2.0, 1.0, 0.0});
    const termin::Affine3d affine_world = affine_child.transform().global_affine();
    CHECK(affine_child.transform().try_reparent_preserve_world(affine_b.transform()));
    CHECK(affine_child.parent() == affine_b);
    CHECK(affine_near(affine_child.transform().global_affine(), affine_world));

    // Moving that affine world transform to the root would require authored
    // local shear, so rejection must leave hierarchy and local TRS unchanged.
    const termin::GeneralPose3 before_rejection = affine_child.transform().local_pose();
    CHECK(!affine_child.transform().try_reparent_preserve_world({}));
    CHECK(affine_child.parent() == affine_b);
    CHECK(vec_near(affine_child.transform().local_position(), before_rejection.lin));
    CHECK(vec_near(affine_child.transform().local_scale(), before_rejection.scale));
    CHECK(affine_near(affine_child.transform().global_affine(), affine_world));

    termin::Entity singular_parent = termin::Entity::create(pool_handle, "singular-parent");
    singular_parent.transform().set_local_scale({1.0, 0.0, 1.0});
    CHECK(!affine_child.transform().try_reparent_preserve_world(singular_parent.transform()));
    CHECK(affine_child.parent() == affine_b);

    tc_entity_pool_registry_destroy(pool_handle);
    return 0;
}
