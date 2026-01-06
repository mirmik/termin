#include "immediate_renderer.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/render/render_state.hpp"

#include <cmath>
#include <algorithm>

// MSVC doesn't define M_PI by default
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace termin {

namespace {

const char* IMMEDIATE_VERT = R"(
#version 330 core
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec4 a_color;

uniform mat4 u_view;
uniform mat4 u_projection;

out vec4 v_color;

void main() {
    v_color = a_color;
    gl_Position = u_projection * u_view * vec4(a_position, 1.0);
}
)";

const char* IMMEDIATE_FRAG = R"(
#version 330 core
in vec4 v_color;
out vec4 fragColor;

void main() {
    fragColor = v_color;
}
)";

} // anonymous namespace


void ImmediateRenderer::begin() {
    line_vertices.clear();
    tri_vertices.clear();
    line_vertices_depth.clear();
    tri_vertices_depth.clear();
}

void ImmediateRenderer::_add_vertex(std::vector<float>& buffer, const Vec3& pos, const Color4& color) {
    buffer.push_back(static_cast<float>(pos.x));
    buffer.push_back(static_cast<float>(pos.y));
    buffer.push_back(static_cast<float>(pos.z));
    buffer.push_back(color.r);
    buffer.push_back(color.g);
    buffer.push_back(color.b);
    buffer.push_back(color.a);
}

std::pair<Vec3, Vec3> ImmediateRenderer::_build_basis(const Vec3& axis) {
    Vec3 up{0.0, 0.0, 1.0};
    if (std::abs(axis.dot(up)) > 0.99) {
        up = Vec3{0.0, 1.0, 0.0};
    }
    Vec3 tangent = axis.cross(up).normalized();
    Vec3 bitangent = axis.cross(tangent);
    return {tangent, bitangent};
}

// ============================================================
// Basic primitives
// ============================================================

void ImmediateRenderer::line(const Vec3& start, const Vec3& end, const Color4& color, bool depth_test) {
    auto& buf = depth_test ? line_vertices_depth : line_vertices;
    _add_vertex(buf, start, color);
    _add_vertex(buf, end, color);
}

void ImmediateRenderer::triangle(const Vec3& p0, const Vec3& p1, const Vec3& p2, const Color4& color, bool depth_test) {
    auto& buf = depth_test ? tri_vertices_depth : tri_vertices;
    _add_vertex(buf, p0, color);
    _add_vertex(buf, p1, color);
    _add_vertex(buf, p2, color);
}

void ImmediateRenderer::quad(const Vec3& p0, const Vec3& p1, const Vec3& p2, const Vec3& p3, const Color4& color, bool depth_test) {
    triangle(p0, p1, p2, color, depth_test);
    triangle(p0, p2, p3, color, depth_test);
}

// ============================================================
// Wireframe primitives
// ============================================================

void ImmediateRenderer::polyline(const std::vector<Vec3>& points, const Color4& color, bool closed, bool depth_test) {
    if (points.size() < 2) return;
    for (size_t i = 0; i < points.size() - 1; ++i) {
        line(points[i], points[i + 1], color, depth_test);
    }
    if (closed && points.size() > 2) {
        line(points.back(), points.front(), color, depth_test);
    }
}

void ImmediateRenderer::circle(
    const Vec3& center,
    const Vec3& normal,
    double radius,
    const Color4& color,
    int segments,
    bool depth_test
) {
    Vec3 norm = normal.normalized();
    auto [tangent, bitangent] = _build_basis(norm);

    std::vector<Vec3> points;
    points.reserve(segments);

    for (int i = 0; i < segments; ++i) {
        double angle = 2.0 * M_PI * i / segments;
        Vec3 point = center + (tangent * std::cos(angle) + bitangent * std::sin(angle)) * radius;
        points.push_back(point);
    }

    polyline(points, color, true, depth_test);
}

