#pragma once

#include <cassert>
#include <cmath>
#include <cstddef>
#include <geom/tc_checked_normalization.h>
#include <type_traits>

namespace termin {

    struct Vec4f;

    // ============================================================================
    // Vec4 (double)
    // ============================================================================

    struct Vec4 {
        double x, y, z, w;

        Vec4()
            : x(0),
              y(0),
              z(0),
              w(0) {}
        Vec4(double x, double y, double z, double w)
            : x(x),
              y(y),
              z(z),
              w(w) {}

        double& operator[](int i) {
            assert(i >= 0 && i < 4);
            return i == 0 ? x : (i == 1 ? y : (i == 2 ? z : w));
        }
        double operator[](int i) const {
            assert(i >= 0 && i < 4);
            return i == 0 ? x : (i == 1 ? y : (i == 2 ? z : w));
        }

        Vec4 operator+(const Vec4& v) const {
            return {x + v.x, y + v.y, z + v.z, w + v.w};
        }
        Vec4 operator-(const Vec4& v) const {
            return {x - v.x, y - v.y, z - v.z, w - v.w};
        }
        Vec4 operator*(double s) const {
            return {x * s, y * s, z * s, w * s};
        }
        Vec4 operator/(double s) const {
            return {x / s, y / s, z / s, w / s};
        }
        Vec4 operator-() const {
            return {-x, -y, -z, -w};
        }

        Vec4& operator+=(const Vec4& v) {
            x += v.x;
            y += v.y;
            z += v.z;
            w += v.w;
            return *this;
        }
        Vec4& operator-=(const Vec4& v) {
            x -= v.x;
            y -= v.y;
            z -= v.z;
            w -= v.w;
            return *this;
        }
        Vec4& operator*=(double s) {
            x *= s;
            y *= s;
            z *= s;
            w *= s;
            return *this;
        }
        Vec4& operator/=(double s) {
            x /= s;
            y /= s;
            z /= s;
            w /= s;
            return *this;
        }

        bool operator==(const Vec4& v) const {
            return x == v.x && y == v.y && z == v.z && w == v.w;
        }
        bool operator!=(const Vec4& v) const {
            return !(*this == v);
        }

        double dot(const Vec4& v) const {
            return x * v.x + y * v.y + z * v.z + w * v.w;
        }

        double norm() const {
            return std::sqrt(x * x + y * y + z * z + w * w);
        }
        double norm_squared() const {
            return x * x + y * y + z * z + w * w;
        }

        Vec4 normalized() const {
            double n = norm();
            return n > 1e-10 ? *this / n : Vec4{0, 0, 0, 1};
        }

        bool is_finite() const noexcept {
            return std::isfinite(x) && std::isfinite(y) && std::isfinite(z) && std::isfinite(w);
        }
        bool try_normalized(Vec4& out, double epsilon = 1.0e-10) const noexcept {
            const double input[4] = {x, y, z, w};
            double output[4];
            if (!tc_detail_try_normalize_f64_components(input, 4, epsilon, output)) {
                return false;
            }
            out = {output[0], output[1], output[2], output[3]};
            return true;
        }
        Vec4 normalized_or(const Vec4& fallback, double epsilon = 1.0e-10) const noexcept {
            Vec4 result;
            return try_normalized(result, epsilon) ? result : fallback;
        }
        double* ptr() noexcept {
            return &x;
        }
        const double* ptr() const noexcept {
            return &x;
        }
        Vec4f to_float() const noexcept;

        static Vec4 zero() {
            return {0, 0, 0, 0};
        }
        static Vec4 unit_x() {
            return {1, 0, 0, 0};
        }
        static Vec4 unit_y() {
            return {0, 1, 0, 0};
        }
        static Vec4 unit_z() {
            return {0, 0, 1, 0};
        }
        static Vec4 unit_w() {
            return {0, 0, 0, 1};
        }
    };

    inline Vec4 operator*(double s, const Vec4& v) {
        return v * s;
    }

    // ============================================================================
    // Vec4f (float)
    // ============================================================================

    struct Vec4f {
        float x, y, z, w;

        Vec4f()
            : x(0),
              y(0),
              z(0),
              w(0) {}
        Vec4f(float x, float y, float z, float w)
            : x(x),
              y(y),
              z(z),
              w(w) {}
        explicit Vec4f(const Vec4& v)
            : x(static_cast<float>(v.x)),
              y(static_cast<float>(v.y)),
              z(static_cast<float>(v.z)),
              w(static_cast<float>(v.w)) {}

