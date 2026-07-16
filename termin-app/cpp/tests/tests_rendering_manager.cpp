#include "guard_main.h"
#include "termin/render/rendering_manager.hpp"
#include "termin/render/render_attachment_context.hpp"
#include "termin/render/graph_compiler.hpp"
#include "termin/render/scene_pipeline_template.hpp"
#include "termin/render/tc_pass.hpp"

#include <string>
#include <optional>
#include <tcbase/trent/json.h>

extern "C" {
#include "core/tc_component.h"
#include "core/tc_entity_pool.h"
#include "core/tc_entity_pool_registry.h"
#include "core/tc_scene.h"
#include "core/tc_scene_render_mount.h"
#include "render/tc_display.h"
#include "render/tc_pipeline.h"
#include "render/tc_frame_graph.h"
#include "render/tc_pipeline_pool.h"
#include "inspect/tc_inspect_pass_adapter.h"
#include "render/tc_render_target.h"
#include "render/tc_render_target_pool.h"
#include "render/tc_pass.h"
#include "render/tc_viewport.h"
#include "render/tc_viewport_pool.h"
#include "tgfx/resources/tc_texture.h"
#include "tgfx/resources/tc_texture_registry.h"
}

using termin::RenderingManager;
using termin::RenderTopology;
using termin::RenderPipeline;
using termin::ResourceSpec;
using termin::TcScenePipelineTemplate;

namespace {

struct RenderLifecycleCounter {
    tc_component component;
    int attach_count = 0;
    int detach_count = 0;
    bool attach_context_valid = false;
    bool detach_context_valid = false;
    bool detach_saw_pipeline = false;
    std::optional<termin::RenderAttachmentContext> retained_context;
};

void lifecycle_counter_on_render_attach(
    tc_component* component,
    const tc_render_attachment_context* context
)
{
    auto* counter = reinterpret_cast<RenderLifecycleCounter*>(component);
    counter->attach_count++;
    counter->attach_context_valid = tc_render_attachment_context_valid(context);
    counter->retained_context = *reinterpret_cast<const termin::RenderAttachmentContext*>(context);
}

void lifecycle_counter_on_render_detach(
    tc_component* component,
    const tc_render_attachment_context* context
)
{
    auto* counter = reinterpret_cast<RenderLifecycleCounter*>(component);
    counter->detach_count++;
    counter->detach_context_valid = tc_render_attachment_context_valid(context);
    counter->detach_saw_pipeline = tc_pipeline_handle_valid(
        tc_render_attachment_context_get_pipeline(context, "lifecycle-template")
    );
    counter->retained_context = *reinterpret_cast<const termin::RenderAttachmentContext*>(context);
}

const tc_component_vtable lifecycle_counter_vtable = {
    .on_render_attach = lifecycle_counter_on_render_attach,
    .on_render_detach = lifecycle_counter_on_render_detach,
};

RenderLifecycleCounter make_render_lifecycle_counter()
{
    RenderLifecycleCounter counter;
    tc_component_init(&counter.component, &lifecycle_counter_vtable);
    return counter;
}

TcScenePipelineTemplate make_empty_scene_pipeline_template(const std::string& name)
{
    TcScenePipelineTemplate templ = TcScenePipelineTemplate::declare(name + "-uuid", name);
    templ.set_from_json(R"JSON(
{
  "name": "lifecycle_pipeline",
  "nodes": [
    { "type": "PipelineOutput", "x": 0.0, "y": 0.0, "node_type": "pipeline_output" }
  ],
  "connections": [],
  "viewport_frames": []
}
)JSON");
    return templ;
}

} // namespace

TEST_CASE("Graph compiler preserves FBO resource params on generated names")
{
    const char* json = R"JSON(
{
  "name": "graph_pipeline",
  "nodes": [
    { "type": "DepthPass", "x": 81.0, "y": -17.0 },
    {
      "type": "FBO",
      "x": -263.0,
      "y": -78.0,
      "node_type": "resource",
      "params": {
        "format": "r32f",
        "samples": "4",
        "size_mode": "fixed",
        "width": 1024,
        "height": 1024
      }
    }
  ],
  "connections": [
    { "from_node": 1, "from_socket": "fbo", "to_node": 0, "to_socket": "input_res" }
  ],
  "viewport_frames": []
}
)JSON";

    nos::trent data = nos::json::parse(json);
    tc::GraphData graph = tc::GraphData::from_trent(data);

    termin::RenderPipeline* pipeline = tc::compile_graph(graph);
    REQUIRE(pipeline != nullptr);

    const ResourceSpec* fbo_spec = nullptr;
    for (size_t i = 0; i < pipeline->spec_count(); i++) {
        const ResourceSpec* spec = pipeline->get_spec_at(i);
        REQUIRE(spec != nullptr);
        if (spec->resource == "fbo_1") {
            fbo_spec = spec;
            break;
        }
    }

    REQUIRE(fbo_spec != nullptr);
    REQUIRE(fbo_spec->format.has_value());
    CHECK(*fbo_spec->format == "r32f");
    CHECK(fbo_spec->samples == 4);
    REQUIRE(fbo_spec->size.has_value());
    CHECK(fbo_spec->size->first == 1024);
    CHECK(fbo_spec->size->second == 1024);

    pipeline->destroy();
    delete pipeline;
}

