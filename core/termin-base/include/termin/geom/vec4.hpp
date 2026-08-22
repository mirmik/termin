#pragma once

#include <cassert>
#include <cstddef>
#include <tcbase/tc_types.h>
#include <type_traits>

namespace termin {

    // ============================================================================
    // Canonical ABI-friendly floating-point vectors
    // ============================================================================

    using Vec4 = ::tc_vec4;
    using Vec4f = ::tc_vec4f;

    static_assert(std::is_same<Vec4, ::tc_vec4>::value, "termin::Vec4 must alias tc_vec4");
    static_assert(std::is_standard_layout<Vec4>::value, "Vec4 must stay standard layout");
    static_assert(std::is_trivially_copyable<Vec4>::value, "Vec4 must stay trivially copyable");
    static_assert(sizeof(Vec4) == sizeof(double) * 4, "Vec4 must stay packed");
    static_assert(offsetof(Vec4, x) == 0, "Vec4.x offset changed");
    static_assert(offsetof(Vec4, w) == sizeof(double) * 3, "Vec4.w offset changed");
    static_assert(std::is_same<Vec4f, ::tc_vec4f>::value, "termin::Vec4f must alias tc_vec4f");
    static_assert(std::is_standard_layout<Vec4f>::value, "Vec4f must stay standard layout");
    static_assert(std::is_trivially_copyable<Vec4f>::value, "Vec4f must stay trivially copyable");
    static_assert(sizeof(Vec4f) == sizeof(float) * 4, "Vec4f must stay packed");
    static_assert(offsetof(Vec4f, x) == 0, "Vec4f.x offset changed");
    static_assert(offsetof(Vec4f, w) == sizeof(float) * 3, "Vec4f.w offset changed");

    // ============================================================================
    // Vec4i (int)
    // ============================================================================

    struct Vec4i {
        int x, y, z, w;

        Vec4i()
            : x(0),
              y(0),
              z(0),
              w(0) {}
        Vec4i(int x, int y, int z, int w)
            : x(x),
              y(y),
              z(z),
              w(w) {}

        int& operator[](int i) {
            assert(i >= 0 && i < 4);
            return i == 0 ? x : (i == 1 ? y : (i == 2 ? z : w));
        }
        int operator[](int i) const {
            assert(i >= 0 && i < 4);
            return i == 0 ? x : (i == 1 ? y : (i == 2 ? z : w));
        }

        Vec4i operator+(const Vec4i& v) const {
            return {x + v.x, y + v.y, z + v.z, w + v.w};
        }
        Vec4i operator-(const Vec4i& v) const {
            return {x - v.x, y - v.y, z - v.z, w - v.w};
        }
        Vec4i operator*(int s) const {
            return {x * s, y * s, z * s, w * s};
        }
        Vec4i operator/(int s) const {
            return {x / s, y / s, z / s, w / s};
        }
        Vec4i operator-() const {
            return {-x, -y, -z, -w};
        }

        Vec4i& operator+=(const Vec4i& v) {
            x += v.x;
            y += v.y;
            z += v.z;
            w += v.w;
            return *this;
        }
        Vec4i& operator-=(const Vec4i& v) {
            x -= v.x;
            y -= v.y;
            z -= v.z;
            w -= v.w;
            return *this;
        }
        Vec4i& operator*=(int s) {
            x *= s;
            y *= s;
            z *= s;
            w *= s;
            return *this;
        }
        Vec4i& operator/=(int s) {
            x /= s;
            y /= s;
            z /= s;
            w /= s;
            return *this;
        }

        bool operator==(const Vec4i& v) const {
            return x == v.x && y == v.y && z == v.z && w == v.w;
        }
        bool operator!=(const Vec4i& v) const {
            return !(*this == v);
        }

        int dot(const Vec4i& v) const {
            return x * v.x + y * v.y + z * v.z + w * v.w;
        }

        Vec4 to_double() const {
            return {static_cast<double>(x), static_cast<double>(y), static_cast<double>(z), static_cast<double>(w)};
        }
        Vec4f to_float() const {
            return {static_cast<float>(x), static_cast<float>(y), static_cast<float>(z), static_cast<float>(w)};
        }

        static Vec4i zero() {
            return {0, 0, 0, 0};
        }
        static Vec4i unit_x() {
            return {1, 0, 0, 0};
        }
        static Vec4i unit_y() {
            return {0, 1, 0, 0};
        }
        static Vec4i unit_z() {
            return {0, 0, 1, 0};
        }
        static Vec4i unit_w() {
            return {0, 0, 0, 1};
        }
    };

    inline Vec4i operator*(int s, const Vec4i& v) {
        return v * s;
    }

} // namespace termin
