#include <cmath>
#include <limits>

#include <termin/camera/screen_ray.hpp>

#include "guard_main.h"

namespace {

    constexpr double kPi = 3.14159265358979323846;

    bool ray_equals(const termin::Ray3& left, const termin::Ray3& right) {
        return left.origin == right.origin && left.direction == right.direction;
    }

    termin::Ray3 sentinel_ray() {
        termin::Ray3 result;
        result.origin = {11.0, 12.0, 13.0};
        result.direction = {-0.25, 0.5, -0.75};
        return result;
    }

    bool projection_equals(const termin::ProjectedScreenPoint& left, const termin::ProjectedScreenPoint& right) {
        return left.screen == right.screen && left.depth == right.depth && left.view_point == right.view_point;
    }

    termin::ProjectedScreenPoint sentinel_projection() {
        return {{91.0, 92.0}, 0.375, {93.0, 94.0, 95.0}};
    }

} // namespace

TEST_CASE("screen ray uses Termin clip depth and viewport coordinates") {
    const termin::Rect2 viewport{100.0, 200.0, 800.0, 400.0};
    termin::Ray3 ray;
    termin::ScreenRayError error = termin::ScreenRayError::DegenerateDirection;

    REQUIRE(termin::try_unproject_screen_ray(termin::Mat44::identity(), {700.0, 300.0}, viewport, ray, &error));

    CHECK(error == termin::ScreenRayError::None);
    CHECK_EQ(ray.origin.x, guard::Approx(0.5));
    CHECK_EQ(ray.origin.y, guard::Approx(-0.5));
    CHECK_EQ(ray.origin.z, guard::Approx(0.0));
    CHECK_EQ(ray.direction.x, guard::Approx(0.0));
    CHECK_EQ(ray.direction.y, guard::Approx(0.0));
    CHECK_EQ(ray.direction.z, guard::Approx(1.0));
}

TEST_CASE("orthographic screen rays have shifted origins and parallel normalized directions") {
    const termin::Mat44 projection_view = termin::Mat44::orthographic(-4.0, 4.0, -3.0, 3.0, 0.1, 100.0);
    const termin::Rect2 viewport{0.0, 0.0, 800.0, 600.0};
    termin::Ray3 upper_left;
    termin::Ray3 lower_right;

    REQUIRE(termin::try_unproject_screen_ray(projection_view, {100.0, 100.0}, viewport, upper_left));
    REQUIRE(termin::try_unproject_screen_ray(projection_view, {700.0, 500.0}, viewport, lower_right));

    CHECK(upper_left.origin != lower_right.origin);
    CHECK_EQ(upper_left.origin.y, guard::Approx(0.1));
    CHECK_EQ(lower_right.origin.y, guard::Approx(0.1));
    CHECK_EQ(upper_left.direction.norm(), guard::Approx(1.0));
    CHECK_EQ(lower_right.direction.norm(), guard::Approx(1.0));
    CHECK_EQ(upper_left.direction.dot(lower_right.direction), guard::Approx(1.0));
    CHECK_EQ(upper_left.direction.x, guard::Approx(0.0));
    CHECK_EQ(upper_left.direction.y, guard::Approx(1.0));
    CHECK_EQ(upper_left.direction.z, guard::Approx(0.0));
}

TEST_CASE("screen ray validates tolerance screen point viewport and matrix") {
    const termin::Mat44 identity = termin::Mat44::identity();
    const termin::Rect2 viewport{0.0, 0.0, 640.0, 480.0};
    const double infinity = std::numeric_limits<double>::infinity();
    const double nan = std::numeric_limits<double>::quiet_NaN();
    termin::ScreenRayError error = termin::ScreenRayError::None;

    termin::Ray3 ray = sentinel_ray();
    const termin::Ray3 original = ray;
    CHECK_FALSE(termin::try_unproject_screen_ray(identity, {320.0, 240.0}, viewport, ray, &error, -1.0));
    CHECK(error == termin::ScreenRayError::InvalidTolerance);
    CHECK(ray_equals(ray, original));

    CHECK_FALSE(termin::try_unproject_screen_ray(identity, {infinity, 240.0}, viewport, ray, &error));
    CHECK(error == termin::ScreenRayError::InvalidScreenPoint);
    CHECK(ray_equals(ray, original));

    CHECK_FALSE(termin::try_unproject_screen_ray(identity, {320.0, 240.0}, {0.0, 0.0, 0.0, 480.0}, ray, &error));
    CHECK(error == termin::ScreenRayError::InvalidViewport);
    CHECK(ray_equals(ray, original));

    CHECK_FALSE(termin::try_unproject_screen_ray(identity, {320.0, 240.0}, {nan, 0.0, 640.0, 480.0}, ray, &error));
    CHECK(error == termin::ScreenRayError::InvalidViewport);
    CHECK(ray_equals(ray, original));

    termin::Mat44 non_finite = identity;
    non_finite(1, 2) = infinity;
    CHECK_FALSE(termin::try_unproject_screen_ray(non_finite, {320.0, 240.0}, viewport, ray, &error));
    CHECK(error == termin::ScreenRayError::NonFiniteProjectionView);
    CHECK(ray_equals(ray, original));
}

