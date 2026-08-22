#pragma once

#include "quat.hpp"
#include "vec3.hpp"
#include "vec4.hpp"
#include <cmath>
#include <cstddef>
#include <cstring>
#include <limits>
#include <type_traits>

namespace termin {

    namespace detail {

        template <typename Scalar>
        bool mat44_inverse_products_are_reliable(const Scalar* input, const Scalar* inverse, Scalar epsilon) noexcept {
            // An inverse is useful only when it behaves as an inverse in the
            // matrix's storage precision. Requiring both products catches the
            // asymmetric cancellation common in projective matrices with large
            // translations. sqrt(machine epsilon) is the conventional
            // half-precision reliability boundary; callers may request a looser
            // absolute residual through epsilon, but not an unrealistically
            // tighter one for the scalar type.
            const Scalar precision_floor = std::sqrt(std::numeric_limits<Scalar>::epsilon());
            const Scalar tolerance = epsilon > precision_floor ? epsilon : precision_floor;

            for (int product = 0; product < 2; ++product) {
                const Scalar* left = product == 0 ? input : inverse;
                const Scalar* right = product == 0 ? inverse : input;
                for (int column = 0; column < 4; ++column) {
                    for (int row = 0; row < 4; ++row) {
                        Scalar value = Scalar{0};
                        for (int k = 0; k < 4; ++k) {
                            value += left[k * 4 + row] * right[column * 4 + k];
                        }
                        const Scalar expected = column == row ? Scalar{1} : Scalar{0};
                        if (!std::isfinite(value) || std::abs(value - expected) > tolerance) {
                            return false;
                        }
                    }
                }
            }
            return true;
        }

