#include <termin/render/execute_context.hpp>
#include <termin/render/standard_gbuffer_pass.hpp>

#include <components/mesh_component.hpp>
#include <termin/render/mesh_renderer.hpp>
#include <termin/render/render_scene_item_collector.hpp>
#include <termin/render/scene_render_services.hpp>
#include <termin/tc_scene.hpp>

#include <tgfx/resources/tc_material_registry.h>
#include <tgfx/resources/tc_mesh_registry.h>
#include <tgfx/resources/tc_shader_registry.h>
#include <tgfx/tgfx_material_handle.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>
#include <tgfx/tgfx_shader_handle.hpp>
#include <tgfx2/device_factory.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/pipeline_cache.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

extern "C" {
#include <core/tc_scene_pool.h>
}

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <exception>
#include <filesystem>
#include <memory>
#include <string>
#include <vector>

namespace {

    constexpr uint32_t WIDTH = 64;
    constexpr uint32_t HEIGHT = 64;

    constexpr const char* STANDARD_EVALUATOR = R"slang(
struct FragmentInput {
    float4 screen_pos : SV_Position;
    float3 world_pos : TEXCOORD0;
    float3 normal_world : TEXCOORD1;
    float2 uv : TEXCOORD2;
    float3 tangent_world : TEXCOORD3;
    float3 bitangent_world : TEXCOORD4;
    float tbn_valid : TEXCOORD5;
};

TerminStandardSurfaceV1 evaluate_standard_surface(FragmentInput input) {
    TerminStandardSurfaceV1 surface;
    surface.base_color = float3(0.2, 0.4, 0.6);
    surface.normal_world = normalize(input.normal_world);
    surface.metallic = 0.25;
    surface.perceptual_roughness = 0.35;
    surface.occlusion = 0.75;
    surface.emission = float3(0.02, 0.04, 0.06);
    surface.opacity = 1.0;
    return surface;
}
)slang";

    struct SmokeVertex {
        float position[3];
        float normal[3];
        float uv[2];
        float tangent[4];
    };

    struct ScopedArtifactConfiguration {
        std::filesystem::path root;

        ScopedArtifactConfiguration() {
            const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
            root = std::filesystem::temp_directory_path() /
                   ("termin-standard-gbuffer-pixel-smoke-" + std::to_string(unique));
            std::filesystem::remove_all(root);
            termin::tgfx2_set_shader_artifact_root(root.string().c_str());
            termin::tgfx2_set_shader_cache_root("");
#ifdef TERMIN_STANDARD_GBUFFER_PIXEL_SMOKE_SHADERC
            termin::tgfx2_set_shader_compiler_path(TERMIN_STANDARD_GBUFFER_PIXEL_SMOKE_SHADERC);
#endif
            termin::tgfx2_set_shader_dev_compile_enabled(true);
        }

        ~ScopedArtifactConfiguration() {
            termin::tgfx2_set_shader_dev_compile_enabled(false);
            termin::tgfx2_set_shader_compiler_path("");
            termin::tgfx2_set_shader_cache_root("");
            termin::tgfx2_set_shader_artifact_root("");
            std::filesystem::remove_all(root);
        }
    };

    bool near(float actual, float expected, float tolerance = 0.04f) {
        return std::abs(actual - expected) <= tolerance;
    }

    termin::TcShader create_surface_producer() {
        const char* semantics[] = {
            "world_pos",
            "normal_world",
            "uv",
            "tangent_world",
            "bitangent_world",
            "tbn_valid",
        };
        const uint32_t types[] = {
            TC_SHADER_CONTRACT_VALUE_FLOAT3,
            TC_SHADER_CONTRACT_VALUE_FLOAT3,
            TC_SHADER_CONTRACT_VALUE_FLOAT2,
            TC_SHADER_CONTRACT_VALUE_FLOAT3,
            TC_SHADER_CONTRACT_VALUE_FLOAT3,
            TC_SHADER_CONTRACT_VALUE_FLOAT,
        };
        tc_shader_fragment_input inputs[6]{};
        for (uint32_t index = 0; index < 6u; ++index) {
            std::snprintf(inputs[index].semantic, sizeof(inputs[index].semantic), "%s", semantics[index]);
            inputs[index].type = types[index];
        }

        const tc_shader_surface_producer_desc producer = {
            TC_SHADER_SURFACE_PRODUCER_SCHEMA_VERSION,
            TC_STANDARD_PBR_SURFACE_CONTRACT_ID,
            TC_STANDARD_PBR_SURFACE_CONTRACT_VERSION,
            "TerminStandardSurfaceV1",
            "evaluate_standard_surface",
            STANDARD_EVALUATOR,
            "termin.surface.standard-pbr@1:gbuffer-pixel-smoke:v1",
            inputs,
            6u,
            nullptr,
            0u,
        };

        termin::TcShaderCreateInfo create_info{};
        create_info.sources.fragment = STANDARD_EVALUATOR;
        create_info.sources.name = "StandardGBufferPixelSmokeProducer";
        create_info.sources.fragment_entry = "evaluate_standard_surface";
        create_info.uuid = "termin-standard-gbuffer-pixel-smoke-producer";
        create_info.language = TC_SHADER_LANGUAGE_SLANG;
        create_info.artifact_policy = TC_SHADER_ARTIFACT_REQUIRED;
        create_info.surface_producer = &producer;
        return termin::TcShader::from_sources(create_info);
    }

    termin::TcMaterial create_material(const termin::TcShader& producer) {
        termin::TcMaterial material = termin::TcMaterial::create("StandardGBufferPixelSmokeMaterial",
                                                                 "termin-standard-gbuffer-pixel-smoke-material");
        if (!material.is_valid()) {
            return {};
        }
        tc_material_phase* phase = material.add_phase(producer.handle, "opaque", 0);
        if (!phase) {
            return {};
        }
        phase->state = tc_render_state_opaque();
        phase->state.cull = 0;
        return material;
    }

    termin::TcMesh create_mesh() {
        const SmokeVertex vertices[] = {
            {{-0.7f, -0.7f, 0.0f}, {0.0f, 0.0f, 1.0f}, {0.0f, 0.0f}, {1.0f, 0.0f, 0.0f, 1.0f}},
            {{0.7f, -0.7f, 0.0f}, {0.0f, 0.0f, 1.0f}, {1.0f, 0.0f}, {1.0f, 0.0f, 0.0f, 1.0f}},
            {{0.0f, 0.7f, 0.0f}, {0.0f, 0.0f, 1.0f}, {0.5f, 1.0f}, {1.0f, 0.0f, 0.0f, 1.0f}},
        };
        const uint32_t indices[] = {0, 1, 2};
        const tc_vertex_layout layout = tc_vertex_layout_pos_normal_uv_tangent();
        termin::TcMeshCreateInfo create_info;
        create_info.data = termin::TcMeshInterleavedDataView{vertices, 3, indices, 3, &layout};
        create_info.name = "StandardGBufferPixelSmokeTriangle";
        create_info.uuid_hint = "termin-standard-gbuffer-pixel-smoke-triangle";
        return termin::TcMesh::from_interleaved(create_info);
    }

    termin::TcSceneRef create_scene(const termin::TcMesh& mesh, const termin::TcMaterial& material) {
        termin::TcSceneRef scene = termin::TcSceneRef::create("standard-gbuffer-pixel-smoke");
        termin::Entity entity = scene.create_entity("StandardGBufferTriangle");
        if (!entity.valid()) {
            return {};
        }
        auto* mesh_component = new termin::MeshComponent();
        mesh_component->set_mesh(mesh);
        entity.add_component(mesh_component);
        auto* renderer = new termin::MeshRenderer();
        renderer->set_material(material);
        entity.add_component(renderer);
        return scene;
    }

    tgfx::TextureHandle create_color_target(tgfx::IRenderDevice& device) {
        tgfx::TextureDesc desc;
        desc.width = WIDTH;
        desc.height = HEIGHT;
        desc.format = tgfx::PixelFormat::RGBA16F;
        desc.usage = tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::CopySrc;
        return device.create_texture(desc);
    }

    int run_smoke() {
        ScopedArtifactConfiguration artifacts;
        termin::TcShader producer = create_surface_producer();
        termin::TcMaterial material = create_material(producer);
        termin::TcMesh mesh = create_mesh();
        termin::TcSceneRef scene = create_scene(mesh, material);
        if (!producer.is_valid() || !material.is_valid() || !mesh.is_valid() || !scene.valid()) {
            std::fprintf(stderr, "Failed to create StandardGBufferPass smoke scene resources\n");
            return 1;
        }

        std::unique_ptr<tgfx::IRenderDevice> device;
        try {
            device = tgfx::create_device(tgfx::BackendType::Vulkan);
        } catch (const std::exception& error) {
            std::fprintf(stderr, "Failed to create Vulkan device: %s\n", error.what());
            return 1;
        }

        const tgfx::TextureHandle base_ao = create_color_target(*device);
        const tgfx::TextureHandle normal_rough = create_color_target(*device);
        const tgfx::TextureHandle metal_emit = create_color_target(*device);
        tgfx::TextureDesc depth_desc;
        depth_desc.width = WIDTH;
        depth_desc.height = HEIGHT;
        depth_desc.format = tgfx::PixelFormat::D32F;
        depth_desc.usage = tgfx::TextureUsage::DepthStencilAttachment | tgfx::TextureUsage::CopySrc;
        const tgfx::TextureHandle depth = device->create_texture(depth_desc);
        if (!base_ao || !normal_rough || !metal_emit || !depth) {
            std::fprintf(stderr, "Failed to create StandardGBufferPass MRT textures\n");
            return 1;
        }

        tgfx::PipelineCache cache(*device);
        tgfx::RenderContext2 render_context(*device, cache);
        termin::RenderItemSnapshot snapshot;
        termin::TcSceneRenderItemSource source(scene.handle());
        termin::RenderItemSourceRequest source_request{};
        source_request.debug_name = "StandardGBufferPixelSmoke";
        if (!source.publish(snapshot, source_request)) {
            std::fprintf(stderr, "Failed to publish StandardGBufferPass RenderItem snapshot\n");
            return 1;
        }

        termin::ExecuteContext context;
        context.ctx2 = &render_context;
        context.render_item_snapshot = &snapshot;
        context.tex2_writes.emplace("gbuffer_base_ao", base_ao);
        context.tex2_writes.emplace("gbuffer_normal_rough", normal_rough);
        context.tex2_writes.emplace("gbuffer_metal_emit", metal_emit);
        context.tex2_depth_writes.emplace("scene_depth", depth);
        context.render_rect = {0, 0, static_cast<int>(WIDTH), static_cast<int>(HEIGHT)};
        context.view.primary = termin::RenderCamera{};
        const termin::SceneRenderServices scene_services(scene);
        termin::RenderExecutionCapabilities capabilities;
        capabilities.add(scene_services);
        context.capabilities = &capabilities;

        termin::StandardGBufferPass pass;
        std::vector<termin::TcShader> packaged_usages;
        pass.collect_scene_shader_usages(
            scene.handle(), [&](termin::TcShader shader) { packaged_usages.push_back(std::move(shader)); });
        render_context.begin_frame();
        pass.execute(context);
        render_context.end_frame();
        device->wait_idle();

        std::vector<float> base_pixels(WIDTH * HEIGHT * 4u);
        std::vector<float> normal_pixels(WIDTH * HEIGHT * 4u);
        std::vector<float> metal_pixels(WIDTH * HEIGHT * 4u);
        std::vector<float> depth_pixels(WIDTH * HEIGHT);
        const bool read_ok = device->read_texture_rgba_float(base_ao, base_pixels.data()) &&
                             device->read_texture_rgba_float(normal_rough, normal_pixels.data()) &&
                             device->read_texture_rgba_float(metal_emit, metal_pixels.data()) &&
                             device->read_texture_depth_float(depth, depth_pixels.data());
        const size_t center = (HEIGHT / 2u * WIDTH + WIDTH / 2u);
        const size_t corner = 0;
        const float* base = &base_pixels[center * 4u];
        const float* normal = &normal_pixels[center * 4u];
        const float* metal = &metal_pixels[center * 4u];

        const bool center_ok = near(base[0], 0.2f) && near(base[1], 0.4f) && near(base[2], 0.6f) &&
                               near(base[3], 0.75f) && near(normal[0], 0.0f) && near(normal[1], 0.0f) &&
                               near(normal[2], 1.0f) && near(normal[3], 0.35f) && near(metal[0], 0.25f) &&
                               near(metal[1], 0.02f) && near(metal[2], 0.04f) && near(metal[3], 0.06f) &&
                               depth_pixels[center] < 0.99f;
        const bool corner_ok = near(base_pixels[corner * 4u], 0.0f) && near(normal_pixels[corner * 4u], 0.0f) &&
                               near(metal_pixels[corner * 4u], 0.0f) && depth_pixels[corner] > 0.99f;

        std::printf("base/AO center: %.3f %.3f %.3f %.3f\n", base[0], base[1], base[2], base[3]);
        std::printf("normal/rough center: %.3f %.3f %.3f %.3f\n", normal[0], normal[1], normal[2], normal[3]);
        std::printf("metal/emission center: %.3f %.3f %.3f %.3f\n", metal[0], metal[1], metal[2], metal[3]);
        std::printf("depth center/corner: %.3f %.3f\n", depth_pixels[center], depth_pixels[corner]);

        device->destroy(base_ao);
        device->destroy(normal_rough);
        device->destroy(metal_emit);
        device->destroy(depth);
        const bool usage_ok =
            packaged_usages.size() == 1u && packaged_usages[0].is_executable() &&
            std::strstr(packaged_usages[0].fragment_source(), "termin_standard_gbuffer_fs") != nullptr;
        if (!read_ok || !center_ok || !corner_ok || cache.size() == 0u || !usage_ok) {
            std::fprintf(stderr,
                         "StandardGBufferPass pixel smoke failed: read=%s center=%s corner=%s cache=%zu usage=%s\n",
                         read_ok ? "true" : "false",
                         center_ok ? "true" : "false",
                         corner_ok ? "true" : "false",
                         cache.size(),
                         usage_ok ? "true" : "false");
            return 1;
        }
        return 0;
    }

} // namespace

int main() {
    std::printf("--- StandardGBufferPass Vulkan pixel smoke ---\n");
    if (!tgfx::backend_is_compiled(tgfx::BackendType::Vulkan)) {
        std::printf("Vulkan backend not compiled, skipping test\n");
        return 0;
    }

    tc_mesh_init();
    tc_shader_init();
    tc_material_init();
    tc_scene_pool_init();
    tc_surface_contract_registry_clear();
    if (!tc_surface_contract_registry_register_builtins()) {
        std::fprintf(stderr, "Failed to register standard surface contract\n");
        return 1;
    }

    const int result = run_smoke();

    tc_surface_contract_registry_clear();
    tc_scene_pool_shutdown();
    tc_material_shutdown();
    tc_shader_shutdown();
    tc_mesh_shutdown();
    return result;
}
