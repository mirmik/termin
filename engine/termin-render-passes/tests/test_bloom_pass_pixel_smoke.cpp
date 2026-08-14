#include <termin/render/bloom_pass.hpp>
#include <termin/render/builtin_passes.hpp>
#include <termin/render/execute_context.hpp>

#include <tgfx/resources/tc_shader_registry.h>
#include <tgfx2/device_factory.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/pipeline_cache.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

#include <algorithm>
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
#include <vector>

namespace {

    constexpr uint32_t kWidth = 128;
    constexpr uint32_t kHeight = 128;

    bool existing_file(const std::filesystem::path& path) {
        std::error_code ec;
        return std::filesystem::is_regular_file(path, ec);
    }

    std::vector<std::filesystem::path> shaderc_candidates(const char* argv0) {
        std::vector<std::filesystem::path> candidates;
        if (const char* configured = std::getenv("TERMIN_SHADERC")) {
            if (configured[0] != '\0')
                candidates.emplace_back(configured);
        }
        if (argv0 && argv0[0] != '\0') {
            std::error_code ec;
            const auto exe_dir = std::filesystem::absolute(argv0, ec).parent_path();
            if (!ec && !exe_dir.empty())
                candidates.push_back(exe_dir / "termin_shaderc");
        }
        if (const char* sdk = std::getenv("TERMIN_SDK")) {
            if (sdk[0] != '\0') {
                candidates.push_back(std::filesystem::path(sdk) / "bin" / "termin_shaderc");
            }
        }
        candidates.push_back(std::filesystem::current_path() / "sdk" / "bin" / "termin_shaderc");
        return candidates;
    }

    void configure_shader_artifacts(const char* argv0, const std::filesystem::path& root) {
        for (const auto& candidate : shaderc_candidates(argv0)) {
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

    std::vector<float> render_bloom(tgfx::IRenderDevice& device,
                                    tgfx::RenderContext2& render_ctx,
                                    tgfx::TextureHandle source,
                                    int mip_levels) {
        tgfx::TextureDesc output_desc;
        output_desc.width = kWidth;
        output_desc.height = kHeight;
        output_desc.format = tgfx::PixelFormat::RGBA16F;
        output_desc.usage = tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::CopySrc;
        const tgfx::TextureHandle output = device.create_texture(output_desc);

        termin::BloomPass pass("source", "result", 0.0f, 0.0f, 1.0f, mip_levels, 0.7f);
        termin::ExecuteContext exec_ctx;
        exec_ctx.ctx2 = &render_ctx;
        exec_ctx.tex2_reads.emplace("source", source);
        exec_ctx.tex2_writes.emplace("result", output);
        exec_ctx.render_rect = {0, 0, static_cast<int>(kWidth), static_cast<int>(kHeight)};

        render_ctx.begin_frame();
        pass.execute(exec_ctx);
        render_ctx.end_frame();
        device.wait_idle();

        std::vector<float> pixels(kWidth * kHeight * 4);
        if (!device.read_texture_rgba_float(output, pixels.data())) {
            pixels.clear();
        }

        pass.destroy();
        device.destroy(output);
        return pixels;
    }

    float red_at(const std::vector<float>& pixels, int x, int y) {
        return pixels[(static_cast<size_t>(y) * kWidth + static_cast<size_t>(x)) * 4];
    }

    bool mip_count_preserves_energy(tgfx::IRenderDevice& device,
                                    tgfx::RenderContext2& render_ctx,
                                    tgfx::TextureHandle source) {
        std::vector<float> constant(kWidth * kHeight * 4, 1.0f);
        for (size_t i = 0; i < constant.size(); i += 4) {
            constant[i + 0] = 2.0f;
            constant[i + 1] = 2.0f;
            constant[i + 2] = 2.0f;
        }
        device.upload_texture(source,
                              std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(constant.data()),
                                                       constant.size() * sizeof(float)));

        const auto three_mips = render_bloom(device, render_ctx, source, 3);
        const auto six_mips = render_bloom(device, render_ctx, source, 6);
        if (three_mips.empty() || six_mips.empty())
            return false;

        const float three = red_at(three_mips, kWidth / 2, kHeight / 2);
        const float six = red_at(six_mips, kWidth / 2, kHeight / 2);
        std::printf("constant HDR center: 3 mips=%.4f, 6 mips=%.4f\n", three, six);
        return std::abs(three - six) < 0.08f && three > 3.8f && three < 4.2f;
    }

    bool impulse_has_smooth_falloff(tgfx::IRenderDevice& device,
                                    tgfx::RenderContext2& render_ctx,
                                    tgfx::TextureHandle source) {
        float worst_angular_cv = 0.0f;
        for (int phase_y = 0; phase_y < 2; phase_y++) {
            for (int phase_x = 0; phase_x < 2; phase_x++) {
                std::vector<float> impulse(kWidth * kHeight * 4, 0.0f);
                for (size_t i = 3; i < impulse.size(); i += 4)
                    impulse[i] = 1.0f;
                const int center_x = static_cast<int>(kWidth / 2) + phase_x;
                const int center_y = static_cast<int>(kHeight / 2) + phase_y;
                const size_t center = (static_cast<size_t>(center_y) * kWidth + center_x) * 4;
                impulse[center + 0] = 320.0f;
                impulse[center + 1] = 320.0f;
                impulse[center + 2] = 320.0f;
                device.upload_texture(source,
                                      std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(impulse.data()),
                                                               impulse.size() * sizeof(float)));

                const auto pixels = render_bloom(device, render_ctx, source, 6);
                if (pixels.empty())
                    return false;

                // Check every 2x2 sampling phase. A moving point source must form
                // one continuous halo instead of exposing a different mip-grid
                // lobe when it crosses a half-resolution texel boundary.
                float previous_mean = 1.0e30f;
                for (int radius = 5; radius <= 36; radius++) {
                    float sum = 0.0f;
                    float sum_squared = 0.0f;
                    int samples = 0;
                    for (int y = center_y - radius; y <= center_y + radius; y++) {
                        for (int x = center_x - radius; x <= center_x + radius; x++) {
                            const int dx = x - center_x;
                            const int dy = y - center_y;
                            const float distance = std::sqrt(static_cast<float>(dx * dx + dy * dy));
                            if (distance >= radius - 0.5f && distance < radius + 0.5f) {
                                const float value = red_at(pixels, x, y);
                                sum += value;
                                sum_squared += value * value;
                                samples++;
                            }
                        }
                    }
                    const float mean = samples > 0 ? sum / static_cast<float>(samples) : 0.0f;
                    if (mean > 0.00005f && samples > 1) {
                        const float variance = std::max(0.0f, sum_squared / static_cast<float>(samples) - mean * mean);
                        worst_angular_cv = std::max(worst_angular_cv, std::sqrt(variance) / mean);
                    }
                    if (mean > previous_mean * 1.12f + 0.002f) {
                        std::fprintf(stderr,
                                     "Bloom impulse phase (%d,%d) ring brightened at "
                                     "radius %d: %.6f -> %.6f\n",
                                     phase_x,
                                     phase_y,
                                     radius,
                                     previous_mean,
                                     mean);
                        return false;
                    }
                    previous_mean = mean;
                }
            }
        }
        std::printf("impulse worst angular coefficient of variation: %.4f\n", worst_angular_cv);
        return worst_angular_cv < 0.55f;
    }

