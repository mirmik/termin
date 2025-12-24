#pragma once

#include "termin/geom/mat44.hpp"
#include "termin/geom/vec3.hpp"

#include <array>
#include <optional>

namespace termin {

/**
 * Shadow camera parameters for directional light.
 *
 * Coordinate convention: Y-forward, Z-up (same as main engine).
 */
struct ShadowCameraParams {
    Vec3 light_direction{0.0, 1.0, 0.0};  // Normalized direction from light into scene
    std::optional<std::array<float, 4>> ortho_bounds;  // (left, right, bottom, top)
    float ortho_size = 20.0f;  // Half-size of symmetric ortho box (fallback)
    float near = 0.1f;
    float far = 100.0f;
    Vec3 center{0.0, 0.0, 0.0};  // Center of shadow box in world coordinates

    ShadowCameraParams() = default;

    ShadowCameraParams(
        const Vec3& light_dir,
        std::optional<std::array<float, 4>> bounds = std::nullopt,
        float ortho_sz = 20.0f,
        float n = 0.1f,
        float f = 100.0f,
        const Vec3& c = Vec3{0, 0, 0}
    ) : light_direction(light_dir.normalized()),
        ortho_bounds(std::move(bounds)),
        ortho_size(ortho_sz),
        near(n),
        far(f),
        center(c) {}
};


/**
 * Build view matrix for shadow camera.
 *
 * Camera is placed at distance from center, looking along light direction.
 *
 * @param params Shadow camera parameters
 * @return 4x4 view matrix
 */
Mat44f build_shadow_view_matrix(const ShadowCameraParams& params);


/**
 * Build orthographic projection matrix for shadow camera.
 *
 * If ortho_bounds is set, uses asymmetric bounds.
 * Otherwise uses symmetric ortho_size.
 *
 * @param params Shadow camera parameters
 * @return 4x4 projection matrix
 */
Mat44f build_shadow_projection_matrix(const ShadowCameraParams& params);


/**
 * Compute combined light space matrix (projection * view).
 *
 * This matrix transforms from world space to shadow clip space.
 *
 * @param params Shadow camera parameters
 * @return 4x4 light space matrix
 */
Mat44f compute_light_space_matrix(const ShadowCameraParams& params);


/**
 * Compute 8 corners of view frustum in world space.
 *
 * The frustum in clip space is a cube [-1,1]^3. This function inverts
 * the VP matrix and transforms all 8 corners back to world space.
 *
 * @param view_matrix 4x4 view matrix
 * @param projection_matrix 4x4 projection matrix
 * @return 8 corners in world space
 */
std::array<Vec3, 8> compute_frustum_corners(
    const Mat44f& view_matrix,
    const Mat44f& projection_matrix
);


/**
 * Fit shadow camera to view frustum.
 *
 * Algorithm:
 * 1. Compute 8 frustum corners in world space
 * 2. Transform to light space (light orientation)
 * 3. Find AABB in light space
 * 4. Use AABB as ortho projection bounds
 * 5. (Optional) Stabilize bounds for shadow jitter prevention
 *
 * @param view_matrix Camera view matrix
 * @param projection_matrix Camera projection matrix (may be modified for max distance)
 * @param light_direction Normalized light direction
 * @param padding Extra padding around frustum
 * @param shadow_map_resolution Resolution for texel snapping
 * @param stabilize Enable texel snapping for jitter prevention
 * @param caster_offset Distance behind camera for shadow casters
 * @return Fitted shadow camera parameters
 */
ShadowCameraParams fit_shadow_frustum_to_camera(
    const Mat44f& view_matrix,
    const Mat44f& projection_matrix,
    const Vec3& light_direction,
    float padding = 1.0f,
    int shadow_map_resolution = 1024,
    bool stabilize = true,
    float caster_offset = 50.0f
);


/**
 * Build light-space rotation matrix (no translation).
 *
 * Used for transforming frustum corners to light space before AABB computation.
 */
Mat44f build_light_rotation_matrix(const Vec3& light_direction);

} // namespace termin