void ImmediateRenderer::arrow(
    const Vec3& origin,
    const Vec3& direction,
    double length,
    const Color4& color,
    double head_length,
    double head_width,
    bool depth_test
) {
    Vec3 dir = direction.normalized();
    Vec3 tip = origin + dir * length;
    Vec3 head_base = tip - dir * (length * head_length);

    // Shaft
    line(origin, head_base, color, depth_test);

    // Head (4 lines)
    auto [right, up] = _build_basis(dir);

    double hw = length * head_width;
    Vec3 p1 = head_base + right * hw;
    Vec3 p2 = head_base - right * hw;
    Vec3 p3 = head_base + up * hw;
    Vec3 p4 = head_base - up * hw;

    line(tip, p1, color, depth_test);
    line(tip, p2, color, depth_test);
    line(tip, p3, color, depth_test);
    line(tip, p4, color, depth_test);
}

void ImmediateRenderer::box(const Vec3& min_pt, const Vec3& max_pt, const Color4& color, bool depth_test) {
    // 8 corners
    Vec3 corners[8] = {
        {min_pt.x, min_pt.y, min_pt.z},
        {max_pt.x, min_pt.y, min_pt.z},
        {max_pt.x, max_pt.y, min_pt.z},
        {min_pt.x, max_pt.y, min_pt.z},
        {min_pt.x, min_pt.y, max_pt.z},
        {max_pt.x, min_pt.y, max_pt.z},
        {max_pt.x, max_pt.y, max_pt.z},
        {min_pt.x, max_pt.y, max_pt.z},
    };

    // 12 edges
    int edges[12][2] = {
        {0, 1}, {1, 2}, {2, 3}, {3, 0},  // bottom
        {4, 5}, {5, 6}, {6, 7}, {7, 4},  // top
        {0, 4}, {1, 5}, {2, 6}, {3, 7},  // vertical
    };

    for (auto& e : edges) {
        line(corners[e[0]], corners[e[1]], color, depth_test);
    }
}

void ImmediateRenderer::cylinder_wireframe(
    const Vec3& start,
    const Vec3& end,
    double radius,
    const Color4& color,
    int segments,
    bool depth_test
) {
    Vec3 axis = end - start;
    double length = axis.norm();
    if (length < 1e-6) return;
    axis = axis / length;

    // Circles at ends
    circle(start, axis, radius, color, segments, depth_test);
    circle(end, axis, radius, color, segments, depth_test);

    // Connecting lines
    auto [tangent, bitangent] = _build_basis(axis);

    for (int i = 0; i < 4; ++i) {
        double angle = 2.0 * M_PI * i / 4;
        Vec3 offset = (tangent * std::cos(angle) + bitangent * std::sin(angle)) * radius;
        line(start + offset, end + offset, color, depth_test);
    }
}

void ImmediateRenderer::sphere_wireframe(
    const Vec3& center,
    double radius,
    const Color4& color,
    int segments,
    bool depth_test
) {
    // 3 orthogonal circles
    circle(center, Vec3{0, 0, 1}, radius, color, segments, depth_test);
    circle(center, Vec3{0, 1, 0}, radius, color, segments, depth_test);
    circle(center, Vec3{1, 0, 0}, radius, color, segments, depth_test);
}

void ImmediateRenderer::capsule_wireframe(
    const Vec3& start,
    const Vec3& end,
    double radius,
    const Color4& color,
    int segments,
    bool depth_test
) {
    Vec3 axis = end - start;
    double length = axis.norm();
    if (length < 1e-6) {
        sphere_wireframe(start, radius, color, segments, depth_test);
        return;
    }
    axis = axis / length;

    auto [tangent, bitangent] = _build_basis(axis);

    // Circles at ends
    circle(start, axis, radius, color, segments, depth_test);
    circle(end, axis, radius, color, segments, depth_test);

    // Connecting lines
    for (int i = 0; i < 4; ++i) {
        double angle = 2.0 * M_PI * i / 4;
        Vec3 offset = (tangent * std::cos(angle) + bitangent * std::sin(angle)) * radius;
        line(start + offset, end + offset, color, depth_test);
    }

    // Hemisphere arcs
    int half_segments = segments / 2;

    for (const Vec3* basis_vec : {&tangent, &bitangent}) {
        // Arc at start
        std::vector<Vec3> points_start;
        points_start.reserve(half_segments + 1);
        for (int i = 0; i <= half_segments; ++i) {
            double angle = M_PI * i / half_segments;
            Vec3 pt = start + (*basis_vec * std::cos(angle) - axis * std::sin(angle)) * radius;
            points_start.push_back(pt);
        }
        polyline(points_start, color, false, depth_test);

        // Arc at end
        std::vector<Vec3> points_end;
        points_end.reserve(half_segments + 1);
        for (int i = 0; i <= half_segments; ++i) {
            double angle = M_PI * i / half_segments;
            Vec3 pt = end + (*basis_vec * std::cos(angle) + axis * std::sin(angle)) * radius;
            points_end.push_back(pt);
        }
        polyline(points_end, color, false, depth_test);
    }
}

