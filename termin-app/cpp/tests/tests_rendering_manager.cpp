#include "guard/guard.h"
#include "termin/render/rendering_manager.hpp"

extern "C" {
#include "core/tc_scene.h"
#include "core/tc_scene_render_mount.h"
#include "render/tc_display.h"
#include "render/tc_viewport.h"
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

TEST_CASE("RenderingManager attach_scene_full binds config viewports to scene")
{
    RenderingManager manager;

    tc_scene_handle scene = tc_scene_new();
    REQUIRE(tc_scene_handle_valid(scene));
    tc_scene_set_name(scene, "rendering-manager-viewport-scene-test");
    tc_scene_render_mount_extension_init();

    manager.set_display_factory([](const std::string& name) {
        return tc_display_new(name.c_str(), nullptr);
    });

    tc_render_target_config rt_config;
    tc_render_target_config_init(&rt_config);
    rt_config.name = "SceneRT";
    tc_scene_add_render_target_config(scene, &rt_config);

    tc_viewport_config config;
    tc_viewport_config_init(&config);
    config.name = "MainViewport";
    config.display_name = "Display0";
    config.render_target_name = "SceneRT";
    config.region[0] = 0.0f;
    config.region[1] = 0.0f;
    config.region[2] = 1.0f;
    config.region[3] = 1.0f;
    config.enabled = true;
    tc_scene_add_viewport_config(scene, &config);

    auto viewports = manager.attach_scene_full(scene);
    REQUIRE_EQ(viewports.size(), 1u);

    tc_display* display = manager.get_display_by_name("Display0");
    REQUIRE(display != nullptr);
    REQUIRE_EQ(tc_display_get_viewport_count(display), 1u);

    tc_viewport_handle viewport = tc_display_get_first_viewport(display);
    REQUIRE(tc_viewport_handle_valid(viewport));
    CHECK(tc_scene_handle_eq(tc_viewport_get_scene(viewport), scene));

    manager.detach_scene_full(scene);
    tc_scene_free(scene);
}
