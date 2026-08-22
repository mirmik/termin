#pragma once

#include "bounds2.hpp"
#include <cmath>
#include <cstddef>
#include <type_traits>

namespace termin {

    // 2D rectangle with double-precision origin and extent.
    struct Rect2 {
        double x = 0.0;
        double y = 0.0;
        double width = 0.0;
        double height = 0.0;

        constexpr Rect2() noexcept = default;
        constexpr Rect2(double x, double y, double width, double height) noexcept
            : x(x),
              y(y),
              width(width),
              height(height) {}
        explicit Rect2(const ::tc_rect2f& value) noexcept
            : Rect2(value.x, value.y, value.width, value.height) {}

        bool is_finite() const noexcept {
            return std::isfinite(x) && std::isfinite(y) && std::isfinite(width) && std::isfinite(height);
        }
        bool is_valid() const noexcept {
            return is_finite() && width >= 0.0 && height >= 0.0;
        }
        constexpr Vec2 origin() const noexcept {
            return {x, y};
        }
        constexpr Vec2 size() const noexcept {
            return {width, height};
        }
        constexpr Vec2 center() const noexcept {
            return {x + width * 0.5, y + height * 0.5};
        }
        constexpr Vec2 min() const noexcept {
            return {x, y};
        }
        constexpr Vec2 max() const noexcept {
            return {x + width, y + height};
        }
        constexpr bool contains_closed(const Vec2& point) const noexcept {
            return point.x >= x && point.x <= x + width && point.y >= y && point.y <= y + height;
        }
        constexpr bool contains_half_open(const Vec2& point) const noexcept {
            return point.x >= x && point.x < x + width && point.y >= y && point.y < y + height;
        }
        constexpr Bounds2 bounds() const noexcept {
            return {x, y, x + width, y + height};
        }
        ::tc_rect2f to_float() const noexcept {
            return {static_cast<float>(x),
                    static_cast<float>(y),
                    static_cast<float>(width),
                    static_cast<float>(height)};
        }
    };

    // 2D rectangle with integer origin and extent.
    struct Rect2i {
        int x = 0;
        int y = 0;
        int width = 0;
        int height = 0;

        Rect2i() = default;
        Rect2i(int x, int y, int width, int height)
            : x(x),
              y(y),
              width(width),
              height(height) {}
    };

    using Rect2f = ::tc_rect2f;

    inline Rect2 Bounds2::to_rect() const noexcept {
        return {x0, y0, width(), height()};
    }

    static_assert(std::is_same<Rect2f, ::tc_rect2f>::value, "termin::Rect2f must alias tc_rect2f");
    static_assert(std::is_standard_layout<Rect2f>::value, "Rect2f must stay ABI-friendly");
    static_assert(std::is_trivially_copyable<Rect2f>::value, "Rect2f must stay trivially copyable");
    static_assert(sizeof(Rect2f) == sizeof(float) * 4, "Rect2f must stay a packed origin/extent tuple");
    static_assert(offsetof(Rect2f, x) == 0, "Rect2f.x offset changed");
    static_assert(offsetof(Rect2f, y) == sizeof(float), "Rect2f.y offset changed");
    static_assert(offsetof(Rect2f, width) == sizeof(float) * 2, "Rect2f.width offset changed");
    static_assert(offsetof(Rect2f, height) == sizeof(float) * 3, "Rect2f.height offset changed");

} // namespace termin

inline termin::Rect2 tc_rect2f::to_double() const noexcept {
    return {x, y, width, height};
}