TEST_CASE("Graph compiler treats render target input as external resources")
{
    const char* json = R"JSON(
{
  "name": "graph_pipeline",
  "nodes": [
    { "type": "RenderTargetInput", "node_type": "render_target_input", "x": -420.0, "y": -80.0 },
    {
      "type": "FBO",
      "node_type": "resource",
      "x": -263.0,
      "y": -78.0,
      "params": { "format": "r32f", "size_mode": "fixed", "width": 1024, "height": 1024 }
    },
    { "type": "DepthPass", "x": 81.0, "y": -17.0 },
    { "type": "PipelineOutput", "node_type": "pipeline_output", "x": 409.0, "y": 40.0 }
  ],
  "connections": [
    { "from_node": 1, "from_socket": "fbo", "to_node": 2, "to_socket": "input_res" },
    { "from_node": 0, "from_socket": "color", "to_node": 2, "to_socket": "output_res_target" },
    { "from_node": 2, "from_socket": "output_res", "to_node": 3, "to_socket": "color" }
  ],
  "viewport_frames": []
}
)JSON";

    nos::trent data = nos::json::parse(json);
    tc::GraphData graph = tc::GraphData::from_trent(data);
    tc::ResourceNaming naming = tc::assign_resource_names(graph);

    REQUIRE(naming.socket_names.count("0") == 1u);
    CHECK(naming.socket_names["0"]["color"] == "RT_COLOR");
    CHECK(naming.socket_names["2"]["input_res"] == "fbo_1");
    CHECK(naming.socket_names["2"]["output_res"] == "DepthPass_2_output_res");
    CHECK(naming.socket_names["3"]["color"] == "DepthPass_2_output_res");
    CHECK(naming.resource_types["RT_COLOR"] == "external_color");
    CHECK(naming.external_resources["RT_COLOR"] == "render_target_color");
    REQUIRE(naming.fbo_compositions.count("DepthPass_2_output_res") == 1u);
    CHECK(naming.fbo_compositions["DepthPass_2_output_res"].color == "RT_COLOR");
    CHECK(naming.fbo_compositions["DepthPass_2_output_res"].depth == "RT_COLOR");

    termin::RenderPipeline* pipeline = tc::compile_graph(graph);
    REQUIRE(pipeline != nullptr);
    REQUIRE(pipeline->pass_count() == 3u);

    termin::TcPassRef pass(pipeline->get_pass_at(1));
    CHECK(pass.type_name() == "DepthPass");
    tc_value input_res = tc_pass_inspect_get(pass.ptr(), "input_res");
    REQUIRE(input_res.type == TC_VALUE_STRING);
    CHECK(std::string(input_res.data.s) == "fbo_1");
    tc_value_free(&input_res);
    tc_value output_res = tc_pass_inspect_get(pass.ptr(), "output_res");
    REQUIRE(output_res.type == TC_VALUE_STRING);
    CHECK(std::string(output_res.data.s) == "DepthPass_2_output_res");
    tc_value_free(&output_res);

    tc_frame_graph* fg = tc_pipeline_get_frame_graph(pipeline->handle());
    REQUIRE(fg != nullptr);
    CHECK(tc_frame_graph_get_error(fg) == TC_FG_OK);

    bool found_fbo = false;
    for (size_t i = 0; i < pipeline->spec_count(); i++) {
        const ResourceSpec* spec = pipeline->get_spec_at(i);
        REQUIRE(spec != nullptr);
        CHECK(spec->resource != "RT_COLOR");
        if (spec->resource == "fbo_1") {
            found_fbo = true;
            REQUIRE(spec->format.has_value());
            CHECK(*spec->format == "r32f");
        }
    }
    CHECK(found_fbo);

    pipeline->destroy();
    delete pipeline;
}