TEST_CASE("screen ray rejects singular and invalid homogeneous unprojection") {
    const termin::Rect2 viewport{0.0, 0.0, 100.0, 100.0};
    termin::Ray3 ray = sentinel_ray();
    const termin::Ray3 original = ray;
    termin::ScreenRayError error = termin::ScreenRayError::None;

    CHECK_FALSE(termin::try_unproject_screen_ray(termin::Mat44::zero(), {50.0, 50.0}, viewport, ray, &error));
    CHECK(error == termin::ScreenRayError::SingularProjectionView);
    CHECK(ray_equals(ray, original));

    // This invertible matrix swaps homogeneous Z and W. Its inverse is
    // itself, so the Termin near clip point (0, 0, 0, 1) maps to W=0.
    termin::Mat44 zero_near_w;
    zero_near_w(0, 0) = 1.0;
    zero_near_w(1, 1) = 1.0;
    zero_near_w(2, 3) = 1.0;
    zero_near_w(3, 2) = 1.0;
    CHECK_FALSE(termin::try_unproject_screen_ray(zero_near_w, {50.0, 50.0}, viewport, ray, &error));
    CHECK(error == termin::ScreenRayError::InvalidUnprojection);
    CHECK(ray_equals(ray, original));
}

TEST_CASE("screen ray homogeneous divide rejects only exact zero W") {
    termin::Mat44 projection_view = termin::Mat44::identity();
    projection_view(3, 3) = 1.0e15;
    termin::Ray3 ray;

    REQUIRE(termin::try_unproject_screen_ray(projection_view, {50.0, 50.0}, {0.0, 0.0, 100.0, 100.0}, ray));
    CHECK(ray.origin == termin::Vec3::zero());
    CHECK(ray.direction == termin::Vec3::unit_z());
}

TEST_CASE("screen ray rejects a direction below the requested reliability tolerance") {
    const termin::Mat44 projection_view = termin::Mat44::scale({1.0, 1.0, 1.0e15});
    termin::Ray3 ray = sentinel_ray();
    const termin::Ray3 original = ray;
    termin::ScreenRayError error = termin::ScreenRayError::None;

    CHECK_FALSE(termin::try_unproject_screen_ray(projection_view, {50.0, 50.0}, {0.0, 0.0, 100.0, 100.0}, ray, &error));
    CHECK(error == termin::ScreenRayError::DegenerateDirection);
    CHECK(ray_equals(ray, original));
}

TEST_CASE("screen ray preserves double precision in a large world") {
    const termin::Vec3 world_origin{1.0e12, -2.0e12, 3.0e12};
    const termin::Mat44 projection_view = termin::Mat44::translation(-world_origin);
    termin::Ray3 ray;

    REQUIRE(termin::try_unproject_screen_ray(projection_view, {625.0, 312.5}, {125.0, 62.5, 1000.0, 500.0}, ray));

    CHECK_EQ(ray.origin.x, guard::Approx(world_origin.x));
    CHECK_EQ(ray.origin.y, guard::Approx(world_origin.y));
    CHECK_EQ(ray.origin.z, guard::Approx(world_origin.z));
    CHECK(ray.direction == termin::Vec3::unit_z());
}

