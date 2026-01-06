#include "termin/render/normal_pass.hpp"

#include <algorithm>
#include "tc_log.hpp"
#include "termin/render/mesh_renderer.hpp"

namespace termin {

namespace {

// Get model matrix from Entity as Mat44f.
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

} // anonymous namespace

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
    : RenderFramePass(pass_name, {input_res}, {output_res})
    , input_res(input_res)
    , output_res(output_res)
{
}

std::vector<ResourceSpec> NormalPass::get_resource_specs() const {
    return {
        ResourceSpec(
            input_res,                                   // resource
            "fbo",                                       // resource_type
            std::nullopt,                                // size
            std::array<double, 4>{0.5, 0.5, 1.0, 1.0},   // clear_color: neutral normal (0,0,1) encoded
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
    const std::vector<Entity>& entities
) {
    std::vector<NormalDrawCall> draw_calls;

    for (const Entity& ent : entities) {
        if (!ent.active() || !ent.visible()) {
            continue;
        }

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

            draw_calls.push_back(NormalDrawCall{ent, tc});
        }
    }

    return draw_calls;
}

void NormalPass::execute_with_data(
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

    // Clear: neutral normal (pointing up in world space, encoded)
    graphics->clear_color_depth(0.5f, 0.5f, 1.0f, 1.0f);

    // Apply render state
    RenderState state;
    state.depth_test = true;
    state.depth_write = true;
    state.blend = false;
    state.cull = true;
    graphics->apply_render_state(state);

    // Get normal shader
    ShaderProgram* shader = get_normal_shader(graphics);
    shader->use();
    shader->set_uniform_matrix4("u_view", view.data, false);
    shader->set_uniform_matrix4("u_projection", projection.data, false);

    // Create render context
    RenderContext context;
    context.view = view;
    context.projection = projection;
    context.context_key = context_key;
    context.graphics = graphics;
    context.phase = "normal";
    context.current_shader = shader;

    // Collect draw calls
    auto draw_calls = collect_draw_calls(entities);

    // Update entity names for debugging
    entity_names.clear();
    std::set<std::string> seen_entities;

    for (const auto& dc : draw_calls) {
        // Re-bind shader (draw_geometry may switch shaders)
        shader->use();

        // Set model matrix
        Mat44f model = get_model_matrix(dc.entity);
        shader->set_uniform_matrix4("u_model", model.data, false);
        context.model = model;

        // Track entity names
        const char* name = dc.entity.name();
        if (name && seen_entities.find(name) == seen_entities.end()) {
            seen_entities.insert(name);
            entity_names.push_back(name);
        }

        // Draw geometry (handles bone matrix upload for skinned meshes)
        tc_component_draw_geometry(dc.component, &context, "");
    }
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
