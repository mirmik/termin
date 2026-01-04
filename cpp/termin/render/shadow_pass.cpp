#include "shadow_pass.hpp"
#include "shader_program.hpp"
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
    int default_resolution,
    float max_shadow_distance,
    float ortho_size,
    float near,
    float far,
    float caster_offset
) : RenderFramePass(pass_name, {}, {output_res}),
    output_res(output_res),
    default_resolution(default_resolution),
    max_shadow_distance(max_shadow_distance),
    ortho_size(ortho_size),
    near(near),
    far(far),
    caster_offset(caster_offset)
{
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


std::vector<ShadowDrawCall> ShadowPass::collect_shadow_casters(
    const std::vector<Entity>& entities
) {
    std::vector<ShadowDrawCall> draw_calls;

    for (size_t ei = 0; ei < entities.size(); ++ei) {
        const Entity& ent = entities[ei];
        if (!ent.active() || !ent.visible()) {
            continue;
        }

        size_t comp_count = ent.component_count();
        for (size_t ci = 0; ci < comp_count; ci++) {
            tc_component* tc = ent.component_at(ci);
            if (!tc || !tc->enabled) {
                continue;
            }

            // Check if component is drawable
            if (!tc_component_is_drawable(tc)) {
                continue;
            }

            // Filter by "shadow" phase
            if (!tc_component_has_phase(tc, "shadow")) {
                continue;
            }

            // Get geometry draws
            void* draws_ptr = tc_component_get_geometry_draws(tc, "shadow");
            if (!draws_ptr) {
                continue;
            }

            auto* geometry_draws = static_cast<std::vector<GeometryDrawCall>*>(draws_ptr);
            for (const auto& gd : *geometry_draws) {
                draw_calls.push_back(ShadowDrawCall{
                    &ent,
                    tc,
                    gd.geometry_id
                });
            }
        }
    }

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
    const std::vector<Entity>& entities,
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
    std::vector<ShadowDrawCall> draw_calls = collect_shadow_casters(entities);

    // Update entity names cache
    entity_names.clear();
    std::set<std::string> seen;
    for (const auto& dc : draw_calls) {
        if (!dc.entity) {
            continue;
        }
        const char* name = dc.entity->name();
        if (name && seen.find(name) == seen.end()) {
            seen.insert(name);
            entity_names.push_back(name);
        }
    }

    if (draw_calls.empty()) {
        // No shadow casters, return empty FBOs
        for (size_t i = 0; i < shadow_lights.size(); ++i) {
            auto [light_index, light] = shadow_lights[i];
            int resolution = light->shadows.map_resolution;
            FramebufferHandle* fbo = get_or_create_fbo(graphics, resolution, static_cast<int>(i));

            // Clear to white (max depth)
            if (fbo) {
                graphics->bind_framebuffer(fbo);
                graphics->set_viewport(0, 0, resolution, resolution);
                graphics->clear_color_depth(1.0f, 1.0f, 1.0f, 1.0f);
            }

            ShadowCameraParams params = build_shadow_params(*light, camera_view, camera_projection);
            Mat44f light_space_matrix = compute_light_space_matrix(params);
            results.emplace_back(fbo, light_space_matrix, light_index);
        }
        graphics->bind_framebuffer(nullptr);
        graphics->reset_gl_state();
        return results;
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

    // Render shadow map for each light
    for (size_t array_index = 0; array_index < shadow_lights.size(); ++array_index) {
        auto [light_index, light] = shadow_lights[array_index];
        int resolution = light->shadows.map_resolution;

        // Get/create FBO
        FramebufferHandle* fbo = get_or_create_fbo(graphics, resolution, static_cast<int>(array_index));
        if (!fbo) {
            tc::Log::error("ShadowPass: FBO is null");
            continue;
        }

        // Compute shadow camera params
        ShadowCameraParams params = build_shadow_params(*light, camera_view, camera_projection);
        Mat44f view_matrix = build_shadow_view_matrix(params);
        Mat44f proj_matrix = build_shadow_projection_matrix(params);
        Mat44f light_space_matrix = compute_light_space_matrix(params);

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
            // Re-bind shader (draw_geometry may have switched to skinned variant)
            shadow_shader_program->use();

            Mat44f model = get_model_matrix(*dc.entity);
            shadow_shader_program->set_uniform_matrix4("u_model", model, false);
            context.model = model;

            tc_component_draw_geometry(dc.component, &context, dc.geometry_id.c_str());
        }

        // Add result
        results.emplace_back(fbo, light_space_matrix, light_index);
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