// ============================================================
// Solid primitives
// ============================================================

void ImmediateRenderer::cylinder_solid(
    const Vec3& start,
    const Vec3& end,
    double radius,
    const Color4& color,
    int segments,
    bool caps,
    bool depth_test
) {
    Vec3 axis = end - start;
    double length = axis.norm();
    if (length < 1e-6) return;
    axis = axis / length;

    auto [tangent, bitangent] = _build_basis(axis);

    // Generate ring points
    std::vector<Vec3> ring_start, ring_end;
    ring_start.reserve(segments);
    ring_end.reserve(segments);

    for (int i = 0; i < segments; ++i) {
        double angle = 2.0 * M_PI * i / segments;
        Vec3 offset = (tangent * std::cos(angle) + bitangent * std::sin(angle)) * radius;
        ring_start.push_back(start + offset);
        ring_end.push_back(end + offset);
    }

    // Side triangles
    for (int i = 0; i < segments; ++i) {
        int j = (i + 1) % segments;
        triangle(ring_start[i], ring_end[i], ring_end[j], color, depth_test);
        triangle(ring_start[i], ring_end[j], ring_start[j], color, depth_test);
    }

    // Caps
    if (caps) {
        for (int i = 0; i < segments; ++i) {
            int j = (i + 1) % segments;
            triangle(start, ring_start[j], ring_start[i], color, depth_test);
            triangle(end, ring_end[i], ring_end[j], color, depth_test);
        }
    }
}

void ImmediateRenderer::cone_solid(
    const Vec3& base,
    const Vec3& tip,
    double radius,
    const Color4& color,
    int segments,
    bool cap,
    bool depth_test
) {
    Vec3 axis = tip - base;
    double length = axis.norm();
    if (length < 1e-6) return;
    axis = axis / length;

    auto [tangent, bitangent] = _build_basis(axis);

    // Generate base ring points
    std::vector<Vec3> ring;
    ring.reserve(segments);
    for (int i = 0; i < segments; ++i) {
        double angle = 2.0 * M_PI * i / segments;
        Vec3 offset = (tangent * std::cos(angle) + bitangent * std::sin(angle)) * radius;
        ring.push_back(base + offset);
    }

    // Side triangles
    for (int i = 0; i < segments; ++i) {
        int j = (i + 1) % segments;
        triangle(ring[i], tip, ring[j], color, depth_test);
    }

    // Base cap
    if (cap) {
        for (int i = 0; i < segments; ++i) {
            int j = (i + 1) % segments;
            triangle(base, ring[j], ring[i], color, depth_test);
        }
    }
}

void ImmediateRenderer::torus_solid(
    const Vec3& center,
    const Vec3& axis,
    double major_radius,
    double minor_radius,
    const Color4& color,
    int major_segments,
    int minor_segments,
    bool depth_test
) {
    Vec3 ax = axis.normalized();
    auto [tangent, bitangent] = _build_basis(ax);

    // Generate torus vertices
    std::vector<std::vector<Vec3>> vertices(major_segments);

    for (int i = 0; i < major_segments; ++i) {
        double theta = 2.0 * M_PI * i / major_segments;
        Vec3 ring_center = center + (tangent * std::cos(theta) + bitangent * std::sin(theta)) * major_radius;
        Vec3 radial = tangent * std::cos(theta) + bitangent * std::sin(theta);

        vertices[i].reserve(minor_segments);
        for (int j = 0; j < minor_segments; ++j) {
            double phi = 2.0 * M_PI * j / minor_segments;
            Vec3 point = ring_center + (radial * std::cos(phi) + ax * std::sin(phi)) * minor_radius;
            vertices[i].push_back(point);
        }
    }

    // Generate triangles
    for (int i = 0; i < major_segments; ++i) {
        int i_next = (i + 1) % major_segments;
        for (int j = 0; j < minor_segments; ++j) {
            int j_next = (j + 1) % minor_segments;
            const Vec3& p00 = vertices[i][j];
            const Vec3& p10 = vertices[i_next][j];
            const Vec3& p01 = vertices[i][j_next];
            const Vec3& p11 = vertices[i_next][j_next];
            triangle(p00, p10, p11, color, depth_test);
            triangle(p00, p11, p01, color, depth_test);
        }
    }
}

