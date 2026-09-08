#include "guard_main.h"

#include "termin/camera/orbit_camera_controller.hpp"
#include "termin/entity/component.hpp"
#include "termin/entity/entity.hpp"
#include "termin/input/input_events.hpp"
#include "termin/editor/editor_viewport_input_manager.hpp"

#include <termin/camera/camera_component.hpp>

#include <cmath>
#include <optional>

extern "C" {
#include "core/tc_entity_pool.h"
#include "core/tc_input_capability.h"
#include "core/tc_scene.h"
#include "render/tc_display.h"
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

TEST_CASE("Editor camera gestures stop on release and focus loss") {
    const tc_scene_handle scene = tc_scene_new_named("camera-gesture-lifetime");
    const tc_entity_pool_handle pool = tc_entity_pool_registry_find(tc_scene_entity_pool(scene));
    CameraRig rig = make_camera_rig("camera", pool);
    REQUIRE(tc_component_set_input_source_mask(rig.controller->tc_component_ptr(), TC_INPUT_SOURCE_EDITOR));
    const tc_render_target_handle target = tc_render_target_new("camera-gesture-target");
    tc_render_target_set_scene(target, scene);
    tc_render_target_set_camera(target, rig.camera->tc_component_ptr());
    const tc_viewport_handle viewport = tc_viewport_new("camera-gesture-viewport", scene);
    tc_viewport_set_render_target(viewport, target);
    // Editor cameras receive input through the viewport's internal hierarchy.
    tc_viewport_set_internal_entities(viewport, rig.entity.handle());
    tc_viewport_set_pixel_rect(viewport, 0, 0, 800, 600);
    const tc_display_handle display = tc_display_new("camera-gesture-display", nullptr);
    REQUIRE(tc_display_alive(display));
    {
        termin::EditorViewportInputManager manager(viewport, display);
        REQUIRE(tc_viewport_get_input_manager(viewport) != nullptr);
        for (int button : {rig.controller->orbit_mouse_button, rig.controller->pan_mouse_button}) {
            for (bool cancel : {false, true}) {
                manager.on_mouse_move(400.0, 300.0);
                const auto before = rig.entity.transform().global_position();
                manager.on_mouse_button(button, TC_INPUT_PRESS, 0, 1);
                manager.on_mouse_move(440.0, 320.0);
                const auto moved = rig.entity.transform().global_position();
                CHECK((moved - before).norm() > 1e-6);
                if (cancel)
                    manager.on_focus_lost();
                else
                    manager.on_mouse_button(button, TC_INPUT_RELEASE, 0, 1);
                manager.on_mouse_move(480.0, 340.0);
                manager.on_mouse_move(520.0, 360.0);
                CHECK((rig.entity.transform().global_position() - moved).norm() < 1e-12);
                if (cancel) {
                    // Late Up ends quarantine; hover must still leave the camera alone.
                    manager.on_mouse_button(button, TC_INPUT_RELEASE, 0, 1);
                    manager.on_mouse_move(560.0, 380.0);
                    manager.on_mouse_move(600.0, 400.0);
                    CHECK((rig.entity.transform().global_position() - moved).norm() < 1e-12);
                }
            }
        }
    }
    tc_viewport_free(viewport);
    tc_display_free(display);
    tc_render_target_free(target);
    tc_entity_free(rig.entity.handle());
    tc_scene_free(scene);
}

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

TEST_CASE("OrbitCameraController snaps all cube directions and preserves orbit state") {
    const struct { termin::ViewDirection direction; termin::Vec3 offset; } views[] = {
        {termin::ViewDirection::North, {0.0, 1.0, 0.0}},
        {termin::ViewDirection::South, {0.0, -1.0, 0.0}},
        {termin::ViewDirection::East, {1.0, 0.0, 0.0}},
        {termin::ViewDirection::West, {-1.0, 0.0, 0.0}},
        {termin::ViewDirection::Top, {0.0, 0.0, 1.0}},
        {termin::ViewDirection::Bottom, {0.0, 0.0, -1.0}},
        {termin::ViewDirection::NorthEast, {1.0, 1.0, 0.0}},
        {termin::ViewDirection::NorthWest, {-1.0, 1.0, 0.0}},
        {termin::ViewDirection::SouthEast, {1.0, -1.0, 0.0}},
        {termin::ViewDirection::SouthWest, {-1.0, -1.0, 0.0}},
        {termin::ViewDirection::TopNorth, {0.0, 1.0, 1.0}},
        {termin::ViewDirection::TopSouth, {0.0, -1.0, 1.0}},
        {termin::ViewDirection::TopEast, {1.0, 0.0, 1.0}},
        {termin::ViewDirection::TopWest, {-1.0, 0.0, 1.0}},
        {termin::ViewDirection::BottomNorth, {0.0, 1.0, -1.0}},
        {termin::ViewDirection::BottomSouth, {0.0, -1.0, -1.0}},
        {termin::ViewDirection::BottomEast, {1.0, 0.0, -1.0}},
        {termin::ViewDirection::BottomWest, {-1.0, 0.0, -1.0}},
        {termin::ViewDirection::TopNorthEast, {1.0, 1.0, 1.0}},
        {termin::ViewDirection::TopNorthWest, {-1.0, 1.0, 1.0}},
        {termin::ViewDirection::TopSouthEast, {1.0, -1.0, 1.0}},
        {termin::ViewDirection::TopSouthWest, {-1.0, -1.0, 1.0}},
        {termin::ViewDirection::BottomNorthEast, {1.0, 1.0, -1.0}},
        {termin::ViewDirection::BottomNorthWest, {-1.0, 1.0, -1.0}},
        {termin::ViewDirection::BottomSouthEast, {1.0, -1.0, -1.0}},
        {termin::ViewDirection::BottomSouthWest, {-1.0, -1.0, -1.0}},
    };
    for (const CameraProjection projection : {CameraProjection::Perspective, CameraProjection::Orthographic}) {
        CameraRig rig = make_camera_rig("snap-camera");
        rig.camera->projection_type = projection;
        rig.camera->ortho_size = 7.0;
        rig.controller->radius = 12.0;
        const termin::Vec3 focus{2.0, -3.0, 4.0};
        rig.controller->center_on(focus);
        for (const auto& view : views) {
            rig.controller->snap_view(view.direction);
            const termin::Vec3 offset = rig.entity.transform().global_position() - focus;
            const termin::Vec3 expected = view.offset.normalized();
            CHECK((offset - expected * 12.0).norm() < 1e-10);
            const termin::Quat rotation = rig.entity.transform().global_rotation();
            CHECK((rotation.rotate(termin::Vec3::unit_y()) + expected).norm() < 1e-10);
            CHECK((rig.controller->target() - focus).norm() < 1e-10);
            CHECK_EQ(rig.controller->radius, Approx(12.0).epsilon(1e-12));
            CHECK(rig.camera->projection_type == projection);
            CHECK_EQ(rig.camera->ortho_size, Approx(7.0).epsilon(1e-12));
            rig.controller->update(0.0f);
            CHECK((rig.controller->target() - focus).norm() < 1e-10);
            rig.controller->orbit(13.0, -9.0);
            CHECK((rig.controller->target() - focus).norm() < 1e-10);
            CHECK(std::abs((rig.entity.transform().global_position() - focus).norm() - 12.0) < 1e-10);
        }
        tc_entity_free(rig.entity.handle());
    }
}

TEST_CASE("OrbitCameraController pole views keep a deterministic frame through pan and zoom") {
    CameraRig rig = make_camera_rig("pole-camera");
    for (const auto direction : {termin::ViewDirection::Top, termin::ViewDirection::Bottom}) {
        rig.controller->snap_view(direction);
        const double sign = direction == termin::ViewDirection::Top ? 1.0 : -1.0;
        const termin::Quat rotation = rig.entity.transform().global_rotation();
        CHECK((rotation.rotate(termin::Vec3::unit_x()) - termin::Vec3::unit_x()).norm() < 1e-10);
        CHECK((rotation.rotate(termin::Vec3::unit_z()) - termin::Vec3{0.0, sign, 0.0}).norm() < 1e-10);
        const termin::Vec3 target = rig.controller->target();
        rig.controller->translate_target({2.0, 3.0});
        CHECK((rig.controller->target() - target - termin::Vec3{2.0, sign * 3.0, 0.0}).norm() < 1e-10);
        const double radius = rig.controller->radius;
        rig.controller->zoom(1.0);
        const termin::Vec3 offset = rig.entity.transform().global_position() - rig.controller->target();
        CHECK((offset - termin::Vec3{0.0, 0.0, sign * (radius + 1.0)}).norm() < 1e-10);
        CHECK((rig.entity.transform().global_rotation().rotate(termin::Vec3::unit_z()) -
               termin::Vec3{0.0, sign, 0.0}).norm() < 1e-10);
    }
    tc_entity_free(rig.entity.handle());
}

TEST_CASE("OrbitCameraController snap synchronizes an externally relocated camera") {
    CameraRig rig = make_camera_rig("relocated-snap-camera");
    const termin::Quat rotation = termin::Quat::from_axis_angle(termin::Vec3::unit_z(), 0.7);
    const termin::Vec3 position{10.0, -4.0, 8.0};
    rig.entity.transform().relocate(termin::Pose3{rotation, position});
    const termin::Vec3 expected_target = position + rotation.rotate(termin::Vec3::unit_y()) * rig.controller->radius;
    rig.controller->snap_view(termin::ViewDirection::North);
    CHECK((rig.controller->target() - expected_target).norm() < 1e-10);
    CHECK((rig.entity.transform().global_position() - expected_target -
           termin::Vec3{0.0, rig.controller->radius, 0.0}).norm() < 1e-10);
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
