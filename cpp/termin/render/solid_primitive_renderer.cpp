#include "solid_primitive_renderer.hpp"
#include "tgfx/graphics_backend.hpp"
#include "tc_log.hpp"

extern "C" {
#include <tgfx/resources/tc_mesh.h>
}

#include <vector>
#include <cmath>
#include <cstring>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace termin {

namespace {

const char* SOLID_VERT = R"(
#version 330 core
layout(location = 0) in vec3 a_position;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;
uniform vec4 u_color;

out vec4 v_color;

void main() {
    v_color = u_color;
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
)";

const char* SOLID_FRAG = R"(
#version 330 core
in vec4 v_color;
out vec4 fragColor;

void main() {
    fragColor = v_color;
}
)";

struct IndexedMesh {
    std::vector<float> vertices;
    std::vector<uint32_t> indices;
};

IndexedMesh build_unit_torus(int major_segments, int minor_segments, float minor_ratio) {
    IndexedMesh mesh;

    for (int i = 0; i < major_segments; ++i) {
        float theta = 2.0f * static_cast<float>(M_PI) * i / major_segments;
        float cos_theta = std::cos(theta);
        float sin_theta = std::sin(theta);

        float cx = cos_theta;
        float cy = sin_theta;

        for (int j = 0; j < minor_segments; ++j) {
            float phi = 2.0f * static_cast<float>(M_PI) * j / minor_segments;
            float cos_phi = std::cos(phi);
            float sin_phi = std::sin(phi);

            float x = cx + minor_ratio * cos_phi * cos_theta;
            float y = cy + minor_ratio * cos_phi * sin_theta;
            float z = minor_ratio * sin_phi;

            mesh.vertices.push_back(x);
            mesh.vertices.push_back(y);
            mesh.vertices.push_back(z);
        }
    }

    for (int i = 0; i < major_segments; ++i) {
        int i_next = (i + 1) % major_segments;
        for (int j = 0; j < minor_segments; ++j) {
            int j_next = (j + 1) % minor_segments;

            uint32_t v00 = i * minor_segments + j;
            uint32_t v10 = i_next * minor_segments + j;
            uint32_t v01 = i * minor_segments + j_next;
            uint32_t v11 = i_next * minor_segments + j_next;

            mesh.indices.push_back(v00);
            mesh.indices.push_back(v10);
            mesh.indices.push_back(v11);

            mesh.indices.push_back(v00);
            mesh.indices.push_back(v11);
            mesh.indices.push_back(v01);
        }
    }

    return mesh;
}

IndexedMesh build_unit_cylinder(int segments) {
    IndexedMesh mesh;

    // Side vertices: two rings
    for (float z : {0.0f, 1.0f}) {
        for (int i = 0; i < segments; ++i) {
            float angle = 2.0f * static_cast<float>(M_PI) * i / segments;
            float x = std::cos(angle);
            float y = std::sin(angle);
            mesh.vertices.push_back(x);
            mesh.vertices.push_back(y);
            mesh.vertices.push_back(z);
        }
    }

    // Side indices
    for (int i = 0; i < segments; ++i) {
        int j = (i + 1) % segments;
        uint32_t b0 = i, b1 = j;
        uint32_t t0 = i + segments, t1 = j + segments;
        mesh.indices.push_back(b0);
        mesh.indices.push_back(t0);
        mesh.indices.push_back(t1);
        mesh.indices.push_back(b0);
        mesh.indices.push_back(t1);
        mesh.indices.push_back(b1);
    }

    // Cap centers
    uint32_t bottom_center = static_cast<uint32_t>(mesh.vertices.size() / 3);
    mesh.vertices.push_back(0.0f);
    mesh.vertices.push_back(0.0f);
    mesh.vertices.push_back(0.0f);

    uint32_t top_center = static_cast<uint32_t>(mesh.vertices.size() / 3);
    mesh.vertices.push_back(0.0f);
    mesh.vertices.push_back(0.0f);
    mesh.vertices.push_back(1.0f);

    // Bottom cap (facing -Z)
    for (int i = 0; i < segments; ++i) {
        int j = (i + 1) % segments;
        mesh.indices.push_back(bottom_center);
        mesh.indices.push_back(j);
        mesh.indices.push_back(i);
    }

    // Top cap (facing +Z)
    for (int i = 0; i < segments; ++i) {
        int j = (i + 1) % segments;
        mesh.indices.push_back(top_center);
        mesh.indices.push_back(i + segments);
        mesh.indices.push_back(j + segments);
    }

    return mesh;
}

