// tcbase/types/geom_types.h - ABI-friendly geometry POD types
#ifndef TCBASE_TYPES_GEOM_TYPES_H
#define TCBASE_TYPES_GEOM_TYPES_H

#include <stddef.h>

#ifdef __cplusplus
#include <cassert>
#include <cmath>
#include <geom/tc_checked_normalization.h>
#include <geom/tc_lerp_detail.h>
#include <geom/tc_quat_detail.h>
#include <limits>

namespace termin {
    struct Bounds2;
    struct Mat44;
    struct Rect2;
} // namespace termin

struct tc_rect2f;
struct tc_vec2f;
struct tc_vec3f;
#endif

#ifdef __cplusplus

struct tc_vec2 {
    double x = 0.0;
    double y = 0.0;

    constexpr tc_vec2() noexcept = default;
    constexpr tc_vec2(double x, double y) noexcept
        : x(x),
          y(y) {}

    double& operator[](int i) noexcept {
        assert(i >= 0 && i < 2);
        return i == 0 ? x : y;
    }
    double operator[](int i) const noexcept {
        assert(i >= 0 && i < 2);
        return i == 0 ? x : y;
    }

    tc_vec2 operator+(const tc_vec2& v) const noexcept {
        return {x + v.x, y + v.y};
    }
    tc_vec2 operator-(const tc_vec2& v) const noexcept {
        return {x - v.x, y - v.y};
    }
    tc_vec2 operator*(double s) const noexcept {
        return {x * s, y * s};
    }
    tc_vec2 operator/(double s) const noexcept {
        return {x / s, y / s};
    }
    tc_vec2 operator-() const noexcept {
        return {-x, -y};
    }

    tc_vec2& operator+=(const tc_vec2& v) noexcept {
        x += v.x;
        y += v.y;
        return *this;
    }
    tc_vec2& operator-=(const tc_vec2& v) noexcept {
        x -= v.x;
        y -= v.y;
        return *this;
    }
    tc_vec2& operator*=(double s) noexcept {
        x *= s;
        y *= s;
        return *this;
    }
    tc_vec2& operator/=(double s) noexcept {
        x /= s;
        y /= s;
        return *this;
    }

    bool operator==(const tc_vec2& v) const noexcept {
        return x == v.x && y == v.y;
    }
    bool operator!=(const tc_vec2& v) const noexcept {
        return !(*this == v);
    }

    double dot(const tc_vec2& v) const noexcept {
        return x * v.x + y * v.y;
    }
    double cross(const tc_vec2& v) const noexcept {
        return x * v.y - y * v.x;
    }

    double norm() const noexcept {
        return std::sqrt(x * x + y * y);
    }
    double norm_squared() const noexcept {
        return x * x + y * y;
    }

    tc_vec2 normalized() const noexcept {
        double n = norm();
        return n > 1e-10 ? *this / n : tc_vec2{1.0, 0.0};
    }

    bool is_finite() const noexcept {
        return std::isfinite(x) && std::isfinite(y);
    }
    bool try_normalized(tc_vec2& out, double epsilon = 1.0e-10) const noexcept {
        const double input[2] = {x, y};
        double output[2];
        if (!tc_detail_try_normalize_f64_components(input, 2, epsilon, output)) {
            return false;
        }
        out = {output[0], output[1]};
        return true;
    }
    tc_vec2 normalized_or(const tc_vec2& fallback, double epsilon = 1.0e-10) const noexcept {
        tc_vec2 result;
        return try_normalized(result, epsilon) ? result : fallback;
    }
    double* ptr() noexcept {
        return &x;
    }
    const double* ptr() const noexcept {
        return &x;
    }
    tc_vec2 cwise_product(const tc_vec2& v) const noexcept {
        return {x * v.x, y * v.y};
    }
    tc_vec2 cwise_quotient(const tc_vec2& v) const noexcept {
        return {x / v.x, y / v.y};
    }
    tc_vec2 cwise_min(const tc_vec2& v) const noexcept {
        return {x < v.x ? x : v.x, y < v.y ? y : v.y};
    }
    tc_vec2 cwise_max(const tc_vec2& v) const noexcept {
        return {x > v.x ? x : v.x, y > v.y ? y : v.y};
    }
    tc_vec2 clamped(const tc_vec2& minimum, const tc_vec2& maximum) const noexcept {
        return {x < minimum.x ? minimum.x : (x > maximum.x ? maximum.x : x),
                y < minimum.y ? minimum.y : (y > maximum.y ? maximum.y : y)};
    }
    tc_vec2 cwise_abs() const noexcept {
        return {std::abs(x), std::abs(y)};
    }
    double min_component() const noexcept {
        return x < y ? x : y;
    }
    double max_component() const noexcept {
        return x > y ? x : y;
    }
    tc_vec2f to_float() const noexcept;

    static tc_vec2 zero() {
        return {0.0, 0.0};
    }
    static tc_vec2 unit_x() {
        return {1.0, 0.0};
    }
    static tc_vec2 unit_y() {
        return {0.0, 1.0};
    }
};

extern "C++" {
inline tc_vec2 operator*(double s, const tc_vec2& v) noexcept {
    return v * s;
}
}

struct tc_vec2f {
    float x = 0.0f;
    float y = 0.0f;

    constexpr tc_vec2f() noexcept = default;
    constexpr tc_vec2f(float x, float y) noexcept
        : x(x),
          y(y) {}
    explicit tc_vec2f(const tc_vec2& v) noexcept
        : x(static_cast<float>(v.x)),
          y(static_cast<float>(v.y)) {}

    float& operator[](int i) noexcept {
        assert(i >= 0 && i < 2);
        return i == 0 ? x : y;
    }
    float operator[](int i) const noexcept {
        assert(i >= 0 && i < 2);
        return i == 0 ? x : y;
    }

    tc_vec2f operator+(const tc_vec2f& v) const noexcept {
        return {x + v.x, y + v.y};
    }
    tc_vec2f operator-(const tc_vec2f& v) const noexcept {
        return {x - v.x, y - v.y};
    }
    tc_vec2f operator*(float s) const noexcept {
        return {x * s, y * s};
    }
    tc_vec2f operator/(float s) const noexcept {
        return {x / s, y / s};
    }
    tc_vec2f operator-() const noexcept {
        return {-x, -y};
    }

    tc_vec2f& operator+=(const tc_vec2f& v) noexcept {
        x += v.x;
        y += v.y;
        return *this;
    }
    tc_vec2f& operator-=(const tc_vec2f& v) noexcept {
        x -= v.x;
        y -= v.y;
        return *this;
    }
    tc_vec2f& operator*=(float s) noexcept {
        x *= s;
        y *= s;
        return *this;
    }
    tc_vec2f& operator/=(float s) noexcept {
        x /= s;
        y /= s;
        return *this;
    }

    bool operator==(const tc_vec2f& v) const noexcept {
        return x == v.x && y == v.y;
    }
    bool operator!=(const tc_vec2f& v) const noexcept {
        return !(*this == v);
    }

    float dot(const tc_vec2f& v) const noexcept {
        return x * v.x + y * v.y;
    }
    float cross(const tc_vec2f& v) const noexcept {
        return x * v.y - y * v.x;
    }

    float norm() const noexcept {
        return std::sqrt(x * x + y * y);
    }
    float norm_squared() const noexcept {
        return x * x + y * y;
    }

    tc_vec2f normalized() const noexcept {
        float n = norm();
        return n > 1e-6f ? *this / n : tc_vec2f{1.0f, 0.0f};
    }