TEST_CASE("Graph compiler allows passes to write into render target input")
{
    const char* json = R"JSON(
{
  "name": "graph_pipeline",
  "nodes": [
    { "type": "RenderTargetInput", "node_type": "render_target_input", "x": -420.0, "y": -80.0 },
    {
      "type": "FBO",
      "node_type": "resource",
      "x": -263.0,
      "y": -78.0,
      "params": { "format": "r32f", "size_mode": "fixed", "width": 1024, "height": 1024 }
    },
    { "type": "DepthPass", "x": 81.0, "y": -17.0 },
    { "type": "PipelineOutput", "node_type": "pipeline_output", "x": 409.0, "y": 40.0 }
  ],
  "connections": [
    { "from_node": 1, "from_socket": "fbo", "to_node": 2, "to_socket": "input_res" },
    { "from_node": 0, "from_socket": "color", "to_node": 2, "to_socket": "output_res_target" },
    { "from_node": 2, "from_socket": "output_res", "to_node": 3, "to_socket": "color" }
  ],
  "viewport_frames": []
}
)JSON";

    nos::trent data = nos::json::parse(json);
    tc::GraphData graph = tc::GraphData::from_trent(data);
    termin::RenderPipeline* pipeline = tc::compile_graph(graph);
    REQUIRE(pipeline != nullptr);

    tc_frame_graph* fg = tc_pipeline_get_frame_graph(pipeline->handle());
    REQUIRE(fg != nullptr);
    CHECK(tc_frame_graph_get_error(fg) == TC_FG_OK);

    pipeline->destroy();
    delete pipeline;
}

TEST_CASE("Graph compiler asks pass metadata for inplace render target aliases")
{
    const char* json = R"JSON(
{
  "name": "graph_pipeline",
  "nodes": [
    { "type": "RenderTargetInput", "node_type": "render_target_input", "x": -204.0, "y": -16.0 },
    { "type": "DepthPass", "x": 106.0, "y": -122.0 },
    { "type": "PipelineOutput", "node_type": "pipeline_output", "x": 409.0, "y": 40.0 }
  ],
  "connections": [
    { "from_node": 0, "from_socket": "color", "to_node": 1, "to_socket": "input_res" },
    { "from_node": 1, "from_socket": "output_res", "to_node": 2, "to_socket": "color" }
  ],
  "viewport_frames": []
}
)JSON";

    nos::trent data = nos::json::parse(json);
    tc::GraphData graph = tc::GraphData::from_trent(data);
    tc::ResourceNaming naming = tc::assign_resource_names(graph);

    CHECK(naming.socket_names["1"]["input_res"] == "RT_COLOR");
    CHECK(naming.socket_names["1"]["output_res"] == "DepthPass_1_output_res");
    CHECK(naming.socket_names["2"]["color"] == "DepthPass_1_output_res");

    termin::RenderPipeline* pipeline = tc::compile_graph(graph);
    REQUIRE(pipeline != nullptr);
    REQUIRE(pipeline->pass_count() == 3u);
    CHECK(pipeline->spec_count() == 1u);

    termin::TcPassRef pass(pipeline->get_pass_at(1));
    CHECK(pass.type_name() == "DepthPass");
    tc_value input_res = tc_pass_inspect_get(pass.ptr(), "input_res");
    REQUIRE(input_res.type == TC_VALUE_STRING);
    CHECK(std::string(input_res.data.s) == "RT_COLOR");
    tc_value_free(&input_res);
    tc_value output_res = tc_pass_inspect_get(pass.ptr(), "output_res");
    REQUIRE(output_res.type == TC_VALUE_STRING);
    CHECK(std::string(output_res.data.s) == "DepthPass_1_output_res");
    tc_value_free(&output_res);

    pipeline->destroy();
    delete pipeline;
}

TEST_CASE("Graph compiler creates FBO attachment views for FboSplit")
{
    const char* json = R"JSON(
{
  "name": "graph_pipeline",
  "nodes": [
    { "type": "RenderTargetInput", "node_type": "render_target_input", "x": -204.0, "y": -16.0 },
    { "type": "FBO Split", "node_type": "fbo_split", "x": 106.0, "y": -122.0 }
  ],
  "connections": [
    { "from_node": 0, "from_socket": "color", "to_node": 1, "to_socket": "fbo" }
  ],
  "viewport_frames": []
}
)JSON";

    nos::trent data = nos::json::parse(json);
    tc::GraphData graph = tc::GraphData::from_trent(data);
    tc::ResourceNaming naming = tc::assign_resource_names(graph);

    CHECK(naming.socket_names["1"]["fbo"] == "RT_COLOR");
    CHECK(naming.socket_names["1"]["color"] == "RT_COLOR.color");
    CHECK(naming.socket_names["1"]["depth"] == "RT_COLOR.depth");
    CHECK(naming.resource_types["RT_COLOR.color"] == "color_texture");
    CHECK(naming.resource_types["RT_COLOR.depth"] == "depth_texture");
    REQUIRE(naming.resource_views.count("RT_COLOR.color") == 1u);
    CHECK(naming.resource_views["RT_COLOR.color"].parent == "RT_COLOR");
    CHECK(naming.resource_views["RT_COLOR.color"].attachment == termin::AttachmentKind::Color);
    REQUIRE(naming.resource_views.count("RT_COLOR.depth") == 1u);
    CHECK(naming.resource_views["RT_COLOR.depth"].parent == "RT_COLOR");
    CHECK(naming.resource_views["RT_COLOR.depth"].attachment == termin::AttachmentKind::Depth);
}