IndexedMesh build_unit_cone(int segments) {
    IndexedMesh mesh;

    // Base ring vertices
    for (int i = 0; i < segments; ++i) {
        float angle = 2.0f * static_cast<float>(M_PI) * i / segments;
        float x = std::cos(angle);
        float y = std::sin(angle);
        mesh.vertices.push_back(x);
        mesh.vertices.push_back(y);
        mesh.vertices.push_back(0.0f);
    }

    // Tip vertex
    uint32_t tip_idx = static_cast<uint32_t>(mesh.vertices.size() / 3);
    mesh.vertices.push_back(0.0f);
    mesh.vertices.push_back(0.0f);
    mesh.vertices.push_back(1.0f);

    // Base center
    uint32_t base_center = static_cast<uint32_t>(mesh.vertices.size() / 3);
    mesh.vertices.push_back(0.0f);
    mesh.vertices.push_back(0.0f);
    mesh.vertices.push_back(0.0f);

    // Side triangles
    for (int i = 0; i < segments; ++i) {
        int j = (i + 1) % segments;
        mesh.indices.push_back(i);
        mesh.indices.push_back(tip_idx);
        mesh.indices.push_back(j);
    }

    // Base cap (facing -Z)
    for (int i = 0; i < segments; ++i) {
        int j = (i + 1) % segments;
        mesh.indices.push_back(base_center);
        mesh.indices.push_back(j);
        mesh.indices.push_back(i);
    }

    return mesh;
}

IndexedMesh build_unit_quad() {
    IndexedMesh mesh;
    mesh.vertices = {
        0.0f, 0.0f, 0.0f,
        1.0f, 0.0f, 0.0f,
        1.0f, 1.0f, 0.0f,
        0.0f, 1.0f, 0.0f,
    };
    mesh.indices = {0, 1, 2, 0, 2, 3};
    return mesh;
}

// Create tc_mesh from IndexedMesh (position only layout)
tc_mesh create_tc_mesh(const IndexedMesh& indexed_mesh) {
    tc_mesh mesh;
    std::memset(&mesh, 0, sizeof(mesh));

    // Setup position-only layout
    mesh.layout = tc_vertex_layout_pos();
    mesh.vertex_count = indexed_mesh.vertices.size() / 3;
    mesh.index_count = indexed_mesh.indices.size();
    mesh.draw_mode = TC_DRAW_TRIANGLES;

    // Copy vertex data
    size_t vertex_bytes = indexed_mesh.vertices.size() * sizeof(float);
    mesh.vertices = malloc(vertex_bytes);
    std::memcpy(mesh.vertices, indexed_mesh.vertices.data(), vertex_bytes);

    // Copy index data
    size_t index_bytes = indexed_mesh.indices.size() * sizeof(uint32_t);
    mesh.indices = static_cast<uint32_t*>(malloc(index_bytes));
    std::memcpy(mesh.indices, indexed_mesh.indices.data(), index_bytes);

    return mesh;
}

// Free tc_mesh data (but not the struct itself)
void free_tc_mesh_data(tc_mesh* mesh) {
    if (mesh->vertices) {
        free(mesh->vertices);
        mesh->vertices = nullptr;
    }
    if (mesh->indices) {
        free(mesh->indices);
        mesh->indices = nullptr;
    }
}