        template <typename Scalar>
        bool try_inverse_mat44(const Scalar* input, Scalar* output, Scalar epsilon) noexcept {
            if (input == nullptr || output == nullptr || !std::isfinite(epsilon) || epsilon < Scalar{0}) {
                return false;
            }

            // Two-sided equilibration reduces sensitivity to world units and
            // non-uniform scale. It cannot make an inverse representable when
            // the input is ill-conditioned at Scalar precision, so the final
            // candidate is validated separately in both multiplication orders.
            Scalar column_scale[4]{};
            for (int column = 0; column < 4; ++column) {
                for (int row = 0; row < 4; ++row) {
                    const Scalar value = input[column * 4 + row];
                    if (!std::isfinite(value)) {
                        return false;
                    }
                    const Scalar absolute = std::abs(value);
                    if (absolute > column_scale[column]) {
                        column_scale[column] = absolute;
                    }
                }
                if (column_scale[column] == Scalar{0} || !std::isfinite(column_scale[column])) {
                    return false;
                }
            }

            Scalar row_scale[4]{};
            for (int row = 0; row < 4; ++row) {
                for (int column = 0; column < 4; ++column) {
                    const Scalar scaled = std::abs(input[column * 4 + row] / column_scale[column]);
                    if (scaled > row_scale[row]) {
                        row_scale[row] = scaled;
                    }
                }
                if (row_scale[row] == Scalar{0} || !std::isfinite(row_scale[row])) {
                    return false;
                }
            }

            Scalar augmented[4][8]{};
            for (int row = 0; row < 4; ++row) {
                for (int column = 0; column < 4; ++column) {
                    augmented[row][column] = input[column * 4 + row] / column_scale[column] / row_scale[row];
                    augmented[row][column + 4] = row == column ? Scalar{1} : Scalar{0};
                }
            }

            for (int pivot_column = 0; pivot_column < 4; ++pivot_column) {
                int pivot_row = pivot_column;
                Scalar pivot_abs = std::abs(augmented[pivot_row][pivot_column]);
                for (int row = pivot_column + 1; row < 4; ++row) {
                    const Scalar candidate_abs = std::abs(augmented[row][pivot_column]);
                    if (candidate_abs > pivot_abs) {
                        pivot_abs = candidate_abs;
                        pivot_row = row;
                    }
                }
                // The equilibrated matrix is dimensionless with entries bounded
                // near one. A pivot below one storage-precision ULP is not
                // distinguishable reliably from rank deficiency. epsilon is
                // intentionally not used here: a world translation can make a
                // valid projective pivot small without proving by itself that
                // the stored inverse will be unreliable.
                if (pivot_abs <= std::numeric_limits<Scalar>::epsilon()) {
                    return false;
                }
                if (pivot_row != pivot_column) {
                    for (int column = 0; column < 8; ++column) {
                        const Scalar temporary = augmented[pivot_column][column];
                        augmented[pivot_column][column] = augmented[pivot_row][column];
                        augmented[pivot_row][column] = temporary;
                    }
                }

                const Scalar pivot = augmented[pivot_column][pivot_column];
                for (int column = 0; column < 8; ++column) {
                    augmented[pivot_column][column] /= pivot;
                    if (!std::isfinite(augmented[pivot_column][column])) {
                        return false;
                    }
                }

                for (int row = 0; row < 4; ++row) {
                    if (row == pivot_column) {
                        continue;
                    }
                    const Scalar factor = augmented[row][pivot_column];
                    for (int column = 0; column < 8; ++column) {
                        augmented[row][column] -= factor * augmented[pivot_column][column];
                        if (!std::isfinite(augmented[row][column])) {
                            return false;
                        }
                    }
                }
            }

            Scalar result[16];
            for (int row = 0; row < 4; ++row) {
                for (int column = 0; column < 4; ++column) {
                    // A = R * E * C, therefore A^-1 = C^-1 * E^-1 * R^-1.
                    const Scalar value = augmented[row][column + 4] / column_scale[row] / row_scale[column];
                    if (!std::isfinite(value)) {
                        return false;
                    }
                    result[column * 4 + row] = value;
                }
            }
            if (!mat44_inverse_products_are_reliable(input, result, epsilon)) {
                // Gauss-Jordan can leave a small cancellation residue after
                // undoing the equilibration, especially for otherwise simple
                // transforms with large translations. Perform one right
                // iterative-refinement step in the matrix's storage precision:
                //
                //   R = I - A * X
                //   X2 = X + X * R
                //
                // Keep every intermediate local so a failed refinement cannot
                // modify the caller's output.
                Scalar residual[16]{};
                for (int column = 0; column < 4; ++column) {
                    for (int row = 0; row < 4; ++row) {
                        Scalar product = Scalar{0};
                        for (int k = 0; k < 4; ++k) {
                            const Scalar term = input[k * 4 + row] * result[column * 4 + k];
                            if (!std::isfinite(term)) {
                                return false;
                            }
                            const Scalar accumulated = product + term;
                            if (!std::isfinite(accumulated)) {
                                return false;
                            }
                            product = accumulated;
                        }
                        const Scalar expected = column == row ? Scalar{1} : Scalar{0};
                        const Scalar value = expected - product;
                        if (!std::isfinite(value)) {
                            return false;
                        }
                        residual[column * 4 + row] = value;
                    }
                }

                Scalar refined[16]{};
                for (int column = 0; column < 4; ++column) {
                    for (int row = 0; row < 4; ++row) {
                        Scalar correction = Scalar{0};
                        for (int k = 0; k < 4; ++k) {
                            const Scalar term = result[k * 4 + row] * residual[column * 4 + k];
                            if (!std::isfinite(term)) {
                                return false;
                            }
                            const Scalar accumulated = correction + term;
                            if (!std::isfinite(accumulated)) {
                                return false;
                            }
                            correction = accumulated;
                        }
                        const Scalar value = result[column * 4 + row] + correction;
                        if (!std::isfinite(value)) {
                            return false;
                        }
                        refined[column * 4 + row] = value;
                    }
                }

                if (!mat44_inverse_products_are_reliable(input, refined, epsilon)) {
                    return false;
                }
                std::memcpy(result, refined, sizeof(result));
            }
            std::memcpy(output, result, sizeof(result));
            return true;
        }

    } // namespace detail

    // ============================================================================
    // Mat44f (float) - 4x4 Matrix in column-major order (OpenGL convention)
    // ============================================================================

    /**
     * 4x4 Matrix in column-major order (OpenGL convention).
     *
     * Memory layout: m[col][row] or m[col * 4 + row]
     *
     * Coordinate convention: Y-forward, Z-up
     *   - X: right
     *   - Y: forward (depth, camera looks along +Y)
     *   - Z: up
     */
    struct Mat44f {
        float data[16]; // Column-major: [col0, col1, col2, col3]

        Mat44f() {
            std::memset(data, 0, sizeof(data));
        }
        explicit Mat44f(const float* column_major_16) noexcept {
            std::memcpy(data, column_major_16, sizeof(data));
        }

        static Mat44f from_column_major(const float* column_major_16) noexcept {
            return Mat44f(column_major_16);
        }
        static Mat44f from_column_major_f32(const float* column_major_16) noexcept {
            return Mat44f(column_major_16);
        }
        static Mat44f from_column_major_f64(const double* column_major_16) noexcept {
            Mat44f result;
            for (int i = 0; i < 16; ++i) {
                result.data[i] = static_cast<float>(column_major_16[i]);
            }
            return result;
        }
        void copy_column_major_to(float* out_column_major_16) const noexcept {
            std::memcpy(out_column_major_16, data, sizeof(data));
        }

        // Access by column and row: m(col, row)
        float& operator()(int col, int row) {
            return data[col * 4 + row];
        }
        float operator()(int col, int row) const {
            return data[col * 4 + row];
        }

