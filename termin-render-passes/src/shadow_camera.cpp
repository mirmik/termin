#include "termin/render/shadow_camera.hpp"
#include <tcbase/tc_log.hpp>

#include <cmath>
#include <algorithm>
#include <vector>

namespace termin {

namespace {

// Normalize vector, return default if length is near zero
Vec3 safe_normalize(const Vec3& v, const Vec3& fallback = Vec3{0, 1, 0}) {
    float len = static_cast<float>(v.norm());
    if (len < 1e-6f) {
        return fallback;
    }
    return v / len;
}

std::array<Vec3, 8> slice_frustum_corners(
    const std::array<Vec3, 8>& full_frustum_corners,
    float camera_near,
    float camera_far,
    float slice_near,
    float slice_far
) {
    float depth_range = camera_far - camera_near;
    if (depth_range < 1e-6f) {
        depth_range = 1.0f;
    }

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

} // anonymous namespace


Mat44f build_light_rotation_matrix(const Vec3& light_direction) {
    Vec3 direction = safe_normalize(light_direction, Vec3{0, 1, 0});

    // Up vector (Z-up in this engine)
    Vec3 world_up{0.0, 0.0, 1.0};
    if (std::abs(direction.dot(world_up)) > 0.99f) {
        // Light looks along Z — use Y as temporary up
        world_up = Vec3{0.0, 1.0, 0.0};
    }

    Vec3 right = direction.cross(world_up).normalized();
    Vec3 up = right.cross(direction).normalized();

    // View matrix (rotation only, no translation)
    // Mat44f uses column-major: m(col, row)
    Mat44f view = Mat44f::identity();

    // Row 0: right vector
    view(0, 0) = static_cast<float>(right.x);
    view(1, 0) = static_cast<float>(right.y);
    view(2, 0) = static_cast<float>(right.z);

    // Row 1: up vector
    view(0, 1) = static_cast<float>(up.x);
    view(1, 1) = static_cast<float>(up.y);
    view(2, 1) = static_cast<float>(up.z);

    // Row 2: -direction (camera looks along -Z in its own space)
    view(0, 2) = static_cast<float>(-direction.x);
    view(1, 2) = static_cast<float>(-direction.y);
    view(2, 2) = static_cast<float>(-direction.z);

    return view;
}


Mat44f build_shadow_view_matrix(const ShadowCameraParams& params) {
    Vec3 direction = safe_normalize(params.light_direction, Vec3{0, 1, 0});

    // Position camera so scene center is roughly between near and far
    Vec3 eye = shadow_camera_position(params);

    // Choose up vector orthogonal to direction
    // Coordinate system: X-right, Y-forward, Z-up
    Vec3 world_up{0.0, 0.0, 1.0};
    if (std::abs(direction.dot(world_up)) > 0.99f) {
        // Light looks along Z — use Y as temporary up
        world_up = Vec3{0.0, 1.0, 0.0};
    }

    // Right vector
    Vec3 right = direction.cross(world_up).normalized();

    // True up
    Vec3 up = right.cross(direction).normalized();

    // Build view matrix (look-at)
    // View = R * T, where R is rotation, T is translation
    // Mat44f uses column-major: m(col, row)
    Mat44f view = Mat44f::identity();

    // Row 0: right vector
    view(0, 0) = static_cast<float>(right.x);
    view(1, 0) = static_cast<float>(right.y);
    view(2, 0) = static_cast<float>(right.z);

    // Row 1: up vector
    view(0, 1) = static_cast<float>(up.x);
    view(1, 1) = static_cast<float>(up.y);
    view(2, 1) = static_cast<float>(up.z);

    // Row 2: -direction (camera looks along -Z in its own space)
    view(0, 2) = static_cast<float>(-direction.x);
    view(1, 2) = static_cast<float>(-direction.y);
    view(2, 2) = static_cast<float>(-direction.z);

    // Translation (column 3)
    view(3, 0) = static_cast<float>(-right.dot(eye));
    view(3, 1) = static_cast<float>(-up.dot(eye));
    view(3, 2) = static_cast<float>(direction.dot(eye));

    return view;
}

Vec3 shadow_camera_position(const ShadowCameraParams& params) {
    Vec3 direction = safe_normalize(params.light_direction, Vec3{0, 1, 0});
    float camera_distance = (params.near + params.far) / 2.0f;
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
    proj(1, 1) = -2.0f / (top - bottom);             // Y flipped
    proj(2, 2) = -1.0f / (far - near);               // Z ∈ [0, 1]

    proj(3, 0) = -(right_bound + left) / (right_bound - left);
    proj(3, 1) = (top + bottom) / (top - bottom);    // sign flipped
    proj(3, 2) = -near / (far - near);
    proj(3, 3) = 1.0f;

    return proj;
}


Mat44f compute_light_space_matrix(const ShadowCameraParams& params) {
    Mat44f view = build_shadow_view_matrix(params);
    Mat44f proj = build_shadow_projection_matrix(params);
    return proj * view;
}


std::array<Vec3, 8> compute_frustum_corners(
    const Mat44f& view_matrix,
    const Mat44f& projection_matrix
) {
    // NDC cube corners — Z ∈ [0, 1] (near=0, far=1) to match the
    // Vulkan-native projection convention used everywhere.
    static const float ndc_corners[8][3] = {
        {-1, -1,  0},  // near bottom left
        { 1, -1,  0},  // near bottom right
        { 1,  1,  0},  // near top right
        {-1,  1,  0},  // near top left
        {-1, -1,  1},  // far bottom left
        { 1, -1,  1},  // far bottom right
        { 1,  1,  1},  // far top right
        {-1,  1,  1},  // far top left
    };

    // Inverse view-projection matrix
    Mat44f vp = projection_matrix * view_matrix;
    Mat44f inv_vp = vp.inverse();

    std::array<Vec3, 8> world_corners;

    for (int i = 0; i < 8; ++i) {
        Vec3 ndc{ndc_corners[i][0], ndc_corners[i][1], ndc_corners[i][2]};

        // Transform by inverse VP with w=1
        float x = inv_vp(0, 0) * static_cast<float>(ndc.x) + inv_vp(1, 0) * static_cast<float>(ndc.y) + inv_vp(2, 0) * static_cast<float>(ndc.z) + inv_vp(3, 0);
        float y = inv_vp(0, 1) * static_cast<float>(ndc.x) + inv_vp(1, 1) * static_cast<float>(ndc.y) + inv_vp(2, 1) * static_cast<float>(ndc.z) + inv_vp(3, 1);
        float z = inv_vp(0, 2) * static_cast<float>(ndc.x) + inv_vp(1, 2) * static_cast<float>(ndc.y) + inv_vp(2, 2) * static_cast<float>(ndc.z) + inv_vp(3, 2);
        float w = inv_vp(0, 3) * static_cast<float>(ndc.x) + inv_vp(1, 3) * static_cast<float>(ndc.y) + inv_vp(2, 3) * static_cast<float>(ndc.z) + inv_vp(3, 3);

        // Perspective divide
        world_corners[i] = Vec3{x / w, y / w, z / w};
    }

    return world_corners;
}


ShadowCameraParams fit_shadow_frustum_to_camera(
    const Mat44f& view_matrix,
    const Mat44f& projection_matrix,
    const Vec3& light_direction,
    float padding,
    int shadow_map_resolution,
    bool stabilize,
    float caster_offset
) {
    Vec3 light_dir = safe_normalize(light_direction, Vec3{0, 1, 0});

    // 1. Get camera frustum corners in world space
    std::array<Vec3, 8> frustum_corners = compute_frustum_corners(view_matrix, projection_matrix);

    // 2. Compute frustum center
    Vec3 center{0, 0, 0};
    for (const auto& corner : frustum_corners) {
        center = center + corner;
    }
    center = center / 8.0;

    // 3. Build light-space rotation matrix
    Mat44f light_rotation = build_light_rotation_matrix(light_dir);

    // 4. Transform CENTERED frustum corners to light space
    std::array<Vec3, 8> light_space_corners;
    for (int i = 0; i < 8; ++i) {
        Vec3 centered = frustum_corners[i] - center;

        // Transform by light rotation (only rotation part, no translation)
        float x = light_rotation(0, 0) * static_cast<float>(centered.x) + light_rotation(1, 0) * static_cast<float>(centered.y) + light_rotation(2, 0) * static_cast<float>(centered.z);
        float y = light_rotation(0, 1) * static_cast<float>(centered.x) + light_rotation(1, 1) * static_cast<float>(centered.y) + light_rotation(2, 1) * static_cast<float>(centered.z);
        float z = light_rotation(0, 2) * static_cast<float>(centered.x) + light_rotation(1, 2) * static_cast<float>(centered.y) + light_rotation(2, 2) * static_cast<float>(centered.z);

        light_space_corners[i] = Vec3{x, y, z};
    }

    // 5. Compute AABB in light space
    Vec3 min_bounds = light_space_corners[0];
    Vec3 max_bounds = light_space_corners[0];

    for (int i = 1; i < 8; ++i) {
        min_bounds.x = std::min(min_bounds.x, light_space_corners[i].x);
        min_bounds.y = std::min(min_bounds.y, light_space_corners[i].y);
        min_bounds.z = std::min(min_bounds.z, light_space_corners[i].z);

        max_bounds.x = std::max(max_bounds.x, light_space_corners[i].x);
        max_bounds.y = std::max(max_bounds.y, light_space_corners[i].y);
        max_bounds.z = std::max(max_bounds.z, light_space_corners[i].z);
    }

    // X, Y — ortho bounds; Z — near/far
    float left = static_cast<float>(min_bounds.x) - padding;
    float right = static_cast<float>(max_bounds.x) + padding;
    float bottom = static_cast<float>(min_bounds.y) - padding;
    float top = static_cast<float>(max_bounds.y) + padding;

    // 6. Stabilization (Texel Snapping) to prevent shadow jitter
    if (stabilize && shadow_map_resolution > 0) {
        // Size of ortho box
        float world_units_per_texel_x = (right - left) / shadow_map_resolution;
        float world_units_per_texel_y = (top - bottom) / shadow_map_resolution;

        // Round bounds to texel size
        // This prevents subpixel shift when camera moves
        left = std::floor(left / world_units_per_texel_x) * world_units_per_texel_x;
        right = std::ceil(right / world_units_per_texel_x) * world_units_per_texel_x;
        bottom = std::floor(bottom / world_units_per_texel_y) * world_units_per_texel_y;
        top = std::ceil(top / world_units_per_texel_y) * world_units_per_texel_y;

        // Also stabilize center in light space
        float center_light_x = light_rotation(0, 0) * static_cast<float>(center.x) + light_rotation(1, 0) * static_cast<float>(center.y) + light_rotation(2, 0) * static_cast<float>(center.z);
        float center_light_y = light_rotation(0, 1) * static_cast<float>(center.x) + light_rotation(1, 1) * static_cast<float>(center.y) + light_rotation(2, 1) * static_cast<float>(center.z);
        float center_light_z = light_rotation(0, 2) * static_cast<float>(center.x) + light_rotation(1, 2) * static_cast<float>(center.y) + light_rotation(2, 2) * static_cast<float>(center.z);

        // Snap center in light space to texels
        center_light_x = std::floor(center_light_x / world_units_per_texel_x) * world_units_per_texel_x;
        center_light_y = std::floor(center_light_y / world_units_per_texel_y) * world_units_per_texel_y;

        // Transform back to world space
        // Inverse of rotation-only matrix is its transpose
        // For column-major: inv_rot(col, row) = rot(row, col)
        center.x = light_rotation(0, 0) * center_light_x + light_rotation(0, 1) * center_light_y + light_rotation(0, 2) * center_light_z;
        center.y = light_rotation(1, 0) * center_light_x + light_rotation(1, 1) * center_light_y + light_rotation(1, 2) * center_light_z;
        center.z = light_rotation(2, 0) * center_light_x + light_rotation(2, 1) * center_light_y + light_rotation(2, 2) * center_light_z;
    }

    // Z in light space: min is closer to light, max is farther
    // caster_offset — distance behind camera for shadow casters
    float z_near = static_cast<float>(min_bounds.z) - caster_offset;
    float z_far = static_cast<float>(max_bounds.z) + padding;

    // near/far must be positive for orthographic projection
    // In our system camera looks along -Z, so invert
    float near = -z_far;
    float far = -z_near;

    // Protection against degenerate cases
    if (near < 0.1f) {
        near = 0.1f;
    }
    if (far <= near) {
        far = near + 100.0f;
    }

    return ShadowCameraParams(
        light_dir,
        Bounds2f{left, bottom, right, top},
        20.0f,  // ortho_size (not used when ortho_bounds is set)
        near,
        far,
        center
    );
}

std::vector<float> compute_cascade_splits(
    float near,
    float far,
    int cascade_count,
    float lambda
) {
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


ShadowCameraParams fit_shadow_frustum_for_cascade(
    const Mat44f& view_matrix,
    const Mat44f& projection_matrix,
    float camera_near,
    float camera_far,
    const Vec3& light_direction,
    float cascade_near,
    float cascade_far,
    int shadow_map_resolution,
    float caster_offset
) {
    Vec3 light_dir = safe_normalize(light_direction, Vec3{0, 1, 0});

    // Use the real camera frustum and slice it along its rays. Rebuilding a
    // symmetric projection from FOV/aspect loses asymmetric XR projection
    // offsets and clips visible shadow coverage near the view edges.
    std::array<Vec3, 8> full_frustum_corners =
        compute_frustum_corners(view_matrix, projection_matrix);
    std::array<Vec3, 8> frustum_corners = slice_frustum_corners(
        full_frustum_corners,
        camera_near,
        camera_far,
        cascade_near,
        cascade_far
    );

    // Compute frustum center
    Vec3 center{0, 0, 0};
    for (const auto& corner : frustum_corners) {
        center = center + corner;
    }
    center = center / 8.0;

    // Build light-space rotation matrix
    Mat44f light_rotation = build_light_rotation_matrix(light_dir);

    // Transform centered frustum corners to light space
    std::array<Vec3, 8> light_space_corners;
    for (int i = 0; i < 8; ++i) {
        Vec3 centered = frustum_corners[i] - center;

        float x = light_rotation(0, 0) * static_cast<float>(centered.x) +
                  light_rotation(1, 0) * static_cast<float>(centered.y) +
                  light_rotation(2, 0) * static_cast<float>(centered.z);
        float y = light_rotation(0, 1) * static_cast<float>(centered.x) +
                  light_rotation(1, 1) * static_cast<float>(centered.y) +
                  light_rotation(2, 1) * static_cast<float>(centered.z);
        float z = light_rotation(0, 2) * static_cast<float>(centered.x) +
                  light_rotation(1, 2) * static_cast<float>(centered.y) +
                  light_rotation(2, 2) * static_cast<float>(centered.z);

        light_space_corners[i] = Vec3{x, y, z};
    }

    // Compute AABB in light space
    Vec3 min_bounds = light_space_corners[0];
    Vec3 max_bounds = light_space_corners[0];

    for (int i = 1; i < 8; ++i) {
        min_bounds.x = std::min(min_bounds.x, light_space_corners[i].x);
        min_bounds.y = std::min(min_bounds.y, light_space_corners[i].y);
        min_bounds.z = std::min(min_bounds.z, light_space_corners[i].z);

        max_bounds.x = std::max(max_bounds.x, light_space_corners[i].x);
        max_bounds.y = std::max(max_bounds.y, light_space_corners[i].y);
        max_bounds.z = std::max(max_bounds.z, light_space_corners[i].z);
    }

    float padding = 1.0f;
    float left = static_cast<float>(min_bounds.x) - padding;
    float right = static_cast<float>(max_bounds.x) + padding;
    float bottom = static_cast<float>(min_bounds.y) - padding;
    float top = static_cast<float>(max_bounds.y) + padding;

    // Texel snapping for cascade stability
    if (shadow_map_resolution > 0) {
        float world_units_per_texel_x = (right - left) / shadow_map_resolution;
        float world_units_per_texel_y = (top - bottom) / shadow_map_resolution;

        left = std::floor(left / world_units_per_texel_x) * world_units_per_texel_x;
        right = std::ceil(right / world_units_per_texel_x) * world_units_per_texel_x;
        bottom = std::floor(bottom / world_units_per_texel_y) * world_units_per_texel_y;
        top = std::ceil(top / world_units_per_texel_y) * world_units_per_texel_y;

        // Snap center
        float center_light_x = light_rotation(0, 0) * static_cast<float>(center.x) +
                               light_rotation(1, 0) * static_cast<float>(center.y) +
                               light_rotation(2, 0) * static_cast<float>(center.z);
        float center_light_y = light_rotation(0, 1) * static_cast<float>(center.x) +
                               light_rotation(1, 1) * static_cast<float>(center.y) +
                               light_rotation(2, 1) * static_cast<float>(center.z);
        float center_light_z = light_rotation(0, 2) * static_cast<float>(center.x) +
                               light_rotation(1, 2) * static_cast<float>(center.y) +
                               light_rotation(2, 2) * static_cast<float>(center.z);

        center_light_x = std::floor(center_light_x / world_units_per_texel_x) * world_units_per_texel_x;
        center_light_y = std::floor(center_light_y / world_units_per_texel_y) * world_units_per_texel_y;

        // Transform back to world space
        center.x = light_rotation(0, 0) * center_light_x +
                   light_rotation(0, 1) * center_light_y +
                   light_rotation(0, 2) * center_light_z;
        center.y = light_rotation(1, 0) * center_light_x +
                   light_rotation(1, 1) * center_light_y +
                   light_rotation(1, 2) * center_light_z;
        center.z = light_rotation(2, 0) * center_light_x +
                   light_rotation(2, 1) * center_light_y +
                   light_rotation(2, 2) * center_light_z;
    }

    // Compute near/far for shadow ortho
    float z_near = static_cast<float>(min_bounds.z) - caster_offset;
    float z_far = static_cast<float>(max_bounds.z) + padding;

    float near = -z_far;
    float far = -z_near;

    if (near < 0.1f) near = 0.1f;
    if (far <= near) far = near + 100.0f;

    return ShadowCameraParams(
        light_dir,
        Bounds2f{left, bottom, right, top},
        20.0f,
        near,
        far,
        center
    );
}

} // namespace termin
