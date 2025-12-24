#pragma once

#include "termin/geom/vec3.hpp"
#include "termin/geom/mat44.hpp"
#include "termin/render/types.hpp"

#include <vector>
#include <cstdint>

namespace termin {

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
 *     renderer.flush(view_matrix, proj_matrix);
 */
class ImmediateRenderer {
public:
    // Vertex data: x, y, z, r, g, b, a
    std::vector<float> line_vertices;
    std::vector<float> tri_vertices;

private:
    // OpenGL resources
    uint32_t _shader_program = 0;
    uint32_t _line_vao = 0;
    uint32_t _line_vbo = 0;
    uint32_t _tri_vao = 0;
    uint32_t _tri_vbo = 0;
    bool _initialized = false;

    // Uniform locations
    int _u_view_loc = -1;
    int _u_proj_loc = -1;

public:
    ImmediateRenderer() = default;
    ~ImmediateRenderer();

    // Non-copyable
    ImmediateRenderer(const ImmediateRenderer&) = delete;
    ImmediateRenderer& operator=(const ImmediateRenderer&) = delete;

    // Movable
    ImmediateRenderer(ImmediateRenderer&& other) noexcept;
    ImmediateRenderer& operator=(ImmediateRenderer&& other) noexcept;

    /**
     * Clear all accumulated primitives. Call at start of frame.
     */
    void begin();

    // ============================================================
    // Basic primitives
    // ============================================================

    void line(const Vec3& start, const Vec3& end, const Color4& color);
    void triangle(const Vec3& p0, const Vec3& p1, const Vec3& p2, const Color4& color);
    void quad(const Vec3& p0, const Vec3& p1, const Vec3& p2, const Vec3& p3, const Color4& color);

    // ============================================================
    // Wireframe primitives
    // ============================================================

    void polyline(const std::vector<Vec3>& points, const Color4& color, bool closed = false);

    void circle(
        const Vec3& center,
        const Vec3& normal,
        double radius,
        const Color4& color,
        int segments = 32
    );

    void arrow(
        const Vec3& origin,
        const Vec3& direction,
        double length,
        const Color4& color,
        double head_length = 0.2,
        double head_width = 0.1
    );

    void box(const Vec3& min_pt, const Vec3& max_pt, const Color4& color);

    void cylinder_wireframe(
        const Vec3& start,
        const Vec3& end,
        double radius,
        const Color4& color,
        int segments = 16
    );

    void sphere_wireframe(
        const Vec3& center,
        double radius,
        const Color4& color,
        int segments = 16
    );

    void capsule_wireframe(
        const Vec3& start,
        const Vec3& end,
        double radius,
        const Color4& color,
        int segments = 16
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
        bool caps = true
    );

    void cone_solid(
        const Vec3& base,
        const Vec3& tip,
        double radius,
        const Color4& color,
        int segments = 16,
        bool cap = true
    );

    void torus_solid(
        const Vec3& center,
        const Vec3& axis,
        double major_radius,
        double minor_radius,
        const Color4& color,
        int major_segments = 32,
        int minor_segments = 12
    );

    void arrow_solid(
        const Vec3& origin,
        const Vec3& direction,
        double length,
        const Color4& color,
        double shaft_radius = 0.03,
        double head_radius = 0.06,
        double head_length_ratio = 0.25,
        int segments = 16
    );

    // ============================================================
    // Rendering
    // ============================================================

    /**
     * Render all accumulated primitives.
     */
    void flush(
        const Mat44& view_matrix,
        const Mat44& proj_matrix,
        bool depth_test = true,
        bool blend = true
    );

    /**
     * Number of lines accumulated.
     */
    size_t line_count() const { return line_vertices.size() / 14; }  // 2 vertices * 7 floats

    /**
     * Number of triangles accumulated.
     */
    size_t triangle_count() const { return tri_vertices.size() / 21; }  // 3 vertices * 7 floats

private:
    void _ensure_initialized();
    void _add_vertex(std::vector<float>& buffer, const Vec3& pos, const Color4& color);
    std::pair<Vec3, Vec3> _build_basis(const Vec3& axis);
};

} // namespace termin