        // Raw data access
        float* ptr() {
            return data;
        }
        const float* ptr() const {
            return data;
        }

        bool is_finite() const noexcept {
            for (float value : data) {
                if (!std::isfinite(value)) {
                    return false;
                }
            }
            return true;
        }

        // Identity matrix
        static Mat44f identity() {
            Mat44f m;
            m(0, 0) = 1;
            m(1, 1) = 1;
            m(2, 2) = 1;
            m(3, 3) = 1;
            return m;
        }

        // Zero matrix
        static Mat44f zero() {
            return Mat44f();
        }

        // Matrix multiplication: this * other
        Mat44f operator*(const Mat44f& b) const {
            Mat44f result;
            for (int col = 0; col < 4; ++col) {
                for (int row = 0; row < 4; ++row) {
                    float sum = 0;
                    for (int k = 0; k < 4; ++k) {
                        sum += (*this)(k, row) * b(col, k);
                    }
                    result(col, row) = sum;
                }
            }
            return result;
        }

        Vec4f transform_homogeneous(const Vec4f& value) const noexcept {
            return {
                (*this)(0, 0) * value.x + (*this)(1, 0) * value.y + (*this)(2, 0) * value.z + (*this)(3, 0) * value.w,
                (*this)(0, 1) * value.x + (*this)(1, 1) * value.y + (*this)(2, 1) * value.z + (*this)(3, 1) * value.w,
                (*this)(0, 2) * value.x + (*this)(1, 2) * value.y + (*this)(2, 2) * value.z + (*this)(3, 2) * value.w,
                (*this)(0, 3) * value.x + (*this)(1, 3) * value.y + (*this)(2, 3) * value.z + (*this)(3, 3) * value.w,
            };
        }

        // Transform point (w=1). The legacy unchecked fallback for near-zero w is preserved.
        Vec3f transform_point(const Vec3f& p) const noexcept {
            const Vec4f transformed = transform_homogeneous({p.x, p.y, p.z, 1.0f});
            const float x = transformed.x;
            const float y = transformed.y;
            const float z = transformed.z;
            const float w = transformed.w;
            if (std::abs(w) > 1e-6f) {
                return {x / w, y / w, z / w};
            }
            return {x, y, z};
        }

        bool try_transform_point(const Vec3f& point, Vec3f& out, float epsilon = 1.0e-6f) const noexcept {
            if (!point.is_finite() || !std::isfinite(epsilon) || epsilon < 0.0f) {
                return false;
            }
            const Vec4f transformed = transform_homogeneous({point.x, point.y, point.z, 1.0f});
            if (!transformed.is_finite() || std::abs(transformed.w) <= epsilon) {
                return false;
            }
            const Vec3f result{
                transformed.x / transformed.w, transformed.y / transformed.w, transformed.z / transformed.w};
            if (!result.is_finite()) {
                return false;
            }
            out = result;
            return true;
        }

        // Transform direction (w=0)
        Vec3f transform_direction(const Vec3f& d) const noexcept {
            return {(*this)(0, 0) * d.x + (*this)(1, 0) * d.y + (*this)(2, 0) * d.z,
                    (*this)(0, 1) * d.x + (*this)(1, 1) * d.y + (*this)(2, 1) * d.z,
                    (*this)(0, 2) * d.x + (*this)(1, 2) * d.y + (*this)(2, 2) * d.z};
        }

        Mat44 to_double() const noexcept;

        // Transpose
        Mat44f transposed() const {
            Mat44f result;
            for (int i = 0; i < 4; ++i) {
                for (int j = 0; j < 4; ++j) {
                    result(i, j) = (*this)(j, i);
                }
            }
            return result;
        }

        float determinant() const {
            const float* m = data;
            const float c00 = m[5] * m[10] * m[15] - m[5] * m[11] * m[14] - m[9] * m[6] * m[15] + m[9] * m[7] * m[14] +
                              m[13] * m[6] * m[11] - m[13] * m[7] * m[10];
            const float c04 = -m[4] * m[10] * m[15] + m[4] * m[11] * m[14] + m[8] * m[6] * m[15] - m[8] * m[7] * m[14] -
                              m[12] * m[6] * m[11] + m[12] * m[7] * m[10];
            const float c08 = m[4] * m[9] * m[15] - m[4] * m[11] * m[13] - m[8] * m[5] * m[15] + m[8] * m[7] * m[13] +
                              m[12] * m[5] * m[11] - m[12] * m[7] * m[9];
            const float c12 = -m[4] * m[9] * m[14] + m[4] * m[10] * m[13] + m[8] * m[5] * m[14] - m[8] * m[6] * m[13] -
                              m[12] * m[5] * m[10] + m[12] * m[6] * m[9];
            return m[0] * c00 + m[1] * c04 + m[2] * c08 + m[3] * c12;
        }

