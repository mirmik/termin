#include <termin/render/line_renderer.hpp>

#include <algorithm>

#include <tcbase/tc_log.hpp>
#include <tgfx2/line_mesh_builder.hpp>

namespace termin {
namespace {

const char* kDefaultLineVert = R"(
#version 330 core

layout(location = 0) in vec3 a_position;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

void main() {
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
)";

const char* kDefaultLineFrag = R"(
#version 330 core

uniform vec4 u_color;

out vec4 FragColor;

void main() {
    FragColor = u_color;
}
)";

double value_as_double(const tc_value* value) {
    if (!value) {
        return 0.0;
    }
    switch (value->type) {
        case TC_VALUE_INT:
            return static_cast<double>(value->data.i);
        case TC_VALUE_FLOAT:
            return static_cast<double>(value->data.f);
        case TC_VALUE_DOUBLE:
            return value->data.d;
        default:
            return 0.0;
    }
}

bool value_to_vec3(const tc_value* value, tc_vec3& out) {
    if (!value || value->type != TC_VALUE_LIST || tc_value_list_size(value) < 3) {
        return false;
    }
    out.x = value_as_double(tc_value_list_get(const_cast<tc_value*>(value), 0));
    out.y = value_as_double(tc_value_list_get(const_cast<tc_value*>(value), 1));
    out.z = value_as_double(tc_value_list_get(const_cast<tc_value*>(value), 2));
    return true;
}

tc_value vec3_to_value(const tc_vec3& point) {
    tc_value value = tc_value_list_new();
    tc_value_list_push(&value, tc_value_double(point.x));
    tc_value_list_push(&value, tc_value_double(point.y));
    tc_value_list_push(&value, tc_value_double(point.z));
    return value;
}

tgfx::LinePoint3 to_line_point(const tc_vec3& point) {
    return {
        static_cast<float>(point.x),
        static_cast<float>(point.y),
        static_cast<float>(point.z),
    };
}

} // namespace

LineRenderer::LineRenderer(const char* type_name)
    : Component(type_name)
{
    install_drawable_vtable(&_c);
}

TcMaterial LineRenderer::default_material() {
    static TcMaterial mat;
    if (mat.is_valid()) {
        return mat;
    }

    mat = TcMaterial::create("DefaultLineMaterial", "");
    if (!mat.is_valid()) {
        tc::Log::error("[LineRenderer] failed to create default material");
        return mat;
    }

    mat.set_shader_name("DefaultLineShader");
    tc_render_state state = tc_render_state_opaque();
    state.cull = 0;
    tc_material_phase* phase = mat.add_phase_from_sources(
        kDefaultLineVert,
        kDefaultLineFrag,
        "",
        "DefaultLineShader",
        "opaque",
        0,
        state);
    if (!phase) {
        tc::Log::error("[LineRenderer] failed to create default material phase");
        return mat;
    }
    tc_material_phase_set_color(phase, 1.0f, 1.0f, 1.0f, 1.0f);
    return mat;
}

TcMaterial LineRenderer::effective_material() const {
    if (material.is_valid()) {
        return material;
    }
    return default_material();
}

void LineRenderer::set_points(const std::vector<tc_vec3>& points) {
    points_ = points;
    dirty_ = true;
}

void LineRenderer::set_points(std::vector<tc_vec3>&& points) {
    points_ = std::move(points);
    dirty_ = true;
}

void LineRenderer::clear_points() {
    points_.clear();
    dirty_ = true;
}

void LineRenderer::add_point(const tc_vec3& point) {
    points_.push_back(point);
    dirty_ = true;
}

void LineRenderer::set_width(float value) {
    width = value;
    dirty_ = true;
}

void LineRenderer::set_raw_lines(bool value) {
    raw_lines = value;
    dirty_ = true;
}

void LineRenderer::set_up_hint(const tc_vec3& value) {
    up_hint = value;
    dirty_ = true;
}

void LineRenderer::set_material(const TcMaterial& value) {
    material = value;
}

void LineRenderer::set_material_by_name(const std::string& name) {
    tc_material_handle handle = tc_material_find_by_name(name.c_str());
    if (tc_material_handle_is_invalid(handle)) {
        tc::Log::error("[LineRenderer] material '%s' not found", name.c_str());
        material = TcMaterial();
        return;
    }
    material = TcMaterial(handle);
}

