#include <cassert>
#include <cmath>

#include "tcplot/plot_frame2d.hpp"

namespace {

    bool near(double lhs, double rhs, double epsilon = 1e-6) {
        return std::abs(lhs - rhs) <= epsilon;
    }

} // namespace

int main() {
    using namespace tcplot;

    const PlotFrame2D frame(PlotRect2D(10.0f, 20.0f, 400.0f, 300.0f),
                            PlotRect2D(60.0f, 40.0f, 300.0f, 200.0f),
                            PlotRange2D(-10.0, 30.0, -5.0, 15.0),
                            PlotRect2D(60.0f, 40.0f, 300.0f, 200.0f),
                            2.0f);

    const PlotPixelPoint2D lower_left = frame.data_to_pixel(-10.0, -5.0);
    assert(near(lower_left.x, 60.0));
    assert(near(lower_left.y, 240.0));

    const PlotPixelPoint2D upper_right = frame.data_to_pixel(30.0, 15.0);
    assert(near(upper_right.x, 360.0));
    assert(near(upper_right.y, 40.0));

    const PlotPixelPoint2D center = frame.data_to_pixel(10.0, 5.0);
    const PlotPoint2D round_trip = frame.pixel_to_data(center.x, center.y);
    assert(near(round_trip.x, 10.0));
    assert(near(round_trip.y, 5.0));
    assert(frame.contains_plot_pixel(center.x, center.y));
    assert(!frame.contains_plot_pixel(59.0f, center.y));
    assert(near(frame.pixel_scale(), 2.0));

    return 0;
}
