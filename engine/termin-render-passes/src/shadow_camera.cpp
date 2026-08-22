#include "termin/render/shadow_camera.hpp"
#include <tcbase/tc_log.hpp>
#include <termin/geom/aabb.hpp>

#include <algorithm>
#include <cmath>
#include <vector>

namespace termin {

    namespace {

        constexpr double kLightDirectionEpsilon = 0.0;

        struct LightBasis {
            Vec3 direction;
            Vec3 right;
            Vec3 up;
        };

        LightBasis make_light_basis(const Vec3& light_direction) {
            const Vec3 direction = light_direction.normalized_or(Vec3::unit_y(), 1.0e-6);
            const Vec3 world_up = std::abs(direction.dot(Vec3::unit_z())) > 0.99 ? Vec3::unit_y() : Vec3::unit_z();
            const Vec3 right = direction.cross(world_up).normalized_or(Vec3::unit_x(), 1.0e-6);
            const Vec3 up = right.cross(direction).normalized_or(Vec3::unit_z(), 1.0e-6);
            return {direction, right, up};
        }

        Mat44f rotation_matrix(const LightBasis& basis) {
            Mat44f view = Mat44f::identity();
            view(0, 0) = static_cast<float>(basis.right.x);
            view(1, 0) = static_cast<float>(basis.right.y);
            view(2, 0) = static_cast<float>(basis.right.z);
            view(0, 1) = static_cast<float>(basis.up.x);
            view(1, 1) = static_cast<float>(basis.up.y);
            view(2, 1) = static_cast<float>(basis.up.z);
            view(0, 2) = static_cast<float>(-basis.direction.x);
            view(1, 2) = static_cast<float>(-basis.direction.y);
            view(2, 2) = static_cast<float>(-basis.direction.z);
            return view;
        }

        bool validate_fit_domain(const Vec3& light_direction,
                                 float padding,
                                 int shadow_map_resolution,
                                 float caster_offset,
                                 const char* operation,
                                 Vec3& normalized_light_direction) {
            if (!light_direction.try_normalized(normalized_light_direction, kLightDirectionEpsilon)) {
                tc::Log::error("[ShadowCamera] %s: light_direction must be finite and non-zero", operation);
                return false;
            }
            if (!std::isfinite(padding) || padding < 0.0f) {
                tc::Log::error("[ShadowCamera] %s: padding must be finite and non-negative", operation);
                return false;
            }
            if (shadow_map_resolution <= 0) {
                tc::Log::error("[ShadowCamera] %s: shadow_map_resolution must be positive", operation);
                return false;
            }
            if (!std::isfinite(caster_offset) || caster_offset < 0.0f) {
                tc::Log::error("[ShadowCamera] %s: caster_offset must be finite and non-negative", operation);
                return false;
            }
            return true;
        }

        bool validate_cascade_range(const ShadowCascadeFitRequest& request) {
            if (!std::isfinite(request.camera_near) || !std::isfinite(request.camera_far) ||
                !std::isfinite(request.cascade_near) || !std::isfinite(request.cascade_far)) {
                tc::Log::error(
                    "[ShadowCamera] try_fit_shadow_frustum_for_cascade: camera and cascade ranges must be finite");
                return false;
            }
            if (request.camera_near <= 0.0f || request.camera_far <= request.camera_near) {
                tc::Log::error(
                    "[ShadowCamera] try_fit_shadow_frustum_for_cascade: camera range must satisfy 0 < near < far");
                return false;
            }
            if (request.cascade_near < request.camera_near || request.cascade_far > request.camera_far ||
                request.cascade_far <= request.cascade_near) {
                tc::Log::error("[ShadowCamera] try_fit_shadow_frustum_for_cascade: cascade range must be non-empty "
                               "and contained in the camera range");
                return false;
            }
            return true;
        }

        bool has_finite_area(const Bounds2f& bounds) {
            const float width = bounds.width();
            const float height = bounds.height();
            return bounds.is_valid() && std::isfinite(width) && std::isfinite(height) && width > 0.0f &&
                   height > 0.0f;
        }

