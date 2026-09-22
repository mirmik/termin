#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <filesystem>
#include <fstream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <system_error>

#include <tgfx2/builtin_shader_sources.hpp>
#include <tgfx2/device_factory.hpp>
#include <tgfx2/tc_shader_bridge.hpp>
#include <tgfx2/vulkan/vulkan_render_device.hpp>

#include <termin/camera/orbit_camera.hpp>
#include <termin/geom/color.hpp>

#include <termin/render/builtin_passes.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/render/frame_pass.hpp>
#include <termin/render/render_engine.hpp>
#include <termin/render/render_item_submission.hpp>
#include <termin/render/render_pipeline.hpp>
#include <termin/render/render_task.hpp>

#include "tcplot/gpu_host.hpp"
#include "tcplot/plot_scene3d_render_item_source.hpp"
#include "tcplot/retained_chart3d.h"
#include "tcplot/retained_chart2d.h"
#include "tcplot/retained_scene_renderer2d.h"

#include "../src/plot_scene3d_chart_chrome.hpp"

extern "C" {
#include <render/tc_pass.h>
#include <tgfx/resources/tc_shader_registry.h>
}

namespace {

    void require(bool condition, const char* message);

    void test_termin_clip_canvas_projection() {
        const auto top_left = tcplot::detail::termin_clip_ndc_to_canvas(-1.0f, -1.0f, 320, 240);
        const auto center = tcplot::detail::termin_clip_ndc_to_canvas(0.0f, 0.0f, 320, 240);
        const auto bottom_right = tcplot::detail::termin_clip_ndc_to_canvas(1.0f, 1.0f, 320, 240);

        require(top_left.x == 0.0f && top_left.y == 0.0f,
                "TerminClip top-left must project to canvas top-left");
        require(center.x == 160.0f && center.y == 120.0f,
                "TerminClip center must project to canvas center");
        require(bottom_right.x == 320.0f && bottom_right.y == 240.0f,
                "TerminClip bottom-right must project to canvas bottom-right");
    }

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

    uint32_t test_texture_sample_support(tcplot::GpuHost& host) {
#ifdef TGFX2_HAS_VULKAN
        auto& device = static_cast<tgfx::VulkanRenderDevice&>(host.device());
        uint32_t supported_samples = 0;
        for (uint32_t samples = 1; samples <= 128; samples *= 2) {
            bool attachments_supported = true;
            for (const auto format : {tgfx::PixelFormat::RGBA8_UNorm, tgfx::PixelFormat::D32F}) {
                tgfx::TextureDesc desc;
                desc.width = 320;
                desc.height = 240;
                desc.format = format;
                desc.sample_count = samples;
                desc.usage = tgfx::TextureUsage::Sampled | tgfx::TextureUsage::CopySrc |
                             tgfx::TextureUsage::CopyDst |
                             (format == tgfx::PixelFormat::D32F ? tgfx::TextureUsage::DepthStencilAttachment
                                                              : tgfx::TextureUsage::ColorAttachment);
                const bool supported = device.supports_texture(desc);
                attachments_supported &= supported;
                bool created = false;
                try {
                    const auto texture = device.create_texture(desc);
                    created = static_cast<bool>(texture);
                    device.destroy(texture);
                } catch (const std::runtime_error&) {
                    require(!supported, "supported texture descriptor failed creation");
                }
                require(created == supported, "texture creation disagrees with sample support query");
            }
            if (attachments_supported)
                supported_samples |= samples;
        }
        require((supported_samples & 1) != 0, "chart attachments require single-sample support");
        for (uint32_t samples : {2u, 4u, 8u, 16u}) {
            if ((supported_samples & samples) != 0)
                return samples;
        }
        throw std::runtime_error("no supported multisample chart attachment combination");
#else
        (void)host;
        throw std::runtime_error("Vulkan backend is unavailable");
#endif
    }

    tc_plot_item3d_snapshot snapshot(tc_retained_chart3d* chart, tc_plot_item3d_handle item) {
        tc_plot_item3d_snapshot result{};
        require(tc_retained_chart3d_item_snapshot(chart, item, &result) != 0, "failed to snapshot retained item");
        return result;
    }

    bool same_snapshot(const tc_plot_item3d_snapshot& left, const tc_plot_item3d_snapshot& right) {
        return left.kind == right.kind && left.geometry_revision == right.geometry_revision &&
               left.style_revision == right.style_revision && left.gpu_revision == right.gpu_revision;
    }

    termin::Vec2 project_camera_point(const tc_orbit_camera3d_state& state,
                                      const termin::Vec3& point,
                                      double width,
                                      double height) {
        termin::OrbitCamera camera;
        camera.target = {state.target_x, state.target_y, state.target_z};
        camera.distance = state.distance;
        camera.azimuth = state.azimuth;
        camera.elevation = state.elevation;
        camera.fov_y = state.fov_y;
        camera.near_clip = state.near_clip;
        camera.far_clip = state.far_clip;
        const termin::Mat44 projection_view = camera.mvp(width / height);
        const double clip_x = projection_view(0, 0) * point.x + projection_view(1, 0) * point.y +
                             projection_view(2, 0) * point.z + projection_view(3, 0);
        const double clip_y = projection_view(0, 1) * point.x + projection_view(1, 1) * point.y +
                             projection_view(2, 1) * point.z + projection_view(3, 1);
        const double clip_w = projection_view(0, 3) * point.x + projection_view(1, 3) * point.y +
                             projection_view(2, 3) * point.z + projection_view(3, 3);
        return {(clip_x / clip_w + 1.0) * 0.5 * width, (clip_y / clip_w + 1.0) * 0.5 * height};
    }

    std::vector<float> read_pixels(tcplot::GpuHost& host, uint32_t texture_id, uint32_t width, uint32_t height) {
        tgfx::TextureHandle texture{};
        texture.id = texture_id;
        std::vector<float> pixels(static_cast<std::size_t>(width) * height * 4u, 0.0f);
        require(host.device().read_texture_rgba_float(texture, pixels.data()),
                "failed to read retained Chart3D encoder output");
        return pixels;
    }

    std::size_t count_non_clear_pixels(tcplot::GpuHost& host, uint32_t texture_id, uint32_t width, uint32_t height) {
        const std::vector<float> pixels = read_pixels(host, texture_id, width, height);
        const termin::LinearColor clear =
            termin::srgb_to_linear(termin::SrgbColor{0.08f, 0.09f, 0.11f, 1.0f});
        std::size_t count = 0;
        for (std::size_t index = 0; index + 3 < pixels.size(); index += 4) {
            if (std::abs(pixels[index + 0] - clear.r) > 0.03f ||
                std::abs(pixels[index + 1] - clear.g) > 0.03f ||
                std::abs(pixels[index + 2] - clear.b) > 0.03f) {
                ++count;
            }
        }
        return count;
    }

    std::size_t count_changed_pixels(const std::vector<float>& left, const std::vector<float>& right) {
        require(left.size() == right.size(), "cannot compare retained Chart3D images with different sizes");
        std::size_t count = 0;
        for (std::size_t index = 0; index + 3 < left.size(); index += 4) {
            if (std::abs(left[index + 0] - right[index + 0]) > 0.01f ||
                std::abs(left[index + 1] - right[index + 1]) > 0.01f ||
                std::abs(left[index + 2] - right[index + 2]) > 0.01f) {
                ++count;
            }
        }
        return count;
    }

    bool same_color(tc_visual_color4f left, tc_visual_color4f right) {
        return left.r == right.r && left.g == right.g && left.b == right.b && left.a == right.a;
    }

    void test_background_color_cpu() {
        using ChartOwner = std::unique_ptr<tc_retained_chart3d, decltype(&tc_retained_chart3d_destroy)>;
        const tc_visual_color4f default_color{0.08f, 0.09f, 0.11f, 1};
        const tc_visual_color4f custom{0.15f, 0.42f, 0.73f, 0.25f};
        require(!tc_retained_chart3d_set_background_color(nullptr, custom) &&
                    !tc_retained_chart3d_get_background_color(nullptr, nullptr),
                "null chart background calls must fail safely");
        for (bool spherical : {false, true}) {
            ChartOwner chart(spherical ? tc_retained_chart3d_create_spherical(nullptr)
                                       : tc_retained_chart3d_create(nullptr), tc_retained_chart3d_destroy);
            require(chart != nullptr, "failed to create background test chart");
            tc_visual_color4f color{};
            require(tc_retained_chart3d_get_background_color(chart.get(), &color) && same_color(color, default_color),
                    "both coordinate systems must preserve the original default background");
            require(!tc_retained_chart3d_get_background_color(chart.get(), nullptr),
                    "null output color must be rejected");
            const auto grid = tc_retained_chart3d_grid_part(chart.get());
            const auto before = snapshot(chart.get(), grid);
            tc_orbit_camera3d_state camera{}, after_camera{};
            require(tc_retained_chart3d_get_camera(chart.get(), &camera), "failed to get background test camera");
            require(tc_retained_chart3d_set_background_color(chart.get(), custom), "failed to set custom background");
            for (int channel = 0; channel < 4; ++channel) {
                for (float invalid : {-0.01f, 1.01f, std::numeric_limits<float>::quiet_NaN(),
                                       std::numeric_limits<float>::infinity()}) {
                    auto bad_color = custom;
                    float* channels[] = {&bad_color.r, &bad_color.g, &bad_color.b, &bad_color.a};
                    *channels[channel] = invalid;
                    require(!tc_retained_chart3d_set_background_color(chart.get(), bad_color) &&
                                tc_retained_chart3d_get_background_color(chart.get(), &color) && same_color(color, custom),
                            "invalid RGBA values must fail without changing the background");
                }
            }
            require(tc_retained_chart3d_get_camera(chart.get(), &after_camera) &&
                        after_camera.target_x == camera.target_x && after_camera.target_y == camera.target_y &&
                        after_camera.target_z == camera.target_z && after_camera.distance == camera.distance &&
                        after_camera.azimuth == camera.azimuth && after_camera.elevation == camera.elevation &&
                        same_snapshot(before, snapshot(chart.get(), grid)),
                    "background mutation must not change camera or item geometry/style revisions");
            tc_retained_chart3d_clear_data(chart.get());
            tc_retained_chart3d_release_gpu(chart.get());
            require(tc_retained_chart3d_set_msaa_samples(chart.get(), 2) &&
                        tc_retained_chart3d_get_background_color(chart.get(), &color) && same_color(color, custom),
                    "background must persist across data clearing and GPU/pipeline recreation");
            require(tc_retained_chart3d_set_background_color(chart.get(), {0, 1, 0, 0}) &&
                        tc_retained_chart3d_get_background_color(chart.get(), &color) &&
                        same_color(color, {0, 1, 0, 0}),
                    "background endpoints including transparent alpha must be accepted exactly");
        }
    }

