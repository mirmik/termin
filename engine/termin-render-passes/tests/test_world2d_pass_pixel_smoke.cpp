#include <termin/entity/unknown_component.hpp>
#include <termin/render/builtin_passes.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/render/render_scene_item_collector.hpp>
#include <termin/render/scene_render_services.hpp>
#include <termin/render/sprite_asset.hpp>
#include <termin/render/sprite_renderer_2d.hpp>
#include <termin/render/world2d_pass.hpp>
#include <termin/tc_scene.hpp>

#include <tgfx/tgfx_texture_handle.hpp>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/device_factory.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/pipeline_cache.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

extern "C" {
#include <core/tc_scene_pool.h>
#include <tgfx/resources/tc_shader_registry.h>
#include <tgfx/resources/tc_texture_registry.h>
}

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <filesystem>
#include <memory>
#include <string>
#include <system_error>
#include <vector>

namespace {

    constexpr uint32_t kWidth = 64;
    constexpr uint32_t kHeight = 64;

    bool existing_file(const std::filesystem::path& path) {
        std::error_code ec;
        return std::filesystem::is_regular_file(path, ec);
    }

    std::vector<std::filesystem::path> shaderc_candidates(const char* argv0) {
        std::vector<std::filesystem::path> candidates;
        if (const char* configured = std::getenv("TERMIN_SHADERC")) {
            if (configured[0] != '\0') {
                candidates.emplace_back(configured);
            }
        }
        if (argv0 && argv0[0] != '\0') {
            std::error_code ec;
            const std::filesystem::path executable = std::filesystem::absolute(argv0, ec);
            if (!ec) {
                candidates.push_back(executable.parent_path() / "termin_shaderc");
#ifdef _WIN32
                candidates.push_back(executable.parent_path() / "termin_shaderc.exe");
#endif
            }
        }
        if (const char* sdk = std::getenv("TERMIN_SDK")) {
            if (sdk[0] != '\0') {
                candidates.push_back(std::filesystem::path(sdk) / "bin" / "termin_shaderc");
#ifdef _WIN32
                candidates.push_back(std::filesystem::path(sdk) / "bin" / "termin_shaderc.exe");
#endif
            }
        }
        candidates.push_back(std::filesystem::current_path() / "sdk" / "bin" / "termin_shaderc");
#ifdef _WIN32
        candidates.push_back(std::filesystem::current_path() / "sdk" / "bin" / "termin_shaderc.exe");
#endif
        return candidates;
    }

    void configure_shader_artifacts(const char* argv0, const std::filesystem::path& root) {
        for (const std::filesystem::path& candidate : shaderc_candidates(argv0)) {
            if (existing_file(candidate)) {
                termin::tgfx2_set_shader_compiler_path(candidate.string().c_str());
                break;
            }
        }
        termin::tgfx2_set_shader_artifact_root(root.string().c_str());
        termin::tgfx2_set_shader_cache_root((root / ".cache").string().c_str());
        termin::tgfx2_set_shader_dev_compile_enabled(true);
    }

    struct ScopedTempDirectory {
        std::filesystem::path path;

        ~ScopedTempDirectory() {
            std::error_code ec;
            std::filesystem::remove_all(path, ec);
        }
    };

    bool matches_red(const float pixel[4]) {
        return pixel[0] > 0.75f && pixel[1] < 0.10f && pixel[2] < 0.10f && pixel[3] > 0.90f;
    }

    bool matches_clear(const float pixel[4]) {
        return pixel[0] < 0.08f && pixel[1] > 0.08f && pixel[1] < 0.18f && pixel[2] > 0.15f && pixel[2] < 0.28f &&
               pixel[3] > 0.90f;
    }

