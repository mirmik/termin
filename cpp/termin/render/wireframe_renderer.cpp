#include "wireframe_renderer.hpp"
#include "glad/include/glad/glad.h"

#include <cmath>
#include <cstring>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace termin {

namespace {

const char* WIREFRAME_VERT = R"(
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

const char* WIREFRAME_FRAG = R"(
#version 330 core
in vec4 v_color;
out vec4 fragColor;

void main() {
    fragColor = v_color;
}
)";

uint32_t compile_shader_data(GLenum type, const char* source) {
    uint32_t shader = glCreateShader(type);
    glShaderSource(shader, 1, &source, nullptr);
    glCompileShader(shader);

    int success;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &success);
    if (!success) {
        glDeleteShader(shader);
        return 0;
    }
    return shader;
}

uint32_t create_shader_data_program(const char* vert_src, const char* frag_src) {
    uint32_t vert = compile_shader_data(GL_VERTEX_SHADER, vert_src);
    if (!vert) return 0;

    uint32_t frag = compile_shader_data(GL_FRAGMENT_SHADER, frag_src);
    if (!frag) {
        glDeleteShader(vert);
        return 0;
    }

    uint32_t program = glCreateProgram();
    glAttachShader(program, vert);
    glAttachShader(program, frag);
    glLinkProgram(program);

    glDeleteShader(vert);
    glDeleteShader(frag);

    int success;
    glGetProgramiv(program, GL_LINK_STATUS, &success);
    if (!success) {
        glDeleteProgram(program);
        return 0;
    }

    return program;
}

// Build unit circle vertices in XY plane, radius=1, centered at origin
void build_unit_circle(float* out_vertices, int segments) {
    for (int i = 0; i < segments; ++i) {
        float angle = static_cast<float>(2.0 * M_PI * i / segments);
        out_vertices[i * 3 + 0] = std::cos(angle);
        out_vertices[i * 3 + 1] = std::sin(angle);
        out_vertices[i * 3 + 2] = 0.0f;
    }
}

// Build unit half-circle (arc) vertices in XY plane, from +X to -X via +Y
void build_unit_arc(float* out_vertices, int segments) {
    for (int i = 0; i <= segments; ++i) {
        float angle = static_cast<float>(M_PI * i / segments);
        out_vertices[i * 3 + 0] = std::cos(angle);
        out_vertices[i * 3 + 1] = std::sin(angle);
        out_vertices[i * 3 + 2] = 0.0f;
    }
}

// Build unit box edges, from -0.5 to +0.5 on each axis. Returns 24 vertices (12 edges * 2)
void build_unit_box(float* out_vertices) {
    // 8 corners
    float corners[8][3] = {
        {-0.5f, -0.5f, -0.5f},
        {+0.5f, -0.5f, -0.5f},
        {+0.5f, +0.5f, -0.5f},
        {-0.5f, +0.5f, -0.5f},
        {-0.5f, -0.5f, +0.5f},
        {+0.5f, -0.5f, +0.5f},
        {+0.5f, +0.5f, +0.5f},
        {-0.5f, +0.5f, +0.5f},
    };

    // 12 edges as pairs of vertex indices
    int edges[12][2] = {
        {0, 1}, {1, 2}, {2, 3}, {3, 0},  // bottom
        {4, 5}, {5, 6}, {6, 7}, {7, 4},  // top
        {0, 4}, {1, 5}, {2, 6}, {3, 7},  // vertical
    };

    for (int i = 0; i < 12; ++i) {
        int a = edges[i][0];
        int b = edges[i][1];
        // First vertex of edge
        out_vertices[i * 6 + 0] = corners[a][0];
        out_vertices[i * 6 + 1] = corners[a][1];
        out_vertices[i * 6 + 2] = corners[a][2];
        // Second vertex of edge
        out_vertices[i * 6 + 3] = corners[b][0];
        out_vertices[i * 6 + 4] = corners[b][1];
        out_vertices[i * 6 + 5] = corners[b][2];
    }
}

// Build unit line from origin to +Z
void build_unit_line(float* out_vertices) {
    out_vertices[0] = 0.0f; out_vertices[1] = 0.0f; out_vertices[2] = 0.0f;
    out_vertices[3] = 0.0f; out_vertices[4] = 0.0f; out_vertices[5] = 1.0f;
}

// Simple shader wrapper for internal use
class SimpleShader {
public:
    uint32_t program = 0;
    int u_model_loc = -1;
    int u_view_loc = -1;
    int u_proj_loc = -1;
    int u_color_loc = -1;