void ImmediateRenderer::arrow_solid(
    const Vec3& origin,
    const Vec3& direction,
    double length,
    const Color4& color,
    double shaft_radius,
    double head_radius,
    double head_length_ratio,
    int segments,
    bool depth_test
) {
    double dir_len = direction.norm();
    if (dir_len < 1e-6) return;
    Vec3 dir = direction / dir_len;

    double head_length = length * head_length_ratio;
    double shaft_length = length - head_length;

    Vec3 shaft_end = origin + dir * shaft_length;
    Vec3 tip = origin + dir * length;

    // Shaft cylinder
    cylinder_solid(origin, shaft_end, shaft_radius, color, segments, true, depth_test);
    // Head cone
    cone_solid(shaft_end, tip, head_radius, color, segments, true, depth_test);
}

// ============================================================
// Rendering
// ============================================================

void ImmediateRenderer::_ensure_shader(GraphicsBackend* graphics) {
    if (_shader) return;

    _shader = std::make_unique<ShaderProgram>(IMMEDIATE_VERT, IMMEDIATE_FRAG);
    _shader->ensure_ready([graphics](const char* v, const char* f, const char* g) {
        return graphics->create_shader(v, f, g);
    });
}

void ImmediateRenderer::_flush_buffers(
    GraphicsBackend* graphics,
    std::vector<float>& lines,
    std::vector<float>& tris,
    const Mat44& view_matrix,
    const Mat44& proj_matrix,
    bool depth_test,
    bool blend
) {
    if (lines.empty() && tris.empty()) return;

    _ensure_shader(graphics);
    if (!_shader) return;

    // Setup render state
    RenderState state;
    state.depth_test = depth_test;
    state.depth_write = depth_test;
    state.blend = blend;
    state.blend_src = BlendFactor::SrcAlpha;
    state.blend_dst = BlendFactor::OneMinusSrcAlpha;
    state.cull = false;
    graphics->apply_render_state(state);

    // Use shader and set uniforms
    _shader->use();

    // Convert Mat44 (double) to float for OpenGL
    float view_f[16], proj_f[16];
    for (int i = 0; i < 16; ++i) {
        view_f[i] = static_cast<float>(view_matrix.data[i]);
        proj_f[i] = static_cast<float>(proj_matrix.data[i]);
    }
    _shader->set_uniform_matrix4("u_view", view_f, false);
    _shader->set_uniform_matrix4("u_projection", proj_f, false);

    // Draw lines
    if (!lines.empty()) {
        int vertex_count = static_cast<int>(lines.size() / 7);
        graphics->draw_immediate_lines(lines.data(), vertex_count);
        lines.clear();
    }

    // Draw triangles
    if (!tris.empty()) {
        int vertex_count = static_cast<int>(tris.size() / 7);
        graphics->draw_immediate_triangles(tris.data(), vertex_count);
        tris.clear();
    }

    _shader->stop();
}

void ImmediateRenderer::flush(
    GraphicsBackend* graphics,
    const Mat44& view_matrix,
    const Mat44& proj_matrix,
    bool depth_test,
    bool blend
) {
    _flush_buffers(graphics, line_vertices, tri_vertices, view_matrix, proj_matrix, depth_test, blend);
}

void ImmediateRenderer::flush_depth(
    GraphicsBackend* graphics,
    const Mat44& view_matrix,
    const Mat44& proj_matrix,
    bool blend
) {
    _flush_buffers(graphics, line_vertices_depth, tri_vertices_depth, view_matrix, proj_matrix, true, blend);
}

} // namespace termin
