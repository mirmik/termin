#pragma once

#include <memory>

#include <tcplot/gpu_host.hpp>
#include <tcplot/retained_chart3d.h>

namespace termin::web {

    class WebChart3D {
    public:
        WebChart3D(tgfx::GraphicsHost& host, const char* x_label, const char* y_label, const char* z_label);

        tc_retained_chart3d* chart() const {
            return chart_.get();
        }
        bool set_surface(const double* x, const double* y, const double* z, uint32_t rows, uint32_t columns, bool fit);

    private:
        tcplot::GpuHost host_;
        std::unique_ptr<tc_retained_chart3d, decltype(&tc_retained_chart3d_destroy)> chart_;
        tc_plot_item3d_handle surface_{};
    };

} // namespace termin::web
