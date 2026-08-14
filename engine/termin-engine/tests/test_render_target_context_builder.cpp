#include "guard_main.h"
#include "render_target_context_builder.hpp"

#include <algorithm>
#include <memory>
#include <span>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include <termin/render/render_engine.hpp>
#include <tgfx2/graphics_host.hpp>
#include <tgfx2/i_render_device.hpp>

extern "C" {
#include "render/tc_render_target.h"
#include "tgfx/resources/tc_texture.h"
#include "tgfx/resources/tc_texture_registry.h"
}

namespace {

    class ContextBuilderTestDevice final : public tgfx::IRenderDevice {
    public:
        tgfx::BackendType backend_type() const override {
            return tgfx::BackendType::Null;
        }
        tgfx::BackendCapabilities capabilities() const override {
            return {};
        }
        void wait_idle() override {}

        tgfx::BufferHandle create_buffer(const tgfx::BufferDesc&) override {
            return {};
        }
        tgfx::TextureHandle create_texture(const tgfx::TextureDesc&) override {
            return {};
        }
        tgfx::SamplerHandle create_sampler(const tgfx::SamplerDesc&) override {
            return {};
        }
        tgfx::ShaderHandle create_shader(const tgfx::ShaderDesc&) override {
            return {};
        }
        tgfx::PipelineHandle create_pipeline(const tgfx::PipelineDesc&) override {
            return {};
        }
        tgfx::ResourceSetHandle create_bound_resource_set(const tgfx::BoundResourceSetDesc&) override {
            return {};
        }

        void destroy(tgfx::BufferHandle) override {}
        void destroy(tgfx::TextureHandle) override {}
        void destroy(tgfx::SamplerHandle) override {}
        void destroy(tgfx::ShaderHandle) override {}
        void destroy(tgfx::PipelineHandle) override {}
        void destroy(tgfx::ResourceSetHandle) override {}

        void upload_buffer(tgfx::BufferHandle, std::span<const uint8_t>, uint64_t = 0) override {}
        void upload_texture(tgfx::TextureHandle, std::span<const uint8_t>, uint32_t = 0) override {}
        void upload_texture_region(tgfx::TextureHandle,
                                   uint32_t,
                                   uint32_t,
                                   uint32_t,
                                   uint32_t,
                                   std::span<const uint8_t>,
                                   uint32_t = 0) override {}
        void read_buffer(tgfx::BufferHandle, std::span<uint8_t>, uint64_t = 0) override {}
        tgfx::TextureDesc texture_desc(tgfx::TextureHandle) const override {
            return {};
        }
        std::unique_ptr<tgfx::ICommandList> create_command_list(tgfx::QueueType = tgfx::QueueType::Graphics) override {
            return {};
        }
        void submit(tgfx::ICommandList&) override {}
        void present() override {}

        tgfx::TextureHandle ensure_tc_texture(tc_texture* texture) override {
            if (!texture)
                return {};
            return tgfx::TextureHandle{texture->header.pool_index + 100u};
        }
    };

} // namespace

TEST_CASE("Special render target providers inherit named pipeline textures") {
    tc_texture_init();

    termin::RenderTopology topology;
    termin::RenderingManager manager(topology);
    termin::RenderEngine engine;
    auto host = tgfx::GraphicsHost::adopt_isolated_device(std::make_unique<ContextBuilderTestDevice>());
    REQUIRE(host != nullptr);
    engine.set_graphics_host(*host);
    manager.set_render_engine(&engine);

    tc_render_target_handle panel = tc_render_target_new("PanelTexture");
    tc_render_target_handle xr = tc_render_target_new("Headset");
    REQUIRE(tc_render_target_handle_valid(panel));
    REQUIRE(tc_render_target_handle_valid(xr));
    tc_render_target_set_kind(xr, TC_RENDER_TARGET_XR_STEREO);
    tc_render_target_ensure_textures(panel);
    REQUIRE(tc_texture_is_valid(tc_render_target_get_color_texture(panel)));

    tc_value params = tc_value_dict_new();
    tc_value_dict_set(&params, "PANEL_COLOR", tc_value_string("PanelTexture"));
    tc_render_target_set_pipeline_params(xr, &params);
    tc_value_free(&params);

    std::vector<tc_render_target_handle> managed_targets{panel, xr};
    std::unordered_map<int, termin::RenderTargetContextProvider> providers;
    providers.emplace(TC_RENDER_TARGET_XR_STEREO,
                      [](termin::RenderingManager&,
                         tc_render_target_handle,
                         const std::string&,
                         tc_entity_handle,
                         std::unordered_map<std::string, termin::RenderTargetContext>& contexts,
                         std::string& default_context) {
                          termin::RenderTargetContext context;
                          context.name = "Stereo";
                          context.external_textures["XR_MULTIVIEW_TARGET"] = tgfx::TextureHandle{7};
                          contexts.emplace(context.name, std::move(context));
                          default_context = "Stereo";
                          return true;
                      });
    std::unordered_set<uint64_t> warnings;
    std::unordered_map<std::string, termin::RenderTargetContext> contexts;
    std::unordered_map<std::string, tc_entity_handle> internal_entities_by_context;
    std::string default_context;
    const std::string base_context;

    termin::rendering_manager_detail::RenderTargetContextBuildRequest request{
        manager,
        &engine,
        xr,
        base_context,
        TC_ENTITY_HANDLE_INVALID,
        1440,
        1584,
        managed_targets,
        providers,
        warnings,
        contexts,
        internal_entities_by_context,
        default_context,
    };
    REQUIRE(termin::rendering_manager_detail::build_render_target_contexts(request));
    REQUIRE_EQ(contexts.size(), 1u);
    REQUIRE(contexts.contains("Stereo"));
    const termin::RenderTargetContext& context = contexts.at("Stereo");
    CHECK(context.external_textures.at("XR_MULTIVIEW_TARGET") == tgfx::TextureHandle{7});

    tc_texture* panel_texture = tc_texture_get(tc_render_target_get_color_texture(panel));
    REQUIRE(panel_texture != nullptr);
    CHECK(context.external_textures.at("PANEL_COLOR") == tgfx::TextureHandle{panel_texture->header.pool_index + 100u});
    const auto panel_source = std::find_if(
        context.material_texture_sources.begin(),
        context.material_texture_sources.end(),
        [](const termin::ResolvedMaterialTextureSource& source) {
            return source.kind == "render_target" && source.source_name == "PanelTexture" &&
                   source.channel == "color";
        });
    REQUIRE(panel_source != context.material_texture_sources.end());
    CHECK(panel_source->texture == tgfx::TextureHandle{panel_texture->header.pool_index + 100u});

    tc_render_target_free(xr);
    tc_render_target_free(panel);
    host->close();
    tc_texture_shutdown();
}

GUARD_TEST_MAIN();