        // Checked inverse: succeeds only when both products with the candidate
        // are close to identity at float precision.
        bool try_inverse(Mat44f& out, float epsilon = 1.0e-6f) const noexcept {
            return detail::try_inverse_mat44(data, out.data, epsilon);
        }

        // Legacy API: singular or non-finite matrices still fall back to identity.
        Mat44f inverse() const {
            Mat44f result;
            return try_inverse(result) ? result : identity();
        }

        // ========== Construction from components ==========

        // Translation matrix
        static Mat44f translation(const Vec3& t) {
            Mat44f m = identity();
            m(3, 0) = static_cast<float>(t.x);
            m(3, 1) = static_cast<float>(t.y);
            m(3, 2) = static_cast<float>(t.z);
            return m;
        }

        static Mat44f translation(float x, float y, float z) {
            return translation(Vec3{x, y, z});
        }

        // Scale matrix
        static Mat44f scale(const Vec3& s) {
            Mat44f m;
            m(0, 0) = static_cast<float>(s.x);
            m(1, 1) = static_cast<float>(s.y);
            m(2, 2) = static_cast<float>(s.z);
            m(3, 3) = 1;
            return m;
        }

        static Mat44f scale(float s) {
            return scale(Vec3{s, s, s});
        }

        // Fast path: q must be a finite unit quaternion. Use try_rotation when
        // the quaternion comes from an unchecked boundary.
        static Mat44f rotation(const Quat& q) noexcept {
            double row_major[9];
            q.to_matrix(row_major);

            Mat44f m = identity();
            for (int row = 0; row < 3; ++row) {
                for (int column = 0; column < 3; ++column) {
                    m(column, row) = static_cast<float>(row_major[row * 3 + column]);
                }
            }
            return m;
        }

        static bool try_rotation(const Quat& q, Mat44f& out, double epsilon = 1.0e-12) noexcept {
            double row_major[9];
            if (!q.try_to_matrix(row_major, epsilon)) {
                return false;
            }

            Mat44f result = identity();
            for (int row = 0; row < 3; ++row) {
                for (int column = 0; column < 3; ++column) {
                    result(column, row) = static_cast<float>(row_major[row * 3 + column]);
                }
            }
            out = result;
            return true;
        }

        // Rotation around axis
        static bool
        try_rotation_axis_angle(const Vec3& axis, float angle, Mat44f& out, double epsilon = 1.0e-12) noexcept {
            Quat orientation;
            if (!Quat::try_from_axis_angle(axis, static_cast<double>(angle), orientation, epsilon)) {
                return false;
            }
            // epsilon belongs to the source-axis magnitude contract. The
            // quaternion produced above is already checked and normalized.
            return try_rotation(orientation, out, 0.0);
        }

        // Invalid axis-angle input is represented by a non-finite matrix. Use
        // try_rotation_axis_angle at unchecked boundaries.
        static Mat44f rotation_axis_angle(const Vec3& axis, float angle) noexcept {
            return rotation(Quat::from_axis_angle(axis, static_cast<double>(angle)));
        }

        // ========== Projection matrices (Vulkan-native NDC) ==========
        //
        // Clip-space convention used uniformly across backends:
        //   - Y+ goes DOWN (framebuffer row 0 = top, matches Vulkan native).
        //   - Z ∈ [0, 1] (0 at near, 1 at far).
        //
        // OpenGL reaches the same convention via a one-time
        // `glClipControl(GL_UPPER_LEFT, GL_ZERO_TO_ONE)` in OpenGLRenderDevice
        // — see coord_system.md.
        //
        // Camera looks along +Y axis:
        //   - View X  -> Clip X (right)
        //   - View Z  -> Clip -Y (camera-up maps to top-of-framebuffer)
        //   - View Y  -> Depth (forward)

        /**
         * Perspective projection matrix (Vulkan-native, Y-down clip, Z ∈ [0,1]).
         *
         * @param fov_y  Vertical field of view in radians
         * @param aspect Aspect ratio (width / height)
         * @param near   Near clipping plane (must be > 0)
         * @param far    Far clipping plane (must be > near)
         */
        static Mat44f perspective(float fov_y, float aspect, float near, float far) {
            float f = 1.0f / std::tan(fov_y * 0.5f);
            Mat44f m;

            m(0, 0) = f / aspect;         // X -> clip X
            m(2, 1) = -f;                 // Z (cam up) -> clip -Y
            m(1, 2) = far / (far - near); // Y -> clip Z (0..1)
            m(3, 2) = -(far * near) / (far - near);
            m(1, 3) = 1.0f; // w = y

            return m;
        }

