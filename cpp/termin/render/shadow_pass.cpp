#include "shadow_pass.hpp"
#include "tc_shader_handle.hpp"
#include "tc_log.hpp"
#include "termin/camera/camera_component.hpp"

extern "C" {
#include "tc_shader_registry.h"
#include "tc_profiler.h"
}

#include <cmath>
#include <algorithm>
#include <set>

namespace termin {

namespace {

// Get model matrix from Entity as Mat44f
// world_matrix outputs column-major, same as Mat44f
Mat44f get_model_matrix(const Entity& entity) {
    double m[16];
    entity.transform().world_matrix(m);

    Mat44f result;
    for (int i = 0; i < 16; ++i) {
        result.data[i] = static_cast<float>(m[i]);
    }
    return result;
}

} // anonymous namespace


ShadowPass::ShadowPass(
    const std::string& output_res,
    const std::string& pass_name,
    float caster_offset
) : output_res(output_res),
    caster_offset(caster_offset)
{
    set_pass_name(pass_name);
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
    tc_shader_handle base_shader;
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
        // Get final shader with overrides (skinning, alpha-test, etc.)
        tc_shader_handle final_shader = tc_component_override_shader(
            tc, "shadow", gd.geometry_id, data->base_shader
        );
        data->draw_calls->push_back(ShadowDrawCall{ent, tc, final_shader, gd.geometry_id});
    }

    return true;
}

} // anonymous namespace

void ShadowPass::collect_shadow_casters(tc_scene_handle scene) {
    cached_draw_calls_.clear();

    if (!tc_scene_handle_valid(scene)) {
        return;
    }

    CollectShadowDrawCallsData data;
    data.draw_calls = &cached_draw_calls_;
    data.base_shader = shadow_shader ? shadow_shader->handle : tc_shader_handle_invalid();

    int filter_flags = TC_DRAWABLE_FILTER_ENABLED
                     | TC_DRAWABLE_FILTER_VISIBLE
                     | TC_DRAWABLE_FILTER_ENTITY_ENABLED;
    tc_scene_foreach_drawable(scene, collect_shadow_drawable_draw_calls, &data, filter_flags, 0);
}

void ShadowPass::sort_draw_calls_by_shader() {
    if (cached_draw_calls_.size() <= 1) return;

    std::sort(cached_draw_calls_.begin(), cached_draw_calls_.end(),
        [](const ShadowDrawCall& a, const ShadowDrawCall& b) {
            return a.final_shader.index < b.final_shader.index;
        });
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
    tc_scene_handle scene,
    const std::vector<Light>& lights,
    const Mat44f& camera_view,
    const Mat44f& camera_projection
) {
    std::vector<ShadowMapResult> results;

    if (!graphics) {
        tc::Log::error("ShadowPass: graphics is null");
        return results;
    }

    // Check shader is set from Python
    if (!shadow_shader) {
        tc::Log::error("ShadowPass: shadow_shader not set");
        return results;
    }

    bool detailed = tc_profiler_detailed_rendering();

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
    if (detailed) tc_profiler_begin_section("CollectCasters");
    collect_shadow_casters(scene);
    if (detailed) tc_profiler_end_section();

    // Sort by shader to minimize state changes
    if (detailed) tc_profiler_begin_section("Sort");
    sort_draw_calls_by_shader();
    if (detailed) tc_profiler_end_section();

    // Update entity names cache
    entity_names.clear();
    std::set<std::string> seen;
    for (const auto& dc : cached_draw_calls_) {
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
            if (detailed) tc_profiler_begin_section(("Cascade" + std::to_string(c)).c_str());

            float cascade_near = splits[c];
            float cascade_far = splits[c + 1];

            // Get/create FBO for this cascade
            FramebufferHandle* fbo = get_or_create_fbo(graphics, resolution, fbo_index);
            fbo_index++;

            if (!fbo) {
                tc::Log::error("ShadowPass: FBO is null for cascade %d", c);
                if (detailed) tc_profiler_end_section();
                continue;
            }

            // Compute shadow camera params for this cascade
            if (detailed) tc_profiler_begin_section("FrustumFit");
            ShadowCameraParams params = fit_shadow_frustum_for_cascade(
                camera_view, camera_projection, light_dir,
                cascade_near, cascade_far, resolution, caster_offset
            );
            Mat44f view_matrix = build_shadow_view_matrix(params);
            Mat44f proj_matrix = build_shadow_projection_matrix(params);
            Mat44f light_space_matrix = compute_light_space_matrix(params);
            if (detailed) tc_profiler_end_section();

            // Handle empty draw calls case
            if (cached_draw_calls_.empty()) {
                graphics->bind_framebuffer(fbo);
                graphics->set_viewport(0, 0, resolution, resolution);
                graphics->clear_color_depth(1.0f, 1.0f, 1.0f, 1.0f);
                results.emplace_back(fbo, light_space_matrix, light_index, c, cascade_near, cascade_far);
                if (detailed) tc_profiler_end_section();
                continue;
            }

            // Bind and clear FBO
            if (detailed) tc_profiler_begin_section("Setup");
            graphics->bind_framebuffer(fbo);
            graphics->set_viewport(0, 0, resolution, resolution);
            graphics->clear_color_depth(1.0f, 1.0f, 1.0f, 1.0f);
            graphics->apply_render_state(render_state);

            context.view = view_matrix;
            context.projection = proj_matrix;
            if (detailed) tc_profiler_end_section();

            // Render all shadow casters with shader caching
            if (detailed) tc_profiler_begin_section("DrawCalls");
            tc_shader_handle last_shader = tc_shader_handle_invalid();

            for (const auto& dc : cached_draw_calls_) {
                Mat44f model = get_model_matrix(dc.entity);
                context.model = model;

                // Use final shader (override already applied during collect)
                tc_shader_handle shader_handle = dc.final_shader;
                bool shader_changed = !tc_shader_handle_eq(shader_handle, last_shader);

                if (shader_changed) {
                    TcShader shader_to_use(shader_handle);
                    shader_to_use.use();
                    // View/projection only need to be set once per shader change
                    shader_to_use.set_uniform_mat4("u_view", view_matrix.data, false);
                    shader_to_use.set_uniform_mat4("u_projection", proj_matrix.data, false);
                    context.current_tc_shader = shader_to_use;
                    last_shader = shader_handle;
                }

                // Model matrix changes per object
                context.current_tc_shader.set_uniform_mat4("u_model", model.data, false);

                tc_component_draw_geometry(dc.component, &context, dc.geometry_id);
            }
            if (detailed) tc_profiler_end_section();

            // Add result with cascade info
            results.emplace_back(fbo, light_space_matrix, light_index, c, cascade_near, cascade_far);

            if (detailed) tc_profiler_end_section();
        }
    }

    // Reset state: unbind framebuffer, reset GL state
    graphics->bind_framebuffer(nullptr);
    graphics->reset_gl_state();

    return results;
}