    bool is_finite() const noexcept {
        return std::isfinite(x) && std::isfinite(y);
    }
    bool try_normalized(tc_vec2f& out, float epsilon = 1.0e-6f) const noexcept {
        const float input[2] = {x, y};
        float output[2];
        if (!tc_detail_try_normalize_f32_components(input, 2, epsilon, output)) {
            return false;
        }
        out = {output[0], output[1]};
        return true;
    }
    tc_vec2f normalized_or(const tc_vec2f& fallback, float epsilon = 1.0e-6f) const noexcept {
        tc_vec2f result;
        return try_normalized(result, epsilon) ? result : fallback;
    }
    float* ptr() noexcept {
        return &x;
    }
    const float* ptr() const noexcept {
        return &x;
    }
    tc_vec2f cwise_product(const tc_vec2f& v) const noexcept {
        return {x * v.x, y * v.y};
    }
    tc_vec2f cwise_quotient(const tc_vec2f& v) const noexcept {
        return {x / v.x, y / v.y};
    }
    tc_vec2f cwise_min(const tc_vec2f& v) const noexcept {
        return {x < v.x ? x : v.x, y < v.y ? y : v.y};
    }
    tc_vec2f cwise_max(const tc_vec2f& v) const noexcept {
        return {x > v.x ? x : v.x, y > v.y ? y : v.y};
    }
    tc_vec2f clamped(const tc_vec2f& minimum, const tc_vec2f& maximum) const noexcept {
        return {x < minimum.x ? minimum.x : (x > maximum.x ? maximum.x : x),
                y < minimum.y ? minimum.y : (y > maximum.y ? maximum.y : y)};
    }
    tc_vec2f cwise_abs() const noexcept {
        return {std::abs(x), std::abs(y)};
    }
    float min_component() const noexcept {
        return x < y ? x : y;
    }
    float max_component() const noexcept {
        return x > y ? x : y;
    }

    tc_vec2 to_double() const noexcept {
        return {x, y};
    }

    static tc_vec2f zero() {
        return {0.0f, 0.0f};
    }
    static tc_vec2f unit_x() {
        return {1.0f, 0.0f};
    }
    static tc_vec2f unit_y() {
        return {0.0f, 1.0f};
    }
};

extern "C++" {
inline tc_vec2f operator*(float s, const tc_vec2f& v) noexcept {
    return v * s;
}
}

inline tc_vec2f tc_vec2::to_float() const noexcept {
    return tc_vec2f{static_cast<float>(x), static_cast<float>(y)};
}

struct tc_size2f {
    float width = 0.0f;
    float height = 0.0f;

    constexpr tc_size2f() noexcept = default;
    constexpr tc_size2f(float width, float height) noexcept
        : width(width),
          height(height) {}

    bool operator==(const tc_size2f& other) const {
        return width == other.width && height == other.height;
    }
    bool operator!=(const tc_size2f& other) const {
        return !(*this == other);
    }
};

struct tc_bounds2f {
    float x0 = 0.0f;
    float y0 = 0.0f;
    float x1 = 0.0f;
    float y1 = 0.0f;

    constexpr tc_bounds2f() noexcept = default;
    constexpr tc_bounds2f(float x0, float y0, float x1, float y1) noexcept
        : x0(x0),
          y0(y0),
          x1(x1),
          y1(y1) {}

    float width() const noexcept {
        return x1 - x0;
    }
    float height() const noexcept {
        return y1 - y0;
    }
    bool is_finite() const noexcept {
        return std::isfinite(x0) && std::isfinite(y0) && std::isfinite(x1) && std::isfinite(y1);
    }
    bool is_valid() const noexcept {
        return is_finite() && x0 <= x1 && y0 <= y1;
    }
    tc_vec2f min() const noexcept {
        return {x0, y0};
    }
    tc_vec2f max() const noexcept {
        return {x1, y1};
    }
    tc_vec2f center() const noexcept {
        return {(x0 + x1) * 0.5f, (y0 + y1) * 0.5f};
    }
    void extend(const tc_vec2f& point) noexcept {
        x0 = x0 < point.x ? x0 : point.x;
        y0 = y0 < point.y ? y0 : point.y;
        x1 = x1 > point.x ? x1 : point.x;
        y1 = y1 > point.y ? y1 : point.y;
    }
    bool contains_closed(const tc_vec2f& point) const noexcept {
        return point.x >= x0 && point.x <= x1 && point.y >= y0 && point.y <= y1;
    }
    bool contains_half_open(const tc_vec2f& point) const noexcept {
        return point.x >= x0 && point.x < x1 && point.y >= y0 && point.y < y1;
    }
    tc_bounds2f expanded(float amount) const noexcept {
        return {x0 - amount, y0 - amount, x1 + amount, y1 + amount};
    }
    tc_bounds2f merged(const tc_bounds2f& other) const noexcept {
        return {x0 < other.x0 ? x0 : other.x0,
                y0 < other.y0 ? y0 : other.y0,
                x1 > other.x1 ? x1 : other.x1,
                y1 > other.y1 ? y1 : other.y1};
    }
    bool try_intersection(const tc_bounds2f& other, tc_bounds2f& out) const noexcept {
        const tc_bounds2f result{
            x0 > other.x0 ? x0 : other.x0,
            y0 > other.y0 ? y0 : other.y0,
            x1 < other.x1 ? x1 : other.x1,
            y1 < other.y1 ? y1 : other.y1,
        };
        if (!result.is_valid()) {
            return false;
        }
        out = result;
        return true;
    }
    tc_rect2f to_rect() const noexcept;
    termin::Bounds2 to_double() const noexcept;
};

struct tc_rect2f {
    float x = 0.0f;
    float y = 0.0f;
    float width = 0.0f;
    float height = 0.0f;

    constexpr tc_rect2f() noexcept = default;
    constexpr tc_rect2f(float x, float y, float width, float height) noexcept
        : x(x),
          y(y),
          width(width),
          height(height) {}

    bool is_finite() const noexcept {
        return std::isfinite(x) && std::isfinite(y) && std::isfinite(width) && std::isfinite(height);
    }
    bool is_valid() const noexcept {
        return is_finite() && width >= 0.0f && height >= 0.0f;
    }
    tc_vec2f origin() const noexcept {
        return {x, y};
    }
    tc_vec2f size() const noexcept {
        return {width, height};
    }
    tc_vec2f center() const noexcept {
        return {x + width * 0.5f, y + height * 0.5f};
    }
    tc_vec2f min() const noexcept {
        return {x, y};
    }
    tc_vec2f max() const noexcept {
        return {x + width, y + height};
    }
    bool contains_closed(const tc_vec2f& point) const noexcept {
        return point.x >= x && point.x <= x + width && point.y >= y && point.y <= y + height;
    }
    bool contains_half_open(const tc_vec2f& point) const noexcept {
        return point.x >= x && point.x < x + width && point.y >= y && point.y < y + height;
    }
    tc_bounds2f bounds() const noexcept {
        return {x, y, x + width, y + height};
    }
    termin::Rect2 to_double() const noexcept;
};

inline tc_rect2f tc_bounds2f::to_rect() const noexcept {
    return {x0, y0, width(), height()};
}

struct tc_vec3 {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;

    constexpr tc_vec3() noexcept = default;
    constexpr tc_vec3(double x, double y, double z) noexcept
        : x(x),
          y(y),
          z(z) {}

    double& operator[](int i) noexcept {
        assert(i >= 0 && i < 3);
        return i == 0 ? x : (i == 1 ? y : z);
    }
    double operator[](int i) const noexcept {
        assert(i >= 0 && i < 3);
        return i == 0 ? x : (i == 1 ? y : z);
    }

    tc_vec3 operator+(const tc_vec3& v) const noexcept {
        return {x + v.x, y + v.y, z + v.z};
    }
    tc_vec3 operator-(const tc_vec3& v) const noexcept {
        return {x - v.x, y - v.y, z - v.z};
    }
    tc_vec3 operator*(double s) const noexcept {
        return {x * s, y * s, z * s};
    }
    tc_vec3 operator/(double s) const noexcept {
        return {x / s, y / s, z / s};
    }
    tc_vec3 operator-() const noexcept {
        return {-x, -y, -z};
    }

    tc_vec3& operator+=(const tc_vec3& v) noexcept {
        x += v.x;
        y += v.y;
        z += v.z;
        return *this;
    }
    tc_vec3& operator-=(const tc_vec3& v) noexcept {
        x -= v.x;
        y -= v.y;
        z -= v.z;
        return *this;
    }
    tc_vec3& operator*=(double s) noexcept {
        x *= s;
        y *= s;
        z *= s;
        return *this;
    }
    tc_vec3& operator/=(double s) noexcept {
        x /= s;
        y /= s;
        z /= s;
        return *this;
    }

