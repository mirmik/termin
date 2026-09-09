#include "guard_main.h"
#include "termin/editor/editor_camera_component.hpp"
#include <termin/camera/orbit_camera_controller.hpp>
#include <core/tc_camera_capability.h>
#include <cmath>

using termin::CameraComponent;
using termin::CameraProjection;
using termin::EditorCameraComponent;
using termin::Mat44;

namespace {
    void register_editor_camera() {
        static const bool registered = [] { EditorCameraComponent::register_type(); return true; }();
        (void)registered;
    }

    void check_focus_plane(const Mat44& actual, const Mat44& expected, double distance) {
        const double point[4] = {1.3, distance, -0.7, 1.0};
        double a[4] = {}, b[4] = {};
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                a[row] += actual(col, row) * point[col];
                b[row] += expected(col, row) * point[col];
            }
        }
        CHECK(std::abs(a[0] / a[3] - b[0] / b[3]) < 1e-10);
        CHECK(std::abs(a[1] / a[3] - b[1] / b[3]) < 1e-10);
    }
}

TEST_CASE("Editor camera projection lerp fixes target plane at every aspect and FOV mode") {
    register_editor_camera();
    for (auto mode : {termin::FovMode::FixHorizontal, termin::FovMode::FixVertical, termin::FovMode::FixBoth}) {
        EditorCameraComponent camera;
        CameraComponent reference;
        camera.fov_mode = reference.fov_mode = mode;
        camera.aspect = 1.7;
        int requests = 0;
        camera.request_render_callback = [&] { ++requests; };
        camera.enter_axis_view(12.0);
        for (int step = 0; step < 6; ++step) {
            for (double aspect : {0.5, 1.7, 2.5}) {
                check_focus_plane(camera.compute_projection_matrix(aspect),
                                  reference.compute_projection_matrix(aspect), 12.0);
            }
            camera.update(0.05f);
        }
        CHECK(!camera.transitioning());
        CHECK(camera.axis_view());
        CHECK(camera.get_projection_matrix()(1, 3) == 0.0);
        const int finished_requests = requests;
        camera.update(1.0f);
        CHECK(requests == finished_requests);
        CHECK(requests > 1);
    }
}

TEST_CASE("Editor camera interrupted projection reversal is continuous and restores perspective") {
    register_editor_camera();
    EditorCameraComponent camera;
    const Mat44 original = camera.get_projection_matrix();
    camera.enter_axis_view(9.0);
    camera.update(0.08f);
    const Mat44 before = camera.get_projection_matrix();
    camera.leave_axis_view();
    const Mat44 after = camera.get_projection_matrix();
    for (int i = 0; i < 16; ++i) CHECK(before.data[i] == after.data[i]);
    camera.update(1.0f);
    const Mat44 restored = camera.get_projection_matrix();
    for (int i = 0; i < 16; ++i) CHECK(original.data[i] == restored.data[i]);
    CHECK(!camera.axis_view());
    CHECK(!camera.transitioning());
}

TEST_CASE("Editor camera explicit projection overrides axis transition and preserves original ortho mode") {
    register_editor_camera();
    EditorCameraComponent camera;
    camera.enter_axis_view(9.0);
    CameraComponent& base = camera;
    base.set_projection_type_str("orthographic");
    CHECK(!camera.transitioning());
    CHECK(!camera.axis_view());
    camera.enter_axis_view(9.0);
    camera.leave_axis_view();
    CHECK(camera.projection_type == CameraProjection::Orthographic);
}

TEST_CASE("Editor camera axis zoom transfers to orbit radius when rotation resumes") {
    register_editor_camera();
    auto entity = termin::Entity::create(termin::Entity::standalone_pool_handle(), "editor-camera");
    auto* camera = new EditorCameraComponent();
    auto* orbit = new termin::OrbitCameraController();
    entity.add_component(camera);
    entity.add_component(orbit);
    orbit->radius = 10.0;
    orbit->_update_pose();
    camera->enter_axis_view(10.0);
    camera->finish_projection_transition();
    camera->ortho_size *= 0.5;
    orbit->orbit(10.0, 0.0);
    camera->update(0.01f);
    CHECK(!camera->axis_view());
    CHECK(std::abs(orbit->radius - 5.0) < 1e-10);
    camera->update(1.0f);
    CHECK(!camera->transitioning());
    tc_entity_free(entity.handle());
}

TEST_CASE("Editor camera axis restoration preserves fly roll with and without zoom") {
    register_editor_camera();
    for (double zoom : {1.0, 0.5}) {
        auto entity = termin::Entity::create(termin::Entity::standalone_pool_handle(), "editor-fly-camera");
        auto* camera = new EditorCameraComponent();
        auto* orbit = new termin::OrbitCameraController();
        entity.add_component(camera);
        entity.add_component(orbit);
        orbit->horizon_lock = false;
        orbit->radius = 10.0;
        orbit->_update_pose();
        camera->enter_axis_view(10.0);
        camera->finish_projection_transition();
        camera->ortho_size *= zoom;
        orbit->fly_rotate(0.0, 0.0, 15.0);
        const auto before = entity.transform().global_rotation();
        const auto target_before = orbit->target();
        camera->update(0.01f);
        const auto after = entity.transform().global_rotation();
        CHECK(std::abs(before.x - after.x) < 1e-12);
        CHECK(std::abs(before.y - after.y) < 1e-12);
        CHECK(std::abs(before.z - after.z) < 1e-12);
        CHECK(std::abs(before.w - after.w) < 1e-12);
        CHECK((target_before - orbit->target()).norm() < 1e-10);
        CHECK(!camera->axis_view());
        tc_entity_free(entity.handle());
    }
}

TEST_CASE("Editor camera capability and picking use interpolated projection") {
    register_editor_camera();
    auto entity = termin::Entity::create(termin::Entity::standalone_pool_handle(), "editor-picking-camera");
    auto* camera = new EditorCameraComponent();
    entity.add_component(camera);
    const auto* capability = tc_camera_capability_get(camera->c_component());
    REQUIRE(capability != nullptr);
    const termin::Vec3 point{1.3, 10.0, -0.7};
    const termin::Rect2 viewport{0.0, 0.0, 800.0, 600.0};
    const auto original_screen = camera->try_project_world_point(point, viewport);
    REQUIRE(original_screen.has_value());
    camera->enter_axis_view(10.0);
    for (int step = 0; step < 5; ++step) {
        tc_camera_data data{};
        REQUIRE(capability->vtable->get_camera_data(camera->c_component(), 4.0 / 3.0, &data));
        const auto expected = camera->compute_projection_matrix(4.0 / 3.0);
        for (int i = 0; i < 16; ++i) CHECK(data.projection[i] == expected.data[i]);
        const auto ray = camera->try_screen_point_to_ray(original_screen->screen, viewport);
        REQUIRE(ray.has_value());
        termin::Vec3 hit;
        REQUIRE(termin::try_intersect_ray_plane(*ray, point, termin::Vec3::unit_y(), hit, true));
        CHECK((hit - point).norm() < 1e-8);
        camera->update(0.05f);
    }
    tc_entity_free(entity.handle());
}
