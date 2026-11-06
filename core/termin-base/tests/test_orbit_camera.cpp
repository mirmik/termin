#include <cmath>
#include <limits>

#include <termin/camera/orbit_camera.hpp>

#include "guard_main.h"

namespace {

    bool near(double a, double b, double eps = 1.0e-9) {
        return std::abs(a - b) <= eps;
    }

    termin::Vec2 project_to_screen(const termin::Mat44& projection_view,
                                   const termin::Vec3& point,
                                   const termin::Rect2& viewport) {
        termin::Vec3 ndc;
        REQUIRE(projection_view.try_transform_point(point, ndc));
        return {viewport.x + (ndc.x + 1.0) * 0.5 * viewport.width,
                viewport.y + (ndc.y + 1.0) * 0.5 * viewport.height};
    }

    double point_to_ray_distance(const termin::Vec3& point, const termin::Ray3& ray) {
        const double distance_along_ray = (point - ray.origin).dot(ray.direction);
        return (point - (ray.origin + ray.direction * distance_along_ray)).norm();
    }

    double large_world_tolerance(double magnitude) {
        const double ulp = std::nextafter(magnitude, std::numeric_limits<double>::infinity()) - magnitude;
        return ulp * 64.0;
    }

} // namespace

TEST_CASE("OrbitCamera default eye matches shared orbit angles") {
    termin::OrbitCamera camera;
    double eye[3];
    camera.compute_eye(eye);

    CHECK(near(eye[0], 3.0618621784789726));
    CHECK(near(eye[1], -3.061862178478973));
    CHECK(near(eye[2], 2.5));
}

TEST_CASE("OrbitCamera fit_bounds updates target and clip planes") {
    termin::OrbitCamera camera;
    camera.fit_bounds(termin::AABB{{-1.0, -2.0, -3.0}, {3.0, 4.0, 5.0}});

    CHECK(near(camera.target.x, 1.0f));
    CHECK(near(camera.target.y, 1.0f));
    CHECK(near(camera.target.z, 1.0f));
    CHECK(camera.distance > 0.0f);
    CHECK(camera.near_clip >= 0.01f);
    CHECK(camera.far_clip > camera.near_clip);
}

TEST_CASE("OrbitCamera center screen ray points toward target") {
    termin::OrbitCamera camera;
    const std::optional<termin::Ray3> ray = camera.try_screen_ray({400.0, 300.0}, {0.0, 0.0, 800.0, 600.0});
    REQUIRE(ray.has_value());
    termin::Vec3 to_target = (camera.target - ray->origin).normalized();

    CHECK(ray->direction.dot(to_target) > 0.999f);
}

TEST_CASE("OrbitCamera screen ray reports invalid input instead of fabricating a ray") {
    termin::OrbitCamera camera;
    termin::ScreenRayError error = termin::ScreenRayError::None;

    CHECK_FALSE(camera.try_screen_ray({0.0, 0.0}, {0.0, 0.0, 0.0, 600.0}, &error).has_value());
    CHECK(error == termin::ScreenRayError::InvalidViewport);
}

TEST_CASE("OrbitCamera projects world points through the checked semantic contract") {
    termin::OrbitCamera camera;
    camera.target = {1.0e12, -7.5e11, 5.0e11};
    camera.distance = 137.0;
    camera.azimuth = 0.63;
    camera.elevation = 0.37;
    camera.near_clip = 0.25;
    camera.far_clip = 4000.0;
    const termin::Rect2 viewport{125.0, 75.0, 1200.0, 700.0};
    termin::ScreenRayError error = termin::ScreenRayError::InvalidProjection;

    const std::optional<termin::ProjectedScreenPoint> projected =
        camera.try_project_world_point(camera.target, viewport, &error);

    REQUIRE(projected.has_value());
    CHECK(error == termin::ScreenRayError::None);
    CHECK(std::abs(projected->screen.x - (viewport.x + viewport.width * 0.5)) <= 0.5);
    CHECK(std::abs(projected->screen.y - (viewport.y + viewport.height * 0.5)) <= 0.5);
    CHECK(projected->depth > 0.0);
    CHECK(projected->depth < 1.0);
    CHECK_EQ(projected->view_point.y, guard::Approx(camera.distance).epsilon(1.0e-3));
    CHECK(std::abs(projected->view_point.z) < 1.0e-3);

    CHECK_FALSE(camera.try_project_world_point({std::numeric_limits<double>::quiet_NaN(), 0.0, 0.0}, viewport, &error)
                    .has_value());
    CHECK(error == termin::ScreenRayError::InvalidWorldPoint);
}

