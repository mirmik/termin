#include "solid_primitive_renderer.hpp"
#include <tcbase/tc_log.hpp>

#include <tgfx2/render_context.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/enums.hpp>
#include <tgfx2/vertex_layout.hpp>

#include <vector>
#include <cmath>
#include <cstring>
#include <span>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace termin {

namespace {

// Push constants (80 bytes: mat4 mvp + vec4 color) fit Vulkan's guaranteed
// 128-byte minimum. Caller pre-multiplies proj * view * model on CPU so
// the vertex shader only needs one matrix. `#ifdef VULKAN` selects the
// native push_constant block; on GL we fall back to the std140 UBO at
// binding 14 (the ring buffer tgfx2 uses to emulate push constants).
const char* SOLID_COMMON_PUSH = R"(
struct SolidPushData {
    mat4 u_mvp;
    vec4 u_color;
};
#ifdef VULKAN
layout(push_constant) uniform SolidPushBlock { SolidPushData pc; };
#else
layout(std140, binding = 14) uniform SolidPushBlock { SolidPushData pc; };
#endif
)";

const char* SOLID_VERT = R"(#version 450 core
struct SolidPushData {
    mat4 u_mvp;
    vec4 u_color;
};
#ifdef VULKAN
layout(push_constant) uniform SolidPushBlock { SolidPushData pc; };
#else
layout(std140, binding = 14) uniform SolidPushBlock { SolidPushData pc; };
#endif

layout(location = 0) in vec3 a_position;
layout(location = 0) out vec4 v_color;

void main() {
    v_color = pc.u_color;
    gl_Position = pc.u_mvp * vec4(a_position, 1.0);
}
)";

const char* SOLID_FRAG = R"(#version 450 core
layout(location = 0) in vec4 v_color;
layout(location = 0) out vec4 fragColor;

void main() {
    fragColor = v_color;
}
)";

struct SolidPushData {
    float u_mvp[16];
    float u_color[4];
};
static_assert(sizeof(SolidPushData) == 80,
              "SolidPushData must be 80 bytes (mat4 + vec4)");

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

