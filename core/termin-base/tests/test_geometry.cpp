#include <cmath>
#include <limits>
#include <random>
#include <type_traits>

#include <tcbase/tc_types.h>
#include <geom/tc_quat.h>
#include <termin/geom/affine2.hpp>
#include <termin/geom/affine3.hpp>
#include <termin/geom/aabb.hpp>
#include <termin/geom/bounds2.hpp>
#include <termin/geom/color.hpp>
#include <termin/geom/mat44.hpp>
#include <termin/geom/mat66.hpp>
#include <termin/geom/pose3.hpp>
#include <termin/geom/quat.hpp>
#include <termin/geom/ray3.hpp>
#include <termin/geom/rect2.hpp>
#include <termin/geom/se3.hpp>
#include <termin/geom/size2.hpp>
#include <termin/geom/spatial_inertia3.hpp>
#include <termin/geom/vec6.hpp>
#include <termin/geom/world2d.hpp>

#include "guard_main.h"

TEST_CASE("tc_vec3 normalized zero vector returns NaNs") {
    tc_vec3 normalized = tc_vec3::zero().normalized();

    CHECK(std::isnan(normalized.x));
    CHECK(std::isnan(normalized.y));
    CHECK(std::isnan(normalized.z));
}

TEST_CASE("Quat checked operations match the C foundation and preserve raw xyzw ABI") {
    using termin::Quat;

    static_assert(sizeof(Quat) == sizeof(double) * 4);
    static_assert(offsetof(Quat, x) == sizeof(double) * 0);
    static_assert(offsetof(Quat, y) == sizeof(double) * 1);
    static_assert(offsetof(Quat, z) == sizeof(double) * 2);
    static_assert(offsetof(Quat, w) == sizeof(double) * 3);

    const Quat value{1.0, -2.0, 3.0, 4.0};
    const Quat other{-0.5, 0.25, 2.0, -1.0};
    CHECK(value.dot(other) == tc_quat_dot(value, other));
    CHECK(value.norm_squared() == tc_quat_norm_squared(value));
    CHECK(value.norm() == tc_quat_norm(value));
    CHECK(value.is_finite() == tc_quat_is_finite(value));

    Quat cpp_normalized{9.0, 8.0, 7.0, 6.0};
    tc_quat c_normalized{9.0, 8.0, 7.0, 6.0};
    REQUIRE(value.try_normalized(cpp_normalized));
    REQUIRE(tc_quat_try_normalized(value, 1.0e-12, &c_normalized));
    CHECK(cpp_normalized.x == c_normalized.x);
    CHECK(cpp_normalized.y == c_normalized.y);
    CHECK(cpp_normalized.z == c_normalized.z);
    CHECK(cpp_normalized.w == c_normalized.w);

    Quat cpp_inverse{9.0, 8.0, 7.0, 6.0};
    tc_quat c_inverse{9.0, 8.0, 7.0, 6.0};
    REQUIRE(value.try_inverse(cpp_inverse));
    REQUIRE(tc_quat_try_inverse(value, 1.0e-12, &c_inverse));
    CHECK(cpp_inverse.x == c_inverse.x);
    CHECK(cpp_inverse.y == c_inverse.y);
    CHECK(cpp_inverse.z == c_inverse.z);
    CHECK(cpp_inverse.w == c_inverse.w);
    const Quat product = value * cpp_inverse;
    CHECK(std::abs(product.x) < 1.0e-15);
    CHECK(std::abs(product.y) < 1.0e-15);
    CHECK(std::abs(product.z) < 1.0e-15);
    CHECK(std::abs(product.w - 1.0) < 1.0e-15);

    const Quat largest_finite{std::numeric_limits<double>::max(), 0.0, 0.0, 0.0};
    REQUIRE(largest_finite.try_inverse(cpp_inverse, 0.0));
    REQUIRE(tc_quat_try_inverse(largest_finite, 0.0, &c_inverse));
    CHECK(cpp_inverse.x == c_inverse.x);
    CHECK(cpp_inverse.x < 0.0);
    const Quat large_product = largest_finite * cpp_inverse;
    CHECK(std::abs(large_product.w - 1.0) < 1.0e-15);

    const Quat partial_underflow{2.0e-162, 2.0e-162, 0.0, 0.0};
    REQUIRE(partial_underflow.try_normalized(cpp_normalized, 0.0));
    REQUIRE(tc_quat_try_normalized(partial_underflow, 0.0, &c_normalized));
    CHECK(std::abs(cpp_normalized.norm() - 1.0) < 1.0e-15);
    CHECK(cpp_normalized.x == c_normalized.x);
    CHECK(cpp_normalized.y == c_normalized.y);
    REQUIRE(partial_underflow.try_inverse(cpp_inverse, 0.0));
    REQUIRE(tc_quat_try_inverse(partial_underflow, 0.0, &c_inverse));
    CHECK(std::abs((partial_underflow * cpp_inverse).w - 1.0) < 1.0e-15);
    CHECK(cpp_inverse.x == c_inverse.x);

    const Quat sentinel{9.0, 8.0, 7.0, 6.0};
    Quat unchanged = sentinel;
    CHECK_FALSE((Quat{0.0, 0.0, 0.0, 0.0}.try_normalized(unchanged, 0.0)));
    CHECK(unchanged.x == sentinel.x);
    CHECK(unchanged.y == sentinel.y);
    CHECK(unchanged.z == sentinel.z);
    CHECK(unchanged.w == sentinel.w);
    CHECK_FALSE(Quat::identity().try_inverse(unchanged, -1.0));
    CHECK(unchanged.x == sentinel.x);
    CHECK_FALSE(Quat::identity().try_inverse(unchanged, std::numeric_limits<double>::quiet_NaN()));
    CHECK(unchanged.x == sentinel.x);
    CHECK_FALSE((Quat{std::numeric_limits<double>::infinity(), 0.0, 0.0, 1.0}.try_normalized(unchanged)));
    CHECK(unchanged.x == sentinel.x);

    const Quat fallback{4.0, 3.0, 2.0, 1.0};
    const Quat normalized_or = Quat{0.0, 0.0, 0.0, 0.0}.normalized_or(fallback, 0.0);
    CHECK(normalized_or.x == fallback.x);
    CHECK(normalized_or.y == fallback.y);
    CHECK(normalized_or.z == fallback.z);
    CHECK(normalized_or.w == fallback.w);
    CHECK_FALSE((Quat{0.0, 0.0, 0.0, 0.0}.normalized().is_finite()));
    CHECK_FALSE((Quat{0.0, 0.0, 0.0, 0.0}.inverse().is_finite()));
}

TEST_CASE("Quat checked slerp and Euler conversion have C++ parity") {
    using termin::Quat;
    using termin::Vec3;

    const Quat a{0.0, 0.0, 0.0, 2.0};
    const Quat b = Quat::from_axis_angle(Vec3::unit_z(), 0.5 * 3.14159265358979323846);
    const Quat scaled_b{b.x * 3.0, b.y * 3.0, b.z * 3.0, b.w * 3.0};

    Quat cpp_result{9.0, 8.0, 7.0, 6.0};
    tc_quat c_result{9.0, 8.0, 7.0, 6.0};
    REQUIRE(Quat::try_slerp(a, scaled_b, 1.5, cpp_result));
    REQUIRE(tc_quat_try_slerp(a, scaled_b, 1.5, 1.0e-12, &c_result));
    CHECK(std::abs(cpp_result.x - c_result.x) < 1.0e-15);
    CHECK(std::abs(cpp_result.y - c_result.y) < 1.0e-15);
    CHECK(std::abs(cpp_result.z - c_result.z) < 1.0e-15);
    CHECK(std::abs(cpp_result.w - c_result.w) < 1.0e-15);
    CHECK(std::abs(cpp_result.norm() - 1.0) < 1.0e-15);

    const Quat antipodal{0.0, 0.0, 0.0, -4.0};
    REQUIRE(Quat::try_slerp(a, antipodal, 0.37, cpp_result));
    CHECK(std::abs(std::abs(cpp_result.dot(Quat::identity())) - 1.0) < 1.0e-15);

    const Quat sentinel{9.0, 8.0, 7.0, 6.0};
    cpp_result = sentinel;
    CHECK_FALSE(Quat::try_slerp(Quat{0.0, 0.0, 0.0, 0.0}, Quat::identity(), 0.5, cpp_result, 0.0));
    CHECK(cpp_result.x == sentinel.x);
    CHECK_FALSE(Quat::try_slerp(Quat::identity(), Quat::identity(),
                                std::numeric_limits<double>::quiet_NaN(), cpp_result));
    CHECK(cpp_result.x == sentinel.x);
    CHECK_FALSE(Quat::slerp(Quat{0.0, 0.0, 0.0, 0.0}, Quat::identity(), 0.5).is_finite());

    const Vec3 euler{0.37, -0.42, 0.81};
    Quat cpp_euler{9.0, 8.0, 7.0, 6.0};
    tc_quat c_euler{9.0, 8.0, 7.0, 6.0};
    REQUIRE(Quat::try_from_euler(euler, cpp_euler));
    REQUIRE(tc_quat_try_from_euler(euler, &c_euler));
    CHECK(std::abs(cpp_euler.x - c_euler.x) < 1.0e-15);
    CHECK(std::abs(cpp_euler.y - c_euler.y) < 1.0e-15);
    CHECK(std::abs(cpp_euler.z - c_euler.z) < 1.0e-15);
    CHECK(std::abs(cpp_euler.w - c_euler.w) < 1.0e-15);

    Vec3 cpp_recovered{9.0, 8.0, 7.0};
    tc_vec3 c_recovered{9.0, 8.0, 7.0};
    REQUIRE(cpp_euler.try_to_euler(cpp_recovered));
    REQUIRE(tc_quat_try_to_euler(c_euler, 1.0e-12, &c_recovered));
    CHECK(std::abs(cpp_recovered.x - c_recovered.x) < 1.0e-15);
    CHECK(std::abs(cpp_recovered.y - c_recovered.y) < 1.0e-15);
    CHECK(std::abs(cpp_recovered.z - c_recovered.z) < 1.0e-15);

    const Vec3 locked{0.4, 0.5 * 3.14159265358979323846, -0.7};
    const Quat locked_quat = Quat::from_euler(locked);
    REQUIRE(locked_quat.try_to_euler(cpp_recovered));
    CHECK(cpp_recovered.x == 0.0);
    CHECK(std::abs(cpp_recovered.y - 0.5 * 3.14159265358979323846) < 1.0e-15);
    const Quat locked_round_trip = Quat::from_euler(cpp_recovered);
    CHECK(std::abs(std::abs(locked_quat.dot(locked_round_trip)) - 1.0) < 1.0e-14);

    const termin::Pose3 pose = termin::Pose3::from_euler(euler);
    CHECK(std::abs(std::abs(pose.ang.dot(cpp_euler)) - 1.0) < 1.0e-15);
    const Vec3 pose_euler = pose.to_euler();
    CHECK(std::abs(pose_euler.x - euler.x) < 1.0e-14);
    CHECK(std::abs(pose_euler.y - euler.y) < 1.0e-14);
    CHECK(std::abs(pose_euler.z - euler.z) < 1.0e-14);

    cpp_euler = sentinel;
    CHECK_FALSE(Quat::try_from_euler(Vec3{std::numeric_limits<double>::quiet_NaN(), 0.0, 0.0}, cpp_euler));
    CHECK(cpp_euler.x == sentinel.x);
    cpp_recovered = {9.0, 8.0, 7.0};
    CHECK_FALSE((Quat{0.0, 0.0, 0.0, 0.0}.try_to_euler(cpp_recovered, 0.0)));
    CHECK(cpp_recovered.x == 9.0);
    CHECK_FALSE((Quat{0.0, 0.0, 0.0, 0.0}.to_euler().is_finite()));
}

