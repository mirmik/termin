#include <termin/render/execute_context.hpp>
#include <termin/render/id_pass.hpp>
#include <termin/render/line_renderer.hpp>
#include <termin/tc_scene.hpp>

#include <tgfx/resources/tc_material_registry.h>
#include <tgfx/resources/tc_shader_registry.h>
#include <tgfx2/device_factory.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/pipeline_cache.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

extern "C" {
#include <core/tc_scene_pool.h>
#include <tc_picking.h>
}

#include <chrono>
#include <cmath>
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

bool matches_clear_color(const float pixel[4])
{
    return pixel[0] >= 0.00f && pixel[0] < 0.04f &&
           pixel[1] >= 0.00f && pixel[1] < 0.04f &&
           pixel[2] >= 0.00f && pixel[2] < 0.04f &&
           pixel[3] >= 0.00f && pixel[3] < 0.04f;
}

bool matches_pick_color(uint32_t pick_id, const float pixel[4])
{
    int r = 0;
    int g = 0;
    int b = 0;
    tc_picking_id_to_rgb(pick_id, &r, &g, &b);
    const float expected[3] = {
        static_cast<float>(r) / 255.0f,
        static_cast<float>(g) / 255.0f,
        static_cast<float>(b) / 255.0f,
    };
    constexpr float kTolerance = 2.0f / 255.0f;
    return std::abs(pixel[0] - expected[0]) <= kTolerance &&
           std::abs(pixel[1] - expected[1]) <= kTolerance &&
           std::abs(pixel[2] - expected[2]) <= kTolerance &&
           pixel[3] >= 0.95f;
}

void print_pixel(const char* label, const float pixel[4])
{
    std::printf(
        "%s: (%.3f %.3f %.3f %.3f)\n",
        label,
        pixel[0],
        pixel[1],
        pixel[2],
        pixel[3]);
}

bool existing_file(const std::filesystem::path& path)
{
    std::error_code ec;
    return std::filesystem::is_regular_file(path, ec);
}

