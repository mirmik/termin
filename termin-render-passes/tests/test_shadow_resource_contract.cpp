#include "guard_main.h"

GUARD_TEST_MAIN();

#include <memory>

#include <termin/lighting/shadow.hpp>
#include <termin/render/builtin_passes.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/render/frame_graph_resource_registry.hpp>
#include <termin/render/render_engine.hpp>
#include <termin/render/render_item_source.hpp>
#include <termin/render/render_scene_item_collector.hpp>
#include <termin/render/scene_render_services.hpp>
#include <termin/render/shadow_pass.hpp>
#include <termin/tc_scene.hpp>

extern "C" {
#include <render/tc_pass.h>
}

TEST_CASE("shadow resource is a registered generic non-texture resource") {
    if (termin::has_frame_graph_resource_type("shadow_map_array")) {
        REQUIRE(termin::unregister_frame_graph_resource_type("shadow_map_array"));
    }
    REQUIRE(termin::register_shadow_map_array_resource_type());
    CHECK(termin::register_shadow_map_array_resource_type());

    termin::ResourceSpec spec{
        "shadow_maps",
        "shadow_map_array",
        std::pair<int, int>{2048, 2048},
    };
    std::unique_ptr<termin::FrameGraphResource> resource(termin::create_frame_graph_resource(spec));
    REQUIRE(resource != nullptr);

    auto* shadow = dynamic_cast<termin::ShadowMapArrayResource*>(resource.get());
    REQUIRE(shadow != nullptr);
    CHECK(shadow->resolution == 2048);

    termin::ShadowMapArrayEntry entry;
    entry.depth_tex2 = tgfx::TextureHandle{42};
    shadow->add_entry(entry);
    const termin::FrameGraphResourceSampledTexture sampled = termin::frame_graph_resource_sampled_texture(*resource);
    CHECK(sampled.texture == entry.depth_tex2);
    CHECK(sampled.kind == termin::FrameGraphResourceSampledTextureKind::Depth);

    termin::ExecuteContext context;
    context.frame_graph_resources.emplace("shadow_maps", resource.get());
    context.frame_graph_resources.emplace("shadow_maps_alias", resource.get());
    CHECK(context.get_frame_graph_resource_as<termin::ShadowMapArrayResource>("shadow_maps") == shadow);
    CHECK(context.get_frame_graph_resource_as<termin::ShadowMapArrayResource>("shadow_maps_alias") == shadow);

    resource.reset();
    CHECK(termin::unregister_frame_graph_resource_type("shadow_map_array"));
}

TEST_CASE("ShadowPass receives and reuses its registered generic resource") {
    REQUIRE(termin::register_shadow_map_array_resource_type());
    if (!tc_pass_registry_has("CxxFramePass")) {
        termin::register_builtin_render_pass_types();
    }
    termin::ShadowPass::register_type();
    REQUIRE(tc_pass_registry_has("ShadowPass"));

    termin::TcSceneRef scene = termin::TcSceneRef::create("shadow-resource-contract");
    REQUIRE(scene.valid());
    termin::TcSceneRenderItemSource source(scene.handle(), nullptr, TC_SCENE_FILTER_NONE);
    termin::RenderItemSnapshot snapshot;
    REQUIRE(source.publish(snapshot, {}));

    termin::SceneRenderServices scene_services(scene);
    termin::RenderExecutionCapabilities capabilities;
    capabilities.add(scene_services);

    termin::RenderPipeline pipeline("shadow-resource-contract");
    REQUIRE(pipeline.is_valid());
    auto* shadow_pass = new termin::ShadowPass();
    pipeline.add_pass(shadow_pass->tc_pass_ptr());

    termin::RenderTargetContext target;
    target.name = "ShadowResourceTarget";
    target.render_rect = {0, 0, 1, 1};
    termin::RenderExecution execution;
    execution.pipeline = &pipeline;
    execution.targets.emplace(target.name,
                              termin::RenderExecutionTarget{
                                  .context = &target,
                                  .render_items = &snapshot,
                                  .capabilities = &capabilities,
                              });

    termin::RenderEngine engine;
    engine.execute_pipeline(execution);
    auto resource_it = pipeline.cache().frame_graph_resources.find("shadow_maps");
    REQUIRE(resource_it != pipeline.cache().frame_graph_resources.end());
    auto* shadow = dynamic_cast<termin::ShadowMapArrayResource*>(resource_it->second.get());
    REQUIRE(shadow != nullptr);

    termin::ShadowMapArrayEntry stale_entry;
    stale_entry.depth_tex2 = tgfx::TextureHandle{42};
    shadow->add_entry(stale_entry);
    engine.execute_pipeline(execution);
    CHECK(shadow->empty());

    pipeline.destroy();
    scene.destroy();
    tc_pass_registry_unregister("ShadowPass");
    CHECK(termin::unregister_frame_graph_resource_type("shadow_map_array"));
}
