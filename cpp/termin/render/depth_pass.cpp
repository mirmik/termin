#include "termin/render/depth_pass.hpp"

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
    : RenderFramePass(pass_name, {input_res}, {output_res})
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
    graphics->bind_framebuffer(fb);
    graphics->set_viewport(0, 0, rect.width, rect.height);

    // Clear: white color (max depth) + depth = 1.0
    graphics->clear_color_depth(1.0f, 1.0f, 1.0f, 1.0f);

    // Apply render state
    RenderState state;
    state.depth_test = true;
    state.depth_write = true;
    state.blend = false;
    state.cull = true;
    graphics->apply_render_state(state);

    // Get depth shader
    ShaderProgram* shader = get_depth_shader(graphics);
    shader->use();
    shader->set_uniform_matrix4("u_view", view.data, false);
    shader->set_uniform_matrix4("u_projection", projection.data, false);
    shader->set_uniform_float("u_near", near_plane);
    shader->set_uniform_float("u_far", far_plane);

    // Extra uniforms for SkinnedMeshRenderer (it will inject skinning and copy these)
    nb::dict extra_uniforms;
    extra_uniforms["u_near"] = nb::make_tuple("float", near_plane);
    extra_uniforms["u_far"] = nb::make_tuple("float", far_plane);

    // Create render context
    RenderContext context;
    context.view = view;
    context.projection = projection;
    context.context_key = context_key;
    context.graphics = graphics;
    context.phase = "depth";
    context.current_shader = shader;
    context.extra_uniforms = extra_uniforms;

    // Collect draw calls
    auto draw_calls = collect_draw_calls(scene, layer_mask);

    // Update entity names for debugging
    entity_names.clear();
    std::set<std::string> seen_entities;

    for (const auto& dc : draw_calls) {
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
            tc_component_override_shader(dc.component, "depth", 0, shader)
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
        shader_to_use->set_uniform_float("u_near", near_plane);
        shader_to_use->set_uniform_float("u_far", far_plane);

        context.current_shader = shader_to_use;

        // Draw geometry (handles bone matrix upload for skinned meshes)
        tc_component_draw_geometry(dc.component, &context, 0);

        // Check for debug blit
        const std::string& debug_symbol = get_debug_internal_point();
        if (!debug_symbol.empty() && name && name == debug_symbol) {
            maybe_blit_to_debugger(graphics, fb, name, rect.width, rect.height);
        }
    }
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