        // Perspective with independent horizontal and vertical FOV (may cause distortion)
        static Mat44f perspective_fov_xy(float fov_x, float fov_y, float near, float far) {
            float fx = 1.0f / std::tan(fov_x * 0.5f);
            float fy = 1.0f / std::tan(fov_y * 0.5f);
            Mat44f m;
            m(0, 0) = fx;
            m(2, 1) = -fy;
            m(1, 2) = far / (far - near);
            m(3, 2) = -(far * near) / (far - near);
            m(1, 3) = 1.0f;
            return m;
        }

        /**
         * Orthographic projection matrix (Vulkan-native, Y-down clip, Z ∈ [0,1]).
         *
         * Camera looks along +Y axis:
         *   - View X -> Clip X (left/right)
         *   - View Z -> Clip -Y (top/bottom, camera-up → top)
         *   - View Y -> Depth (near/far)
         */
        static Mat44f orthographic(float left, float right, float bottom, float top, float near, float far) {
            float lr = right - left;
            float tb = top - bottom;
            float fn = far - near;

            Mat44f m;
            m(0, 0) = 2.0f / lr;
            m(2, 1) = -2.0f / tb; // cam Z up -> clip -Y
            m(1, 2) = 1.0f / fn;  // cam Y -> clip Z (0..1)
            m(3, 0) = -(right + left) / lr;
            m(3, 1) = (top + bottom) / tb; // sign flipped for Y-down
            m(3, 2) = -near / fn;
            m(3, 3) = 1.0f;

            return m;
        }

        // ========== View matrix (Y-forward, Z-up convention) ==========

        /**
         * Look-at view matrix.
         *
         * Creates a view matrix where camera is at 'eye', looking at 'target',
         * with 'up' direction (default: +Z).
         *
         * Convention: Y-forward, Z-up
         */
        static Mat44f look_at(const Vec3& eye, const Vec3& target, const Vec3& up = Vec3::unit_z()) {
            Vec3 forward = (target - eye).normalized();  // +Y direction in camera space
            Vec3 right = forward.cross(up).normalized(); // +X direction
            Vec3 up_ortho = right.cross(forward);        // +Z direction (orthogonalized up)

            Mat44f m = identity();

            // Rotation part (transposed because we're building the inverse)
            m(0, 0) = static_cast<float>(right.x);
            m(1, 0) = static_cast<float>(right.y);
            m(2, 0) = static_cast<float>(right.z);
            m(0, 1) = static_cast<float>(forward.x);
            m(1, 1) = static_cast<float>(forward.y);
            m(2, 1) = static_cast<float>(forward.z);
            m(0, 2) = static_cast<float>(up_ortho.x);
            m(1, 2) = static_cast<float>(up_ortho.y);
            m(2, 2) = static_cast<float>(up_ortho.z);

            // Translation part
            m(3, 0) = static_cast<float>(-right.dot(eye));
            m(3, 1) = static_cast<float>(-forward.dot(eye));
            m(3, 2) = static_cast<float>(-up_ortho.dot(eye));

            return m;
        }

        // ========== Compose transform (T * R * S) ==========

        /**
         * Compose TRS matrix: Translation * Rotation * Scale
         */
        static Mat44f compose(const Vec3& t, const Quat& r, const Vec3& s) {
            Mat44f rot = rotation(r);

            // Scale the rotation columns
            for (int i = 0; i < 3; ++i) {
                rot(0, i) *= static_cast<float>(s.x);
                rot(1, i) *= static_cast<float>(s.y);
                rot(2, i) *= static_cast<float>(s.z);
            }

            // Set translation
            rot(3, 0) = static_cast<float>(t.x);
            rot(3, 1) = static_cast<float>(t.y);
            rot(3, 2) = static_cast<float>(t.z);

            return rot;
        }

        // ========== Extract components ==========

        Vec3 get_translation() const {
            return {(*this)(3, 0), (*this)(3, 1), (*this)(3, 2)};
        }

        Vec3 get_scale() const {
            float sx = std::sqrt((*this)(0, 0) * (*this)(0, 0) + (*this)(0, 1) * (*this)(0, 1) +
                                 (*this)(0, 2) * (*this)(0, 2));
            float sy = std::sqrt((*this)(1, 0) * (*this)(1, 0) + (*this)(1, 1) * (*this)(1, 1) +
                                 (*this)(1, 2) * (*this)(1, 2));
            float sz = std::sqrt((*this)(2, 0) * (*this)(2, 0) + (*this)(2, 1) * (*this)(2, 1) +
                                 (*this)(2, 2) * (*this)(2, 2));
            return {sx, sy, sz};
        }

        // Return copy with modified translation
        Mat44f with_translation(const Vec3& t) const {
            Mat44f result = *this;
            result(3, 0) = static_cast<float>(t.x);
            result(3, 1) = static_cast<float>(t.y);
            result(3, 2) = static_cast<float>(t.z);
            return result;
        }

        Mat44f with_translation(float x, float y, float z) const {
            return with_translation(Vec3{x, y, z});
        }
    };

