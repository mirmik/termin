#include "tcplot/gpu_host.hpp"
#include "tcplot/retained_chart2d.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <termin_visual_scene/scene2d.hpp>
#include <termin_visual_scene/scene_render2d.hpp>
#include <tgfx2/device_factory.hpp>
#include <tgfx2/font_atlas.hpp>
#include <unordered_map>
#include <variant>
#include <vector>

namespace {
    void require(bool condition, const char* message) {
        if (!condition)
            throw std::runtime_error(message);
    }
    bool close(float a, float b) {
        return std::abs(a - b) < 0.05f;
    }

    // Only a detached paint snapshot is inspected; no GPU commands are executed.
    class Resolver final : public termin::visual::SceneRenderResourceResolver2D {
        std::optional<tgfx::FontHandle> resolve_font(std::string_view) override {
            return tgfx::FontHandle{1};
        }
        std::optional<tgfx::TextureHandle> resolve_image(std::string_view) override {
            return std::nullopt;
        }
        std::optional<termin::visual::ResolvedCustomBatch2D> resolve_custom_batch(std::string_view,
                                                                                  termin::Bounds2f) override {
            return std::nullopt;
        }
    };
    class Snapshot final : public termin::visual::ScenePaintLayerSink2D {
        std::unordered_map<uint32_t, tgfx::DrawList2D> layers_;