        float& operator[](int i) {
            assert(i >= 0 && i < 4);
            return i == 0 ? x : (i == 1 ? y : (i == 2 ? z : w));
        }
        float operator[](int i) const {
            assert(i >= 0 && i < 4);
            return i == 0 ? x : (i == 1 ? y : (i == 2 ? z : w));
        }

        Vec4f operator+(const Vec4f& v) const {
            return {x + v.x, y + v.y, z + v.z, w + v.w};
        }
        Vec4f operator-(const Vec4f& v) const {
            return {x - v.x, y - v.y, z - v.z, w - v.w};
        }
        Vec4f operator*(float s) const {
            return {x * s, y * s, z * s, w * s};
        }
        Vec4f operator/(float s) const {
            return {x / s, y / s, z / s, w / s};
        }
        Vec4f operator-() const {
            return {-x, -y, -z, -w};
        }

        Vec4f& operator+=(const Vec4f& v) {
            x += v.x;
            y += v.y;
            z += v.z;
            w += v.w;
            return *this;
        }
        Vec4f& operator-=(const Vec4f& v) {
            x -= v.x;
            y -= v.y;
            z -= v.z;
            w -= v.w;
            return *this;
        }
        Vec4f& operator*=(float s) {
            x *= s;
            y *= s;
            z *= s;
            w *= s;
            return *this;
        }
        Vec4f& operator/=(float s) {
            x /= s;
            y /= s;
            z /= s;
            w /= s;
            return *this;
        }

        bool operator==(const Vec4f& v) const {
            return x == v.x && y == v.y && z == v.z && w == v.w;
        }
        bool operator!=(const Vec4f& v) const {
            return !(*this == v);
        }

        float dot(const Vec4f& v) const {
            return x * v.x + y * v.y + z * v.z + w * v.w;
        }

        float norm() const {
            return std::sqrt(x * x + y * y + z * z + w * w);
        }
        float norm_squared() const {
            return x * x + y * y + z * z + w * w;
        }

        Vec4f normalized() const {
            float n = norm();
            return n > 1e-6f ? *this / n : Vec4f{0, 0, 0, 1};
        }

        bool is_finite() const noexcept {
            return std::isfinite(x) && std::isfinite(y) && std::isfinite(z) && std::isfinite(w);
        }
        bool try_normalized(Vec4f& out, float epsilon = 1.0e-6f) const noexcept {
            const float input[4] = {x, y, z, w};
            float output[4];
            if (!tc_detail_try_normalize_f32_components(input, 4, epsilon, output)) {
                return false;
            }
            out = {output[0], output[1], output[2], output[3]};
            return true;
        }
        Vec4f normalized_or(const Vec4f& fallback, float epsilon = 1.0e-6f) const noexcept {
            Vec4f result;
            return try_normalized(result, epsilon) ? result : fallback;
        }
        float* ptr() noexcept {
            return &x;
        }
        const float* ptr() const noexcept {
            return &x;
        }

        Vec4 to_double() const {
            return {x, y, z, w};
        }

        static Vec4f zero() {
            return {0, 0, 0, 0};
        }
        static Vec4f unit_x() {
            return {1, 0, 0, 0};
        }
        static Vec4f unit_y() {
            return {0, 1, 0, 0};
        }
        static Vec4f unit_z() {
            return {0, 0, 1, 0};
        }
        static Vec4f unit_w() {
            return {0, 0, 0, 1};
        }
    };

    inline Vec4f operator*(float s, const Vec4f& v) {
        return v * s;
    }

    inline Vec4f Vec4::to_float() const noexcept {
        return Vec4f{static_cast<float>(x), static_cast<float>(y), static_cast<float>(z), static_cast<float>(w)};
    }

    static_assert(std::is_standard_layout<Vec4>::value, "Vec4 must stay standard layout");
    static_assert(std::is_trivially_copyable<Vec4>::value, "Vec4 must stay trivially copyable");
    static_assert(sizeof(Vec4) == sizeof(double) * 4, "Vec4 must stay packed");
    static_assert(offsetof(Vec4, x) == 0, "Vec4.x offset changed");
    static_assert(offsetof(Vec4, w) == sizeof(double) * 3, "Vec4.w offset changed");
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
