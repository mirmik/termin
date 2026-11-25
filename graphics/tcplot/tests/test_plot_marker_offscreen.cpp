#include <chrono>
#include <cstdio>
#include <exception>
#include <filesystem>
#include <memory>
#include <stdexcept>
#include <system_error>
#include <utility>
#include <vector>

#include <tgfx2/device_factory.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

#include "tcplot/gpu_host.hpp"
#include "tcplot/plot_annotations2d.hpp"
#include "tcplot/plot_projection2d.hpp"
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

    void require(bool condition, const char* message) {
        if (!condition)
            throw std::runtime_error(message);
    }

    std::vector<float> render(tcplot::GpuHost& host, tc_visual_scene_handle scene, int width, int height) {
        std::unique_ptr<tc_retained_scene_renderer2d, decltype(&tc_retained_scene_renderer2d_destroy)> renderer(
            tc_retained_scene_renderer2d_create(&host, scene), tc_retained_scene_renderer2d_destroy);
        require(renderer && tc_retained_scene_renderer2d_set_msaa_samples(renderer.get(), 1),
                "failed to configure retained scene renderer");
        const tgfx::TextureHandle texture{tc_retained_scene_renderer2d_render(renderer.get(), width, height)};
        require(texture.id != 0, "render produced no texture");
        host.device().wait_idle();
        std::vector<float> pixels(static_cast<std::size_t>(width) * height * 4);
        require(host.device().read_texture_rgba_float(texture, pixels.data()), "render readback failed");
        return pixels;
    }

    template <typename Predicate> std::size_t count_pixels(const std::vector<float>& pixels, Predicate matches) {
        std::size_t count = 0;
        for (std::size_t i = 0; i < pixels.size(); i += 4) {
            if (matches(pixels[i], pixels[i + 1], pixels[i + 2], pixels[i + 3]))
                ++count;
        }
        return count;
    }

} // namespace