    bool operator==(const tc_vec3& v) const noexcept {
        return x == v.x && y == v.y && z == v.z;
    }
    bool operator!=(const tc_vec3& v) const noexcept {
        return !(*this == v);
    }

    double dot(const tc_vec3& v) const noexcept {
        return x * v.x + y * v.y + z * v.z;
    }

    tc_vec3 cross(const tc_vec3& v) const noexcept {
        return {y * v.z - z * v.y, z * v.x - x * v.z, x * v.y - y * v.x};
    }

    double norm() const noexcept {
        return std::sqrt(x * x + y * y + z * z);
    }
    double norm_squared() const noexcept {
        return x * x + y * y + z * z;
    }
    bool is_finite() const noexcept {
        return std::isfinite(x) && std::isfinite(y) && std::isfinite(z);
    }

    tc_vec3 normalized() const noexcept {
        double n = norm();
        double nan = std::numeric_limits<double>::quiet_NaN();
        return n > 1e-10 ? *this / n : tc_vec3{nan, nan, nan};
    }

    bool try_normalized(tc_vec3& out, double epsilon = 1.0e-10) const noexcept {
        const double input[3] = {x, y, z};
        double output[3];
        if (!tc_detail_try_normalize_f64_components(input, 3, epsilon, output)) {
            return false;
        }
        out = {output[0], output[1], output[2]};
        return true;
    }
    tc_vec3 normalized_or(const tc_vec3& fallback, double epsilon = 1.0e-10) const noexcept {
        tc_vec3 result;
        return try_normalized(result, epsilon) ? result : fallback;
    }
    static tc_vec3 lerp(const tc_vec3& a, const tc_vec3& b, double t) noexcept {
        return {tc_detail_lerp_f64_component(a.x, b.x, t),
                tc_detail_lerp_f64_component(a.y, b.y, t),
                tc_detail_lerp_f64_component(a.z, b.z, t)};
    }
    double* ptr() noexcept {
        return &x;
    }
    const double* ptr() const noexcept {
        return &x;
    }
    tc_vec3 cwise_product(const tc_vec3& v) const noexcept {
        return {x * v.x, y * v.y, z * v.z};
    }
    tc_vec3 cwise_quotient(const tc_vec3& v) const noexcept {
        return {x / v.x, y / v.y, z / v.z};
    }
    tc_vec3 cwise_min(const tc_vec3& v) const noexcept {
        return {x < v.x ? x : v.x, y < v.y ? y : v.y, z < v.z ? z : v.z};
    }
    tc_vec3 cwise_max(const tc_vec3& v) const noexcept {
        return {x > v.x ? x : v.x, y > v.y ? y : v.y, z > v.z ? z : v.z};
    }
    tc_vec3 clamped(const tc_vec3& minimum, const tc_vec3& maximum) const noexcept {
        return {x < minimum.x ? minimum.x : (x > maximum.x ? maximum.x : x),
                y < minimum.y ? minimum.y : (y > maximum.y ? maximum.y : y),
                z < minimum.z ? minimum.z : (z > maximum.z ? maximum.z : z)};
    }
    tc_vec3 cwise_abs() const noexcept {
        return {std::abs(x), std::abs(y), std::abs(z)};
    }
    double min_component() const noexcept {
        const double yz = y < z ? y : z;
        return x < yz ? x : yz;
    }
    double max_component() const noexcept {
        const double yz = y > z ? y : z;
        return x > yz ? x : yz;
    }
    // Narrows finite components that lie within the finite float range without
    // underflowing a non-zero component to zero. Any failure leaves out unchanged.
    bool try_to_float(tc_vec3f& out) const noexcept;
    tc_vec3f to_float() const noexcept;

    static double angle(const tc_vec3& a, const tc_vec3& b) {
        double d = a.normalized().dot(b.normalized());
        d = d < -1.0 ? -1.0 : (d > 1.0 ? 1.0 : d);
        return std::acos(d);
    }

    static double angle_degrees(const tc_vec3& a, const tc_vec3& b) {
        return angle(a, b) * 180.0 / 3.14159265358979323846;
    }

    static tc_vec3 zero() {
        return {0, 0, 0};
    }
    static tc_vec3 unit_x() {
        return {1, 0, 0};
    }
    static tc_vec3 unit_y() {
        return {0, 1, 0};
    }
    static tc_vec3 unit_z() {
        return {0, 0, 1};
    }
    static tc_vec3 right() {
        return unit_x();
    }
    static tc_vec3 left() {
        return {-1, 0, 0};
    }
    static tc_vec3 forward() {
        return unit_y();
    }
    static tc_vec3 backward() {
        return {0, -1, 0};
    }
    static tc_vec3 up() {
        return unit_z();
    }
    static tc_vec3 down() {
        return {0, 0, -1};
    }
};

extern "C++" {
inline tc_vec3 operator*(double s, const tc_vec3& v) noexcept {
    return v * s;
}
}

struct tc_ray3 {
    tc_vec3 origin;
    tc_vec3 direction;

    constexpr tc_ray3() noexcept
        : origin(0.0, 0.0, 0.0),
          direction(0.0, 0.0, 1.0) {}

    tc_ray3(const tc_vec3& origin, const tc_vec3& dir)
        : origin(origin),
          direction(dir) {
        const double n = std::hypot(dir.x, dir.y, dir.z);
        if (dir.is_finite() && std::isfinite(n) && n > 1.0e-10) {
            direction = dir / n;
        }
    }

    tc_vec3 point_at(double t) const {
        return origin + direction * t;
    }
};

struct tc_quat {
    // Raw packed xyzw coefficients. rotate/inverse_rotate/to_matrix are finite
    // unit-quaternion fast paths; use their try_ counterparts for uncertain
    // runtime input.
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
    double w = 1.0;

    constexpr tc_quat() noexcept = default;
    constexpr tc_quat(double x, double y, double z, double w) noexcept
        : x(x),
          y(y),
          z(z),
          w(w) {}

    static constexpr tc_quat identity() noexcept {
        return {0, 0, 0, 1};
    }

    tc_quat operator*(const tc_quat& q) const noexcept {
        return {w * q.x + x * q.w + y * q.z - z * q.y,
                w * q.y - x * q.z + y * q.w + z * q.x,
                w * q.z + x * q.y - y * q.x + z * q.w,
                w * q.w - x * q.x - y * q.y - z * q.z};
    }

    tc_quat conjugate() const noexcept {
        return {-x, -y, -z, w};
    }

    double dot(const tc_quat& other) const noexcept {
        return x * other.x + y * other.y + z * other.z + w * other.w;
    }

    double norm_squared() const noexcept {
        return dot(*this);
    }

    double norm() const noexcept {
        const double squared = norm_squared();
        // A positive subnormal sum may already have lost a material fraction
        // of its terms. Use hypot for that range as well as complete under/overflow.
        if (std::isnormal(squared)) {
            return std::sqrt(squared);
        }
        return std::hypot(std::hypot(x, y), std::hypot(z, w));
    }

    bool is_finite() const noexcept {
        return std::isfinite(x) && std::isfinite(y) && std::isfinite(z) && std::isfinite(w);
    }

    bool try_normalized(tc_quat& out, double epsilon = 1.0e-12) const noexcept {
        const double input[4] = {x, y, z, w};
        double output[4];
        if (!tc_detail_try_normalize_f64_components(input, 4, epsilon, output)) {
            return false;
        }
        out = {output[0], output[1], output[2], output[3]};
        return true;
    }

    tc_quat normalized_or(const tc_quat& fallback, double epsilon = 1.0e-12) const noexcept {
        tc_quat result;
        return try_normalized(result, epsilon) ? result : fallback;
    }

    tc_quat normalized(double epsilon = 1.0e-12) const noexcept {
        tc_quat result;
        if (try_normalized(result, epsilon)) {
            return result;
        }
        const double nan = std::numeric_limits<double>::quiet_NaN();
        return {nan, nan, nan, nan};
    }

