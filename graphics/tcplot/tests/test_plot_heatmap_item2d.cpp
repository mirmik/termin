#include "tcplot/gpu_host.hpp"
#include "tcplot/plot_heatmap_item2d.hpp"
#include "tcplot/retained_scene_renderer2d.h"
#include "tcplot/tc_plot_series_item2d.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <termin_visual_scene/scene_render2d.hpp>
#include <tgfx2/device_factory.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/tc_shader_bridge.hpp>
#include <variant>

namespace {
    class Resolver final : public termin::visual::SceneRenderResourceResolver2D {
        std::optional<tgfx::FontHandle> resolve_font(std::string_view) override {
            return std::nullopt;
        }
        std::optional<tgfx::TextureHandle> resolve_image(std::string_view) override {
            return std::nullopt;
        }
        std::optional<termin::visual::ResolvedCustomBatch2D> resolve_custom_batch(std::string_view,
                                                                                  termin::Bounds2f) override {
            return std::nullopt;
        }
    };

    void require(bool ok, const char* message) {
        if (!ok)
            throw std::runtime_error(message);
    }
    int pixels_test(tgfx::BackendType backend) {
        if (!tgfx::backend_is_compiled(backend))
            return 77;
        termin::tgfx2_set_shader_dev_compile_enabled(true);
        tcplot::GpuHost host(TCPLOT_TEST_FONT, backend);
        const auto scene_handle = tc_visual_scene_create();
        termin::visual::TcVisualScene scene{scene_handle};
        const tcplot::PlotFrame2D frame{{0, 0, 128, 128}, {16, 16, 96, 96}, {0, 2, 0, 2}, {16, 16, 96, 96}, 1};
        auto projection = tcplot::create_plot_projection2d(scene, frame);
        require(projection.has_value(), "projection creation failed");
        const double values[]{0, 1, std::numeric_limits<double>::quiet_NaN(), 0.5};
        auto style = tc_plot_heatmap_item2d_default_style();
        style.colormap = TC_PLOT_COLORMAP_GRAYSCALE_2D;
        const auto item =
            tc_plot_heatmap_item2d_create(scene_handle, projection->handle(), values, 4, 2, 2, {0, 2, 0, 2}, style);
        require(!tc_graphic_item_handle_is_invalid(item), "heatmap creation failed");
        auto* renderer = tc_retained_scene_renderer2d_create(&host, scene_handle);
        require(renderer != nullptr, "renderer creation failed");
        tc_retained_scene_renderer2d_set_clear_srgb_color(renderer, {1, 0, 0, 1});
        require(tc_retained_scene_renderer2d_set_msaa_samples(renderer, 1) != 0, "MSAA setup failed");
        auto pixels = [&](int width = 128, int height = 128) {
            const auto id = tc_retained_scene_renderer2d_render(renderer, width, height);
            require(id != 0, "heatmap render failed");
            const auto desc = host.device().texture_desc(tgfx::TextureHandle{id});
            require(desc.format == tgfx::PixelFormat::RGBA16F,
                    "retained scene output must preserve linear color precision in an RGBA16F texture");
            require(desc.width == static_cast<uint32_t>(width) && desc.height == static_cast<uint32_t>(height) &&
                        desc.sample_count == static_cast<uint32_t>(tc_retained_scene_renderer2d_msaa_samples(renderer)),
                    "retained scene output must match the requested dimensions and MSAA count");
            host.device().wait_idle();
            std::vector<float> result(static_cast<size_t>(width) * height * 4);
            require(host.device().read_texture_rgba_float(tgfx::TextureHandle{id}, result.data()),
                    "heatmap readback failed");
            return result;
        };
        auto output = pixels();
        auto channel = [&](int x, int y, int c) {
            return output[(y * 128 + x) * 4 + c];
        };
        require(channel(40, 88, 0) < 0.02f && channel(40, 88, 1) < 0.02f, "lower-left must be minimum black cell");
        require(channel(88, 88, 0) > 0.95f && channel(88, 88, 1) > 0.95f, "lower-right must be maximum white cell");
        require(channel(40, 40, 0) > 0.95f && channel(40, 40, 1) < 0.02f, "NaN cell must reveal red clear color");
        require(channel(88, 40, 0) > 0.19f && channel(88, 40, 0) < 0.24f,
                "midpoint must be decoded from sRGB exactly once");
        require(channel(4, 4, 0) > 0.95f && channel(4, 4, 1) < 0.02f, "plot clip must preserve exterior");
        style.colormap_reversed = true;
        require(tc_plot_heatmap_item2d_set_style(scene_handle, item, style), "palette reverse failed");
        output = pixels();
        require(channel(40, 88, 0) > 0.95f && channel(88, 88, 0) < 0.02f,
                "palette reversal must affect retained rendering");
        style.colormap_reversed = false;
        style.auto_range = false;
        style.scalar_max = 2;
        require(tc_plot_heatmap_item2d_set_style(scene_handle, item, style), "fixed color range update failed");
        output = pixels();
        require(channel(88, 88, 0) > 0.19f && channel(88, 88, 0) < 0.24f,
                "fixed range must change sampled palette position");
        const double replacement[]{1, 0, std::numeric_limits<double>::quiet_NaN(), 0.5};
        require(tc_plot_heatmap_item2d_set_data(scene_handle, item, replacement, 4, 2, 2, {0, 2, 0, 2}),
                "grid replacement failed");
        output = pixels();
        require(channel(40, 88, 0) > 0.19f && channel(40, 88, 0) < 0.24f && channel(88, 88, 0) < 0.02f,
                "replacement data must update the scalar texture");
        const tcplot::PlotFrame2D zoomed{{0, 0, 128, 128}, {16, 16, 96, 96}, {0, 1, 0, 2}, {16, 16, 96, 96}, 1};
        require(projection->update(zoomed), "projection zoom failed");
        output = pixels();
        require(channel(40, 88, 0) > 0.19f && channel(40, 88, 0) < 0.24f && channel(88, 88, 0) > 0.19f &&
                    channel(88, 88, 0) < 0.24f,
                "projection zoom must show the first column across the plot");

        // A 0/1 scalar transition must pass through linearized middle gray,
        // rather than interpolate the already mapped black/white colors.
        require(projection->update(frame), "projection reset failed");
        style.scalar_max = 1;
        style.interpolation = TC_PLOT_HEATMAP_NEAREST_2D;
        require(tc_plot_heatmap_item2d_set_style(scene_handle, item, style), "nearest interpolation setup failed");
        const double horizontal[]{0, 1, 0, 1};
        require(tc_plot_heatmap_item2d_set_data(scene_handle, item, horizontal, 4, 2, 2, {0, 2, 0, 2}),
                "interpolation fixture setup failed");
        output = pixels();
        require(channel(64, 64, 1) > 0.95f, "nearest interpolation must preserve discrete cell colors");
        style.interpolation = TC_PLOT_HEATMAP_BILINEAR_2D;
        require(tc_plot_heatmap_item2d_set_style(scene_handle, item, style), "bilinear interpolation setup failed");
        output = pixels();
        require(channel(64, 64, 1) > 0.20f && channel(64, 64, 1) < 0.25f,
                "bilinear interpolation must map the interpolated scalar, not blend palette colors");
        require(channel(16, 64, 1) < 0.02f && channel(111, 64, 1) > 0.95f,
                "bilinear interpolation must clamp scalar samples at outer edges");
        style.interpolation = TC_PLOT_HEATMAP_NEAREST_2D;
        require(tc_plot_heatmap_item2d_set_style(scene_handle, item, style), "nearest switch failed");
        output = pixels();
        require(channel(64, 64, 1) > 0.95f, "switching back to nearest must work without replacing data");
        style.interpolation = TC_PLOT_HEATMAP_BILINEAR_2D;
        require(tc_plot_heatmap_item2d_set_style(scene_handle, item, style), "bilinear switch failed");
        const double four_way[]{0, 0, 0, 1};
        require(tc_plot_heatmap_item2d_set_data(scene_handle, item, four_way, 4, 2, 2, {0, 2, 0, 2}),
                "four-way interpolation fixture setup failed");
        output = pixels();
        require(channel(64, 64, 1) > 0.04f && channel(64, 64, 1) < 0.065f,
                "bilinear interpolation must combine all four neighboring scalar values");

        // Missing neighbors contribute zero coverage, not a zero scalar. At the
        // midpoint the remaining white cells blend with the red clear color.
        const double missing[]{
            std::numeric_limits<double>::quiet_NaN(), 1, std::numeric_limits<double>::quiet_NaN(), 1};
        require(tc_plot_heatmap_item2d_set_data(scene_handle, item, missing, 4, 2, 2, {0, 2, 0, 2}),
                "missing-neighbor interpolation fixture setup failed");
        output = pixels();
        require(channel(64, 64, 0) > 0.97f && channel(64, 64, 1) > 0.48f && channel(64, 64, 1) < 0.54f,
                "bilinear interpolation must renormalize valid scalars and reduce opacity by missing weight");
        require(channel(16, 64, 0) > 0.97f && channel(16, 64, 1) < 0.02f && channel(111, 64, 1) > 0.95f,
                "bilinear missing-cell edges must remain transparent and valid edges opaque");
        const double singleton[]{0.5};
        require(tc_plot_heatmap_item2d_set_data(scene_handle, item, singleton, 1, 1, 1, {0, 2, 0, 2}),
                "singleton interpolation fixture setup failed");
        output = pixels();
        require(channel(16, 16, 1) > 0.19f && channel(16, 16, 1) < 0.24f && channel(111, 111, 1) > 0.19f &&
                    channel(111, 111, 1) < 0.24f,
                "bilinear interpolation must clamp a 1x1 grid across its full extent");
        require(tc_plot_heatmap_item2d_set_data(scene_handle, item, missing, 1, 1, 1, {0, 2, 0, 2}),
                "missing singleton setup failed");
        output = pixels();
        require(channel(64, 64, 0) > 0.97f && channel(64, 64, 1) < 0.02f,
                "an all-missing bilinear grid must remain transparent");

        // Linear 8-bit intermediates collapse this entire dark sRGB gradient
        // into two levels. Inspect the linear target before presentation so a
        // later output transform cannot hide that earlier loss of precision.
        const double dark_ramp[]{0.01, 0.05, 0.01, 0.05};
        require(tc_plot_heatmap_item2d_set_data(scene_handle, item, dark_ramp, 4, 2, 2, {0, 2, 0, 2}),
                "dark gradient setup failed");
        auto verify_dark_gradient = [&](int width, int height, int plot_width, int plot_height) {
            const auto linear = pixels(width, height);
            const int first_x = 16 + plot_width / 4;
            const int last_x = 16 + plot_width * 3 / 4;
            const int y = 16 + plot_height / 2;
            float previous = -1;
            size_t distinct_levels = 0;
            for (int x = first_x; x < last_x; ++x) {
                const float weight = (static_cast<float>(x) + 0.5f - 16) / plot_width * 2 - 0.5f;
                const float srgb = 0.01f + weight * 0.04f;
                const float expected = termin::srgb_to_linear(termin::SrgbColor{srgb, srgb, srgb, 1}).r;
                const size_t pixel = (static_cast<size_t>(y) * width + x) * 4;
                const float actual = linear[pixel];
                // Allow finite sampler-weight precision and half-float rounding;
                // this is still far below one linear UNorm8 step (1/255).
                require(std::abs(actual - expected) < 0.00002f,
                        "dark gradient must retain its expected tiny linear values before presentation");
                require(std::abs(linear[pixel + 1] - actual) < 0.000002f &&
                            std::abs(linear[pixel + 2] - actual) < 0.000002f,
                        "dark grayscale gradient must preserve equal RGB channels");
                require(actual > previous, "dark gradient must retain a distinct increasing level at every pixel");
                if (actual > previous)
                    ++distinct_levels;
                previous = actual;
            }
            require(distinct_levels >= 48, "dark gradient must preserve many levels below one linear 8-bit step");
        };
        verify_dark_gradient(128, 128, 96, 96);
        require(tc_retained_scene_renderer2d_set_msaa_samples(renderer, 4) != 0, "4x MSAA setup failed");
        verify_dark_gradient(128, 128, 96, 96);
        const tcplot::PlotFrame2D resized{{0, 0, 192, 160}, {16, 16, 160, 128}, {0, 2, 0, 2}, {16, 16, 160, 128}, 1};
        require(projection->update(resized), "dark gradient resize projection failed");
        verify_dark_gradient(192, 160, 160, 128);
        require(tc_retained_scene_renderer2d_set_msaa_samples(renderer, 1) != 0, "single-sample restore failed");
        verify_dark_gradient(192, 160, 160, 128);
        tc_retained_scene_renderer2d_destroy(renderer);
        require(tc_visual_scene_destroy_item(scene_handle, item), "item destruction failed");
        require(tcplot::destroy_plot_projection2d(*projection), "projection destruction failed");
        tc_visual_scene_destroy(scene_handle);
        return 0;
    }
} // namespace