// Upload an IndexedMesh (pos-only layout: 3 floats per vertex) as a
// tgfx2 vertex + index buffer pair. The returned MeshRes owns both
// handles; the caller is responsible for destroying them through the
// same tgfx2 device.
SolidPrimitiveRenderer::MeshRes upload_mesh_tgfx2(
    tgfx::IRenderDevice& device,
    const IndexedMesh& indexed_mesh
) {
    SolidPrimitiveRenderer::MeshRes res;

    tgfx::BufferDesc vb_desc;
    vb_desc.size = indexed_mesh.vertices.size() * sizeof(float);
    vb_desc.usage = tgfx::BufferUsage::Vertex | tgfx::BufferUsage::CopyDst;
    res.vbo = device.create_buffer(vb_desc);
    device.upload_buffer(
        res.vbo,
        std::span<const uint8_t>(
            reinterpret_cast<const uint8_t*>(indexed_mesh.vertices.data()),
            vb_desc.size));

    tgfx::BufferDesc ib_desc;
    ib_desc.size = indexed_mesh.indices.size() * sizeof(uint32_t);
    ib_desc.usage = tgfx::BufferUsage::Index | tgfx::BufferUsage::CopyDst;
    res.ibo = device.create_buffer(ib_desc);
    device.upload_buffer(
        res.ibo,
        std::span<const uint8_t>(
            reinterpret_cast<const uint8_t*>(indexed_mesh.indices.data()),
            ib_desc.size));

    res.index_count = static_cast<uint32_t>(indexed_mesh.indices.size());
    return res;
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

SolidPrimitiveRenderer::~SolidPrimitiveRenderer() {
    if (_device) {
        auto destroy_mesh = [this](MeshRes& m) {
            if (m.vbo) _device->destroy(m.vbo);
            if (m.ibo) _device->destroy(m.ibo);
            m = {};
        };
        destroy_mesh(_torus);
        destroy_mesh(_cylinder);
        destroy_mesh(_cone);
        destroy_mesh(_quad);
        if (_vs) _device->destroy(_vs);
        if (_fs) _device->destroy(_fs);
        _vs = {};
        _fs = {};
    }
}

SolidPrimitiveRenderer::SolidPrimitiveRenderer(SolidPrimitiveRenderer&& other) noexcept {
    *this = std::move(other);
}

SolidPrimitiveRenderer& SolidPrimitiveRenderer::operator=(SolidPrimitiveRenderer&& other) noexcept {
    if (this != &other) {
        _torus = other._torus;       other._torus = {};
        _cylinder = other._cylinder; other._cylinder = {};
        _cone = other._cone;         other._cone = {};
        _quad = other._quad;         other._quad = {};
        _initialized = other._initialized;
        _vs = other._vs; other._vs = {};
        _fs = other._fs; other._fs = {};
        _device = other._device;
        _ctx2 = other._ctx2;
        _vp = other._vp;

        other._initialized = false;
        other._device = nullptr;
        other._ctx2 = nullptr;
    }
    return *this;
}

void SolidPrimitiveRenderer::_ensure_initialized(tgfx::IRenderDevice* device) {
    if (_initialized && _device == device) return;

    // New device — release previous resources (if any).
    if (_device && _device != device) {
        if (_torus.vbo) _device->destroy(_torus.vbo);
        if (_torus.ibo) _device->destroy(_torus.ibo);
        if (_cylinder.vbo) _device->destroy(_cylinder.vbo);
        if (_cylinder.ibo) _device->destroy(_cylinder.ibo);
        if (_cone.vbo) _device->destroy(_cone.vbo);
        if (_cone.ibo) _device->destroy(_cone.ibo);
        if (_quad.vbo) _device->destroy(_quad.vbo);
        if (_quad.ibo) _device->destroy(_quad.ibo);
        if (_vs) _device->destroy(_vs);
        if (_fs) _device->destroy(_fs);
        _torus = _cylinder = _cone = _quad = {};
        _vs = {};
        _fs = {};
    }
    _device = device;

    if (!_vs) {
        tgfx::ShaderDesc vs_desc;
        vs_desc.stage = tgfx::ShaderStage::Vertex;
        vs_desc.source = SOLID_VERT;
        _vs = device->create_shader(vs_desc);
    }
    if (!_fs) {
        tgfx::ShaderDesc fs_desc;
        fs_desc.stage = tgfx::ShaderStage::Fragment;
        fs_desc.source = SOLID_FRAG;
        _fs = device->create_shader(fs_desc);
    }

    // Upload unit primitives as tgfx2 buffers (pos-only, vec3 at loc 0).
    _torus    = upload_mesh_tgfx2(*device,
        build_unit_torus(TORUS_MAJOR_SEGMENTS, TORUS_MINOR_SEGMENTS, TORUS_MINOR_RATIO));
    _cylinder = upload_mesh_tgfx2(*device, build_unit_cylinder(CYLINDER_SEGMENTS));
    _cone     = upload_mesh_tgfx2(*device, build_unit_cone(CONE_SEGMENTS));
    _quad     = upload_mesh_tgfx2(*device, build_unit_quad());

    _initialized = true;
}

void SolidPrimitiveRenderer::begin(
    tgfx::RenderContext2* ctx2,
    const Mat44f& view,
    const Mat44f& proj,
    bool depth_test,
    bool blend
) {
    if (!ctx2) {
        tc::Log::error("[SolidPrimitiveRenderer] ctx2 is null");
        return;
    }
    _ctx2 = ctx2;
    _ensure_initialized(&ctx2->device());

    _vp = proj * view;

    // ctx2 state. Caller owns the render pass boundary; we just set
    // pipeline state and shader binding.
    ctx2->set_depth_test(depth_test);
    ctx2->set_depth_write(depth_test);
    if (blend) {
        ctx2->set_blend(true);
        ctx2->set_blend_func(tgfx::BlendFactor::SrcAlpha,
                             tgfx::BlendFactor::OneMinusSrcAlpha);
    } else {
        ctx2->set_blend(false);
    }
    ctx2->set_cull(tgfx::CullMode::Back);

    ctx2->bind_shader(_vs, _fs);

    // Vertex layout: single vec3 position at location 0, tightly packed.
    tgfx::VertexBufferLayout layout;
    layout.stride = 3 * sizeof(float);
    layout.attributes.push_back({0, tgfx::VertexFormat::Float3, 0});
    ctx2->set_vertex_layout(layout);
    ctx2->set_topology(tgfx::PrimitiveTopology::TriangleList);
}

void SolidPrimitiveRenderer::end() {
    // Nothing needed — caller closes its ctx2 pass.
}

void SolidPrimitiveRenderer::_push_and_draw(const Mat44f& model,
                                            const Color4& color,
                                            const MeshRes& mesh) {
    if (!_ctx2) return;
    Mat44f mvp = _vp * model;
    SolidPushData push{};
    std::memcpy(push.u_mvp, mvp.data, sizeof(push.u_mvp));
    push.u_color[0] = color.r;
    push.u_color[1] = color.g;
    push.u_color[2] = color.b;
    push.u_color[3] = color.a;
    _ctx2->set_push_constants(&push, static_cast<uint32_t>(sizeof(push)));
    _ctx2->draw(mesh.vbo, mesh.ibo, mesh.index_count);
}

void SolidPrimitiveRenderer::draw_torus(const Mat44f& model, const Color4& color) {
    _push_and_draw(model, color, _torus);
}

void SolidPrimitiveRenderer::draw_cylinder(const Mat44f& model, const Color4& color) {
    _push_and_draw(model, color, _cylinder);
}

void SolidPrimitiveRenderer::draw_cone(const Mat44f& model, const Color4& color) {
    _push_and_draw(model, color, _cone);
}

void SolidPrimitiveRenderer::draw_quad(const Mat44f& model, const Color4& color) {
    _push_and_draw(model, color, _quad);
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
