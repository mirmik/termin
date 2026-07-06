#include <termin/render/debug_triangle_pass.hpp>
#include <termin/render/execute_context.hpp>

#include <tgfx2/descriptors.hpp>
#include <tgfx2/device_factory.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/pipeline_cache.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

extern "C" {
#include <tgfx/resources/tc_shader_registry.h>
}

#include <cstdio>
#include <cstdlib>
#include <chrono>
#include <exception>
#include <filesystem>
#include <memory>
#include <string>
#include <system_error>
#include <vector>

namespace {

constexpr uint32_t kWidth = 64;
constexpr uint32_t kHeight = 64;

bool matches_clear_color(const float pixel[4]) {
    return pixel[0] > 0.05f && pixel[0] < 0.11f &&
           pixel[1] > 0.06f && pixel[1] < 0.12f &&
           pixel[2] > 0.08f && pixel[2] < 0.14f &&
           pixel[3] > 0.95f;
}

bool differs_from_clear_color(const float pixel[4]) {
    return pixel[0] > 0.13f ||
           pixel[1] > 0.15f ||
           pixel[2] > 0.18f;
}

void print_pixel(const char* label, const float pixel[4]) {
    std::printf(
        "%s: (%.3f %.3f %.3f %.3f)\n",
        label,
        pixel[0],
        pixel[1],
        pixel[2],
        pixel[3]);
}

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
        std::filesystem::remove_all(path);
    }
};

int run_smoke(const char* argv0) {
    const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
    const ScopedTempDirectory artifact_root{
        std::filesystem::temp_directory_path() /
        ("termin-render-passes-debug-triangle-pixel-smoke-" + std::to_string(unique))
    };
    std::filesystem::remove_all(artifact_root.path);
    configure_shader_artifacts(argv0, artifact_root.path);

    std::unique_ptr<tgfx::IRenderDevice> device;
    try {
        device = tgfx::create_device(tgfx::BackendType::Vulkan);
    } catch (const std::exception& e) {
        std::fprintf(stderr, "Failed to create Vulkan device: %s\n", e.what());
        return 1;
    }

    tgfx::TextureDesc target_desc;
    target_desc.width = kWidth;
    target_desc.height = kHeight;
    target_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
    target_desc.usage =
        tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::CopySrc;
    tgfx::TextureHandle target = device->create_texture(target_desc);
    if (!target) {
        std::fprintf(stderr, "Failed to create output texture\n");
        return 1;
    }

    tgfx::PipelineCache cache(*device);
    tgfx::RenderContext2 render_ctx(*device, cache);
    termin::DebugTrianglePass pass("debug_output", "DebugTrianglePixelSmoke");

    termin::ExecuteContext exec_ctx;
    exec_ctx.ctx2 = &render_ctx;
    exec_ctx.tex2_writes.emplace("debug_output", target);
    exec_ctx.render_rect = {0, 0, static_cast<int>(kWidth), static_cast<int>(kHeight)};

    render_ctx.begin_frame();
    pass.execute(exec_ctx);
    render_ctx.end_frame();
    device->wait_idle();

    float center[4] = {};
    float corner[4] = {};
    const bool read_ok =
        device->read_pixel_rgba8(
            target,
            static_cast<int>(kWidth / 2),
            static_cast<int>(kHeight / 2),
            center) &&
        device->read_pixel_rgba8(target, 0, 0, corner);

    print_pixel("center", center);
    print_pixel("top-left", corner);

    const size_t pipeline_cache_size = cache.size();
    const bool pass_ok =
        read_ok &&
        differs_from_clear_color(center) &&
        matches_clear_color(corner) &&
        pipeline_cache_size == 1;

    pass.destroy();
    device->destroy(target);

    if (!pass_ok) {
        std::fprintf(
            stderr,
            "DebugTrianglePass pixel smoke failed: read_ok=%s cache_size=%zu\n",
            read_ok ? "true" : "false",
            pipeline_cache_size);
        return 1;
    }

    return 0;
}

} // namespace

int main(int argc, char** argv) {
    std::printf("--- termin-render-passes DebugTrianglePass pixel smoke ---\n");

    if (!tgfx::backend_is_compiled(tgfx::BackendType::Vulkan)) {
        std::printf("Vulkan backend not compiled, skipping test\n");
        return 0;
    }

    tc_shader_init();
    const int result = run_smoke(argc > 0 ? argv[0] : nullptr);
    tc_shader_shutdown();
    return result;
}