TEST_CASE("OrbitCamera z-plane projection rejects non-finite planes") {
    termin::OrbitCamera camera;
    const termin::Rect2 viewport{0.0, 0.0, 800.0, 600.0};

    CHECK_FALSE(
        camera.world_point_on_z_plane({400.0, 300.0}, viewport, std::numeric_limits<double>::quiet_NaN()).has_value());
    CHECK_FALSE(
        camera.world_point_on_z_plane({400.0, 300.0}, viewport, std::numeric_limits<double>::infinity()).has_value());
    CHECK_FALSE(camera.world_point_on_z_plane({400.0, 300.0}, viewport, 100.0).has_value());
}

TEST_CASE("OrbitCamera perspective pan keeps the grabbed target under the cursor") {
    termin::OrbitCamera camera;
    const termin::Rect2 viewport{0.0, 0.0, 800.0, 600.0};
    const termin::Vec3 grabbed = camera.target;
    const auto gesture = camera.begin_pan({400.0, 300.0}, viewport);
    REQUIRE(gesture.has_value());
    REQUIRE(camera.pan(*gesture, {525.0, 360.0}));

    const termin::Vec2 projected = project_to_screen(camera.mvp(800.0 / 600.0), grabbed, viewport);
    CHECK_EQ(projected.x, guard::Approx(525.0).epsilon(1.0e-4));
    CHECK_EQ(projected.y, guard::Approx(360.0).epsilon(1.0e-4));
}

TEST_CASE("OrbitCamera uses local X right Y forward Z up for both projections") {
    termin::OrbitCamera camera;
    camera.azimuth = 0.0;
    camera.elevation = 0.0;
    const termin::Vec3 view_target = camera.view_matrix().transform_point(camera.target);
    CHECK(near(view_target.x, 0.0));
    CHECK(near(view_target.y, camera.distance));
    CHECK(near(view_target.z, 0.0));

    const termin::Rect2 viewport{0.0, 0.0, 800.0, 600.0};
    for (const auto projection : {termin::CameraProjection::Perspective, termin::CameraProjection::Orthographic}) {
        camera.projection_type = projection;
        const auto center = camera.try_project_world_point(camera.target, viewport);
        const auto right = camera.try_project_world_point(camera.target + termin::Vec3::unit_x(), viewport);
        const auto up = camera.try_project_world_point(camera.target + termin::Vec3::unit_z(), viewport);
        const auto forward = camera.try_project_world_point(camera.target + termin::Vec3::unit_y(), viewport);
        REQUIRE(center.has_value());
        REQUIRE(right.has_value());
        REQUIRE(up.has_value());
        REQUIRE(forward.has_value());
        CHECK(right->screen.x > center->screen.x);
        CHECK(near(right->screen.y, center->screen.y));
        CHECK(up->screen.y < center->screen.y);
        CHECK(near(up->screen.x, center->screen.x));
        CHECK(forward->depth > center->depth);
    }
}

TEST_CASE("OrbitCamera isometric preset projects all unit axes with equal lengths") {
    termin::OrbitCamera camera;
    camera.set_isometric();
    CHECK(camera.projection_type == termin::CameraProjection::Orthographic);
    const termin::Rect2 viewport{0.0, 0.0, 1200.0, 600.0};
    const auto center = camera.try_project_world_point(camera.target, viewport);
    const auto x = camera.try_project_world_point(camera.target + termin::Vec3::unit_x(), viewport);
    const auto y = camera.try_project_world_point(camera.target + termin::Vec3::unit_y(), viewport);
    const auto z = camera.try_project_world_point(camera.target + termin::Vec3::unit_z(), viewport);
    REQUIRE(center.has_value());
    REQUIRE(x.has_value());
    REQUIRE(y.has_value());
    REQUIRE(z.has_value());
    const double x_length = (x->screen - center->screen).norm();
    CHECK(x_length > 0.0);
    CHECK(near(x_length, (y->screen - center->screen).norm()));
    CHECK(near(x_length, (z->screen - center->screen).norm()));
}

