#include "shadow_pass.hpp"
#include "shader_program.hpp"
#include "tc_shader_handle.hpp"
#include "tc_log.hpp"

#include <cmath>
#include <algorithm>
#include <set>

namespace termin {

namespace {

// Get model matrix from Entity as Mat44f
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


ShadowPass::ShadowPass(
    const std::string& output_res,
    const std::string& pass_name,
    float caster_offset
) : RenderFramePass(pass_name, {}, {output_res}),
    output_res(output_res),
    caster_offset(caster_offset)
{
}


void ShadowPass::destroy() {
    fbo_pool_.clear();
}


std::vector<ResourceSpec> ShadowPass::get_resource_specs() const {
    return {
        ResourceSpec{
            output_res,
            "shadow_map_array",
            std::nullopt,
            std::nullopt,
            std::nullopt
        }
    };
}


FramebufferHandle* ShadowPass::get_or_create_fbo(
    GraphicsBackend* graphics,
    int resolution,
    int index
) {
    auto it = fbo_pool_.find(index);
    if (it != fbo_pool_.end()) {
        FramebufferHandle* fbo = it->second.get();
        // Check if resolution matches
        if (fbo->get_width() != resolution || fbo->get_height() != resolution) {
            fbo->resize(resolution, resolution);
        }
        return fbo;
    }

    // Create new shadow FBO
    auto fbo = graphics->create_shadow_framebuffer(resolution, resolution);
    if (!fbo) {
        tc::Log::error("ShadowPass: failed to create shadow framebuffer");
        return nullptr;
    }

    FramebufferHandle* ptr = fbo.get();
    fbo_pool_[index] = std::move(fbo);
    return ptr;
}


namespace {

struct CollectShadowDrawCallsData {
    std::vector<ShadowDrawCall>* draw_calls;
};

bool collect_shadow_drawable_draw_calls(tc_component* tc, void* user_data) {
    auto* data = static_cast<CollectShadowDrawCallsData*>(user_data);

    if (!tc_component_has_phase(tc, "shadow")) {
        return true;
    }

    void* draws_ptr = tc_component_get_geometry_draws(tc, "shadow");
    if (!draws_ptr) {
        return true;
    }

    Entity ent(tc->owner_pool, tc->owner_entity_id);

    auto* geometry_draws = static_cast<std::vector<GeometryDrawCall>*>(draws_ptr);
    for (const auto& gd : *geometry_draws) {
        data->draw_calls->push_back(ShadowDrawCall{ent, tc, gd.geometry_id});
    }

    return true;
}

} // anonymous namespace

std::vector<ShadowDrawCall> ShadowPass::collect_shadow_casters(tc_scene* scene) {
    std::vector<ShadowDrawCall> draw_calls;

    if (!scene) {
        return draw_calls;
    }

    CollectShadowDrawCallsData data;
    data.draw_calls = &draw_calls;

    int filter_flags = TC_DRAWABLE_FILTER_ENABLED
                     | TC_DRAWABLE_FILTER_VISIBLE
                     | TC_DRAWABLE_FILTER_ENTITY_ENABLED;
    tc_scene_foreach_drawable(scene, collect_shadow_drawable_draw_calls, &data, filter_flags, 0);

    return draw_calls;
}


ShadowCameraParams ShadowPass::build_shadow_params(
    const Light& light,
    const Mat44f& camera_view,
    const Mat44f& camera_projection
) {
    Vec3 light_dir = light.direction.normalized();

    // Use frustum fitting for better shadow quality
    return fit_shadow_frustum_to_camera(
        camera_view,
        camera_projection,
        light_dir,
        1.0f,  // padding
        light.shadows.map_resolution,
        true,  // stabilize (texel snapping)
        caster_offset
    );
}


std::vector<ShadowMapResult> ShadowPass::execute_shadow_pass(
    GraphicsBackend* graphics,
    tc_scene* scene,
    const std::vector<Light>& lights,
    const Mat44f& camera_view,
    const Mat44f& camera_projection,
    int64_t context_key
) {
    std::vector<ShadowMapResult> results;

    if (!graphics) {
        tc::Log::error("ShadowPass: graphics is null");
        return results;
    }

    // Check shader is set from Python
    if (!shadow_shader_program) {
        tc::Log::error("ShadowPass: shadow_shader_program not set");
        return results;
    }

    // Find lights with shadows enabled (only directional for now)
    std::vector<std::pair<int, const Light*>> shadow_lights;
    for (size_t i = 0; i < lights.size(); ++i) {
        const Light& light = lights[i];
        if (light.type == LightType::Directional && light.shadows.enabled) {
            shadow_lights.push_back({static_cast<int>(i), &light});
        }
    }

    if (shadow_lights.empty()) {
        return results;
    }

    // Collect shadow casters
    std::vector<ShadowDrawCall> draw_calls = collect_shadow_casters(scene);

    // Update entity names cache
    entity_names.clear();
    std::set<std::string> seen;
    for (const auto& dc : draw_calls) {
        const char* name = dc.entity.name();
        if (name && seen.find(name) == seen.end()) {
            seen.insert(name);
            entity_names.push_back(name);
        }
    }

    // Extract camera near plane from projection matrix
    // Our Y-forward convention: proj[2,3] = -2*far*near/(far-near)
    // proj[2,1] = (far+near)/(far-near)
    // From these we can derive near
    float camera_near = 0.1f;  // Default fallback
    float proj_23 = camera_projection(2, 3);
    float proj_21 = camera_projection(2, 1);
    if (std::abs(proj_21 - 1.0f) > 0.001f && std::abs(proj_23) > 0.001f) {
        // near = -proj_23 / (proj_21 + 1)
        camera_near = -proj_23 / (proj_21 + 1.0f);
        if (camera_near < 0.01f) camera_near = 0.1f;
    }

    // Render state: depth test/write, no blending, cull back faces
    RenderState render_state;
    render_state.depth_test = true;
    render_state.depth_write = true;
    render_state.blend = false;
    render_state.cull = true;

    // Create render context
    RenderContext context;
    context.context_key = context_key;
    context.graphics = graphics;
    context.phase = "shadow";

    int fbo_index = 0;

    // Render shadow maps for each light (with cascades)
    for (size_t light_array_index = 0; light_array_index < shadow_lights.size(); ++light_array_index) {
        auto [light_index, light] = shadow_lights[light_array_index];
        int resolution = light->shadows.map_resolution;
        int cascade_count = std::max(1, std::min(4, light->shadows.cascade_count));
        float max_distance = light->shadows.max_distance;
        float split_lambda = light->shadows.split_lambda;

        // Compute cascade splits
        std::vector<float> splits = compute_cascade_splits(
            camera_near, max_distance, cascade_count, split_lambda
        );

        Vec3 light_dir = light->direction.normalized();

        // Render each cascade
        for (int c = 0; c < cascade_count; ++c) {
            float cascade_near = splits[c];
            float cascade_far = splits[c + 1];

            // Get/create FBO for this cascade
            FramebufferHandle* fbo = get_or_create_fbo(graphics, resolution, fbo_index);
            fbo_index++;

            if (!fbo) {
                tc::Log::error("ShadowPass: FBO is null for cascade %d", c);
                continue;
            }

            // Compute shadow camera params for this cascade
            ShadowCameraParams params = fit_shadow_frustum_for_cascade(
                camera_view, camera_projection, light_dir,
                cascade_near, cascade_far, resolution, caster_offset
            );
            Mat44f view_matrix = build_shadow_view_matrix(params);
            Mat44f proj_matrix = build_shadow_projection_matrix(params);
            Mat44f light_space_matrix = compute_light_space_matrix(params);

            // Handle empty draw calls case
            if (draw_calls.empty()) {
                graphics->bind_framebuffer(fbo);
                graphics->set_viewport(0, 0, resolution, resolution);
                graphics->clear_color_depth(1.0f, 1.0f, 1.0f, 1.0f);
                results.emplace_back(fbo, light_space_matrix, light_index, c, cascade_near, cascade_far);
                continue;
            }

            // Bind and clear FBO
            graphics->bind_framebuffer(fbo);
            graphics->set_viewport(0, 0, resolution, resolution);
            graphics->clear_color_depth(1.0f, 1.0f, 1.0f, 1.0f);
            graphics->apply_render_state(render_state);

            // Setup shader
            shadow_shader_program->use();
            shadow_shader_program->set_uniform_matrix4("u_view", view_matrix, false);
            shadow_shader_program->set_uniform_matrix4("u_projection", proj_matrix, false);

            context.view = view_matrix;
            context.projection = proj_matrix;
            context.current_shader = shadow_shader_program;

            // Render all shadow casters
            for (const auto& dc : draw_calls) {
                Mat44f model = get_model_matrix(dc.entity);
                context.model = model;

                // Get shader handle and apply override
                tc_shader_handle base_handle = shadow_shader_program->tc_shader().handle;
                tc_shader_handle shader_handle = tc_component_override_shader(
                    dc.component, "shadow", dc.geometry_id, base_handle
                );

                // Use TcShader
                TcShader shader_to_use(shader_handle);
                shader_to_use.use();

                // Apply uniforms via TcShader
                shader_to_use.set_uniform_mat4("u_model", model.data, false);
                shader_to_use.set_uniform_mat4("u_view", view_matrix.data, false);
                shader_to_use.set_uniform_mat4("u_projection", proj_matrix.data, false);

                context.current_shader = shadow_shader_program;  // Legacy
                context.current_tc_shader = shader_to_use;

                tc_component_draw_geometry(dc.component, &context, dc.geometry_id);
            }

            // Add result with cascade info
            results.emplace_back(fbo, light_space_matrix, light_index, c, cascade_near, cascade_far);
        }
    }

    // Reset state: stop shader, unbind framebuffer, reset GL state
    shadow_shader_program->stop();
    graphics->bind_framebuffer(nullptr);
    graphics->reset_gl_state();

    return results;
}


void ShadowPass::execute(
    GraphicsBackend* graphics,
    const FBOMap& reads_fbos,
    const FBOMap& writes_fbos,
    const Rect4i& rect,
    void* scene,
    void* camera,
    int64_t context_key,
    const std::vector<Light*>* lights
) {
    // Legacy execute - not used, call execute_shadow_pass instead
}

} // namespace termin
