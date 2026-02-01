#pragma once

#include <string>

#include "termin/geom/mat44.hpp"
#include "termin/render/tc_shader_handle.hpp"

namespace termin {

// Forward declarations
class GraphicsBackend;

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

    // Graphics backend pointer
    GraphicsBackend* graphics = nullptr;

    // Current render phase ("main", "shadow", "gizmo_mask", etc.)
    std::string phase = "main";

    // Model matrix (set by pass before drawing each entity)
    Mat44f model = Mat44f::identity();

    // Currently bound shader (TcShader handle)
    TcShader current_tc_shader;

    // Layer mask for filtering entities (which layers to render)
    uint64_t layer_mask = 0xFFFFFFFFFFFFFFFF;

    // Helper to set model matrix
    void set_model(const Mat44f& m) { model = m; }

    // Helper to get MVP matrix
    Mat44f mvp() const {
        return projection * view * model;
    }
};

} // namespace termin
