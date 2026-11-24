#include "web_chart2d.hpp"
#include "web_graphics_assets.hpp"

#include <stdexcept>

namespace termin::web {

    WebChart2D::WebChart2D(tgfx::GraphicsHost& host,
                           tc_plot_rect2d viewport,
                           float scale,
                           const char* title,
                           const char* x_label,
                           const char* y_label,
                           const char* series_name)
        : host_(default_font_path, host),
          chart_(tc_retained_chart2d_create(&host_, viewport, {0, 1, 0, 1}, "ui://default-font", scale, nullptr),
                 &tc_retained_chart2d_destroy),
          renderer_(nullptr, &tc_retained_scene_renderer2d_destroy) {
        if (!chart_ || !tc_retained_chart2d_set_title(chart(), title) ||
            !tc_retained_chart2d_set_x_axis_label(chart(), x_label) ||
            !tc_retained_chart2d_set_y_axis_label(chart(), y_label)) {
            throw std::runtime_error("could not initialize chart axes");
        }
        const tc_plot_line_style_state2d style{
            {0.06f, 0.82f, 0.66f, 1}, 2, TC_PLOT_LINE_STYLE_SOLID_2D, 8, 5, TC_PLOT_COLORMAP_SOLID_2D, false, 0, 1};
        const auto series = tc_retained_chart2d_add_named_line(
            chart(), series_name, series_name && *series_name, nullptr, nullptr, nullptr, 0, style);
        tc_chart_series_snapshot2d snapshot{};
        if (!tc_retained_chart2d_series_snapshot(chart(), series, &snapshot)) {
            throw std::runtime_error("could not initialize chart line");
        }
        line_ = snapshot.item;
        renderer_.reset(tc_retained_scene_renderer2d_create(&host_, tc_retained_chart2d_scene(chart())));
        if (!renderer_) {
            throw std::runtime_error("could not initialize retained scene renderer");
        }
    }

    bool WebChart2D::set_data(const double* x, const double* y, size_t count, bool fit) {
        if (!tc_plot_line_series_item2d_set_data(tc_retained_chart2d_scene(chart()), line_, x, y, nullptr, count)) {
            return false;
        }
        return !fit || count == 0 || tc_retained_chart2d_fit(chart(), 0.05);
    }

    bool WebChart2D::render(uint32_t target, int width, int height) {
        return tc_retained_scene_renderer2d_render_to(renderer_.get(), target, width, height);
    }

} // namespace termin::web