        std::array<Vec3, 8> slice_frustum_corners(const std::array<Vec3, 8>& full_frustum_corners,
                                                  float camera_near,
                                                  float camera_far,
                                                  float slice_near,
                                                  float slice_far) {
            const float depth_range = camera_far - camera_near;
            float near_t = (slice_near - camera_near) / depth_range;
            float far_t = (slice_far - camera_near) / depth_range;
            near_t = std::clamp(near_t, 0.0f, 1.0f);
            far_t = std::clamp(far_t, near_t, 1.0f);

            std::array<Vec3, 8> slice_corners;
            for (int i = 0; i < 4; ++i) {
                const Vec3& near_corner = full_frustum_corners[i];
                const Vec3& far_corner = full_frustum_corners[i + 4];
                const Vec3 ray = far_corner - near_corner;
                slice_corners[i] = near_corner + ray * near_t;
                slice_corners[i + 4] = near_corner + ray * far_t;
            }
            return slice_corners;
        }

        std::optional<ShadowCameraParams> fit_shadow_corners(const std::array<Vec3, 8>& frustum_corners,
                                                            const Vec3& normalized_light_direction,
                                                            float padding,
                                                            int shadow_map_resolution,
                                                            bool stabilize,
                                                            float caster_offset) {
            Vec3 center = Vec3::zero();
            for (const Vec3& corner : frustum_corners) {
                if (!corner.is_finite()) {
                    tc::Log::error("[ShadowCamera] cannot fit shadow corners: frustum contains a non-finite point");
                    return std::nullopt;
                }
                center += corner;
            }
            center /= static_cast<double>(frustum_corners.size());
            if (!center.is_finite()) {
                tc::Log::error("[ShadowCamera] cannot fit shadow corners: frustum center is non-finite");
                return std::nullopt;
            }

            const Mat44f light_rotation = build_light_rotation_matrix(normalized_light_direction);
            AABBf light_bounds;
            bool has_light_bounds = false;
            for (const Vec3& corner : frustum_corners) {
                const Vec3f centered = (corner - center).to_float();
                const Vec3f light_corner = light_rotation.transform_direction(centered);
                if (!light_corner.is_finite()) {
                    tc::Log::error(
                        "[ShadowCamera] cannot fit shadow corners: light-space point exceeds the float render domain");
                    return std::nullopt;
                }
                if (!has_light_bounds) {
                    light_bounds = AABBf{light_corner, light_corner};
                    has_light_bounds = true;
                } else {
                    light_bounds.extend(light_corner);
                }
            }
            if (!has_light_bounds || !light_bounds.is_valid()) {
                tc::Log::error("[ShadowCamera] cannot fit shadow corners: light-space bounds are invalid");
                return std::nullopt;
            }

            float left = light_bounds.min_point.x - padding;
            float right = light_bounds.max_point.x + padding;
            float bottom = light_bounds.min_point.y - padding;
            float top = light_bounds.max_point.y + padding;
            Bounds2f ortho_bounds{left, bottom, right, top};
            if (!has_finite_area(ortho_bounds)) {
                tc::Log::error("[ShadowCamera] cannot fit shadow corners: orthographic bounds are invalid or empty");
                return std::nullopt;
            }

            if (stabilize) {
                const float world_units_per_texel_x = (right - left) / shadow_map_resolution;
                const float world_units_per_texel_y = (top - bottom) / shadow_map_resolution;
                if (!std::isfinite(world_units_per_texel_x) || !std::isfinite(world_units_per_texel_y) ||
                    world_units_per_texel_x <= 0.0f || world_units_per_texel_y <= 0.0f) {
                    tc::Log::error("[ShadowCamera] cannot fit shadow corners: texel scale is invalid");
                    return std::nullopt;
                }

                left = std::floor(left / world_units_per_texel_x) * world_units_per_texel_x;
                right = std::ceil(right / world_units_per_texel_x) * world_units_per_texel_x;
                bottom = std::floor(bottom / world_units_per_texel_y) * world_units_per_texel_y;
                top = std::ceil(top / world_units_per_texel_y) * world_units_per_texel_y;

                Vec3f center_light = light_rotation.transform_direction(center.to_float());
                if (!center_light.is_finite()) {
                    tc::Log::error(
                        "[ShadowCamera] cannot fit shadow corners: center exceeds the float render domain");
                    return std::nullopt;
                }
                center_light.x = std::floor(center_light.x / world_units_per_texel_x) * world_units_per_texel_x;
                center_light.y = std::floor(center_light.y / world_units_per_texel_y) * world_units_per_texel_y;
                center = light_rotation.transposed().transform_direction(center_light).to_double();
                if (!center.is_finite()) {
                    tc::Log::error("[ShadowCamera] cannot fit shadow corners: stabilized center is non-finite");
                    return std::nullopt;
                }

                ortho_bounds = Bounds2f{left, bottom, right, top};
                if (!has_finite_area(ortho_bounds)) {
                    tc::Log::error("[ShadowCamera] cannot fit shadow corners: stabilized bounds are invalid or empty");
                    return std::nullopt;
                }
            }

            const float z_near = light_bounds.min_point.z - caster_offset;
            const float z_far = light_bounds.max_point.z + padding;
            const float near = std::max(-z_far, 0.1f);
            const float far = -z_near;
            if (!std::isfinite(near) || !std::isfinite(far) || far <= near) {
                tc::Log::error("[ShadowCamera] cannot fit shadow corners: depth range is invalid or empty");
                return std::nullopt;
            }

            return ShadowCameraParams{
                normalized_light_direction, ortho_bounds, 20.0f, near, far, center};
        }

    } // anonymous namespace