TEST_CASE("OrbitCamera orthographic size is independent of depth and zoom preserves pose") {
    termin::OrbitCamera camera;
    camera.projection_type = termin::CameraProjection::Orthographic;
    camera.azimuth = 0.0;
    camera.elevation = 0.0;
    const termin::Rect2 viewport{0.0, 0.0, 800.0, 600.0};
    const auto near_point = camera.try_project_world_point({1.0, 0.0, 1.0}, viewport);
    const auto far_point = camera.try_project_world_point({1.0, 20.0, 1.0}, viewport);
    REQUIRE(near_point.has_value());
    REQUIRE(far_point.has_value());
    CHECK(near(near_point->screen.x, far_point->screen.x));
    CHECK(near(near_point->screen.y, far_point->screen.y));
    CHECK(far_point->depth > near_point->depth);

    const auto left_ray = camera.try_screen_ray({100.0, 200.0}, viewport);
    const auto right_ray = camera.try_screen_ray({700.0, 400.0}, viewport);
    REQUIRE(left_ray.has_value());
    REQUIRE(right_ray.has_value());
    CHECK((left_ray->direction - right_ray->direction).norm() < 1.0e-9);
    CHECK((left_ray->origin - right_ray->origin).norm() > 1.0);

    const double distance = camera.distance;
    const double size = camera.ortho_size;
    camera.zoom(0.5);
    CHECK(near(camera.distance, distance));
    CHECK(near(camera.ortho_size, size * 0.5));
    const auto zoomed = camera.try_project_world_point({1.0, 0.0, 1.0}, viewport);
    REQUIRE(zoomed.has_value());
    CHECK(near(zoomed->screen.x - 400.0, 2.0 * (near_point->screen.x - 400.0)));
}

TEST_CASE("OrbitCamera fit frames all corners in both projections and portrait viewports") {
    const termin::AABB bounds{{-12.0, -2.0, -5.0}, {9.0, 4.0, 7.0}};
    termin::Vec3 corners[8];
    bounds.get_corners(corners);
    for (const auto projection : {termin::CameraProjection::Perspective, termin::CameraProjection::Orthographic}) {
        for (const double aspect : {0.2, 1.0, 4.0}) {
            termin::OrbitCamera camera;
            camera.projection_type = projection;
            const double azimuth = camera.azimuth;
            const double elevation = camera.elevation;
            camera.fit_bounds(bounds, aspect);
            CHECK(camera.projection_type == projection);
            CHECK(near(camera.azimuth, azimuth));
            CHECK(near(camera.elevation, elevation));
            const termin::Mat44 mvp = camera.mvp(aspect);
            for (const auto& corner : corners) {
                const termin::Vec3 ndc = mvp.transform_point(corner);
                CHECK(std::abs(ndc.x) < 1.0);
                CHECK(std::abs(ndc.y) < 1.0);
                CHECK(ndc.z > 0.0);
                CHECK(ndc.z < 1.0);
            }
        }
    }
}

TEST_CASE("OrbitCamera orthographic pan keeps the grabbed target under the cursor") {
    termin::OrbitCamera camera;
    camera.set_isometric();
    const termin::Rect2 viewport{25.0, 50.0, 800.0, 600.0};
    const termin::Vec3 grabbed = camera.target;
    const auto gesture = camera.begin_pan({425.0, 350.0}, viewport);
    REQUIRE(gesture.has_value());
    REQUIRE(camera.pan(*gesture, {530.0, 415.0}));
    const auto projected = camera.try_project_world_point(grabbed, viewport);
    REQUIRE(projected.has_value());
    CHECK(near(projected->screen.x, 530.0));
    CHECK(near(projected->screen.y, 415.0));
}