    bool try_inverse(tc_quat& out, double epsilon = 1.0e-12) const noexcept {
        const double input[4] = {x, y, z, w};
        double result[4];
        if (!tc_detail_try_inverse_quat_f64_components(input, epsilon, result)) {
            return false;
        }
        out = {result[0], result[1], result[2], result[3]};
        return true;
    }

    tc_quat inverse(double epsilon = 1.0e-12) const noexcept {
        tc_quat result;
        if (try_inverse(result, epsilon)) {
            return result;
        }
        const double nan = std::numeric_limits<double>::quiet_NaN();
        return {nan, nan, nan, nan};
    }

    // Fast path: both the quaternion and vector must be finite and the
    // quaternion must have unit norm. Use try_rotate for uncertain input.
    tc_vec3 rotate(const tc_vec3& v) const noexcept {
        double tx = 2.0 * (y * v.z - z * v.y);
        double ty = 2.0 * (z * v.x - x * v.z);
        double tz = 2.0 * (x * v.y - y * v.x);

        return {v.x + w * tx + y * tz - z * ty, v.y + w * ty + z * tx - x * tz, v.z + w * tz + x * ty - y * tx};
    }

    // Fast path with the same finite unit-quaternion precondition as rotate.
    tc_vec3 inverse_rotate(const tc_vec3& v) const noexcept {
        return conjugate().rotate(v);
    }

    bool try_rotate(const tc_vec3& v, tc_vec3& out, double epsilon = 1.0e-12) const noexcept {
        tc_quat unit;
        if (!try_normalized(unit, epsilon)) {
            return false;
        }
        const double quat[4] = {unit.x, unit.y, unit.z, unit.w};
        const double vector[3] = {v.x, v.y, v.z};
        double result[3];
        if (!tc_detail_try_rotate_unit_quat_f64_components(quat, vector, false, result)) {
            return false;
        }
        out = {result[0], result[1], result[2]};
        return true;
    }

    bool try_inverse_rotate(const tc_vec3& v, tc_vec3& out, double epsilon = 1.0e-12) const noexcept {
        tc_quat unit;
        if (!try_normalized(unit, epsilon)) {
            return false;
        }
        const double quat[4] = {unit.x, unit.y, unit.z, unit.w};
        const double vector[3] = {v.x, v.y, v.z};
        double result[3];
        if (!tc_detail_try_rotate_unit_quat_f64_components(quat, vector, true, result)) {
            return false;
        }
        out = {result[0], result[1], result[2]};
        return true;
    }

    static bool
    try_from_axis_angle(const tc_vec3& axis, double angle, tc_quat& out, double epsilon = 1.0e-12) noexcept {
        const double axis_components[3] = {axis.x, axis.y, axis.z};
        double result[4];
        if (!tc_detail_try_quat_from_axis_angle_f64_components(axis_components, angle, epsilon, result)) {
            return false;
        }
        out = {result[0], result[1], result[2], result[3]};
        return true;
    }

    static tc_quat from_axis_angle(const tc_vec3& axis, double angle) {
        tc_quat result;
        if (try_from_axis_angle(axis, angle, result)) {
            return result;
        }
        const double nan = std::numeric_limits<double>::quiet_NaN();
        return {nan, nan, nan, nan};
    }

    static tc_quat look_rotation(const tc_vec3& forward, const tc_vec3& up = tc_vec3::unit_z()) {
        tc_vec3 f = forward.normalized();
        tc_vec3 r = f.cross(up).normalized();
        tc_vec3 u = r.cross(f);

        double m[9] = {r.x, f.x, u.x, r.y, f.y, u.y, r.z, f.z, u.z};
        return from_rotation_matrix(m);
    }

    static bool
    try_slerp(const tc_quat& a, const tc_quat& b, double t, tc_quat& out, double epsilon = 1.0e-12) noexcept {
        if (!std::isfinite(t) || !std::isfinite(epsilon) || epsilon < 0.0) {
            return false;
        }

        tc_quat from;
        tc_quat to;
        if (!a.try_normalized(from, epsilon) || !b.try_normalized(to, epsilon)) {
            return false;
        }

        double normalized_dot = from.dot(to);
        if (!std::isfinite(normalized_dot)) {
            return false;
        }
        if (normalized_dot < 0.0) {
            to = {-to.x, -to.y, -to.z, -to.w};
            normalized_dot = -normalized_dot;
        }
        if (normalized_dot > 1.0) {
            normalized_dot = 1.0;
        }

        tc_quat interpolated;
        if (normalized_dot > 0.9995) {
            interpolated = {from.x + t * (to.x - from.x),
                            from.y + t * (to.y - from.y),
                            from.z + t * (to.z - from.z),
                            from.w + t * (to.w - from.w)};
        } else {
            const double theta = std::acos(normalized_dot);
            const double sin_theta = std::sin(theta);
            const double from_angle = (1.0 - t) * theta;
            const double to_angle = t * theta;
            if (!std::isfinite(theta) || !std::isfinite(sin_theta) || sin_theta == 0.0 || !std::isfinite(from_angle) ||
                !std::isfinite(to_angle)) {
                return false;
            }
            const double from_weight = std::sin(from_angle) / sin_theta;
            const double to_weight = std::sin(to_angle) / sin_theta;
            interpolated = {from_weight * from.x + to_weight * to.x,
                            from_weight * from.y + to_weight * to.y,
                            from_weight * from.z + to_weight * to.z,
                            from_weight * from.w + to_weight * to.w};
        }

        tc_quat result;
        if (!interpolated.try_normalized(result, epsilon)) {
            return false;
        }
        out = result;
        return true;
    }

    static tc_quat slerp(const tc_quat& a, const tc_quat& b, double t, double epsilon = 1.0e-12) noexcept {
        tc_quat result;
        if (try_slerp(a, b, t, result, epsilon)) {
            return result;
        }
        const double nan = std::numeric_limits<double>::quiet_NaN();
        return {nan, nan, nan, nan};
    }

    static bool try_from_euler(const tc_vec3& euler_xyz, tc_quat& out) noexcept {
        if (!euler_xyz.is_finite()) {
            return false;
        }

        const double cx = std::cos(euler_xyz.x * 0.5);
        const double sx = std::sin(euler_xyz.x * 0.5);
        const double cy = std::cos(euler_xyz.y * 0.5);
        const double sy = std::sin(euler_xyz.y * 0.5);
        const double cz = std::cos(euler_xyz.z * 0.5);
        const double sz = std::sin(euler_xyz.z * 0.5);
        const tc_quat raw{sx * cy * cz - cx * sy * sz,
                          cx * sy * cz + sx * cy * sz,
                          cx * cy * sz - sx * sy * cz,
                          cx * cy * cz + sx * sy * sz};
        tc_quat result;
        if (!raw.try_normalized(result, 0.0)) {
            return false;
        }
        out = result;
        return true;
    }

    static tc_quat from_euler(const tc_vec3& euler_xyz) noexcept {
        tc_quat result;
        if (try_from_euler(euler_xyz, result)) {
            return result;
        }
        const double nan = std::numeric_limits<double>::quiet_NaN();
        return {nan, nan, nan, nan};
    }