    bool create(const char* vert, const char* frag) {
        program = create_shader_data_program(vert, frag);
        if (!program) return false;

        u_model_loc = glGetUniformLocation(program, "u_model");
        u_view_loc = glGetUniformLocation(program, "u_view");
        u_proj_loc = glGetUniformLocation(program, "u_projection");
        u_color_loc = glGetUniformLocation(program, "u_color");
        return true;
    }

    void use() {
        glUseProgram(program);
    }

    void set_model(const Mat44f& m) {
        glUniformMatrix4fv(u_model_loc, 1, GL_FALSE, m.data);
    }

    void set_view(const Mat44f& m) {
        glUniformMatrix4fv(u_view_loc, 1, GL_FALSE, m.data);
    }

    void set_proj(const Mat44f& m) {
        glUniformMatrix4fv(u_proj_loc, 1, GL_FALSE, m.data);
    }

    void set_color(const Color4& c) {
        glUniform4f(u_color_loc, c.r, c.g, c.b, c.a);
    }

    void destroy() {
        if (program) {
            glDeleteProgram(program);
            program = 0;
        }
    }
};

} // anonymous namespace


// Store shader as opaque pointer to avoid exposing SimpleShader in header
struct WireframeShaderData {
    SimpleShader shader;
};

static WireframeShaderData* get_shader_data_data(void* ptr) {
    return reinterpret_cast<WireframeShaderData*>(ptr);
}


WireframeRenderer::WireframeRenderer() = default;

WireframeRenderer::~WireframeRenderer() {
    if (_shader_data && _owns_shader) {
        auto* data = get_shader_data_data(_shader_data);
        data->shader.destroy();
        delete data;
    }
    if (_circle_vao) glDeleteVertexArrays(1, &_circle_vao);
    if (_circle_vbo) glDeleteBuffers(1, &_circle_vbo);
    if (_arc_vao) glDeleteVertexArrays(1, &_arc_vao);
    if (_arc_vbo) glDeleteBuffers(1, &_arc_vbo);
    if (_box_vao) glDeleteVertexArrays(1, &_box_vao);
    if (_box_vbo) glDeleteBuffers(1, &_box_vbo);
    if (_line_vao) glDeleteVertexArrays(1, &_line_vao);
    if (_line_vbo) glDeleteBuffers(1, &_line_vbo);
}

WireframeRenderer::WireframeRenderer(WireframeRenderer&& other) noexcept
    : _shader_data(other._shader_data)
    , _owns_shader(other._owns_shader)
    , _circle_vao(other._circle_vao)
    , _circle_vbo(other._circle_vbo)
    , _circle_vertex_count(other._circle_vertex_count)
    , _arc_vao(other._arc_vao)
    , _arc_vbo(other._arc_vbo)
    , _arc_vertex_count(other._arc_vertex_count)
    , _box_vao(other._box_vao)
    , _box_vbo(other._box_vbo)
    , _box_vertex_count(other._box_vertex_count)
    , _line_vao(other._line_vao)
    , _line_vbo(other._line_vbo)
    , _initialized(other._initialized)
    , _in_frame(other._in_frame)
{
    other._shader_data = nullptr;
    other._owns_shader = false;
    other._circle_vao = 0;
    other._circle_vbo = 0;
    other._arc_vao = 0;
    other._arc_vbo = 0;
    other._box_vao = 0;
    other._box_vbo = 0;
    other._line_vao = 0;
    other._line_vbo = 0;
    other._initialized = false;
    other._in_frame = false;
}

WireframeRenderer& WireframeRenderer::operator=(WireframeRenderer&& other) noexcept {
    if (this != &other) {
        // Clean up
        if (_shader_data && _owns_shader) {
            auto* data = get_shader_data_data(_shader_data);
            data->shader.destroy();
            delete data;
        }
        if (_circle_vao) glDeleteVertexArrays(1, &_circle_vao);
        if (_circle_vbo) glDeleteBuffers(1, &_circle_vbo);
        if (_arc_vao) glDeleteVertexArrays(1, &_arc_vao);
        if (_arc_vbo) glDeleteBuffers(1, &_arc_vbo);
        if (_box_vao) glDeleteVertexArrays(1, &_box_vao);
        if (_box_vbo) glDeleteBuffers(1, &_box_vbo);
        if (_line_vao) glDeleteVertexArrays(1, &_line_vao);
        if (_line_vbo) glDeleteBuffers(1, &_line_vbo);

        // Move
        _shader_data = other._shader_data;
        _owns_shader = other._owns_shader;
        _circle_vao = other._circle_vao;
        _circle_vbo = other._circle_vbo;
        _circle_vertex_count = other._circle_vertex_count;
        _arc_vao = other._arc_vao;
        _arc_vbo = other._arc_vbo;
        _arc_vertex_count = other._arc_vertex_count;
        _box_vao = other._box_vao;
        _box_vbo = other._box_vbo;
        _box_vertex_count = other._box_vertex_count;
        _line_vao = other._line_vao;
        _line_vbo = other._line_vbo;
        _initialized = other._initialized;
        _in_frame = other._in_frame;

        other._shader_data = nullptr;
        other._owns_shader = false;
        other._circle_vao = 0;
        other._circle_vbo = 0;
        other._arc_vao = 0;
        other._arc_vbo = 0;
        other._box_vao = 0;
        other._box_vbo = 0;
        other._line_vao = 0;
        other._line_vbo = 0;
        other._initialized = false;
        other._in_frame = false;
    }
    return *this;
}