TEST_CASE("OrbitCamera fit frames sub-unit bounds without a one-unit radius floor") {
    const termin::AABB bounds{{-0.001, -0.001, -0.001}, {0.001, 0.001, 0.001}};
    const termin::Rect2 viewport{0.0, 0.0, 800.0, 600.0};
    termin::Vec3 corners[8];
    bounds.get_corners(corners);
    for (const auto projection : {termin::CameraProjection::Perspective, termin::CameraProjection::Orthographic}) {
        termin::OrbitCamera camera;
        camera.projection_type = projection;
        camera.fit_bounds(bounds, viewport.width / viewport.height);
        CHECK(camera.distance < 0.01);
        CHECK(camera.near_clip < 0.001);
        CHECK(camera.far_clip < 0.1);
        const auto first = camera.try_project_world_point(corners[0], viewport);
        const auto opposite = camera.try_project_world_point(corners[7], viewport);
        REQUIRE(first.has_value());
        REQUIRE(opposite.has_value());
        CHECK((first->screen - opposite->screen).norm() > 100.0);
        for (const auto& corner : corners) {
            const termin::Vec3 ndc = camera.mvp(viewport.width / viewport.height).transform_point(corner);
            CHECK(std::abs(ndc.x) < 1.0);
            CHECK(std::abs(ndc.y) < 1.0);
            CHECK(ndc.z > 0.0);
            CHECK(ndc.z < 1.0);
        }
        const auto ray = camera.try_screen_ray({400.0, 300.0}, viewport);
        REQUIRE(ray.has_value());
        CHECK(point_to_ray_distance(camera.target, *ray) < 1.0e-9);
    }
}

TEST_CASE("OrbitCamera orthographic zoom is independent of perspective distance limits") {
    termin::OrbitCamera camera;
    camera.projection_type = termin::CameraProjection::Orthographic;
    camera.ortho_size = 0.001;
    camera.zoom(0.9);
    CHECK(near(camera.ortho_size, 0.0009));
    camera.ortho_size = camera.max_distance * 2.0;
    camera.zoom(1.1);
    CHECK(near(camera.ortho_size, camera.max_distance * 2.2));
    const double previous_size = camera.ortho_size;
    camera.zoom(std::numeric_limits<double>::max());
    CHECK(camera.ortho_size == previous_size);
    camera.zoom(-1.0);
    CHECK(camera.ortho_size == previous_size);
}

TEST_CASE("OrbitCamera fit keeps a single point projectable at the origin and far away") {
    for (const auto projection : {termin::CameraProjection::Perspective, termin::CameraProjection::Orthographic}) {
        for (const auto target : {termin::Vec3::zero(), termin::Vec3{1e12, -1e12, 1e12}}) {
            termin::OrbitCamera camera;
            camera.projection_type = projection;
            camera.fit_bounds(termin::AABB{target, target});
            const auto point = camera.try_project_world_point(target, {0.0, 0.0, 800.0, 600.0});
            REQUIRE(point.has_value());
            CHECK(std::abs(point->screen.x - 400.0) < 0.1);
            CHECK(std::abs(point->screen.y - 300.0) < 0.1);
            CHECK(point->depth > 0.0);
            CHECK(point->depth < 1.0);
        }
    }
}

TEST_CASE("OrbitCamera pan gesture supports orthographic projection") {
    const termin::Rect2 viewport{0.0, 0.0, 800.0, 600.0};
    const termin::Vec3 eye{0.0, -5.0, 0.0};
    const termin::Vec3 target{0.0, 0.0, 0.0};
    const termin::Mat44 projection = termin::Mat44::orthographic(-4.0, 4.0, -3.0, 3.0, 0.1, 100.0);
    const termin::Mat44 initial_view = termin::Mat44::look_at(eye, target);
    const auto gesture = termin::OrbitCameraPan::begin(initial_view, projection, eye, target, {400.0, 300.0}, viewport);
    REQUIRE(gesture.has_value());

    const auto moved_target = gesture->target_at({510.0, 375.0});
    REQUIRE(moved_target.has_value());
    const termin::Vec3 translation = *moved_target - target;
    const termin::Vec3 moved_eye = eye + translation;
    const termin::Mat44 moved_view = termin::Mat44::look_at(moved_eye, *moved_target);
    const termin::Vec2 projected = project_to_screen(projection * moved_view, target, viewport);
    CHECK(near(projected.x, 510.0, 2.0e-9));
    CHECK(near(projected.y, 375.0, 2.0e-9));
}