int main() {
    try {
        if (!tgfx::backend_is_compiled(tgfx::BackendType::Vulkan)) {
            std::printf("tcplot marker offscreen smoke skipped: Vulkan unavailable\n");
            return 77;
        }
        const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
        TemporaryShaderRoot shader_root{
            std::filesystem::temp_directory_path() / ("tcplot-marker-smoke-" + std::to_string(unique)),
        };
        std::filesystem::create_directories(shader_root.path / "cache");
        termin::tgfx2_set_shader_artifact_root(shader_root.path.string().c_str());
        termin::tgfx2_set_shader_cache_root((shader_root.path / "cache").string().c_str());
        termin::tgfx2_set_shader_dev_compile_enabled(true);

        tcplot::GpuHost host(TCPLOT_TEST_FONT, tgfx::BackendType::Vulkan);
        constexpr int width = 320;
        constexpr int height = 240;
        std::unique_ptr<tc_retained_chart2d, decltype(&tc_retained_chart2d_destroy)> chart(
            tc_retained_chart2d_create(&host, {0, 0, width, height}, {0, 10, 0, 10}, "ui://default-font", 1, nullptr),
            tc_retained_chart2d_destroy);
        require(chart && tc_retained_chart2d_set_title(chart.get(), "Retained marker"), "failed to create chart");
        const double series_x[] = {1.0, 3.0, 5.0, 7.0, 9.0};
        const double solid_y[] = {2.0, 3.0, 2.0, 3.0, 2.0};
        const double dashed_y[] = {7.0, 8.0, 7.0, 8.0, 7.0};
        const double colormap_y[] = {8.8, 9.2, 8.8, 9.2, 8.8};
        const double scatter_y[] = {4.0, 6.0, 4.0, 6.0, 4.0};
        const double scalar[] = {0.0, 0.25, 0.5, 0.75, 1.0};
        const tc_plot_line_style_state2d solid{
            {0.1f, 0.3f, 0.9f, 1.0f}, 2, TC_PLOT_LINE_STYLE_SOLID_2D, 8, 5, TC_PLOT_COLORMAP_SOLID_2D, false, 0, 1};
        const tc_plot_line_style_state2d dashed{
            {0.1f, 0.9f, 0.1f, 1.0f}, 3, TC_PLOT_LINE_STYLE_DASH_2D, 10, 5, TC_PLOT_COLORMAP_SOLID_2D, false, 0, 1};
        const tc_plot_line_style_state2d colormap{
            {1, 1, 1, 1}, 3, TC_PLOT_LINE_STYLE_SOLID_2D, 8, 5, TC_PLOT_COLORMAP_VIRIDIS_2D, true, 0, 1};
        const auto solid_line =
            tc_retained_chart2d_add_named_line(chart.get(), "solid", true, series_x, solid_y, nullptr, 5, solid);
        const auto dashed_line =
            tc_retained_chart2d_add_named_line(chart.get(), "dashed", true, series_x, dashed_y, nullptr, 5, dashed);
        const auto colored_line = tc_retained_chart2d_add_named_line(
            chart.get(), "colormap", true, series_x, colormap_y, scalar, 5, colormap);
        const auto scatter = tc_retained_chart2d_add_named_scatter(
            chart.get(), "scatter", true, series_x, scatter_y, 5, {{0.9f, 0.1f, 0.9f, 1.0f}, 10});
        for (const auto series : {solid_line, dashed_line, colored_line, scatter}) {
            require(tc_retained_chart2d_series_is_valid(chart.get(), series), "failed to create retained series");
        }

        const tcplot::PlotProjection2D projection(tc_retained_chart2d_projection(chart.get()));
        const auto projection_state = projection.snapshot();
        require(projection_state.has_value(), "failed to snapshot retained chart projection");
        tcplot::PlotAnnotationLayer2D annotations;
        tcplot::PlotDataMarker2D marker;
        marker.data_position = {5.0, 5.0};
        marker.text = "sample 5.0";
        require(annotations.create_data_marker(std::move(marker)).has_value(), "failed to create data marker");
        annotations.project(projection_state->frame, {});
        const auto& anchors =
            annotations.visual_scene(tcplot::PlotAnnotationPhase2D::Overlay, tcplot::PlotAnnotationClip2D::PlotArea);
        const auto& callouts =
            annotations.visual_scene(tcplot::PlotAnnotationPhase2D::Chrome, tcplot::PlotAnnotationClip2D::PlotArea);
        const auto anchor_pixels = render(host, anchors.handle(), width, height);
        const auto callout_pixels = render(host, callouts.handle(), width, height);
        const auto chart_pixels = render(host, tc_retained_chart2d_scene(chart.get()), width, height);

        // Authored sRGB colors reach the linear render target after one decode.
        const auto orange = count_pixels(anchor_pixels, [](float r, float g, float b, float) {
            return r > 0.80f && g > 0.20f && g < 0.35f && b < 0.05f;
        });
        const auto light = count_pixels(
            callout_pixels, [](float r, float g, float b, float) { return r > 0.52f && g > 0.58f && b > 0.72f; });
        const auto blue = count_pixels(
            chart_pixels, [](float r, float g, float b, float) { return b > 0.70f && r < 0.35f && g < 0.65f; });
        const auto green = count_pixels(
            chart_pixels, [](float r, float g, float b, float) { return g > 0.65f && r < 0.35f && b < 0.35f; });
        const auto magenta = count_pixels(
            chart_pixels, [](float r, float g, float b, float) { return r > 0.65f && b > 0.65f && g < 0.35f; });
        const auto opaque = count_pixels(chart_pixels, [](float, float, float, float a) { return a > 0.9f; });
        require(orange >= 20, "marker anchor is missing its orange pixels");
        require(light >= 40, "marker callout is missing its light pixels");
        require(blue >= 20, "solid line is missing its blue pixels");
        require(green >= 20, "dashed line is missing its green pixels");
        require(magenta >= 20, "scatter series is missing its magenta pixels");
        require(opaque > width * height * 9 / 10, "chart is missing its opaque background");
        return 0;
    } catch (const std::exception& error) {
        std::fprintf(stderr, "tcplot marker offscreen smoke failed: %s\n", error.what());
        return 1;
    }
}