    Mat44f build_light_rotation_matrix(const Vec3& light_direction) {
        return rotation_matrix(make_light_basis(light_direction));
    }

    Mat44f build_shadow_view_matrix(const ShadowCameraParams& params) {
        const LightBasis basis = make_light_basis(params.light_direction);
        const Vec3 eye = shadow_camera_position(params);
        Mat44f view = rotation_matrix(basis);

        // Translation (column 3)
        view(3, 0) = static_cast<float>(-basis.right.dot(eye));
        view(3, 1) = static_cast<float>(-basis.up.dot(eye));
        view(3, 2) = static_cast<float>(basis.direction.dot(eye));

        return view;
    }

    Vec3 shadow_camera_position(const ShadowCameraParams& params) {
        const Vec3 direction = params.light_direction.normalized_or(Vec3::unit_y(), 1.0e-6);
        const float camera_distance = (params.near + params.far) / 2.0f;
        return params.center - direction * camera_distance;
    }

    Mat44f build_shadow_projection_matrix(const ShadowCameraParams& params) {
        float near = params.near;
        float far = params.far;

        float left, right_bound, bottom, top;

        if (params.ortho_bounds.has_value()) {
            const auto& bounds = *params.ortho_bounds;
            left = bounds.x0;
            bottom = bounds.y0;
            right_bound = bounds.x1;
            top = bounds.y1;
        } else {
            float size = params.ortho_size;
            left = -size;
            right_bound = size;
            bottom = -size;
            top = size;
        }

        Mat44f proj = Mat44f::zero();

        // Vulkan-native NDC: Y+ down, Z ∈ [0, 1]. Shadow camera looks along
        // its own -Z (standard graphics convention in build_shadow_view_matrix).
        // See termin-base/include/termin/geom/mat44.hpp for the matching scene
        // projection.
        proj(0, 0) = 2.0f / (right_bound - left);
        proj(1, 1) = -2.0f / (top - bottom); // Y flipped
        proj(2, 2) = -1.0f / (far - near);   // Z ∈ [0, 1]

        proj(3, 0) = -(right_bound + left) / (right_bound - left);
        proj(3, 1) = (top + bottom) / (top - bottom); // sign flipped
        proj(3, 2) = -near / (far - near);
        proj(3, 3) = 1.0f;

        return proj;
    }

    Mat44f compute_light_space_matrix(const ShadowCameraParams& params) {
        Mat44f view = build_shadow_view_matrix(params);
        Mat44f proj = build_shadow_projection_matrix(params);
        return proj * view;
    }

