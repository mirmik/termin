#pragma once

#include <memory>

#include <tcplot/gpu_host.hpp>
#include <tcplot/retained_chart2d.h>
#include <tcplot/retained_scene_renderer2d.h>

namespace termin::web {

    class WebChart2D {
    public:
        WebChart2D(tgfx::GraphicsHost& host,
                   tc_plot_rect2d viewport,
                   float scale,
                   const char* title,
                   const char* x_label,
                   const char* y_label,
                   const char* series_name);

        tc_retained_chart2d* chart() const {
            return chart_.get();
        }
        bool set_data(const double* x, const double* y, size_t count, bool fit);
        bool render(uint32_t target, int width, int height);

    private:
        tcplot::GpuHost host_;
        std::unique_ptr<tc_retained_chart2d, decltype(&tc_retained_chart2d_destroy)> chart_;
        std::unique_ptr<tc_retained_scene_renderer2d, decltype(&tc_retained_scene_renderer2d_destroy)> renderer_;
        tc_graphic_item_handle line_;
    };

} // namespace termin::web