TEST_CASE("Mat66 follows the canonical column-major matrix contract") {
    termin::Mat66 matrix;
    matrix(2, 4) = 7.5;

    CHECK(matrix.ptr()[2 * 6 + 4] == 7.5);
    CHECK(matrix(2, 4) == 7.5);
    CHECK(matrix(4, 2) == 0.0);

    const termin::Mat66 identity = termin::Mat66::identity();
    const termin::Mat66 product = matrix * identity;
    CHECK(product(2, 4) == 7.5);

    const termin::Mat66 transposed = matrix.transposed();
    CHECK(transposed(4, 2) == 7.5);

    const termin::Vec6 vector{1.0, 2.0, 3.0, 4.0, 5.0, 6.0};
    const termin::Vec6 transformed = matrix.transform(vector);
    CHECK(transformed[4] == 22.5);
}

TEST_CASE("Vec6 provides contiguous fixed-size vector operations") {
    const termin::Vec6 left{1.0, 2.0, 3.0, 4.0, 5.0, 6.0};
    const termin::Vec6 right{6.0, 5.0, 4.0, 3.0, 2.0, 1.0};

    CHECK(left.ptr()[3] == 4.0);
    CHECK(left.dot(right) == 56.0);
    CHECK(left.norm_squared() == 91.0);
    const termin::Vec6 sum{7.0, 7.0, 7.0, 7.0, 7.0, 7.0};
    CHECK((left + right) == sum);
    CHECK((left * 2.0)[5] == 12.0);
}

TEST_CASE("Screw3 scalar arithmetic and Vec6 order are explicit") {
    const termin::Screw3 screw{{2.0, 4.0, 6.0}, {8.0, 10.0, 12.0}};
    const termin::Screw3 half = screw / 2.0;
    CHECK(half.ang == termin::Vec3(1.0, 2.0, 3.0));
    CHECK(half.lin == termin::Vec3(4.0, 5.0, 6.0));

    const termin::Vec6 vw = termin::screw3_to_vec6_vw(screw);
    CHECK(vw == termin::Vec6(8.0, 10.0, 12.0, 2.0, 4.0, 6.0));
    const termin::Vec6 wv = termin::screw3_to_vec6_wv(screw);
    CHECK(wv == termin::Vec6(2.0, 4.0, 6.0, 8.0, 10.0, 12.0));
    CHECK(termin::screw3_from_vec6_vw(vw).ang == screw.ang);
    CHECK(termin::screw3_from_vec6_vw(vw).lin == screw.lin);
    CHECK(termin::screw3_from_vec6_wv(wv).ang == screw.ang);
    CHECK(termin::screw3_from_vec6_wv(wv).lin == screw.lin);
}

TEST_CASE("SE3 exponential and logarithm preserve coupled translation") {
    const termin::Screw3 tangent{
        {0.35, -0.2, 0.6},
        {1.25, -0.75, 0.4},
    };
    const termin::Pose3 pose = termin::se3_exp(tangent);
    const termin::Screw3 recovered = termin::se3_log(pose);
    CHECK((recovered.ang - tangent.ang).norm() < 1e-12);
    CHECK((recovered.lin - tangent.lin).norm() < 1e-12);
    CHECK((pose.lin - tangent.lin).norm() > 1e-3);

    const termin::Screw3 tiny{
        {1e-10, -2e-10, 3e-10},
        {4e-5, -5e-5, 6e-5},
    };
    const termin::Screw3 recovered_tiny = termin::se3_log(termin::se3_exp(tiny));
    CHECK((recovered_tiny.ang - tiny.ang).norm() < 1e-15);
    CHECK((recovered_tiny.lin - tiny.lin).norm() < 1e-15);
}

TEST_CASE("Screw3 adjoint and coadjoint preserve instantaneous power") {
    const termin::Pose3 frame{
        termin::Quat::from_axis_angle(termin::Vec3{0.2, -0.4, 0.7}.normalized(), 0.83),
        {4.0, -6.0, 2.5},
    };
    const termin::Screw3 twist{{0.5, -1.0, 2.0}, {4.0, 3.0, -2.0}};
    const termin::Screw3 wrench{{7.0, -4.0, 1.0}, {-2.0, 5.0, 3.0}};
    const termin::Screw3 transformed_twist = twist.transform_as_twist_by(frame);
    const termin::Screw3 transformed_wrench = wrench.transform_as_wrench_by(frame);
    CHECK(std::abs(transformed_twist.dot(transformed_wrench) - twist.dot(wrench)) < 1e-11);
    CHECK((transformed_twist.inverse_transform_as_twist_by(frame).ang - twist.ang).norm() < 1e-12);
    CHECK((transformed_twist.inverse_transform_as_twist_by(frame).lin - twist.lin).norm() < 1e-12);
    CHECK((transformed_wrench.inverse_transform_as_wrench_by(frame).ang - wrench.ang).norm() < 1e-12);
    CHECK((transformed_wrench.inverse_transform_as_wrench_by(frame).lin - wrench.lin).norm() < 1e-12);

    const termin::Vec3 arm{0.25, -0.5, 1.0};
    const termin::Screw3 point_twist = twist.velocity_at_offset(arm);
    const termin::Screw3 origin_wrench = wrench.wrench_at_origin_from_offset(arm);
    CHECK((point_twist.lin - (twist.lin + twist.ang.cross(arm))).norm() < 1e-12);
    CHECK((origin_wrench.ang - (wrench.ang + arm.cross(wrench.lin))).norm() < 1e-12);
    CHECK((point_twist.velocity_at_origin_from_offset(arm).lin - twist.lin).norm() < 1e-12);
    CHECK((origin_wrench.wrench_at_offset(arm).ang - wrench.ang).norm() < 1e-12);
}

TEST_CASE("SpatialInertia3 maps twists to momentum consistently") {
    const termin::SpatialInertia3 inertia{
        2.5,
        {3.0, 4.0, 5.0},
        {
            termin::Quat::from_axis_angle(termin::Vec3::unit_z(), 0.4),
            {0.5, -0.25, 0.75},
        },
    };
    CHECK(inertia.is_valid());

    const termin::Screw3 velocity{{0.3, -0.7, 1.1}, {2.0, -3.0, 4.0}};
    const termin::Screw3 momentum = inertia.momentum(velocity);
    const termin::Vec6 dense_momentum = inertia.matrix_vw().transform(termin::screw3_to_vec6_vw(velocity));
    const termin::Screw3 recovered = termin::screw3_from_vec6_vw(dense_momentum);
    CHECK((recovered.ang - momentum.ang).norm() < 1e-12);
    CHECK((recovered.lin - momentum.lin).norm() < 1e-12);
    CHECK(std::abs(inertia.kinetic_energy(velocity) - 0.5 * velocity.dot(momentum)) < 1e-12);

    const termin::Mat33 cross = termin::Mat33::cross_product(inertia.inertia_frame.lin);
    CHECK((cross.transform(velocity.lin) - inertia.inertia_frame.lin.cross(velocity.lin)).norm() < 1e-12);

    const termin::Pose3 frame{
        termin::Quat::from_axis_angle(termin::Vec3::unit_y(), 0.7),
        {3.0, -2.0, 1.0},
    };
    const termin::Screw3 velocity_world = velocity.transform_as_twist_by(frame);
    const termin::Screw3 momentum_world = inertia.transformed_by(frame).momentum(velocity_world);
    const termin::Screw3 expected_world = momentum.transform_as_wrench_by(frame);
    CHECK((momentum_world.ang - expected_world.ang).norm() < 1e-11);
    CHECK((momentum_world.lin - expected_world.lin).norm() < 1e-11);
}

TEST_CASE("tc_vec3 normalized non-zero vector remains unit length") {
    tc_vec3 normalized = tc_vec3{3.0, 4.0, 0.0}.normalized();

    CHECK(std::abs(normalized.x - 0.6) < 1.0e-12);
    CHECK(std::abs(normalized.y - 0.8) < 1.0e-12);
    CHECK(std::abs(normalized.z) < 1.0e-12);
}

