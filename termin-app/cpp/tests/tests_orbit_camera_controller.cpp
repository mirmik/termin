#include "guard_main.h"

#include "termin/camera/orbit_camera_controller.hpp"
#include "termin/entity/component.hpp"
#include "termin/entity/entity.hpp"
#include "termin/input/input_events.hpp"

#include <termin/camera/camera_component.hpp>

extern "C" {
#include "core/tc_entity_pool.h"
#include "core/tc_scene.h"
#include "render/tc_render_target.h"
#include "render/tc_viewport.h"
}

using guard::Approx;
using termin::CameraComponent;
using termin::Entity;
using termin::OrbitCameraController;
using termin::ScrollEvent;

namespace {

struct CameraRig {
    Entity entity;
    CameraComponent* camera = nullptr;
    OrbitCameraController* controller = nullptr;
};

CameraRig make_camera_rig(
    const char* name,
    tc_entity_pool_handle pool = Entity::standalone_pool_handle())
{
    CameraRig rig;
    rig.entity = Entity::create(pool, name);
    rig.camera = new CameraComponent();
    rig.controller = new OrbitCameraController();
    rig.entity.add_component(rig.camera);
    rig.entity.add_component(rig.controller);
    return rig;
}

} // namespace

TEST_CASE("OrbitCameraController only handles events from viewports rendered by its camera")
{
    tc_scene_handle scene = tc_scene_new_named("orbit-camera-controller-test");
    REQUIRE(tc_scene_alive(scene));
    tc_entity_pool_handle scene_pool = tc_entity_pool_registry_find(
        tc_scene_entity_pool(scene));
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

TEST_CASE("OrbitCameraController center_on keeps camera offset from target")
{
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