    // ============================================================================
    // Mat44 (double) - 4x4 Matrix in column-major order
    // ============================================================================

    struct Mat44 {
        double data[16]; // Column-major: [col0, col1, col2, col3]

        Mat44() {
            std::memset(data, 0, sizeof(data));
        }
        explicit Mat44(const double* column_major_16) noexcept {
            std::memcpy(data, column_major_16, sizeof(data));
        }
        explicit Mat44(const tc_mat44& value) noexcept
            : Mat44(value.m) {}

        static Mat44 from_column_major(const double* column_major_16) noexcept {
            return Mat44(column_major_16);
        }
        static Mat44 from_column_major_f64(const double* column_major_16) noexcept {
            return Mat44(column_major_16);
        }
        static Mat44 from_column_major_f32(const float* column_major_16) noexcept {
            Mat44 result;
            for (int i = 0; i < 16; ++i) {
                result.data[i] = static_cast<double>(column_major_16[i]);
            }
            return result;
        }
        static Mat44 from_tc_mat44(const tc_mat44& value) noexcept {
            return Mat44(value);
        }
        void copy_column_major_to(double* out_column_major_16) const noexcept {
            std::memcpy(out_column_major_16, data, sizeof(data));
        }
        tc_mat44 to_tc_mat44() const noexcept {
            tc_mat44 result;
            copy_column_major_to(result.m);
            return result;
        }

        // Access by column and row: m(col, row)
        double& operator()(int col, int row) {
            return data[col * 4 + row];
        }
        double operator()(int col, int row) const {
            return data[col * 4 + row];
        }

        double* ptr() {
            return data;
        }
        const double* ptr() const {
            return data;
        }

        bool is_finite() const noexcept {
            for (double value : data) {
                if (!std::isfinite(value)) {
                    return false;
                }
            }
            return true;
        }

        static Mat44 identity() {
            Mat44 m;
            m(0, 0) = 1;
            m(1, 1) = 1;
            m(2, 2) = 1;
            m(3, 3) = 1;
            return m;
        }

        static Mat44 zero() {
            return Mat44();
        }

        // Matrix multiplication
        Mat44 operator*(const Mat44& b) const {
            Mat44 result;
            for (int col = 0; col < 4; ++col) {
                for (int row = 0; row < 4; ++row) {
                    double sum = 0;
                    for (int k = 0; k < 4; ++k) {
                        sum += (*this)(k, row) * b(col, k);
                    }
                    result(col, row) = sum;
                }
            }
            return result;
        }

        Vec4 transform_homogeneous(const Vec4& value) const noexcept {
            return {
                (*this)(0, 0) * value.x + (*this)(1, 0) * value.y + (*this)(2, 0) * value.z + (*this)(3, 0) * value.w,
                (*this)(0, 1) * value.x + (*this)(1, 1) * value.y + (*this)(2, 1) * value.z + (*this)(3, 1) * value.w,
                (*this)(0, 2) * value.x + (*this)(1, 2) * value.y + (*this)(2, 2) * value.z + (*this)(3, 2) * value.w,
                (*this)(0, 3) * value.x + (*this)(1, 3) * value.y + (*this)(2, 3) * value.z + (*this)(3, 3) * value.w,
            };
        }

        // Transform point (w=1). The legacy unchecked fallback for near-zero w is preserved.
        Vec3 transform_point(const Vec3& p) const noexcept {
            const Vec4 transformed = transform_homogeneous({p.x, p.y, p.z, 1.0});
            const double x = transformed.x;
            const double y = transformed.y;
            const double z = transformed.z;
            const double w = transformed.w;
            if (std::abs(w) > 1e-10) {
                return {x / w, y / w, z / w};
            }
            return {x, y, z};
        }

        bool try_transform_point(const Vec3& point, Vec3& out, double epsilon = 1.0e-10) const noexcept {
            if (!point.is_finite() || !std::isfinite(epsilon) || epsilon < 0.0) {
                return false;
            }
            const Vec4 transformed = transform_homogeneous({point.x, point.y, point.z, 1.0});
            if (!transformed.is_finite() || std::abs(transformed.w) <= epsilon) {
                return false;
            }
            const Vec3 result{
                transformed.x / transformed.w, transformed.y / transformed.w, transformed.z / transformed.w};
            if (!result.is_finite()) {
                return false;
            }
            out = result;
            return true;
        }

        // Transform direction (w=0)
        Vec3 transform_direction(const Vec3& d) const noexcept {
            return {(*this)(0, 0) * d.x + (*this)(1, 0) * d.y + (*this)(2, 0) * d.z,
                    (*this)(0, 1) * d.x + (*this)(1, 1) * d.y + (*this)(2, 1) * d.z,
                    (*this)(0, 2) * d.x + (*this)(1, 2) * d.y + (*this)(2, 2) * d.z};
        }