Mat44f rotation_matrix_align_z_to(const Vec3f& target) {
    float length = target.norm();
    if (length < 1e-6f) {
        return Mat44f::identity();
    }

    Vec3f z_new = target / length;

    Vec3f up{0.0f, 0.0f, 1.0f};
    if (std::abs(z_new.dot(up)) > 0.99f) {
        up = Vec3f{0.0f, 1.0f, 0.0f};
    }

    Vec3f x_new = up.cross(z_new).normalized();
    Vec3f y_new = z_new.cross(x_new);

    // Mat44f uses m(col, row), column-major layout
    // Column 0 = x_new, Column 1 = y_new, Column 2 = z_new
    Mat44f m = Mat44f::identity();
    m(0, 0) = x_new.x; m(0, 1) = x_new.y; m(0, 2) = x_new.z;
    m(1, 0) = y_new.x; m(1, 1) = y_new.y; m(1, 2) = y_new.z;
    m(2, 0) = z_new.x; m(2, 1) = z_new.y; m(2, 2) = z_new.z;
    return m;
}

Mat44f compose_trs(const Vec3f& translate, const Mat44f& rotate, const Vec3f& scale) {
    Mat44f m = Mat44f::identity();

    // Mat44f uses m(col, row), column-major layout
    // Apply scale to each column of rotation matrix:
    // Column 0 *= scale.x
    m(0, 0) = rotate(0, 0) * scale.x;
    m(0, 1) = rotate(0, 1) * scale.x;
    m(0, 2) = rotate(0, 2) * scale.x;

    // Column 1 *= scale.y
    m(1, 0) = rotate(1, 0) * scale.y;
    m(1, 1) = rotate(1, 1) * scale.y;
    m(1, 2) = rotate(1, 2) * scale.y;

    // Column 2 *= scale.z
    m(2, 0) = rotate(2, 0) * scale.z;
    m(2, 1) = rotate(2, 1) * scale.z;
    m(2, 2) = rotate(2, 2) * scale.z;

    // Translation goes in column 3
    m(3, 0) = translate.x;
    m(3, 1) = translate.y;
    m(3, 2) = translate.z;

    return m;
}

} // anonymous namespace

SolidPrimitiveRenderer::SolidPrimitiveRenderer(SolidPrimitiveRenderer&& other) noexcept {
    *this = std::move(other);
}

SolidPrimitiveRenderer& SolidPrimitiveRenderer::operator=(SolidPrimitiveRenderer&& other) noexcept {
    if (this != &other) {
        _torus_mesh = std::move(other._torus_mesh);
        _cylinder_mesh = std::move(other._cylinder_mesh);
        _cone_mesh = std::move(other._cone_mesh);
        _quad_mesh = std::move(other._quad_mesh);
        _initialized = other._initialized;
        _shader = std::move(other._shader);
        _graphics = other._graphics;

        other._initialized = false;
        other._graphics = nullptr;
    }
    return *this;
}

void SolidPrimitiveRenderer::_ensure_initialized(GraphicsBackend* graphics) {
    if (_initialized) return;

    // Shader
    _shader = TcShader::from_sources(SOLID_VERT, SOLID_FRAG, "", "SolidPrimitiveRenderer");
    _shader.ensure_ready();

    // Create meshes using tc_mesh and GPUMeshHandle
    {
        auto indexed = build_unit_torus(TORUS_MAJOR_SEGMENTS, TORUS_MINOR_SEGMENTS, TORUS_MINOR_RATIO);
        tc_mesh mesh = create_tc_mesh(indexed);
        _torus_mesh = graphics->create_mesh(mesh.vertices, mesh.vertex_count, mesh.indices, mesh.index_count, &mesh.layout,
            mesh.draw_mode == TC_DRAW_LINES ? DrawMode::Lines : DrawMode::Triangles);
        free_tc_mesh_data(&mesh);
    }
    {
        auto indexed = build_unit_cylinder(CYLINDER_SEGMENTS);
        tc_mesh mesh = create_tc_mesh(indexed);
        _cylinder_mesh = graphics->create_mesh(mesh.vertices, mesh.vertex_count, mesh.indices, mesh.index_count, &mesh.layout,
            mesh.draw_mode == TC_DRAW_LINES ? DrawMode::Lines : DrawMode::Triangles);
        free_tc_mesh_data(&mesh);
    }
    {
        auto indexed = build_unit_cone(CONE_SEGMENTS);
        tc_mesh mesh = create_tc_mesh(indexed);
        _cone_mesh = graphics->create_mesh(mesh.vertices, mesh.vertex_count, mesh.indices, mesh.index_count, &mesh.layout,
            mesh.draw_mode == TC_DRAW_LINES ? DrawMode::Lines : DrawMode::Triangles);
        free_tc_mesh_data(&mesh);
    }
    {
        auto indexed = build_unit_quad();
        tc_mesh mesh = create_tc_mesh(indexed);
        _quad_mesh = graphics->create_mesh(mesh.vertices, mesh.vertex_count, mesh.indices, mesh.index_count, &mesh.layout,
            mesh.draw_mode == TC_DRAW_LINES ? DrawMode::Lines : DrawMode::Triangles);
        free_tc_mesh_data(&mesh);
    }

    _initialized = true;
}