    void test_background_color_d3d11(tcplot::GpuHost& host) {
        using ChartOwner = std::unique_ptr<tc_retained_chart3d, decltype(&tc_retained_chart3d_destroy)>;
        constexpr uint32_t width = 96, height = 72;
        for (bool spherical : {false, true}) {
            ChartOwner chart(spherical ? tc_retained_chart3d_create_spherical(&host)
                                       : tc_retained_chart3d_create(&host), tc_retained_chart3d_destroy);
            require(chart && tc_retained_chart3d_destroy_item(chart.get(), tc_retained_chart3d_grid_part(chart.get())),
                    "failed to create empty background render chart");
            for (int samples : {1, 4}) {
                require(tc_retained_chart3d_set_msaa_samples(chart.get(), samples), "failed to configure background MSAA");
                uint32_t output_texture = 0;
                for (tc_visual_color4f color : {tc_visual_color4f{0.08f, 0.09f, 0.11f, 1},
                                                tc_visual_color4f{0.8f, 0.3f, 0.2f, 0.35f},
                                                tc_visual_color4f{0.2f, 0.7f, 0.5f, 0.8f},
                                                tc_visual_color4f{0.08f, 0.09f, 0.11f, 1}}) {
                    require(tc_retained_chart3d_set_background_color(chart.get(), color), "failed to set D3D11 background");
                    const auto texture = tc_retained_chart3d_render(chart.get(), width, height);
                    require(texture != 0 && (output_texture == 0 || output_texture == texture),
                            "background changes must render into the existing chart output");
                    output_texture = texture;
                    const auto pixels = read_pixels(host, texture, width, height);
                    const auto linear = termin::srgb_to_linear(termin::SrgbColor{color.r, color.g, color.b, color.a});
                    for (size_t pixel = 0; pixel < pixels.size(); pixel += 4) {
                        require(std::abs(pixels[pixel] - linear.r) < 1.5f / 255 &&
                                    std::abs(pixels[pixel + 1] - linear.g) < 1.5f / 255 &&
                                    std::abs(pixels[pixel + 2] - linear.b) < 1.5f / 255 &&
                                    std::abs(pixels[pixel + 3] - linear.a) < 1.5f / 255,
                                "live D3D11 background must match linearized RGB and preserve alpha for every pixel");
                    }
                }
            }
        }
    }