std::vector<std::filesystem::path> shaderc_candidates(const char* argv0)
{
    std::vector<std::filesystem::path> candidates;

    if (const char* configured = std::getenv("TERMIN_SHADERC")) {
        if (configured[0] != '\0') {
            candidates.emplace_back(configured);
        }
    }

    if (argv0 && argv0[0] != '\0') {
        std::error_code ec;
        const std::filesystem::path exe_dir =
            std::filesystem::absolute(argv0, ec).parent_path();
        if (!ec && !exe_dir.empty()) {
            candidates.push_back(exe_dir / "termin_shaderc");
#ifdef _WIN32
            candidates.push_back(exe_dir / "termin_shaderc.exe");
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

void configure_shader_artifacts(const char* argv0, const std::filesystem::path& root)
{
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

    ~ScopedTempDirectory()
    {
        std::filesystem::remove_all(path);
    }
};

termin::TcMaterial create_line_material()
{
    termin::TcMaterial material = termin::TcMaterial::create(
        "IdPassLinePixelSmokeMaterial",
        "id-pass-line-pixel-smoke-mat");
    if (!material.is_valid()) {
        return {};
    }

    tc_material_phase* phase = material.add_phase(
        tc_shader_handle_invalid(),
        "opaque",
        0);
    if (!phase) {
        return {};
    }
    phase->state = tc_render_state_opaque();
    phase->state.cull = 0;
    phase->state.depth_test = 0;
    phase->state.depth_write = 0;
    return material;
}

termin::TcSceneRef create_scene(const termin::TcMaterial& material, uint32_t& out_pick_id)
{
    termin::LineRenderer::register_type();

    termin::TcSceneRef scene = termin::TcSceneRef::create("id-pass-line-pixel-smoke");
    termin::Entity entity = scene.create_entity("PickableLine");
    if (!entity.valid()) {
        return {};
    }
    entity.set_pickable(true);
    out_pick_id = entity.pick_id();

    auto* renderer = new termin::LineRenderer();
    renderer->set_material(material);
    renderer->set_render_mode(termin::LineRenderMode::ScreenSpace);
    renderer->set_width(8.0f);
    renderer->set_points({tc_vec3{-0.75f, 0.0f, 0.0f}, tc_vec3{0.75f, 0.0f, 0.0f}});
    entity.add_component(renderer);

    return scene;
}

int run_smoke(const char* argv0)
{
    const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
    const ScopedTempDirectory artifact_root{
        std::filesystem::temp_directory_path() /
        ("termin-render-passes-id-pass-line-pixel-smoke-" + std::to_string(unique))
    };
    std::filesystem::remove_all(artifact_root.path);
    configure_shader_artifacts(argv0, artifact_root.path);

    termin::TcMaterial material = create_line_material();
    if (!material.is_valid()) {
        std::fprintf(stderr, "Failed to create IdPass line smoke material\n");
        return 1;
    }

    uint32_t pick_id = 0;
    termin::TcSceneRef scene = create_scene(material, pick_id);
    if (!scene.valid()) {
        std::fprintf(stderr, "Failed to create IdPass line smoke scene\n");
        return 1;
    }
    if (pick_id == 0) {
        std::fprintf(stderr, "Failed to create pickable line entity\n");
        return 1;
    }

    std::unique_ptr<tgfx::IRenderDevice> device;
    try {
        device = tgfx::create_device(tgfx::BackendType::Vulkan);
    } catch (const std::exception& e) {
        std::fprintf(stderr, "Failed to create Vulkan device: %s\n", e.what());
        return 1;
    }

    tgfx::TextureDesc color_desc;
    color_desc.width = kWidth;
    color_desc.height = kHeight;
    color_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
    color_desc.usage =
        tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::CopySrc;
    tgfx::TextureHandle color = device->create_texture(color_desc);
    if (!color) {
        std::fprintf(stderr, "Failed to create id color texture\n");
        return 1;
    }

    tgfx::TextureDesc depth_desc;
    depth_desc.width = kWidth;
    depth_desc.height = kHeight;
    depth_desc.format = tgfx::PixelFormat::D32F;
    depth_desc.usage = tgfx::TextureUsage::DepthStencilAttachment;
    tgfx::TextureHandle depth = device->create_texture(depth_desc);
    if (!depth) {
        std::fprintf(stderr, "Failed to create id depth texture\n");
        device->destroy(color);
        return 1;
    }

    tgfx::PipelineCache cache(*device);
    tgfx::RenderContext2 render_ctx(*device, cache);
    termin::IdPass pass("empty", "id", "IdPassLinePixelSmoke");

    termin::ExecuteContext exec_ctx;
    exec_ctx.ctx2 = &render_ctx;
    exec_ctx.tex2_writes.emplace("id", color);
    exec_ctx.tex2_depth_writes.emplace("id", depth);
    exec_ctx.render_rect = {0, 0, static_cast<int>(kWidth), static_cast<int>(kHeight)};
    exec_ctx.scene = scene;

    render_ctx.begin_frame();
    pass.execute_with_data_tgfx2(
        exec_ctx,
        exec_ctx.render_rect,
        scene.handle(),
        termin::Mat44f::identity(),
        termin::Mat44f::identity(),
        termin::Vec3{0.0, -1.0, 0.0},
        UINT64_MAX);
    render_ctx.end_frame();
    device->wait_idle();

    float center[4] = {};
    float corner[4] = {};
    const bool read_ok =
        device->read_pixel_rgba8(
            color,
            static_cast<int>(kWidth / 2),
            static_cast<int>(kHeight / 2),
            center) &&
        device->read_pixel_rgba8(color, 0, 0, corner);

    print_pixel("center", center);
    print_pixel("top-left", corner);

    const bool entity_seen =
        pass.entity_names.size() == 1 &&
        pass.entity_names[0] == "PickableLine";
    const bool pass_ok =
        read_ok &&
        matches_pick_color(pick_id, center) &&
        matches_clear_color(corner) &&
        cache.size() >= 1 &&
        entity_seen;

    pass.destroy();
    device->destroy(depth);
    device->destroy(color);

    if (!pass_ok) {
        std::fprintf(
            stderr,
            "IdPass line pixel smoke failed: read_ok=%s cache_size=%zu entity_seen=%s pick_id=%u\n",
            read_ok ? "true" : "false",
            cache.size(),
            entity_seen ? "true" : "false",
            pick_id);
        return 1;
    }

    return 0;
}

} // namespace

int main(int argc, char** argv)
{
    std::printf("--- termin-render-passes IdPass line pixel smoke ---\n");

    if (!tgfx::backend_is_compiled(tgfx::BackendType::Vulkan)) {
        std::printf("Vulkan backend not compiled, skipping test\n");
        return 0;
    }

    tc_shader_init();
    tc_material_init();
    tc_scene_pool_init();

    const int result = run_smoke(argc > 0 ? argv[0] : nullptr);

    tc_scene_pool_shutdown();
    tc_material_shutdown();
    tc_shader_shutdown();
    return result;
}