void SolidPrimitiveRenderer::begin(
    GraphicsBackend* graphics,
    const Mat44f& view,
    const Mat44f& proj,
    bool depth_test,
    bool blend
) {
    _graphics = graphics;
    _ensure_initialized(graphics);

    // Setup state via GraphicsBackend
    graphics->set_depth_test(depth_test);
    if (blend) {
        graphics->set_blend(true);
        graphics->set_blend_func(BlendFactor::SrcAlpha, BlendFactor::OneMinusSrcAlpha);
    } else {
        graphics->set_blend(false);
    }
    graphics->set_cull_face(true);

    // Bind shader and set view/proj
    _shader.use();
    _shader.set_uniform_mat4("u_view", view.data, false);
    _shader.set_uniform_mat4("u_projection", proj.data, false);
}

void SolidPrimitiveRenderer::end() {
    // Nothing needed
}

void SolidPrimitiveRenderer::draw_torus(const Mat44f& model, const Color4& color) {
    _shader.set_uniform_mat4("u_model", model.data, false);
    _shader.set_uniform_vec4("u_color", color.r, color.g, color.b, color.a);
    _torus_mesh->draw();
}

void SolidPrimitiveRenderer::draw_cylinder(const Mat44f& model, const Color4& color) {
    _shader.set_uniform_mat4("u_model", model.data, false);
    _shader.set_uniform_vec4("u_color", color.r, color.g, color.b, color.a);
    _cylinder_mesh->draw();
}

void SolidPrimitiveRenderer::draw_cone(const Mat44f& model, const Color4& color) {
    _shader.set_uniform_mat4("u_model", model.data, false);
    _shader.set_uniform_vec4("u_color", color.r, color.g, color.b, color.a);
    _cone_mesh->draw();
}

void SolidPrimitiveRenderer::draw_quad(const Mat44f& model, const Color4& color) {
    _shader.set_uniform_mat4("u_model", model.data, false);
    _shader.set_uniform_vec4("u_color", color.r, color.g, color.b, color.a);
    _quad_mesh->draw();
}

void SolidPrimitiveRenderer::draw_arrow(
    const Vec3f& origin,
    const Vec3f& direction,
    float length,
    const Color4& color,
    float shaft_radius,
    float head_radius,
    float head_length_ratio
) {
    float dir_len = direction.norm();
    if (dir_len < 1e-6f) return;
    Vec3f dir = direction / dir_len;

    float head_length = length * head_length_ratio;
    float shaft_length = length - head_length;

    // Rotation matrix to align Z with direction
    Mat44f rot = rotation_matrix_align_z_to(dir);

    // Shaft: cylinder from origin
    Mat44f shaft_model = compose_trs(
        origin,
        rot,
        Vec3f{shaft_radius, shaft_radius, shaft_length}
    );
    draw_cylinder(shaft_model, color);

    // Head: cone from shaft_end to tip
    Vec3f shaft_end = origin + dir * shaft_length;
    Mat44f head_model = compose_trs(
        shaft_end,
        rot,
        Vec3f{head_radius, head_radius, head_length}
    );
    draw_cone(head_model, color);
}

} // namespace termin
