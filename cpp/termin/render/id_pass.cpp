#include "termin/render/id_pass.hpp"
#include "termin/render/tc_shader_handle.hpp"
#include "tc_log.hpp"

namespace termin {

const char* ID_PASS_VERT = R"(
#version 330 core

layout(location=0) in vec3 a_position;
layout(location=1) in vec3 a_normal;
layout(location=2) in vec2 a_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

void main() {
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
)";

const char* ID_PASS_FRAG = R"(
#version 330 core

uniform vec3 u_pickColor;
out vec4 fragColor;

void main() {
    fragColor = vec4(u_pickColor, 1.0);
}
)";

namespace {

uint32_t hash_int(uint32_t i) {
    i = ((i >> 16) ^ i) * 0x45d9f3b;
    i = ((i >> 16) ^ i) * 0x45d9f3b;
    i = (i >> 16) ^ i;
    return i;
}

} // anonymous namespace

void IdPass::id_to_rgb(int id, float& r, float& g, float& b) {
    uint32_t pid = hash_int(static_cast<uint32_t>(id));

    uint32_t r_int = pid & 0x000000FF;
    uint32_t g_int = (pid & 0x0000FF00) >> 8;
    uint32_t b_int = (pid & 0x00FF0000) >> 16;

    r = static_cast<float>(r_int) / 255.0f;
    g = static_cast<float>(g_int) / 255.0f;
    b = static_cast<float>(b_int) / 255.0f;
}

void IdPass::execute_with_data(
    GraphicsBackend* graphics,
    const FBOMap& reads_fbos,
    const FBOMap& writes_fbos,
    const Rect4i& rect,
    tc_scene* scene,
    const Mat44f& view,
    const Mat44f& projection,
    int64_t context_key,
    uint64_t layer_mask
) {
    // Find output FBO
    auto it = writes_fbos.find(output_res);
    if (it == writes_fbos.end() || it->second == nullptr) {
        return;
    }
    FramebufferHandle* fb = it->second;

    // Bind and clear
    bind_and_clear(graphics, fb, rect);
    apply_default_render_state(graphics);

    // Get shader
    TcShader& shader = get_shader(graphics);

    // Import Python picking module for id_to_rgb cache
    nb::object py_id_to_rgb;
    try {
        nb::object picking_module = nb::module_::import_("termin.visualization.core.picking");
        py_id_to_rgb = picking_module.attr("id_to_rgb");
    } catch (const nb::python_error& e) {
        tc::Log::error("IdPass: Failed to import picking module: %s", e.what());
        return;
    }

    // Collect draw calls
    auto draw_calls = collect_draw_calls(scene, layer_mask);

    // Render
    entity_names.clear();
    std::set<std::string> seen_entities;

    nb::dict extra_uniforms;

    RenderContext context;
    context.view = view;
    context.projection = projection;
    context.context_key = context_key;
    context.graphics = graphics;
    context.phase = phase_name();
    context.extra_uniforms = extra_uniforms;

    const std::string& debug_symbol = get_debug_internal_point();

    int current_pick_id = -1;
    float pick_r = 0.0f, pick_g = 0.0f, pick_b = 0.0f;

    for (const auto& dc : draw_calls) {
        Mat44f model = get_model_matrix(dc.entity);
        context.model = model;

        const char* name = dc.entity.name();
        if (name && seen_entities.insert(name).second) {
            entity_names.push_back(name);
        }

        // Update pick color if pick_id changed
        if (dc.pick_id != current_pick_id) {
            current_pick_id = dc.pick_id;

            try {
                nb::tuple rgb = nb::cast<nb::tuple>(py_id_to_rgb(dc.pick_id));
                pick_r = nb::cast<float>(rgb[0]);
                pick_g = nb::cast<float>(rgb[1]);
                pick_b = nb::cast<float>(rgb[2]);
            } catch (const nb::python_error& e) {
                id_to_rgb(dc.pick_id, pick_r, pick_g, pick_b);
            }

            extra_uniforms["u_pickColor"] = nb::make_tuple("vec3", nb::make_tuple(pick_r, pick_g, pick_b));
            context.extra_uniforms = extra_uniforms;
        }

        // Get shader handle and apply override
        tc_shader_handle base_handle = shader.handle;
        tc_shader_handle shader_handle = tc_component_override_shader(
            dc.component, phase_name(), dc.geometry_id, base_handle
        );

        // Use TcShader
        TcShader shader_to_use(shader_handle);
        shader_to_use.use();

        shader_to_use.set_uniform_mat4("u_model", model.data, false);
        shader_to_use.set_uniform_mat4("u_view", view.data, false);
        shader_to_use.set_uniform_mat4("u_projection", projection.data, false);
        shader_to_use.set_uniform_vec3("u_pickColor", pick_r, pick_g, pick_b);

        context.current_tc_shader = shader_to_use;

        tc_component_draw_geometry(dc.component, &context, dc.geometry_id);

        if (!debug_symbol.empty() && name && debug_symbol == name) {
            maybe_blit_to_debugger(graphics, fb, name, rect.width, rect.height);
        }
    }
}

} // namespace termin
