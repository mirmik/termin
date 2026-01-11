#include "termin/render/id_pass.hpp"

#include <algorithm>
#include "tc_log.hpp"
#include "termin/render/mesh_renderer.hpp"

namespace termin {

namespace {

// Get model matrix from Entity as Mat44f.
// GeneralTransform3::world_matrix outputs row-major double[16], Mat44f is column-major float.
Mat44f get_model_matrix(const Entity& entity) {
    double m_row[16];
    entity.transform().world_matrix(m_row);

    // Transpose from row-major to column-major
    Mat44f result;
    for (int col = 0; col < 4; ++col) {
        for (int row = 0; row < 4; ++row) {
            result(col, row) = static_cast<float>(m_row[row * 4 + col]);
        }
    }
    return result;
}

// Simple integer hash function (same as Python hash_int)
uint32_t hash_int(uint32_t i) {
    i = ((i >> 16) ^ i) * 0x45d9f3b;
    i = ((i >> 16) ^ i) * 0x45d9f3b;
    i = (i >> 16) ^ i;
    return i;
}

} // anonymous namespace

// Pick shader - renders entity ID as color
static const char* PICK_VERT = R"(
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

static const char* PICK_FRAG = R"(
#version 330 core

uniform vec3 u_pickColor;
out vec4 fragColor;

void main() {
    fragColor = vec4(u_pickColor, 1.0);
}
)";


IdPass::IdPass(
    const std::string& input_res,
    const std::string& output_res,
    const std::string& pass_name
)
    : RenderFramePass(pass_name, {input_res}, {output_res})
    , input_res(input_res)
    , output_res(output_res)
{
}


void IdPass::destroy() {
    _pick_shader.reset();
}


std::vector<ResourceSpec> IdPass::get_resource_specs() const {
    return {
        ResourceSpec(
            input_res,                                   // resource
            "fbo",                                       // resource_type
            std::nullopt,                                // size
            std::array<double, 4>{0.0, 0.0, 0.0, 1.0},   // clear_color: black = no entity
            1.0f,                                        // clear_depth
            std::nullopt,                                // format (default RGB8)
            1                                            // samples
        )
    };
}

ShaderProgram* IdPass::get_pick_shader(GraphicsBackend* graphics) {
    if (!_pick_shader) {
        _pick_shader = std::make_unique<ShaderProgram>(PICK_VERT, PICK_FRAG);
        _pick_shader->ensure_ready([graphics](const char* v, const char* f, const char* g) {
            return graphics->create_shader(v, f, g);
        });
    }
    return _pick_shader.get();
}

void IdPass::id_to_rgb(int id, float& r, float& g, float& b) {
    // Hash the ID for visual variety (same as Python)
    uint32_t pid = hash_int(static_cast<uint32_t>(id));

    uint32_t r_int = pid & 0x000000FF;
    uint32_t g_int = (pid & 0x0000FF00) >> 8;
    uint32_t b_int = (pid & 0x00FF0000) >> 16;

    r = static_cast<float>(r_int) / 255.0f;
    g = static_cast<float>(g_int) / 255.0f;
    b = static_cast<float>(b_int) / 255.0f;
}

std::vector<IdPass::IdDrawCall> IdPass::collect_draw_calls(
    const std::vector<Entity>& entities
) {
    std::vector<IdDrawCall> draw_calls;

    for (const Entity& ent : entities) {
        if (!ent.visible() || !ent.enabled()) {
            continue;
        }

        // Check if entity is pickable
        if (!ent.pickable()) {
            continue;
        }

        int pick_id = ent.pick_id();

        // Get drawable components from entity
        size_t comp_count = ent.component_count();
        for (size_t ci = 0; ci < comp_count; ci++) {
            tc_component* tc = ent.component_at(ci);
            if (!tc || !tc->enabled) {
                continue;
            }

            // Check if component is drawable via vtable
            if (!tc_component_is_drawable(tc)) {
                continue;
            }

            draw_calls.push_back(IdDrawCall{ent, tc, pick_id});
        }
    }

    return draw_calls;
}

