#pragma once

#include <string>

#include <pybind11/pybind11.h>

#include "termin/geom/mat44.hpp"

namespace py = pybind11;

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

    // Camera (py::object - can be C++ Camera or Python CameraComponent)
    py::object camera;

    // Scene (stored as py::object - not migrated to C++ yet)
    py::object scene;

    // Context key for VAO/shader caching
    int64_t context_key = 0;

    // Graphics backend pointer
    GraphicsBackend* graphics = nullptr;

    // Current render phase ("main", "shadow", "gizmo_mask", etc.)
    std::string phase = "main";

    // Model matrix (set by pass before drawing each entity)
    Mat44f model = Mat44f::identity();

    // Shadow mapping data (stored as py::object - not migrated to C++ yet)
    py::object shadow_data;

    // Currently bound shader (for setting additional uniforms)
    ShaderProgram* current_shader = nullptr;

    // Extra uniforms to copy when switching shader variants (py::dict in Python)
    py::object extra_uniforms;

    // Helper to set model matrix
    void set_model(const Mat44f& m) { model = m; }

    // Helper to get MVP matrix
    Mat44f mvp() const {
        return projection * view * model;
    }
};

} // namespace termin