        // Transpose
        Mat44 transposed() const {
            Mat44 result;
            for (int i = 0; i < 4; ++i) {
                for (int j = 0; j < 4; ++j) {
                    result(i, j) = (*this)(j, i);
                }
            }
            return result;
        }

        double determinant() const {
            const double* m = data;
            const double c00 = m[5] * m[10] * m[15] - m[5] * m[11] * m[14] - m[9] * m[6] * m[15] + m[9] * m[7] * m[14] +
                               m[13] * m[6] * m[11] - m[13] * m[7] * m[10];
            const double c04 = -m[4] * m[10] * m[15] + m[4] * m[11] * m[14] + m[8] * m[6] * m[15] -
                               m[8] * m[7] * m[14] - m[12] * m[6] * m[11] + m[12] * m[7] * m[10];
            const double c08 = m[4] * m[9] * m[15] - m[4] * m[11] * m[13] - m[8] * m[5] * m[15] + m[8] * m[7] * m[13] +
                               m[12] * m[5] * m[11] - m[12] * m[7] * m[9];
            const double c12 = -m[4] * m[9] * m[14] + m[4] * m[10] * m[13] + m[8] * m[5] * m[14] - m[8] * m[6] * m[13] -
                               m[12] * m[5] * m[10] + m[12] * m[6] * m[9];
            return m[0] * c00 + m[1] * c04 + m[2] * c08 + m[3] * c12;
        }

        // Checked inverse with the same two-sided reliability contract as Mat44f.
        bool try_inverse(Mat44& out, double epsilon = 1.0e-12) const noexcept {
            return detail::try_inverse_mat44(data, out.data, epsilon);
        }

        // Legacy API: singular or non-finite matrices still fall back to identity.
        Mat44 inverse() const {
            Mat44 result;
            return try_inverse(result, 0.0) ? result : identity();
        }

        // Conversion to float
        Mat44f to_float() const {
            Mat44f m;
            for (int i = 0; i < 16; ++i) {
                m.data[i] = static_cast<float>(data[i]);
            }
            return m;
        }

        // ========== Construction from components ==========

        static Mat44 translation(const Vec3& t) {
            Mat44 m = identity();
            m(3, 0) = t.x;
            m(3, 1) = t.y;
            m(3, 2) = t.z;
            return m;
        }

        static Mat44 translation(double x, double y, double z) {
            return translation(Vec3{x, y, z});
        }

        static Mat44 scale(const Vec3& s) {
            Mat44 m;
            m(0, 0) = s.x;
            m(1, 1) = s.y;
            m(2, 2) = s.z;
            m(3, 3) = 1;
            return m;
        }

        static Mat44 scale(double s) {
            return scale(Vec3{s, s, s});
        }

        // Fast path: q must be a finite unit quaternion. Use try_rotation when
        // the quaternion comes from an unchecked boundary.
        static Mat44 rotation(const Quat& q) noexcept {
            double row_major[9];
            q.to_matrix(row_major);

            Mat44 m = identity();
            for (int row = 0; row < 3; ++row) {
                for (int column = 0; column < 3; ++column) {
                    m(column, row) = row_major[row * 3 + column];
                }
            }
            return m;
        }

        static bool try_rotation(const Quat& q, Mat44& out, double epsilon = 1.0e-12) noexcept {
            double row_major[9];
            if (!q.try_to_matrix(row_major, epsilon)) {
                return false;
            }

            Mat44 result = identity();
            for (int row = 0; row < 3; ++row) {
                for (int column = 0; column < 3; ++column) {
                    result(column, row) = row_major[row * 3 + column];
                }
            }
            out = result;
            return true;
        }

        static bool
        try_rotation_axis_angle(const Vec3& axis, double angle, Mat44& out, double epsilon = 1.0e-12) noexcept {
            Quat orientation;
            if (!Quat::try_from_axis_angle(axis, angle, orientation, epsilon)) {
                return false;
            }
            // epsilon belongs to the source-axis magnitude contract. The
            // quaternion produced above is already checked and normalized.
            return try_rotation(orientation, out, 0.0);
        }

        // Invalid axis-angle input is represented by a non-finite matrix. Use
        // try_rotation_axis_angle at unchecked boundaries.
        static Mat44 rotation_axis_angle(const Vec3& axis, double angle) noexcept {
            return rotation(Quat::from_axis_angle(axis, angle));
        }

        // Double-precision twin of Mat44f::perspective — same Vulkan-native
        // NDC convention (clip Y-down, Z ∈ [0, 1]). See the Mat44f comment.
        static Mat44 perspective(double fov_y, double aspect, double near, double far) {
            double f = 1.0 / std::tan(fov_y * 0.5);
            Mat44 m;
            m(0, 0) = f / aspect;
            m(2, 1) = -f;
            m(1, 2) = far / (far - near);
            m(3, 2) = -(far * near) / (far - near);
            m(1, 3) = 1.0;
            return m;
        }

