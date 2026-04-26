#include "guard/guard.h"
#include "termin/render/rendering_manager.hpp"

extern "C" {
#include "core/tc_scene.h"
}

using termin::RenderingManager;

TEST_CASE("RenderingManager detach_scene removes attached scene")
{
    RenderingManager manager;

    tc_scene_handle scene = tc_scene_new();
    REQUIRE(tc_scene_handle_valid(scene));
    tc_scene_set_name(scene, "rendering-manager-test");

    manager.attach_scene_full(scene);
    REQUIRE_EQ(manager.attached_scenes().size(), 1u);
    CHECK(tc_scene_handle_eq(manager.attached_scenes()[0], scene));

    manager.detach_scene(scene);
    CHECK_EQ(manager.attached_scenes().size(), 0u);

    manager.attach_scene_full(scene);
    REQUIRE_EQ(manager.attached_scenes().size(), 1u);

    manager.detach_scene_full(scene);
    CHECK_EQ(manager.attached_scenes().size(), 0u);

    tc_scene_free(scene);
}