    int run_smoke(const char* argv0) {
        const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
        const ScopedTempDirectory artifact_root{std::filesystem::temp_directory_path() /
                                                ("termin-render-passes-bloom-pixel-smoke-" + std::to_string(unique))};
        configure_shader_artifacts(argv0, artifact_root.path);

        std::unique_ptr<tgfx::IRenderDevice> device;
        try {
            device = tgfx::create_device(tgfx::BackendType::Vulkan);
        } catch (const std::exception& e) {
            std::fprintf(stderr, "Failed to create Vulkan device: %s\n", e.what());
            return 1;
        }

        tgfx::TextureDesc source_desc;
        source_desc.width = kWidth;
        source_desc.height = kHeight;
        source_desc.format = tgfx::PixelFormat::RGBA32F;
        source_desc.usage = tgfx::TextureUsage::Sampled | tgfx::TextureUsage::CopyDst;
        const tgfx::TextureHandle source = device->create_texture(source_desc);
        if (!source) {
            std::fprintf(stderr, "Failed to create bloom source texture\n");
            return 1;
        }

        tgfx::PipelineCache cache(*device);
        tgfx::RenderContext2 render_ctx(*device, cache);
        const bool energy_ok = mip_count_preserves_energy(*device, render_ctx, source);
        const bool impulse_ok = impulse_has_smooth_falloff(*device, render_ctx, source);
        device->destroy(source);

        if (!energy_ok || !impulse_ok) {
            std::fprintf(stderr,
                         "Bloom pixel smoke failed: energy=%s impulse=%s\n",
                         energy_ok ? "ok" : "failed",
                         impulse_ok ? "ok" : "failed");
            return 1;
        }
        return 0;
    }

} // namespace

int main(int argc, char** argv) {
    std::printf("--- termin-render-passes Bloom pixel smoke ---\n");
    if (!tgfx::backend_is_compiled(tgfx::BackendType::Vulkan)) {
        std::printf("Vulkan backend not compiled, skipping test\n");
        return 0;
    }

    tc_shader_init();
    termin::register_builtin_render_pass_types();
    termin::BloomPass::register_type();
    const int result = run_smoke(argc > 0 ? argv[0] : nullptr);
    tc_shader_shutdown();
    return result;
}
