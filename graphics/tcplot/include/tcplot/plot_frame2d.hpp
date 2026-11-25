// plot_frame2d.hpp - Immutable snapshot of a 2D plot projection.
#pragma once

#include "tcplot/tcplot_api.h"

namespace tcplot {

    struct PlotPoint2D {
        double x = 0.0;
        double y = 0.0;
    };

    struct PlotPixelPoint2D {
        float x = 0.0f;
        float y = 0.0f;
    };

    class TCPLOT_API PlotRect2D final {
    public:
        constexpr PlotRect2D() = default;
        constexpr PlotRect2D(float x, float y, float width, float height)
            : x_(x),
              y_(y),
              width_(width),
              height_(height) {}

        constexpr float x() const {
            return x_;
        }
        constexpr float y() const {
            return y_;
        }
        constexpr float width() const {
            return width_;
        }
        constexpr float height() const {
            return height_;
        }
        constexpr float right() const {
            return x_ + width_;
        }
        constexpr float bottom() const {
            return y_ + height_;
        }
        constexpr bool contains(float x, float y) const {
            return x >= x_ && x <= right() && y >= y_ && y <= bottom();
        }

    private:
        float x_ = 0.0f;
        float y_ = 0.0f;
        float width_ = 0.0f;
        float height_ = 0.0f;
    };

    class TCPLOT_API PlotRange2D final {
    public:
        constexpr PlotRange2D() = default;
        constexpr PlotRange2D(double x_min, double x_max, double y_min, double y_max)
            : x_min_(x_min),
              x_max_(x_max),
              y_min_(y_min),
              y_max_(y_max) {}

        constexpr double x_min() const {
            return x_min_;
        }
        constexpr double x_max() const {
            return x_max_;
        }
        constexpr double y_min() const {
            return y_min_;
        }
        constexpr double y_max() const {
            return y_max_;
        }
        constexpr double x_span() const {
            return x_max_ - x_min_;
        }
        constexpr double y_span() const {
            return y_max_ - y_min_;
        }

    private:
        double x_min_ = 0.0;
        double x_max_ = 1.0;
        double y_min_ = 0.0;
        double y_max_ = 1.0;
    };

    // A detached, immutable projection snapshot. A frame remains usable after
    // its chart changes viewport or range.
    class TCPLOT_API PlotFrame2D final {
    public:
        PlotFrame2D() = default;
        PlotFrame2D(
            PlotRect2D viewport, PlotRect2D plot_area, PlotRange2D range, PlotRect2D clip_rect, float pixel_scale);

        const PlotRect2D& viewport() const {
            return viewport_;
        }
        const PlotRect2D& plot_area() const {
            return plot_area_;
        }
        const PlotRange2D& range() const {
            return range_;
        }
        const PlotRect2D& clip_rect() const {
            return clip_rect_;
        }
        float pixel_scale() const {
            return pixel_scale_;
        }

        PlotPixelPoint2D data_to_pixel(double x, double y) const;
        PlotPoint2D pixel_to_data(float x, float y) const;
        bool contains_plot_pixel(float x, float y) const {
            return plot_area_.contains(x, y);
        }

    private:
        PlotRect2D viewport_{};
        PlotRect2D plot_area_{};
        PlotRange2D range_{};
        PlotRect2D clip_rect_{};
        float pixel_scale_ = 1.0f;
    };

} // namespace tcplot