TEST_CASE("Vec3 checked float narrowing is finite and transactional") {
    termin::Vec3f narrowed{7.0f, 8.0f, 9.0f};
    CHECK((termin::Vec3{1.25, -2.5, 3.75}.try_to_float(narrowed)));
    CHECK(narrowed == termin::Vec3f(1.25f, -2.5f, 3.75f));

    const termin::Vec3f unchanged = narrowed;
    CHECK((!termin::Vec3{std::numeric_limits<double>::max(), 0.0, 0.0}.try_to_float(narrowed)));
    CHECK(narrowed == unchanged);
    CHECK((!termin::Vec3{0.0, std::numeric_limits<double>::infinity(), 0.0}.try_to_float(narrowed)));
    CHECK(narrowed == unchanged);
    CHECK((!termin::Vec3{0.0, 0.0, std::numeric_limits<double>::quiet_NaN()}.try_to_float(narrowed)));
    CHECK(narrowed == unchanged);
    CHECK((!termin::Vec3{std::numeric_limits<double>::denorm_min(), 0.0, 0.0}.try_to_float(narrowed)));
    CHECK(narrowed == unchanged);
}

TEST_CASE("canonical vectors provide checked normalization and component operations") {
    const termin::Vec2 left2{-2.0, 8.0};
    const termin::Vec2 right2{4.0, 2.0};
    CHECK(left2.cwise_product(right2) == termin::Vec2(-8.0, 16.0));
    CHECK(left2.cwise_quotient(right2) == termin::Vec2(-0.5, 4.0));
    CHECK(left2.cwise_min(right2) == termin::Vec2(-2.0, 2.0));
    CHECK(left2.cwise_max(right2) == termin::Vec2(4.0, 8.0));
    CHECK(left2.clamped({-1.0, 3.0}, {2.0, 5.0}) == termin::Vec2(-1.0, 5.0));
    CHECK(left2.cwise_abs() == termin::Vec2(2.0, 8.0));
    CHECK(left2.min_component() == -2.0);
    CHECK(left2.max_component() == 8.0);
    CHECK(left2.ptr()[1] == 8.0);

    const termin::Vec2f left2f{-2.0f, 8.0f};
    CHECK(left2f.cwise_product({4.0f, 2.0f}) == termin::Vec2f(-8.0f, 16.0f));
    CHECK(left2f.clamped({-1.0f, 3.0f}, {2.0f, 5.0f}) == termin::Vec2f(-1.0f, 5.0f));
    termin::Vec2f vec2f_out{7.0f, 8.0f};
    CHECK(!termin::Vec2f::zero().try_normalized(vec2f_out));
    CHECK(vec2f_out == termin::Vec2f(7.0f, 8.0f));
    CHECK(left2f.to_double().to_float() == left2f);

    termin::Vec3 unchanged{7.0, 8.0, 9.0};
    CHECK(!termin::Vec3::zero().try_normalized(unchanged));
    CHECK(unchanged == termin::Vec3(7.0, 8.0, 9.0));
    CHECK((!termin::Vec3{std::numeric_limits<double>::infinity(), 0.0, 0.0}.try_normalized(unchanged)));
    CHECK(unchanged == termin::Vec3(7.0, 8.0, 9.0));
    CHECK(termin::Vec3::zero().normalized_or(termin::Vec3::unit_y()) == termin::Vec3::unit_y());

    termin::Vec3 normalized;
    CHECK((termin::Vec3{0.0, 3.0, 4.0}.try_normalized(normalized)));
    CHECK((normalized - termin::Vec3{0.0, 0.6, 0.8}).norm() < 1.0e-12);
    CHECK((termin::Vec3{-2.0, 4.0, -8.0}.cwise_abs() == termin::Vec3(2.0, 4.0, 8.0)));
    CHECK((termin::Vec3{2.0, 4.0, 8.0}.cwise_quotient({2.0, 2.0, 4.0}) == termin::Vec3(1.0, 2.0, 2.0)));
    CHECK((termin::Vec3{1.25, -2.5, 3.75}.to_float().to_double() == termin::Vec3(1.25, -2.5, 3.75)));

    termin::Vec3f vec3f_out{7.0f, 8.0f, 9.0f};
    CHECK(!termin::Vec3f::zero().try_normalized(vec3f_out));
    CHECK(vec3f_out == termin::Vec3f(7.0f, 8.0f, 9.0f));
    CHECK((termin::Vec3f{0.0f, 3.0f, 4.0f}.try_normalized(vec3f_out)));
    CHECK((vec3f_out - termin::Vec3f{0.0f, 0.6f, 0.8f}).norm() < 1.0e-6f);
    CHECK((termin::Vec3f{-2.0f, 4.0f, -8.0f}.cwise_abs() == termin::Vec3f(2.0f, 4.0f, 8.0f)));

    termin::Vec4 vec4_out{9.0, 8.0, 7.0, 6.0};
    CHECK(!termin::Vec4::zero().try_normalized(vec4_out));
    CHECK(vec4_out == termin::Vec4(9.0, 8.0, 7.0, 6.0));
    CHECK((termin::Vec4{1.0, 2.0, 3.0, 4.0}.ptr()[2] == 3.0));
    CHECK((termin::Vec4{1.0, 2.0, 3.0, 4.0}.to_float().to_double() == termin::Vec4(1.0, 2.0, 3.0, 4.0)));

    termin::Vec4f vec4f_out{9.0f, 8.0f, 7.0f, 6.0f};
    CHECK(!termin::Vec4f::zero().try_normalized(vec4f_out));
    CHECK(vec4f_out == termin::Vec4f(9.0f, 8.0f, 7.0f, 6.0f));
    CHECK(termin::Vec4f::zero().normalized_or(termin::Vec4f::unit_w()) == termin::Vec4f::unit_w());
}

TEST_CASE("Bounds2 and Rect2 make validity and edge inclusion explicit") {
    const termin::Bounds2 bounds{1.0, 2.0, 5.0, 8.0};
    CHECK(bounds.is_valid());
    CHECK(bounds.min() == termin::Vec2(1.0, 2.0));
    CHECK(bounds.max() == termin::Vec2(5.0, 8.0));
    CHECK(bounds.center() == termin::Vec2(3.0, 5.0));
    CHECK(bounds.contains_closed({5.0, 8.0}));
    CHECK(!bounds.contains_half_open({5.0, 8.0}));
    CHECK(bounds.expanded(1.0).min() == termin::Vec2(0.0, 1.0));
    termin::Bounds2 extended = bounds;
    extended.extend({-2.0, 10.0});
    CHECK(extended.min() == termin::Vec2(-2.0, 2.0));
    CHECK(extended.max() == termin::Vec2(5.0, 10.0));

    termin::Bounds2 intersection{20.0, 21.0, 22.0, 23.0};
    CHECK(bounds.try_intersection({4.0, 0.0, 10.0, 4.0}, intersection));
    CHECK(intersection.min() == termin::Vec2(4.0, 2.0));
    CHECK(intersection.max() == termin::Vec2(5.0, 4.0));
    const termin::Bounds2 previous = intersection;
    CHECK(!bounds.try_intersection({6.0, 9.0, 10.0, 12.0}, intersection));
    CHECK(intersection.min() == previous.min());
    CHECK(intersection.max() == previous.max());

    const termin::Rect2 rect = bounds.to_rect();
    CHECK(rect.is_valid());
    CHECK(rect.origin() == bounds.min());
    CHECK(rect.size() == termin::Vec2(4.0, 6.0));
    CHECK(rect.bounds().min() == bounds.min());
    CHECK(rect.contains_closed({5.0, 8.0}));
    CHECK(!rect.contains_half_open({5.0, 8.0}));
    CHECK(termin::Bounds2(bounds.to_float()).min() == bounds.min());
    CHECK(termin::Rect2(rect.to_float()).size() == rect.size());
    CHECK((!termin::Bounds2{2.0, 0.0, 1.0, 1.0}.is_valid()));
    CHECK((!termin::Rect2{0.0, 0.0, -1.0, 1.0}.is_valid()));

    const termin::Bounds2f bounds_f = bounds.to_float();
    CHECK(bounds_f.is_valid());
    CHECK(bounds_f.center() == termin::Vec2f(3.0f, 5.0f));
    CHECK(bounds_f.contains_closed({5.0f, 8.0f}));
    CHECK(!bounds_f.contains_half_open({5.0f, 8.0f}));
    termin::Bounds2f extended_f = bounds_f;
    extended_f.extend({-2.0f, 10.0f});
    CHECK(extended_f.min() == termin::Vec2f(-2.0f, 2.0f));
    CHECK(extended_f.max() == termin::Vec2f(5.0f, 10.0f));
    termin::Bounds2f intersection_f{20.0f, 21.0f, 22.0f, 23.0f};
    CHECK(bounds_f.try_intersection({4.0f, 0.0f, 10.0f, 4.0f}, intersection_f));
    CHECK(intersection_f.min() == termin::Vec2f(4.0f, 2.0f));
    CHECK(termin::Rect2f(rect.to_float()).bounds().min() == bounds_f.min());
    CHECK(termin::Rect2f(rect.to_float()).bounds().max() == bounds_f.max());
}

