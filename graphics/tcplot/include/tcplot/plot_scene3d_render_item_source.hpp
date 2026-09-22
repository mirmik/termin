#pragma once

#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <map>
#include <memory>
#include <string>
#include <vector>

#include <termin/render/render_item_source.hpp>

#include "tcplot/retained_chart3d.h"
#include "tcplot/axes.hpp"
#include "tcplot/tcplot_api.h"

namespace tcplot {

    // Adapter-owned values outside the built-in render-item kind range. Concrete
    // draw encoders are intentionally a separate migration step; these values
    // already make retained chart snapshots unambiguous to generic passes.
    inline constexpr uint32_t PLOT_RENDER_ITEM_KIND_SURFACE = 0x54500001u;
    inline constexpr uint32_t PLOT_RENDER_ITEM_KIND_SCATTER = 0x54500002u;
    inline constexpr uint32_t PLOT_RENDER_ITEM_KIND_GRID = 0x54500003u;
    inline constexpr uint32_t PLOT_RENDER_ITEM_KIND_LINE = 0x54500004u;

    // ASCII "tcplot3d" encoded as a stable adapter-owned 64-bit domain id.
    inline constexpr uint64_t PLOT_RENDER_ITEM_SOURCE_DOMAIN = UINT64_C(0x7463706c6f743364);

    // Immutable CPU draw data shared by snapshots until its retained inputs
    // change. Surface/scatter inputs are item-local; grid geometry also depends on
    // chart bounds and receives a geometry revision when those bounds may change.
    // A mutation installs a new value instead of modifying published data.
    struct PlotScene3DItemRenderData {
        tc_plot_item3d_kind kind = TC_PLOT_ITEM3D_INVALID;
        std::vector<double> x;
        std::vector<double> y;
        std::vector<double> z;
        uint32_t rows = 0;
        uint32_t columns = 0;
        bool spherical_surface = false;
        double radius_min = 0.0;
        double radius_max = 1.0;
        tc_surface_item3d_style surface_style{};
        tc_scatter_item3d_style scatter_style{};
        tc_line_item3d_style line_style{};
        tc_grid_item3d_style grid_style{};

        // Encoder-ready immutable stream. The layout is the builtin tcplot3d
        // vertex ABI (19 floats per vertex); vertices are already expanded in draw
        // order so submission can use the shared transient vertex ring without
        // owning device-lifetime buffers in a snapshot.
        std::vector<float> draw_vertices;
        uint32_t draw_vertex_count = 0;
    };

    struct PlotAxis3DDisplay {
        double offset = 0.0;
        std::map<double, std::string> tick_labels;
    };

    struct PlotAxis3DDisplayTick {
        double value;
        std::string label;
    };

    inline std::string plot_axis3d_tick_label(const PlotAxis3DDisplay& display, double value) {
        const auto label = display.tick_labels.find(value);
        return label == display.tick_labels.end() ? axes::format_tick(value + display.offset) : label->second;
    }

    // One pure source of raw positions and displayed text for drawing, text
    // measurement and CPU tests. Overrides outside this domain are irrelevant.
    inline std::vector<PlotAxis3DDisplayTick> plot_axis3d_display_ticks(
        const PlotAxis3DDisplay& display, double lo, double hi, int count) {
        if (!std::isfinite(lo) || !std::isfinite(hi) || hi < lo)
            return {};
        auto values = axes::nice_ticks(lo, hi, count);
        for (const auto& [value, label] : display.tick_labels) {
            if (value < lo || value > hi)
                continue;
            const double tolerance = 16.0 * std::numeric_limits<double>::epsilon() *
                std::max({std::abs(lo), std::abs(hi), std::abs(value)});
            const auto existing = std::find_if(values.begin(), values.end(), [=](double tick) {
                return std::abs(tick - value) <= tolerance;
            });
            if (existing == values.end())
                values.push_back(value);
            else
                *existing = value;
        }
        std::sort(values.begin(), values.end());
        std::vector<PlotAxis3DDisplayTick> ticks;
        ticks.reserve(values.size());
        for (double value : values)
            ticks.push_back({value, plot_axis3d_tick_label(display, value)});
        return ticks;
    }

    // Chart-wide values captured independently for every publication. They are
    // intentionally values rather than a retained-chart pointer so an encoder can
    // consume a snapshot after later chart mutations or destruction.
    struct PlotScene3DFrameRenderState {
        bool spherical_coordinates = false;
        double grid_radius = 1.0;
        std::array<double, 3> spherical_polar_axis{0.0, 0.0, 1.0};
        std::array<double, 3> spherical_zero_longitude{1.0, 0.0, 0.0};
        std::array<double, 3> spherical_quarter_longitude{0.0, 1.0, 0.0};
        tc_orbit_camera3d_state camera{};
        std::array<float, 3> axis_scale{1.0f, 1.0f, 1.0f};
        std::array<PlotAxis3DDisplay, 4> axis_display;
        bool surface_shading = true;
        float surface_shading_strength = 0.38f;
        std::array<float, 3> surface_light_direction{-0.4f, -0.6f, 0.7f};
        std::array<double, 3> bounds_min{0.0, 0.0, 0.0};
        std::array<double, 3> bounds_max{1.0, 1.0, 1.0};
        std::string x_label = "x";
        std::string y_label = "y";
        std::string z_label = "z";
    };

    inline std::array<double, 3> transform_spherical_direction(
        const PlotScene3DFrameRenderState& frame,
        const std::array<double, 3>& local) {
        return {
            frame.spherical_zero_longitude[0] * local[0] +
                frame.spherical_quarter_longitude[0] * local[1] +
                frame.spherical_polar_axis[0] * local[2],
            frame.spherical_zero_longitude[1] * local[0] +
                frame.spherical_quarter_longitude[1] * local[1] +
                frame.spherical_polar_axis[1] * local[2],
            frame.spherical_zero_longitude[2] * local[0] +
                frame.spherical_quarter_longitude[2] * local[1] +
                frame.spherical_polar_axis[2] * local[2],
        };
    }

    // Both the shader and colorbar consume this true scalar range. Equal bounds
    // map to the palette midpoint and the colorbar displays a single value.
    inline std::array<double, 2> plot_scene3d_surface_color_range(
        const PlotScene3DItemRenderData& item, const PlotScene3DFrameRenderState& frame) {
        if (!item.spherical_surface)
            return {frame.bounds_min[2], frame.bounds_max[2]};
        return {item.radius_min, item.radius_max};
    }

    struct PlotScene3DRenderItemPayload {
        std::shared_ptr<const PlotScene3DItemRenderData> item;
        PlotScene3DFrameRenderState frame;
        uint64_t geometry_revision = 0;
        uint64_t style_revision = 0;
        uint64_t render_revision = 0;
    };

    // The returned source is owned by chart and remains valid only while chart is
    // alive. Published snapshots own their adapter payloads and do not borrow
    // mutable retained slots from the chart.
    TCPLOT_API termin::RenderItemSource& plot_scene3d_render_item_source(tc_retained_chart3d& chart);

    // Returns the immutable tcplot payload retained by the item's owning snapshot,
    // or null when the item belongs to another adapter/kind or is malformed.
    TCPLOT_API const PlotScene3DRenderItemPayload*
    plot_scene3d_render_item_payload(const tc_render_item& item) noexcept;

} // namespace tcplot
