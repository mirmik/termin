#include "guard/guard.h"
#include "termin/render/rendering_manager.hpp"
#include "termin/render/graph_compiler.hpp"
#include "termin/render/tc_pass.hpp"

#include <string>
#include <trent/json.h>

extern "C" {
#include "core/tc_scene.h"
#include "core/tc_scene_render_mount.h"
#include "render/tc_display.h"
#include "render/tc_pipeline.h"
#include "render/tc_pipeline_pool.h"
#include "render/tc_render_target.h"
#include "render/tc_render_target_pool.h"
#include "render/tc_viewport.h"
#include "render/tc_viewport_pool.h"
}

using termin::RenderingManager;

TEST_CASE("Graph compiler maps RenderTarget output node to viewport OUTPUT")
{
    const char* json = R"JSON(
{
  "name": "graph_pipeline",
  "nodes": [
    { "type": "SkyBoxPass", "x": -40.0, "y": -37.0 },
    { "type": "FBO", "x": -377.0, "y": -26.0, "node_type": "resource" },
    { "type": "RenderTarget", "x": 281.0, "y": -34.0, "node_type": "output" }
  ],
  "connections": [
    { "from_node": 1, "from_socket": "fbo", "to_node": 0, "to_socket": "input_res" },
    { "from_node": 0, "from_socket": "output_res", "to_node": 2, "to_socket": "color" }
  ],
  "viewport_frames": []
}
)JSON";

    nos::trent data = nos::json::parse(json);
    tc::GraphData graph = tc::GraphData::from_trent(data);
    tc::ResourceNaming naming = tc::assign_resource_names(graph);

    REQUIRE(naming.socket_names.count("0") == 1u);
    REQUIRE(naming.socket_names["0"].count("output_res") == 1u);
    CHECK(naming.socket_names["0"]["output_res"] == "OUTPUT");
}

TEST_CASE("Graph compiler synthesizes blit for External RT to RenderTarget")
{
    const char* json = R"JSON(
{
  "name": "graph_pipeline",
  "nodes": [
    { "type": "RenderTarget", "x": 409.0, "y": 40.0, "node_type": "output" },
    {
      "type": "External RT",
      "x": 49.0,
      "y": 21.0,
      "node_type": "external_rt",
      "params": { "slot": "fov_input" }
    }
  ],
  "connections": [
    { "from_node": 1, "from_socket": "fbo", "to_node": 0, "to_socket": "color" }
  ],
  "viewport_frames": []
}
)JSON";

    nos::trent data = nos::json::parse(json);
    tc::GraphData graph = tc::GraphData::from_trent(data);
    tc::ResourceNaming naming = tc::assign_resource_names(graph);

    REQUIRE(naming.socket_names.count("1") == 1u);
    REQUIRE(naming.socket_names["1"].count("fbo") == 1u);
    CHECK(naming.socket_names["1"]["fbo"] == "fov_input");

    termin::RenderPipeline* pipeline = tc::compile_graph(graph);
    REQUIRE(pipeline != nullptr);
    REQUIRE(pipeline->pass_count() == 1u);

    termin::TcPassRef pass(pipeline->get_pass_at(0));
    CHECK(pass.type_name() == "PresentToScreenPass");
    CHECK(pass.pass_name() == "OutputBlit");

    pipeline->destroy();
    delete pipeline;
}

TEST_CASE("Graph compiler prefers External RT slot over display name")
{
    const char* json = R"JSON(
{
  "name": "graph_pipeline",
  "nodes": [
    { "type": "RenderTarget", "x": 409.0, "y": 40.0, "node_type": "output" },
    {
      "type": "External RT",
      "x": 49.0,
      "y": 21.0,
      "node_type": "external_rt",
      "name": "External",
      "params": { "slot": "repeatTex" }
    }
  ],
  "connections": [
    { "from_node": 1, "from_socket": "fbo", "to_node": 0, "to_socket": "color" }
  ],
  "viewport_frames": []
}
)JSON";

    nos::trent data = nos::json::parse(json);
    tc::GraphData graph = tc::GraphData::from_trent(data);
    tc::ResourceNaming naming = tc::assign_resource_names(graph);

    REQUIRE(naming.socket_names.count("1") == 1u);
    REQUIRE(naming.socket_names["1"].count("fbo") == 1u);
    CHECK(naming.socket_names["1"]["fbo"] == "repeatTex");
}

TEST_CASE("Graph compiler uses unnamed slot for External RT without name")
{
    const char* json = R"JSON(
{
  "name": "graph_pipeline",
  "nodes": [
    { "type": "RenderTarget", "x": 409.0, "y": 40.0, "node_type": "output" },
    {
      "type": "External RT",
      "x": 49.0,
      "y": 21.0,
      "node_type": "external_rt",
      "params": { "slot": "" }
    }
  ],
  "connections": [
    { "from_node": 1, "from_socket": "fbo", "to_node": 0, "to_socket": "color" }
  ],
  "viewport_frames": []
}
)JSON";

    nos::trent data = nos::json::parse(json);
    tc::GraphData graph = tc::GraphData::from_trent(data);
    tc::ResourceNaming naming = tc::assign_resource_names(graph);

    REQUIRE(naming.socket_names.count("1") == 1u);
    REQUIRE(naming.socket_names["1"].count("fbo") == 1u);
    CHECK(naming.socket_names["1"]["fbo"] == "unnamed");
}

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