    bool try_to_euler(tc_vec3& out, double epsilon = 1.0e-12) const noexcept {
        tc_quat q;
        if (!try_normalized(q, epsilon)) {
            return false;
        }

        double sin_pitch = 2.0 * (q.w * q.y - q.z * q.x);
        if (sin_pitch > 1.0) {
            sin_pitch = 1.0;
        } else if (sin_pitch < -1.0) {
            sin_pitch = -1.0;
        }

        tc_vec3 result;
        if (std::abs(sin_pitch) >= 1.0 - 1.0e-12) {
            // XYZ gimbal policy: choose roll = 0 and retain the uniquely
            // observable combined Z rotation in yaw.
            result.x = 0.0;
            result.y = std::copysign(0.5 * 3.14159265358979323846, sin_pitch);
            result.z = std::atan2(2.0 * (q.w * q.z - q.x * q.y), 1.0 - 2.0 * (q.x * q.x + q.z * q.z));
        } else {
            result.x = std::atan2(2.0 * (q.w * q.x + q.y * q.z), 1.0 - 2.0 * (q.x * q.x + q.y * q.y));
            result.y = std::asin(sin_pitch);
            result.z = std::atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z));
        }
        if (!result.is_finite()) {
            return false;
        }
        out = result;
        return true;
    }

    tc_vec3 to_euler(double epsilon = 1.0e-12) const noexcept {
        tc_vec3 result;
        if (try_to_euler(result, epsilon)) {
            return result;
        }
        const double nan = std::numeric_limits<double>::quiet_NaN();
        return {nan, nan, nan};
    }

    static tc_quat from_rotation_matrix(const double* m) {
        double trace = m[0] + m[4] + m[8];
        double x, y, z, w;

        if (trace > 0) {
            double s = 0.5 / std::sqrt(trace + 1.0);
            w = 0.25 / s;
            x = (m[7] - m[5]) * s;
            y = (m[2] - m[6]) * s;
            z = (m[3] - m[1]) * s;
        } else if (m[0] > m[4] && m[0] > m[8]) {
            double s = 2.0 * std::sqrt(1.0 + m[0] - m[4] - m[8]);
            w = (m[7] - m[5]) / s;
            x = 0.25 * s;
            y = (m[1] + m[3]) / s;
            z = (m[2] + m[6]) / s;
        } else if (m[4] > m[8]) {
            double s = 2.0 * std::sqrt(1.0 + m[4] - m[0] - m[8]);
            w = (m[2] - m[6]) / s;
            x = (m[1] + m[3]) / s;
            y = 0.25 * s;
            z = (m[5] + m[7]) / s;
        } else {
            double s = 2.0 * std::sqrt(1.0 + m[8] - m[0] - m[4]);
            w = (m[3] - m[1]) / s;
            x = (m[2] + m[6]) / s;
            y = (m[5] + m[7]) / s;
            z = 0.25 * s;
        }

        return tc_quat{x, y, z, w}.normalized();
    }

    bool try_to_matrix(double* out_row_major_9, double epsilon = 1.0e-12) const noexcept {
        if (out_row_major_9 == nullptr) {
            return false;
        }
        tc_quat unit;
        if (!try_normalized(unit, epsilon)) {
            return false;
        }
        double result[9];
        unit.to_matrix(result);
        for (double coefficient : result) {
            if (!std::isfinite(coefficient)) {
                return false;
            }
        }
        for (int i = 0; i < 9; ++i) {
            out_row_major_9[i] = result[i];
        }
        return true;
    }

    // Fast row-major 3x3 conversion. The quaternion must be finite and unit;
    // use try_to_matrix for uncertain input.
    void to_matrix(double* m) const noexcept {
        const double quat[4] = {x, y, z, w};
        tc_detail_unit_quat_to_matrix3_row_major_f64(quat, m);
    }
};

struct tc_vec3f {
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;

    constexpr tc_vec3f() noexcept = default;
    constexpr tc_vec3f(float x, float y, float z) noexcept
        : x(x),
          y(y),
          z(z) {}
    explicit tc_vec3f(const tc_vec3& v) noexcept
        : x(static_cast<float>(v.x)),
          y(static_cast<float>(v.y)),
          z(static_cast<float>(v.z)) {}

    float& operator[](int i) noexcept {
        assert(i >= 0 && i < 3);
        return i == 0 ? x : (i == 1 ? y : z);
    }
    float operator[](int i) const noexcept {
        assert(i >= 0 && i < 3);
        return i == 0 ? x : (i == 1 ? y : z);
    }

    tc_vec3f operator+(const tc_vec3f& v) const noexcept {
        return {x + v.x, y + v.y, z + v.z};
    }
    tc_vec3f operator-(const tc_vec3f& v) const noexcept {
        return {x - v.x, y - v.y, z - v.z};
    }
    tc_vec3f operator*(float s) const noexcept {
        return {x * s, y * s, z * s};
    }
    tc_vec3f operator/(float s) const noexcept {
        return {x / s, y / s, z / s};
    }
    tc_vec3f operator-() const noexcept {
        return {-x, -y, -z};
    }

    tc_vec3f& operator+=(const tc_vec3f& v) noexcept {
        x += v.x;
        y += v.y;
        z += v.z;
        return *this;
    }
    tc_vec3f& operator-=(const tc_vec3f& v) noexcept {
        x -= v.x;
        y -= v.y;
        z -= v.z;
        return *this;
    }
    tc_vec3f& operator*=(float s) noexcept {
        x *= s;
        y *= s;
        z *= s;
        return *this;
    }
    tc_vec3f& operator/=(float s) noexcept {
        x /= s;
        y /= s;
        z /= s;
        return *this;
    }

    bool operator==(const tc_vec3f& v) const noexcept {
        return x == v.x && y == v.y && z == v.z;
    }
    bool operator!=(const tc_vec3f& v) const noexcept {
        return !(*this == v);
    }

    float dot(const tc_vec3f& v) const noexcept {
        return x * v.x + y * v.y + z * v.z;
    }

    tc_vec3f cross(const tc_vec3f& v) const noexcept {
        return {y * v.z - z * v.y, z * v.x - x * v.z, x * v.y - y * v.x};
    }

    float norm() const noexcept {
        return std::sqrt(x * x + y * y + z * z);
    }
    float norm_squared() const noexcept {
        return x * x + y * y + z * z;
    }

    tc_vec3f normalized() const noexcept {
        float n = norm();
        return n > 1e-6f ? *this / n : tc_vec3f{0, 0, 1};
    }

    bool is_finite() const noexcept {
        return std::isfinite(x) && std::isfinite(y) && std::isfinite(z);
    }
    bool try_normalized(tc_vec3f& out, float epsilon = 1.0e-6f) const noexcept {
        const float input[3] = {x, y, z};
        float output[3];
        if (!tc_detail_try_normalize_f32_components(input, 3, epsilon, output)) {
            return false;
        }
        out = {output[0], output[1], output[2]};
        return true;
    }
    tc_vec3f normalized_or(const tc_vec3f& fallback, float epsilon = 1.0e-6f) const noexcept {
        tc_vec3f result;
        return try_normalized(result, epsilon) ? result : fallback;
    }
    float* ptr() noexcept {
        return &x;
    }
    const float* ptr() const noexcept {
        return &x;
    }
    tc_vec3f cwise_product(const tc_vec3f& v) const noexcept {
        return {x * v.x, y * v.y, z * v.z};
    }
    tc_vec3f cwise_quotient(const tc_vec3f& v) const noexcept {
        return {x / v.x, y / v.y, z / v.z};
    }
    tc_vec3f cwise_min(const tc_vec3f& v) const noexcept {
        return {x < v.x ? x : v.x, y < v.y ? y : v.y, z < v.z ? z : v.z};
    }
    tc_vec3f cwise_max(const tc_vec3f& v) const noexcept {
        return {x > v.x ? x : v.x, y > v.y ? y : v.y, z > v.z ? z : v.z};
    }
    tc_vec3f clamped(const tc_vec3f& minimum, const tc_vec3f& maximum) const noexcept {
        return {x < minimum.x ? minimum.x : (x > maximum.x ? maximum.x : x),
                y < minimum.y ? minimum.y : (y > maximum.y ? maximum.y : y),
                z < minimum.z ? minimum.z : (z > maximum.z ? maximum.z : z)};
    }
    tc_vec3f cwise_abs() const noexcept {
        return {std::abs(x), std::abs(y), std::abs(z)};
    }
    float min_component() const noexcept {
        const float yz = y < z ? y : z;
        return x < yz ? x : yz;
    }
    float max_component() const noexcept {
        const float yz = y > z ? y : z;
        return x > yz ? x : yz;
    }

    tc_vec3 to_double() const noexcept {
        return {x, y, z};
    }