TEST_CASE("Graph compiler keeps FboJoin name and aliases it to parent FBO")
{
    const char* json = R"JSON(
{
  "name": "graph_pipeline",
  "nodes": [
    { "type": "RenderTargetInput", "node_type": "render_target_input", "x": -204.0, "y": -16.0 },
    { "type": "FBO Split", "node_type": "fbo_split", "x": 106.0, "y": -122.0 },
    { "type": "FBO Join", "node_type": "fbo_join", "x": 306.0, "y": -122.0, "name": "JoinedFbo" },
    { "type": "PipelineOutput", "node_type": "pipeline_output", "x": 409.0, "y": 40.0 }
  ],
  "connections": [
    { "from_node": 0, "from_socket": "color", "to_node": 1, "to_socket": "fbo" },
    { "from_node": 1, "from_socket": "color", "to_node": 2, "to_socket": "color" },
    { "from_node": 1, "from_socket": "depth", "to_node": 2, "to_socket": "depth" },
    { "from_node": 2, "from_socket": "fbo", "to_node": 3, "to_socket": "color" }
  ],
  "viewport_frames": []
}
)JSON";

    nos::trent data = nos::json::parse(json);
    tc::GraphData graph = tc::GraphData::from_trent(data);
    tc::ResourceNaming naming = tc::assign_resource_names(graph);

    CHECK(naming.socket_names["2"]["fbo"] == "JoinedFbo");
    CHECK(naming.socket_names["3"]["color"] == "JoinedFbo");
    REQUIRE(naming.fbo_compositions.count("JoinedFbo") == 1u);
    CHECK(naming.fbo_compositions["JoinedFbo"].color == "RT_COLOR.color");
    CHECK(naming.fbo_compositions["JoinedFbo"].depth == "RT_COLOR.depth");

    termin::RenderPipeline* pipeline = tc::compile_graph(graph);
    REQUIRE(pipeline != nullptr);
    CHECK(pipeline->pass_count() == 4u);
    CHECK(pipeline->spec_count() == 0u);
    termin::TcPassRef join_pass(pipeline->get_pass_at(2));
    REQUIRE(join_pass.type_name() == "GraphAliasPass");
    const char* aliases[4];
    size_t alias_count = tc_pass_get_inplace_aliases(join_pass.ptr(), aliases, 2);
    REQUIRE(alias_count == 1u);
    CHECK(std::string(aliases[0]) == "RT_COLOR");
    CHECK(std::string(aliases[1]) == "JoinedFbo");
    pipeline->destroy();
    delete pipeline;
}

