#include <termin/render/builtin_passes.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/render/tonemap_pass.hpp>

#include <tgfx/resources/tc_shader_registry.h>
#include <tgfx2/device_factory.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/pipeline_cache.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <filesystem>
#include <memory>
#include <span>
#include <string>
#include <system_error>

namespace {

    bool existing_file(const std::filesystem::path& path) {
        std::error_code ec;
        return std::filesystem::is_regular_file(path, ec);
    }

    void configure_shader_artifacts(const char* argv0, const std::filesystem::path& root) {
        std::array<std::filesystem::path, 3> candidates = {
            argv0 ? std::filesystem::absolute(argv0).parent_path() / "termin_shaderc" : std::filesystem::path{},
            std::filesystem::current_path() / "sdk" / "bin" / "termin_shaderc",
            std::getenv("TERMIN_SDK")
                ? std::filesystem::path(std::getenv("TERMIN_SDK")) / "bin" / "termin_shaderc"
                : std::filesystem::path{},
        };
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

    float srgb_oetf(float linear) {
        linear = std::max(linear, 0.0f);
        if (linear <= 0.0031308f)
            return 12.92f * linear;
        return 1.055f * std::pow(linear, 1.0f / 2.4f) - 0.055f;
    }

    float aces(float value) {
        return std::clamp((value * (2.51f * value + 0.03f)) /
                              (value * (2.43f * value + 0.59f) + 0.14f),
                          0.0f,
                          1.0f);
    }

    tgfx::TextureHandle make_texture(tgfx::IRenderDevice& device,
                                     tgfx::PixelFormat format,
                                     tgfx::TextureUsage usage) {
        tgfx::TextureDesc desc;
        desc.width = 4;
        desc.height = 1;
        desc.format = format;
        desc.usage = usage;
        return device.create_texture(desc);
    }

    int run_smoke(const char* argv0) {
        const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
        const std::filesystem::path artifact_root = std::filesystem::temp_directory_path() /
                                                    ("termin-output-transform-smoke-" + std::to_string(unique));
        configure_shader_artifacts(argv0, artifact_root);

        std::unique_ptr<tgfx::IRenderDevice> device;
        try {
            device = tgfx::create_device(tgfx::BackendType::Vulkan);
        } catch (const std::exception& e) {
            std::fprintf(stderr, "Failed to create Vulkan device: %s\n", e.what());
            return 1;
        }

        const tgfx::TextureHandle source = make_texture(
            *device, tgfx::PixelFormat::RGBA32F, tgfx::TextureUsage::Sampled | tgfx::TextureUsage::CopyDst);
        const tgfx::TextureHandle tonemapped = make_texture(*device,
                                                            tgfx::PixelFormat::RGBA16F,
                                                            tgfx::TextureUsage::ColorAttachment |
                                                                tgfx::TextureUsage::Sampled |
                                                                tgfx::TextureUsage::CopySrc);
        const tgfx::TextureHandle output = make_texture(
            *device,
            tgfx::PixelFormat::RGBA8_sRGB,
            tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::CopySrc | tgfx::TextureUsage::CopyDst);
        if (!source || !tonemapped || !output) {
            std::fprintf(stderr, "Failed to create output-transform smoke textures\n");
            return 1;
        }

        // The last sample deliberately exceeds 1.0. If the pipeline clamps to
        // UNORM before tonemapping, it lands near sRGB(ACES(1)) ~= 0.908 rather
        // than the expected sRGB(ACES(4)) ~= 0.988.
        const std::array<float, 16> source_pixels = {
            0.0f, 0.0f, 0.0f, 1.0f,
            0.0031308f, 0.0031308f, 0.0031308f, 1.0f,
            0.18f, 0.18f, 0.18f, 1.0f,
            4.0f, 4.0f, 4.0f, 1.0f,
        };
        device->upload_texture(source,
                               std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(source_pixels.data()),
                                                        sizeof(source_pixels)));

        tgfx::PipelineCache cache(*device);
        tgfx::RenderContext2 render_ctx(*device, cache);
        termin::TonemapPass tonemap("source", "tonemapped", 1.0f, 0);

        termin::ExecuteContext tonemap_ctx;
        tonemap_ctx.ctx2 = &render_ctx;
        tonemap_ctx.tex2_reads.emplace("source", source);
        tonemap_ctx.tex2_writes.emplace("tonemapped", tonemapped);
        tonemap_ctx.render_rect = {0, 0, 4, 1};

        render_ctx.begin_frame();
        tonemap.execute(tonemap_ctx);
        render_ctx.blit(tonemapped, output);
        render_ctx.end_frame();
        device->wait_idle();

        std::array<float, 16> result{};
        const bool read_ok = device->read_texture_rgba_float(output, result.data());
        const std::array<float, 4> expected = {
            srgb_oetf(aces(0.0f)),
            srgb_oetf(aces(0.0031308f)),
            srgb_oetf(aces(0.18f)),
            srgb_oetf(aces(4.0f)),
        };

        bool values_ok = read_ok;
        constexpr float tolerance = 2.5f / 255.0f;
        for (size_t x = 0; x < expected.size() && read_ok; ++x) {
            const float actual = result[x * 4];
            std::printf("linear[%zu] -> actual %.6f, expected %.6f\n", x, actual, expected[x]);
            if (std::abs(actual - expected[x]) > tolerance)
                values_ok = false;
        }

        tonemap.destroy();
        device->destroy(output);
        device->destroy(tonemapped);
        device->destroy(source);
        std::error_code ec;
        std::filesystem::remove_all(artifact_root, ec);

        if (!values_ok) {
            std::fprintf(stderr, "Output-transform numeric contract failed\n");
            return 1;
        }
        return 0;
    }

} // namespace

int main(int argc, char** argv) {
    std::printf("--- termin-render color output binding pixel smoke ---\n");
    if (!tgfx::backend_is_compiled(tgfx::BackendType::Vulkan)) {
        std::printf("Vulkan backend not compiled, skipping test\n");
        return 0;
    }

    tc_shader_init();
    termin::register_builtin_render_pass_types();
    termin::TonemapPass::register_type();
    const int result = run_smoke(argc > 0 ? argv[0] : nullptr);
    tc_shader_shutdown();
    return result;
}