TEST_CASE("AABBf is a packed valid-by-default float bounds type") {
    static_assert(std::is_same_v<termin::AABBf, tc_aabbf>);
    static_assert(std::is_standard_layout_v<termin::AABBf>);
    static_assert(std::is_trivially_copyable_v<termin::AABBf>);

    termin::AABBf bounds;
    CHECK(bounds.is_valid());
    CHECK(bounds.min_point == termin::Vec3f::zero());
    CHECK(bounds.max_point == termin::Vec3f::zero());
    bounds.extend({-2.0f, 3.0f, -4.0f});
    bounds.extend({5.0f, 6.0f, 7.0f});
    CHECK(bounds.min_point == termin::Vec3f(-2.0f, 0.0f, -4.0f));
    CHECK(bounds.max_point == termin::Vec3f(5.0f, 6.0f, 7.0f));
    CHECK(bounds.contains({0.0f, 1.0f, 2.0f}));
    CHECK(bounds.project_point({20.0f, -3.0f, 2.0f}) == termin::Vec3f(5.0f, 0.0f, 2.0f));
    CHECK(bounds.expanded(1.0f).min_point == termin::Vec3f(-3.0f, -1.0f, -5.0f));
    const termin::Vec3f points[] = {{2.0f, 3.0f, 4.0f}, {-1.0f, 8.0f, 0.0f}};
    const termin::AABBf from_points = termin::AABBf::from_points(points, 2);
    CHECK(from_points.min_point == termin::Vec3f(-1.0f, 3.0f, 0.0f));
    CHECK(from_points.max_point == termin::Vec3f(2.0f, 8.0f, 4.0f));

    const termin::AABB invalid{{1.0, 0.0, 0.0}, {0.0, 1.0, 1.0}};
    CHECK(!invalid.is_valid());
    CHECK((termin::AABB{{0.0, 0.0, 0.0}, {1.0, 2.0, 3.0}}.expanded(2.0).max_point ==
           termin::Vec3(3.0, 4.0, 5.0)));
}

TEST_CASE("Ray3 is tc_ray3 alias and normalizes direction") {
    static_assert(std::is_same_v<termin::Ray3, tc_ray3>);

    termin::Ray3 ray{tc_vec3{1.0, 2.0, 3.0}, tc_vec3{0.0, 0.0, 2.0}};

    CHECK(std::abs(ray.direction.x) < 1.0e-12);
    CHECK(std::abs(ray.direction.y) < 1.0e-12);
    CHECK(std::abs(ray.direction.z - 1.0) < 1.0e-12);

    tc_vec3 point = ray.point_at(2.0);
    CHECK(std::abs(point.x - 1.0) < 1.0e-12);
    CHECK(std::abs(point.y - 2.0) < 1.0e-12);
    CHECK(std::abs(point.z - 5.0) < 1.0e-12);

    const termin::Ray3 zero_direction{{1.0, 2.0, 3.0}, termin::Vec3::zero()};
    CHECK(zero_direction.direction == termin::Vec3::zero());

    const termin::Ray3 non_finite_direction{
        {1.0, 2.0, 3.0},
        {std::numeric_limits<double>::quiet_NaN(), 4.0, 5.0},
    };
    CHECK(std::isnan(non_finite_direction.direction.x));
    CHECK(non_finite_direction.direction.y == 4.0);
    CHECK(non_finite_direction.direction.z == 5.0);
}

TEST_CASE("Ray3 plane intersection is checked and leaves failed output unchanged") {
    const termin::Vec3 sentinel{91.0, 92.0, 93.0};
    termin::Vec3 point = sentinel;
    const termin::Ray3 toward_plane{{1.0, 2.0, 3.0}, {0.0, 0.0, -2.0}};

    REQUIRE(termin::try_intersect_ray_plane(toward_plane, {0.0, 0.0, 0.0}, termin::Vec3::unit_z(), point, true));
    CHECK(point == termin::Vec3(1.0, 2.0, 0.0));

    const auto rejects_unchanged = [&](const termin::Ray3& ray,
                                       const termin::Vec3& plane_origin,
                                       const termin::Vec3& plane_normal,
                                       bool forward_only,
                                       double epsilon = 1.0e-10) {
        point = sentinel;
        CHECK_FALSE(termin::try_intersect_ray_plane(ray, plane_origin, plane_normal, point, forward_only, epsilon));
        CHECK(point == sentinel);
    };

    rejects_unchanged({{0.0, 0.0, 1.0}, {1.0, 0.0, 0.0}}, {0.0, 0.0, 0.0}, termin::Vec3::unit_z(), true);
    rejects_unchanged(toward_plane, {0.0, 0.0, 0.0}, termin::Vec3::zero(), true);
    rejects_unchanged(toward_plane, {0.0, 0.0, 0.0}, {0.0, 0.0, std::numeric_limits<double>::quiet_NaN()}, true);
    rejects_unchanged(toward_plane, {0.0, 0.0, std::numeric_limits<double>::infinity()}, termin::Vec3::unit_z(), true);
    rejects_unchanged(
        toward_plane, {0.0, 0.0, 0.0}, termin::Vec3::unit_z(), true, std::numeric_limits<double>::quiet_NaN());

    termin::Ray3 invalid_ray;
    invalid_ray.origin = {std::numeric_limits<double>::quiet_NaN(), 0.0, 0.0};
    rejects_unchanged(invalid_ray, {0.0, 0.0, 0.0}, termin::Vec3::unit_z(), true);
    invalid_ray.origin = termin::Vec3::zero();
    invalid_ray.direction = termin::Vec3::zero();
    rejects_unchanged(invalid_ray, {0.0, 0.0, 0.0}, termin::Vec3::unit_z(), true);

    const termin::Ray3 away_from_plane{{0.0, 0.0, 1.0}, termin::Vec3::unit_z()};
    rejects_unchanged(away_from_plane, {0.0, 0.0, 0.0}, termin::Vec3::unit_z(), true);
    REQUIRE(termin::try_intersect_ray_plane(away_from_plane, {0.0, 0.0, 0.0}, termin::Vec3::unit_z(), point, false));
    CHECK(point == termin::Vec3::zero());
}

TEST_CASE("Ray3 triangle intersection returns a ray parameter and closed barycentric coordinates") {
    const termin::Vec3 a{0.0, 0.0, 0.0};
    const termin::Vec3 b{1.0, 0.0, 0.0};
    const termin::Vec3 c{0.0, 1.0, 0.0};
    termin::RayTriangleHit hit{91.0, {92.0, 93.0, 94.0}, {95.0, 96.0, 97.0}};

    const termin::Ray3 face_ray{{0.2, 0.3, 1.0}, {0.0, 0.0, -2.0}};
    REQUIRE(termin::try_intersect_ray_triangle(face_ray, a, b, c, hit));
    CHECK(std::abs(hit.ray_parameter - 1.0) < 1.0e-12);
    CHECK((hit.barycentric - termin::Vec3{0.5, 0.2, 0.3}).norm() < 1.0e-12);
    CHECK(hit.normal == termin::Vec3::unit_z());
    CHECK((face_ray.point_at(hit.ray_parameter) - termin::Vec3{0.2, 0.3, 0.0}).norm() < 1.0e-12);

    REQUIRE(termin::try_intersect_ray_triangle(face_ray, a, c, b, hit));
    CHECK((hit.barycentric - termin::Vec3{0.5, 0.3, 0.2}).norm() < 1.0e-12);
    CHECK(hit.normal == termin::Vec3::down());

    REQUIRE(termin::try_intersect_ray_triangle({{0.5, 0.0, 1.0}, termin::Vec3::down()}, a, b, c, hit));
    CHECK((hit.barycentric - termin::Vec3{0.5, 0.5, 0.0}).norm() < 1.0e-12);
    REQUIRE(termin::try_intersect_ray_triangle({a, termin::Vec3::up()}, a, b, c, hit));
    CHECK(hit.ray_parameter == 0.0);
    CHECK(hit.barycentric == termin::Vec3(1.0, 0.0, 0.0));

    termin::Ray3 parameterized_ray;
    parameterized_ray.origin = {0.2, 0.3, 1.0};
    parameterized_ray.direction = {0.0, 0.0, -0.25};
    REQUIRE(termin::try_intersect_ray_triangle(parameterized_ray, a, b, c, hit));
    CHECK(std::abs(hit.ray_parameter - 4.0) < 1.0e-12);
    CHECK((parameterized_ray.point_at(hit.ray_parameter) - termin::Vec3{0.2, 0.3, 0.0}).norm() < 1.0e-12);

    const termin::Ray3 behind_ray{{0.2, 0.3, -1.0}, termin::Vec3::up()};
    const termin::Vec3 behind_a{0.0, 0.0, -2.0};
    const termin::Vec3 behind_b{1.0, 0.0, -2.0};
    const termin::Vec3 behind_c{0.0, 1.0, -2.0};
    CHECK_FALSE(termin::try_intersect_ray_triangle(behind_ray, behind_a, behind_b, behind_c, hit));
    REQUIRE(termin::try_intersect_ray_triangle(behind_ray, behind_a, behind_b, behind_c, hit, false));
    CHECK(std::abs(hit.ray_parameter + 1.0) < 1.0e-12);
}