    public:
        bool append_item_layer(const tc_graphic_item& item, tgfx::DrawList2D list) override {
            layers_.insert_or_assign(item.handle.index, std::move(list));
            return true;
        }
        template <typename T> const T* find(tc_graphic_item_handle handle) const {
            const auto layer = layers_.find(handle.index);
            if (layer == layers_.end())
                return nullptr;
            for (const auto& command : layer->second.commands())
                if (const auto* value = std::get_if<T>(&command))
                    return value;
            return nullptr;
        }
        template <typename T> const T& get(tc_graphic_item_handle handle) const {
            const auto* result = find<T>(handle);
            require(result != nullptr, "expected public chart part paint snapshot is missing");
            return *result;
        }
    };
    struct Cell {
        float left, top, right, bottom;
    };
    Cell text_cell(tgfx::FontAtlas& font, const tgfx::DrawText2D& text) {
        font.ensure_glyphs(text.text, text.size_px);
        const auto measured = font.measure_text(text.text, text.size_px);
        float left = text.origin.x, top = text.origin.y;
        // This is the Canvas text renderer's anchor contract: Center shifts by
        // half nominal size vertically, Left/Right start at the line-cell top.
        if (text.anchor == tgfx::TextAnchor2D::Center) {
            left -= measured.width * 0.5f;
            top -= text.size_px * 0.5f;
        } else if (text.anchor == tgfx::TextAnchor2D::Right)
            left -= measured.width;
        return {left, top, left + measured.width, top + font.line_height_px(text.size_px)};
    }
    bool inside(Cell cell, const termin::Rect2f& bounds) {
        constexpr float epsilon = 0.1f;
        return cell.left >= bounds.x - epsilon && cell.top >= bounds.y - epsilon &&
               cell.right <= bounds.x + bounds.width + epsilon && cell.bottom <= bounds.y + bounds.height + epsilon;
    }
    std::vector<tc_graphic_item_handle> children(tc_visual_scene_handle scene, tc_graphic_item_handle parent) {
        std::vector<tc_graphic_item_handle> result;
        for (size_t i = 0; i < tc_visual_scene_item_child_count(scene, parent); ++i)
            result.push_back(tc_visual_scene_item_child_at(scene, parent, i));
        return result;
    }
    bool has_tick(const tgfx::DrawPath2D& path, float coordinate, bool x_axis) {
        const auto& points = path.path.points();
        for (size_t i = 0; i + 1 < points.size(); i += 2) {
            const auto a = points[i], b = points[i + 1];
            if (x_axis && close(a.x, b.x) && !close(a.y, b.y) && close(a.x, coordinate))
                return true;
            if (!x_axis && close(a.y, b.y) && !close(a.x, b.x) && close(a.y, coordinate))
                return true;
        }
        return false;
    }
    void verify(tc_retained_chart2d* chart, tgfx::FontAtlas& font, const tc_chart2d_theme& theme, float dpi) {
        const auto scene_handle = tc_retained_chart2d_scene(chart);
        termin::visual::TcVisualScene scene{scene_handle};
        Resolver resolver;
        Snapshot snapshot;
        require(scene.paint_layers(snapshot, resolver), "chart paint snapshot failed");
        tc_chart2d_layout layout{};
        require(tc_retained_chart2d_layout(chart, &layout), "chart layout snapshot failed");
        auto part = [&](tc_chart2d_part kind) {
            return tc_retained_chart2d_part_handle(chart, kind);
        };
        const auto& viewport = layout.viewport;
        const auto& plot = layout.plot_area;
        const float padding = theme.outer_padding_logical_px * dpi;
        const float gap = theme.gap_logical_px * dpi;
        const float tick = theme.tick_length_logical_px * dpi;
        const termin::Rect2f padded{
            viewport.x + padding, viewport.y + padding, viewport.width - 2 * padding, viewport.height - 2 * padding};
        const auto title = text_cell(font, snapshot.get<tgfx::DrawText2D>(part(TC_CHART2D_PART_TITLE)));
        const auto xlabel = text_cell(font, snapshot.get<tgfx::DrawText2D>(part(TC_CHART2D_PART_X_AXIS_LABEL)));
        const auto ylabel = text_cell(font, snapshot.get<tgfx::DrawText2D>(part(TC_CHART2D_PART_Y_AXIS_LABEL)));
        require(close(title.top, padded.y), "title line cell must start at the viewport padding");
        require(inside(title, padded), "title line cell must remain inside padded viewport");
        require(inside(xlabel, padded), "X axis label line cell must remain inside padded viewport");
        require(close(xlabel.bottom, padded.y + padded.height),
                "X axis label bottom must match viewport bottom padding");
        require(close((ylabel.top + ylabel.bottom) * 0.5f, plot.y + plot.height * 0.5f),
                "Y axis label line cell must be vertically centered on the plot");
        require(inside(ylabel, padded), "Y axis label must remain inside padded viewport");

        const auto& xaxis = snapshot.get<tgfx::DrawPath2D>(part(TC_CHART2D_PART_X_AXIS));
        const auto& yaxis = snapshot.get<tgfx::DrawPath2D>(part(TC_CHART2D_PART_Y_AXIS));
        size_t xcount = 0, ycount = 0;
        for (const auto handle : children(scene_handle, part(TC_CHART2D_PART_X_TICK_LABELS_ROOT))) {
            const auto* text = snapshot.find<tgfx::DrawText2D>(handle);
            if (!text)
                continue;
            ++xcount;
            const auto cell = text_cell(font, *text);
            require(close(cell.top, plot.y + plot.height + tick + gap),
                    "X tick line-cell top must follow tick marks and gap");
            require(cell.bottom <= xlabel.top - gap + 0.1f, "X tick labels must fit above X axis label with a gap");
            require(has_tick(xaxis, text->origin.x, true), "X label must center horizontally on an actual axis tick");
            require(cell.left >= viewport.x && cell.right <= viewport.x + viewport.width,
                    "X tick labels must fit horizontal viewport margins");
        }
        for (const auto handle : children(scene_handle, part(TC_CHART2D_PART_Y_TICK_LABELS_ROOT))) {
            const auto* text = snapshot.find<tgfx::DrawText2D>(handle);
            if (!text)
                continue;
            ++ycount;
            const auto cell = text_cell(font, *text);
            require(has_tick(yaxis, (cell.top + cell.bottom) * 0.5f, false),
                    "Y label line-cell center must align with an actual axis tick");
            require(close(cell.right, plot.x - tick - gap), "Y tick labels must sit before tick marks and gap");
            require(cell.left >= ylabel.right + gap - 0.1f,
                    "Y tick labels must fit their allocated margin after Y axis label");
            require(cell.top >= viewport.y && cell.bottom <= viewport.y + viewport.height,
                    "Y tick line cells must fit vertical viewport margins");
        }
        require(xcount > 1 && ycount > 1, "fixture must exercise multiple labels on both axes");

        const auto legend = part(TC_CHART2D_PART_LEGEND_ROOT);
        const tgfx::DrawRect2D* background = nullptr;
        for (const auto handle : children(scene_handle, legend))
            if (const auto* rect = snapshot.find<tgfx::DrawRect2D>(handle))
                background = rect;
        require(background != nullptr, "legend background snapshot is missing");
        size_t entries = 0;
        float previous_bottom = -1;
        for (const auto group : children(scene_handle, legend)) {
            const tgfx::DrawText2D* label = nullptr;
            const tgfx::DrawPath2D* swatch = nullptr;
            for (const auto handle : children(scene_handle, group)) {
                if (const auto* text = snapshot.find<tgfx::DrawText2D>(handle))
                    label = text;
                if (const auto* path = snapshot.find<tgfx::DrawPath2D>(handle))
                    swatch = path;
            }
            if (!label)
                continue;
            require(swatch != nullptr && swatch->path.points().size() == 2, "legend row must contain its swatch path");
            const auto cell = text_cell(font, *label);
            const auto& points = swatch->path.points();
            require(close(points[0].y, points[1].y), "legend swatch must be horizontal");
            require(close((cell.top + cell.bottom) * 0.5f, points[0].y),
                    "legend label line-cell center must align with swatch center");
            require(inside(cell, background->rect), "legend label line cell must fit completely inside background");
            require(cell.top > previous_bottom, "successive legend rows must not overlap");
            previous_bottom = cell.bottom;
            ++entries;
        }
        require(entries == 3, "all named legend entries must participate in the layout fixture");
    }