int main(int argc, char** argv) {
    if (argc == 2) {
        try {
            return pixels_test(std::strcmp(argv[1], "--d3d11") == 0 ? tgfx::BackendType::D3D11
                                                                    : tgfx::BackendType::Vulkan);
        } catch (const std::exception& e) {
            std::fprintf(stderr, "heatmap pixel test: %s\n", e.what());
            return 1;
        }
    }
    const auto scene_handle = tc_visual_scene_create(), other_handle = tc_visual_scene_create();
    termin::visual::TcVisualScene scene{scene_handle}, other{other_handle};
    const tcplot::PlotFrame2D frame{{0, 0, 640, 480}, {80, 40, 540, 380}, {0, 10, -5, 5}, {80, 40, 540, 380}, 1};
    const auto projection = tcplot::create_plot_projection2d(scene, frame);
    const auto other_projection = tcplot::create_plot_projection2d(other, frame);
    assert(projection && other_projection);
    const double nan = std::numeric_limits<double>::quiet_NaN();
    const double inf = std::numeric_limits<double>::infinity();
    double values[]{1, 2, nan, 4, 5, 6};
    const tc_plot_range2d bounds{0, 6, -2, 2};
    auto style = tc_plot_heatmap_item2d_default_style();
    assert(style.interpolation == TC_PLOT_HEATMAP_NEAREST_2D);
    const auto item = tc_plot_heatmap_item2d_create(scene_handle, projection->handle(), values, 6, 2, 3, bounds, style);
    assert(!tc_graphic_item_handle_is_invalid(item));
    assert(tc_graphic_item_handle_is_invalid(
        tc_plot_heatmap_item2d_create(other_handle, projection->handle(), values, 6, 2, 3, bounds, style)));
    assert(tc_graphic_item_handle_is_invalid(
        tc_plot_heatmap_item2d_create(scene_handle, projection->handle(), values, 5, 2, 3, bounds, style)));
    assert(tc_graphic_item_handle_is_invalid(
        tc_plot_heatmap_item2d_create(scene_handle, projection->handle(), values, 0, 0, 3, bounds, style)));
    assert(tc_graphic_item_handle_is_invalid(
        tc_plot_heatmap_item2d_create(scene_handle, projection->handle(), &inf, 1, 1, 1, bounds, style)));
    const double biggest = std::numeric_limits<double>::max();
    assert(tc_graphic_item_handle_is_invalid(tc_plot_heatmap_item2d_create(
        scene_handle, projection->handle(), values, 6, 2, 3, {-biggest, biggest, -2, 2}, style)));
    tc_plot_heatmap_snapshot2d snapshot{};
    tc_plot_heatmap_style2d copied_style{};
    assert(tc_plot_heatmap_item2d_snapshot(scene_handle, item, &snapshot, &copied_style));
    assert(snapshot.rows == 2 && snapshot.columns == 3 && snapshot.scalar_min == 1 && snapshot.scalar_max == 6);
    assert(snapshot.bounds.x_max == 6 && snapshot.revision == 1);
    values[0] = 100; // data is copied, not borrowed
    double copied[6]{};
    assert(tc_plot_heatmap_item2d_copy_data(scene_handle, item, nullptr, 0) == 6);
    assert(tc_plot_heatmap_item2d_copy_data(scene_handle, item, copied, 5) == 0);
    assert(tc_plot_heatmap_item2d_copy_data(scene_handle, item, copied, 6) == 6);
    assert(copied[0] == 1 && std::isnan(copied[2]));
    tc_plot_heatmap_sample2d sample{};
    assert(tc_plot_heatmap_item2d_sample(scene_handle, item, 0, -2, &sample));
    assert(sample.row == 0 && sample.column == 0 && sample.value == 1);
    assert(tc_plot_heatmap_item2d_sample(scene_handle, item, 2, -1, &sample));
    assert(sample.row == 0 && sample.column == 1 && sample.value == 2);
    assert(tc_plot_heatmap_item2d_sample(scene_handle, item, 6, 2, &sample));
    assert(sample.row == 1 && sample.column == 2 && sample.value == 6);
    assert(tc_plot_heatmap_item2d_sample(scene_handle, item, 5, -1, &sample) && std::isnan(sample.value));
    assert(!tc_plot_heatmap_item2d_sample(scene_handle, item, 6.01, 0, &sample));
    assert(!tc_plot_heatmap_item2d_sample(scene_handle, item, nan, 0, &sample));
    assert(!tc_plot_heatmap_item2d_set_projection(scene_handle, item, other_projection->handle()));
    assert(!tc_plot_heatmap_item2d_snapshot(other_handle, item, &snapshot, &copied_style));
    assert(!tc_plot_line_series_item2d_set_data(scene_handle, item, nullptr, nullptr, nullptr, 0));
    style.auto_range = false;
    style.scalar_min = -10;
    style.scalar_max = 10;
    assert(tc_plot_heatmap_item2d_set_style(scene_handle, item, style));
    assert(tc_plot_heatmap_item2d_snapshot(scene_handle, item, &snapshot, &copied_style));
    assert(snapshot.scalar_min == -10 && snapshot.scalar_max == 10);
    const auto revision = snapshot.revision;
    auto invalid_style = style;
    invalid_style.interpolation = static_cast<tc_plot_heatmap_interpolation2d>(99);
    assert(!tc_plot_heatmap_item2d_set_style(scene_handle, item, invalid_style));
    assert(tc_graphic_item_handle_is_invalid(
        tc_plot_heatmap_item2d_create(scene_handle, projection->handle(), values, 6, 2, 3, bounds, invalid_style)));
    invalid_style = style;
    invalid_style.scalar_max = invalid_style.scalar_min;
    assert(!tc_plot_heatmap_item2d_set_style(scene_handle, item, invalid_style));
    assert(!tc_plot_heatmap_item2d_set_data(scene_handle, item, &inf, 1, 1, 1, bounds));
    assert(tc_plot_heatmap_item2d_snapshot(scene_handle, item, &snapshot, &copied_style) &&
           snapshot.revision == revision);
    style.auto_range = true;
    style.interpolation = TC_PLOT_HEATMAP_BILINEAR_2D;
    assert(tc_plot_heatmap_item2d_set_style(scene_handle, item, style));
    assert(tc_plot_heatmap_item2d_snapshot(scene_handle, item, &snapshot, &copied_style));
    assert(copied_style.interpolation == TC_PLOT_HEATMAP_BILINEAR_2D);
    const double constant[]{4};
    assert(tc_plot_heatmap_item2d_set_data(scene_handle, item, constant, 1, 1, 1, bounds));
    assert(tc_plot_heatmap_item2d_snapshot(scene_handle, item, &snapshot, &copied_style));
    assert(snapshot.scalar_min < 4 && snapshot.scalar_max > 4);
    assert(tc_plot_heatmap_item2d_set_data(scene_handle, item, &nan, 1, 1, 1, bounds));
    assert(tc_plot_heatmap_item2d_snapshot(scene_handle, item, &snapshot, &copied_style));
    assert(snapshot.scalar_min == 0 && snapshot.scalar_max == 1);
    assert(tc_plot_heatmap_item2d_set_data(scene_handle, item, &biggest, 1, 1, 1, bounds));
    assert(tc_plot_heatmap_item2d_snapshot(scene_handle, item, &snapshot, &copied_style));
    assert(std::isfinite(snapshot.scalar_min) && std::isfinite(snapshot.scalar_max) &&
           snapshot.scalar_min < snapshot.scalar_max);

    // Scene snapshots contain one retained command regardless of cell count.
    std::vector<double> large(1024 * 1024, 2);
    assert(tc_plot_heatmap_item2d_set_data(scene_handle, item, large.data(), large.size(), 1024, 1024, bounds));
    Resolver resolver;
    tgfx::DrawList2DBuilder builder;
    assert(scene.paint(builder, resolver));
    const auto draw_list = builder.freeze();
    assert(draw_list);
    size_t commands = 0;
    for (const auto& command : draw_list->commands())
        if (std::holds_alternative<tgfx::DrawRetainedBatch2D>(command))
            ++commands;
    assert(commands == 1);
    assert(tc_visual_scene_destroy_item(scene_handle, item));
    assert(!tc_plot_heatmap_item2d_snapshot(scene_handle, item, &snapshot, &copied_style));
    assert(tcplot::destroy_plot_projection2d(*projection));
    assert(tcplot::destroy_plot_projection2d(*other_projection));
    tc_visual_scene_destroy(scene_handle);
    tc_visual_scene_destroy(other_handle);
}
