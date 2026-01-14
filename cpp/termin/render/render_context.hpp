#pragma once

#include <string>

#include <nanobind/nanobind.h>

#include "termin/geom/mat44.hpp"
#include "termin/render/tc_shader_handle.hpp"

namespace nb = nanobind;

namespace termin {

// Forward declarations
class GraphicsBackend;
class ShaderProgram;

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

    // Camera (nb::object - can be C++ Camera or Python CameraComponent)
    nb::object camera;

    // Scene (stored as nb::object - not migrated to C++ yet)
    nb::object scene;

    // Context key for VAO/shader caching
    int64_t context_key = 0;

    // Graphics backend pointer
    GraphicsBackend* graphics = nullptr;

    // Current render phase ("main", "shadow", "gizmo_mask", etc.)
    std::string phase = "main";

    // Model matrix (set by pass before drawing each entity)
    Mat44f model = Mat44f::identity();

    // Shadow mapping data (stored as nb::object - not migrated to C++ yet)
    nb::object shadow_data;

    // Currently bound shader (for setting additional uniforms)
    // DEPRECATED: use current_tc_shader instead
    ShaderProgram* current_shader = nullptr;

    // Currently bound shader (TcShader handle)
    TcShader current_tc_shader;

    // Extra uniforms to copy when switching shader variants (nb::dict in Python)
    nb::object extra_uniforms;

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