    int run_smoke(const char* argv0) {
        const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
        const ScopedTempDirectory artifacts{std::filesystem::temp_directory_path() /
                                            ("termin-world2d-pass-pixel-smoke-" + std::to_string(unique))};
        configure_shader_artifacts(argv0, artifacts.path);

        const uint8_t red_pixels[] = {
            255,
            0,
            0,
            255,
            255,
            0,
            0,
            255,
            255,
            0,
            0,
            255,
            255,
            0,
            0,
            255,
        };
        termin::TcTexture texture = termin::TcTexture::from_data(termin::TcTextureCreateInfo{
            {red_pixels, 2, 2, 4},
            {},
            "World2DPassPixelSmokeTexture",
            "",
            "termin-world2d-pass-pixel-smoke-texture",
        });
        if (!texture.is_valid()) {
            std::fprintf(stderr, "Failed to create World2D smoke texture\n");
            return 1;
        }

        termin::TcSpriteAsset sprite =
            termin::TcSpriteAsset::declare("termin-world2d-pass-pixel-smoke-sprite", "World2DPassPixelSmokeSprite");
        if (!sprite.update(texture.uuid(), {0, 0, 2, 2}, 2, 2, 0.5f, 0.5f, 1.0f, termin::SpriteSampling::Nearest)) {
            return 1;
        }

        termin::TcSceneRef scene = termin::TcSceneRef::create("world2d-pass-pixel-smoke");
        termin::Entity entity = scene.create_entity("World2DPassPixelSmokeSprite");
        auto* renderer = new termin::SpriteRenderer2D();
        renderer->set_sprite_uuid(sprite.uuid());
        entity.add_component(renderer);

        termin::RenderItemSnapshot snapshot;
        termin::TcSceneRenderItemSource item_source(scene.handle());
        termin::RenderItemSourceRequest source_request;
        source_request.debug_name = "World2DPassPixelSmoke";
        if (!item_source.publish(snapshot, source_request) || snapshot.item_count() != 1) {
            std::fprintf(stderr, "Failed to collect World2D smoke render item\n");
            scene.destroy();
            return 1;
        }

        std::unique_ptr<tgfx::IRenderDevice> device;
        try {
            device = tgfx::create_device(tgfx::BackendType::Vulkan);
        } catch (const std::exception& error) {
            std::fprintf(stderr, "Failed to create Vulkan device: %s\n", error.what());
            scene.destroy();
            return 1;
        }

        tgfx::TextureDesc color_desc;
        color_desc.width = kWidth;
        color_desc.height = kHeight;
        color_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
        color_desc.usage = tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::CopySrc;
        const tgfx::TextureHandle color = device->create_texture(color_desc);

        tgfx::TextureDesc depth_desc;
        depth_desc.width = kWidth;
        depth_desc.height = kHeight;
        depth_desc.format = tgfx::PixelFormat::D32F;
        depth_desc.usage = tgfx::TextureUsage::DepthStencilAttachment;
        const tgfx::TextureHandle depth = device->create_texture(depth_desc);
        if (!color || !depth) {
            std::fprintf(stderr, "Failed to create World2D smoke attachments\n");
            scene.destroy();
            return 1;
        }

        tgfx::PipelineCache cache(*device);
        tgfx::RenderContext2 render_context(*device, cache);
        termin::RenderCamera camera;
        camera.view = termin::Mat44::look_at({0.0, -2.0, 0.0}, {0.0, 0.0, 0.0}, {0.0, 0.0, 1.0});
        camera.projection = termin::Mat44::orthographic(-2.0, 2.0, -2.0, 2.0, 0.1, 10.0);

        termin::ExecuteContext context;
        context.ctx2 = &render_context;
        context.view.primary = camera;
        const termin::SceneRenderServices scene_services(scene);
        termin::RenderExecutionCapabilities capabilities;
        capabilities.add(scene_services);
        context.capabilities = &capabilities;
        context.render_item_snapshot = &snapshot;
        context.tex2_writes.emplace("world2d", color);
        context.tex2_depth_writes.emplace("world2d", depth);
        context.render_rect = {0, 0, static_cast<int>(kWidth), static_cast<int>(kHeight)};

        const termin::LinearColor clear{0.02f, 0.12f, 0.22f, 1.0f};
        termin::World2DPass pass("opaque", "world2d");
        render_context.begin_frame();
        render_context.begin_pass(color, depth, &clear, 1.0f, true);
        render_context.end_pass();
        pass.execute(context);
        render_context.end_frame();
        device->wait_idle();

        float center[4] = {};
        float corner[4] = {};
        const bool read_ok = device->read_pixel_rgba8(color, kWidth / 2, kHeight / 2, center) &&
                             device->read_pixel_rgba8(color, 0, 0, corner);
        std::printf("center=(%.3f %.3f %.3f %.3f) corner=(%.3f %.3f %.3f %.3f)\n",
                    center[0],
                    center[1],
                    center[2],
                    center[3],
                    corner[0],
                    corner[1],
                    corner[2],
                    corner[3]);

        const bool ok = read_ok && matches_red(center) && matches_clear(corner) && cache.size() == 1;
        pass.destroy();
        device->destroy(depth);
        device->destroy(color);
        scene.destroy();
        texture = {};
        if (!ok) {
            std::fprintf(stderr,
                         "World2DPass pixel smoke failed: read_ok=%s cache_size=%zu\n",
                         read_ok ? "true" : "false",
                         cache.size());
            return 1;
        }
        return 0;
    }

} // namespace

int main(int argc, char** argv) {
    std::printf("--- termin-render-passes World2DPass pixel smoke ---\n");
    if (!tgfx::backend_is_compiled(tgfx::BackendType::Vulkan)) {
        std::printf("Vulkan backend not compiled, skipping test\n");
        return 0;
    }

    tc_texture_init();
    tc_shader_init();
    tc_scene_pool_init();
    termin::register_builtin_scene_component_types();
    termin::SpriteRenderer2D::register_type();
    termin::register_builtin_render_pass_types();
    termin::World2DPass::register_type();

    const int result = run_smoke(argc > 0 ? argv[0] : nullptr);

    tc_scene_pool_shutdown();
    tc_shader_shutdown();
    tc_texture_shutdown();
    return result;
}