TEST_CASE("Graph compiler supports DepthOnlyPass depth texture output")
{
    const char* json = R"JSON(
{
  "name": "graph_pipeline",
  "nodes": [
    { "type": "RenderTargetInput", "node_type": "render_target_input", "x": -204.0, "y": -16.0 },
    { "type": "FBO Split", "node_type": "fbo_split", "x": 0.0, "y": -122.0 },
    { "type": "DepthOnlyPass", "x": 220.0, "y": -122.0 },
    { "type": "FBO Join", "node_type": "fbo_join", "x": 440.0, "y": -122.0 }
  ],
  "connections": [
    { "from_node": 0, "from_socket": "color", "to_node": 1, "to_socket": "fbo" },
    { "from_node": 1, "from_socket": "depth", "to_node": 2, "to_socket": "output_res_target" },
    { "from_node": 2, "from_socket": "output_res", "to_node": 3, "to_socket": "depth" }
  ],
  "viewport_frames": []
}
)JSON";

    nos::trent data = nos::json::parse(json);
    tc::GraphData graph = tc::GraphData::from_trent(data);
    tc::ResourceNaming naming = tc::assign_resource_names(graph);

    CHECK(naming.socket_names["2"]["output_res"] == "DepthOnlyPass_2_output_res");
    REQUIRE(naming.resource_views.count("DepthOnlyPass_2_output_res") == 1u);
    CHECK(naming.resource_views["DepthOnlyPass_2_output_res"].parent == "RT_COLOR");
    CHECK(naming.resource_views["DepthOnlyPass_2_output_res"].attachment == termin::AttachmentKind::Depth);
    CHECK(naming.resource_types[naming.socket_names["2"]["output_res"]] == "depth_texture");
    CHECK(naming.socket_names["3"]["depth"] == naming.socket_names["2"]["output_res"]);

    termin::RenderPipeline* pipeline = tc::compile_graph(graph);
    REQUIRE(pipeline != nullptr);
    REQUIRE(pipeline->pass_count() == 4u);

    termin::TcPassRef pass(pipeline->get_pass_at(2));
    CHECK(pass.type_name() == "DepthOnlyPass");

    ResourceSpec pass_specs[4];
    size_t pass_spec_count = tc_pass_get_resource_specs(pass.ptr(), pass_specs, 4);
    REQUIRE(pass_spec_count == 1u);
    CHECK(pass_specs[0].resource == naming.socket_names["2"]["output_res"]);
    CHECK(pass_specs[0].resource_type == "depth_texture");

    pipeline->destroy();
    delete pipeline;
}

TEST_CASE("Graph compiler supports explicit depth color conversion passes")
{
    const char* json = R"JSON(
{
  "name": "graph_pipeline",
  "nodes": [
    { "type": "RenderTargetInput", "node_type": "render_target_input", "x": -204.0, "y": -16.0 },
    { "type": "FBO Split", "node_type": "fbo_split", "x": 0.0, "y": -122.0 },
    { "type": "DepthToColorPass", "x": 220.0, "y": -122.0 },
    { "type": "ColorToDepthPass", "x": 440.0, "y": -122.0 },
    { "type": "FBO Join", "node_type": "fbo_join", "x": 660.0, "y": -122.0, "name": "ConvertedFbo" }
  ],
  "connections": [
    { "from_node": 0, "from_socket": "color", "to_node": 1, "to_socket": "fbo" },
    { "from_node": 1, "from_socket": "depth", "to_node": 2, "to_socket": "input_res" },
    { "from_node": 2, "from_socket": "output_res", "to_node": 3, "to_socket": "input_res" },
    { "from_node": 2, "from_socket": "output_res", "to_node": 4, "to_socket": "color" },
    { "from_node": 3, "from_socket": "output_res", "to_node": 4, "to_socket": "depth" }
  ],
  "viewport_frames": []
}
)JSON";

    nos::trent data = nos::json::parse(json);
    tc::GraphData graph = tc::GraphData::from_trent(data);
    tc::ResourceNaming naming = tc::assign_resource_names(graph);

    CHECK(naming.resource_types[naming.socket_names["2"]["output_res"]] == "color_texture");
    CHECK(naming.resource_types[naming.socket_names["3"]["output_res"]] == "depth_texture");
    REQUIRE(naming.fbo_compositions.count("ConvertedFbo") == 1u);
    CHECK(naming.fbo_compositions["ConvertedFbo"].color == naming.socket_names["2"]["output_res"]);
    CHECK(naming.fbo_compositions["ConvertedFbo"].depth == naming.socket_names["3"]["output_res"]);

    termin::RenderPipeline* pipeline = tc::compile_graph(graph);
    REQUIRE(pipeline != nullptr);
    REQUIRE(pipeline->pass_count() == 5u);

    termin::TcPassRef pass0(pipeline->get_pass_at(2));
    termin::TcPassRef pass1(pipeline->get_pass_at(3));
    CHECK(pass0.type_name() == "DepthToColorPass");
    CHECK(pass1.type_name() == "ColorToDepthPass");

    pipeline->destroy();
    delete pipeline;
}

