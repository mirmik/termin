#pragma once

#include "termin/geom/vec3.hpp"
#include "termin/geom/mat44.hpp"
#include "tgfx/types.hpp"
#include "termin/render/tc_shader_handle.hpp"

#include <vector>
#include <memory>
#include <functional>

namespace termin {

class GraphicsBackend;

/**
 * Immediate mode renderer for debug visualization, gizmos, etc.
 *
 * Accumulates primitives (lines, triangles) during the frame and batches
 * them into a single draw call at flush time.
 *
 * Usage:
 *     renderer.begin();
 *     renderer.line(start, end, color);
 *     renderer.circle(center, normal, radius, color);
 *     renderer.flush(graphics, view_matrix, proj_matrix);
 */
class ImmediateRenderer {
public:
    // Vertex data: x, y, z, r, g, b, a
    // No depth test (overlay)
    std::vector<float> line_vertices;
    std::vector<float> tri_vertices;
    // With depth test
    std::vector<float> line_vertices_depth;
    std::vector<float> tri_vertices_depth;

public:
    ImmediateRenderer() = default;
    ~ImmediateRenderer() = default;

    // Non-copyable
    ImmediateRenderer(const ImmediateRenderer&) = delete;
    ImmediateRenderer& operator=(const ImmediateRenderer&) = delete;

    // Movable
    ImmediateRenderer(ImmediateRenderer&& other) noexcept = default;
    ImmediateRenderer& operator=(ImmediateRenderer&& other) noexcept = default;

    /**
     * Clear all accumulated primitives. Call at start of frame.
     */
    void begin();

    // ============================================================
    // Basic primitives
    // ============================================================

    void line(const Vec3& start, const Vec3& end, const Color4& color, bool depth_test = false);
    void triangle(const Vec3& p0, const Vec3& p1, const Vec3& p2, const Color4& color, bool depth_test = false);
    void quad(const Vec3& p0, const Vec3& p1, const Vec3& p2, const Vec3& p3, const Color4& color, bool depth_test = false);

    // Batch triangles from arrays (efficient for meshes)
    // vertices: Nx3 array of positions
    // indices: Mx3 array of triangle indices
    // colors: Nx4 array of RGBA colors (per-vertex)
    void triangles(
        const float* vertices, size_t vertex_count,
        const uint32_t* indices, size_t triangle_count,
        const float* colors,
        bool depth_test = false
    );

    // Batch triangles with single color
    void triangles(
        const float* vertices, size_t vertex_count,
        const uint32_t* indices, size_t triangle_count,
        const Color4& color,
        bool depth_test = false
    );

    // ============================================================
    // Wireframe primitives
    // ============================================================

    void polyline(const std::vector<Vec3>& points, const Color4& color, bool closed = false, bool depth_test = false);

    void circle(
        const Vec3& center,
        const Vec3& normal,
        double radius,
        const Color4& color,
        int segments = 32,
        bool depth_test = false
    );

    void arrow(
        const Vec3& origin,
        const Vec3& direction,
        double length,
        const Color4& color,
        double head_length = 0.2,
        double head_width = 0.1,
        bool depth_test = false
    );

    void box(const Vec3& min_pt, const Vec3& max_pt, const Color4& color, bool depth_test = false);

    void cylinder_wireframe(
        const Vec3& start,
        const Vec3& end,
        double radius,
        const Color4& color,
        int segments = 16,
        bool depth_test = false
    );

    void sphere_wireframe(
        const Vec3& center,
        double radius,
        const Color4& color,
        int segments = 16,
        bool depth_test = false
    );

    void capsule_wireframe(
        const Vec3& start,
        const Vec3& end,
        double radius,
        const Color4& color,
        int segments = 16,
        bool depth_test = false
    );

    // ============================================================
    // Solid primitives
    // ============================================================

    void cylinder_solid(
        const Vec3& start,
        const Vec3& end,
        double radius,
        const Color4& color,
        int segments = 16,
        bool caps = true,
        bool depth_test = false
    );

    void cone_solid(
        const Vec3& base,
        const Vec3& tip,
        double radius,
        const Color4& color,
        int segments = 16,
        bool cap = true,
        bool depth_test = false
    );

    void torus_solid(
        const Vec3& center,
        const Vec3& axis,
        double major_radius,
        double minor_radius,
        const Color4& color,
        int major_segments = 32,
        int minor_segments = 12,
        bool depth_test = false
    );

    void arrow_solid(
        const Vec3& origin,
        const Vec3& direction,
        double length,
        const Color4& color,
        double shaft_radius = 0.03,
        double head_radius = 0.06,
        double head_length_ratio = 0.25,
        int segments = 16,
        bool depth_test = false
    );

    // ============================================================
    // Rendering
    // ============================================================

    /**
     * Render all accumulated primitives (no depth test buffer).
     * Clears buffers after rendering.
     */
    void flush(
        GraphicsBackend* graphics,
        const Mat44& view_matrix,
        const Mat44& proj_matrix,
        bool depth_test = true,
        bool blend = true
    );

    /**
     * Render only depth-tested primitives.
     * Clears depth buffers after rendering.
     */
    void flush_depth(
        GraphicsBackend* graphics,
        const Mat44& view_matrix,
        const Mat44& proj_matrix,
        bool blend = true
    );

    /**
     * Number of lines accumulated (no depth test).
     */
    size_t line_count() const { return line_vertices.size() / 14; }  // 2 vertices * 7 floats

    /**
     * Number of triangles accumulated (no depth test).
     */
    size_t triangle_count() const { return tri_vertices.size() / 21; }  // 3 vertices * 7 floats

    /**
     * Number of lines accumulated (with depth test).
     */
    size_t line_count_depth() const { return line_vertices_depth.size() / 14; }

    /**
     * Number of triangles accumulated (with depth test).
     */
    size_t triangle_count_depth() const { return tri_vertices_depth.size() / 21; }

private:
    void _add_vertex(std::vector<float>& buffer, const Vec3& pos, const Color4& color);
    std::pair<Vec3, Vec3> _build_basis(const Vec3& axis);

    void _ensure_shader(GraphicsBackend* graphics);

    void _flush_buffers(
        GraphicsBackend* graphics,
        std::vector<float>& lines,
        std::vector<float>& tris,
        const Mat44& view_matrix,
        const Mat44& proj_matrix,
        bool depth_test,
        bool blend
    );

    TcShader _shader;
};

} // namespace termin
