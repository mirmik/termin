#include "shadow_pass.hpp"
#include <tgfx/tgfx_shader_handle.hpp>
#include <tcbase/tc_log.hpp>
#include "termin/camera/camera_component.hpp"

#include "termin/render/tgfx2_bridge.hpp"
#include "tgfx2/render_context.hpp"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/opengl/opengl_render_device.hpp"
#include "tgfx2/tc_shader_bridge.hpp"

extern "C" {
#include <tgfx/resources/tc_shader_registry.h>
#include "tc_profiler.h"
#include "core/tc_drawable_protocol.h"
#include "core/tc_scene_drawable.h"
}

#include <cmath>
#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <set>
#include <span>

namespace termin {

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

// PushConstants (binding 14, slot TGFX2_PUSH_CONSTANTS_BINDING): the
// per-object model matrix. Written per-draw via
// RenderContext2::set_push_constants. 64 bytes, well under the
// TGFX2_PUSH_CONSTANTS_MAX_BYTES (128 byte) Vulkan-compat cap.
struct ShadowPushStd140 {
    float u_model[16];
};
static_assert(sizeof(ShadowPushStd140) == 64,
              "ShadowPushStd140 must be exactly one mat4");

// Per-frame view+proj on binding 0 (UBO set from ctx2 per cascade).
// Per-object model matrix rides push_constants on Vulkan / std140 UBO at
// slot 14 on GL (tgfx2's emulation ring). Same `ShadowPushData` struct
// on both sides, so the CPU packer doesn't need to fork.
constexpr const char* SHADOW_VS_UBO = R"(#version 450 core
layout(location = 0) in vec3 a_position;

layout(std140, binding = 0) uniform PerFrame {
    mat4 u_view;
    mat4 u_projection;
};

struct ShadowPushData {
    mat4 u_model;
};
#ifdef VULKAN
layout(push_constant) uniform ShadowPushBlock { ShadowPushData pc; };
#else
layout(std140, binding = 14) uniform ShadowPushBlock { ShadowPushData pc; };
#endif

void main() {
    gl_Position = u_projection * u_view * pc.u_model * vec4(a_position, 1.0);
}
)";

constexpr const char* SHADOW_FS_UBO = R"(#version 450 core
void main() {
    // Depth-only pass: fragment shader output is irrelevant because
    // the FBO has no color attachment.
}
)";

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
        shadow_shader_handle_ = tc_shader_from_sources(
            SHADOW_VS_UBO, SHADOW_FS_UBO,
            /*geometry=*/nullptr,
            /*name=*/"ShadowEngineVSFS",
            /*source_path=*/nullptr,
            /*uuid=*/nullptr);
    }
}

tgfx::BufferHandle ShadowPass::get_or_create_per_frame_ubo(
    tgfx::IRenderDevice& device,
    int index
) {
    auto it = per_frame_ubo_pool_.find(index);
    if (it != per_frame_ubo_pool_.end()) return it->second;

    tgfx::BufferDesc ubo_desc;
    ubo_desc.size = sizeof(ShadowPerFrameStd140);
    ubo_desc.usage = tgfx::BufferUsage::Uniform | tgfx::BufferUsage::CopyDst;
    tgfx::BufferHandle ubo = device.create_buffer(ubo_desc);
    per_frame_ubo_pool_[index] = ubo;
    return ubo;
}