TEST_CASE("Ray3 triangle intersection is scale-aware and leaves failed output unchanged") {
    const termin::RayTriangleHit sentinel{91.0, {92.0, 93.0, 94.0}, {95.0, 96.0, 97.0}};
    termin::RayTriangleHit hit = sentinel;
    const auto rejects_unchanged = [&](const termin::Ray3& ray,
                                       const termin::Vec3& a,
                                       const termin::Vec3& b,
                                       const termin::Vec3& c,
                                       double epsilon = 1.0e-10) {
        hit = sentinel;
        CHECK_FALSE(termin::try_intersect_ray_triangle(ray, a, b, c, hit, true, epsilon));
        CHECK(hit.ray_parameter == sentinel.ray_parameter);
        CHECK(hit.barycentric == sentinel.barycentric);
        CHECK(hit.normal == sentinel.normal);
    };

    const termin::Vec3 a{0.0, 0.0, 0.0};
    const termin::Vec3 b{1.0, 0.0, 0.0};
    const termin::Vec3 c{0.0, 1.0, 0.0};
    rejects_unchanged({{2.0, 2.0, 1.0}, termin::Vec3::down()}, a, b, c);
    rejects_unchanged({{0.25, 0.25, 1.0}, termin::Vec3::unit_x()}, a, b, c);
    rejects_unchanged({{0.25, 0.25, 1.0}, termin::Vec3::down()}, a, b, {2.0, 0.0, 0.0});
    rejects_unchanged({{0.25, 0.25, 1.0}, termin::Vec3::down()}, a, b, {0.0, 1.0e-12, 0.0});
    rejects_unchanged({{0.2, 0.3, 0.0}, {1.0, 0.0, -0.5e-6}}, a, b, c, 1.0e-6);
    REQUIRE(termin::try_intersect_ray_triangle({{0.2, 0.3, 0.0}, {1.0, 0.0, -2.0e-6}}, a, b, c, hit, true, 1.0e-6));
    CHECK(hit.ray_parameter == 0.0);

    REQUIRE(
        termin::try_intersect_ray_triangle({{-0.5e-6, 0.5, 1.0}, termin::Vec3::down()}, a, b, c, hit, true, 1.0e-6));
    CHECK(hit.barycentric.y == 0.0);
    rejects_unchanged({{-2.0e-6, 0.5, 1.0}, termin::Vec3::down()}, a, b, c, 1.0e-6);

    REQUIRE(
        termin::try_intersect_ray_triangle({{0.25, 0.25, 0.5e-6}, termin::Vec3::down()}, a, b, c, hit, true, 1.0e-6));
    CHECK(hit.ray_parameter > 0.0);
    CHECK(hit.ray_parameter < 1.0e-6);

    termin::Ray3 invalid_ray{{0.25, 0.25, 1.0}, termin::Vec3::down()};
    invalid_ray.direction = termin::Vec3::zero();
    rejects_unchanged(invalid_ray, a, b, c);
    invalid_ray.direction = {0.0, 0.0, std::numeric_limits<double>::quiet_NaN()};
    rejects_unchanged(invalid_ray, a, b, c);
    invalid_ray.origin = {0.25, 0.25, 1.0e-300};
    invalid_ray.direction = {0.0, 0.0, 1.0e300};
    rejects_unchanged(invalid_ray, a, b, c);
    invalid_ray.direction = {0.0, 0.0, -1.0e300};
    rejects_unchanged(invalid_ray, a, b, c);
    invalid_ray.origin = {0.2e-20, 0.3e-20, 1.0e-20};
    invalid_ray.direction = {0.0, 0.0, -1.0e300};
    rejects_unchanged(invalid_ray, a, {1.0e-20, 0.0, 0.0}, {0.0, 1.0e-20, 0.0});
    rejects_unchanged(
        {{0.25, 0.25, 1.0}, termin::Vec3::down()}, {std::numeric_limits<double>::infinity(), 0.0, 0.0}, b, c);
    rejects_unchanged({{0.25, 0.25, 1.0}, termin::Vec3::down()}, a, b, c, std::numeric_limits<double>::quiet_NaN());
    rejects_unchanged({{0.25, 0.25, 1.0}, termin::Vec3::down()}, a, b, c, -1.0);
    rejects_unchanged({{0.25, 0.25, 1.0}, termin::Vec3::down()},
                      {std::numeric_limits<double>::max(), 0.0, 0.0},
                      {-std::numeric_limits<double>::max(), 0.0, 0.0},
                      c);

    for (const double scale : {1.0e-120, 1.0e120}) {
        const termin::Ray3 ray{{0.2 * scale, 0.3 * scale, scale}, termin::Vec3::down()};
        REQUIRE(termin::try_intersect_ray_triangle(ray, a, {scale, 0.0, 0.0}, {0.0, scale, 0.0}, hit));
        CHECK(std::abs(hit.ray_parameter / scale - 1.0) < 1.0e-12);
        CHECK((hit.barycentric - termin::Vec3{0.5, 0.2, 0.3}).norm() < 1.0e-12);
    }

    const double world = 1.0e12;
    const termin::Ray3 large_world_ray{{world + 1.0, world + 1.0, world + 8.0}, termin::Vec3::down()};
    REQUIRE(termin::try_intersect_ray_triangle(
        large_world_ray, {world, world, world}, {world + 4.0, world, world}, {world, world + 4.0, world}, hit));
    CHECK(std::abs(hit.ray_parameter - 8.0) < 1.0e-12);
    CHECK((hit.barycentric - termin::Vec3{0.5, 0.25, 0.25}).norm() < 1.0e-12);
}

TEST_CASE("base geometry value types preserve simple construction semantics") {
    static_assert(std::is_standard_layout_v<termin::SrgbColor>);
    static_assert(std::is_same_v<termin::Vec2f, tc_vec2f>);
    static_assert(std::is_same_v<termin::Size2f, tc_size2f>);
    static_assert(std::is_same_v<termin::Bounds2f, tc_bounds2f>);
    static_assert(std::is_same_v<termin::Rect2f, tc_rect2f>);
    static_assert(std::is_same_v<termin::Affine2f, tc_affine2f>);
    static_assert(std::is_same_v<termin::Basis3d, tc_basis3d>);
    static_assert(std::is_same_v<termin::Affine3d, tc_affine3d>);
    static_assert(std::is_standard_layout_v<termin::Size2i>);
    static_assert(std::is_standard_layout_v<termin::Size2f>);
    static_assert(std::is_standard_layout_v<termin::Bounds2i>);
    static_assert(std::is_standard_layout_v<termin::Bounds2>);
    static_assert(std::is_standard_layout_v<termin::Bounds2f>);
    static_assert(std::is_standard_layout_v<termin::Rect2i>);
    static_assert(std::is_standard_layout_v<termin::Rect2>);
    static_assert(std::is_standard_layout_v<termin::Rect2f>);

    termin::SrgbColor color = termin::SrgbColor::green();
    CHECK(color.r == 0.0f);
    CHECK(color.g == 1.0f);
    CHECK(color.b == 0.0f);
    CHECK(color.a == 1.0f);

    termin::Size2i size{320, 240};
    termin::Bounds2i rect = termin::Bounds2i::from_size(size);

    CHECK(size == termin::Size2i(320, 240));
    CHECK(rect.x0 == 0);
    CHECK(rect.y0 == 0);
    CHECK(rect.x1 == 320);
    CHECK(rect.y1 == 240);
    CHECK(rect.width() == 320);
    CHECK(rect.height() == 240);

    termin::Rect2i viewport{10, 20, 320, 240};
    CHECK(viewport.x == 10);
    CHECK(viewport.y == 20);
    CHECK(viewport.width == 320);
    CHECK(viewport.height == 240);

    const termin::Rect2 precise_viewport{0.25, 0.5, 800.125, 600.25};
    const termin::Bounds2 precise_bounds = precise_viewport.bounds();
    CHECK(precise_bounds.x0 == 0.25);
    CHECK(precise_bounds.y0 == 0.5);
    CHECK(precise_bounds.x1 == 800.375);
    CHECK(precise_bounds.y1 == 600.75);

    termin::Rect2f rect_f{1.5f, 2.0f, 3.25f, 4.5f};
    termin::Bounds2f bounds_f = rect_f.bounds();
    CHECK(bounds_f.x0 == 1.5f);
    CHECK(bounds_f.y0 == 2.0f);
    CHECK(bounds_f.x1 == 4.75f);
    CHECK(bounds_f.y1 == 6.5f);
    CHECK(bounds_f.width() == 3.25f);
    CHECK(bounds_f.height() == 4.5f);

    termin::Size2f size_f{640.0f, 480.0f};
    CHECK(size_f == termin::Size2f(640.0f, 480.0f));
}

TEST_CASE("Mat44 determinant supports double and float matrices") {
    const termin::Mat44 matrix = termin::Mat44::translation({3.0, -2.0, 7.0}) *
                                  termin::Mat44::scale({2.0, 3.0, 4.0});
    CHECK(std::abs(matrix.determinant() - 24.0) < 1.0e-12);

    const termin::Mat44 singular = termin::Mat44::scale({2.0, 0.0, 4.0});
    CHECK(singular.determinant() == 0.0);

    const termin::Mat44 small_but_invertible = termin::Mat44::scale({1.0e-12, 2.0, 3.0});
    const termin::Mat44 inverse = small_but_invertible.inverse();
    CHECK(std::abs(inverse(0, 0) - 1.0e12) < 1.0e-3);

    const termin::Mat44f matrix_f = termin::Mat44f::translation(3.0f, -2.0f, 7.0f) *
                                    termin::Mat44f::scale(termin::Vec3{2.0, 3.0, 4.0});
    CHECK(std::abs(matrix_f.determinant() - 24.0f) < 1.0e-5f);
}

