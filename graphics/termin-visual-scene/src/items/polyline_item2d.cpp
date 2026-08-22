#include "termin_visual_scene/items/polyline_item2d.hpp"

#include <algorithm>
#include <stdexcept>

#include <tcbase/tc_log.hpp>

namespace termin::visual {
    namespace {

        void validate(const std::vector<termin::Vec2f>& points, const tgfx::StrokePaint& stroke) {
            if (points.size() < 2 || !stroke.validate() ||
                !std::all_of(points.begin(), points.end(), [](termin::Vec2f point) { return point.is_finite(); })) {
                throw std::invalid_argument("invalid PolylineItem2D state");
            }
        }

        tgfx::Path2f hit_path(const std::vector<termin::Vec2f>& points, bool closed) {
            tgfx::Path2f path;
            path.move_to(points.front());
            for (std::size_t i = 1; i < points.size(); ++i) {
                path.line_to(points[i]);
            }
            if (closed)
                path.close();
            return path;
        }

    } // namespace

    PolylineItem2D::PolylineItem2D()
        : NativeGraphicItem2D("termin.visual.Polyline2D") {}

    PolylineItem2D::PolylineItem2D(std::vector<termin::Vec2f> points, tgfx::StrokePaint stroke, bool closed)
        : PolylineItem2D() {
        set(std::move(points), std::move(stroke), closed);
    }

    void PolylineItem2D::set(std::vector<termin::Vec2f> points, tgfx::StrokePaint stroke, bool closed) {
        validate(points, stroke);
        points_ = std::move(points);
        stroke_ = std::move(stroke);
        closed_ = closed;
    }

    void PolylineItem2D::set_points(std::vector<termin::Vec2f> points) {
        validate(points, stroke_);
        points_ = std::move(points);
    }

    void PolylineItem2D::set_stroke(tgfx::StrokePaint stroke) {
        validate(points_, stroke);
        stroke_ = std::move(stroke);
    }

    void PolylineItem2D::set_closed(bool closed) {
        closed_ = closed;
    }

    std::optional<termin::Bounds2f> PolylineItem2D::local_bounds() const {
        if (points_.empty())
            return std::nullopt;
        termin::Vec2f minimum = points_.front();
        termin::Vec2f maximum = points_.front();
        for (const auto point : points_) {
            minimum = minimum.cwise_min(point);
            maximum = maximum.cwise_max(point);
        }
        return termin::Bounds2f{minimum.x, minimum.y, maximum.x, maximum.y}.expanded(stroke_.width * 0.5f);
    }

    bool PolylineItem2D::hit_test(termin::Vec2f point, float) const {
        return !points_.empty() && hit_path(points_, closed_).flatten().stroke_contains(point, stroke_);
    }

    bool PolylineItem2D::paint(GraphicItemPaintContext2D& context) const {
        return context.polyline(points_, stroke_, closed_);
    }

} // namespace termin::visual