void LineRenderer::rebuild_geometry() {
    mesh_ = TcMesh();
    if (points_.size() < 2) {
        dirty_ = false;
        return;
    }

    tc_vertex_layout layout = tc_vertex_layout_pos();

    if (raw_lines) {
        std::vector<float> vertices;
        vertices.reserve(points_.size() * 3);
        for (const tc_vec3& point : points_) {
            vertices.push_back(static_cast<float>(point.x));
            vertices.push_back(static_cast<float>(point.y));
            vertices.push_back(static_cast<float>(point.z));
        }

        std::vector<uint32_t> indices;
        indices.reserve((points_.size() - 1) * 2);
        for (uint32_t i = 1; i < static_cast<uint32_t>(points_.size()); ++i) {
            indices.push_back(i - 1);
            indices.push_back(i);
        }

        mesh_ = TcMesh::from_interleaved(
            vertices.data(),
            points_.size(),
            indices.data(),
            indices.size(),
            layout,
            "line_renderer_raw",
            "",
            TC_DRAW_LINES);
    } else {
        std::vector<tgfx::LinePoint3> line_points;
        line_points.reserve(points_.size());
        for (const tc_vec3& point : points_) {
            line_points.push_back(to_line_point(point));
        }

        tgfx::LineStyle style;
        style.width = std::max(width, 0.0f);
        style.up_hint = to_line_point(up_hint);
        style.cap = tgfx::LineCapStyle::Round;
        style.join = tgfx::LineJoinStyle::Round;
        style.round_segments = 8;
        tgfx::LineMesh line_mesh = tgfx::build_line_mesh(line_points, style);
        if (line_mesh.empty()) {
            dirty_ = false;
            return;
        }

        std::vector<float> vertices;
        vertices.reserve(line_mesh.vertices.size() * 3);
        for (const tgfx::LineVertex& vertex : line_mesh.vertices) {
            vertices.push_back(vertex.position.x);
            vertices.push_back(vertex.position.y);
            vertices.push_back(vertex.position.z);
        }

        mesh_ = TcMesh::from_interleaved(
            vertices.data(),
            line_mesh.vertices.size(),
            line_mesh.indices.data(),
            line_mesh.indices.size(),
            layout,
            "line_renderer",
            "",
            TC_DRAW_TRIANGLES);
    }

    if (!mesh_.is_valid()) {
        tc::Log::error("[LineRenderer] failed to rebuild line mesh");
    }
    dirty_ = false;
}

void LineRenderer::ensure_geometry() {
    if (dirty_) {
        rebuild_geometry();
    }
}

tc_mesh* LineRenderer::current_mesh_ptr() const {
    const_cast<LineRenderer*>(this)->ensure_geometry();
    return mesh_.get();
}

tc_value LineRenderer::serialize_points() const {
    tc_value result = tc_value_list_new();
    for (const tc_vec3& point : points_) {
        tc_value_list_push(&result, vec3_to_value(point));
    }
    return result;
}

void LineRenderer::deserialize_points(const tc_value* value) {
    std::vector<tc_vec3> loaded;
    if (value && value->type == TC_VALUE_LIST) {
        loaded.reserve(tc_value_list_size(value));
        for (size_t i = 0; i < tc_value_list_size(value); ++i) {
            tc_value* item = tc_value_list_get(const_cast<tc_value*>(value), i);
            tc_vec3 point = {0.0, 0.0, 0.0};
            if (value_to_vec3(item, point)) {
                loaded.push_back(point);
            } else {
                tc::Log::error("[LineRenderer] invalid point at index %zu during deserialize", i);
            }
        }
    }
    set_points(std::move(loaded));
}

tc_value LineRenderer::serialize_data() const {
    return Component::serialize_data();
}

void LineRenderer::deserialize_data(const tc_value* data, tc_scene_handle scene) {
    Component::deserialize_data(data, scene);
    dirty_ = true;
}

std::set<std::string> LineRenderer::get_phase_marks() const {
    std::set<std::string> marks;
    TcMaterial mat = effective_material();
    tc_material* raw = mat.get();
    if (!raw) {
        return marks;
    }
    for (size_t i = 0; i < raw->phase_count; ++i) {
        marks.insert(raw->phases[i].phase_mark);
    }
    return marks;
}

void LineRenderer::draw_geometry(const RenderContext& context, int geometry_id) {
    (void)context;
    (void)geometry_id;
    tc_mesh* mesh = current_mesh_ptr();
    if (!mesh) {
        return;
    }
    tc_mesh_draw_gpu(mesh);
}

tc_mesh* LineRenderer::get_mesh_for_phase(const std::string& phase_mark, int geometry_id) const {
    (void)phase_mark;
    (void)geometry_id;
    return current_mesh_ptr();
}

std::vector<GeometryDrawCall> LineRenderer::get_geometry_draws(const std::string* phase_mark) {
    std::vector<GeometryDrawCall> draws;
    tc_mesh* mesh = current_mesh_ptr();
    if (!mesh) {
        return draws;
    }

    TcMaterial mat = effective_material();
    tc_material* raw = mat.get();
    if (!raw) {
        return draws;
    }

    for (size_t i = 0; i < raw->phase_count; ++i) {
        tc_material_phase* phase = &raw->phases[i];
        if (!phase_mark || *phase_mark == phase->phase_mark) {
            draws.emplace_back(phase, 0);
        }
    }
    return draws;
}

TcMesh LineRenderer::get_mesh() {
    ensure_geometry();
    return mesh_;
}

} // namespace termin
