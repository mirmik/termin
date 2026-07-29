#include <cmath>
#include <iostream>
#include <stdexcept>

#include <termin/entity/entity.hpp>
#include <termin/geom/general_transform3.hpp>

#define CHECK(condition) \
    do { \
        if (!(condition)) { \
            std::cerr << "CHECK failed at " << __FILE__ << ":" << __LINE__ \
                      << ": " #condition << "\n"; \
            return 1; \
        } \
    } while (0)

namespace {

bool near(double actual, double expected, double epsilon = 1.0e-10) {
    return std::abs(actual - expected) <= epsilon;
}

bool vec_near(
    const termin::Vec3& actual,
    const termin::Vec3& expected,
    double epsilon = 1.0e-10) {
    return near(actual.x, expected.x, epsilon)
        && near(actual.y, expected.y, epsilon)
        && near(actual.z, expected.z, epsilon);
}

termin::Quat rotation_z(double radians) {
    const double half = radians * 0.5;
    return {0.0, 0.0, std::sin(half), std::cos(half)};
}

} // namespace

int main() {
    const tc_entity_pool_handle pool_handle =
        tc_entity_pool_registry_create(8);
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
        termin::Affine3d::trs(
            {3.0, 4.0, 5.0},
            {0.0, 0.0, 0.0, 1.0},
            {2.0, 1.0, 0.5})
        * termin::Affine3d::trs(
            {1.0, 2.0, 3.0},
            rotation_z(0.5 * std::acos(-1.0)),
            {1.0, 3.0, 1.0});
    const termin::Vec3 local_point{2.0, -1.0, 4.0};
    const termin::Vec3 world_point = expected.transform_point(local_point);
    CHECK(vec_near(transform.transform_point(local_point), world_point));
    CHECK(vec_near(transform.transform_point_inverse(world_point), local_point));

    const termin::Vec3 local_vector{2.0, -1.0, 4.0};
    const termin::Vec3 world_vector = expected.transform_vector(local_vector);
    CHECK(vec_near(transform.transform_vector(local_vector), world_vector));
    CHECK(vec_near(transform.transform_vector_inverse(world_vector), local_vector));

    // Directions and editor axes intentionally follow the logical quaternion,
    // not the sheared geometric basis.
    CHECK(vec_near(transform.right(), {0.0, 1.0, 0.0}));
    const termin::Vec3 axis_lengths = transform.basis_axis_lengths();
    CHECK(vec_near(axis_lengths, {
        expected.basis.x.norm(),
        expected.basis.y.norm(),
        expected.basis.z.norm(),
    }));

    double world_matrix[16];
    double inverse_matrix[16];
    transform.world_matrix(world_matrix);
    transform.inverse_world_matrix(inverse_matrix);
    for (int row = 0; row < 4; ++row) {
        for (int col = 0; col < 4; ++col) {
            double value = 0.0;
            for (int k = 0; k < 4; ++k) {
                value += world_matrix[k * 4 + row]
                    * inverse_matrix[col * 4 + k];
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
    CHECK(near(std::abs(
        requested_orientation.x * actual_orientation.x
        + requested_orientation.y * actual_orientation.y
        + requested_orientation.z * actual_orientation.z
        + requested_orientation.w * actual_orientation.w), 1.0));

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

    tc_entity_pool_registry_destroy(pool_handle);
    return 0;
}
