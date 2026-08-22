#include "guard_main.h"

#include "termin/camera/orbit_camera_controller.hpp"
#include "termin/entity/component.hpp"
#include "termin/entity/entity.hpp"
#include "termin/input/input_events.hpp"

#include <termin/camera/camera_component.hpp>

#include <cmath>
#include <optional>

extern "C" {
#include "core/tc_entity_pool.h"
#include "core/tc_scene.h"
#include "render/tc_render_target.h"
#include "render/tc_viewport.h"
}

using guard::Approx;
using termin::CameraComponent;
using termin::CameraProjection;
using termin::Entity;
using termin::MouseButtonEvent;
using termin::MouseMoveEvent;
using termin::OrbitCameraController;
using termin::PointerEvent;
using termin::ScrollEvent;

namespace {

    struct CameraRig {
        Entity entity;
        CameraComponent* camera = nullptr;
        OrbitCameraController* controller = nullptr;
    };

    CameraRig make_camera_rig(const char* name, tc_entity_pool_handle pool = Entity::standalone_pool_handle()) {
        CameraRig rig;
        rig.entity = Entity::create(pool, name);
        rig.camera = new CameraComponent();
        rig.controller = new OrbitCameraController();
        rig.entity.add_component(rig.camera);
        rig.entity.add_component(rig.controller);
        return rig;
    }

    PointerEvent make_pointer_event(tc_viewport_handle viewport,
                                    uint64_t pointer_id,
                                    int phase,
                                    double x,
                                    double y,
                                    double dx = 0.0,
                                    double dy = 0.0) {
        return PointerEvent(tc_pointer_event_init_info{
            .viewport = viewport,
            .pointer_id = pointer_id,
            .device = TC_POINTER_DEVICE_TOUCH,
            .phase = phase,
            .x = x,
            .y = y,
            .dx = dx,
            .dy = dy,
            .pressure = 1.0f,
            .source = TC_INPUT_SOURCE_RUNTIME,
        });
    }

    termin::Vec3 project_to_screen(const CameraComponent& camera,
                                   const termin::Vec3& point,
                                   double width,
                                   double height) {
        const termin::Mat44 projection_view = camera.compute_projection_matrix(width / height) * camera.get_view_matrix();
        const termin::Vec3 ndc = projection_view.transform_point(point);
        return {(ndc.x + 1.0) * 0.5 * width, (ndc.y + 1.0) * 0.5 * height, ndc.z};
    }

} // namespace

TEST_CASE("OrbitCameraController only handles events from viewports rendered by its camera") {
    tc_scene_handle scene = tc_scene_new_named("orbit-camera-controller-test");
    REQUIRE(tc_scene_alive(scene));
    tc_entity_pool_handle scene_pool = tc_entity_pool_registry_find(tc_scene_entity_pool(scene));
    REQUIRE(tc_entity_pool_handle_valid(scene_pool));

    CameraRig primary = make_camera_rig("primary-camera", scene_pool);
    CameraRig secondary = make_camera_rig("secondary-camera", scene_pool);

    tc_render_target_handle primary_rt = tc_render_target_new("primary-rt");
    tc_render_target_handle secondary_rt = tc_render_target_new("secondary-rt");
    REQUIRE(tc_render_target_handle_valid(primary_rt));
    REQUIRE(tc_render_target_handle_valid(secondary_rt));

    tc_render_target_set_scene(primary_rt, scene);
    tc_render_target_set_scene(secondary_rt, scene);
    tc_render_target_set_camera(primary_rt, primary.camera->tc_component_ptr());
    tc_render_target_set_camera(secondary_rt, secondary.camera->tc_component_ptr());

    tc_viewport_handle primary_viewport = tc_viewport_new("primary-viewport", TC_SCENE_HANDLE_INVALID);
    tc_viewport_handle secondary_viewport = tc_viewport_new("secondary-viewport", TC_SCENE_HANDLE_INVALID);
    REQUIRE(tc_viewport_handle_valid(primary_viewport));
    REQUIRE(tc_viewport_handle_valid(secondary_viewport));

    tc_viewport_set_render_target(primary_viewport, primary_rt);
    tc_viewport_set_render_target(secondary_viewport, secondary_rt);

    const double initial_radius = primary.controller->radius;

    ScrollEvent foreign_scroll(secondary_viewport, 0.0, 0.0, 0.0, 1.0, 0);
    primary.controller->on_scroll(&foreign_scroll);
    CHECK_EQ(primary.controller->radius, Approx(initial_radius).epsilon(1e-12));

    ScrollEvent own_scroll(primary_viewport, 0.0, 0.0, 0.0, 1.0, 0);
    primary.controller->on_scroll(&own_scroll);
    CHECK_EQ(primary.controller->radius, Approx(initial_radius - 0.5).epsilon(1e-12));

    tc_viewport_free(primary_viewport);
    tc_viewport_free(secondary_viewport);
    tc_render_target_free(primary_rt);
    tc_render_target_free(secondary_rt);
    tc_entity_free(primary.entity.handle());
    tc_entity_free(secondary.entity.handle());
    tc_scene_free(scene);
}