    static tc_vec3f zero() {
        return {0, 0, 0};
    }
    static tc_vec3f unit_x() {
        return {1, 0, 0};
    }
    static tc_vec3f unit_y() {
        return {0, 1, 0};
    }
    static tc_vec3f unit_z() {
        return {0, 0, 1};
    }
    static tc_vec3f right() {
        return unit_x();
    }
    static tc_vec3f left() {
        return {-1, 0, 0};
    }
    static tc_vec3f forward() {
        return unit_y();
    }
    static tc_vec3f backward() {
        return {0, -1, 0};
    }
    static tc_vec3f up() {
        return unit_z();
    }
    static tc_vec3f down() {
        return {0, 0, -1};
    }
};

extern "C++" {
inline tc_vec3f operator*(float s, const tc_vec3f& v) noexcept {
    return v * s;
}
}

inline tc_vec3f tc_vec3::to_float() const noexcept {
    return tc_vec3f{static_cast<float>(x), static_cast<float>(y), static_cast<float>(z)};
}

inline bool tc_vec3::try_to_float(tc_vec3f& out) const noexcept {
    constexpr double float_max = static_cast<double>(std::numeric_limits<float>::max());
    if (!is_finite() || x < -float_max || x > float_max || y < -float_max || y > float_max || z < -float_max ||
        z > float_max) {
        return false;
    }

    const tc_vec3f narrowed = to_float();
    if (!narrowed.is_finite() || (x != 0.0 && narrowed.x == 0.0f) || (y != 0.0 && narrowed.y == 0.0f) ||
        (z != 0.0 && narrowed.z == 0.0f)) {
        return false;
    }
    out = narrowed;
    return true;
}

struct tc_quatf {
    float x;
    float y;
    float z;
    float w;
};

struct tc_pose2 {
    double ang = 0.0;
    tc_vec2 lin;

    constexpr tc_pose2() noexcept = default;
    constexpr tc_pose2(double ang, const tc_vec2& lin) noexcept
        : ang(ang),
          lin(lin) {}

    static tc_pose2 identity();

    tc_pose2 operator*(const tc_pose2& other) const;
    tc_pose2 inverse() const;

    tc_vec2 transform_point(const tc_vec2& p) const;
    tc_vec2 transform_vector(const tc_vec2& v) const;
    tc_vec2 rotate_vector(const tc_vec2& v) const;
    tc_vec2 inverse_transform_point(const tc_vec2& p) const;
    tc_vec2 inverse_rotate_vector(const tc_vec2& v) const;
    tc_vec2 inverse_transform_vector(const tc_vec2& v) const;

    tc_pose2 copy() const;
    void normalize_angle();

    static tc_pose2 rotation(double angle);
    static tc_pose2 translation(double x, double y);
    static tc_pose2 move(double dx, double dy);
    static tc_pose2 move_x(double distance);
    static tc_pose2 move_y(double distance);
    static tc_pose2 right(double distance);
    static tc_pose2 forward(double distance);
    static tc_pose2 lerp(const tc_pose2& a, const tc_pose2& b, double t);
};

struct tc_affine2f {
    // Packed row coefficients for the documented column-vector equations:
    // x' = m00*x + m01*y + tx
    // y' = m10*x + m11*y + ty
    float m00 = 1.0f;
    float m01 = 0.0f;
    float m10 = 0.0f;
    float m11 = 1.0f;
    float tx = 0.0f;
    float ty = 0.0f;

    constexpr tc_affine2f() noexcept = default;
    constexpr tc_affine2f(float m00, float m01, float m10, float m11, float tx, float ty) noexcept
        : m00(m00),
          m01(m01),
          m10(m10),
          m11(m11),
          tx(tx),
          ty(ty) {}
    explicit tc_affine2f(const tc_pose2& pose) noexcept;

    static tc_affine2f identity();
    static tc_affine2f translation(float x, float y);
    static tc_affine2f translation(const tc_vec2f& value);
    static tc_affine2f rotation(float radians);
    static tc_affine2f scaling(float sx, float sy);
    static tc_affine2f scaling(const tc_vec2f& value);
    static tc_affine2f scaling(float uniform);
    static tc_affine2f shear(float x_by_y, float y_by_x);
    static tc_affine2f trs(const tc_vec2f& translation, float radians, const tc_vec2f& scale);
    static tc_affine2f from_pose2(const tc_pose2& pose);

    tc_affine2f operator*(const tc_affine2f& child) const;
    tc_vec2f transform_point(const tc_vec2f& point) const;
    tc_vec2f transform_vector(const tc_vec2f& vector) const;
    tc_bounds2f transform_bounds(const tc_bounds2f& bounds) const;
    float determinant() const;
    bool is_finite() const;
    bool try_inverse(tc_affine2f& out, float epsilon = 1.0e-8f) const;
};

struct tc_basis3d {
    // Column vectors. For column-vector multiplication:
    // result = x * vector.x + y * vector.y + z * vector.z.
    tc_vec3 x = {1.0, 0.0, 0.0};
    tc_vec3 y = {0.0, 1.0, 0.0};
    tc_vec3 z = {0.0, 0.0, 1.0};

    constexpr tc_basis3d() noexcept = default;
    constexpr tc_basis3d(const tc_vec3& x, const tc_vec3& y, const tc_vec3& z) noexcept
        : x(x),
          y(y),
          z(z) {}

    static tc_basis3d identity();
    static tc_basis3d from_quat(const tc_quat& rotation);
    static tc_basis3d scaling(double sx, double sy, double sz);
    static tc_basis3d scaling(const tc_vec3& scale);
    static tc_basis3d scaling(double uniform);

    tc_basis3d operator*(const tc_basis3d& child) const;
    tc_vec3 transform_vector(const tc_vec3& vector) const;
    bool try_transform_normal(const tc_vec3& normal, tc_vec3& out, double epsilon = 1.0e-12) const;
    double determinant() const;
    bool is_finite() const;
    bool try_inverse(tc_basis3d& out, double epsilon = 1.0e-12) const;
};

struct tc_pose3;
struct tc_general_pose3;

struct tc_affine3d {
    // T * Basis for column vectors. The packed ABI is 9 basis coefficients
    // followed by 3 translation coefficients.
    tc_basis3d basis;
    tc_vec3 translation;

    constexpr tc_affine3d() noexcept = default;
    constexpr tc_affine3d(const tc_basis3d& basis, const tc_vec3& translation) noexcept
        : basis(basis),
          translation(translation) {}

    static tc_affine3d identity();
    static tc_affine3d from_translation(double x, double y, double z);
    static tc_affine3d from_translation(const tc_vec3& value);
    static tc_affine3d from_rotation(const tc_quat& rotation);
    static tc_affine3d scaling(double sx, double sy, double sz);
    static tc_affine3d scaling(const tc_vec3& scale);
    static tc_affine3d scaling(double uniform);
    static tc_affine3d trs(const tc_vec3& translation, const tc_quat& rotation, const tc_vec3& scale);
    static tc_affine3d from_pose3(const tc_pose3& pose);
    static tc_affine3d from_general_pose3(const tc_general_pose3& pose);

    tc_affine3d operator*(const tc_affine3d& child) const;
    tc_vec3 transform_point(const tc_vec3& point) const;
    tc_vec3 transform_vector(const tc_vec3& vector) const;
    bool try_transform_normal(const tc_vec3& normal, tc_vec3& out, double epsilon = 1.0e-12) const;
    bool try_inverse_transform_point(const tc_vec3& point, tc_vec3& out, double epsilon = 1.0e-12) const;
    bool try_inverse_transform_vector(const tc_vec3& vector, tc_vec3& out, double epsilon = 1.0e-12) const;
    double determinant() const;
    bool is_finite() const;
    bool try_inverse(tc_affine3d& out, double epsilon = 1.0e-12) const;
    void matrix4(double* out_column_major_16) const;
    static bool try_from_matrix4(const double* column_major_16, tc_affine3d& out, double epsilon = 1.0e-12);
};

struct tc_pose3 {
    // Raw ABI-friendly pose value. Native transform/composition/inverse/matrix
    // methods require ang to be finite and unit; owning boundaries normalize
    // uncertain input before storing or applying the pose.
    tc_quat ang;
    tc_vec3 lin;