TEST_CASE("Mat44 checked transforms and inverse preserve output on failure") {
    const termin::Mat44 matrix = termin::Mat44::translation({3.0, -2.0, 7.0}) * termin::Mat44::scale({2.0, 3.0, 4.0});
    const termin::Vec4 homogeneous = matrix.transform_homogeneous({1.0, 2.0, 3.0, 1.0});
    CHECK(homogeneous == termin::Vec4(5.0, 4.0, 19.0, 1.0));

    termin::Vec3 transformed{9.0, 8.0, 7.0};
    CHECK(termin::Mat44::identity().try_transform_point({1.0, 2.0, 3.0}, transformed));
    CHECK(transformed == termin::Vec3(1.0, 2.0, 3.0));
    const termin::Vec3 previous = transformed;
    CHECK(!termin::Mat44::zero().try_transform_point({1.0, 2.0, 3.0}, transformed));
    CHECK(transformed == previous);

    termin::Mat44 inverse = termin::Mat44::translation({9.0, 8.0, 7.0});
    CHECK(!termin::Mat44::scale({1.0, 0.0, 1.0}).try_inverse(inverse));
    CHECK(inverse.get_translation() == termin::Vec3(9.0, 8.0, 7.0));

    termin::Mat44 non_finite = termin::Mat44::identity();
    non_finite(2, 1) = std::numeric_limits<double>::infinity();
    CHECK(!non_finite.is_finite());
    CHECK(!non_finite.try_inverse(inverse));
    CHECK(inverse.get_translation() == termin::Vec3(9.0, 8.0, 7.0));

    const termin::Mat44f matrix_f = matrix.to_float();
    CHECK(matrix_f.transform_homogeneous({1.0f, 2.0f, 3.0f, 1.0f}) == termin::Vec4f(5.0f, 4.0f, 19.0f, 1.0f));
    termin::Vec3f transformed_f{9.0f, 8.0f, 7.0f};
    CHECK(termin::Mat44f::identity().try_transform_point({1.0f, 2.0f, 3.0f}, transformed_f));
    CHECK(transformed_f == termin::Vec3f(1.0f, 2.0f, 3.0f));
    const termin::Vec3f previous_f = transformed_f;
    CHECK(!termin::Mat44f::zero().try_transform_point({1.0f, 2.0f, 3.0f}, transformed_f));
    CHECK(transformed_f == previous_f);

    termin::Mat44f inverse_f = termin::Mat44f::translation(9.0f, 8.0f, 7.0f);
    CHECK(!termin::Mat44f::scale(termin::Vec3{1.0, 0.0, 1.0}).try_inverse(inverse_f));
    CHECK(inverse_f.get_translation() == termin::Vec3(9.0, 8.0, 7.0));
    CHECK(matrix_f.try_inverse(inverse_f));
    CHECK((inverse_f.transform_point(matrix_f.transform_point({1.0f, 2.0f, 3.0f})) -
           termin::Vec3f{1.0f, 2.0f, 3.0f})
              .norm() < 1.0e-5f);
}

TEST_CASE("Mat44 checked inverse uses relative scale and raw bridges stay explicit") {
    termin::Mat44 uniformly_small = termin::Mat44::zero();
    uniformly_small(0, 0) = 1.0e-20;
    uniformly_small(1, 1) = 2.0e-20;
    uniformly_small(2, 2) = 3.0e-20;
    uniformly_small(3, 3) = 4.0e-20;
    termin::Mat44 uniformly_small_inverse;
    CHECK(uniformly_small.try_inverse(uniformly_small_inverse));
    const termin::Mat44 product = uniformly_small * uniformly_small_inverse;
    for (int column = 0; column < 4; ++column) {
        for (int row = 0; row < 4; ++row) {
            CHECK(std::abs(product(column, row) - (column == row ? 1.0 : 0.0)) < 1.0e-12);
        }
    }

    const double raw64[16] = {
        1.0, 2.0, 3.0, 4.0,
        5.0, 6.0, 7.0, 8.0,
        9.0, 10.0, 11.0, 12.0,
        13.0, 14.0, 15.0, 16.0,
    };
    const termin::Mat44 from64 = termin::Mat44::from_column_major_f64(raw64);
    CHECK(from64(2, 1) == 10.0);
    double copied[16]{};
    from64.copy_column_major_to(copied);
    CHECK(copied[9] == 10.0);

    const tc_mat44 c_matrix = from64.to_tc_mat44();
    CHECK(c_matrix.m[9] == 10.0);
    CHECK(termin::Mat44::from_tc_mat44(c_matrix)(2, 1) == 10.0);

    const float raw32[16] = {
        1.0f, 2.0f, 3.0f, 4.0f,
        5.0f, 6.0f, 7.0f, 8.0f,
        9.0f, 10.0f, 11.0f, 12.0f,
        13.0f, 14.0f, 15.0f, 16.0f,
    };
    CHECK(termin::Mat44::from_column_major_f32(raw32)(2, 1) == 10.0);
    const termin::Mat44f from32 = termin::Mat44f::from_column_major_f32(raw32);
    CHECK(from32.transform_homogeneous({1.0f, 0.0f, 0.0f, 0.0f}) == termin::Vec4f(1.0f, 2.0f, 3.0f, 4.0f));
    CHECK(from32.to_double()(2, 1) == 10.0);

    const termin::Mat44 large_world_view_projection =
        termin::Mat44::perspective(1.1, 16.0 / 9.0, 0.1, 5000.0) *
        termin::Mat44::translation({-1.0e6, 2.0e6, -3.0e6});
    termin::Mat44 large_world_inverse;
    CHECK(large_world_view_projection.try_inverse(large_world_inverse));
    const termin::Vec3 world_point{1.0e6 + 2.0, -2.0e6 + 10.0, 3.0e6 - 4.0};
    const termin::Vec3 projected = large_world_view_projection.transform_point(world_point);
    const termin::Vec3 round_trip = large_world_inverse.transform_point(projected);
    CHECK((round_trip - world_point).norm() < 1.0e-5);
}

TEST_CASE("Mat44f checked inverse validates both products at large world coordinates") {
    const termin::Mat44f large_translation =
        termin::Mat44f::translation(termin::Vec3{-30000.0, 60000.0, -90000.0});
    termin::Mat44f large_translation_inverse;
    CHECK(large_translation.try_inverse(large_translation_inverse));

    const termin::Mat44f translation_left_identity = large_translation * large_translation_inverse;
    const termin::Mat44f translation_right_identity = large_translation_inverse * large_translation;
    for (int column = 0; column < 4; ++column) {
        for (int row = 0; row < 4; ++row) {
            const float expected = column == row ? 1.0f : 0.0f;
            CHECK(std::abs(translation_left_identity(column, row) - expected) < 1.0e-6f);
            CHECK(std::abs(translation_right_identity(column, row) - expected) < 1.0e-6f);
        }
    }

    const termin::Mat44f ill_conditioned =
        termin::Mat44f::perspective(1.1f, 16.0f / 9.0f, 0.1f, 5000.0f) * large_translation;
    termin::Mat44f unchanged = termin::Mat44f::translation(7.0f, 8.0f, 9.0f);
    const termin::Mat44f expected_unchanged = unchanged;
    CHECK(!ill_conditioned.try_inverse(unchanged));
    for (int i = 0; i < 16; ++i) {
        CHECK(unchanged.data[i] == expected_unchanged.data[i]);
    }

    CHECK(!termin::Mat44f::scale(termin::Vec3{1.0, 0.0, 1.0}).try_inverse(unchanged));
    for (int i = 0; i < 16; ++i) {
        CHECK(unchanged.data[i] == expected_unchanged.data[i]);
    }

    const termin::Mat44 double_precision =
        termin::Mat44::perspective(1.1, 16.0 / 9.0, 0.1, 5000.0) *
        termin::Mat44::translation(termin::Vec3{-30000.0, 60000.0, -90000.0});
    termin::Mat44 double_inverse;
    CHECK(double_precision.try_inverse(double_inverse));
    const termin::Mat44 double_left_identity = double_precision * double_inverse;
    const termin::Mat44 double_right_identity = double_inverse * double_precision;
    for (int column = 0; column < 4; ++column) {
        for (int row = 0; row < 4; ++row) {
            const double expected = column == row ? 1.0 : 0.0;
            CHECK(std::abs(double_left_identity(column, row) - expected) < 1.0e-8);
            CHECK(std::abs(double_right_identity(column, row) - expected) < 1.0e-8);
        }
    }
}

TEST_CASE("Mat44 checked inverse refines large translation candidates") {
    const termin::Mat44 large_translation = termin::Mat44::translation(termin::Vec3{1.0e12, -2.0e12, 3.0e12});
    termin::Mat44 large_translation_inverse;
    CHECK(large_translation.try_inverse(large_translation_inverse));

    const termin::Mat44 left_identity = large_translation * large_translation_inverse;
    const termin::Mat44 right_identity = large_translation_inverse * large_translation;
    for (int column = 0; column < 4; ++column) {
        for (int row = 0; row < 4; ++row) {
            const double expected = column == row ? 1.0 : 0.0;
            CHECK(left_identity(column, row) == expected);
            CHECK(right_identity(column, row) == expected);
        }
    }
}

TEST_CASE("Mat44f checked inverse refines million-unit translation candidates") {
    const termin::Mat44f large_translation = termin::Mat44f::translation(termin::Vec3{1.0e6, -2.0e6, 3.0e6});
    termin::Mat44f large_translation_inverse;
    CHECK(large_translation.try_inverse(large_translation_inverse));

    const termin::Mat44f left_identity = large_translation * large_translation_inverse;
    const termin::Mat44f right_identity = large_translation_inverse * large_translation;
    for (int column = 0; column < 4; ++column) {
        for (int row = 0; row < 4; ++row) {
            const float expected = column == row ? 1.0f : 0.0f;
            CHECK(left_identity(column, row) == expected);
            CHECK(right_identity(column, row) == expected);
        }
    }
}

TEST_CASE("Affine2f composes arbitrary affine transforms exactly") {
    constexpr float half_pi = 1.57079632679489661923f;
    const termin::Affine2f parent = termin::Affine2f::translation(5.0f, -3.0f) * termin::Affine2f::scaling(2.0f, 0.5f);
    const termin::Affine2f child = termin::Affine2f::rotation(half_pi / 2.0f) * termin::Affine2f::shear(0.25f, -0.4f);
    const termin::Vec2f point{3.0f, -2.0f};

    const termin::Vec2f sequential = parent.transform_point(child.transform_point(point));
    const termin::Vec2f composed = (parent * child).transform_point(point);

    CHECK(std::abs(composed.x - sequential.x) < 1.0e-5f);
    CHECK(std::abs(composed.y - sequential.y) < 1.0e-5f);

    const termin::Affine2f third = termin::Affine2f::trs({-1.0f, 4.0f}, -0.3f, {-2.0f, 1.25f});
    const termin::Vec2f left = ((parent * child) * third).transform_point(point);
    const termin::Vec2f right = (parent * (child * third)).transform_point(point);
    CHECK(std::abs(left.x - right.x) < 1.0e-5f);
    CHECK(std::abs(left.y - right.y) < 1.0e-5f);
}