    int run(tgfx::BackendType backend) {
        if (!tgfx::backend_is_compiled(backend))
            return 77;
        tcplot::GpuHost host(TCPLOT_TEST_FONT, backend);
        auto theme = tc_retained_chart2d_default_theme();
        auto* chart = tc_retained_chart2d_create(&host, {37, 23, 900, 620}, {0, 6, -2, 4}, TCPLOT_TEST_FONT, 1, &theme);
        require(chart != nullptr, "chart creation failed");
        require(tc_retained_chart2d_set_title(chart, "Chart title gyp"), "title setup failed");
        require(tc_retained_chart2d_set_x_axis_label(chart, "Frequency gyp [Hz]"), "X label setup failed");
        require(tc_retained_chart2d_set_y_axis_label(chart, "Gain [dB]"), "Y label setup failed");
        const double x[]{0, 3, 6}, y[]{-2, 1, 4};
        const tc_plot_line_style_state2d line{
            {0.2f, 0.6f, 0.9f, 1}, 2, TC_PLOT_LINE_STYLE_SOLID_2D, 8, 5, TC_PLOT_COLORMAP_SOLID_2D, false, 0, 1};
        for (const char* name : {"Probe path", "gyp jq descenders", "Mg reference"}) {
            const auto series = tc_retained_chart2d_add_named_line(chart, name, true, x, y, nullptr, 3, line);
            require(series.chart_id != 0, "named series setup failed");
        }
        for (float dpi : {1.0f, 1.25f, 2.0f}) {
            for (float font_size : {12.0f, 17.0f, 24.0f}) {
                std::printf("chart2d layout: DPI %.2f, logical font %.0f\n", dpi, font_size);
                theme.font_size_logical_px = font_size;
                theme.title_font_size_logical_px = font_size * 1.5f;
                require(tc_retained_chart2d_set_theme(chart, &theme), "theme update failed");
                require(tc_retained_chart2d_set_viewport(chart, {37 * dpi, 23 * dpi, 900 * dpi, 620 * dpi}, dpi),
                        "DPI viewport setup failed");
                verify(chart, host.font(), theme, dpi);
                require(tc_retained_chart2d_set_viewport(chart, {37 * dpi, 23 * dpi, 1040 * dpi, 730 * dpi}, dpi),
                        "viewport resize failed");
                verify(chart, host.font(), theme, dpi);
                require(tc_retained_chart2d_set_x_range(chart, -0.5, 6.5), "fast X range update failed");
                verify(chart, host.font(), theme, dpi);
            }
        }
        tc_retained_chart2d_destroy(chart);
        return 0;
    }
} // namespace
int main(int argc, char** argv) {
    try {
        return run(argc == 2 && std::strcmp(argv[1], "--d3d11") == 0 ? tgfx::BackendType::D3D11
                                                                     : tgfx::BackendType::Vulkan);
    } catch (const std::exception& error) {
        std::fprintf(stderr, "retained chart2d layout test: %s\n", error.what());
        return 1;
    }
}
