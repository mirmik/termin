#pragma once

#include "size2.hpp"
#include "vec2.hpp"
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <type_traits>

namespace termin {

    struct Rect2;

    // 2D bounds with double-precision min/max coordinates.
    struct Bounds2 {
        double x0 = 0.0;
        double y0 = 0.0;
        double x1 = 0.0;
        double y1 = 0.0;

        constexpr Bounds2() noexcept = default;
        constexpr Bounds2(double x0, double y0, double x1, double y1) noexcept
            : x0(x0),
              y0(y0),
              x1(x1),
              y1(y1) {}
        explicit Bounds2(const ::tc_bounds2f& value) noexcept
            : Bounds2(value.x0, value.y0, value.x1, value.y1) {}

        constexpr double width() const noexcept {
            return x1 - x0;
        }
        constexpr double height() const noexcept {
            return y1 - y0;
        }

        bool is_finite() const noexcept {
            return std::isfinite(x0) && std::isfinite(y0) && std::isfinite(x1) && std::isfinite(y1);
        }
        bool is_valid() const noexcept {
            return is_finite() && x0 <= x1 && y0 <= y1;
        }
        constexpr Vec2 min() const noexcept {
            return {x0, y0};
        }
        constexpr Vec2 max() const noexcept {
            return {x1, y1};
        }
        constexpr Vec2 center() const noexcept {
            return {(x0 + x1) * 0.5, (y0 + y1) * 0.5};
        }
        void extend(const Vec2& point) noexcept {
            x0 = x0 < point.x ? x0 : point.x;
            y0 = y0 < point.y ? y0 : point.y;
            x1 = x1 > point.x ? x1 : point.x;
            y1 = y1 > point.y ? y1 : point.y;
        }
        constexpr bool contains_closed(const Vec2& point) const noexcept {
            return point.x >= x0 && point.x <= x1 && point.y >= y0 && point.y <= y1;
        }
        constexpr bool contains_half_open(const Vec2& point) const noexcept {
            return point.x >= x0 && point.x < x1 && point.y >= y0 && point.y < y1;
        }
        constexpr Bounds2 expanded(double amount) const noexcept {
            return {x0 - amount, y0 - amount, x1 + amount, y1 + amount};
        }
        constexpr Bounds2 merged(const Bounds2& other) const noexcept {
            return {x0 < other.x0 ? x0 : other.x0,
                    y0 < other.y0 ? y0 : other.y0,
                    x1 > other.x1 ? x1 : other.x1,
                    y1 > other.y1 ? y1 : other.y1};
        }
        bool try_intersection(const Bounds2& other, Bounds2& out) const noexcept {
            const Bounds2 result{
                std::max(x0, other.x0),
                std::max(y0, other.y0),
                std::min(x1, other.x1),
                std::min(y1, other.y1),
            };
            if (!result.is_valid()) {
                return false;
            }
            out = result;
            return true;
        }
        Rect2 to_rect() const noexcept;
        ::tc_bounds2f to_float() const noexcept {
            return {static_cast<float>(x0), static_cast<float>(y0), static_cast<float>(x1), static_cast<float>(y1)};
        }

        static constexpr Bounds2 from_size(double width, double height) noexcept {
            return {0.0, 0.0, width, height};
        }
    };

    // 2D bounds with integer min/max coordinates.
    struct Bounds2i {
        int x0 = 0;
        int y0 = 0;
        int x1 = 0;
        int y1 = 0;

        Bounds2i() = default;
        Bounds2i(int x0, int y0, int x1, int y1)
            : x0(x0),
              y0(y0),
              x1(x1),
              y1(y1) {}

        int width() const {
            return x1 - x0;
        }
        int height() const {
            return y1 - y0;
        }

        static Bounds2i from_size(int width, int height) {
            return {0, 0, width, height};
        }
        static Bounds2i from_size(Size2i size) {
            return {0, 0, size.width, size.height};
        }
    };

    using Bounds2f = ::tc_bounds2f;

    static_assert(std::is_same<Bounds2f, ::tc_bounds2f>::value, "termin::Bounds2f must alias tc_bounds2f");
    static_assert(std::is_standard_layout<Bounds2f>::value, "Bounds2f must stay ABI-friendly");
    static_assert(std::is_trivially_copyable<Bounds2f>::value, "Bounds2f must stay trivially copyable");
    static_assert(sizeof(Bounds2f) == sizeof(float) * 4, "Bounds2f must stay a packed min/max tuple");
    static_assert(offsetof(Bounds2f, x0) == 0, "Bounds2f.x0 offset changed");
    static_assert(offsetof(Bounds2f, y0) == sizeof(float), "Bounds2f.y0 offset changed");
    static_assert(offsetof(Bounds2f, x1) == sizeof(float) * 2, "Bounds2f.x1 offset changed");
    static_assert(offsetof(Bounds2f, y1) == sizeof(float) * 3, "Bounds2f.y1 offset changed");

} // namespace termin

inline termin::Bounds2 tc_bounds2f::to_double() const noexcept {
    return {x0, y0, x1, y1};
}