TEST_CASE("Graph compiler supports standalone texture resource nodes")
{
    const char* json = R"JSON(
{
  "name": "graph_pipeline",
  "nodes": [
    { "type": "Color Texture", "node_type": "resource", "name": "ScratchColor" },
    { "type": "Depth Texture", "node_type": "resource", "name": "ScratchDepth" },
    { "type": "ColorToDepthPass", "x": 220.0, "y": -122.0 },
    { "type": "DepthToColorPass", "x": 440.0, "y": -122.0 }
  ],
  "connections": [
    { "from_node": 0, "from_socket": "color", "to_node": 2, "to_socket": "input_res" },
    { "from_node": 1, "from_socket": "depth", "to_node": 2, "to_socket": "output_res_target" },
    { "from_node": 2, "from_socket": "output_res", "to_node": 3, "to_socket": "input_res" },
    { "from_node": 0, "from_socket": "color", "to_node": 3, "to_socket": "output_res_target" }
  ],
  "viewport_frames": []
}
)JSON";

    nos::trent data = nos::json::parse(json);
    tc::GraphData graph = tc::GraphData::from_trent(data);
    tc::ResourceNaming naming = tc::assign_resource_names(graph);

    CHECK(naming.socket_names["0"]["color"] == "ScratchColor");
    CHECK(naming.resource_types["ScratchColor"] == "color_texture");
    CHECK(naming.socket_names["1"]["depth"] == "ScratchDepth");
    CHECK(naming.resource_types["ScratchDepth"] == "depth_texture");
    CHECK(naming.socket_names["2"]["output_res"] == "ColorToDepthPass_2_output_res");
    CHECK(naming.socket_names["3"]["output_res"] == "DepthToColorPass_3_output_res");
    REQUIRE(naming.resource_views.count("ColorToDepthPass_2_output_res") == 1u);
    CHECK(naming.resource_views["ColorToDepthPass_2_output_res"].parent == "ScratchDepth");
    CHECK(naming.resource_views["ColorToDepthPass_2_output_res"].attachment == termin::AttachmentKind::Depth);
    REQUIRE(naming.resource_views.count("DepthToColorPass_3_output_res") == 1u);
    CHECK(naming.resource_views["DepthToColorPass_3_output_res"].parent == "ScratchColor");
    CHECK(naming.resource_views["DepthToColorPass_3_output_res"].attachment == termin::AttachmentKind::Color);

    termin::RenderPipeline* pipeline = tc::compile_graph(graph);
    REQUIRE(pipeline != nullptr);
    REQUIRE(pipeline->pass_count() == 2u);

    bool saw_color_spec = false;
    bool saw_depth_spec = false;
    for (const auto& spec : pipeline->specs()) {
        if (spec.resource == "ScratchColor") {
            saw_color_spec = true;
            CHECK(spec.resource_type == "color_texture");
        }
        if (spec.resource == "ScratchDepth") {
            saw_depth_spec = true;
            CHECK(spec.resource_type == "depth_texture");
        }
    }
    CHECK(saw_color_spec);
    CHECK(saw_depth_spec);

    pipeline->destroy();
    delete pipeline;
}

TEST_CASE("Graph compiler creates typed temporary texture resources for empty inputs")
{
    const char* json = R"JSON(
{
  "name": "graph_pipeline",
  "nodes": [
    { "type": "ColorToDepthPass", "x": 220.0, "y": -122.0 }
  ],
  "connections": [],
  "viewport_frames": []
}
)JSON";

    nos::trent data = nos::json::parse(json);
    tc::GraphData graph = tc::GraphData::from_trent(data);
    tc::ResourceNaming naming = tc::assign_resource_names(graph);

    REQUIRE(naming.socket_names["0"].count("input_res") == 1u);
    const std::string input_name = naming.socket_names["0"]["input_res"];
    CHECK(naming.resource_types[input_name] == "color_texture");
    CHECK(naming.resource_types[naming.socket_names["0"]["output_res"]] == "depth_texture");

    termin::RenderPipeline* pipeline = tc::compile_graph(graph);
    REQUIRE(pipeline != nullptr);

    bool saw_input_spec = false;
    bool saw_output_spec = false;
    for (const auto& spec : pipeline->specs()) {
        if (spec.resource == input_name) {
            saw_input_spec = true;
            CHECK(spec.resource_type == "color_texture");
        }
        if (spec.resource == naming.socket_names["0"]["output_res"]) {
            saw_output_spec = true;
            CHECK(spec.resource_type == "depth_texture");
        }
    }
    CHECK(saw_input_spec);
    CHECK(saw_output_spec);

    pipeline->destroy();
    delete pipeline;
}

TEST_CASE("Graph compiler rejects direct resource type conversion without split or join")
{
    const char* json = R"JSON(
{
  "name": "graph_pipeline",
  "nodes": [
    { "type": "RenderTargetInput", "node_type": "render_target_input", "x": -204.0, "y": -16.0 },
    { "type": "FBO Join", "node_type": "fbo_join", "x": 306.0, "y": -122.0, "name": "JoinedFbo" }
  ],
  "connections": [
    { "from_node": 0, "from_socket": "color", "to_node": 1, "to_socket": "depth" }
  ],
  "viewport_frames": []
}
)JSON";

    nos::trent data = nos::json::parse(json);
    tc::GraphData graph = tc::GraphData::from_trent(data);

    bool threw = false;
    try {
        termin::RenderPipeline* pipeline = tc::compile_graph(graph);
        if (pipeline) {
            pipeline->destroy();
            delete pipeline;
        }
    } catch (const tc::GraphCompileError&) {
        threw = true;
    }
    REQUIRE(threw);
}