TEST_CASE("OrbitCameraController center_on keeps camera offset from target") {
    CameraRig rig = make_camera_rig("focus-camera");

    const termin::Vec3 initial_eye = rig.entity.transform().global_position();
    const termin::Vec3 initial_target = rig.controller->target();
    const termin::Vec3 initial_offset = initial_eye - initial_target;

    const termin::Vec3 focus{12.0, -3.0, 4.5};
    rig.controller->center_on(focus);

    const termin::Vec3 focused_eye = rig.entity.transform().global_position();
    const termin::Vec3 focused_target = rig.controller->target();
    const termin::Vec3 focused_offset = focused_eye - focused_target;

    CHECK_EQ(focused_target.x, Approx(focus.x).epsilon(1e-12));
    CHECK_EQ(focused_target.y, Approx(focus.y).epsilon(1e-12));
    CHECK_EQ(focused_target.z, Approx(focus.z).epsilon(1e-12));

    CHECK_EQ(focused_offset.x, Approx(initial_offset.x).epsilon(1e-12));
    CHECK_EQ(focused_offset.y, Approx(initial_offset.y).epsilon(1e-12));
    CHECK_EQ(focused_offset.z, Approx(initial_offset.z).epsilon(1e-12));

    tc_entity_free(rig.entity.handle());
}

TEST_CASE("CameraComponent C++ ray API returns an optional canonical Ray3") {
    CameraRig rig = make_camera_rig("ray-camera");

    const std::optional<termin::Ray3> ray =
        rig.camera->try_screen_point_to_ray(termin::Vec2{400.0, 300.0}, termin::Rect2{0.0, 0.0, 800.0, 600.0});
    REQUIRE(ray.has_value());

    CHECK(std::abs(ray->direction.x) <= 1.0e-12);
    CHECK(std::abs(ray->direction.y - 1.0) <= 1.0e-12);
    CHECK(std::abs(ray->direction.z) <= 1.0e-12);
    CHECK_EQ(ray->direction.norm(), Approx(1.0).epsilon(1e-12));
    CHECK_FALSE(rig.camera->try_screen_point_to_ray(termin::Vec2{400.0, 300.0}, termin::Rect2{0.0, 0.0, 0.0, 600.0})
                    .has_value());

    tc_entity_free(rig.entity.handle());
}

TEST_CASE("CameraComponent checked ray API rejects a missing owner transform") {
    CameraComponent camera;
    termin::ScreenRayError error = termin::ScreenRayError::None;

    CHECK_FALSE(
        camera.try_screen_point_to_ray(termin::Vec2{400.0, 300.0}, termin::Rect2{0.0, 0.0, 800.0, 600.0}, &error)
            .has_value());
    CHECK(error == termin::ScreenRayError::MissingViewTransform);
}

TEST_CASE("OrbitCameraController fly_move accepts one local displacement vector") {
    CameraRig rig = make_camera_rig("fly-camera");
    const termin::Quat rotation = termin::Quat::from_axis_angle(termin::Vec3::unit_z(), 0.5 * std::acos(-1.0));
    rig.entity.transform().relocate(termin::Pose3{rotation, {10.0, -4.0, 2.0}});

    rig.controller->fly_move({1.0, 2.0, 3.0});

    const termin::Vec3 position = rig.entity.transform().global_position();
    CHECK(std::abs(position.x - 8.0) <= 1.0e-12);
    CHECK(std::abs(position.y + 3.0) <= 1.0e-12);
    CHECK(std::abs(position.z - 5.0) <= 1.0e-12);

    const termin::Quat actual_rotation = rig.entity.transform().global_rotation();
    CHECK(std::abs(actual_rotation.x - rotation.x) <= 1.0e-12);
    CHECK(std::abs(actual_rotation.y - rotation.y) <= 1.0e-12);
    CHECK(std::abs(actual_rotation.z - rotation.z) <= 1.0e-12);
    CHECK(std::abs(actual_rotation.w - rotation.w) <= 1.0e-12);

    tc_entity_free(rig.entity.handle());
}