void WireframeRenderer::_create_mesh(
    const float* vertices,
    int vertex_count,
    uint32_t& vao,
    uint32_t& vbo
) {
    glGenVertexArrays(1, &vao);
    glGenBuffers(1, &vbo);

    glBindVertexArray(vao);
    glBindBuffer(GL_ARRAY_BUFFER, vbo);
    glBufferData(GL_ARRAY_BUFFER, vertex_count * 3 * sizeof(float), vertices, GL_STATIC_DRAW);

    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, nullptr);

    glBindBuffer(GL_ARRAY_BUFFER, 0);
    glBindVertexArray(0);
}

void WireframeRenderer::_ensure_initialized() {
    if (_initialized) return;

    // Check if OpenGL context is available, load glad if needed
    if (!glCreateShader) {
        if (!gladLoaderLoadGL()) {
            return;
        }
    }

    // Create shader
    auto* shader_data = new WireframeShaderData();
    if (!shader_data->shader.create(WIREFRAME_VERT, WIREFRAME_FRAG)) {
        delete shader_data;
        return;
    }
    _shader_data = shader_data;
    _owns_shader = true;

    // Create circle mesh
    _circle_vertex_count = CIRCLE_SEGMENTS;
    float* circle_verts = new float[CIRCLE_SEGMENTS * 3];
    build_unit_circle(circle_verts, CIRCLE_SEGMENTS);
    _create_mesh(circle_verts, CIRCLE_SEGMENTS, _circle_vao, _circle_vbo);
    delete[] circle_verts;

    // Create arc mesh
    _arc_vertex_count = ARC_SEGMENTS + 1;
    float* arc_verts = new float[(ARC_SEGMENTS + 1) * 3];
    build_unit_arc(arc_verts, ARC_SEGMENTS);
    _create_mesh(arc_verts, ARC_SEGMENTS + 1, _arc_vao, _arc_vbo);
    delete[] arc_verts;

    // Create box mesh
    _box_vertex_count = 24;
    float box_verts[24 * 3];
    build_unit_box(box_verts);
    _create_mesh(box_verts, 24, _box_vao, _box_vbo);

    // Create line mesh
    float line_verts[6];
    build_unit_line(line_verts);
    _create_mesh(line_verts, 2, _line_vao, _line_vbo);

    _initialized = true;
}

void WireframeRenderer::begin(
    GraphicsBackend* graphics,
    const Mat44f& view,
    const Mat44f& proj,
    bool depth_test
) {
    _ensure_initialized();
    if (!_initialized) return;

    _in_frame = true;

    // Setup state
    if (depth_test) {
        glEnable(GL_DEPTH_TEST);
    } else {
        glDisable(GL_DEPTH_TEST);
    }

    glDisable(GL_CULL_FACE);
    glEnable(GL_BLEND);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);

    // Bind shader and set view/proj
    auto* data = get_shader_data_data(_shader_data);
    data->shader.use();
    data->shader.set_view(view);
    data->shader.set_proj(proj);
}

void WireframeRenderer::end() {
    if (!_in_frame) return;
    glEnable(GL_CULL_FACE);
    _in_frame = false;
}

void WireframeRenderer::draw_circle(const Mat44f& model, const Color4& color) {
    if (!_in_frame) return;

    auto* data = get_shader_data_data(_shader_data);
    data->shader.set_model(model);
    data->shader.set_color(color);

    glBindVertexArray(_circle_vao);
    glDrawArrays(GL_LINE_LOOP, 0, _circle_vertex_count);
    glBindVertexArray(0);
}

void WireframeRenderer::draw_arc(const Mat44f& model, const Color4& color) {
    if (!_in_frame) return;

    auto* data = get_shader_data_data(_shader_data);
    data->shader.set_model(model);
    data->shader.set_color(color);

    glBindVertexArray(_arc_vao);
    glDrawArrays(GL_LINE_STRIP, 0, _arc_vertex_count);
    glBindVertexArray(0);
}