        // Perspective with independent horizontal and vertical FOV (may cause distortion)
        static Mat44 perspective_fov_xy(double fov_x, double fov_y, double near, double far) {
            double fx = 1.0 / std::tan(fov_x * 0.5);
            double fy = 1.0 / std::tan(fov_y * 0.5);
            Mat44 m;
            m(0, 0) = fx;
            m(2, 1) = -fy;
            m(1, 2) = far / (far - near);
            m(3, 2) = -(far * near) / (far - near);
            m(1, 3) = 1.0;
            return m;
        }

        static Mat44 orthographic(double left, double right, double bottom, double top, double near, double far) {
            double lr = right - left;
            double tb = top - bottom;
            double fn = far - near;

            Mat44 m;
            m(0, 0) = 2.0 / lr;
            m(2, 1) = -2.0 / tb;
            m(1, 2) = 1.0 / fn;
            m(3, 0) = -(right + left) / lr;
            m(3, 1) = (top + bottom) / tb;
            m(3, 2) = -near / fn;
            m(3, 3) = 1.0;
            return m;
        }

        static Mat44 look_at(const Vec3& eye, const Vec3& target, const Vec3& up = Vec3::unit_z()) {
            Vec3 forward = (target - eye).normalized();
            Vec3 right = forward.cross(up).normalized();
            Vec3 up_ortho = right.cross(forward);

            Mat44 m = identity();
            m(0, 0) = right.x;
            m(1, 0) = right.y;
            m(2, 0) = right.z;
            m(0, 1) = forward.x;
            m(1, 1) = forward.y;
            m(2, 1) = forward.z;
            m(0, 2) = up_ortho.x;
            m(1, 2) = up_ortho.y;
            m(2, 2) = up_ortho.z;
            m(3, 0) = -right.dot(eye);
            m(3, 1) = -forward.dot(eye);
            m(3, 2) = -up_ortho.dot(eye);
            return m;
        }

        static Mat44 compose(const Vec3& t, const Quat& r, const Vec3& s) {
            Mat44 rot = rotation(r);
            for (int i = 0; i < 3; ++i) {
                rot(0, i) *= s.x;
                rot(1, i) *= s.y;
                rot(2, i) *= s.z;
            }
            rot(3, 0) = t.x;
            rot(3, 1) = t.y;
            rot(3, 2) = t.z;
            return rot;
        }

        Vec3 get_translation() const {
            return {(*this)(3, 0), (*this)(3, 1), (*this)(3, 2)};
        }

        Vec3 get_scale() const {
            double sx = std::sqrt((*this)(0, 0) * (*this)(0, 0) + (*this)(0, 1) * (*this)(0, 1) +
                                  (*this)(0, 2) * (*this)(0, 2));
            double sy = std::sqrt((*this)(1, 0) * (*this)(1, 0) + (*this)(1, 1) * (*this)(1, 1) +
                                  (*this)(1, 2) * (*this)(1, 2));
            double sz = std::sqrt((*this)(2, 0) * (*this)(2, 0) + (*this)(2, 1) * (*this)(2, 1) +
                                  (*this)(2, 2) * (*this)(2, 2));
            return {sx, sy, sz};
        }

        // Return copy with modified translation
        Mat44 with_translation(const Vec3& t) const {
            Mat44 result = *this;
            result(3, 0) = t.x;
            result(3, 1) = t.y;
            result(3, 2) = t.z;
            return result;
        }

        Mat44 with_translation(double x, double y, double z) const {
            return with_translation(Vec3{x, y, z});
        }
    };

    inline Mat44 Mat44f::to_double() const noexcept {
        Mat44 result;
        for (int i = 0; i < 16; ++i) {
            result.data[i] = static_cast<double>(data[i]);
        }
        return result;
    }

    static_assert(std::is_standard_layout<Mat44>::value, "Mat44 must stay standard layout");
    static_assert(std::is_trivially_copyable<Mat44>::value, "Mat44 must stay trivially copyable");
    static_assert(sizeof(Mat44) == sizeof(double) * 16, "Mat44 must stay a packed column-major matrix");
    static_assert(offsetof(Mat44, data) == 0, "Mat44.data offset changed");
    static_assert(std::is_standard_layout<Mat44f>::value, "Mat44f must stay standard layout");
    static_assert(std::is_trivially_copyable<Mat44f>::value, "Mat44f must stay trivially copyable");
    static_assert(sizeof(Mat44f) == sizeof(float) * 16, "Mat44f must stay a packed column-major matrix");
    static_assert(offsetof(Mat44f, data) == 0, "Mat44f.data offset changed");

} // namespace termin