    constexpr tc_pose3() noexcept = default;
    constexpr tc_pose3(const tc_quat& ang, const tc_vec3& lin) noexcept
        : ang(ang),
          lin(lin) {}

    static tc_pose3 identity();

    tc_pose3 operator*(const tc_pose3& other) const;
    tc_pose3 inverse() const;

    tc_vec3 transform_point(const tc_vec3& p) const;
    tc_vec3 transform_vector(const tc_vec3& v) const;
    tc_vec3 rotate_point(const tc_vec3& p) const;
    tc_vec3 inverse_transform_point(const tc_vec3& p) const;
    tc_vec3 inverse_transform_vector(const tc_vec3& v) const;

    tc_vec3 point_to_global(const tc_vec3& p) const;
    tc_vec3 vector_to_global(const tc_vec3& v) const;
    tc_vec3 point_to_local(const tc_vec3& p) const;
    tc_vec3 vector_to_local(const tc_vec3& v) const;

    tc_vec3 forward_in_global(double distance = 1.0) const;
    tc_vec3 backward_in_global(double distance = 1.0) const;
    tc_vec3 up_in_global(double distance = 1.0) const;
    tc_vec3 down_in_global(double distance = 1.0) const;
    tc_vec3 right_in_global(double distance = 1.0) const;
    tc_vec3 left_in_global(double distance = 1.0) const;

    tc_vec3 global_forward_in_local(double distance = 1.0) const;
    tc_vec3 global_backward_in_local(double distance = 1.0) const;
    tc_vec3 global_up_in_local(double distance = 1.0) const;
    tc_vec3 global_down_in_local(double distance = 1.0) const;
    tc_vec3 global_right_in_local(double distance = 1.0) const;
    tc_vec3 global_left_in_local(double distance = 1.0) const;

    tc_pose3 normalized() const;
    bool is_finite() const;
    tc_pose3 with_translation(const tc_vec3& new_lin) const;
    tc_pose3 with_rotation(const tc_quat& new_ang) const;

    void rotation_matrix(double* m) const;
    void as_matrix(double* m) const;
    termin::Mat44 as_mat44() const;

    double distance(const tc_pose3& other) const;

    static tc_pose3 translation(double x, double y, double z);
    static tc_pose3 translation(const tc_vec3& t);
    static tc_pose3 rotation(const tc_vec3& axis, double angle);
    static tc_pose3 rotate_x(double angle);
    static tc_pose3 rotate_y(double angle);
    static tc_pose3 rotate_z(double angle);
    static tc_pose3 looking_at(const tc_vec3& eye, const tc_vec3& target, const tc_vec3& up = tc_vec3::unit_z());
    static tc_pose3 from_euler(const tc_vec3& euler_xyz);

    tc_vec3 to_euler() const;
    void to_axis_angle(tc_vec3& axis, double& angle) const;
    tc_pose3 copy() const;
};

struct tc_general_pose3 {
    // The same finite unit-quaternion precondition as tc_pose3 applies to all
    // native transform/composition/inverse/matrix methods.
    tc_quat ang;
    tc_vec3 lin;
    tc_vec3 scale = {1.0, 1.0, 1.0};

    constexpr tc_general_pose3() noexcept = default;
    constexpr tc_general_pose3(const tc_quat& ang,
                               const tc_vec3& lin,
                               const tc_vec3& scale = tc_vec3{1.0, 1.0, 1.0}) noexcept
        : ang(ang),
          lin(lin),
          scale(scale) {}

    static tc_general_pose3 identity();

    // These operations project an affine result back into TRS and are not
    // closed for arbitrary non-uniform scale and rotation.
    tc_general_pose3 compose_trs_projected(const tc_general_pose3& other) const;
    tc_general_pose3 compose_trs_projected(const tc_pose3& other) const;
    tc_general_pose3 inverse_trs_projected() const;

    tc_vec3 transform_point(const tc_vec3& p) const;
    tc_vec3 transform_vector(const tc_vec3& v) const;
    tc_vec3 transform_direction(const tc_vec3& d) const;
    tc_vec3 rotate_point(const tc_vec3& p) const;
    tc_vec3 inverse_transform_point(const tc_vec3& p) const;
    tc_vec3 inverse_transform_vector(const tc_vec3& v) const;
    tc_vec3 inverse_transform_direction(const tc_vec3& d) const;

    tc_vec3 point_to_global(const tc_vec3& p) const;
    tc_vec3 vector_to_global(const tc_vec3& v) const;
    tc_vec3 direction_to_global(const tc_vec3& d) const;
    tc_vec3 point_to_local(const tc_vec3& p) const;
    tc_vec3 vector_to_local(const tc_vec3& v) const;
    tc_vec3 direction_to_local(const tc_vec3& d) const;

    tc_vec3 forward_in_global(double distance = 1.0) const;
    tc_vec3 backward_in_global(double distance = 1.0) const;
    tc_vec3 up_in_global(double distance = 1.0) const;
    tc_vec3 down_in_global(double distance = 1.0) const;
    tc_vec3 right_in_global(double distance = 1.0) const;
    tc_vec3 left_in_global(double distance = 1.0) const;

    tc_vec3 global_forward_in_local(double distance = 1.0) const;
    tc_vec3 global_backward_in_local(double distance = 1.0) const;
    tc_vec3 global_up_in_local(double distance = 1.0) const;
    tc_vec3 global_down_in_local(double distance = 1.0) const;
    tc_vec3 global_right_in_local(double distance = 1.0) const;
    tc_vec3 global_left_in_local(double distance = 1.0) const;

    tc_general_pose3 normalized() const;
    tc_general_pose3 with_rotation(const tc_quat& new_ang) const;
    tc_general_pose3 with_translation(const tc_vec3& new_lin) const;
    tc_general_pose3 with_scale(const tc_vec3& new_scale) const;
    tc_pose3 to_pose3() const;

    void rotation_matrix(double* m) const;
    void matrix4(double* m) const;
    void matrix34(double* m) const;
    void inverse_matrix4(double* m) const;

    double distance(const tc_general_pose3& other) const;

    static tc_general_pose3 translation(double x, double y, double z);
    static tc_general_pose3 translation(const tc_vec3& t);
    static tc_general_pose3 rotation(const tc_vec3& axis, double angle);
    static tc_general_pose3 scaling(double sx, double sy, double sz);
    static tc_general_pose3 scaling(double s);
    static tc_general_pose3 rotate_x(double angle);
    static tc_general_pose3 rotate_y(double angle);
    static tc_general_pose3 rotate_z(double angle);
    static tc_general_pose3 move(double dx, double dy, double dz);
    static tc_general_pose3 move_x(double d);
    static tc_general_pose3 move_y(double d);
    static tc_general_pose3 move_z(double d);
    static tc_general_pose3 right(double d);
    static tc_general_pose3 forward(double d);
    static tc_general_pose3 up(double d);
    static tc_general_pose3
    looking_at(const tc_vec3& eye, const tc_vec3& target, const tc_vec3& up_vec = tc_vec3{0.0, 0.0, 1.0});
};

struct tc_screw3 {
    tc_vec3 ang;
    tc_vec3 lin;

    constexpr tc_screw3() noexcept = default;
    constexpr tc_screw3(const tc_vec3& ang, const tc_vec3& lin) noexcept
        : ang(ang),
          lin(lin) {}

    static tc_screw3 zero();

    tc_screw3 operator+(const tc_screw3& s) const;
    tc_screw3 operator-(const tc_screw3& s) const;
    tc_screw3 operator*(double k) const;
    tc_screw3 operator/(double k) const;
    tc_screw3 operator-() const;

    tc_screw3& operator+=(const tc_screw3& s);
    tc_screw3& operator-=(const tc_screw3& s);
    tc_screw3& operator*=(double k);
    tc_screw3& operator/=(double k);