TEST_CASE("Affine2f inverse is explicit and round trips reflections") {
    const termin::Affine2f affine = termin::Affine2f::translation(7.0f, -5.0f) * termin::Affine2f::rotation(0.37f) *
                                    termin::Affine2f::scaling(-2.0f, 0.75f) * termin::Affine2f::shear(0.3f, -0.2f);
    termin::Affine2f inverse;
    CHECK(affine.try_inverse(inverse));

    const termin::Vec2f point{8.0f, -1.5f};
    const termin::Vec2f round_trip = inverse.transform_point(affine.transform_point(point));
    CHECK(std::abs(round_trip.x - point.x) < 1.0e-4f);
    CHECK(std::abs(round_trip.y - point.y) < 1.0e-4f);

    termin::Affine2f unchanged = termin::Affine2f::translation(9.0f, 11.0f);
    const termin::Affine2f singular = termin::Affine2f::scaling(0.0f, 2.0f);
    CHECK(!singular.try_inverse(unchanged));
    CHECK(unchanged.tx == 9.0f);
    CHECK(unchanged.ty == 11.0f);
}

TEST_CASE("Affine2f transforms all bounds corners") {
    const termin::Affine2f affine = termin::Affine2f::rotation(0.5f) * termin::Affine2f::shear(0.6f, -0.25f);
    const termin::Bounds2f bounds{-2.0f, -1.0f, 3.0f, 4.0f};
    const termin::Bounds2f transformed = affine.transform_bounds(bounds);

    const termin::Vec2f corners[] = {
        {-2.0f, -1.0f},
        {3.0f, -1.0f},
        {-2.0f, 4.0f},
        {3.0f, 4.0f},
    };
    for (const termin::Vec2f& corner : corners) {
        const termin::Vec2f p = affine.transform_point(corner);
        CHECK(p.x >= transformed.x0 - 1.0e-5f);
        CHECK(p.x <= transformed.x1 + 1.0e-5f);
        CHECK(p.y >= transformed.y0 - 1.0e-5f);
        CHECK(p.y <= transformed.y1 + 1.0e-5f);
    }
}

TEST_CASE("Affine2f conversion preserves the rigid Pose2 contract") {
    const termin::Pose2 pose{0.75, {4.0, -6.0}};
    const termin::Affine2f affine = termin::Affine2f::from_pose2(pose);
    const termin::Vec2f point{2.0f, 3.0f};
    const termin::Vec2 pose_result = pose.transform_point(point.to_double());
    const termin::Vec2f affine_result = affine.transform_point(point);

    CHECK(std::abs(affine_result.x - static_cast<float>(pose_result.x)) < 1.0e-5f);
    CHECK(std::abs(affine_result.y - static_cast<float>(pose_result.y)) < 1.0e-5f);
}

namespace {

    bool affine3_near_vec(const termin::Vec3& a, const termin::Vec3& b, double epsilon = 1.0e-10) {
        return std::abs(a.x - b.x) <= epsilon && std::abs(a.y - b.y) <= epsilon && std::abs(a.z - b.z) <= epsilon;
    }

} // namespace

TEST_CASE("Basis3d checked inverse is unit independent and normal transform is semantic") {
    for (const double uniform_scale : {1.0e-6, 1.0e6}) {
        const termin::Basis3d basis = termin::Basis3d::scaling(uniform_scale);
        termin::Basis3d inverse;
        REQUIRE(basis.try_inverse(inverse));
        const termin::Basis3d product = basis * inverse;
        CHECK(affine3_near_vec(product.x, termin::Vec3::unit_x(), 1.0e-12));
        CHECK(affine3_near_vec(product.y, termin::Vec3::unit_y(), 1.0e-12));
        CHECK(affine3_near_vec(product.z, termin::Vec3::unit_z(), 1.0e-12));
    }

    const termin::Basis3d mixed_axes =
        termin::Basis3d::from_quat(termin::Quat::from_axis_angle(termin::Vec3::unit_z(), 0.7853981633974483));
    const termin::Basis3d unreliable = mixed_axes * termin::Basis3d::scaling(1.0e-16, 1.0e16, 1.0) * mixed_axes;
    termin::Basis3d unchanged{{9.0, 8.0, 7.0}, {6.0, 5.0, 4.0}, {3.0, 2.0, 1.0}};
    const termin::Basis3d expected_unchanged = unchanged;
    CHECK_FALSE(unreliable.try_inverse(unchanged));
    CHECK(unchanged.x == expected_unchanged.x);
    CHECK(unchanged.y == expected_unchanged.y);
    CHECK(unchanged.z == expected_unchanged.z);
    CHECK_FALSE(termin::Basis3d::identity().try_inverse(unchanged, -1.0));
    CHECK_FALSE(termin::Basis3d::identity().try_inverse(unchanged, std::numeric_limits<double>::quiet_NaN()));
    CHECK(unchanged.x == expected_unchanged.x);

    const termin::Basis3d oriented_nonuniform =
        termin::Basis3d::from_quat(termin::Quat::from_axis_angle(termin::Vec3{1.0, 2.0, -0.5}.normalized(), 0.71)) *
        termin::Basis3d::scaling(2.0, 3.0, 4.0);
    const termin::Vec3 local_tangent0{1.0, 2.0, -0.5};
    const termin::Vec3 local_tangent1{-0.3, 0.4, 1.2};
    const termin::Vec3 local_normal = local_tangent0.cross(local_tangent1);
    termin::Vec3 transformed_normal{99.0, 98.0, 97.0};
    REQUIRE(oriented_nonuniform.try_transform_normal(local_normal, transformed_normal));
    CHECK(std::abs(transformed_normal.dot(oriented_nonuniform.transform_vector(local_tangent0))) < 1.0e-12);
    CHECK(std::abs(transformed_normal.dot(oriented_nonuniform.transform_vector(local_tangent1))) < 1.0e-12);

    const termin::Affine3d affine{oriented_nonuniform, {1.0e12, -2.0e12, 3.0e12}};
    termin::Vec3 affine_normal;
    REQUIRE(affine.try_transform_normal(local_normal, affine_normal));
    CHECK(affine3_near_vec(affine_normal, transformed_normal, 1.0e-12));

    termin::Vec3 raw_normal;
    REQUIRE(termin::Basis3d::scaling(2.0, 3.0, 4.0).try_transform_normal({0.0, 0.0, 2.0}, raw_normal));
    CHECK(raw_normal == termin::Vec3(0.0, 0.0, 0.5));

    const termin::Vec3 normal_sentinel{99.0, 98.0, 97.0};
    transformed_normal = normal_sentinel;
    CHECK_FALSE(
        termin::Basis3d::scaling(1.0, 0.0, 1.0).try_transform_normal(termin::Vec3::unit_z(), transformed_normal));
    CHECK(transformed_normal == normal_sentinel);
    CHECK_FALSE(termin::Basis3d::identity().try_transform_normal({std::numeric_limits<double>::quiet_NaN(), 0.0, 0.0},
                                                                 transformed_normal));
    CHECK(transformed_normal == normal_sentinel);
}

TEST_CASE("Affine3d preserves hierarchy-generated shear exactly") {
    const termin::Affine3d parent =
        termin::Affine3d::from_translation(5.0, -3.0, 2.0) * termin::Affine3d::scaling(2.0, 0.5, 1.25);
    const termin::Affine3d child = termin::Affine3d::trs(
        {-1.0, 4.0, 0.75}, termin::Quat::from_axis_angle(termin::Vec3::unit_z(), 0.63), {0.8, 1.4, 2.0});
    const termin::Affine3d composed = parent * child;
    const termin::Vec3 point{3.0, -2.0, 1.5};

    CHECK(affine3_near_vec(composed.transform_point(point), parent.transform_point(child.transform_point(point))));
    CHECK(std::abs(composed.basis.x.dot(composed.basis.y)) > 1.0e-3);

    double matrix[16];
    composed.matrix4(matrix);
    termin::Affine3d from_matrix;
    CHECK(termin::Affine3d::try_from_matrix4(matrix, from_matrix));
    CHECK(affine3_near_vec(from_matrix.transform_point(point), composed.transform_point(point)));
}

TEST_CASE("Affine3d TRS conversion matches the existing public matrix convention") {
    const termin::GeneralPose3 pose{termin::Quat::from_axis_angle(termin::Vec3{0.2, -0.4, 0.7}.normalized(), 0.83),
                                    {4.0, -6.0, 2.5},
                                    {-2.0, 0.75, 1.5}};
    const termin::Affine3d affine = termin::Affine3d::from_general_pose3(pose);

    double expected[16];
    double actual[16];
    pose.matrix4(expected);
    affine.matrix4(actual);
    for (int i = 0; i < 16; ++i) {
        CHECK(std::abs(actual[i] - expected[i]) < 1.0e-12);
    }

    const termin::Vec3 point{1.5, -2.0, 0.25};
    CHECK(affine3_near_vec(affine.transform_point(point), pose.transform_point(point), 1.0e-12));
}