void ShadowPass::execute(ExecuteContext& ctx) {
    bool profile = tc_profiler_enabled();
    if (profile) tc_profiler_begin_section("ShadowPass");

    // Get shadow array from writes_fbos
    auto it = ctx.writes_fbos.find(output_res);
    if (it == ctx.writes_fbos.end() || it->second == nullptr) {
        if (profile) tc_profiler_end_section();
        return;
    }

    // Dynamic cast to ShadowMapArrayResource
    ShadowMapArrayResource* shadow_array = dynamic_cast<ShadowMapArrayResource*>(it->second);
    if (!shadow_array) {
        tc::Log::error("ShadowPass: writes_fbos[%s] is not a ShadowMapArrayResource", output_res.c_str());
        if (profile) tc_profiler_end_section();
        return;
    }

    // Clear previous frame's entries
    shadow_array->clear();

    if (ctx.lights.empty()) {
        if (profile) tc_profiler_end_section();
        return;
    }

    // Get shadow shader from registry if not set
    if (!shadow_shader) {
        tc_shader_handle h = tc_shader_find_by_name("system:shadow");
        if (!tc_shader_is_valid(h)) {
            // Create shadow shader if it doesn't exist
            static const char* shadow_vert = R"(
#version 330 core
layout(location = 0) in vec3 a_position;
uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;
void main() {
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
)";
            static const char* shadow_frag = R"(
#version 330 core
void main() {
    // Depth-only pass
}
)";
            h = tc_shader_from_sources(shadow_vert, shadow_frag, nullptr, "system:shadow", nullptr, nullptr);
        }
        if (tc_shader_is_valid(h)) {
            static TcShader cached_shader;
            cached_shader = TcShader(h);
            cached_shader.ensure_ready();
            shadow_shader = &cached_shader;
        }
    }

    if (!shadow_shader) {
        tc::Log::error("ShadowPass: failed to create shadow shader");
        return;
    }

    if (!ctx.camera) {
        tc::Log::error("ShadowPass: camera is null");
        return;
    }

    // Get camera matrices
    Mat44 view_d = ctx.camera->get_view_matrix();
    Mat44 proj_d = ctx.camera->get_projection_matrix();
    Mat44f camera_view = view_d.to_float();
    Mat44f camera_projection = proj_d.to_float();

    // Execute shadow pass
    std::vector<ShadowMapResult> results = execute_shadow_pass(
        ctx.graphics,
        ctx.scene.handle(),
        ctx.lights,
        camera_view,
        camera_projection
    );

    // Add results to shadow array
    for (const auto& result : results) {
        shadow_array->add_entry(
            result.fbo,
            result.light_space_matrix,
            result.light_index,
            result.cascade_index,
            result.cascade_split_near,
            result.cascade_split_far
        );
    }

    if (profile) tc_profiler_end_section();
}

// Register ShadowPass in tc_pass_registry for C#/standalone C++ usage
TC_REGISTER_FRAME_PASS(ShadowPass);

} // namespace termin
