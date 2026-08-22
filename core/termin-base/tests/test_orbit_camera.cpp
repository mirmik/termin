#include <cmath>

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

} // namespace

TEST_CASE("OrbitCamera default eye matches tcplot convention") {
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
    termin::OrbitCameraRay ray = camera.screen_ray({400.0, 300.0}, {0.0, 0.0, 800.0, 600.0});
    termin::Vec3 to_target = (camera.target - ray.origin).normalized();

    CHECK(ray.direction.dot(to_target) > 0.999f);
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

GUARD_TEST_MAIN();