TEST_CASE("OrbitCameraController handles one-finger orbit and two-finger pinch") {
    tc_scene_handle scene = tc_scene_new_named("orbit-camera-touch-test");
    REQUIRE(tc_scene_alive(scene));
    tc_entity_pool_handle scene_pool = tc_entity_pool_registry_find(tc_scene_entity_pool(scene));
    REQUIRE(tc_entity_pool_handle_valid(scene_pool));

    CameraRig rig = make_camera_rig("touch-camera", scene_pool);
    tc_render_target_handle render_target = tc_render_target_new("touch-rt");
    REQUIRE(tc_render_target_handle_valid(render_target));
    tc_render_target_set_scene(render_target, scene);
    tc_render_target_set_camera(render_target, rig.camera->tc_component_ptr());

    tc_viewport_handle viewport = tc_viewport_new("touch-viewport", TC_SCENE_HANDLE_INVALID);
    REQUIRE(tc_viewport_handle_valid(viewport));
    tc_viewport_set_render_target(viewport, render_target);
    tc_viewport_set_pixel_rect(viewport, 0, 0, 800, 600);

    const termin::Vec3 initial_position = rig.entity.transform().global_position();
    PointerEvent first_down = make_pointer_event(viewport, 1, TC_POINTER_DOWN, 20.0, 20.0);
    rig.controller->on_pointer(&first_down);
    PointerEvent first_move = make_pointer_event(viewport, 1, TC_POINTER_MOVE, 40.0, 20.0, 20.0, 0.0);
    rig.controller->on_pointer(&first_move);
    const termin::Vec3 orbited_position = rig.entity.transform().global_position();
    CHECK(std::abs(orbited_position.x - initial_position.x) > 1e-6 ||
          std::abs(orbited_position.y - initial_position.y) > 1e-6);

    PointerEvent second_down = make_pointer_event(viewport, 2, TC_POINTER_DOWN, 140.0, 20.0);
    rig.controller->on_pointer(&second_down);
    const double radius_before_pinch = rig.controller->radius;
    PointerEvent second_move = make_pointer_event(viewport, 2, TC_POINTER_MOVE, 160.0, 20.0, 20.0, 0.0);
    rig.controller->on_pointer(&second_move);
    CHECK(rig.controller->radius < radius_before_pinch);

    PointerEvent first_cancel = make_pointer_event(viewport, 1, TC_POINTER_CANCEL, 40.0, 20.0);
    PointerEvent second_cancel = make_pointer_event(viewport, 2, TC_POINTER_CANCEL, 160.0, 20.0);
    rig.controller->on_pointer(&first_cancel);
    rig.controller->on_pointer(&second_cancel);

    tc_viewport_free(viewport);
    tc_render_target_free(render_target);
    tc_entity_free(rig.entity.handle());
    tc_scene_free(scene);
}

TEST_CASE("OrbitCameraController pan keeps the grabbed point under the cursor for both projections") {
    constexpr double width = 800.0;
    constexpr double height = 600.0;

    for (const CameraProjection projection : {CameraProjection::Perspective, CameraProjection::Orthographic}) {
        tc_scene_handle scene = tc_scene_new_named("orbit-camera-pan-test");
        REQUIRE(tc_scene_alive(scene));
        tc_entity_pool_handle scene_pool = tc_entity_pool_registry_find(tc_scene_entity_pool(scene));
        REQUIRE(tc_entity_pool_handle_valid(scene_pool));

        CameraRig rig = make_camera_rig("pan-camera", scene_pool);
        rig.camera->projection_type = projection;
        rig.camera->ortho_size = 3.0;
        tc_render_target_handle render_target = tc_render_target_new("pan-rt");
        REQUIRE(tc_render_target_handle_valid(render_target));
        tc_render_target_set_scene(render_target, scene);
        tc_render_target_set_camera(render_target, rig.camera->tc_component_ptr());
        tc_viewport_handle viewport = tc_viewport_new("pan-viewport", TC_SCENE_HANDLE_INVALID);
        REQUIRE(tc_viewport_handle_valid(viewport));
        tc_viewport_set_render_target(viewport, render_target);
        tc_viewport_set_pixel_rect(viewport, 0, 0, static_cast<int>(width), static_cast<int>(height));

        const termin::Vec3 grabbed = rig.controller->target();
        MouseButtonEvent press(viewport,
                               width * 0.5,
                               height * 0.5,
                               rig.controller->pan_mouse_button,
                               static_cast<int>(tcbase::Action::PRESS));
        rig.controller->on_mouse_button(&press);
        MouseMoveEvent move(viewport, 515.0, 365.0, 115.0, 65.0);
        rig.controller->on_mouse_move(&move);

        const termin::Vec3 projected = project_to_screen(*rig.camera, grabbed, width, height);
        CHECK_EQ(projected.x, Approx(515.0).epsilon(1e-10));
        CHECK_EQ(projected.y, Approx(365.0).epsilon(1e-10));

        tc_viewport_free(viewport);
        tc_render_target_free(render_target);
        tc_entity_free(rig.entity.handle());
        tc_scene_free(scene);
    }
}
