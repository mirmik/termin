#include <chrono>
#include <cmath>
#include <cstdio>
#include <exception>
#include <filesystem>
#include <memory>
#include <system_error>
#include <vector>

#include <tgfx2/device_factory.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

#include "tcplot/gpu_host.hpp"
#include "tcplot/retained_chart2d.h"
#include "tcplot/retained_scene_renderer2d.h"

namespace {

    struct TemporaryShaderRoot {
        std::filesystem::path path;
        ~TemporaryShaderRoot() {
            std::error_code error;
            std::filesystem::remove_all(path, error);
        }
    };

} // namespace

int main() {
    try {
        if (!tgfx::backend_is_compiled(tgfx::BackendType::Vulkan)) {
            std::printf("tcplot series performance skipped: Vulkan unavailable\n");
            return 77;
        }
        const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
        TemporaryShaderRoot shader_root{std::filesystem::temp_directory_path() /
                                        ("tcplot-series-performance-" + std::to_string(unique))};
        std::filesystem::create_directories(shader_root.path / "cache");
        termin::tgfx2_set_shader_artifact_root(shader_root.path.string().c_str());
        termin::tgfx2_set_shader_cache_root((shader_root.path / "cache").string().c_str());
        termin::tgfx2_set_shader_dev_compile_enabled(true);

        tcplot::GpuHost host(TCPLOT_TEST_FONT, tgfx::BackendType::Vulkan);
        constexpr int width = 1280;
        constexpr int height = 720;
        std::unique_ptr<tc_retained_chart2d, decltype(&tc_retained_chart2d_destroy)> chart(
            tc_retained_chart2d_create(
                &host, {0, 0, width, height}, {0.0, 100.0, -1.2, 1.2}, "ui://default-font", 1, nullptr),
            tc_retained_chart2d_destroy);
        if (!chart)
            return 1;
        std::unique_ptr<tc_retained_scene_renderer2d, decltype(&tc_retained_scene_renderer2d_destroy)> renderer(
            tc_retained_scene_renderer2d_create(&host, tc_retained_chart2d_scene(chart.get())),
            tc_retained_scene_renderer2d_destroy);
        if (!renderer || !tc_retained_scene_renderer2d_set_msaa_samples(renderer.get(), 1))
            return 1;

        constexpr std::size_t count = 100000;
        std::vector<double> x(count);
        std::vector<double> line_y(count);
        std::vector<double> scatter_y(count);
        for (std::size_t index = 0; index < count; ++index) {
            x[index] = static_cast<double>(index) * 100.0 / static_cast<double>(count - 1);
            line_y[index] = std::sin(x[index] * 0.2);
            scatter_y[index] = std::cos(x[index] * 0.2);
        }
        const tc_plot_line_style_state2d line_style{
            {0.1f, 0.6f, 0.9f, 1.0f}, 1.5f, TC_PLOT_LINE_STYLE_SOLID_2D, 8, 5, TC_PLOT_COLORMAP_SOLID_2D, false, 0, 1};
        const tc_plot_scatter_style_state2d scatter_style{{0.9f, 0.3f, 0.2f, 0.7f}, 3.0f};
        const auto line = tc_retained_chart2d_add_named_line(
            chart.get(), "100k line", true, x.data(), line_y.data(), nullptr, count, line_style);
        const auto scatter = tc_retained_chart2d_add_named_scatter(
            chart.get(), "100k scatter", true, x.data(), scatter_y.data(), count, scatter_style);
        if (!tc_retained_chart2d_series_is_valid(chart.get(), line) ||
            !tc_retained_chart2d_series_is_valid(chart.get(), scatter)) {
            std::fprintf(stderr, "failed to create retained series for performance test\n");
            return 1;
        }

        if (!tc_retained_scene_renderer2d_render(renderer.get(), width, height))
            return 1;
        host.device().wait_idle();

        const auto start = std::chrono::steady_clock::now();
        constexpr int measured_frames = 5;
        for (int frame = 0; frame < measured_frames; ++frame) {
            if (!tc_retained_scene_renderer2d_render(renderer.get(), width, height))
                return 1;
        }
        host.device().wait_idle();
        const auto elapsed = std::chrono::steady_clock::now() - start;
        const double milliseconds = std::chrono::duration<double, std::milli>(elapsed).count();
        const double per_frame = milliseconds / measured_frames;
        std::printf("retained-series steady render: line=100000 scatter=100000 "
                    "1280x720, %.3f ms/frame\n",
                    per_frame);

        // This gate includes scene publication, draw submission and GPU wait.
        // The pre-migration scatter path emitted 100k Canvas circles per
        // frame; the retained path must remain comfortably interactive.
        return per_frame <= 250.0 ? 0 : 1;
    } catch (const std::exception& error) {
        std::fprintf(stderr, "tcplot series performance failed: %s\n", error.what());
        return 1;
    }
}