void ShadowPass::release_tgfx2_resources() {
    if (!device2_) return;
    // shadow_shader_handle_ is intentionally NOT destroyed here — it lives
    // in the global tc_shader registry and is shared across pass
    // re-creations. Its tgfx2 shader handles get torn down automatically
    // when the device is released (see tc_gpu_slot teardown).
    for (auto& [_, ubo] : per_frame_ubo_pool_) {
        if (ubo) device2_->destroy(ubo);
    }
    per_frame_ubo_pool_.clear();
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
        // Reusing the same gl_id for a new texture of a different
        // size invalidates any FBO the device cached on the old id.
        if (auto* gl_dev =
                dynamic_cast<tgfx::OpenGLRenderDevice*>(&device)) {
            gl_dev->invalidate_fbo_cache();
        }
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

    // Configure the GL texture object for hardware shadow sampling:
    // CLAMP_TO_BORDER with white border (outside-frustum = not in shadow),
    // and REF_TO_TEXTURE compare mode so sampler2DShadow / textureShadow
    // in the fragment shader does PCF. These parameters are intrinsic to
    // the texture rather than the sampler, so setting them here is the
    // right place. Legacy OpenGLShadowFramebufferHandle::create() does
    // the equivalent setup.
    if (auto* gl_dev = dynamic_cast<tgfx::OpenGLRenderDevice*>(&device)) {
        auto* gl_tex = gl_dev->get_texture(tex);
        if (gl_tex) {
            glBindTexture(gl_tex->target, gl_tex->gl_id);
            glTexParameteri(gl_tex->target, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_BORDER);
            glTexParameteri(gl_tex->target, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_BORDER);
            float border[] = {1.0f, 1.0f, 1.0f, 1.0f};
            glTexParameterfv(gl_tex->target, GL_TEXTURE_BORDER_COLOR, border);
            glTexParameteri(gl_tex->target, GL_TEXTURE_COMPARE_MODE, GL_COMPARE_REF_TO_TEXTURE);
            glTexParameteri(gl_tex->target, GL_TEXTURE_COMPARE_FUNC, GL_LEQUAL);
            glBindTexture(gl_tex->target, 0);
        }
    }

    depth_pool_[index] = ShadowDepthSlot{tex, resolution};
    return tex;
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

    Entity ent(tc->owner);

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

void ShadowPass::collect_shadow_casters(tc_scene_handle scene, uint64_t layer_mask) {
    cached_draw_calls_.clear();

    if (!tc_scene_handle_valid(scene)) {
        return;
    }

    CollectShadowDrawCallsData data;
    data.draw_calls = &cached_draw_calls_;
    data.base_shader = shadow_shader ? shadow_shader->handle : tc_shader_handle_invalid();

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
// Draws shadow casters through RenderContext2. The shadow FBO itself is
// still allocated via the legacy FBOPool; its depth texture is wrapped as
// a non-owning tgfx2 handle per frame, the pass opens a depth-only render
// pass on it, and each drawable is drawn via ctx.ctx2->draw(vbo, ibo, ...)
// with per-draw UBO updates. Drawables that can't expose a tc_mesh* (i.e.
// SkinnedMeshRenderer and friends) fall back to the legacy draw_geometry
// call inside the same FBO — the OpenGL backend of ctx2 has already bound
// the same GL FBO via its fbo_cache_ so legacy glDraw calls land in the
// right place.
std::vector<ShadowMapResult> ShadowPass::execute_shadow_pass_tgfx2(
    ExecuteContext& ctx,
    tc_scene_handle scene,
    const std::vector<Light>& lights,
    const Mat44f& camera_view,
    const Mat44f& camera_projection,
    uint64_t layer_mask
) {
    std::vector<ShadowMapResult> results;

    if (!ctx.ctx2) {
        tc::Log::error("ShadowPass/tgfx2: ctx2 is null");
        return results;
    }
    if (!shadow_shader) {
        tc::Log::error("ShadowPass/tgfx2: shadow_shader not set");
        return results;
    }

    auto& device = ctx.ctx2->device();

    ensure_tgfx2_resources(device);

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

    // Extract camera near plane (same logic as legacy path).
    float camera_near = 0.1f;
    float proj_23 = camera_projection(2, 3);
    float proj_21 = camera_projection(2, 1);
    if (std::abs(proj_21 - 1.0f) > 0.001f && std::abs(proj_23) > 0.001f) {
        camera_near = -proj_23 / (proj_21 + 1.0f);
        if (camera_near < 0.01f) camera_near = 0.1f;
    }

    int fbo_index = 0;

    for (auto [light_index, light] : shadow_lights) {
        int resolution = light->shadows.map_resolution;
        int cascade_count = std::max(1, std::min(4, light->shadows.cascade_count));
        float max_distance = light->shadows.max_distance;
        float split_lambda = light->shadows.split_lambda;

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
                camera_view, camera_projection, light_dir,
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
            ctx.ctx2->set_cull(tgfx::CullMode::Back);

            // Fetch cached VkShaderModule handles from the tc_shader slot.
            // First call on a fresh device compiles via shaderc; every
            // subsequent ShadowPass lifetime hits the slot cache.
            tgfx::ShaderHandle shadow_vs2, shadow_fs2;
            {
                tc_shader* raw = tc_shader_get(shadow_shader_handle_);
                if (!raw || !tc_shader_ensure_tgfx2(raw, &device, &shadow_vs2, &shadow_fs2)) {
                    tc::Log::error("ShadowPass: tc_shader_ensure_tgfx2 failed for engine shadow shader");
                    ctx.ctx2->end_pass();
                    continue;
                }
            }
            ctx.ctx2->bind_shader(shadow_vs2, shadow_fs2);

            // PerFrame UBO (view + projection). Each cascade gets its
            // own UBO slot (per_frame_ubo_pool_, keyed by fbo_index) so
            // Vulkan's deferred command buffer sees the right data at
            // draw-execute time. A single shared UBO would be overwritten
            // between cascades during recording and all cascades' draws
            // would end up reading the final cascade's matrices — see
            // the extended note in shadow_pass.hpp. The depth pool uses
            // the same `fbo_index` keying so slot lifetimes match.
            tgfx::BufferHandle per_frame_ubo =
                get_or_create_per_frame_ubo(ctx.ctx2->device(), fbo_index - 1);
            ShadowPerFrameStd140 per_frame{};
            std::memcpy(per_frame.u_view, view_matrix.data, sizeof(float) * 16);
            std::memcpy(per_frame.u_projection, proj_matrix.data, sizeof(float) * 16);
            ctx.ctx2->device().upload_buffer(
                per_frame_ubo,
                std::span<const uint8_t>(
                    reinterpret_cast<const uint8_t*>(&per_frame),
                    sizeof(per_frame)));
            ctx.ctx2->bind_uniform_buffer(0, per_frame_ubo);

            if (cached_draw_calls_.empty()) {
                ctx.ctx2->end_pass();
                results.emplace_back(depth_tex2, resolution, resolution,
                                     light_space_matrix, light_index,
                                     c, cascade_near, cascade_far);
                continue;
            }

            tc_shader_handle last_shader = tc_shader_handle_invalid();

            for (const auto& dc : cached_draw_calls_) {
                Drawable* drawable = nullptr;
                if (tc_component_get_drawable_vtable(dc.component)
                    == &Drawable::cxx_drawable_vtable()) {
                    drawable = static_cast<Drawable*>(
                        tc_component_get_drawable_userdata(dc.component));
                }
                if (!drawable) continue;

                tc_mesh* mesh = drawable->get_mesh_for_phase("shadow", dc.geometry_id);
                if (!mesh) continue;  // non-mesh drawables don't cast shadows

                Mat44f model = drawable->get_model_matrix(dc.entity);

                bool override_is_base = tc_shader_handle_eq(
                    dc.final_shader,
                    shadow_shader ? shadow_shader->handle : tc_shader_handle_invalid());

                Tgfx2MeshBinding bind = wrap_mesh_as_tgfx2(device, mesh);
                if (bind.index_count == 0) continue;

                if (override_is_base) {
                    // Fast path: push constants for u_model.
                    ShadowPushStd140 push{};
                    std::memcpy(push.u_model, model.data, sizeof(float) * 16);
                    ctx.ctx2->set_push_constants(&push, sizeof(push));

                    // Shadow VS only reads `a_position`. Filter unused
                    // attrs so Vulkan doesn't warn about loc 1/2/3 per
                    // pipeline creation. See filter_vertex_layout_to_locations.
                    ctx.ctx2->set_vertex_layout(
                        filter_vertex_layout_to_locations(bind.layout, {0}));
                    ctx.ctx2->set_topology(bind.topology);
                    ctx.ctx2->draw(bind.vertex_buffer, bind.index_buffer,
                                   bind.index_count, bind.index_type);
                } else {
                    // Skinning variant (override shader): compile via
                    // bridge, bind, upload bone matrices + legacy
                    // u_model/u_view/u_projection via ctx2's
                    // transitional plain-uniform helpers, draw.
                    tc_shader* raw = tc_shader_get(dc.final_shader);
                    if (!raw) {
                        release_mesh_binding(device, bind);
                        continue;
                    }
                    tgfx::ShaderHandle vs2, fs2;
                    if (!tc_shader_ensure_tgfx2(raw, &device, &vs2, &fs2)) {
                        release_mesh_binding(device, bind);
                        continue;
                    }
                    ctx.ctx2->bind_shader(vs2, fs2);
                    ctx.ctx2->set_vertex_layout(bind.layout);
                    ctx.ctx2->set_topology(bind.topology);

                    ctx.ctx2->set_uniform_mat4("u_model",      model.data,        false);
                    ctx.ctx2->set_uniform_mat4("u_view",       view_matrix.data,  false);
                    ctx.ctx2->set_uniform_mat4("u_projection", proj_matrix.data,  false);

                    // Per-draw uniforms (bone matrices for SkinnedMeshRenderer).
                    drawable->upload_per_draw_uniforms_tgfx2(*ctx.ctx2, dc.geometry_id);

                    ctx.ctx2->draw(bind.vertex_buffer, bind.index_buffer,
                                   bind.index_count, bind.index_type);

                    // Next mesh-backed draw must re-bind the base shadow
                    // shader; skinning variant left its own program bound.
                    last_shader = dc.final_shader;
                    ctx.ctx2->bind_shader(shadow_vs2, shadow_fs2);
                }

                release_mesh_binding(device, bind);
            }
            (void)last_shader;

            ctx.ctx2->end_pass();

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
            // tgfx2 path compiles lazily via tc_shader_ensure_tgfx2 in
            // the inner draw loop — no legacy GL compile needed here.
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