    void test_retained_chart2d_colors_d3d11(tcplot::GpuHost& host) {
        using ChartOwner = std::unique_ptr<tc_retained_chart2d, decltype(&tc_retained_chart2d_destroy)>;
        using RendererOwner = std::unique_ptr<tc_retained_scene_renderer2d,
            decltype(&tc_retained_scene_renderer2d_destroy)>;
        constexpr uint32_t width = 240, height = 180;
        auto theme = tc_retained_chart2d_default_theme();
        theme.background_color = {0.3f, 0.4f, 0.6f, 1};
        theme.plot_background_color = {0.05f, 0.07f, 0.09f, 1};
        const tc_plot_color2d authored{0.7f, 0.2f, 0.5f, 1};
        const double x[] = {0.2, 0.8}, y[] = {0.5, 0.5}, scalar[] = {0.5, 0.5};
        for (int mode = 0; mode < 4; ++mode) {
            ChartOwner chart(tc_retained_chart2d_create(&host, {0, 0, width, height}, {0, 1, 0, 1},
                "ui://default-font", 1, &theme), tc_retained_chart2d_destroy);
            require(chart != nullptr, "failed to create Chart2D color fixture");
            const auto scene = tc_retained_chart2d_scene(chart.get());
            require(tc_visual_scene_item_set_visible(scene,
                        tc_retained_chart2d_part_handle(chart.get(), TC_CHART2D_PART_GRID), false) &&
                    tc_visual_scene_item_set_visible(scene,
                        tc_retained_chart2d_part_handle(chart.get(), TC_CHART2D_PART_CHROME_ROOT), false),
                    "failed to isolate Chart2D series colors");
            tc_chart_series_handle2d series{};
            if (mode == 2) {
                series = tc_retained_chart2d_add_named_scatter(chart.get(), "", false, x, y, 1, {authored, 18});
            } else {
                tc_plot_line_style_state2d style{authored, mode == 0 ? 1.0f : 8.0f,
                    mode == 1 ? TC_PLOT_LINE_STYLE_DASH_2D : TC_PLOT_LINE_STYLE_SOLID_2D, 8, 4,
                    mode == 3 ? TC_PLOT_COLORMAP_GRAYSCALE_2D : TC_PLOT_COLORMAP_SOLID_2D, false, 0, 1};
                series = tc_retained_chart2d_add_named_line(chart.get(), "", false, x, y,
                    mode == 3 ? scalar : nullptr, 2, style);
            }
            require(tc_retained_chart2d_series_is_valid(chart.get(), series), "failed to add Chart2D color series");
            RendererOwner renderer(tc_retained_scene_renderer2d_create(&host, scene), tc_retained_scene_renderer2d_destroy);
            require(renderer && tc_retained_scene_renderer2d_set_msaa_samples(renderer.get(), 1),
                    "failed to create Chart2D color renderer");
            const auto texture = tc_retained_scene_renderer2d_render(renderer.get(), width, height);
            require(texture != 0, "failed to render Chart2D color fixture");
            const auto pixels = read_pixels(host, texture, width, height);
            const auto background = termin::srgb_to_linear(termin::SrgbColor{0.3f, 0.4f, 0.6f, 1});
            const size_t corner = (2 * width + 2) * 4;
            require(std::abs(pixels[corner] - background.r) < 1.5f / 255 &&
                        std::abs(pixels[corner + 1] - background.g) < 1.5f / 255 &&
                        std::abs(pixels[corner + 2] - background.b) < 1.5f / 255,
                    "Chart2D authored theme fill must render into a linear target");
            const auto expected = termin::srgb_to_linear(mode == 3 ? termin::SrgbColor{0.5f, 0.5f, 0.5f, 1}
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

    void capture_spherical_image(const std::vector<float>& pixels, uint32_t width, uint32_t height) {
        const char* path = std::getenv("TERMIN_SPHERICAL_CAPTURE");
        if (!path || !*path)
            return;
        std::ofstream output(path, std::ios::binary);
        require(output.is_open(), "failed to open spherical capture output");
        output << "P6\n" << width << ' ' << height << "\n255\n";
        for (size_t pixel = 0; pixel < pixels.size(); pixel += 4) {
            for (size_t channel = 0; channel < 3; ++channel) {
                const float linear = std::clamp(pixels[pixel + channel], 0.0f, 1.0f);
                const float srgb = linear <= 0.0031308f ? linear * 12.92f
                                                      : 1.055f * std::pow(linear, 1.0f / 2.4f) - 0.055f;
                output.put(static_cast<char>(std::lround(srgb * 255.0f)));
            }
        }
        output.close();
        require(output.good(), "failed to write spherical capture output");
        std::printf("spherical Chart3D capture written to %s\n", path);
    }

    void test_spherical_chart_d3d11(tcplot::GpuHost& host) {
        constexpr double pi = 3.14159265358979323846;
        constexpr uint32_t rows = 25, columns = 48, width = 800, height = 600;
        std::vector<double> azimuths(columns), polar(rows), radii(rows * columns);
        for (uint32_t column = 0; column < columns; ++column)
            azimuths[column] = 2.0 * pi * column / columns;
        for (uint32_t row = 0; row < rows; ++row) {
            polar[row] = pi * row / (rows - 1);
            for (uint32_t column = 0; column < columns; ++column) {
                const double latitude = row == 0 || row + 1 == rows ? 0.0 : std::sin(polar[row]);
                radii[row * columns + column] = 2.0 + 0.6 * latitude * latitude * std::cos(2 * azimuths[column]) +
                                               0.35 * latitude * std::cos(azimuths[column]);
            }
        }
        std::unique_ptr<tc_retained_chart3d, decltype(&tc_retained_chart3d_destroy)> chart(
            tc_retained_chart3d_create_spherical(&host), tc_retained_chart3d_destroy);
        require(chart != nullptr, "failed to create D3D11 spherical chart");
        require(tc_retained_chart3d_set_msaa_samples(chart.get(), 1), "failed to configure D3D11 spherical MSAA");
        tc_surface_item3d_style style{};
        style.color_r = style.color_g = style.color_b = style.color_a = 1;
        style.colormap = TC_PLOT_COLORMAP3D_VIRIDIS;
        style.surface_grid_visible = 1;
        style.surface_grid_row_step = 3;
        style.surface_grid_col_step = 6;
        style.surface_grid_width_px = 1.0f;
        style.surface_grid_r = style.surface_grid_g = style.surface_grid_b = 0.07f;
        style.surface_grid_a = 0.7f;
        const auto surface = tc_retained_chart3d_add_spherical_surface(
            chart.get(), azimuths.data(), columns, polar.data(), rows, radii.data(), 1, &style);
        require(tc_retained_chart3d_item_is_valid(chart.get(), surface), "failed to add D3D11 spherical surface");
        tc_colorbar3d_style colorbar{5, 18.0f, 0.62f, 18.0f, 8.0f, 13.0f,
                                     0.8f, 0.8f, 0.8f, 1.0f, 0.42f, 0.45f, 0.52f, 1.0f};
        require(tc_retained_chart3d_set_colorbar(chart.get(), surface, "radius", &colorbar),
                "failed to add D3D11 radial colorbar");
        const auto render = [&] {
            const uint32_t texture = tc_retained_chart3d_render(chart.get(), width, height);
            require(texture != 0, "D3D11 spherical render failed");
            return read_pixels(host, texture, width, height);
        };
        const uint32_t first_texture = tc_retained_chart3d_render(chart.get(), width, height);
        require(first_texture != 0 && count_non_clear_pixels(host, first_texture, width, height) > 4000,
                "D3D11 spherical chart must visibly render its surface and reference frame");
        const auto first = read_pixels(host, first_texture, width, height);
        capture_spherical_image(first, width, height);

        tc_retained_chart3d_clear_colorbar(chart.get());
        const auto no_colorbar = render();
        require(count_changed_pixels(first, no_colorbar) > 100,
                "radial colorbar must change the rendered D3D11 image");
        require(tc_retained_chart3d_set_colorbar(chart.get(), surface, "radius", &colorbar),
                "failed to restore D3D11 radial colorbar");

        const auto grid = tc_retained_chart3d_grid_part(chart.get());
        tc_grid_item3d_style grid_style{};
        require(tc_retained_chart3d_grid_get_style(chart.get(), grid, &grid_style),
                "failed to read spherical grid style");
        grid_style.labels_visible = 0;
        require(tc_retained_chart3d_grid_set_style(chart.get(), grid, &grid_style),
                "failed to hide spherical angle/radius labels");
        const auto no_labels = render();
        require(count_changed_pixels(first, no_labels) > 10,
                "spherical angle and radius labels must appear in the D3D11 image");
        grid_style.labels_visible = 1;
        require(tc_retained_chart3d_grid_set_style(chart.get(), grid, &grid_style),
                "failed to restore spherical labels");
        for (double& radius : radii)
            radius *= 0.8;
        require(tc_retained_chart3d_spherical_surface_set_radii(chart.get(), surface, radii.data(), radii.size()),
                "failed to update D3D11 spherical radii");
        const auto updated = render();
        require(count_changed_pixels(first, updated) > 100,
                "updated radii must change the D3D11 surface image without resetting the camera");

        // A 0.002 m^2 RCS sample is -26.99 dBsm: offset -40 leaves a
        // positive radius 13.01. Render the constant sphere independently of
        // grid geometry so a visible reference frame cannot mask a missing surface.
        radii.assign(radii.size(), 13.01);
        require(tc_retained_chart3d_spherical_surface_set_radii(chart.get(), surface, radii.data(), radii.size()) &&
                    tc_retained_chart3d_set_axis_display_offset(chart.get(), TC_PLOT_AXIS3D_RADIUS, -40) &&
                    tc_retained_chart3d_set_axis_tick_label(chart.get(), TC_PLOT_AXIS3D_RADIUS, 0, "<= -40 dBsm") &&
                    tc_retained_chart3d_destroy_item(chart.get(), grid),
                "failed to configure constant dBsm sphere");
        tc_retained_chart3d_fit_camera(chart.get());
        tc_retained_chart3d_clear_colorbar(chart.get());
        const uint32_t constant_texture = tc_retained_chart3d_render(chart.get(), width, height);
        require(constant_texture != 0 && count_non_clear_pixels(host, constant_texture, width, height) > 4000,
                "constant-radius sphere must remain visible without coordinate grid or colorbar");
        const auto constant_surface = read_pixels(host, constant_texture, width, height);
        require(tc_retained_chart3d_set_axis_display_offset(chart.get(), TC_PLOT_AXIS3D_RADIUS, 100),
                "failed to change display-only offset");
        require(count_changed_pixels(constant_surface, render()) == 0,
                "display offset must leave every surface pixel unchanged");
        require(tc_retained_chart3d_set_axis_display_offset(chart.get(), TC_PLOT_AXIS3D_RADIUS, -40) &&
                    tc_retained_chart3d_set_colorbar(chart.get(), surface, "dBsm", &colorbar),
                "failed to attach constant dBsm colorbar");
        const auto constant_colorbar = render();
        require(count_changed_pixels(constant_surface, constant_colorbar) > 100,
                "constant-radius colorbar must remain visible with its single offset label");
        require(tc_retained_chart3d_set_axis_display_offset(chart.get(), TC_PLOT_AXIS3D_RADIUS, 0),
                "failed to reset constant colorbar offset");
        require(count_changed_pixels(constant_colorbar, render()) > 10,
                "constant colorbar must render the changed display label");
    }

    const tc_render_item* find_render_item(const termin::RenderItemSnapshot& snapshot, tc_plot_item3d_handle handle) {
        for (const tc_render_item& item : snapshot.items()) {
            if (item.source.namespace_id == handle.scene_id && item.source.object_id == handle.index &&
                item.source.generation == handle.generation) {
                return &item;
            }
        }
        return nullptr;
    }

    const tcplot::PlotScene3DRenderItemPayload* find_plot_payload(const termin::RenderItemSnapshot& snapshot,
                                                                  tc_plot_item3d_handle handle) {
        const tc_render_item* item = find_render_item(snapshot, handle);
        return item ? tcplot::plot_scene3d_render_item_payload(*item) : nullptr;
    }

    void test_axis_display_cpu() {
        constexpr double pi = 3.14159265358979323846;
        constexpr auto radius_axis = TC_PLOT_AXIS3D_RADIUS;
        using ChartOwner = std::unique_ptr<tc_retained_chart3d, decltype(&tc_retained_chart3d_destroy)>;
        ChartOwner spherical(tc_retained_chart3d_create_spherical(nullptr), tc_retained_chart3d_destroy);
        ChartOwner cartesian(tc_retained_chart3d_create(nullptr), tc_retained_chart3d_destroy);
        require(spherical && cartesian, "failed to create axis display charts");
        auto* chart = spherical.get();
        double offset = 123.0;
        require(tc_retained_chart3d_get_axis_display_offset(chart, radius_axis, &offset) && offset == 0,
                "axis display defaults must preserve old numeric labels");
        for (auto axis : {TC_PLOT_AXIS3D_X, TC_PLOT_AXIS3D_Y, TC_PLOT_AXIS3D_Z}) {
            const double expected = 12.5 + static_cast<int>(axis);
            require(tc_retained_chart3d_set_axis_display_offset(cartesian.get(), axis, expected) &&
                        tc_retained_chart3d_get_axis_display_offset(cartesian.get(), axis, &offset) && offset == expected,
                    "Cartesian axes must support independent offsets");
            require(!tc_retained_chart3d_set_axis_display_offset(chart, axis, 1) &&
                        !tc_retained_chart3d_set_axis_tick_label(chart, axis, 0, "bad") &&
                        !tc_retained_chart3d_clear_axis_tick_labels(chart, axis),
                    "spherical charts must reject Cartesian display axes");
        }
        termin::RenderItemSnapshot cartesian_frame;
        require(tcplot::plot_scene3d_render_item_source(*cartesian).publish(cartesian_frame, {}),
                "failed to publish Cartesian display frame");
        const auto* cartesian_grid = find_plot_payload(cartesian_frame, tc_retained_chart3d_grid_part(cartesian.get()));
        require(cartesian_grid && cartesian_grid->frame.axis_display[0].offset == 12.5 &&
                    cartesian_grid->frame.axis_display[1].offset == 13.5 &&
                    cartesian_grid->frame.axis_display[2].offset == 14.5,
                "Cartesian display settings must remain independent in the rendered frame");
        require(!tc_retained_chart3d_set_axis_display_offset(cartesian.get(), radius_axis, 1) &&
                    !tc_retained_chart3d_set_axis_display_offset(chart, static_cast<tc_plot_axis3d>(-1), 1) &&
                    !tc_retained_chart3d_get_axis_display_offset(chart, TC_PLOT_AXIS3D_Z, &offset) &&
                    !tc_retained_chart3d_get_axis_display_offset(chart, radius_axis, nullptr),
                "invalid display axis calls must fail safely");
        require(tc_retained_chart3d_set_axis_display_offset(chart, radius_axis, -40) &&
                    tc_retained_chart3d_set_axis_tick_label(chart, radius_axis, 0, "<= -40 dBsm"),
                "failed to configure radial display before adding data");
        for (double invalid : {std::numeric_limits<double>::quiet_NaN(),
                               std::numeric_limits<double>::infinity()}) {
            require(!tc_retained_chart3d_set_axis_display_offset(chart, radius_axis, invalid) &&
                        !tc_retained_chart3d_set_axis_tick_label(chart, radius_axis, invalid, "bad"),
                    "display settings must reject non-finite values");
        }
        require(tc_retained_chart3d_get_axis_display_offset(chart, radius_axis, &offset) && offset == -40,
                "invalid offsets must not mutate settings");
        const double azimuths[] = {0, pi / 2, pi, 3 * pi / 2};
        const double polar[] = {0, pi / 2, pi};
        std::vector<double> radii(12, 13.01);
        auto surface = tc_retained_chart3d_add_spherical_surface(chart, azimuths, 4, polar, 3, radii.data(), 1, nullptr);
        require(tc_retained_chart3d_item_is_valid(chart, surface), "failed to add constant display sphere");
        auto& source = tcplot::plot_scene3d_render_item_source(*chart);
        termin::RenderItemSnapshot first;
        require(source.publish(first, {}), "failed to publish radial display frame");
        const auto* original = find_plot_payload(first, surface);
        require(original && original->frame.axis_display[radius_axis].offset == -40,
                "snapshot must own axis display settings");
        const auto constant_range = tcplot::plot_scene3d_surface_color_range(*original->item, original->frame);
        const auto constant_ticks = tcplot::plot_axis3d_display_ticks(
            original->frame.axis_display[radius_axis], constant_range[0], constant_range[1], 5);
        require(constant_range == std::array<double, 2>{13.01, 13.01} && constant_ticks.size() == 1 &&
                    constant_ticks[0].value == 13.01 && constant_ticks[0].label == "-26.99",
                "constant radius must expose one true offset label without the zero-radius override");
        const auto radial_ticks = tcplot::plot_axis3d_display_ticks(original->frame.axis_display[radius_axis], 0, 13.01, 5);
        require(!radial_ticks.empty() && radial_ticks.front().value == 0 && radial_ticks.front().label == "<= -40 dBsm",
                "radial origin must use its explicit raw-value label");

        const auto before = snapshot(chart, surface);
        tc_orbit_camera3d_state camera{};
        require(tc_retained_chart3d_get_camera(chart, &camera), "failed to get display test camera");
        require(tc_retained_chart3d_set_axis_display_offset(chart, radius_axis, 5) &&
                    tc_retained_chart3d_set_axis_tick_label(chart, radius_axis, 13.01, "constant"),
                "failed to update display state");
        termin::RenderItemSnapshot changed;
        require(source.publish(changed, {}), "failed to publish changed display frame");
        const auto* updated = find_plot_payload(changed, surface);
        require(updated && updated->item == original->item && same_snapshot(before, snapshot(chart, surface)) &&
                    updated->frame.bounds_min == original->frame.bounds_min &&
                    updated->frame.bounds_max == original->frame.bounds_max &&
                    updated->frame.camera.azimuth == camera.azimuth && updated->frame.camera.distance == camera.distance &&
                    tcplot::plot_scene3d_surface_color_range(*updated->item, updated->frame) == constant_range &&
                    original->frame.axis_display[radius_axis].offset == -40 &&
                    original->frame.axis_display[radius_axis].tick_labels.size() == 1,
                "display mutations must preserve geometry, colors, camera and old snapshots");

        // Explicit labels outside nice-number ticks must be inserted only in their domain.
        tcplot::PlotAxis3DDisplay display;
        display.offset = -40;
        display.tick_labels = {{0, "floor"}, {1.3, "boundary"}, {5, ""}};
        const auto ticks = tcplot::plot_axis3d_display_ticks(display, 1.3, 8, 3);
        require(ticks.size() == 2 && ticks[0].value == 1.3 && ticks[0].label == "boundary" &&
                    ticks[1].value == 5 && ticks[1].label.empty(),
                "raw label overrides must insert omitted bounds, hide empty labels and exclude other domains");
        display.tick_labels.clear();
        const auto shifted = tcplot::plot_axis3d_display_ticks(display, 0, 10, 5);
        const auto raw_ticks = tcplot::axes::nice_ticks(0, 10, 5);
        require(shifted.size() == raw_ticks.size(), "offset must not add tick positions");
        for (size_t index = 0; index < shifted.size(); ++index)
            require(shifted[index].value == raw_ticks[index] &&
                        shifted[index].label == tcplot::axes::format_tick(raw_ticks[index] - 40),
                    "display offset must preserve raw tick positions");

        require(tc_retained_chart3d_set_axis_tick_label(chart, radius_axis, 13.01, nullptr) &&
                    tc_retained_chart3d_set_axis_display_offset(chart, radius_axis, -40),
                "failed to remove label override");
        radii.assign(12, 0);
        require(tc_retained_chart3d_spherical_surface_set_radii(chart, surface, radii.data(), radii.size()),
                "failed to collapse display sphere");
        termin::RenderItemSnapshot collapsed;
        require(source.publish(collapsed, {}), "failed to publish collapsed display sphere");
        const auto* zero = find_plot_payload(collapsed, surface);
        const auto zero_ticks = tcplot::plot_axis3d_display_ticks(zero->frame.axis_display[radius_axis], 0, 0, 5);
        require(zero_ticks.size() == 1 && zero_ticks[0].value == 0 && zero_ticks[0].label == "<= -40 dBsm" &&
                    zero->frame.axis_display[radius_axis].tick_labels.size() == 1,
                "zero-radius colorbar must retain the floor label after data updates");
        tc_retained_chart3d_clear_data(chart);
        const auto old_grid = tc_retained_chart3d_grid_part(chart);
        require(tc_retained_chart3d_destroy_item(chart, old_grid), "failed to remove display test grid");
        const auto new_grid = tc_retained_chart3d_add_grid(chart, nullptr);
        require(tc_retained_chart3d_set_grid_part(chart, new_grid), "failed to replace display test grid");
        radii.assign(12, 13.01);
        surface = tc_retained_chart3d_add_spherical_surface(chart, azimuths, 4, polar, 3, radii.data(), 1, nullptr);
        require(tc_retained_chart3d_set_colorbar(chart, surface, "dBsm", nullptr), "failed to replace display colorbar");
        tc_retained_chart3d_clear_colorbar(chart);
        require(tc_retained_chart3d_set_colorbar(chart, surface, "dBsm", nullptr), "failed to restore display colorbar");
        termin::RenderItemSnapshot replacement;
        require(source.publish(replacement, {}), "failed to publish replacement display state");
        const auto* replaced = find_plot_payload(replacement, surface);
        require(replaced && replaced->frame.axis_display[radius_axis].offset == -40 &&
                    replaced->frame.axis_display[radius_axis].tick_labels.at(0) == "<= -40 dBsm",
                "display settings must survive all item and colorbar replacements");
        require(tc_retained_chart3d_clear_axis_tick_labels(chart, radius_axis), "failed to clear axis labels");
        termin::RenderItemSnapshot cleared;
        require(source.publish(cleared, {}) && find_plot_payload(cleared, surface)->frame.axis_display[radius_axis].tick_labels.empty(),
                "clearing labels must remove every override");
        spherical.reset();
        require(original->frame.axis_display[radius_axis].offset == -40 &&
                    replaced->frame.axis_display[radius_axis].tick_labels.at(0) == "<= -40 dBsm",
                "snapshots must retain display values after chart destruction");
    }

    void test_oriented_spherical_chart_cpu() {
        constexpr double pi = 3.14159265358979323846;
        const tc_spherical_coordinate_frame3d frame{
            0.0, -1.0, 0.0,
            1.0, 0.0, 0.0,
        };
        using ChartOwner = std::unique_ptr<tc_retained_chart3d, decltype(&tc_retained_chart3d_destroy)>;
        ChartOwner owner(
            tc_retained_chart3d_create_spherical_with_frame(nullptr, &frame),
            tc_retained_chart3d_destroy);
        require(owner != nullptr, "failed to create oriented spherical chart");

        const double longitudes[] = {0.0, pi / 2, pi};
        const double polar[] = {0.0, pi / 2, pi};
        const double radii[] = {2, 2, 2, 3, 4, 5, 2, 2, 2};
        const auto surface = tc_retained_chart3d_add_spherical_surface(
            owner.get(), longitudes, 3, polar, 3, radii, 0, nullptr);
        require(tc_retained_chart3d_item_is_valid(owner.get(), surface),
                "oriented spherical surface creation failed");

        termin::RenderItemSnapshot snapshot;
        auto& source = tcplot::plot_scene3d_render_item_source(*owner);
        require(source.publish(snapshot, {}), "oriented spherical snapshot publication failed");
        const auto* payload = find_plot_payload(snapshot, surface);
        require(payload && payload->item, "oriented spherical payload is missing");
        const auto& data = *payload->item;
        const auto point_is = [&](size_t index, double x, double y, double z) {
            return std::abs(data.x[index] - x) < 1e-12 && std::abs(data.y[index] - y) < 1e-12 &&
                   std::abs(data.z[index] - z) < 1e-12;
        };
        require(point_is(0, 0, -2, 0) && point_is(3, 3, 0, 0) && point_is(4, 0, 0, 4) &&
                    point_is(6, 0, 2, 0),
                "oriented spherical frame must rotate cardinal directions consistently");
        require(payload->frame.spherical_polar_axis == std::array<double, 3>{0.0, -1.0, 0.0} &&
                    payload->frame.spherical_zero_longitude == std::array<double, 3>{1.0, 0.0, 0.0} &&
                    payload->frame.spherical_quarter_longitude == std::array<double, 3>{0.0, 0.0, 1.0},
                "oriented spherical frame must be published for grid and label generation");

        const tc_spherical_coordinate_frame3d parallel{
            0.0, 1.0, 0.0,
            0.0, 2.0, 0.0,
        };
        ChartOwner rejected(
            tc_retained_chart3d_create_spherical_with_frame(nullptr, &parallel),
            tc_retained_chart3d_destroy);
        require(rejected == nullptr, "parallel spherical frame directions must be rejected");
    }

    void test_spherical_chart_cpu() {
        constexpr double pi = 3.14159265358979323846;
        const double azimuths[] = {0.0, pi / 2, pi, 3 * pi / 2};
        const double polar[] = {0.0, pi / 2, pi};
        const double radii[] = {2, 2, 2, 2, 3, 4, 5, 6, 2, 2, 2, 2};
        using ChartOwner = std::unique_ptr<tc_retained_chart3d, decltype(&tc_retained_chart3d_destroy)>;
        ChartOwner owner(tc_retained_chart3d_create_spherical(nullptr), tc_retained_chart3d_destroy);
        ChartOwner cartesian(tc_retained_chart3d_create(nullptr), tc_retained_chart3d_destroy);
        auto* chart = owner.get();
        require(chart && cartesian, "failed to create detached spherical test charts");
        tc_surface_item3d_style style{};
        style.color_r = style.color_g = style.color_b = style.color_a = 1.0f;
        style.colormap = TC_PLOT_COLORMAP3D_VIRIDIS;
        style.surface_grid_row_step = style.surface_grid_col_step = 1;
        style.surface_grid_width_px = 1.0f;
        const auto surface = tc_retained_chart3d_add_spherical_surface(
            chart, azimuths, 4, polar, 3, radii, 1, &style);
        require(tc_retained_chart3d_item_is_valid(chart, surface), "spherical surface creation failed");
        const auto grid = tc_retained_chart3d_grid_part(chart);
        termin::RenderItemSnapshot first;
        auto& source = tcplot::plot_scene3d_render_item_source(*chart);
        require(source.publish(first, {}), "spherical snapshot publication failed");
        const auto* payload = find_plot_payload(first, surface);
        const auto* grid_payload = find_plot_payload(first, grid);
        require(payload && payload->item && grid_payload && grid_payload->item &&
                    payload->item->spherical_surface && payload->frame.spherical_coordinates &&
                    grid_payload->frame.spherical_coordinates,
                "spherical mode must apply to both surface and coordinate grid");
        const auto& data = *payload->item;
        require(data.rows == 3 && data.columns == 5 && data.x.size() == 15,
                "closed azimuth must add one seam column");
        for (size_t row = 0; row < data.rows; ++row) {
            const size_t start = row * data.columns;
            const size_t end = start + data.columns - 1;
            require(data.x[start] == data.x[end] && data.y[start] == data.y[end] && data.z[start] == data.z[end],
                    "closed spherical seam must exactly match its first column");
        }
        const auto point_is = [&](size_t index, double x, double y, double z) {
            return std::abs(data.x[index] - x) < 1e-12 && std::abs(data.y[index] - y) < 1e-12 &&
                   std::abs(data.z[index] - z) < 1e-12;
        };
        require(point_is(0, 0, 0, 2) && point_is(5, 3, 0, 0) && point_is(6, 0, 4, 0) &&
                    point_is(7, -5, 0, 0) && point_is(8, 0, -6, 0) && point_is(10, 0, 0, -2),
                "spherical angles must map to the documented cardinal directions");
        require(data.draw_vertex_count == 24, "pole fans must contain exactly eight nondegenerate triangles");
        for (size_t vertex = 0; vertex < data.draw_vertex_count; vertex += 3) {
            const auto* a = &data.draw_vertices[vertex * 19];
            const auto* b = a + 19;
            const auto* c = b + 19;
            const double ux = b[0] - a[0], uy = b[1] - a[1], uz = b[2] - a[2];
            const double vx = c[0] - a[0], vy = c[1] - a[1], vz = c[2] - a[2];
            const double cx = uy * vz - uz * vy, cy = uz * vx - ux * vz, cz = ux * vy - uy * vx;
            require(cx * cx + cy * cy + cz * cz > 1e-10, "spherical draw stream contains a degenerate pole triangle");
        }
        const auto color_range = tcplot::plot_scene3d_surface_color_range(data, payload->frame);
        require(color_range[0] == 2 && color_range[1] == 6 && payload->frame.bounds_min[2] == -6 &&
                    payload->frame.bounds_max[2] == 6 && payload->frame.grid_radius == 6,
                "spherical color range must use radius while grid bounds include complete reference circles");
        bool curved_grid_segment = false;
        const auto& grid_data = *grid_payload->item;
        for (size_t vertex = 0; vertex + 1 < grid_data.draw_vertex_count; vertex += 2) {
            const auto* a = &grid_data.draw_vertices[vertex * 19];
            const auto* b = a + 19;
            int varying_axes = 0;
            for (size_t axis = 0; axis < 3; ++axis)
                varying_axes += std::abs(a[axis] - b[axis]) > 1e-6;
            curved_grid_segment |= varying_axes >= 2;
        }
        require(curved_grid_segment, "spherical grid must contain coordinate circles instead of only Cartesian lines");

        tc_orbit_camera3d_state camera{};
        tc_retained_chart3d_fit_camera(chart);
        require(tc_retained_chart3d_get_camera(chart, &camera) && camera.target_x == 0 && camera.target_y == 0 &&
                    camera.target_z == 0 && camera.distance > 6,
                "spherical camera fit must include the origin and full coordinate grid");
        camera.azimuth = 0.731;
        camera.elevation = 0.413;
        require(tc_retained_chart3d_set_camera(chart, &camera), "failed to set spherical camera");
        const auto before = snapshot(chart, surface);
        double updated[] = {4, 4, 4, 4, 6, 8, 10, 12, 4, 4, 4, 4};
        require(tc_retained_chart3d_spherical_surface_set_radii(chart, surface, updated, 12), "radius update failed");
        const auto after = snapshot(chart, surface);
        tc_orbit_camera3d_state after_camera{};
        require(tc_retained_chart3d_get_camera(chart, &after_camera) && after_camera.azimuth == camera.azimuth &&
                    after_camera.elevation == camera.elevation && after_camera.distance == camera.distance &&
                    after.geometry_revision != before.geometry_revision && after.style_revision == before.style_revision,
                "radius update must preserve handle, style and camera");
        termin::RenderItemSnapshot second;
        require(source.publish(second, {}), "updated spherical snapshot publication failed");
        const auto* updated_payload = find_plot_payload(second, surface);
        require(updated_payload && updated_payload->item != payload->item && updated_payload->item->radius_max == 12 &&
                    data.radius_max == 6 && data.x[5] == 3 && payload->frame.grid_radius == 6,
                "radius update must preserve published snapshot values");

        const auto invalid_update = [&](const double* values, size_t count) {
            require(!tc_retained_chart3d_spherical_surface_set_radii(chart, surface, values, count) &&
                        same_snapshot(after, snapshot(chart, surface)),
                    "invalid radius update must fail without mutating item revisions");
        };
        invalid_update(updated, 11);
        updated[4] = -1;
        invalid_update(updated, 12);
        updated[4] = std::numeric_limits<double>::quiet_NaN();
        invalid_update(updated, 12);
        updated[4] = std::numeric_limits<double>::infinity();
        invalid_update(updated, 12);
        updated[4] = 6;
        updated[0] = 3;
        invalid_update(updated, 12);
        const auto count = tc_retained_chart3d_item_count(chart);
        const double repeated_azimuths[] = {0, pi / 2, pi, 2 * pi};
        const double unordered_azimuths[] = {0, pi, pi / 2, 3 * pi / 2};
        const double invalid_polar[] = {-0.1, pi / 2, pi};
        for (const double* invalid_angles : {repeated_azimuths, unordered_azimuths}) {
            const auto rejected = tc_retained_chart3d_add_spherical_surface(
                chart, invalid_angles, 4, polar, 3, radii, 1, &style);
            require(!tc_retained_chart3d_item_is_valid(chart, rejected), "invalid azimuth axis was accepted");
        }
        const auto rejected_polar = tc_retained_chart3d_add_spherical_surface(
            chart, azimuths, 4, invalid_polar, 3, radii, 1, &style);
        require(!tc_retained_chart3d_item_is_valid(chart, rejected_polar) && tc_retained_chart3d_item_count(chart) == count,
                "invalid axes must not add retained items");
        const double xyz[] = {0, 1, 2, 3};
        const auto wrong_cartesian = tc_retained_chart3d_add_surface(chart, xyz, xyz, xyz, 2, 2, &style);
        const auto wrong_spherical = tc_retained_chart3d_add_spherical_surface(
            cartesian.get(), azimuths, 4, polar, 3, radii, 1, &style);
        require(!tc_retained_chart3d_item_is_valid(chart, wrong_cartesian) &&
                    !tc_retained_chart3d_item_is_valid(cartesian.get(), wrong_spherical) &&
                    !tc_retained_chart3d_surface_set_data(chart, surface, xyz, xyz, xyz, 2, 2),
                "surface APIs must not mix incompatible coordinate modes");
        const auto sector = tc_retained_chart3d_add_spherical_surface(
            chart, azimuths, 4, polar, 3, radii, 0, &style);
        termin::RenderItemSnapshot open_snapshot;
        require(source.publish(open_snapshot, {}), "open sector publication failed");
        const auto* sector_payload = find_plot_payload(open_snapshot, sector);
        require(sector_payload && sector_payload->item->columns == 4 && sector_payload->item->draw_vertex_count == 18,
                "open sectors must not gain an azimuth seam");
        const double collapsed_radii[12]{};
        require(tc_retained_chart3d_spherical_surface_set_radii(chart, surface, collapsed_radii, 12),
                "zero radii must remain valid spherical data");
        termin::RenderItemSnapshot collapsed_snapshot;
        require(source.publish(collapsed_snapshot, {}), "collapsed spherical publication failed");
        const auto* collapsed = find_plot_payload(collapsed_snapshot, surface);
        require(collapsed && collapsed->item->draw_vertex_count == 0 &&
                    tcplot::plot_scene3d_surface_color_range(*collapsed->item, collapsed->frame) ==
                        std::array<double, 2>{0, 0},
                "collapsed spherical surfaces must omit degenerate geometry and retain a finite color range");
        tc_retained_chart3d_clear_data(chart);
        require(tc_retained_chart3d_item_count(chart) == 1 && tc_retained_chart3d_item_is_valid(chart, grid),
                "clearing spherical data must preserve coordinate grid");
        owner.reset();
        require(data.x[5] == 3 && payload->frame.spherical_coordinates,
                "spherical snapshot must remain readable after chart destruction");
    }

    constexpr const char* kPlotSnapshotProbeType = "PlotScene3DSnapshotProbe";
    const termin::RenderItemSnapshot* g_probe_snapshot = nullptr;
    std::size_t g_probe_item_count = 0;
    bool g_probe_executed = false;

    class PlotSnapshotProbe final : public termin::CxxFramePass {
    public:
        PlotSnapshotProbe() {
            pass_name_set(kPlotSnapshotProbeType);
            link_to_type_registry(kPlotSnapshotProbeType);
        }

        void execute(termin::ExecuteContext& context) override {
            g_probe_snapshot = context.render_item_snapshot;
            g_probe_item_count = context.render_item_snapshot ? context.render_item_snapshot->item_count() : 0;
            g_probe_executed = true;
        }
    };

    void execute_snapshot_probe(const termin::RenderItemSnapshot& snapshot, tcplot::GpuHost& host) {
        if (!tc_pass_registry_has("CxxFramePass")) {
            termin::register_builtin_render_pass_types();
        }
        tc_pass_registry_unregister(kPlotSnapshotProbeType);
        auto descriptor =
            termin::FramePassTypeDescriptorBuilder::native<PlotSnapshotProbe>(kPlotSnapshotProbeType, "tcplot-test");
        require(descriptor.commit(), "failed to register plot snapshot probe");

        termin::RenderPipeline pipeline("plot-scene3d-source-test");
        require(pipeline.is_valid(), "failed to create plot snapshot probe pipeline");
        tc_pass* pass = tc_pass_registry_create(kPlotSnapshotProbeType);
        require(pass != nullptr, "failed to create plot snapshot probe pass");
        pipeline.add_pass(pass);

        termin::RenderTargetContext target;
        target.name = "PlotScene3DTarget";
        target.render_rect = {0, 0, 1, 1};
        termin::RenderExecution execution;
        execution.pipeline = &pipeline;
        execution.default_render_target = target.name;
        execution.targets.emplace(target.name,
                                  termin::RenderExecutionTarget{
                                      .context = &target,
                                      .render_items = &snapshot,
                                  });

        g_probe_snapshot = nullptr;
        g_probe_item_count = 0;
        g_probe_executed = false;
        termin::RenderEngine engine;
        engine.set_graphics_host(host.graphics());
        engine.execute_pipeline(execution);
        require(g_probe_executed, "generic render pipeline did not execute plot probe");
        require(g_probe_snapshot == &snapshot, "plot probe received another snapshot");
        require(g_probe_item_count == snapshot.item_count(), "plot probe observed the wrong item count");

        pipeline.destroy();
        tc_pass_registry_unregister(kPlotSnapshotProbeType);
    }

} // namespace

int main(int argc, char** argv) {
    try {
        const bool cpu_only = argc == 2 && std::string(argv[1]) == "--cpu-only";
        const bool spherical_d3d11 = argc == 2 && std::string(argv[1]) == "--spherical-d3d11";
        require(argc == 1 || cpu_only || spherical_d3d11,
                "usage: tcplot_retained_chart3d_test [--cpu-only|--spherical-d3d11]");
        test_termin_clip_canvas_projection();
        test_spherical_chart_cpu();
        test_oriented_spherical_chart_cpu();
        test_axis_display_cpu();
        test_background_color_cpu();
        if (cpu_only) {
            std::printf("retained Chart3D CPU geometry and lifecycle test passed\n");
            return 0;
        }

        if (!spherical_d3d11 && !tgfx::backend_is_compiled(tgfx::BackendType::Vulkan)) {
            std::printf("retained Chart3D test skipped: Vulkan unavailable\n");
            return 77;
        }

        const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
        TemporaryShaderRoot shader_root{
            std::filesystem::temp_directory_path() / ("tcplot-retained-chart3d-" + std::to_string(unique)),
        };
        std::filesystem::create_directories(shader_root.path / "cache");
        termin::tgfx2_set_shader_artifact_root(shader_root.path.string().c_str());
        termin::tgfx2_set_shader_cache_root((shader_root.path / "cache").string().c_str());
        termin::tgfx2_set_shader_dev_compile_enabled(true);

        if (spherical_d3d11) {
            require(tgfx::backend_is_compiled(tgfx::BackendType::D3D11), "D3D11 backend is unavailable");
            tcplot::GpuHost d3d_host(TCPLOT_TEST_FONT, tgfx::BackendType::D3D11);
            test_spherical_chart_d3d11(d3d_host);
            test_background_color_d3d11(d3d_host);
            test_retained_chart2d_colors_d3d11(d3d_host);
            std::printf("spherical Chart3D D3D11 pixels and retained updates test passed\n");
            return 0;
        }

        tcplot::GpuHost host(TCPLOT_TEST_FONT, tgfx::BackendType::Vulkan);
        const uint32_t supported_msaa_samples = test_texture_sample_support(host);
        tc_retained_chart3d* detached = tc_retained_chart3d_create(nullptr);
        require(detached != nullptr, "failed to create detached chart");
        const double line_x[] = {-1.0, 0.0, 1.0};
        const double line_y[] = {0.0, 1.0, 0.0};
        const double line_z[] = {0.0, 0.5, 1.0};
        tc_line_item3d_style line_style{
            0.2f,
            0.6f,
            1.0f,
            1.0f,
            2.0f,
        };
        const tc_plot_item3d_handle line =
            tc_retained_chart3d_add_line(detached, line_x, line_y, line_z, 3, &line_style);
        require(tc_retained_chart3d_item_is_valid(detached, line) != 0,
                "detached chart must accept CPU line data before GPU attachment");
        termin::RenderItemSnapshot detached_snapshot;
        require(tcplot::plot_scene3d_render_item_source(*detached).publish(detached_snapshot,
                                                                           {.debug_name = "DetachedPlotScene3D"}),
                "detached chart snapshot publication failed");
        const tc_render_item* line_render_item = find_render_item(detached_snapshot, line);
        require(detached_snapshot.item_count() == 2 && line_render_item &&
                    line_render_item->kind == tcplot::PLOT_RENDER_ITEM_KIND_LINE,
                "detached chart did not publish its retained line item");
        const auto* line_payload = tcplot::plot_scene3d_render_item_payload(*line_render_item);
        require(line_payload && line_payload->item && line_payload->item->draw_vertex_count == 4,
                "retained line draw stream must contain two line segments");
        require(tc_retained_chart3d_attach_gpu_host(detached, &host) != 0,
                "failed to attach detached chart to its GPU host");
        tc_retained_chart3d_destroy(detached);

        tc_retained_chart3d* chart = tc_retained_chart3d_create(&host);
        tc_retained_chart3d* other = tc_retained_chart3d_create(&host);
        require(chart != nullptr && other != nullptr, "failed to create charts");
        require(tc_retained_chart3d_set_msaa_samples(chart, 1) != 0,
                "failed to select single-sample rendering");
        require(tc_retained_chart3d_scene_id(chart) != tc_retained_chart3d_scene_id(other),
                "chart scene ids must be unique");
        require(tc_retained_chart3d_item_count(chart) == 1, "chart must create one default grid part");

        termin::RenderItemSnapshot empty_snapshot;
        const tc_plot_item3d_handle other_grid = tc_retained_chart3d_grid_part(other);
        require(tc_retained_chart3d_destroy_item(other, other_grid) != 0,
                "failed to remove the other chart default grid");
        termin::RenderItemSource& empty_source = tcplot::plot_scene3d_render_item_source(*other);
        require(empty_source.publish(empty_snapshot, {.debug_name = "EmptyPlotScene3D"}),
                "empty PlotScene3D source publication failed");
        require(empty_snapshot.valid() && empty_snapshot.item_count() == 0 &&
                    empty_snapshot.counters().source_traversals == 1 && empty_snapshot.counters().producers == 0,
                "empty PlotScene3D snapshot counters are invalid");

        const double x[] = {-1.0, 1.0, -1.0, 1.0};
        const double y[] = {-1.0, -1.0, 1.0, 1.0};
        const double z[] = {0.0, 0.5, 1.0, 0.25};
        tc_surface_item3d_style surface_style{
            1.0f,
            1.0f,
            1.0f,
            1.0f,
            TC_PLOT_COLORMAP3D_VIRIDIS,
            0,
            0,
            1,
            1,
            1,
            1.0f,
        };
        const tc_plot_item3d_handle surface = tc_retained_chart3d_add_surface(chart, x, y, z, 2, 2, &surface_style);
        require(tc_retained_chart3d_item_is_valid(chart, surface) != 0, "surface handle must be valid in its scene");
        require(tc_retained_chart3d_item_is_valid(other, surface) == 0, "cross-scene surface handle must be rejected");
        require(tc_retained_chart3d_surface_set_style(other, surface, &surface_style) == 0,
                "cross-scene surface mutation must be rejected");
        tc_colorbar3d_style colorbar_style{
            5,
            18.0f,
            0.62f,
            18.0f,
            8.0f,
            13.0f,
            0.8f,
            0.8f,
            0.8f,
            1.0f,
            0.42f,
            0.45f,
            0.52f,
            1.0f,
        };
        require(tc_retained_chart3d_set_colorbar(chart, surface, "height", &colorbar_style) != 0,
                "failed to enable the retained colorbar");
        require(tc_retained_chart3d_set_colorbar(other, surface, "height", &colorbar_style) == 0,
                "cross-scene colorbar source must be rejected");
        tc_colorbar3d_style invalid_colorbar_style = colorbar_style;
        invalid_colorbar_style.tick_count = 1;
        require(tc_retained_chart3d_set_colorbar(chart, surface, "height", &invalid_colorbar_style) == 0,
                "invalid colorbar style must be rejected");

        const double scatter_x[] = {-0.5, 0.0, 0.75};
        const double scatter_y[] = {0.5, -0.25, 0.25};
        const double scatter_z[] = {0.25, 0.75, 0.5};
        tc_scatter_item3d_style scatter_style{
            1.0f,
            0.25f,
            0.1f,
            1.0f,
            5.0f,
        };
        const tc_plot_item3d_handle scatter =
            tc_retained_chart3d_add_scatter(chart, scatter_x, scatter_y, scatter_z, 3, &scatter_style);
        require(tc_retained_chart3d_set_colorbar(chart, scatter, "invalid", &colorbar_style) == 0,
                "a colorbar must reject a non-surface source");

        termin::RenderItemSource& render_item_source = tcplot::plot_scene3d_render_item_source(*chart);
        termin::RenderViewState first_view;
        termin::RenderViewState second_view;
        termin::RenderItemSnapshot first_render_snapshot;
        termin::RenderItemSnapshot second_render_snapshot;
        require(render_item_source.publish(first_render_snapshot,
                                           {.view = &first_view, .debug_name = "PlotScene3D first view"}),
                "first PlotScene3D source publication failed");
        require(render_item_source.publish(second_render_snapshot,
                                           {.view = &second_view, .debug_name = "PlotScene3D second view"}),
                "second PlotScene3D source publication failed");
        require(first_render_snapshot.valid() && second_render_snapshot.valid() &&
                    first_render_snapshot.item_count() == 3 && second_render_snapshot.item_count() == 3,
                "multi-view PlotScene3D snapshots must remain independently valid");
        require(first_render_snapshot.counters().source_traversals == 1 &&
                    first_render_snapshot.counters().producers == 3,
                "PlotScene3D snapshot counters are invalid");

        const tc_render_item* surface_render_item = find_render_item(first_render_snapshot, surface);
        const tc_render_item* scatter_render_item = find_render_item(first_render_snapshot, scatter);
        const tc_render_item* grid_render_item =
            find_render_item(first_render_snapshot, tc_retained_chart3d_grid_part(chart));
        require(surface_render_item && scatter_render_item && grid_render_item,
                "PlotScene3D snapshot lost retained item identity");
        require(surface_render_item->kind == tcplot::PLOT_RENDER_ITEM_KIND_SURFACE &&
                    scatter_render_item->kind == tcplot::PLOT_RENDER_ITEM_KIND_SCATTER &&
                    grid_render_item->kind == tcplot::PLOT_RENDER_ITEM_KIND_GRID,
                "PlotScene3D snapshot published incorrect item kinds");
        for (const tc_render_item& item : first_render_snapshot.items()) {
            require(item.source.domain_id == tcplot::PLOT_RENDER_ITEM_SOURCE_DOMAIN &&
                        item.source.namespace_id == tc_retained_chart3d_scene_id(chart) &&
                        item.source.adapter_data != 0 && tcplot::plot_scene3d_render_item_payload(item) != nullptr,
                    "PlotScene3D item must retain an immutable adapter payload");
        }
        const tcplot::PlotScene3DRenderItemPayload* first_surface_payload =
            find_plot_payload(first_render_snapshot, surface);
        const tcplot::PlotScene3DRenderItemPayload* first_scatter_payload =
            find_plot_payload(first_render_snapshot, scatter);
        const tcplot::PlotScene3DRenderItemPayload* first_grid_payload =
            find_plot_payload(first_render_snapshot, tc_retained_chart3d_grid_part(chart));
        require(first_surface_payload && first_surface_payload->item && first_scatter_payload &&
                    first_scatter_payload->item && first_grid_payload && first_grid_payload->item,
                "PlotScene3D payload lookup failed");
        require(first_surface_payload->item->z == std::vector<double>(std::begin(z), std::end(z)) &&
                    first_surface_payload->item->surface_style.wireframe == 0 &&
                    first_surface_payload->item->draw_vertex_count == 6 &&
                    first_surface_payload->item->draw_vertices.size() == 6u * 19u &&
                    first_scatter_payload->item->x == std::vector<double>(std::begin(scatter_x), std::end(scatter_x)) &&
                    first_scatter_payload->item->draw_vertex_count == 18 &&
                    first_scatter_payload->item->draw_vertices.size() == 18u * 19u &&
                    first_grid_payload->item->draw_vertex_count >= 6 &&
                    first_grid_payload->item->draw_vertex_count % 2 == 0 &&
                    first_grid_payload->item->draw_vertices.size() ==
                        first_grid_payload->item->draw_vertex_count * 19u &&
                    first_surface_payload->frame.x_label == "x",
                "PlotScene3D payload lost item or chart values");
        const float expected_scatter_cross_size =
            static_cast<float>(std::sqrt(1.25 * 1.25 + 0.75 * 0.75 + 0.5 * 0.5) * 0.008 * (scatter_style.size / 4.0));
        const termin::LinearColor expected_scatter_color = termin::srgb_to_linear(
            termin::SrgbColor{scatter_style.color_r, scatter_style.color_g, scatter_style.color_b, scatter_style.color_a});
        require(std::abs(first_scatter_payload->item->draw_vertices[0] - (-0.5f - expected_scatter_cross_size)) <
                        1e-6f &&
                    first_scatter_payload->item->draw_vertices[1] == 0.5f &&
                    first_scatter_payload->item->draw_vertices[2] == 0.25f &&
                    std::abs(first_scatter_payload->item->draw_vertices[3] - expected_scatter_color.r) < 1e-6f &&
                    std::abs(first_scatter_payload->item->draw_vertices[4] - expected_scatter_color.g) < 1e-6f &&
                    std::abs(first_scatter_payload->item->draw_vertices[5] - expected_scatter_color.b) < 1e-6f,
                "PlotScene3D scatter stream lost geometry or linear color semantics");

        termin::RenderItemEncoderCapabilities surface_capabilities{};
        require(
            termin::get_render_item_encoder_capabilities(tcplot::PLOT_RENDER_ITEM_KIND_SURFACE, surface_capabilities) &&
                surface_capabilities.phase_mask == TC_PHASE_OPAQUE && surface_capabilities.requires_draw_context &&
                !surface_capabilities.consumes_common_resources,
            "PlotScene3D surface encoder capabilities are invalid");
        termin::RenderItemTaskPlanningContract surface_contract{};
        surface_contract.phase = TC_PHASE_OPAQUE;
        surface_contract.material_phase_policy = termin::RenderItemMaterialPhasePolicy::Forbidden;
        surface_contract.provided_input_mask =
            termin::render_item_task_input_bit(termin::RenderItemTaskInput::DrawContext);
        surface_contract.required_input_mask = surface_contract.provided_input_mask;
        surface_contract.debug_pass_name = "PlotScene3D surface planning test";
        termin::RenderItemTaskPlanningRequest surface_planning{};
        surface_planning.item = surface_render_item;
        surface_planning.item_index = 0;
        surface_planning.source_draw_index = 0;
        surface_planning.contract = &surface_contract;
        termin::RenderTaskList surface_tasks;
        const termin::RenderItemTaskPlanningResult surface_plan =
            termin::plan_render_item_task(surface_planning, surface_tasks);
        require(surface_plan.accepted() && surface_tasks.size() == 1 &&
                    !tc_shader_handle_is_invalid(surface_tasks.at(surface_plan.task_index).final_shader),
                "PlotScene3D surface task planning failed");

        termin::RenderItemEncoderCapabilities scatter_capabilities{};
        require(
            termin::get_render_item_encoder_capabilities(tcplot::PLOT_RENDER_ITEM_KIND_SCATTER, scatter_capabilities) &&
                scatter_capabilities.phase_mask == TC_PHASE_OPAQUE && scatter_capabilities.requires_draw_context &&
                !scatter_capabilities.consumes_common_resources,
            "PlotScene3D scatter encoder capabilities are invalid");
        termin::RenderItemTaskPlanningRequest scatter_planning = surface_planning;
        scatter_planning.item = scatter_render_item;
        scatter_planning.item_index = 1;
        scatter_planning.source_draw_index = 1;
        termin::RenderTaskList scatter_tasks;
        const termin::RenderItemTaskPlanningResult scatter_plan =
            termin::plan_render_item_task(scatter_planning, scatter_tasks);
        require(scatter_plan.accepted() && scatter_tasks.size() == 1 &&
                    !tc_shader_handle_is_invalid(scatter_tasks.at(scatter_plan.task_index).final_shader),
                "PlotScene3D scatter task planning failed");

        termin::RenderItemEncoderCapabilities grid_capabilities{};
        require(termin::get_render_item_encoder_capabilities(tcplot::PLOT_RENDER_ITEM_KIND_GRID, grid_capabilities) &&
                    grid_capabilities.phase_mask == TC_PHASE_OPAQUE && grid_capabilities.requires_draw_context &&
                    !grid_capabilities.consumes_common_resources,
                "PlotScene3D grid encoder capabilities are invalid");
        termin::RenderItemTaskPlanningRequest grid_planning = surface_planning;
        grid_planning.item = grid_render_item;
        grid_planning.item_index = 2;
        grid_planning.source_draw_index = 2;
        termin::RenderTaskList grid_tasks;
        const termin::RenderItemTaskPlanningResult grid_plan = termin::plan_render_item_task(grid_planning, grid_tasks);
        require(grid_plan.accepted() && grid_tasks.size() == 1 &&
                    !tc_shader_handle_is_invalid(grid_tasks.at(grid_plan.task_index).final_shader),
                "PlotScene3D grid task planning failed");

        auto malformed_surface_data = std::make_shared<tcplot::PlotScene3DItemRenderData>(*first_surface_payload->item);
        malformed_surface_data->draw_vertices.clear();
        malformed_surface_data->draw_vertex_count = 0;
        tcplot::PlotScene3DRenderItemPayload malformed_surface_payload = *first_surface_payload;
        malformed_surface_payload.item = std::move(malformed_surface_data);
        tc_render_item malformed_surface_item = *surface_render_item;
        malformed_surface_item.source.adapter_data = reinterpret_cast<uintptr_t>(&malformed_surface_payload);
        termin::RenderContext malformed_draw_context;
        malformed_draw_context.phase = TC_PHASE_OPAQUE;
        malformed_draw_context.viewport_width = 320;
        malformed_draw_context.viewport_height = 240;
        termin::RenderItemDrawSubmitRequest malformed_submission{};
        malformed_submission.shader_handle = surface_tasks.at(surface_plan.task_index).final_shader;
        malformed_submission.device = &host.device();
        malformed_submission.draw_context = &malformed_draw_context;
        malformed_submission.phase = TC_PHASE_OPAQUE;
        malformed_submission.debug_pass_name = "PlotScene3D malformed surface test";
        require(!termin::submit_render_item_draw(host.ctx(), malformed_surface_item, malformed_submission),
                "PlotScene3D surface encoder accepted a malformed draw stream");

        auto malformed_scatter_data = std::make_shared<tcplot::PlotScene3DItemRenderData>(*first_scatter_payload->item);
        malformed_scatter_data->draw_vertices.clear();
        malformed_scatter_data->draw_vertex_count = 0;
        tcplot::PlotScene3DRenderItemPayload malformed_scatter_payload = *first_scatter_payload;
        malformed_scatter_payload.item = std::move(malformed_scatter_data);
        tc_render_item malformed_scatter_item = *scatter_render_item;
        malformed_scatter_item.source.adapter_data = reinterpret_cast<uintptr_t>(&malformed_scatter_payload);
        malformed_submission.shader_handle = scatter_tasks.at(scatter_plan.task_index).final_shader;
        malformed_submission.debug_pass_name = "PlotScene3D malformed scatter test";
        require(!termin::submit_render_item_draw(host.ctx(), malformed_scatter_item, malformed_submission),
                "PlotScene3D scatter encoder accepted a malformed draw stream");

        auto malformed_grid_data = std::make_shared<tcplot::PlotScene3DItemRenderData>(*first_grid_payload->item);
        malformed_grid_data->draw_vertices.clear();
        malformed_grid_data->draw_vertex_count = 0;
        tcplot::PlotScene3DRenderItemPayload malformed_grid_payload = *first_grid_payload;
        malformed_grid_payload.item = std::move(malformed_grid_data);
        tc_render_item malformed_grid_item = *grid_render_item;
        malformed_grid_item.source.adapter_data = reinterpret_cast<uintptr_t>(&malformed_grid_payload);
        malformed_submission.shader_handle = grid_tasks.at(grid_plan.task_index).final_shader;
        malformed_submission.debug_pass_name = "PlotScene3D malformed grid test";
        require(!termin::submit_render_item_draw(host.ctx(), malformed_grid_item, malformed_submission),
                "PlotScene3D grid encoder accepted a malformed draw stream");

        termin::RenderItemTaskPlanningContract unsupported_surface_contract = surface_contract;
        unsupported_surface_contract.phase = TC_PHASE_TRANSPARENT;
        surface_planning.contract = &unsupported_surface_contract;
        termin::RenderTaskList unsupported_surface_tasks;
        require(termin::plan_render_item_task(surface_planning, unsupported_surface_tasks).rejection ==
                        termin::RenderItemTaskRejection::PassOutputUnsupported &&
                    unsupported_surface_tasks.empty(),
                "PlotScene3D surface planner accepted an unsupported output");

        termin::RenderItemTaskPlanningContract missing_input_contract = surface_contract;
        missing_input_contract.provided_input_mask = 0;
        surface_planning.contract = &missing_input_contract;
        termin::RenderTaskList missing_input_tasks;
        require(termin::plan_render_item_task(surface_planning, missing_input_tasks).rejection ==
                        termin::RenderItemTaskRejection::RequiredInputMissing &&
                    missing_input_tasks.empty(),
                "PlotScene3D surface planner accepted missing draw context input");
        surface_planning.contract = &surface_contract;
        surface_planning.material_phase = reinterpret_cast<tc_material_phase*>(uintptr_t{1});
        termin::RenderTaskList material_surface_tasks;
        require(termin::plan_render_item_task(surface_planning, material_surface_tasks).rejection ==
                        termin::RenderItemTaskRejection::MaterialPhaseForbidden &&
                    material_surface_tasks.empty(),
                "PlotScene3D surface planner accepted a material phase");
        surface_planning.material_phase = nullptr;

        scatter_planning.contract = &unsupported_surface_contract;
        termin::RenderTaskList unsupported_scatter_tasks;
        require(termin::plan_render_item_task(scatter_planning, unsupported_scatter_tasks).rejection ==
                        termin::RenderItemTaskRejection::PassOutputUnsupported &&
                    unsupported_scatter_tasks.empty(),
                "PlotScene3D scatter planner accepted an unsupported output");
        scatter_planning.contract = &missing_input_contract;
        termin::RenderTaskList missing_scatter_input_tasks;
        require(termin::plan_render_item_task(scatter_planning, missing_scatter_input_tasks).rejection ==
                        termin::RenderItemTaskRejection::RequiredInputMissing &&
                    missing_scatter_input_tasks.empty(),
                "PlotScene3D scatter planner accepted missing draw context input");
        scatter_planning.contract = &surface_contract;
        scatter_planning.material_phase = reinterpret_cast<tc_material_phase*>(uintptr_t{1});
        termin::RenderTaskList material_scatter_tasks;
        require(termin::plan_render_item_task(scatter_planning, material_scatter_tasks).rejection ==
                        termin::RenderItemTaskRejection::MaterialPhaseForbidden &&
                    material_scatter_tasks.empty(),
                "PlotScene3D scatter planner accepted a material phase");
        scatter_planning.material_phase = nullptr;

        const tc_plot_item3d_handle isolated_scatter =
            tc_retained_chart3d_add_scatter(other, scatter_x, scatter_y, scatter_z, 3, &scatter_style);
        const uint32_t isolated_scatter_texture = tc_retained_chart3d_render(other, 320, 240);
        require(isolated_scatter_texture != 0 && snapshot(other, isolated_scatter).gpu_revision != 0 &&
                    count_non_clear_pixels(host, isolated_scatter_texture, 320, 240) > 5,
                "PlotScene3D scatter encoder produced no visible output");
        const tcplot::PlotScene3DRenderItemPayload* second_surface_payload =
            find_plot_payload(second_render_snapshot, surface);
        require(second_surface_payload && second_surface_payload->item == first_surface_payload->item,
                "unchanged item data must be shared between snapshots");
        execute_snapshot_probe(first_render_snapshot, host);

        const double changed_z[] = {0.25, 0.75, 1.25, 0.5};
        require(tc_retained_chart3d_surface_set_data(chart, surface, x, y, changed_z, 2, 2) != 0,
                "failed to update surface data for snapshot isolation");
        termin::RenderItemSnapshot geometry_changed_snapshot;
        require(render_item_source.publish(geometry_changed_snapshot, {}),
                "PlotScene3D publication after geometry mutation failed");
        const tcplot::PlotScene3DRenderItemPayload* changed_surface_payload =
            find_plot_payload(geometry_changed_snapshot, surface);
        const tcplot::PlotScene3DRenderItemPayload* changed_grid_payload =
            find_plot_payload(geometry_changed_snapshot, tc_retained_chart3d_grid_part(chart));
        require(changed_surface_payload && changed_surface_payload->item &&
                    changed_surface_payload->item->z ==
                        std::vector<double>(std::begin(changed_z), std::end(changed_z)) &&
                    changed_surface_payload->geometry_revision == first_surface_payload->geometry_revision + 1 &&
                    changed_surface_payload->item != first_surface_payload->item,
                "geometry mutation must publish a new immutable item payload");
        require(changed_grid_payload && changed_grid_payload->item &&
                    changed_grid_payload->item != first_grid_payload->item &&
                    changed_grid_payload->geometry_revision == first_grid_payload->geometry_revision + 1 &&
                    changed_grid_payload->frame.bounds_max[2] == 1.25 && first_grid_payload->frame.bounds_max[2] == 1.0,
                "chart bounds mutation must replace the immutable grid stream");
        require(first_surface_payload->item->z == std::vector<double>(std::begin(z), std::end(z)) &&
                    find_plot_payload(geometry_changed_snapshot, scatter)->item == first_scatter_payload->item,
                "geometry mutation changed an older or unrelated snapshot payload");

        const double changed_scatter_x[] = {-1.0, 0.0, 1.0};
        const double changed_scatter_y[] = {0.0, 0.75, -0.5};
        const double changed_scatter_z[] = {0.25, 1.0, 0.5};
        require(tc_retained_chart3d_scatter_set_data(
                    chart, scatter, changed_scatter_x, changed_scatter_y, changed_scatter_z, 3) != 0,
                "failed to update scatter data for snapshot isolation");
        termin::RenderItemSnapshot scatter_geometry_snapshot;
        require(render_item_source.publish(scatter_geometry_snapshot, {}),
                "PlotScene3D publication after scatter mutation failed");
        const tcplot::PlotScene3DRenderItemPayload* changed_scatter_payload =
            find_plot_payload(scatter_geometry_snapshot, scatter);
        require(changed_scatter_payload && changed_scatter_payload->item &&
                    changed_scatter_payload->item->x ==
                        std::vector<double>(std::begin(changed_scatter_x), std::end(changed_scatter_x)) &&
                    changed_scatter_payload->item->draw_vertex_count == 18 &&
                    changed_scatter_payload->geometry_revision == first_scatter_payload->geometry_revision + 1 &&
                    changed_scatter_payload->item != first_scatter_payload->item &&
                    find_plot_payload(scatter_geometry_snapshot, surface)->item == changed_surface_payload->item,
                "scatter mutation must replace only its immutable item payload");
        require(first_scatter_payload->item->x == std::vector<double>(std::begin(scatter_x), std::end(scatter_x)),
                "scatter mutation altered an older snapshot payload");

        const auto surface_initial = snapshot(chart, surface);
        const auto scatter_initial = snapshot(chart, scatter);
        require(tc_retained_chart3d_surface_set_style(chart, surface, &surface_style) != 0,
                "identical surface style must be accepted");
        require(same_snapshot(surface_initial, snapshot(chart, surface)), "identical style must be a no-op");

        tc_orbit_camera3d_state camera{};
        require(tc_retained_chart3d_get_camera(chart, &camera) != 0, "failed to read camera");
        camera.azimuth += 0.25f;
        require(tc_retained_chart3d_set_camera(chart, &camera) != 0, "failed to update camera");
        require(tc_retained_chart3d_set_surface_shading(chart, 1, 0.4f) != 0 &&
                    tc_retained_chart3d_set_surface_shading(chart, 1, std::numeric_limits<float>::quiet_NaN()) == 0,
                "shading validation must be observable by callers");
        require(tc_retained_chart3d_set_light_direction(chart, 0, 0, 0) == 0 &&
                    tc_retained_chart3d_set_axis_scale(chart, 1, -1, 1) == 0,
                "invalid chart policy values must be rejected");
        require(same_snapshot(surface_initial, snapshot(chart, surface)) &&
                    same_snapshot(scatter_initial, snapshot(chart, scatter)),
                "camera changes must not invalidate item state");
        termin::RenderItemSnapshot chart_state_snapshot;
        require(render_item_source.publish(chart_state_snapshot, {}),
                "PlotScene3D publication after chart-state mutation failed");
        const tcplot::PlotScene3DRenderItemPayload* chart_state_payload =
            find_plot_payload(chart_state_snapshot, surface);
        require(chart_state_payload && chart_state_payload->frame.camera.azimuth == camera.azimuth &&
                    chart_state_payload->frame.surface_shading_strength == 0.4f &&
                    first_surface_payload->frame.camera.azimuth != camera.azimuth,
                "chart-state mutation must publish values without altering older snapshots");

        tgfx::set_builtin_shader_read_callback([](std::string_view path, std::string& contents) {
            if (!path.ends_with("termin-engine-tcplot-3d.slang")) {
                return false;
            }
            contents = "invalid PlotScene3D shader source";
            return true;
        });
        const tc_shader_handle plot_shader = tc_shader_find("termin-engine-tcplot-3d");
        if (tc_shader_is_valid(plot_shader)) {
            require(tc_shader_destroy(plot_shader), "failed to invalidate the plot shader for failure testing");
        }
        require(tc_retained_chart3d_render(chart, 320, 240) == 0,
                "shader preparation failure must be visible through the public render result");
        require(snapshot(chart, surface).gpu_revision == 0 && snapshot(chart, scatter).gpu_revision == 0 &&
                    snapshot(chart, tc_retained_chart3d_grid_part(chart)).gpu_revision == 0,
                "failed retained render must leave every item dirty");

        tgfx::set_builtin_shader_read_callback({});
        const tc_shader_handle failed_plot_shader = tc_shader_find("termin-engine-tcplot-3d");
        if (tc_shader_is_valid(failed_plot_shader)) {
            require(tc_shader_destroy(failed_plot_shader), "failed to remove the rejected plot shader");
        }
        const uint32_t first_render_texture = tc_retained_chart3d_render(chart, 320, 240);
        require(first_render_texture != 0, "initial retained render failed");
        tc_orbit_camera3d_state pan_before{};
        require(tc_retained_chart3d_get_camera(chart, &pan_before) != 0, "failed to read pre-pan camera");
        const termin::Vec3 grabbed_target{pan_before.target_x, pan_before.target_y, pan_before.target_z};
        require(tc_retained_chart3d_pointer_down(chart, 160.0f, 120.0f, 2) != 0,
                "failed to begin retained Chart3D pan");
        tc_retained_chart3d_pointer_move(chart, 220.0f, 155.0f);
        tc_retained_chart3d_pointer_up(chart, 220.0f, 155.0f, 2);
        tc_orbit_camera3d_state pan_after{};
        require(tc_retained_chart3d_get_camera(chart, &pan_after) != 0, "failed to read post-pan camera");
        const termin::Vec2 projected_grab = project_camera_point(pan_after, grabbed_target, 320.0, 240.0);
        require(std::abs(projected_grab.x - 220.0f) < 0.02f && std::abs(projected_grab.y - 155.0f) < 0.02f,
                "retained Chart3D pan did not preserve the grabbed point");
        tgfx::TextureHandle first_render_handle{};
        first_render_handle.id = first_render_texture;
        require(host.device().texture_desc(first_render_handle).sample_count == 1,
                "RetainedChart3D must publish a resolved single-sample texture");
        const std::size_t labeled_pixel_count = count_non_clear_pixels(host, first_render_texture, 320, 240);
        require(labeled_pixel_count > 100, "PlotScene3D retained encoders produced no visible output");
        const auto surface_rendered = snapshot(chart, surface);
        const auto scatter_rendered = snapshot(chart, scatter);
        const auto grid_rendered = snapshot(chart, tc_retained_chart3d_grid_part(chart));
        require(surface_rendered.gpu_revision != 0 && scatter_rendered.gpu_revision != 0 &&
                    grid_rendered.gpu_revision != 0,
                "render must synchronize item GPU revisions");

        require(tc_retained_chart3d_set_msaa_samples(chart, static_cast<int>(supported_msaa_samples)) != 0 &&
                    tc_retained_chart3d_set_msaa_samples(chart, 3) == 0,
                "retained Chart3D MSAA validation failed");
        const uint32_t multisample_render_texture = tc_retained_chart3d_render(chart, 320, 240);
        tgfx::TextureHandle multisample_render_handle{};
        multisample_render_handle.id = multisample_render_texture;
        const std::size_t multisample_labeled_pixel_count =
            count_non_clear_pixels(host, multisample_render_texture, 320, 240);
        const std::vector<float> visible_labels_pixels =
            read_pixels(host, multisample_render_texture, 320, 240);
        require(multisample_render_texture != 0 &&
                    host.device().texture_desc(multisample_render_handle).sample_count == 1 &&
                    multisample_labeled_pixel_count > 100,
                "MSAA Chart3D render was not resolved to a visible single-sample output");

        tc_grid_item3d_style grid_style{};
        const tc_plot_item3d_handle grid = tc_retained_chart3d_grid_part(chart);
        require(tc_retained_chart3d_grid_get_style(chart, grid, &grid_style) != 0 && grid_style.labels_visible != 0,
                "failed to read the retained grid style");
        grid_style.labels_visible = 0;
        require(tc_retained_chart3d_grid_set_style(chart, grid, &grid_style) != 0,
                "failed to disable retained grid labels");
        termin::RenderItemSnapshot hidden_grid_snapshot;
        require(render_item_source.publish(hidden_grid_snapshot, {}),
                "PlotScene3D publication after grid style mutation failed");
        const tcplot::PlotScene3DRenderItemPayload* hidden_grid_payload = find_plot_payload(hidden_grid_snapshot, grid);
        require(hidden_grid_payload && hidden_grid_payload->item &&
                    hidden_grid_payload->item->grid_style.labels_visible == 0 &&
                    hidden_grid_payload->style_revision == first_grid_payload->style_revision + 1 &&
                    first_grid_payload->item->grid_style.labels_visible != 0,
                "grid style mutation altered an older snapshot payload");
        const uint32_t hidden_labels_texture = tc_retained_chart3d_render(chart, 320, 240);
        const std::vector<float> hidden_labels_pixels = read_pixels(host, hidden_labels_texture, 320, 240);
        require(hidden_labels_texture != 0 &&
                    count_changed_pixels(visible_labels_pixels, hidden_labels_pixels) > 10,
                "chart-owned grid labels produced no visible annotation pixels");
        grid_style.labels_visible = 1;
        require(tc_retained_chart3d_grid_set_style(chart, grid, &grid_style) != 0 &&
                    tc_retained_chart3d_render(chart, 320, 240) != 0,
                "failed to restore retained grid labels");

        surface_style.wireframe = 1;
        require(tc_retained_chart3d_surface_set_style(chart, surface, &surface_style) != 0,
                "failed to update surface style");
        const auto surface_invalidated = snapshot(chart, surface);
        require(surface_invalidated.geometry_revision == surface_rendered.geometry_revision &&
                    surface_invalidated.style_revision == surface_rendered.style_revision + 1 &&
                    surface_invalidated.gpu_revision == 0,
                "style change must preserve semantic geometry and invalidate GPU state");
        termin::RenderItemSnapshot style_changed_snapshot;
        require(render_item_source.publish(style_changed_snapshot, {}),
                "PlotScene3D publication after style mutation failed");
        const tcplot::PlotScene3DRenderItemPayload* styled_surface_payload =
            find_plot_payload(style_changed_snapshot, surface);
        require(styled_surface_payload && styled_surface_payload->item &&
                    styled_surface_payload->item->surface_style.wireframe == 1 &&
                    styled_surface_payload->item->draw_vertex_count == 12 &&
                    first_surface_payload->item->draw_vertex_count == 6 &&
                    first_surface_payload->item->surface_style.wireframe == 0 &&
                    styled_surface_payload->style_revision == first_surface_payload->style_revision + 1,
                "style mutation must not alter an older snapshot payload");
        require(same_snapshot(scatter_rendered, snapshot(chart, scatter)),
                "surface style must not invalidate unrelated scatter");

        scatter_style.size = 8.0f;
        scatter_style.color_g = 0.75f;
        require(tc_retained_chart3d_scatter_set_style(chart, scatter, &scatter_style) != 0,
                "failed to update scatter style");
        const auto scatter_invalidated = snapshot(chart, scatter);
        require(scatter_invalidated.geometry_revision == scatter_rendered.geometry_revision &&
                    scatter_invalidated.style_revision == scatter_rendered.style_revision + 1 &&
                    scatter_invalidated.gpu_revision == 0 &&
                    same_snapshot(surface_invalidated, snapshot(chart, surface)),
                "scatter style change must invalidate only scatter GPU state");
        termin::RenderItemSnapshot scatter_style_snapshot;
        require(render_item_source.publish(scatter_style_snapshot, {}),
                "PlotScene3D publication after scatter style mutation failed");
        const tcplot::PlotScene3DRenderItemPayload* styled_scatter_payload =
            find_plot_payload(scatter_style_snapshot, scatter);
        require(styled_scatter_payload && styled_scatter_payload->item &&
                    styled_scatter_payload->item->scatter_style.size == 8.0f &&
                    styled_scatter_payload->item->draw_vertex_count == 18 &&
                    styled_scatter_payload->item != changed_scatter_payload->item &&
                    changed_scatter_payload->item->scatter_style.size == 5.0f &&
                    styled_scatter_payload->style_revision == changed_scatter_payload->style_revision + 1,
                "scatter style mutation must replace its immutable draw stream");

        tc_scatter_item3d_style invalid_scatter_style = scatter_style;
        invalid_scatter_style.size = -1.0f;
        require(tc_retained_chart3d_scatter_set_style(chart, scatter, &invalid_scatter_style) == 0 &&
                    same_snapshot(scatter_invalidated, snapshot(chart, scatter)),
                "rejected scatter style must not mutate item revisions");

        tc_surface_item3d_style invalid_style = surface_style;
        invalid_style.surface_grid_width_px = -1.0f;
        require(tc_retained_chart3d_surface_set_style(chart, surface, &invalid_style) == 0,
                "invalid surface style must be rejected");
        require(same_snapshot(surface_invalidated, snapshot(chart, surface)),
                "rejected style must not mutate item revisions");

        require(tc_retained_chart3d_render(chart, 512, 256) != 0, "resized retained render failed");
        require(snapshot(chart, surface).gpu_revision != 0, "style update must be synchronized by render");
        const auto scatter_after_style_render = snapshot(chart, scatter);
        require(scatter_after_style_render.geometry_revision == scatter_invalidated.geometry_revision &&
                    scatter_after_style_render.style_revision == scatter_invalidated.style_revision &&
                    scatter_after_style_render.gpu_revision != 0,
                "resized render must submit scatter without rebuilding its stream");

        tc_retained_chart3d_release_gpu(chart);
        require(snapshot(chart, surface).gpu_revision == 0 && snapshot(chart, scatter).gpu_revision == 0 &&
                    snapshot(chart, tc_retained_chart3d_grid_part(chart)).gpu_revision == 0,
                "GPU release must invalidate item GPU revisions");
        require(tc_retained_chart3d_render(chart, 512, 256) != 0, "render after GPU release failed");
        require(snapshot(chart, surface).gpu_revision != 0 && snapshot(chart, scatter).gpu_revision != 0 &&
                    snapshot(chart, tc_retained_chart3d_grid_part(chart)).gpu_revision != 0,
                "render after GPU release must rebuild item resources");

        require(tc_retained_chart3d_destroy_item(chart, scatter) != 0, "failed to destroy scatter");
        require(tc_retained_chart3d_item_is_valid(chart, scatter) == 0, "destroyed handle must be stale");
        termin::RenderItemSnapshot after_destroy_snapshot;
        require(render_item_source.publish(after_destroy_snapshot, {}), "PlotScene3D publication after destroy failed");
        require(find_render_item(after_destroy_snapshot, scatter) == nullptr,
                "destroyed item must disappear from PlotScene3D snapshots");
        const tc_plot_item3d_handle replacement =
            tc_retained_chart3d_add_scatter(chart, scatter_x, scatter_y, scatter_z, 3, &scatter_style);
        require(replacement.index == scatter.index && replacement.generation != scatter.generation,
                "reused slot must advance its generation");
        termin::RenderItemSnapshot replacement_snapshot;
        require(render_item_source.publish(replacement_snapshot, {}),
                "PlotScene3D publication after slot reuse failed");
        require(find_render_item(replacement_snapshot, scatter) == nullptr &&
                    find_render_item(replacement_snapshot, replacement) != nullptr,
                "PlotScene3D snapshot must publish only the live slot generation");
        const tcplot::PlotScene3DRenderItemPayload* replacement_payload =
            find_plot_payload(replacement_snapshot, replacement);
        require(replacement_payload && replacement_payload->item &&
                    replacement_payload->item != first_scatter_payload->item,
                "reused slot must not recycle the previous generation's payload");
        require(tc_retained_chart3d_destroy_item(chart, scatter) == 0,
                "stale handle must not destroy replacement item");

        const tc_plot_item3d_handle retained_grid = tc_retained_chart3d_grid_part(chart);
        tc_retained_chart3d_clear_data(chart);
        require(tc_retained_chart3d_item_count(chart) == 1 &&
                    tc_retained_chart3d_item_is_valid(chart, retained_grid) != 0 &&
                    tc_retained_chart3d_item_is_valid(chart, surface) == 0 &&
                    tc_retained_chart3d_item_is_valid(chart, replacement) == 0,
                "clear_data must preserve only the configured grid");

        const tc_plot_item3d_handle reattached_surface =
            tc_retained_chart3d_add_surface(chart, x, y, z, 2, 2, &surface_style);

        tc_retained_chart3d_detach_gpu_host(chart);
        require(snapshot(chart, reattached_surface).gpu_revision == 0,
                "GPU-host detach must preserve CPU items and invalidate their GPU revisions");
        require(tc_retained_chart3d_attach_gpu_host(chart, &host) != 0 &&
                    tc_retained_chart3d_render(chart, 320, 240) != 0,
                "detached retained chart did not reattach and render");

        tc_retained_chart3d_destroy(other);
        tc_retained_chart3d_destroy(chart);
        require(first_surface_payload->item->z == std::vector<double>(std::begin(z), std::end(z)) &&
                    first_surface_payload->frame.x_label == "x" &&
                    first_surface_payload->item->surface_style.wireframe == 0,
                "snapshot-owned PlotScene3D payload did not survive chart destruction");
        std::printf("retained Chart3D lifecycle and invalidation test passed\n");
        return 0;
    } catch (const std::exception& error) {
        std::fprintf(stderr, "retained Chart3D test failed: %s\n", error.what());
        return 1;
    }
}