TEST_CASE("Affine3d randomized composition and inverse match sequential transforms") {
    std::mt19937_64 rng(0xAFF13DULL);
    std::uniform_real_distribution<double> position(-10.0, 10.0);
    std::uniform_real_distribution<double> axis_component(-1.0, 1.0);
    std::uniform_real_distribution<double> angle(-3.0, 3.0);
    std::uniform_real_distribution<double> positive_scale(0.25, 3.0);

    auto random_affine = [&]() {
        termin::Vec3 axis{axis_component(rng), axis_component(rng), axis_component(rng)};
        if (axis.norm_squared() < 1.0e-6) {
            axis = termin::Vec3::unit_x();
        } else {
            axis = axis.normalized();
        }

        termin::Vec3 scale{positive_scale(rng), positive_scale(rng), positive_scale(rng)};
        if ((rng() & 1U) != 0U) {
            scale.x = -scale.x;
        }
        if ((rng() & 2U) != 0U) {
            scale.y = -scale.y;
        }

        return termin::Affine3d::trs(
            {position(rng), position(rng), position(rng)}, termin::Quat::from_axis_angle(axis, angle(rng)), scale);
    };

    for (int iteration = 0; iteration < 256; ++iteration) {
        const termin::Affine3d first = random_affine();
        const termin::Affine3d second = random_affine();
        const termin::Affine3d third = random_affine();
        const termin::Vec3 point{position(rng), position(rng), position(rng)};
        const termin::Vec3 vector{axis_component(rng), axis_component(rng), axis_component(rng)};

        const termin::Affine3d composed = first * second;
        CHECK(affine3_near_vec(
            composed.transform_point(point), first.transform_point(second.transform_point(point)), 1.0e-9));
        CHECK(affine3_near_vec(
            composed.transform_vector(vector), first.transform_vector(second.transform_vector(vector)), 1.0e-9));

        CHECK(affine3_near_vec(((first * second) * third).transform_point(point),
                               (first * (second * third)).transform_point(point),
                               1.0e-8));

        termin::Affine3d inverse;
        CHECK(composed.try_inverse(inverse));
        CHECK(affine3_near_vec(inverse.transform_point(composed.transform_point(point)), point, 1.0e-8));
        CHECK(affine3_near_vec(inverse.transform_vector(composed.transform_vector(vector)), vector, 1.0e-8));
    }
}

TEST_CASE("Affine3d inverse and matrix import fail without modifying output") {
    termin::Affine3d unchanged = termin::Affine3d::from_translation(9.0, 11.0, 13.0);
    CHECK(!termin::Affine3d::scaling(0.0, 2.0, 3.0).try_inverse(unchanged));
    CHECK(unchanged.translation == termin::Vec3(9.0, 11.0, 13.0));

    double projective[16] = {
        1.0,
        0.0,
        0.0,
        0.25,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        2.0,
        3.0,
        4.0,
        1.0,
    };
    CHECK(!termin::Affine3d::try_from_matrix4(projective, unchanged));
    CHECK(unchanged.translation == termin::Vec3(9.0, 11.0, 13.0));

    projective[3] = 0.0;
    CHECK(!termin::Affine3d::try_from_matrix4(projective, unchanged, -1.0));
    CHECK(!termin::Affine3d::try_from_matrix4(projective, unchanged, std::numeric_limits<double>::quiet_NaN()));
    CHECK(unchanged.translation == termin::Vec3(9.0, 11.0, 13.0));
}

TEST_CASE("world2d maps double positions between Vec2 and the canonical XZ plane") {
    constexpr termin::Vec2 position_2d{2.5, -4.0};
    constexpr termin::Vec3 position_world = termin::world2d::position_to_world(position_2d, 7.25);

    static_assert(position_world.x == 2.5);
    static_assert(position_world.y == 7.25);
    static_assert(position_world.z == -4.0);

    constexpr termin::Vec2 round_trip = termin::world2d::position_from_world(position_world);
    static_assert(round_trip.x == position_2d.x);
    static_assert(round_trip.y == position_2d.y);
    static_assert(termin::world2d::depth_from_world(position_world) == 7.25);

    constexpr termin::Vec3 moved_in_depth = termin::world2d::with_world_depth(position_world, -3.0);
    static_assert(moved_in_depth.x == position_world.x);
    static_assert(moved_in_depth.y == -3.0);
    static_assert(moved_in_depth.z == position_world.z);

    CHECK(round_trip == position_2d);
}

TEST_CASE("world2d maps vectors without injecting world depth") {
    constexpr termin::Vec2 vector_2d{-1.5, 3.0};
    constexpr termin::Vec3 vector_world = termin::world2d::vector_to_world(vector_2d);

    static_assert(vector_world.x == -1.5);
    static_assert(vector_world.y == 0.0);
    static_assert(vector_world.z == 3.0);

    constexpr termin::Vec2 round_trip = termin::world2d::vector_from_world(vector_world);
    static_assert(round_trip.x == vector_2d.x);
    static_assert(round_trip.y == vector_2d.y);

    CHECK(round_trip == vector_2d);
}

TEST_CASE("world2d float helpers preserve the canonical basis and depth") {
    constexpr termin::Vec3 horizontal = termin::world2d::world_horizontal_axis();
    constexpr termin::Vec3 depth = termin::world2d::world_depth_axis();
    constexpr termin::Vec3 vertical = termin::world2d::world_vertical_axis();

    static_assert(horizontal.x == 1.0 && horizontal.y == 0.0 && horizontal.z == 0.0);
    static_assert(depth.x == 0.0 && depth.y == 1.0 && depth.z == 0.0);
    static_assert(vertical.x == 0.0 && vertical.y == 0.0 && vertical.z == 1.0);

    const termin::Vec2f position_2d{12.5f, -8.25f};
    const termin::Vec3f position_world = termin::world2d::position_to_world(position_2d, 4.5f);
    const termin::Vec2f round_trip = termin::world2d::position_from_world(position_world);
    const termin::Vec3f moved_in_depth = termin::world2d::with_world_depth(position_world, -2.0f);

    CHECK(position_world.x == 12.5f);
    CHECK(position_world.y == 4.5f);
    CHECK(position_world.z == -8.25f);
    CHECK(round_trip.x == position_2d.x);
    CHECK(round_trip.y == position_2d.y);
    CHECK(termin::world2d::depth_from_world(position_world) == 4.5f);
    CHECK(moved_in_depth.x == position_world.x);
    CHECK(moved_in_depth.y == -2.0f);
    CHECK(moved_in_depth.z == position_world.z);

    const termin::Vec3f vector_world = termin::world2d::vector_to_world(termin::Vec2f{2.0f, 6.0f});
    const termin::Vec2f vector_round_trip = termin::world2d::vector_from_world(vector_world);
    CHECK(vector_world.y == 0.0f);
    CHECK(vector_round_trip.x == 2.0f);
    CHECK(vector_round_trip.y == 6.0f);

    CHECK(round_trip == position_2d);
}

TEST_CASE("world2d canonical camera and sprite face each other along world Y") {
    constexpr termin::Vec3 camera_forward = termin::world2d::canonical_camera_forward_axis();
    constexpr termin::Vec3 sprite_front = termin::world2d::canonical_sprite_front_axis();

    static_assert(camera_forward.x == 0.0);
    static_assert(camera_forward.y == 1.0);
    static_assert(camera_forward.z == 0.0);
    static_assert(sprite_front.x == 0.0);
    static_assert(sprite_front.y == -1.0);
    static_assert(sprite_front.z == 0.0);
    static_assert(termin::world2d::positive_rotation_axis().y == sprite_front.y);

    CHECK(camera_forward.dot(sprite_front) == -1.0);
}

TEST_CASE("look_at preserves the Y-forward Z-up camera convention") {
    const termin::Vec3 eye{0.0, -2.0, 0.0};
    const termin::Vec3 target{0.0, 0.0, 0.0};
    const termin::Vec3 world_up{0.0, 0.0, 1.0};

    const termin::Mat44 view = termin::Mat44::look_at(eye, target, world_up);
    const termin::Vec3 eye_view = view.transform_point(eye);
    const termin::Vec3 target_view = view.transform_point(target);
    const termin::Vec3 up_view = view.transform_point(target + world_up);

    CHECK((eye_view - termin::Vec3{0.0, 0.0, 0.0}).norm() < 1.0e-12);
    CHECK((target_view - termin::Vec3{0.0, 2.0, 0.0}).norm() < 1.0e-12);
    CHECK((up_view - termin::Vec3{0.0, 2.0, 1.0}).norm() < 1.0e-12);

    const termin::Mat44f view_f = termin::Mat44f::look_at(eye, target, world_up);
    const termin::Vec3f target_view_f = view_f.transform_point(target.to_float());
    const termin::Vec3f up_view_f = view_f.transform_point((target + world_up).to_float());
    CHECK((target_view_f - termin::Vec3f{0.0f, 2.0f, 0.0f}).norm() < 1.0e-6f);
    CHECK((up_view_f - termin::Vec3f{0.0f, 2.0f, 1.0f}).norm() < 1.0e-6f);
}

TEST_CASE("world2d positive angle is counter-clockwise in the visible XZ plane") {
    constexpr double half_pi = 1.57079632679489661923;
    const termin::Quat rotation = termin::world2d::rotation_to_world(half_pi);
    const termin::Vec3 rotated_horizontal = rotation.rotate(termin::world2d::world_horizontal_axis());

    CHECK(std::abs(rotated_horizontal.x) < 1.0e-12);
    CHECK(std::abs(rotated_horizontal.y) < 1.0e-12);
    CHECK(std::abs(rotated_horizontal.z - 1.0) < 1.0e-12);
}

TEST_CASE("world2d canonical quad has logical CCW winding toward the camera") {
    constexpr termin::Vec3 bottom_left{-1.0, 0.0, -1.0};
    constexpr termin::Vec3 bottom_right{1.0, 0.0, -1.0};
    constexpr termin::Vec3 top_right{1.0, 0.0, 1.0};

    const termin::Vec3 normal = (bottom_right - bottom_left).cross(top_right - bottom_left).normalized();
    const termin::Vec3 sprite_front = termin::world2d::canonical_sprite_front_axis();

    CHECK(std::abs(normal.x - sprite_front.x) < 1.0e-12);
    CHECK(std::abs(normal.y - sprite_front.y) < 1.0e-12);
    CHECK(std::abs(normal.z - sprite_front.z) < 1.0e-12);
}

GUARD_TEST_MAIN();