void IdPass::execute_with_data(
    GraphicsBackend* graphics,
    const FBOMap& reads_fbos,
    const FBOMap& writes_fbos,
    const Rect4i& rect,
    const std::vector<Entity>& entities,
    const Mat44f& view,
    const Mat44f& projection,
    int64_t context_key
) {
    // Find output FBO
    auto it = writes_fbos.find(output_res);
    if (it == writes_fbos.end() || it->second == nullptr) {
        return;
    }
    FramebufferHandle* fb = it->second;

    // Bind FBO and set viewport
    graphics->bind_framebuffer(fb);
    graphics->set_viewport(0, 0, rect.width, rect.height);

    // Clear: black (0,0,0) = no entity, depth = 1.0
    graphics->clear_color_depth(0.0f, 0.0f, 0.0f, 0.0f);

    // Apply render state
    RenderState state;
    state.depth_test = true;
    state.depth_write = true;
    state.blend = false;
    state.cull = true;
    graphics->apply_render_state(state);

    // Get pick shader
    ShaderProgram* shader = get_pick_shader(graphics);
    shader->use();
    shader->set_uniform_matrix4("u_view", view.data, false);
    shader->set_uniform_matrix4("u_projection", projection.data, false);

    // Extra uniforms for SkinnedMeshRenderer (it will inject skinning and copy these)
    nb::dict extra_uniforms;

    // Create render context
    RenderContext context;
    context.view = view;
    context.projection = projection;
    context.context_key = context_key;
    context.graphics = graphics;
    context.phase = "pick";
    context.current_shader = shader;
    context.extra_uniforms = extra_uniforms;

    // Collect draw calls
    auto draw_calls = collect_draw_calls(entities);

    // Update entity names for debugging
    entity_names.clear();
    std::set<std::string> seen_entities;

    // Current pick_id for batching
    int current_pick_id = -1;
    float pick_r = 0.0f, pick_g = 0.0f, pick_b = 0.0f;

    // Call Python id_to_rgb to update the cache for rgb_to_id lookup
    nb::object picking_module;
    nb::object py_id_to_rgb;
    try {
        picking_module = nb::module_::import_("termin.visualization.core.picking");
        py_id_to_rgb = picking_module.attr("id_to_rgb");
    } catch (const nb::python_error& e) {
        tc::Log::error("IdPass: Failed to import picking module: %s", e.what());
        return;
    }

    for (const auto& dc : draw_calls) {
        // Update pick color only when entity changes
        if (dc.pick_id != current_pick_id) {
            current_pick_id = dc.pick_id;

            // Call Python id_to_rgb to update cache
            try {
                nb::tuple rgb = nb::cast<nb::tuple>(py_id_to_rgb(dc.pick_id));
                pick_r = nb::cast<float>(rgb[0]);
                pick_g = nb::cast<float>(rgb[1]);
                pick_b = nb::cast<float>(rgb[2]);
            } catch (const nb::python_error& e) {
                // Fallback to C++ implementation
                id_to_rgb(dc.pick_id, pick_r, pick_g, pick_b);
            }

            // Update extra_uniforms for SkinnedMeshRenderer
            extra_uniforms["u_pickColor"] = nb::make_tuple("vec3", nb::make_tuple(pick_r, pick_g, pick_b));
            context.extra_uniforms = extra_uniforms;
        }

        // Set model matrix
        Mat44f model = get_model_matrix(dc.entity);
        context.model = model;

        // Track entity names
        const char* name = dc.entity.name();
        if (name && seen_entities.find(name) == seen_entities.end()) {
            seen_entities.insert(name);
            entity_names.push_back(name);
        }

        // Allow drawable to override shader (for skinning injection)
        ShaderProgram* shader_to_use = static_cast<ShaderProgram*>(
            tc_component_override_shader(dc.component, "pick", "", shader)
        );
        if (shader_to_use == nullptr) {
            shader_to_use = shader;
        }

        // Ensure shader is ready and bind
        shader_to_use->ensure_ready([graphics](const char* v, const char* f, const char* g) {
            return graphics->create_shader(v, f, g);
        });
        shader_to_use->use();

        // Apply uniforms to (possibly overridden) shader
        shader_to_use->set_uniform_matrix4("u_model", model.data, false);
        shader_to_use->set_uniform_matrix4("u_view", view.data, false);
        shader_to_use->set_uniform_matrix4("u_projection", projection.data, false);
        shader_to_use->set_uniform_vec3("u_pickColor", pick_r, pick_g, pick_b);

        context.current_shader = shader_to_use;

        // Draw geometry (handles bone matrix upload for skinned meshes)
        tc_component_draw_geometry(dc.component, &context, "");

        // Check for debug blit
        const std::string& debug_symbol = get_debug_internal_point();
        if (!debug_symbol.empty() && name && name == debug_symbol) {
            maybe_blit_to_debugger(graphics, fb, name, rect.width, rect.height);
        }
    }
}

void IdPass::maybe_blit_to_debugger(
    GraphicsBackend* graphics,
    FramebufferHandle* fb,
    const std::string& entity_name,
    int width,
    int height
) {
    // Check if debugger window is set
    if (debugger_window.is_none()) {
        return;
    }

    try {
        // Call Python debugger_window.blit_from_pass(fb, graphics, width, height, depth_callback)
        debugger_window.attr("blit_from_pass")(
            nb::cast(fb, nb::rv_policy::reference),
            nb::cast(graphics, nb::rv_policy::reference),
            width,
            height,
            depth_capture_callback
        );
    } catch (const nb::python_error& e) {
        tc::Log::error(e, "IdPass::blit_to_debugger_window");
    }
}

void IdPass::execute(
    GraphicsBackend* graphics,
    const FBOMap& reads_fbos,
    const FBOMap& writes_fbos,
    const Rect4i& rect,
    void* scene,
    void* camera,
    int64_t context_key,
    const std::vector<Light*>* lights
) {
    // Legacy execute - not used, call execute_with_data instead
}

} // namespace termin
