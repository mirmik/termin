#include "web_chart3d.hpp"
#include "web_graphics_assets.hpp"

#include <limits>
#include <stdexcept>

namespace termin::web {

    WebChart3D::WebChart3D(tgfx::GraphicsHost& host, const char* x_label, const char* y_label, const char* z_label)
        : host_(default_font_path, host), chart_(tc_retained_chart3d_create(&host_), &tc_retained_chart3d_destroy) {
        if (!chart_ || !tc_retained_chart3d_set_msaa_samples(chart(), 1)) {
            throw std::runtime_error("could not initialize retained 3D chart");
        }
        tc_retained_chart3d_set_axis_labels(chart(), x_label, y_label, z_label);
    }

    bool WebChart3D::set_surface(
        const double* x, const double* y, const double* z, uint32_t rows, uint32_t columns, bool fit) {
        if (!x || !y || !z || rows < 2 || columns < 2 ||
            rows > std::numeric_limits<size_t>::max() / sizeof(double) / columns) {
            return false;
        }
        if (tc_retained_chart3d_item_is_valid(chart(), surface_)) {
            if (!tc_retained_chart3d_surface_set_data(chart(), surface_, x, y, z, rows, columns)) {
                return false;
            }
            if (fit) {
                tc_retained_chart3d_fit_camera(chart());
            }
            return true;
        }

        // The native add operation frames the first surface automatically.
        tc_orbit_camera3d_state camera{};
        if (!fit && !tc_retained_chart3d_get_camera(chart(), &camera)) {
            return false;
        }
        surface_ = tc_retained_chart3d_add_surface(chart(), x, y, z, rows, columns, nullptr);
        return tc_retained_chart3d_item_is_valid(chart(), surface_) &&
               (fit || tc_retained_chart3d_set_camera(chart(), &camera));
    }

} // namespace termin::web