TEST_CASE("RenderingManager attach detach restores editor render counts")
{
    RenderingManager manager;
    tc_scene_render_mount_extension_init();

    tc_scene_handle editor_scene = tc_scene_new();
    REQUIRE(tc_scene_handle_valid(editor_scene));
    tc_scene_set_name(editor_scene, "editor-counts-scene");

    tc_display* editor_display = tc_display_new("Editor", nullptr);
    REQUIRE(editor_display != nullptr);
    tc_render_target_handle editor_rt = tc_render_target_new("(Editor)");
    REQUIRE(tc_render_target_handle_valid(editor_rt));
    tc_render_target_set_scene(editor_rt, editor_scene);
    tc_pipeline_handle editor_pipeline = tc_pipeline_create("(Editor)");
    REQUIRE(tc_pipeline_handle_valid(editor_pipeline));
    tc_render_target_set_pipeline(editor_rt, editor_pipeline);
    tc_viewport_handle editor_viewport = tc_viewport_new("(Editor)", editor_scene);
    REQUIRE(tc_viewport_handle_valid(editor_viewport));
    tc_viewport_set_render_target(editor_viewport, editor_rt);
    tc_display_add_viewport(editor_display, editor_viewport);
    manager.add_editor_display(editor_display);

    const size_t baseline_viewports = tc_viewport_pool_count();
    const size_t baseline_targets = tc_render_target_pool_count();
    const size_t baseline_pipelines = tc_pipeline_pool_count();

    manager.set_display_factory([](const std::string& name) {
        tc_display* display = tc_display_new(name.c_str(), nullptr);
        tc_display_set_auto_remove_when_empty(display, true);
        return display;
    });
    manager.set_pipeline_factory([](const std::string& name) {
        return tc_pipeline_create(name.c_str());
    });

    tc_scene_handle scene = tc_scene_new();
    REQUIRE(tc_scene_handle_valid(scene));
    tc_scene_set_name(scene, "game-counts-scene");

    tc_render_target_config rt_config;
    tc_render_target_config_init(&rt_config);
    rt_config.name = "GameRT";
    rt_config.pipeline_name = "Default";
    rt_config.dynamic_resolution = true;
    rt_config.color_format = "rgba8";
    rt_config.depth_format = "depth24";
    tc_scene_add_render_target_config(scene, &rt_config);

    tc_viewport_config vp_config;
    tc_viewport_config_init(&vp_config);
    vp_config.name = "GameViewport";
    vp_config.display_name = "GameDisplay";
    vp_config.render_target_name = "GameRT";
    vp_config.region[0] = 0.0f;
    vp_config.region[1] = 0.0f;
    vp_config.region[2] = 1.0f;
    vp_config.region[3] = 1.0f;
    vp_config.enabled = true;
    tc_scene_add_viewport_config(scene, &vp_config);

    auto viewports = manager.attach_scene_full(scene);
    REQUIRE_EQ(viewports.size(), 1u);
    CHECK_EQ(tc_display_get_viewport_count(editor_display), 1u);
    CHECK_EQ(tc_viewport_pool_count(), baseline_viewports + 1);
    CHECK_EQ(tc_render_target_pool_count(), baseline_targets + 1);
    CHECK_EQ(tc_pipeline_pool_count(), baseline_pipelines + 1);
    REQUIRE_EQ(manager.standalone_render_targets().size(), 1u);
    tc_render_target_handle restored_rt = manager.standalone_render_targets()[0];
    CHECK(tc_render_target_get_dynamic_resolution(restored_rt));
    CHECK(tc_render_target_get_color_format(restored_rt) == TC_TEXTURE_RGBA8);
    CHECK(tc_render_target_get_depth_format(restored_rt) == TC_TEXTURE_DEPTH24);

    manager.detach_scene_full(scene);

    CHECK_EQ(tc_display_get_viewport_count(editor_display), 1u);
    CHECK(tc_render_target_alive(editor_rt));
    CHECK(tc_pipeline_pool_alive(editor_pipeline));
    CHECK_EQ(manager.standalone_render_targets().size(), 0u);
    CHECK_EQ(tc_viewport_pool_count(), baseline_viewports);
    CHECK_EQ(tc_render_target_pool_count(), baseline_targets);
    CHECK_EQ(tc_pipeline_pool_count(), baseline_pipelines);

    tc_display_remove_viewport(editor_display, editor_viewport);
    tc_viewport_free(editor_viewport);
    tc_pipeline_destroy(editor_pipeline);
    tc_render_target_free(editor_rt);
    tc_display_free(editor_display);
    tc_scene_free(scene);
    tc_scene_free(editor_scene);
}