void WireframeRenderer::draw_box(const Mat44f& model, const Color4& color) {
    if (!_in_frame) return;

    auto* data = get_shader_data_data(_shader_data);
    data->shader.set_model(model);
    data->shader.set_color(color);

    glBindVertexArray(_box_vao);
    glDrawArrays(GL_LINES, 0, _box_vertex_count);
    glBindVertexArray(0);
}

void WireframeRenderer::draw_line(const Mat44f& model, const Color4& color) {
    if (!_in_frame) return;

    auto* data = get_shader_data_data(_shader_data);
    data->shader.set_model(model);
    data->shader.set_color(color);

    glBindVertexArray(_line_vao);
    glDrawArrays(GL_LINES, 0, 2);
    glBindVertexArray(0);
}

// ============================================================
// Matrix helpers
// ============================================================

Mat44f mat4_identity() {
    Mat44f m;
    std::memset(m.data, 0, sizeof(m.data));
    m.data[0] = 1.0f;
    m.data[5] = 1.0f;
    m.data[10] = 1.0f;
    m.data[15] = 1.0f;
    return m;
}

Mat44f mat4_translate(float x, float y, float z) {
    Mat44f m = mat4_identity();
    // Column-major: translation is in column 3
    m.data[12] = x;
    m.data[13] = y;
    m.data[14] = z;
    return m;
}

Mat44f mat4_scale(float sx, float sy, float sz) {
    Mat44f m = mat4_identity();
    m.data[0] = sx;
    m.data[5] = sy;
    m.data[10] = sz;
    return m;
}

Mat44f mat4_scale_uniform(float s) {
    return mat4_scale(s, s, s);
}

Mat44f mat4_from_rotation_matrix(const float* rot3x3) {
    Mat44f m = mat4_identity();
    // rot3x3 is row-major 3x3, we need column-major 4x4
    // Row 0 -> column 0
    m.data[0] = rot3x3[0];
    m.data[1] = rot3x3[3];
    m.data[2] = rot3x3[6];
    // Row 1 -> column 1
    m.data[4] = rot3x3[1];
    m.data[5] = rot3x3[4];
    m.data[6] = rot3x3[7];
    // Row 2 -> column 2
    m.data[8] = rot3x3[2];
    m.data[9] = rot3x3[5];
    m.data[10] = rot3x3[8];
    return m;
}

void rotation_matrix_align_z_to_axis(const float* axis, float* out_rot3x3) {
    float x = axis[0], y = axis[1], z = axis[2];
    float length = std::sqrt(x*x + y*y + z*z);

    if (length < 1e-6f) {
        // Identity
        out_rot3x3[0] = 1; out_rot3x3[1] = 0; out_rot3x3[2] = 0;
        out_rot3x3[3] = 0; out_rot3x3[4] = 1; out_rot3x3[5] = 0;
        out_rot3x3[6] = 0; out_rot3x3[7] = 0; out_rot3x3[8] = 1;
        return;
    }

    float z_new[3] = {x/length, y/length, z/length};

    // Choose up vector
    float up[3] = {0.0f, 0.0f, 1.0f};
    float dot = z_new[0]*up[0] + z_new[1]*up[1] + z_new[2]*up[2];
    if (std::abs(dot) > 0.99f) {
        up[0] = 0.0f; up[1] = 1.0f; up[2] = 0.0f;
    }

    // x_new = cross(up, z_new)
    float x_new[3] = {
        up[1]*z_new[2] - up[2]*z_new[1],
        up[2]*z_new[0] - up[0]*z_new[2],
        up[0]*z_new[1] - up[1]*z_new[0]
    };
    float x_len = std::sqrt(x_new[0]*x_new[0] + x_new[1]*x_new[1] + x_new[2]*x_new[2]);
    x_new[0] /= x_len; x_new[1] /= x_len; x_new[2] /= x_len;

    // y_new = cross(z_new, x_new)
    float y_new[3] = {
        z_new[1]*x_new[2] - z_new[2]*x_new[1],
        z_new[2]*x_new[0] - z_new[0]*x_new[2],
        z_new[0]*x_new[1] - z_new[1]*x_new[0]
    };

    // Store as row-major: row i = basis vector i
    out_rot3x3[0] = x_new[0]; out_rot3x3[1] = y_new[0]; out_rot3x3[2] = z_new[0];
    out_rot3x3[3] = x_new[1]; out_rot3x3[4] = y_new[1]; out_rot3x3[5] = z_new[1];
    out_rot3x3[6] = x_new[2]; out_rot3x3[7] = y_new[2]; out_rot3x3[8] = z_new[2];
}

} // namespace termin