TEST_CASE("split projection and view preserve perspective rays in a large world") {
    const termin::Vec3 world_origin{1.0e12, -2.0e12, 3.0e12};
    const termin::Mat44 projection = termin::Mat44::perspective(60.0 * kPi / 180.0, 4.0 / 3.0, 0.1, 100.0);
    const termin::Mat44 view = termin::Mat44::translation(-world_origin);
    termin::Ray3 ray;

    REQUIRE(termin::try_unproject_screen_ray(projection, view, {400.0, 300.0}, {0.0, 0.0, 800.0, 600.0}, ray));

    CHECK(std::abs(ray.origin.x - world_origin.x) <= 2.0e-3);
    CHECK(std::abs(ray.origin.y - (world_origin.y + 0.1)) <= 2.0e-3);
    CHECK(std::abs(ray.origin.z - world_origin.z) <= 2.0e-3);
    CHECK(std::abs(ray.direction.x) <= 1.0e-6);
    CHECK(std::abs(ray.direction.y - 1.0) <= 1.0e-6);
    CHECK(std::abs(ray.direction.z) <= 1.0e-6);
}

TEST_CASE("split projection and rotated view preserve translation-free direction in a large world") {
    const termin::Vec3 eye{1.0e12, -2.0e12, 3.0e12};
    const termin::Vec3 target = eye + termin::Vec3{1.0, 2.0, 3.0};
    const termin::Mat44 projection = termin::Mat44::perspective(55.0 * kPi / 180.0, 16.0 / 9.0, 0.1, 250.0);
    const termin::Mat44 view = termin::Mat44::look_at(eye, target);
    termin::Ray3 ray;

    REQUIRE(termin::try_unproject_screen_ray(projection, view, {960.0, 540.0}, {0.0, 0.0, 1920.0, 1080.0}, ray));

    const termin::Vec3 expected_direction = (target - eye).normalized();
    CHECK((ray.origin - eye).norm() <= 0.25);
    CHECK((ray.direction - expected_direction).norm() <= 1.0e-12);
}

TEST_CASE("split projection and view failures leave the ray unchanged") {
    const termin::Rect2 viewport{0.0, 0.0, 100.0, 100.0};
    termin::Ray3 ray = sentinel_ray();
    const termin::Ray3 original = ray;
    termin::ScreenRayError error = termin::ScreenRayError::None;

    termin::Mat44 non_finite_view = termin::Mat44::identity();
    non_finite_view(3, 0) = std::numeric_limits<double>::infinity();
    CHECK_FALSE(termin::try_unproject_screen_ray(
        termin::Mat44::identity(), non_finite_view, {50.0, 50.0}, viewport, ray, &error));
    CHECK(error == termin::ScreenRayError::NonFiniteProjectionView);
    CHECK(ray_equals(ray, original));

    CHECK_FALSE(termin::try_unproject_screen_ray(
        termin::Mat44::identity(), termin::Mat44::scale({1.0, 0.0, 1.0}), {50.0, 50.0}, viewport, ray, &error));
    CHECK(error == termin::ScreenRayError::SingularProjectionView);
    CHECK(ray_equals(ray, original));

    termin::Mat44 projective_view = termin::Mat44::identity();
    projective_view(0, 3) = 0.25;
    CHECK_FALSE(termin::try_unproject_screen_ray(
        termin::Mat44::identity(), projective_view, {50.0, 50.0}, viewport, ray, &error));
    CHECK(error == termin::ScreenRayError::NonAffineView);
    CHECK(ray_equals(ray, original));
}

TEST_CASE("screen point depth round-trips through perspective and orthographic cameras") {
    const termin::Rect2 viewport{120.0, 75.0, 1280.0, 720.0};
    const termin::Vec2 screen_point{731.5, 286.5};
    const termin::Mat44 view = termin::Mat44::look_at({4.0, -8.0, 3.0}, {-1.0, 2.0, 0.5});

    const termin::Mat44 projections[] = {
        termin::Mat44::perspective(57.0 * kPi / 180.0, viewport.width / viewport.height, 0.2, 400.0),
        termin::Mat44::orthographic(-8.0, 8.0, -4.5, 4.5, 0.2, 400.0),
    };
    for (const termin::Mat44& projection : projections) {
        termin::Vec3 world_point;
        termin::ScreenRayError error = termin::ScreenRayError::DegenerateDirection;
        REQUIRE(
            termin::try_unproject_screen_point(projection, view, screen_point, 0.375, viewport, world_point, &error));
        CHECK(error == termin::ScreenRayError::None);

        termin::ProjectedScreenPoint projected;
        REQUIRE(termin::try_project_world_point(projection, view, world_point, viewport, projected, &error));
        CHECK(error == termin::ScreenRayError::None);
        CHECK_EQ(projected.screen.x, guard::Approx(screen_point.x).epsilon(1.0e-10));
        CHECK_EQ(projected.screen.y, guard::Approx(screen_point.y).epsilon(1.0e-10));
        CHECK_EQ(projected.depth, guard::Approx(0.375).epsilon(1.0e-12));
        CHECK(projected.view_point.is_finite());
    }
}

