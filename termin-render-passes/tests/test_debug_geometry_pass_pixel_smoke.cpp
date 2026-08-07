#include <termin/render/debug_geometry_pass.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/render/scene_render_services.hpp>
#include <termin/render/render_camera.hpp>
#include <termin/tc_scene.hpp>

#include <tgfx2/descriptors.hpp>
#include <tgfx2/device_factory.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/pipeline_cache.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

extern "C" {
#include <core/tc_debug_geometry.h>
#include <core/tc_scene_render_mount.h>
#include <termin_scene/internal/tc_scene_extension_registry.h>
#include <tgfx/resources/tc_shader_registry.h>
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
constexpr float kClear[4] = {0.02f, 0.10f, 0.20f, 1.0f};

bool existing_file(const std::filesystem::path& path) {
    std::error_code error;
    return std::filesystem::is_regular_file(path, error);
}

void configure_shader_artifacts(
    const char* argv0,
    const std::filesystem::path& root)
{
    std::vector<std::filesystem::path> candidates;
    if (const char* configured = std::getenv("TERMIN_SHADERC")) {
        if (configured[0] != '\0') candidates.emplace_back(configured);
    }
    if (argv0 && argv0[0] != '\0') {
        std::error_code error;
        const auto executable = std::filesystem::absolute(argv0, error);
        if (!error) candidates.push_back(executable.parent_path() / "termin_shaderc");
    }
    if (const char* sdk = std::getenv("TERMIN_SDK")) {
        if (sdk[0] != '\0') {
            candidates.push_back(std::filesystem::path(sdk) / "bin" / "termin_shaderc");
        }
    }
    candidates.push_back(
        std::filesystem::current_path() / "sdk" / "bin" / "termin_shaderc");
    for (const auto& candidate : candidates) {
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
        std::error_code error;
        std::filesystem::remove_all(path, error);
    }
};

bool matches_clear(const float pixel[4]) {
    return pixel[0] < 0.08f &&
        pixel[1] > 0.05f && pixel[1] < 0.16f &&
        pixel[2] > 0.14f && pixel[2] < 0.27f &&
        pixel[3] > 0.90f;
}

bool matches_debug_line(const float pixel[4]) {
    return pixel[0] > 0.65f && pixel[1] > 0.65f && pixel[2] < 0.25f;
}

bool region_matches(
    tgfx::IRenderDevice& device,
    tgfx::TextureHandle target,
    bool expect_line,
    float reported_pixel[4])
{
    bool all_read = true;
    bool found_line = false;
    bool all_clear = true;
    for (int y = static_cast<int>(kHeight / 2) - 2;
         y <= static_cast<int>(kHeight / 2) + 2;
         ++y) {
        for (int x = static_cast<int>(kWidth / 2) - 2;
             x <= static_cast<int>(kWidth / 2) + 2;
             ++x) {
            float pixel[4] = {};
            all_read = device.read_pixel_rgba8(target, x, y, pixel) && all_read;
            if (x == static_cast<int>(kWidth / 2) &&
                y == static_cast<int>(kHeight / 2)) {
                for (int channel = 0; channel < 4; ++channel) {
                    reported_pixel[channel] = pixel[channel];
                }
            }
            if (matches_debug_line(pixel)) {
                found_line = true;
                for (int channel = 0; channel < 4; ++channel) {
                    reported_pixel[channel] = pixel[channel];
                }
            }
            all_clear = matches_clear(pixel) && all_clear;
        }
    }
    return all_read && (expect_line ? found_line : all_clear);
}

bool collect_line(
    tc_scene_handle scene,
    tc_debug_geometry_type_id type_id,
    bool enabled)
{
    if (!tc_scene_debug_geometry_set_enabled(scene, type_id, enabled)) return false;
    tc_scene_debug_geometry_begin_collection(scene);
    const tc_debug_geometry_drawer drawer{scene, type_id};
    const float start[3] = {-0.8f, 0.0f, 0.0f};
    const float end[3] = {0.8f, 0.0f, 0.0f};
    const float color[4] = {1.0f, 1.0f, 0.0f, 1.0f};
    const bool published =
        tc_debug_geometry_drawer_line(&drawer, start, end, color, false);
    tc_scene_debug_geometry_end_collection(scene);
    return published == enabled;
}

int run_smoke(const char* argv0) {
    const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
    const ScopedTempDirectory artifacts{
        std::filesystem::temp_directory_path() /
        ("termin-debug-geometry-pass-pixel-smoke-" + std::to_string(unique))};
    configure_shader_artifacts(argv0, artifacts.path);

    termin::TcSceneRef scene = termin::TcSceneRef::create("debug-geometry-pass-smoke");
    if (!tc_scene_render_mount_ensure(scene.handle())) return 1;
    int attachment_storage = 0;
    const auto* attachment = reinterpret_cast<const tc_render_attachment_context*>(
        &attachment_storage);
    tc_scene_render_mount_notify_attach(scene.handle(), attachment);
    const tc_debug_geometry_type_id type_id = tc_debug_geometry_type_register(
        "tests.debug-geometry.pixel", "Debug Geometry Pixel", "Tests", true);
    if (type_id == TC_DEBUG_GEOMETRY_TYPE_INVALID ||
        !collect_line(scene.handle(), type_id, true)) {
        return 1;
    }

    std::unique_ptr<tgfx::IRenderDevice> device;
    try {
        device = tgfx::create_device(tgfx::BackendType::Vulkan);
    } catch (const std::exception& error) {
        std::fprintf(stderr, "Failed to create Vulkan device: %s\n", error.what());
        return 1;
    }

    tgfx::TextureDesc target_desc;
    target_desc.width = kWidth;
    target_desc.height = kHeight;
    target_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
    target_desc.usage =
        tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::CopySrc;
    const tgfx::TextureHandle target = device->create_texture(target_desc);
    if (!target) return 1;

    tgfx::PipelineCache cache(*device);
    tgfx::RenderContext2 render_context(*device, cache);
    termin::RenderCamera camera;
    camera.view = termin::Mat44::identity();
    camera.projection = termin::Mat44::orthographic(
        -1.0, 1.0, -1.0, 1.0, -1.0, 1.0);
    termin::ExecuteContext context;
    context.ctx2 = &render_context;
    context.view.primary = camera;
    const termin::SceneRenderServices scene_services(scene);
    termin::RenderExecutionCapabilities capabilities;
    capabilities.add(scene_services);
    context.capabilities = &capabilities;
    context.tex2_writes.emplace("debug", target);
    context.render_rect = {0, 0, static_cast<int>(kWidth), static_cast<int>(kHeight)};
    termin::DebugGeometryPass pass("debug", "debug", "DebugGeometryPixelSmoke");

    render_context.begin_frame();
    render_context.begin_pass(target, {}, kClear, 1.0f, true);
    render_context.end_pass();
    pass.execute(context);
    render_context.end_frame();
    device->wait_idle();
    float enabled_center[4] = {};
    const bool enabled_matches = region_matches(
        *device, target, true, enabled_center);

    if (!collect_line(scene.handle(), type_id, false)) return 1;
    render_context.begin_frame();
    render_context.begin_pass(target, {}, kClear, 1.0f, true);
    render_context.end_pass();
    pass.execute(context);
    render_context.end_frame();
    device->wait_idle();
    float disabled_center[4] = {};
    const bool disabled_matches = region_matches(
        *device, target, false, disabled_center);

    std::printf(
        "enabled=(%.3f %.3f %.3f %.3f) disabled=(%.3f %.3f %.3f %.3f)\n",
        enabled_center[0], enabled_center[1], enabled_center[2], enabled_center[3],
        disabled_center[0], disabled_center[1], disabled_center[2], disabled_center[3]);
    const bool ok = enabled_matches && disabled_matches;

    pass.destroy();
    device->destroy(target);
    tc_scene_render_mount_notify_detach(scene.handle(), attachment);
    scene.destroy();
    if (!tc_debug_geometry_type_unregister(type_id)) return 1;
    if (!ok) {
        std::fprintf(stderr, "DebugGeometryPass enable/disable pixel smoke failed\n");
        return 1;
    }
    return 0;
}

} // namespace

int main(int argc, char** argv) {
    std::printf("--- termin-render-passes DebugGeometryPass pixel smoke ---\n");
    if (!tgfx::backend_is_compiled(tgfx::BackendType::Vulkan)) {
        std::printf("Vulkan backend not compiled, skipping test\n");
        return 0;
    }
    tc_shader_init();
    tc_scene_ext_registry_init();
    tc_scene_render_mount_extension_init();
    const int result = run_smoke(argc > 0 ? argv[0] : nullptr);
    tc_scene_ext_registry_shutdown();
    tc_shader_shutdown();
    return result;
}