TEST_CASE("OrbitCamera perspective pan remains anchored in an oriented large world") {
    termin::OrbitCamera camera;
    camera.target = {1.0e12, -7.5e11, 5.0e11};
    camera.distance = 137.0;
    camera.azimuth = 0.63;
    camera.elevation = 0.37;
    camera.near_clip = 0.25;
    camera.far_clip = 4000.0;

    const termin::Rect2 viewport{125.0, 75.0, 1200.0, 700.0};
    const termin::Vec2 start{613.0, 329.0};
    const termin::Vec2 finish{777.0, 408.0};
    const auto gesture = camera.begin_pan(start, viewport);
    REQUIRE(gesture.has_value());
    const termin::Vec3 grabbed = gesture->grabbed_point();

    REQUIRE(camera.pan(*gesture, finish));
    const std::optional<termin::Ray3> moved_ray = camera.try_screen_ray(finish, viewport);
    REQUIRE(moved_ray.has_value());
    CHECK(point_to_ray_distance(grabbed, *moved_ray) <= large_world_tolerance(1.0e12));
}

TEST_CASE("OrbitCamera orthographic pan remains anchored in an oriented large world") {
    const termin::Vec3 target{1.0e12, -7.5e11, 5.0e11};
    const termin::Vec3 eye = target + termin::Vec3{97.0, -131.0, 83.0};
    const termin::Rect2 viewport{125.0, 75.0, 1200.0, 700.0};
    const termin::Mat44 projection = termin::Mat44::orthographic(-8.0, 8.0, -5.0, 5.0, 0.25, 4000.0);
    const termin::Mat44 initial_view = termin::Mat44::look_at(eye, target);
    const termin::Vec2 start{613.0, 329.0};
    const termin::Vec2 finish{777.0, 408.0};
    const auto gesture = termin::OrbitCameraPan::begin(initial_view, projection, eye, target, start, viewport);
    REQUIRE(gesture.has_value());
    const termin::Vec3 grabbed = gesture->grabbed_point();

    const std::optional<termin::Vec3> moved_target = gesture->target_at(finish);
    REQUIRE(moved_target.has_value());
    const termin::Vec3 translation = *moved_target - target;
    const termin::Mat44 moved_view = termin::Mat44::look_at(eye + translation, *moved_target);
    termin::Ray3 moved_ray;
    REQUIRE(termin::try_unproject_screen_ray(projection, moved_view, finish, viewport, moved_ray));
    CHECK(point_to_ray_distance(grabbed, moved_ray) <= large_world_tolerance(1.0e12));
}

TEST_CASE("OrbitCamera pan rejects invalid structured projection and view inputs") {
    const termin::Rect2 viewport{0.0, 0.0, 800.0, 600.0};
    const termin::Vec3 eye{0.0, -5.0, 0.0};
    const termin::Vec3 target{0.0, 0.0, 0.0};
    const termin::Mat44 projection = termin::Mat44::orthographic(-4.0, 4.0, -3.0, 3.0, 0.1, 100.0);

    CHECK_FALSE(
        termin::OrbitCameraPan::begin(
            termin::Mat44::look_at(eye, target), projection, eye, target, {400.0, 300.0}, {0.0, 0.0, 0.0, 600.0})
            .has_value());

    termin::Mat44 non_affine_view = termin::Mat44::look_at(eye, target);
    non_affine_view(0, 3) = 0.25;
    CHECK_FALSE(
        termin::OrbitCameraPan::begin(non_affine_view, projection, eye, target, {400.0, 300.0}, viewport).has_value());

    CHECK_FALSE(termin::OrbitCameraPan::begin(
                    termin::Mat44::look_at(eye, target), termin::Mat44::zero(), eye, target, {400.0, 300.0}, viewport)
                    .has_value());

    termin::Mat44 zero_near_w;
    zero_near_w(0, 0) = 1.0;
    zero_near_w(1, 1) = 1.0;
    zero_near_w(2, 3) = 1.0;
    zero_near_w(3, 2) = 1.0;
    CHECK_FALSE(termin::OrbitCameraPan::begin(
                    termin::Mat44::look_at(eye, target), zero_near_w, eye, target, {400.0, 300.0}, viewport)
                    .has_value());
}

GUARD_TEST_MAIN();