TEST_CASE("screen point depth preserves oriented large-world projection") {
    const termin::Vec3 eye{1.0e12, -2.0e12, 3.0e12};
    const termin::Vec3 target = eye + termin::Vec3{2.0, 3.0, -1.0};
    const termin::Rect2 viewport{125.0, 62.5, 1600.0, 900.0};
    const termin::Vec2 screen_point{1111.5, 447.5};
    const double clip_depth = 0.625;
    const termin::Mat44 projection =
        termin::Mat44::perspective(61.0 * kPi / 180.0, viewport.width / viewport.height, 0.1, 500.0);
    const termin::Mat44 view = termin::Mat44::look_at(eye, target);
    termin::Vec3 world_point;

    REQUIRE(termin::try_unproject_screen_point(projection, view, screen_point, clip_depth, viewport, world_point));
    CHECK((world_point - eye).norm() < 1.0);

    termin::ProjectedScreenPoint projected;
    REQUIRE(termin::try_project_world_point(projection, view, world_point, viewport, projected));
    CHECK(std::abs(projected.screen.x - screen_point.x) <= 0.5);
    CHECK(std::abs(projected.screen.y - screen_point.y) <= 0.5);
    CHECK(std::abs(projected.depth - clip_depth) <= 2.0e-4);
    CHECK(projected.view_point.is_finite());
}

TEST_CASE("screen projection preserves finite points outside viewport and clip volume") {
    const termin::Mat44 identity = termin::Mat44::identity();
    const termin::Rect2 viewport{10.0, 20.0, 100.0, 200.0};

    termin::Vec3 outside_world;
    REQUIRE(termin::try_unproject_screen_point(identity, identity, {-40.0, 350.0}, 0.25, viewport, outside_world));
    CHECK_EQ(outside_world.x, guard::Approx(-2.0));
    CHECK_EQ(outside_world.y, guard::Approx(2.3));
    CHECK_EQ(outside_world.z, guard::Approx(0.25));

    termin::ProjectedScreenPoint projected;
    REQUIRE(termin::try_project_world_point(identity, identity, {2.0, -3.0, 1.5}, viewport, projected));
    CHECK_EQ(projected.screen.x, guard::Approx(160.0));
    CHECK_EQ(projected.screen.y, guard::Approx(-180.0));
    CHECK_EQ(projected.depth, guard::Approx(1.5));
    CHECK(projected.view_point == termin::Vec3(2.0, -3.0, 1.5));
}

