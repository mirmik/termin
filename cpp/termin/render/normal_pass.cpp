#include "termin/render/normal_pass.hpp"

#include <algorithm>
#include "tc_log.hpp"
#include "termin/render/mesh_renderer.hpp"

namespace termin {

// Normal shader - outputs world-space normals
static const char* NORMAL_VERT = R"(
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_world_normal;

void main()
{
    // Transform normal to world space (using normal matrix)
    mat3 normal_matrix = transpose(inverse(mat3(u_model)));
    v_world_normal = normalize(normal_matrix * a_normal);

    vec4 world_pos = u_model * vec4(a_position, 1.0);
    gl_Position = u_projection * u_view * world_pos;
}
)";

static const char* NORMAL_FRAG = R"(
#version 330 core

in vec3 v_world_normal;
out vec4 FragColor;

void main()
{
    // Encode normal from [-1,1] to [0,1]
    vec3 encoded = normalize(v_world_normal) * 0.5 + 0.5;
    FragColor = vec4(encoded, 1.0);
}
)";

NormalPass::NormalPass(
    const std::string& input_res,
    const std::string& output_res,
    const std::string& pass_name
)
    : GeometryPassBase(pass_name, {input_res}, {output_res})
    , input_res(input_res)
    , output_res(output_res)
{
}


void NormalPass::destroy() {
    _normal_shader.reset();
}


std::vector<ResourceSpec> NormalPass::get_resource_specs() const {
    return {
        ResourceSpec(
            input_res,                                   // resource
            "fbo",                                       // resource_type
            std::nullopt,                                // size
            std::array<double, 4>{0.5, 0.5, 0.5, 1.0},   // clear_color: zero normal (no data)
            1.0f,                                        // clear_depth
            std::nullopt,                                // format: default RGBA8
            1                                            // samples
        )
    };
}

ShaderProgram* NormalPass::get_normal_shader(GraphicsBackend* graphics) {
    if (!_normal_shader) {
        _normal_shader = std::make_unique<ShaderProgram>(NORMAL_VERT, NORMAL_FRAG);
        _normal_shader->ensure_ready([graphics](const char* v, const char* f, const char* g) {
            return graphics->create_shader(v, f, g);
        });
    }
    return _normal_shader.get();
}

std::vector<NormalPass::NormalDrawCall> NormalPass::collect_draw_calls(
    tc_scene* scene,
    uint64_t layer_mask
) {
    std::vector<NormalDrawCall> draw_calls;

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

    auto entity_filter = [](const Entity&) {
        return true;
    };
    auto emit = [&draw_calls](const Entity& ent, tc_component* tc) {
        draw_calls.push_back(NormalPass::NormalDrawCall{ent, tc});
    };
    collect_draw_calls_common(scene, layer_mask, entity_filter, emit);

    return draw_calls;
}

void NormalPass::execute_with_data(
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
    bind_and_clear(graphics, fb, rect, 0.5f, 0.5f, 0.5f, 1.0f);
    apply_default_render_state(graphics);

    // Get normal shader
    ShaderProgram* shader = get_normal_shader(graphics);
    // Empty extra_uniforms (normal pass doesn't need extra uniforms)
    nb::dict extra_uniforms;

    // Collect draw calls
    auto draw_calls = collect_draw_calls(scene, layer_mask);

    auto setup_uniforms = [&](const NormalDrawCall& dc,
                              ShaderProgram* shader_to_use,
                              const Mat44f& model,
                              const Mat44f& view_matrix,
                              const Mat44f& proj_matrix,
                              RenderContext& context) {
        shader_to_use->set_uniform_matrix4("u_model", model.data, false);
        shader_to_use->set_uniform_matrix4("u_view", view_matrix.data, false);
        shader_to_use->set_uniform_matrix4("u_projection", proj_matrix.data, false);
        context.extra_uniforms = extra_uniforms;
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
        "normal",
        extra_uniforms,
        rect,
        setup_uniforms,
        maybe_blit
    );
}

void NormalPass::execute(
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
