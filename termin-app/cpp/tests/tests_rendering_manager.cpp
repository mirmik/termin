#include "guard/guard.h"
#include "termin/render/rendering_manager.hpp"

#include <string>

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
    config.region[0] = 0.0f;
    config.region[1] = 0.0f;
    config.region[2] = 1.0f;
    config.region[3] = 1.0f;
    config.enabled = true;
    config.render_target_name = "SceneRT";
    tc_scene_add_viewport_config(scene, &config);

    auto viewports = manager.attach_scene_full(scene);
    REQUIRE_EQ(viewports.size(), 1u);

    tc_display* display = manager.get_display_by_name("Display0");
    REQUIRE(display != nullptr);
    REQUIRE_EQ(tc_display_get_viewport_count(display), 1u);

    tc_viewport_handle viewport = tc_display_get_first_viewport(display);
    REQUIRE(tc_viewport_handle_valid(viewport));
    CHECK(tc_scene_handle_eq(tc_viewport_get_scene(viewport), scene));
    tc_render_target_handle rt = tc_viewport_get_render_target(viewport);
    REQUIRE(tc_render_target_handle_valid(rt));
    CHECK(std::string(tc_render_target_get_name(rt)) == "SceneRT");

    manager.detach_scene_full(scene);
    tc_scene_free(scene);
}

TEST_CASE("Viewport references render target without owning it")
{
    tc_viewport_handle viewport = tc_viewport_new("flat-viewport", TC_SCENE_HANDLE_INVALID);
    REQUIRE(tc_viewport_handle_valid(viewport));

    CHECK(!tc_render_target_handle_valid(tc_viewport_get_render_target(viewport)));

    tc_render_target_handle first = tc_render_target_new("first-target");
    tc_render_target_handle second = tc_render_target_new("second-target");
    REQUIRE(tc_render_target_handle_valid(first));
    REQUIRE(tc_render_target_handle_valid(second));
    CHECK(!tc_render_target_get_dynamic_resolution(first));

    tc_render_target_set_dynamic_resolution(first, true);
    CHECK(tc_render_target_get_dynamic_resolution(first));

    tc_viewport_set_render_target(viewport, first);
    CHECK(tc_render_target_handle_eq(tc_viewport_get_render_target(viewport), first));
    CHECK(tc_viewport_get_override_resolution(viewport));

    tc_viewport_set_override_resolution(viewport, false);
    CHECK(!tc_render_target_get_dynamic_resolution(first));

    tc_viewport_set_render_target(viewport, second);
    CHECK(tc_render_target_alive(first));
    CHECK(tc_render_target_handle_eq(tc_viewport_get_render_target(viewport), second));

    tc_viewport_free(viewport);
    CHECK(tc_render_target_alive(second));

    tc_render_target_free(first);
    tc_render_target_free(second);
}