TEST_CASE("screen point depth checked failures leave semantic outputs unchanged") {
    const termin::Rect2 viewport{0.0, 0.0, 640.0, 480.0};
    const termin::Mat44 identity = termin::Mat44::identity();
    const double nan = std::numeric_limits<double>::quiet_NaN();
    const double infinity = std::numeric_limits<double>::infinity();
    termin::ScreenRayError error = termin::ScreenRayError::None;
    termin::Vec3 world{11.0, 12.0, 13.0};
    const termin::Vec3 original_world = world;

    CHECK_FALSE(
        termin::try_unproject_screen_point(identity, identity, {320.0, 240.0}, 0.5, viewport, world, &error, -1.0));
    CHECK(error == termin::ScreenRayError::InvalidTolerance);
    CHECK(world == original_world);

    CHECK_FALSE(
        termin::try_unproject_screen_point(identity, identity, {infinity, 240.0}, 0.5, viewport, world, &error));
    CHECK(error == termin::ScreenRayError::InvalidScreenPoint);
    CHECK(world == original_world);

    CHECK_FALSE(termin::try_unproject_screen_point(identity, identity, {320.0, 240.0}, nan, viewport, world, &error));
    CHECK(error == termin::ScreenRayError::InvalidClipDepth);
    CHECK(world == original_world);

    CHECK_FALSE(termin::try_unproject_screen_point(identity, identity, {320.0, 240.0}, -0.01, viewport, world, &error));
    CHECK(error == termin::ScreenRayError::InvalidClipDepth);
    CHECK(world == original_world);

    CHECK_FALSE(termin::try_unproject_screen_point(identity, identity, {320.0, 240.0}, 1.01, viewport, world, &error));
    CHECK(error == termin::ScreenRayError::InvalidClipDepth);
    CHECK(world == original_world);

    CHECK_FALSE(termin::try_unproject_screen_point(
        identity, identity, {320.0, 240.0}, 0.5, {0.0, 0.0, 0.0, 480.0}, world, &error));
    CHECK(error == termin::ScreenRayError::InvalidViewport);
    CHECK(world == original_world);

    termin::Mat44 non_finite_projection = identity;
    non_finite_projection(0, 0) = infinity;
    CHECK_FALSE(termin::try_unproject_screen_point(
        non_finite_projection, identity, {320.0, 240.0}, 0.5, viewport, world, &error));
    CHECK(error == termin::ScreenRayError::NonFiniteProjectionView);
    CHECK(world == original_world);

    CHECK_FALSE(termin::try_unproject_screen_point(
        termin::Mat44::zero(), identity, {320.0, 240.0}, 0.5, viewport, world, &error));
    CHECK(error == termin::ScreenRayError::SingularProjectionView);
    CHECK(world == original_world);

    CHECK_FALSE(termin::try_unproject_screen_point(
        identity, termin::Mat44::scale({1.0, 0.0, 1.0}), {320.0, 240.0}, 0.5, viewport, world, &error));
    CHECK(error == termin::ScreenRayError::SingularProjectionView);
    CHECK(world == original_world);

    termin::Mat44 projective_view = identity;
    projective_view(0, 3) = 0.25;
    CHECK_FALSE(
        termin::try_unproject_screen_point(identity, projective_view, {320.0, 240.0}, 0.5, viewport, world, &error));
    CHECK(error == termin::ScreenRayError::NonAffineView);
    CHECK(world == original_world);

    termin::Mat44 zero_w_unprojection;
    zero_w_unprojection(0, 0) = 1.0;
    zero_w_unprojection(1, 1) = 1.0;
    zero_w_unprojection(2, 3) = 1.0;
    zero_w_unprojection(3, 2) = 1.0;
    CHECK_FALSE(termin::try_unproject_screen_point(
        zero_w_unprojection, identity, {320.0, 240.0}, 0.0, viewport, world, &error));
    CHECK(error == termin::ScreenRayError::InvalidUnprojection);
    CHECK(world == original_world);

    termin::ProjectedScreenPoint projected = sentinel_projection();
    const termin::ProjectedScreenPoint original_projected = projected;
    CHECK_FALSE(termin::try_project_world_point(identity, identity, {nan, 0.0, 0.0}, viewport, projected, &error));
    CHECK(error == termin::ScreenRayError::InvalidWorldPoint);
    CHECK(projection_equals(projected, original_projected));

    CHECK_FALSE(
        termin::try_project_world_point(termin::Mat44::zero(), identity, {0.0, 1.0, 0.0}, viewport, projected, &error));
    CHECK(error == termin::ScreenRayError::SingularProjectionView);
    CHECK(projection_equals(projected, original_projected));

    const termin::Mat44 perspective = termin::Mat44::perspective(kPi / 3.0, 4.0 / 3.0, 0.1, 100.0);
    CHECK_FALSE(termin::try_project_world_point(perspective, identity, {0.0, 0.0, 0.0}, viewport, projected, &error));
    CHECK(error == termin::ScreenRayError::InvalidProjection);
    CHECK(projection_equals(projected, original_projected));
}

TEST_CASE("screen ray failure messages describe every public error") {
    using termin::ScreenRayError;
    const ScreenRayError errors[] = {
        ScreenRayError::None,
        ScreenRayError::InvalidTolerance,
        ScreenRayError::InvalidScreenPoint,
        ScreenRayError::InvalidClipDepth,
        ScreenRayError::InvalidWorldPoint,
        ScreenRayError::InvalidViewport,
        ScreenRayError::MissingViewTransform,
        ScreenRayError::NonFiniteProjectionView,
        ScreenRayError::NonAffineView,
        ScreenRayError::SingularProjectionView,
        ScreenRayError::InvalidUnprojection,
        ScreenRayError::InvalidProjection,
        ScreenRayError::DegenerateDirection,
    };
    for (ScreenRayError error : errors) {
        CHECK(termin::screen_ray_error_message(error)[0] != '\0');
    }
}

GUARD_TEST_MAIN();