    std::optional<std::array<Vec3, 8>>
    compute_frustum_corners(const Mat44& view_matrix, const Mat44& projection_matrix) {
        // NDC cube corners — Z ∈ [0, 1] (near=0, far=1) to match the
        // Vulkan-native projection convention used everywhere.
        static constexpr std::array<Vec3, 8> ndc_corners{{
            {-1.0, -1.0, 0.0},
            {1.0, -1.0, 0.0},
            {1.0, 1.0, 0.0},
            {-1.0, 1.0, 0.0},
            {-1.0, -1.0, 1.0},
            {1.0, -1.0, 1.0},
            {1.0, 1.0, 1.0},
            {-1.0, 1.0, 1.0},
        }};

        const Mat44 view_projection = projection_matrix * view_matrix;
        Mat44 inverse_view_projection;
        if (!view_projection.try_inverse(inverse_view_projection)) {
            tc::Log::error("[ShadowCamera] cannot compute frustum corners: view-projection matrix is singular");
            return std::nullopt;
        }

        std::array<Vec3, 8> world_corners;
        for (size_t i = 0; i < ndc_corners.size(); ++i) {
            Vec3 world_corner;
            if (!inverse_view_projection.try_transform_point(ndc_corners[i], world_corner)) {
                tc::Log::error("[ShadowCamera] cannot compute frustum corner %zu: homogeneous w is invalid", i);
                return std::nullopt;
            }
            world_corners[i] = world_corner;
        }

        return world_corners;
    }

    std::optional<ShadowCameraParams> fit_shadow_frustum_to_camera(const Mat44& view_matrix,
                                                                   const Mat44& projection_matrix,
                                                                   const Vec3& light_direction,
                                                                   float padding,
                                                                   int shadow_map_resolution,
                                                                   bool stabilize,
                                                                   float caster_offset) {
        Vec3 normalized_light_direction;
        if (!validate_fit_domain(light_direction,
                                 padding,
                                 shadow_map_resolution,
                                 caster_offset,
                                 "fit_shadow_frustum_to_camera",
                                 normalized_light_direction)) {
            return std::nullopt;
        }
        const auto frustum_corners = compute_frustum_corners(view_matrix, projection_matrix);
        if (!frustum_corners.has_value()) {
            return std::nullopt;
        }
        return fit_shadow_corners(*frustum_corners,
                                  normalized_light_direction,
                                  padding,
                                  shadow_map_resolution,
                                  stabilize,
                                  caster_offset);
    }

    std::vector<float> compute_cascade_splits(float near, float far, int cascade_count, float lambda) {
        // Clamp cascade count to valid range
        cascade_count = std::max(1, std::min(4, cascade_count));

        std::vector<float> splits(cascade_count + 1);
        splits[0] = near;
        splits[cascade_count] = far;

        // Single cascade: just near and far
        if (cascade_count == 1) {
            return splits;
        }

        // PSSM split scheme: blend of logarithmic and linear
        // C_log(i) = near * (far/near)^(i/n)
        // C_lin(i) = near + (far-near) * (i/n)
        // C(i) = lambda * C_log(i) + (1-lambda) * C_lin(i)
        float ratio = far / near;

        for (int i = 1; i < cascade_count; ++i) {
            float p = static_cast<float>(i) / static_cast<float>(cascade_count);

            // Logarithmic split
            float c_log = near * std::pow(ratio, p);

            // Linear split
            float c_lin = near + (far - near) * p;

            // Blend
            splits[i] = lambda * c_log + (1.0f - lambda) * c_lin;
        }

        return splits;
    }

    std::optional<ShadowCameraParams> try_fit_shadow_frustum_for_cascade(const ShadowCascadeFitRequest& request) {
        Vec3 normalized_light_direction;
        if (!validate_fit_domain(request.light_direction,
                                 1.0f,
                                 request.shadow_map_resolution,
                                 request.caster_offset,
                                 "try_fit_shadow_frustum_for_cascade",
                                 normalized_light_direction) ||
            !validate_cascade_range(request)) {
            return std::nullopt;
        }
        // Use the real camera frustum and slice it along its rays. Rebuilding a
        // symmetric projection from FOV/aspect loses asymmetric XR projection
        // offsets and clips visible shadow coverage near the view edges.
        const auto full_frustum_corners = compute_frustum_corners(request.view_matrix, request.projection_matrix);
        if (!full_frustum_corners.has_value()) {
            return std::nullopt;
        }
        const std::array<Vec3, 8> frustum_corners = slice_frustum_corners(
            *full_frustum_corners, request.camera_near, request.camera_far, request.cascade_near, request.cascade_far);
        return fit_shadow_corners(frustum_corners,
                                  normalized_light_direction,
                                  1.0f,
                                  request.shadow_map_resolution,
                                  true,
                                  request.caster_offset);
    }

} // namespace termin
