#include "termin/render/id_pass.hpp"

#include <algorithm>
#include "tc_log.hpp"
#include "termin/render/mesh_renderer.hpp"

namespace termin {

namespace {

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
    : GeometryPassBase(pass_name, {input_res}, {output_res})
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
    tc_scene* scene,
    uint64_t layer_mask
) {
    std::vector<IdDrawCall> draw_calls;

    if (!scene) {
        return draw_calls;
    }

    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    if (!pool) {
        return draw_calls;
    }

    // Estimate capacity
    size_t entity_count = tc_entity_pool_count(pool);
    draw_calls.reserve(entity_count);

    auto entity_filter = [](const Entity& ent) {
        return ent.pickable();
    };
    auto emit = [&draw_calls](const Entity& ent, tc_component* tc) {
        draw_calls.push_back(IdPass::IdDrawCall{ent, tc, static_cast<int>(ent.pick_id())});
    };
    collect_draw_calls_common(scene, layer_mask, entity_filter, emit);

    return draw_calls;
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

    // Bind FBO and set viewport
    bind_and_clear(graphics, fb, rect, 0.0f, 0.0f, 0.0f, 0.0f);
    apply_default_render_state(graphics);

    // Get pick shader
    ShaderProgram* shader = get_pick_shader(graphics);
    // Extra uniforms for SkinnedMeshRenderer (it will inject skinning and copy these)
    nb::dict extra_uniforms;

    // Collect draw calls
    auto draw_calls = collect_draw_calls(scene, layer_mask);

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

    auto setup_uniforms = [&](const IdDrawCall& dc,
                              ShaderProgram* shader_to_use,
                              const Mat44f& model,
                              const Mat44f& view_matrix,
                              const Mat44f& proj_matrix,
                              RenderContext& context) {
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

        shader_to_use->set_uniform_matrix4("u_model", model.data, false);
        shader_to_use->set_uniform_matrix4("u_view", view_matrix.data, false);
        shader_to_use->set_uniform_matrix4("u_projection", proj_matrix.data, false);
        shader_to_use->set_uniform_vec3("u_pickColor", pick_r, pick_g, pick_b);
    };

    auto maybe_blit = [&](const std::string& name, int width, int height) {
        this->maybe_blit_to_debugger(graphics, fb, name, width, height);
    };

    render_draw_calls(
        draw_calls,
        graphics,
        shader,
        view,
        projection,
        context_key,
        "pick",
        extra_uniforms,
        rect,
        setup_uniforms,
        maybe_blit
    );
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
