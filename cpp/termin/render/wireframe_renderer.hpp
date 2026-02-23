#pragma once

#include "termin/geom/mat44.hpp"
#include "tgfx/types.hpp"

#include <cstdint>

namespace termin {

// Forward declarations
class GraphicsBackend;

/**
 * Efficient wireframe renderer using pre-built unit meshes.
 *
 * All geometry is created once at initialization. Drawing is done by
 * setting model matrices and colors per-primitive.
 *
 * Unit meshes:
 *   - Circle: XY plane, radius=1, centered at origin
 *   - Arc: XY plane, half-circle from +X to -X via +Y, radius=1
 *   - Box: from -0.5 to +0.5 on each axis
 *   - Line: from origin to (0, 0, 1)
 *
 * Usage:
 *     renderer.begin(graphics, view, proj);
 *     renderer.draw_box(model, color);
 *     renderer.draw_circle(model, color);
 *     renderer.end();
 */
class WireframeRenderer {
public:
    // Configuration
    static constexpr int CIRCLE_SEGMENTS = 16;
    static constexpr int ARC_SEGMENTS = 8;

private:
    // Shader (opaque pointer to internal WireframeShaderData)
    void* _shader_data = nullptr;
    bool _owns_shader = false;

    // VAOs and VBOs for unit meshes
    uint32_t _circle_vao = 0;
    uint32_t _circle_vbo = 0;
    int _circle_vertex_count = 0;

    uint32_t _arc_vao = 0;
    uint32_t _arc_vbo = 0;
    int _arc_vertex_count = 0;

    uint32_t _box_vao = 0;
    uint32_t _box_vbo = 0;
    int _box_vertex_count = 0;

    uint32_t _line_vao = 0;
    uint32_t _line_vbo = 0;

    bool _initialized = false;
    bool _in_frame = false;

public:
    WireframeRenderer();
    ~WireframeRenderer();

    // Non-copyable
    WireframeRenderer(const WireframeRenderer&) = delete;
    WireframeRenderer& operator=(const WireframeRenderer&) = delete;

    // Movable
    WireframeRenderer(WireframeRenderer&& other) noexcept;
    WireframeRenderer& operator=(WireframeRenderer&& other) noexcept;

    /**
     * Begin wireframe rendering. Sets up shader and state.
     *
     * @param graphics Graphics backend
     * @param view View matrix (4x4, column-major)
     * @param proj Projection matrix (4x4, column-major)
     * @param depth_test Enable depth testing (default: false)
     */
    void begin(
        GraphicsBackend* graphics,
        const Mat44f& view,
        const Mat44f& proj,
        bool depth_test = false
    );

    /**
     * End wireframe rendering. Restores state.
     */
    void end();

    /**
     * Draw a circle using model matrix.
     *
     * Unit circle is in XY plane with radius=1.
     * Model matrix should encode position, rotation, and scale (radius).
     */
    void draw_circle(const Mat44f& model, const Color4& color);

    /**
     * Draw a half-circle arc using model matrix.
     *
     * Unit arc is in XY plane from +X to -X via +Y, radius=1.
     */
    void draw_arc(const Mat44f& model, const Color4& color);

    /**
     * Draw a wireframe box using model matrix.
     *
     * Unit box is from -0.5 to +0.5 on each axis.
     * Model matrix should encode position, rotation, and scale (size).
     */
    void draw_box(const Mat44f& model, const Color4& color);

    /**
     * Draw a line using model matrix.
     *
     * Unit line is from origin to (0, 0, 1).
     * Model matrix should encode start position, rotation, and scale (length).
     */
    void draw_line(const Mat44f& model, const Color4& color);

    /**
     * Check if initialized.
     */
    bool initialized() const { return _initialized; }

private:
    void _ensure_initialized();
    void _create_mesh(
        const float* vertices,
        int vertex_count,
        uint32_t& vao,
        uint32_t& vbo
    );
};

// ============================================================
// Matrix helpers for building model matrices
// ============================================================

/**
 * Create identity 4x4 matrix.
 */
Mat44f mat4_identity();

/**
 * Create translation matrix.
 */
Mat44f mat4_translate(float x, float y, float z);

/**
 * Create scale matrix.
 */
Mat44f mat4_scale(float sx, float sy, float sz);

/**
 * Create uniform scale matrix.
 */
Mat44f mat4_scale_uniform(float s);

/**
 * Create 4x4 matrix from 3x3 rotation matrix.
 * The rotation matrix should be stored as 9 floats in row-major order.
 */
Mat44f mat4_from_rotation_matrix(const float* rot3x3);

/**
 * Build rotation matrix that aligns Z axis to given axis.
 * Returns 3x3 rotation matrix as 9 floats (row-major).
 */
void rotation_matrix_align_z_to_axis(const float* axis, float* out_rot3x3);

} // namespace termin
