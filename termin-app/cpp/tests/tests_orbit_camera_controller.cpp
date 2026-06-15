#include "guard_main.h"

#include "termin/camera/orbit_camera_controller.hpp"
#include "termin/entity/component.hpp"
#include "termin/entity/entity.hpp"
#include "termin/input/input_events.hpp"

#include <termin/camera/camera_component.hpp>

extern "C" {
#include "core/tc_entity_pool.h"
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

CameraRig make_camera_rig(const char* name)
{
    CameraRig rig;
    rig.entity = Entity::create(Entity::standalone_pool_handle(), name);
    rig.camera = new CameraComponent();
    rig.controller = new OrbitCameraController();
    rig.entity.add_component(rig.camera);
    rig.entity.add_component(rig.controller);
    return rig;
}

} // namespace

TEST_CASE("OrbitCameraController only handles events from viewports rendered by its camera")
{
    CameraRig primary = make_camera_rig("primary-camera");
    CameraRig secondary = make_camera_rig("secondary-camera");

    tc_render_target_handle primary_rt = tc_render_target_new("primary-rt");
    tc_render_target_handle secondary_rt = tc_render_target_new("secondary-rt");
    REQUIRE(tc_render_target_handle_valid(primary_rt));
    REQUIRE(tc_render_target_handle_valid(secondary_rt));

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
}
