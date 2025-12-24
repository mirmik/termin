#pragma once

#include <string>
#include <unordered_map>
#include <variant>

#include "termin/geom/mat44.hpp"
#include "termin/geom/vec3.hpp"

namespace termin {

// Forward declarations
class GraphicsBackend;
class ShaderHandle;

/**
 * Extra uniform value types.
 */
using UniformValue = std::variant<
    int,
    float,
    Vec3,
    Mat44f
>;

/**
 * Render context passed to components during rendering.
 *
 * Contains view/projection matrices, current shader, and other
 * rendering parameters needed by drawables.
 */
struct RenderContext {
    // View and projection matrices
    Mat44f view;
    Mat44f projection;

    // Context key for VAO/shader caching
    int64_t context_key = 0;

    // Graphics backend pointer
    GraphicsBackend* graphics = nullptr;

    // Current render phase ("main", "shadow", "gizmo_mask", etc.)
    std::string phase = "main";

    // Model matrix (set by pass before drawing each entity)
    Mat44f model = Mat44f::identity();

    // Currently bound shader (for setting additional uniforms)
    ShaderHandle* current_shader = nullptr;

    // Extra uniforms to copy when switching shader variants
    std::unordered_map<std::string, UniformValue> extra_uniforms;

    // Helper to set model matrix
    void set_model(const Mat44f& m) { model = m; }

    // Helper to get MVP matrix
    Mat44f mvp() const {
        return projection * view * model;
    }
};

} // namespace termin
