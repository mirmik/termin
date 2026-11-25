#include <cmath>
#include <memory>
#include <stdexcept>
#include <vector>

#include <termin/geom/color.hpp>
#include <tgfx2/i_render_device.hpp>

#include "tcplot/gpu_host.hpp"
#include "tcplot/retained_chart2d.h"
#include "tcplot/retained_scene_renderer2d.h"

namespace {

    void require(bool condition, const char* message) {
        if (!condition)
            throw std::runtime_error(message);
    }

} // namespace

namespace tcplot::tests {

    void test_retained_chart2d_colors_d3d11(tcplot::GpuHost& host) {
        using ChartOwner = std::unique_ptr<tc_retained_chart2d, decltype(&tc_retained_chart2d_destroy)>;
        using RendererOwner =
            std::unique_ptr<tc_retained_scene_renderer2d, decltype(&tc_retained_scene_renderer2d_destroy)>;
        constexpr uint32_t width = 240, height = 180;
        auto theme = tc_retained_chart2d_default_theme();
        theme.background_color = {0.3f, 0.4f, 0.6f, 1};
        theme.plot_background_color = {0.05f, 0.07f, 0.09f, 1};
        const tc_plot_color2d authored{0.7f, 0.2f, 0.5f, 1};
        const double x[] = {0.2, 0.8}, y[] = {0.5, 0.5}, scalar[] = {0.5, 0.5};
        for (int mode = 0; mode < 4; ++mode) {
            ChartOwner chart(
                tc_retained_chart2d_create(&host, {0, 0, width, height}, {0, 1, 0, 1}, "ui://default-font", 1, &theme),
                tc_retained_chart2d_destroy);
            require(chart != nullptr, "failed to create Chart2D color fixture");
            const auto scene = tc_retained_chart2d_scene(chart.get());
            require(tc_visual_scene_item_set_visible(
                        scene, tc_retained_chart2d_part_handle(chart.get(), TC_CHART2D_PART_GRID), false) &&
                        tc_visual_scene_item_set_visible(
                            scene, tc_retained_chart2d_part_handle(chart.get(), TC_CHART2D_PART_CHROME_ROOT), false),
                    "failed to isolate Chart2D series colors");
            tc_chart_series_handle2d series{};
            if (mode == 2) {
                series = tc_retained_chart2d_add_named_scatter(chart.get(), "", false, x, y, 1, {authored, 18});
            } else {
                tc_plot_line_style_state2d style{authored,
                                                 mode == 0 ? 1.0f : 8.0f,
                                                 mode == 1 ? TC_PLOT_LINE_STYLE_DASH_2D : TC_PLOT_LINE_STYLE_SOLID_2D,
                                                 8,
                                                 4,
                                                 mode == 3 ? TC_PLOT_COLORMAP_GRAYSCALE_2D : TC_PLOT_COLORMAP_SOLID_2D,
                                                 false,
                                                 0,
                                                 1};
                series = tc_retained_chart2d_add_named_line(
                    chart.get(), "", false, x, y, mode == 3 ? scalar : nullptr, 2, style);
            }
            require(tc_retained_chart2d_series_is_valid(chart.get(), series), "failed to add Chart2D color series");
            RendererOwner renderer(tc_retained_scene_renderer2d_create(&host, scene),
                                   tc_retained_scene_renderer2d_destroy);
            require(renderer && tc_retained_scene_renderer2d_set_msaa_samples(renderer.get(), 1),
                    "failed to create Chart2D color renderer");
            const auto texture = tc_retained_scene_renderer2d_render(renderer.get(), width, height);
            require(texture != 0, "failed to render Chart2D color fixture");
            std::vector<float> pixels(static_cast<std::size_t>(width) * height * 4);
            require(host.device().read_texture_rgba_float(tgfx::TextureHandle{texture}, pixels.data()),
                    "failed to read Chart2D color fixture");
            const auto background = termin::srgb_to_linear(termin::SrgbColor{0.3f, 0.4f, 0.6f, 1});
            const size_t corner = (2 * width + 2) * 4;
            require(std::abs(pixels[corner] - background.r) < 1.5f / 255 &&
                        std::abs(pixels[corner + 1] - background.g) < 1.5f / 255 &&
                        std::abs(pixels[corner + 2] - background.b) < 1.5f / 255,
                    "Chart2D authored theme fill must render into a linear target");
            const auto expected =
                termin::srgb_to_linear(mode == 3 ? termin::SrgbColor{0.5f, 0.5f, 0.5f, 1}
                                                 : termin::SrgbColor{authored.r, authored.g, authored.b, authored.a});
            size_t matching_pixels = 0;
            for (size_t pixel = 0; pixel < pixels.size(); pixel += 4) {
                if (std::abs(pixels[pixel] - expected.r) < 1.5f / 255 &&
                    std::abs(pixels[pixel + 1] - expected.g) < 1.5f / 255 &&
                    std::abs(pixels[pixel + 2] - expected.b) < 1.5f / 255)
                    ++matching_pixels;
            }
            require(matching_pixels > 10,
                    "thin/styled line, scatter and colormap must decode authored RGB exactly once");
        }
    }

} // namespace tcplot::tests