    tc_screw3 scaled(double k) const;
    double dot(const tc_screw3& s) const;
    tc_screw3 cross_motion(const tc_screw3& s) const;
    tc_screw3 cross_force(const tc_screw3& s) const;
    bool is_finite() const;
    tc_screw3 rotated_by(const tc_quat& orientation) const;
    tc_screw3 inverse_rotated_by(const tc_quat& orientation) const;
    // Pose adjoint/coadjoint change both axes and reference origin.
    tc_screw3 adjoint(const tc_pose3& pose) const;
    tc_screw3 adjoint_inv(const tc_pose3& pose) const;
    tc_screw3 coadjoint(const tc_pose3& pose) const;
    tc_screw3 coadjoint_inv(const tc_pose3& pose) const;
    // offset_from_origin points from the current origin to the target point.
    tc_screw3 velocity_at_offset(const tc_vec3& offset_from_origin) const;
    tc_screw3 velocity_at_origin_from_offset(const tc_vec3& offset_from_origin) const;
    tc_screw3 wrench_at_offset(const tc_vec3& offset_from_origin) const;
    tc_screw3 wrench_at_origin_from_offset(const tc_vec3& offset_from_origin) const;
    tc_screw3 transform_as_twist_by(const tc_pose3& pose) const;
    tc_screw3 inverse_transform_as_twist_by(const tc_pose3& pose) const;
    tc_screw3 transform_as_wrench_by(const tc_pose3& pose) const;
    tc_screw3 inverse_transform_as_wrench_by(const tc_pose3& pose) const;
    [[deprecated("Screw3::to_pose() copies lin directly and is not the SE(3) "
                 "exponential; do not use it to integrate a twist")]]
    tc_pose3 to_pose() const;
};

extern "C++" {
inline tc_screw3 operator*(double k, const tc_screw3& s) {
    return s * k;
}
}

struct tc_screw2 {
    double ang = 0.0;
    tc_vec2 lin;

    constexpr tc_screw2() noexcept = default;
    constexpr tc_screw2(double ang, const tc_vec2& lin) noexcept
        : ang(ang),
          lin(lin) {}

    static tc_screw2 zero();

    tc_screw2 operator+(const tc_screw2& s) const;
    tc_screw2 operator-(const tc_screw2& s) const;
    tc_screw2 operator*(double k) const;
    tc_screw2 operator/(double k) const;
    tc_screw2 operator-() const;

    tc_screw2& operator+=(const tc_screw2& s);
    tc_screw2& operator-=(const tc_screw2& s);
    tc_screw2& operator*=(double k);
    tc_screw2& operator/=(double k);

    double moment() const;
    tc_vec2 vector() const;
    tc_screw2 kinematic_carry(const tc_vec2& arm) const;
    tc_screw2 force_carry(const tc_vec2& arm) const;
    tc_screw2 twist_carry(const tc_vec2& arm) const;
    tc_screw2 wrench_carry(const tc_vec2& arm) const;
    tc_screw2 transform_by(const tc_pose2& pose) const;
    tc_screw2 rotated_by(const tc_pose2& pose) const;
    tc_screw2 inverse_transform_by(const tc_pose2& pose) const;
    tc_screw2 transform_as_twist_by(const tc_pose2& pose) const;
    tc_screw2 inverse_transform_as_twist_by(const tc_pose2& pose) const;
    tc_screw2 transform_as_wrench_by(const tc_pose2& pose) const;
    tc_screw2 inverse_transform_as_wrench_by(const tc_pose2& pose) const;
    tc_pose2 to_pose() const;
    tc_screw2 copy() const;

    static tc_screw2 from_vector_vw_order(const double* data);
    static tc_screw2 from_vector_wv_order(const double* data);
};

extern "C++" {
inline tc_screw2 operator*(double k, const tc_screw2& s) {
    return s * k;
}
}

struct tc_aabb {
    tc_vec3 min_point;
    tc_vec3 max_point;

    constexpr tc_aabb() noexcept = default;
    constexpr tc_aabb(const tc_vec3& min_pt, const tc_vec3& max_pt) noexcept
        : min_point(min_pt),
          max_point(max_pt) {}

    void extend(const tc_vec3& point);
    bool intersects(const tc_aabb& other) const;
    bool contains(const tc_vec3& point) const;
    tc_aabb merge(const tc_aabb& other) const;
    tc_vec3 center() const;
    tc_vec3 size() const;
    tc_vec3 half_size() const;
    tc_vec3 project_point(const tc_vec3& point) const;
    bool is_finite() const;
    bool is_valid() const;
    tc_aabb expanded(double amount) const;
    double surface_area() const;
    double volume() const;
    static tc_aabb from_points(const tc_vec3* points, size_t count);

    tc_aabb transformed_by(const tc_pose3& pose) const;
    tc_aabb transformed_by(const tc_general_pose3& pose) const;
    void get_corners(tc_vec3* out_corners) const;
};

struct tc_aabbf {
    tc_vec3f min_point;
    tc_vec3f max_point;

    constexpr tc_aabbf() noexcept = default;
    constexpr tc_aabbf(const tc_vec3f& min_pt, const tc_vec3f& max_pt) noexcept
        : min_point(min_pt),
          max_point(max_pt) {}

    void extend(const tc_vec3f& point) noexcept;
    bool intersects(const tc_aabbf& other) const noexcept;
    bool contains(const tc_vec3f& point) const noexcept;
    tc_aabbf merge(const tc_aabbf& other) const noexcept;
    tc_vec3f center() const noexcept;
    tc_vec3f size() const noexcept;
    tc_vec3f half_size() const noexcept;
    tc_vec3f project_point(const tc_vec3f& point) const noexcept;
    bool is_finite() const noexcept;
    bool is_valid() const noexcept;
    tc_aabbf expanded(float amount) const noexcept;
    static tc_aabbf from_points(const tc_vec3f* points, size_t count) noexcept;
};

struct tc_mat44 {
    double m[16]; // column-major (OpenGL convention)
};

#else

typedef struct tc_vec2 {
    double x, y;
} tc_vec2;

typedef struct tc_vec2f {
    float x, y;
} tc_vec2f;

typedef struct tc_size2f {
    float width, height;
} tc_size2f;

typedef struct tc_bounds2f {
    float x0, y0, x1, y1;
} tc_bounds2f;

typedef struct tc_rect2f {
    float x, y, width, height;
} tc_rect2f;

typedef struct tc_vec3 {
    double x, y, z;
} tc_vec3;

typedef struct tc_ray3 {
    tc_vec3 origin;
    tc_vec3 direction;
} tc_ray3;

typedef struct tc_quat {
    double x, y, z, w;
} tc_quat;

typedef struct tc_vec3f {
    float x, y, z;
} tc_vec3f;

typedef struct tc_quatf {
    float x, y, z, w;
} tc_quatf;

typedef struct tc_pose2 {
    double ang;
    tc_vec2 lin;
} tc_pose2;

typedef struct tc_affine2f {
    float m00, m01;
    float m10, m11;
    float tx, ty;
} tc_affine2f;

typedef struct tc_basis3d {
    tc_vec3 x;
    tc_vec3 y;
    tc_vec3 z;
} tc_basis3d;

typedef struct tc_affine3d {
    tc_basis3d basis;
    tc_vec3 translation;
} tc_affine3d;

typedef struct tc_pose3 {
    tc_quat ang;
    tc_vec3 lin;
} tc_pose3;

typedef struct tc_general_pose3 {
    tc_quat ang;
    tc_vec3 lin;
    tc_vec3 scale;
} tc_general_pose3;

typedef struct tc_screw3 {
    tc_vec3 ang;
    tc_vec3 lin;
} tc_screw3;

typedef struct tc_screw2 {
    double ang;
    tc_vec2 lin;
} tc_screw2;

typedef struct tc_aabb {
    tc_vec3 min_point;
    tc_vec3 max_point;
} tc_aabb;

typedef struct tc_aabbf {
    tc_vec3f min_point;
    tc_vec3f max_point;
} tc_aabbf;

typedef struct tc_mat44 {
    double m[16]; // column-major (OpenGL convention)
} tc_mat44;

#endif

#endif // TCBASE_TYPES_GEOM_TYPES_H
