#pragma once

#include <algorithm>

#include <termin/geom/rect2.hpp>

namespace termin::visual::detail {

    inline bool rounded_rect_contains(termin::Rect2f rect, float radius, termin::Vec2f point) {
        if (!rect.contains_closed(point))
            return false;
        const float r = std::min(radius, std::min(rect.width, rect.height) * 0.5f);
        if (r <= 0.0f)
            return true;
        const termin::Vec2f radius_offset{r, r};
        const termin::Vec2f closest = point.clamped(rect.min() + radius_offset, rect.max() - radius_offset);
        return (point - closest).norm_squared() <= r * r;
    }

    inline bool ellipse_contains(termin::Rect2f bounds, termin::Vec2f point) {
        if (bounds.width <= 0.0f || bounds.height <= 0.0f) {
            return false;
        }
        const termin::Vec2f half_size = bounds.size() * 0.5f;
        return (point - bounds.center()).cwise_quotient(half_size).norm_squared() <= 1.0f;
    }

} // namespace termin::visual::detail
