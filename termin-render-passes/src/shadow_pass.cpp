#include "termin/render/shadow_pass.hpp"
#include <tgfx/tgfx_shader_handle.hpp>
#include <tcbase/tc_log.hpp>
#include "termin/camera/camera_component.hpp"

#include "tgfx2/builtin_shader_sources.hpp"
#include "termin/render/frame_graph_debugger_core.hpp"
#include "termin/render/frame_uniforms.hpp"
#include "termin/render/material_pipeline.hpp"
#include "termin/render/tgfx2_bridge.hpp"
#include "tgfx2/render_context.hpp"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/tc_shader_bridge.hpp"

extern "C" {
#include <tgfx/resources/tc_shader_registry.h>
#include "tc_profiler.h"
#include "core/tc_drawable_protocol.h"
#include "core/tc_scene_drawable.h"
#include "core/tc_scene_render_state.h"
}

#include <cmath>
#include <algorithm>
#include <array>
#include <cstdlib>
#include <cstring>
#include <set>
#include <span>

namespace termin {

constexpr const char* SHADOW_ENGINE_SHADER_UUID = "termin-engine-shadow";

namespace {

// PerFrame UBO (binding 0): view + projection. Uploaded ONCE per
// cascade, bound as a regular uniform buffer. 128 bytes, std140
// mat4-aligned.
struct ShadowPerFrameStd140 {
    float u_view[16];
    float u_projection[16];
};
static_assert(sizeof(ShadowPerFrameStd140) == 128,
              "ShadowPerFrameStd140 must be 2 * mat4");

// Draw-scope per-object model matrix. The shader resource layout maps it to
// the backend-specific storage, while this pass binds by resource name.
struct ShadowPushStd140 {
    float u_model[16];
};
static_assert(sizeof(ShadowPushStd140) == 64,
              "ShadowPushStd140 must be mat4");

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
    if (depth_pool_device_) {
        for (auto& [_, slot] : depth_pool_) {
            if (slot.tex) depth_pool_device_->destroy(slot.tex);
        }
    }
    depth_pool_.clear();
    depth_pool_device_ = nullptr;
    release_tgfx2_resources();
}

void ShadowPass::ensure_tgfx2_resources(tgfx::IRenderDevice& device) {
    device2_ = &device;

    // Register the engine's shadow VS/FS sources as a TcShader so the
    // global hash-based registry dedups them across pass re-creations.
    // When the editor toggles Play/Stop and the frame-graph rebuilds its
    // ShadowPass, `tc_shader_from_sources` returns the existing handle
    // (same source -> same hash -> same slot), and `tc_shader_ensure_tgfx2`
    // below finds cached VkShaderModules on the slot — no shaderc recompile.
    // Used to live as direct `device.create_shader()` calls owned by this
    // pass; every ShadowPass destruction destroyed the shader modules,
    // every construction re-ran shaderc (~35 ms × 19 engine shaders on
    // Play/Stop = ~700 ms lag).
    if (tc_shader_handle_is_invalid(shadow_shader_handle_)) {
        // Process-lifetime engine shader: never destroyed (transient
        // TcShader wrappers from material phases / Python bindings
        // can't bounce ref_count through zero and take it down).
        shadow_shader_handle_ = tgfx::register_builtin_shader_from_catalog(SHADOW_ENGINE_SHADER_UUID);
    }
}

void ShadowPass::release_tgfx2_resources() {
    if (!device2_) return;
    // shadow_shader_handle_ intentionally NOT released here. The +1 ref
    // we took in ensure_tgfx2_resources is an intentional process-
    // lifetime hold: engine shaders need to survive ShadowPass teardown
    // on Play/Stop (frame-graph rebuild) so the render-device shader
    // cache can reuse compiled modules instead of forcing shaderc to
    // recompile on the next pass creation.
    device2_ = nullptr;
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


tgfx::TextureHandle ShadowPass::get_or_create_depth_tex2(
    tgfx::IRenderDevice& device,
    int resolution,
    int index
) {
    if (depth_pool_device_ && depth_pool_device_ != &device) {
        // Device changed — throw the whole pool away.
        for (auto& [_, slot] : depth_pool_) {
            if (slot.tex) depth_pool_device_->destroy(slot.tex);
        }
        depth_pool_.clear();
        depth_pool_device_ = nullptr;
    }
    depth_pool_device_ = &device;

    auto it = depth_pool_.find(index);
    if (it != depth_pool_.end() && it->second.resolution == resolution) {
        return it->second.tex;
    }

    // Resolution changed or slot missing — recreate.
    if (it != depth_pool_.end()) {
        if (it->second.tex) device.destroy(it->second.tex);
        // Reusing backend-native texture storage for a new size invalidates
        // cached render targets keyed on the old attachment identity.
        device.invalidate_render_target_cache();
        depth_pool_.erase(it);
    }

    tgfx::TextureDesc desc;
    desc.width = static_cast<uint32_t>(resolution);
    desc.height = static_cast<uint32_t>(resolution);
    // D32F is universally supported as a depth attachment across GL/Vulkan
    // drivers. D24_UNorm maps to VK_FORMAT_X8_D24_UNORM_PACK32 on Vulkan,
    // which is an *optional* format — unsupported on AMD and some Intel
    // parts, and produces a silently broken VkImage on affected hardware
    // (no validation error, just garbage depth values in the shadow map).
    desc.format = tgfx::PixelFormat::D32F;
    desc.sample_count = 1;
    desc.usage = tgfx::TextureUsage::Sampled |
                 tgfx::TextureUsage::DepthStencilAttachment |
                 tgfx::TextureUsage::CopySrc;   // needed for Frame Debugger blit

    tgfx::TextureHandle tex = device.create_texture(desc);
    if (!tex) {
        tc::Log::error("ShadowPass: failed to create depth texture (res=%d)",
                       resolution);
        return {};
    }

    depth_pool_[index] = ShadowDepthSlot{tex, resolution};
    return tex;
}


namespace {

struct CollectShadowDrawCallsData {
    std::vector<ShadowDrawCall>* draw_calls;
    tc_shader_handle base_shader;
    MaterialPipelinePassContract pass_contract;
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

    Entity ent(tc->owner);

    auto* geometry_draws = static_cast<std::vector<GeometryDrawCall>*>(draws_ptr);
    for (const auto& gd : *geometry_draws) {
        tc_material_phase* phase = gd.resolve_phase();
        if (!phase) {
            continue;
        }
        // Get final shader with overrides (skinning, alpha-test, etc.)
        ShaderOverrideContext override_context;
        override_context.phase_mark = "shadow";
        override_context.geometry_id = gd.geometry_id;
        override_context.original_shader = TcShader(data->base_shader);
        override_context.pass_contract = data->pass_contract;
        tc_shader_handle final_shader =
            override_drawable_shader(tc, override_context).handle;
        ShadowDrawCall dc;
        dc.entity = ent;
        dc.component = tc;
        dc.phase = phase;
        dc.final_shader = final_shader;
        dc.geometry_id = gd.geometry_id;
        dc.material = gd.material;
        dc.phase_index = gd.phase_index;
        data->draw_calls->push_back(dc);
    }

    return true;
}

} // anonymous namespace

void ShadowPass::collect_shadow_casters(tc_scene_handle scene, uint64_t layer_mask) {
    cached_draw_calls_.clear();

    if (!tc_scene_handle_valid(scene)) {
        return;
    }

    CollectShadowDrawCallsData data;
    data.draw_calls = &cached_draw_calls_;
    // Use the UBO-based shadow shader as the base. Skinned variants are
    // assembled through the material pipeline vertex-variant helper and keep
    // the same draw/per-frame resource contract as the base path.
    data.base_shader = shadow_shader_handle_;
    data.pass_contract =
        material_pipeline_builtin_pass_contract(MaterialPipelinePassKind::Shadow);

    int filter_flags = TC_SCENE_FILTER_ENABLED
                     | TC_SCENE_FILTER_VISIBLE
                     | TC_SCENE_FILTER_ENTITY_ENABLED;
    tc_scene_foreach_drawable(scene, collect_shadow_drawable_draw_calls, &data, filter_flags, layer_mask);
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


// ----------------------------------------------------------------------------
// tgfx2 path — Stage 5.B.
// ----------------------------------------------------------------------------
//
// Draws shadow casters through RenderContext2. The pass owns tgfx2 depth
// textures, opens a depth-only render pass for each cascade, and draws
// mesh-backed drawables through the backend-neutral tc_mesh bridge.
// Drawables that cannot expose a tc_mesh* may still cast shadows through
// Drawable::draw_tgfx2(), using the pass' shadow shader contract.
std::vector<ShadowMapResult> ShadowPass::execute_shadow_pass_tgfx2(
    ExecuteContext& ctx,
    tc_scene_handle scene,
    const std::vector<Light>& lights,
    const Mat44f& camera_view,
    const Mat44f& camera_projection,
    float camera_near,
    float camera_far,
    uint64_t layer_mask
) {
    std::vector<ShadowMapResult> results;

    if (!ctx.ctx2) {
        tc::Log::error("ShadowPass/tgfx2: ctx2 is null");
        return results;
    }

    auto& device = ctx.ctx2->device();

    ensure_tgfx2_resources(device);

    if (tc_shader_handle_is_invalid(shadow_shader_handle_)) {
        tc::Log::error("ShadowPass/tgfx2: shadow_shader_handle_ not registered");
        return results;
    }

    // Find directional lights that cast shadows.
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

    collect_shadow_casters(scene, layer_mask);
    sort_draw_calls_by_shader();

    entity_names.clear();
    std::set<std::string> seen;
    for (const auto& dc : cached_draw_calls_) {
        const char* name = dc.entity.name();
        if (name && seen.find(name) == seen.end()) {
            seen.insert(name);
            entity_names.push_back(name);
        }
    }

    if (camera_near < 0.001f) {
        camera_near = 0.1f;
    }
    if (camera_far <= camera_near + 0.001f) {
        camera_far = camera_near + 100.0f;
    }

    int fbo_index = 0;
    for (auto [light_index, light] : shadow_lights) {
        int resolution = light->shadows.map_resolution;
        int cascade_count = std::max(1, std::min(4, light->shadows.cascade_count));
        float max_distance = std::min(light->shadows.max_distance, camera_far);
        if (max_distance <= camera_near + 0.001f) {
            max_distance = camera_far;
        }
        float split_lambda = light->shadows.split_lambda;
        float depth_bias_slope = static_cast<float>(light->shadows.normal_bias);

        std::vector<float> splits = compute_cascade_splits(
            camera_near, max_distance, cascade_count, split_lambda);

        Vec3 light_dir = light->direction.normalized();

        for (int c = 0; c < cascade_count; ++c) {
            float cascade_near = splits[c];
            float cascade_far = splits[c + 1];

            tgfx::TextureHandle depth_tex2 =
                get_or_create_depth_tex2(ctx.ctx2->device(), resolution, fbo_index);
            fbo_index++;
            if (!depth_tex2) {
                tc::Log::error("ShadowPass/tgfx2: depth tex is null for cascade %d", c);
                continue;
            }

            ShadowCameraParams params = fit_shadow_frustum_for_cascade(
                camera_view, camera_projection, camera_near, camera_far, light_dir,
                cascade_near, cascade_far, resolution, caster_offset
            );
            Mat44f view_matrix = build_shadow_view_matrix(params);
            Mat44f proj_matrix = build_shadow_projection_matrix(params);
            Mat44f light_space_matrix = compute_light_space_matrix(params);

            ctx.ctx2->begin_pass(
                tgfx::TextureHandle{},  // depth-only
                depth_tex2,
                nullptr,                 // no color clear
                1.0f,                    // clear depth to 1.0
                true                     // clear_depth_enabled
            );
            ctx.ctx2->set_viewport(0, 0, resolution, resolution);
            ctx.ctx2->set_depth_test(true);
            ctx.ctx2->set_depth_write(true);
            ctx.ctx2->set_blend(false);
            // Render back faces into the shadow map. For closed meshes this
            // avoids front-face self-shadow acne without moving caster geometry
            // in light space; receiver bias remains a pure compare-depth offset
            // in the shader shadow helper.
            ctx.ctx2->set_cull(tgfx::CullMode::Front);
            ctx.ctx2->set_depth_bias(depth_bias_slope != 0.0f,
                                     0.0f,
                                     depth_bias_slope,
                                     0.0f);

            auto restore_shadow_raster_state = [&]() {
                ctx.ctx2->set_depth_test(true);
                ctx.ctx2->set_depth_write(true);
                ctx.ctx2->set_blend(false);
                ctx.ctx2->set_cull(tgfx::CullMode::Front);
                ctx.ctx2->set_depth_bias(depth_bias_slope != 0.0f,
                                         0.0f,
                                         depth_bias_slope,
                                         0.0f);
            };

            auto end_shadow_pass = [&]() {
                ctx.ctx2->end_pass();
                ctx.ctx2->set_depth_bias(false);
            };

            // Fetch cached VkShaderModule handles from the tc_shader slot.
            // First call on a fresh device compiles via shaderc; every
            // subsequent ShadowPass lifetime hits the slot cache.
            MaterialPipelineShaderBinding shadow_shader{};
            if (!ensure_material_pipeline_shader(
                    *ctx.ctx2,
                    device,
                    shadow_shader_handle_,
                    "ShadowPass",
                    shadow_shader)) {
                end_shadow_pass();
                continue;
            }

            // PerFrame UBO through the ring: a fresh offset per cascade,
            // so the per-cascade matrices survive into draw-execute time
            // without a slot-per-cascade pool (the shared ring buffer and
            // dynamic descriptor offsets do what per_frame_ubo_pool_ used
            // to do on the per-UBO path).
            ShadowPerFrameStd140 per_frame{};
            std::memcpy(per_frame.u_view, view_matrix.data, sizeof(float) * 16);
            std::memcpy(per_frame.u_projection, proj_matrix.data, sizeof(float) * 16);
            std::array<MaterialPipelineUniformData, 1> per_frame_uniforms{{
                {"per_frame", &per_frame, static_cast<uint32_t>(sizeof(per_frame))},
            }};
            MaterialPipelineResourceContext shadow_resources{};
            shadow_resources.uniforms = per_frame_uniforms;
            prepare_material_pipeline_resources(
                *ctx.ctx2,
                device,
                shadow_shader.shader,
                nullptr,
                shadow_resources);

            if (cached_draw_calls_.empty()) {
                end_shadow_pass();
                results.emplace_back(depth_tex2, resolution, resolution,
                                     light_space_matrix, light_index,
                                     c, cascade_near, cascade_far);
                continue;
            }

            tc_shader_handle last_shader = tc_shader_handle_invalid();
            const std::string& debug_symbol = get_debug_internal_point();
            auto capture_debug_symbol = [&](const char* entity_name) {
                if (debug_symbol.empty() || !entity_name || debug_symbol != entity_name) {
                    return;
                }
                FrameGraphCapture* capture = debug_capture();
                if (!capture) {
                    return;
                }

                end_shadow_pass();
                capture->capture_direct_via_ctx2(
                    ctx.ctx2,
                    depth_tex2,
                    resolution,
                    resolution,
                    tgfx::PixelFormat::D32F);
                ctx.ctx2->begin_pass(
                    tgfx::TextureHandle{},
                    depth_tex2,
                    nullptr,
                    1.0f,
                    false);
                ctx.ctx2->set_viewport(0, 0, resolution, resolution);
                restore_shadow_raster_state();
                ctx.ctx2->bind_shader(shadow_shader.vertex, shadow_shader.fragment);
                ctx.ctx2->use_shader_resource_layout(shadow_shader.shader);
                prepare_material_pipeline_resources(
                    *ctx.ctx2,
                    device,
                    shadow_shader.shader,
                    nullptr,
                    shadow_resources);
            };

            for (const auto& dc : cached_draw_calls_) {
                tc_material_phase* phase = dc.resolve_phase();
                if (!phase) continue;

                Drawable* drawable = nullptr;
                if (tc_component_get_drawable_vtable(dc.component)
                    == &Drawable::cxx_drawable_vtable()) {
                    drawable = static_cast<Drawable*>(
                        tc_component_get_drawable_userdata(dc.component));
                }
                if (!drawable) continue;

                MeshDrawGeometry mesh_geometry{};
                if (!drawable->resolve_mesh_geometry("shadow", dc.geometry_id, mesh_geometry)) {
                    if (!drawable->supports_direct_tgfx2_draw(
                            "shadow", dc.geometry_id, DirectTgfx2DrawKind::MaterialPhase)) {
                        continue;
                    }

                    RenderContext direct_context;
                    direct_context.view = view_matrix;
                    direct_context.projection = proj_matrix;
                    direct_context.model = drawable->get_model_matrix(dc.entity);
                    direct_context.phase = "shadow";
                    direct_context.pass_contract =
                        material_pipeline_builtin_pass_contract(MaterialPipelinePassKind::Shadow);
                    direct_context.current_tc_shader = TcShader(dc.final_shader);
                    direct_context.layer_mask = layer_mask;
                    direct_context.camera_position = shadow_camera_position(params);
                    direct_context.viewport_width = resolution;
                    direct_context.viewport_height = resolution;

                    drawable->draw_tgfx2(
                        *ctx.ctx2, direct_context, "shadow", phase, dc.geometry_id);
                    capture_debug_symbol(dc.entity.name());
                    restore_shadow_raster_state();
                    ctx.ctx2->bind_shader(shadow_shader.vertex, shadow_shader.fragment);
                    ctx.ctx2->use_shader_resource_layout(shadow_shader.shader);
                    prepare_material_pipeline_resources(
                        *ctx.ctx2,
                        device,
                        shadow_shader.shader,
                        nullptr,
                        shadow_resources);
                    continue;
                }

                Mat44f model = drawable->get_model_matrix(dc.entity);

                bool override_is_base =
                    tc_shader_handle_eq(dc.final_shader, shadow_shader_handle_);

                // Both paths share the same draw-scope model matrix + PerFrame UBO
                // layout. Bias is applied receiver-side while sampling so the
                // caster's projected XY footprint stays stable.
                ShadowPushStd140 push{};
                std::memcpy(push.u_model, model.data, sizeof(float) * 16);
                std::array<MaterialPipelineUniformData, 2> draw_uniforms{{
                    {"per_frame", &per_frame, static_cast<uint32_t>(sizeof(per_frame))},
                    {"shadow_draw", &push, static_cast<uint32_t>(sizeof(push))},
                }};
                MaterialPipelineResourceContext draw_resources{};
                draw_resources.uniforms = draw_uniforms;

                if (override_is_base) {
                    prepare_material_pipeline_resources(
                        *ctx.ctx2,
                        device,
                        shadow_shader.shader,
                        nullptr,
                        draw_resources);
                    // Non-skinned fast path. Shadow VS only reads position.
                    draw_material_pipeline_submesh(
                        *ctx.ctx2,
                        mesh_geometry.mesh,
                        mesh_geometry.submesh_index,
                        material_mesh_vertex_input_for_shader(
                            shadow_shader.shader,
                            MaterialMeshVertexInput::Position));
                    capture_debug_symbol(dc.entity.name());
                } else {
                    // Skinning variant: bind the material-pipeline shader and
                    // let SkinnedMeshRenderer upload BoneBlock through the
                    // reflected draw-scope resource.
                    MaterialPipelineShaderBinding skinned_shader{};
                    if (!ensure_material_pipeline_shader(
                            *ctx.ctx2,
                            device,
                            dc.final_shader,
                            "ShadowPass/skinned",
                            skinned_shader)) {
                        continue;
                    }
                    prepare_material_pipeline_resources(
                        *ctx.ctx2,
                        device,
                        skinned_shader.shader,
                        nullptr,
                        draw_resources);

                    drawable->upload_per_draw_uniforms_tgfx2(*ctx.ctx2, dc.geometry_id);

                    draw_material_pipeline_submesh(
                        *ctx.ctx2,
                        mesh_geometry.mesh,
                        mesh_geometry.submesh_index,
                        material_mesh_vertex_input_for_shader(
                            skinned_shader.shader,
                            MaterialMeshVertexInput::Position));
                    capture_debug_symbol(dc.entity.name());

                    // Next mesh-backed draw must re-bind the base shadow
                    // shader; the variant left its own program bound.
                    last_shader = dc.final_shader;
                    ctx.ctx2->bind_shader(shadow_shader.vertex, shadow_shader.fragment);
                    ctx.ctx2->use_shader_resource_layout(shadow_shader.shader);
                    prepare_material_pipeline_resources(
                        *ctx.ctx2,
                        device,
                        shadow_shader.shader,
                        nullptr,
                        shadow_resources);
                }
            }
            (void)last_shader;

            end_shadow_pass();

            results.emplace_back(depth_tex2, resolution, resolution,
                                 light_space_matrix, light_index,
                                 c, cascade_near, cascade_far);
        }
    }

    return results;
}

void ShadowPass::execute(ExecuteContext& ctx) {
    bool profile = tc_profiler_enabled();
    if (profile) tc_profiler_begin_section("ShadowPass");

    auto it = ctx.shadow_arrays.find(output_res);
    if (it == ctx.shadow_arrays.end() || it->second == nullptr) {
        if (profile) tc_profiler_end_section();
        return;
    }
    ShadowMapArrayResource* shadow_array = it->second;

    // Clear previous frame's entries
    shadow_array->clear();

    if (ctx.lights.empty()) {
        if (profile) tc_profiler_end_section();
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
    float camera_near = static_cast<float>(ctx.camera->near_clip);
    float camera_far = static_cast<float>(ctx.camera->far_clip);

    if (!ctx.ctx2) {
        tc::Log::error("[ShadowPass] ctx.ctx2 is null — ShadowPass is tgfx2-only");
        if (profile) tc_profiler_end_section();
        return;
    }

    std::vector<ShadowMapResult> results = execute_shadow_pass_tgfx2(
        ctx,
        ctx.scene.handle(),
        ctx.lights,
        camera_view,
        camera_projection,
        camera_near,
        camera_far,
        ctx.layer_mask
    );

    // Add results to shadow array
    for (const auto& result : results) {
        shadow_array->add_entry(
            result.depth_tex2,
            result.width,
            result.height,
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
