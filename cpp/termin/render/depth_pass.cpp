#include "termin/render/depth_pass.hpp"

#include <algorithm>
#include "tc_log.hpp"
#include "termin/render/mesh_renderer.hpp"

namespace termin {

namespace {

// User data for entity iteration callback
struct CollectDrawCallsData {
    std::vector<DepthPass::DepthDrawCall>* draw_calls;
    uint64_t layer_mask;
};

// Callback for tc_entity_pool_foreach
bool collect_depth_draw_calls(tc_entity_pool* pool, tc_entity_id id, void* user_data) {
    auto* data = static_cast<CollectDrawCallsData*>(user_data);

    // Filter by visibility and enabled
    if (!tc_entity_pool_visible(pool, id) || !tc_entity_pool_enabled(pool, id)) {
        return true; // continue iteration
    }

    // Filter by layer mask
    uint64_t entity_layer = tc_entity_pool_layer(pool, id);
    if (!(data->layer_mask & (1ULL << entity_layer))) {
        return true; // continue iteration
    }

    // Create Entity wrapper for component access
    Entity ent(pool, id);

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

        data->draw_calls->push_back(DepthPass::DepthDrawCall{ent, tc});
    }

    return true; // continue iteration
}

} // anonymous namespace

// Depth shader - regular version
static const char* DEPTH_VERT = R"(
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;
uniform float u_near;
uniform float u_far;

out float v_linear_depth;

void main()
{
    vec4 world_pos = u_model * vec4(a_position, 1.0);
    vec4 view_pos  = u_view * world_pos;

    // Y-forward convention: depth is along +Y axis in view space
    float y = view_pos.y;
    float depth = (y - u_near) / (u_far - u_near);

    v_linear_depth = depth;
    gl_Position = u_projection * view_pos;
}
)";

static const char* DEPTH_FRAG = R"(
#version 330 core

in float v_linear_depth;
out vec4 FragColor;

void main()
{
    float d = clamp(v_linear_depth, 0.0, 1.0);
    // R16F format - only red channel is used
    FragColor = vec4(d, 0.0, 0.0, 1.0);
}
)";


DepthPass::DepthPass(
    const std::string& input_res,
    const std::string& output_res,
    const std::string& pass_name
)
    : GeometryPassBase(pass_name, {input_res}, {output_res})
    , input_res(input_res)
    , output_res(output_res)
{
}


void DepthPass::destroy() {
    _depth_shader.reset();
}


std::vector<ResourceSpec> DepthPass::get_resource_specs() const {
    return {
        ResourceSpec(
            input_res,                                   // resource
            "fbo",                                       // resource_type
            std::nullopt,                                // size
            std::array<double, 4>{1.0, 1.0, 1.0, 1.0},   // clear_color: white = max depth
            1.0f,                                        // clear_depth
            std::string("r16f"),                         // format: 16-bit float
            1                                            // samples
        )
    };
}

ShaderProgram* DepthPass::get_depth_shader(GraphicsBackend* graphics) {
    if (!_depth_shader) {
        _depth_shader = std::make_unique<ShaderProgram>(DEPTH_VERT, DEPTH_FRAG);
        _depth_shader->ensure_ready([graphics](const char* v, const char* f, const char* g) {
            return graphics->create_shader(v, f, g);
        });
    }
    return _depth_shader.get();
}

std::vector<DepthPass::DepthDrawCall> DepthPass::collect_draw_calls(
    tc_scene* scene,
    uint64_t layer_mask
) {
    std::vector<DepthDrawCall> draw_calls;

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

    // Collect draw calls via callback iteration
    CollectDrawCallsData data;
    data.draw_calls = &draw_calls;
    data.layer_mask = layer_mask;

    tc_entity_pool_foreach(pool, collect_depth_draw_calls, &data);

    return draw_calls;
}

void DepthPass::execute_with_data(
    GraphicsBackend* graphics,
    const FBOMap& reads_fbos,
    const FBOMap& writes_fbos,
    const Rect4i& rect,
    tc_scene* scene,
    const Mat44f& view,
    const Mat44f& projection,
    int64_t context_key,
    float near_plane,
    float far_plane,
    uint64_t layer_mask
) {
    // Find output FBO
    auto it = writes_fbos.find(output_res);
    if (it == writes_fbos.end() || it->second == nullptr) {
        return;
    }
    FramebufferHandle* fb = it->second;

    // Bind FBO and set viewport
    bind_and_clear(graphics, fb, rect, 1.0f, 1.0f, 1.0f, 1.0f);
    apply_default_render_state(graphics);

    // Get depth shader
    ShaderProgram* shader = get_depth_shader(graphics);
    // Extra uniforms for SkinnedMeshRenderer (it will inject skinning and copy these)
    nb::dict extra_uniforms;
    extra_uniforms["u_near"] = nb::make_tuple("float", near_plane);
    extra_uniforms["u_far"] = nb::make_tuple("float", far_plane);

    // Collect draw calls
    auto draw_calls = collect_draw_calls(scene, layer_mask);

    auto setup_uniforms = [&](const DepthDrawCall& dc,
                              ShaderProgram* shader_to_use,
                              const Mat44f& model,
                              const Mat44f& view_matrix,
                              const Mat44f& proj_matrix,
                              RenderContext& context) {
        shader_to_use->set_uniform_matrix4("u_model", model.data, false);
        shader_to_use->set_uniform_matrix4("u_view", view_matrix.data, false);
        shader_to_use->set_uniform_matrix4("u_projection", proj_matrix.data, false);
        shader_to_use->set_uniform_float("u_near", near_plane);
        shader_to_use->set_uniform_float("u_far", far_plane);
        context.extra_uniforms = extra_uniforms;
    };

    auto maybe_blit = [&](const std::string& name, int width, int height) {
        maybe_blit_to_debugger(graphics, fb, name, width, height);
    };

    render_draw_calls(
        draw_calls,
        graphics,
        shader,
        view,
        projection,
        context_key,
        "depth",
        extra_uniforms,
        rect,
        setup_uniforms,
        maybe_blit
    );
}

void DepthPass::maybe_blit_to_debugger(
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
        tc::Log::error(e, "DepthPass::blit_to_debugger_window");
    }
}

void DepthPass::execute(
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