TEST_CASE("Graph compiler keeps PipelineOutput as declarative graph endpoint")
{
    const char* json = R"JSON(
{
  "name": "graph_pipeline",
  "nodes": [
    { "type": "PipelineOutput", "x": 409.0, "y": 40.0, "node_type": "pipeline_output" },
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
    CHECK(pass.type_name() == "GraphAliasPass");

    pipeline->destroy();
    delete pipeline;
}

TEST_CASE("Graph compiler prefers External RT slot over display name")
{
    const char* json = R"JSON(
{
  "name": "graph_pipeline",
  "nodes": [
    { "type": "PipelineOutput", "x": 409.0, "y": 40.0, "node_type": "pipeline_output" },
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
    { "type": "PipelineOutput", "x": 409.0, "y": 40.0, "node_type": "pipeline_output" },
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
    RenderTopology topology;
    RenderingManager manager(topology);

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

TEST_CASE("RenderingManager render lifecycle notifications are not duplicated")
{
    RenderTopology topology;
    RenderingManager manager(topology);
    tc_scene_render_mount_extension_init();

    tc_scene_handle scene = tc_scene_new();
    REQUIRE(tc_scene_handle_valid(scene));
    tc_scene_set_name(scene, "rendering-manager-lifecycle-test");

    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    REQUIRE(pool != nullptr);
    tc_entity_id entity = tc_entity_pool_alloc(pool, "LifecycleEntity");
    REQUIRE(tc_entity_id_valid(entity));

    RenderLifecycleCounter counter = make_render_lifecycle_counter();
    tc_entity_pool_add_component(pool, entity, &counter.component);

    TcScenePipelineTemplate templ = make_empty_scene_pipeline_template("lifecycle-template");
    REQUIRE(templ.is_valid());
    REQUIRE(templ.is_loaded());
    tc_scene_add_pipeline_template(scene, templ.handle());

    manager.attach_scene(scene);
    CHECK_EQ(counter.attach_count, 1);
    CHECK_EQ(counter.detach_count, 0);
    CHECK(counter.attach_context_valid);
    REQUIRE(counter.retained_context.has_value());
    CHECK(!counter.retained_context->valid());

    manager.attach_scene(scene);
    CHECK_EQ(counter.attach_count, 2);
    CHECK_EQ(counter.detach_count, 0);

    manager.detach_scene(scene);
    CHECK_EQ(counter.attach_count, 2);
    CHECK_EQ(counter.detach_count, 1);
    CHECK(counter.detach_context_valid);
    CHECK(counter.detach_saw_pipeline);
    CHECK(!counter.retained_context->valid());

    tc_spt_free(templ.handle());
    tc_scene_free(scene);
}

TEST_CASE("RenderingManager rolls back partial topology when pipeline attach fails")
{
    RenderTopology topology;
    RenderingManager manager(topology);
    tc_scene_render_mount_extension_init();

    const size_t baseline_targets = tc_render_target_pool_count();
    tc_scene_handle scene = tc_scene_new();
    REQUIRE(tc_scene_handle_valid(scene));

    tc_render_target_config target_config;
    tc_render_target_config_init(&target_config);
    target_config.name = "RollbackTarget";
    tc_scene_add_render_target_config(scene, &target_config);

    TcScenePipelineTemplate unloaded = TcScenePipelineTemplate::declare(
        "rollback-template-uuid",
        "rollback-template"
    );
    REQUIRE(unloaded.is_valid());
    REQUIRE(!unloaded.is_loaded());
    tc_scene_add_pipeline_template(scene, unloaded.handle());

    CHECK(manager.attach_scene_full(scene).empty());
    CHECK(!topology.is_attached(scene));
    CHECK(topology.render_targets(scene).empty());
    CHECK(manager.managed_render_targets().empty());
    CHECK_EQ(tc_render_target_pool_count(), baseline_targets);

    tc_spt_free(unloaded.handle());
    tc_scene_free(scene);
}

TEST_CASE("RenderTopology preserves live pipelines when replacement compilation fails")
{
    RenderTopology topology;
    tc_scene_render_mount_extension_init();
    tc_scene_handle scene = tc_scene_new();
    REQUIRE(tc_scene_handle_valid(scene));

    TcScenePipelineTemplate live = make_empty_scene_pipeline_template("stable-pipeline");
    tc_scene_add_pipeline_template(scene, live.handle());
    REQUIRE(topology.attach_scene(scene));
    tc_pipeline_handle original = topology.get_pipeline(scene, "stable-pipeline");
    REQUIRE(tc_pipeline_handle_valid(original));

    TcScenePipelineTemplate unloaded = TcScenePipelineTemplate::declare(
        "failed-replacement-uuid",
        "failed-replacement"
    );
    tc_scene_add_pipeline_template(scene, unloaded.handle());
    CHECK(!topology.attach_scene(scene));
    CHECK(tc_pipeline_handle_eq(topology.get_pipeline(scene, "stable-pipeline"), original));
    CHECK(tc_pipeline_pool_alive(original));

    topology.detach_scene(scene);
    tc_spt_free(unloaded.handle());
    tc_spt_free(live.handle());
    tc_scene_free(scene);
}

TEST_CASE("RenderingManager attach_scene_full binds config viewports to scene")
{
    RenderTopology topology;
    RenderingManager manager(topology);

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

TEST_CASE("RenderingManager attach_scene_full keeps config viewport empty without render target")
{
    RenderTopology topology;
    RenderingManager manager(topology);

    tc_scene_handle scene = tc_scene_new();
    REQUIRE(tc_scene_handle_valid(scene));
    tc_scene_set_name(scene, "rendering-manager-empty-viewport-scene-test");
    tc_scene_render_mount_extension_init();

    manager.set_display_factory([](const std::string& name) {
        return tc_display_new(name.c_str(), nullptr);
    });

    const size_t baseline_targets = tc_render_target_pool_count();

    tc_viewport_config config;
    tc_viewport_config_init(&config);
    config.name = "EmptyViewport";
    config.display_name = "Display0";
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
    CHECK(!tc_render_target_handle_valid(tc_viewport_get_render_target(viewport)));
    CHECK_EQ(manager.managed_render_targets().size(), 0u);
    CHECK_EQ(tc_render_target_pool_count(), baseline_targets);

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

TEST_CASE("Render target ensure_textures refreshes owned texture size")
{
    tc_render_target_handle rt = tc_render_target_new("resize-target");
    REQUIRE(tc_render_target_handle_valid(rt));

    tc_render_target_set_width(rt, 128);
    tc_render_target_set_height(rt, 64);
    tc_render_target_ensure_textures(rt);

    tc_texture* color = tc_texture_get(tc_render_target_get_color_texture(rt));
    REQUIRE(color != nullptr);
    CHECK_EQ(color->width, 128u);
    CHECK_EQ(color->height, 64u);

    tc_texture_set_size_format(color, 32, 32, TC_TEXTURE_RGBA8);
    tc_render_target_ensure_textures(rt);

    CHECK_EQ(color->width, 128u);
    CHECK_EQ(color->height, 64u);

    tc_render_target_free(rt);
}

TEST_CASE("RenderingManager attach detach restores editor render counts")
{
    RenderTopology topology;
    RenderingManager manager(topology);
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
    REQUIRE_EQ(manager.managed_render_targets().size(), 1u);
    tc_render_target_handle restored_rt = manager.managed_render_targets()[0];
    CHECK(tc_render_target_get_dynamic_resolution(restored_rt));
    CHECK(tc_render_target_get_color_format(restored_rt) == TC_TEXTURE_RGBA8);
    CHECK(tc_render_target_get_depth_format(restored_rt) == TC_TEXTURE_DEPTH24);

    manager.detach_scene_full(scene);

    CHECK_EQ(tc_display_get_viewport_count(editor_display), 1u);
    CHECK(tc_render_target_alive(editor_rt));
    CHECK(tc_pipeline_pool_alive(editor_pipeline));
    CHECK_EQ(manager.managed_render_targets().size(), 0u);
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

TEST_CASE("Default pipeline color FBOs inherit output render target format")
{
    RenderTopology topology;
    RenderingManager manager(topology);
    tc_pipeline_handle pipeline_handle = manager.make_default_pipeline();
    REQUIRE(tc_pipeline_handle_valid(pipeline_handle));

    RenderPipeline pipeline(pipeline_handle);
    REQUIRE(pipeline.spec_count() > 0);

    bool found_color = false;
    for (size_t i = 0; i < pipeline.spec_count(); i++) {
        const ResourceSpec* spec = pipeline.get_spec_at(i);
        REQUIRE(spec != nullptr);
        if (spec->resource == "color") {
            found_color = true;
            REQUIRE(spec->format.has_value());
            CHECK(*spec->format == "render_target");
        }
    }

    CHECK(found_color);
    pipeline.destroy();
}
