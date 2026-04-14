#include "shadow_pass.hpp"
#include <tgfx/tgfx_shader_handle.hpp>
#include <tcbase/tc_log.hpp>
#include "termin/camera/camera_component.hpp"

#include "termin/render/tgfx2_bridge.hpp"
#include "tgfx2/render_context.hpp"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/opengl/opengl_render_device.hpp"

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

constexpr const char* SHADOW_VS_UBO = R"(
#version 330 core
#extension GL_ARB_shading_language_420pack : require

layout(location = 0) in vec3 a_position;

layout(std140, binding = 0) uniform PerFrame {
    mat4 u_view;
    mat4 u_projection;
};

layout(std140, binding = 14) uniform PushConstants {
    mat4 u_model;
};

void main() {
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
)";

constexpr const char* SHADOW_FS_UBO = R"(
#version 330 core
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
    fbo_pool_.clear();
    release_tgfx2_resources();
}

void ShadowPass::ensure_tgfx2_resources(tgfx2::IRenderDevice& device) {
    if (device2_ == &device && shadow_vs2_ && shadow_fs2_ && per_frame_ubo_) {
        return;
    }
    if (device2_ && device2_ != &device) {
        // Device changed under us — tear down old handles. This should
        // never happen in production, but makes pass hot-reload safe.
        release_tgfx2_resources();
    }
    device2_ = &device;

    tgfx2::ShaderDesc vs_desc;
    vs_desc.stage = tgfx2::ShaderStage::Vertex;
    vs_desc.source = SHADOW_VS_UBO;
    shadow_vs2_ = device.create_shader(vs_desc);

    tgfx2::ShaderDesc fs_desc;
    fs_desc.stage = tgfx2::ShaderStage::Fragment;
    fs_desc.source = SHADOW_FS_UBO;
    shadow_fs2_ = device.create_shader(fs_desc);

    tgfx2::BufferDesc ubo_desc;
    ubo_desc.size = sizeof(ShadowPerFrameStd140);
    ubo_desc.usage = tgfx2::BufferUsage::Uniform | tgfx2::BufferUsage::CopyDst;
    per_frame_ubo_ = device.create_buffer(ubo_desc);
}

void ShadowPass::release_tgfx2_resources() {
    if (!device2_) return;
    if (shadow_vs2_) { device2_->destroy(shadow_vs2_); shadow_vs2_ = {}; }
    if (shadow_fs2_) { device2_->destroy(shadow_fs2_); shadow_fs2_ = {}; }
    if (per_frame_ubo_) { device2_->destroy(per_frame_ubo_); per_frame_ubo_ = {}; }
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

    if (!ctx.ctx2 || !ctx.graphics) {
        tc::Log::error("ShadowPass/tgfx2: ctx2 or graphics is null");
        return results;
    }
    if (!shadow_shader) {
        tc::Log::error("ShadowPass/tgfx2: shadow_shader not set");
        return results;
    }

    auto* gl_dev = dynamic_cast<tgfx2::OpenGLRenderDevice*>(&ctx.ctx2->device());
    if (!gl_dev) {
        tc::Log::error("ShadowPass/tgfx2: device is not OpenGLRenderDevice");
        return results;
    }

    ensure_tgfx2_resources(ctx.ctx2->device());

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

            FramebufferHandle* fbo = get_or_create_fbo(ctx.graphics, resolution, fbo_index);
            fbo_index++;
            if (!fbo) {
                tc::Log::error("ShadowPass/tgfx2: FBO is null for cascade %d", c);
                continue;
            }

            ShadowCameraParams params = fit_shadow_frustum_for_cascade(
                camera_view, camera_projection, light_dir,
                cascade_near, cascade_far, resolution, caster_offset
            );
            Mat44f view_matrix = build_shadow_view_matrix(params);
            Mat44f proj_matrix = build_shadow_projection_matrix(params);
            Mat44f light_space_matrix = compute_light_space_matrix(params);

            // Wrap the shadow FBO's depth texture as a tgfx2 handle so
            // we can open a depth-only pass on it. Destroyed at the end
            // of this cascade.
            tgfx2::TextureHandle depth_tex2 = wrap_fbo_depth_as_tgfx2(*gl_dev, fbo);
            if (!depth_tex2) {
                tc::Log::error("ShadowPass/tgfx2: failed to wrap depth texture");
                continue;
            }

            ctx.ctx2->begin_pass(
                tgfx2::TextureHandle{},  // depth-only
                depth_tex2,
                nullptr,                 // no color clear
                1.0f,                    // clear depth to 1.0
                true                     // clear_depth_enabled
            );
            ctx.ctx2->set_viewport(0, 0, resolution, resolution);
            ctx.ctx2->set_depth_test(true);
            ctx.ctx2->set_depth_write(true);
            ctx.ctx2->set_blend(false);
            ctx.ctx2->set_cull(tgfx2::CullMode::Back);
            ctx.ctx2->set_color_format(tgfx2::PixelFormat::RGBA8_UNorm);
            ctx.ctx2->set_depth_format(tgfx2::PixelFormat::D32F);
            ctx.ctx2->bind_shader(shadow_vs2_, shadow_fs2_);

            // PerFrame UBO (view + projection) — upload ONCE per
            // cascade, bound at slot 0. Never re-uploaded inside the
            // draw loop.
            ShadowPerFrameStd140 per_frame{};
            std::memcpy(per_frame.u_view, view_matrix.data, sizeof(float) * 16);
            std::memcpy(per_frame.u_projection, proj_matrix.data, sizeof(float) * 16);
            ctx.ctx2->device().upload_buffer(
                per_frame_ubo_,
                std::span<const uint8_t>(
                    reinterpret_cast<const uint8_t*>(&per_frame),
                    sizeof(per_frame)));
            ctx.ctx2->bind_uniform_buffer(0, per_frame_ubo_);

            if (cached_draw_calls_.empty()) {
                ctx.ctx2->end_pass();
                gl_dev->destroy(depth_tex2);
                results.emplace_back(fbo, light_space_matrix, light_index,
                                     c, cascade_near, cascade_far);
                continue;
            }

            // RenderContext setup for the legacy fallback path (used
            // when a drawable can't expose a tc_mesh*).
            RenderContext legacy_ctx;
            legacy_ctx.graphics = ctx.graphics;
            legacy_ctx.phase = "shadow";
            legacy_ctx.view = view_matrix;
            legacy_ctx.projection = proj_matrix;
            bool legacy_shader_in_use = false;

            for (const auto& dc : cached_draw_calls_) {
                auto* drawable = static_cast<Drawable*>(
                    tc_component_get_drawable_userdata(dc.component));
                if (!drawable) continue;

                Mat44f model = drawable->get_model_matrix(dc.entity);

                tc_mesh* mesh = drawable->get_mesh_for_phase("shadow", dc.geometry_id);
                bool override_is_base = tc_shader_handle_eq(
                    dc.final_shader,
                    shadow_shader ? shadow_shader->handle : tc_shader_handle_invalid());

                if (mesh && override_is_base) {
                    // Fast path: mesh-backed drawable, no shader override.
                    // Per-object data goes through push constants — 64 B
                    // per draw via the ring buffer, no ResourceSet churn.
                    ShadowPushStd140 push{};
                    std::memcpy(push.u_model, model.data, sizeof(float) * 16);
                    ctx.ctx2->set_push_constants(&push, sizeof(push));

                    Tgfx2MeshBinding bind = wrap_mesh_as_tgfx2(*gl_dev, mesh);
                    if (bind.index_count == 0) continue;

                    ctx.ctx2->set_vertex_layout(bind.layout);
                    ctx.ctx2->set_topology(bind.topology);
                    ctx.ctx2->draw(bind.vertex_buffer, bind.index_buffer,
                                   bind.index_count, bind.index_type);

                    gl_dev->destroy(bind.vertex_buffer);
                    gl_dev->destroy(bind.index_buffer);
                } else {
                    // Fallback: shader override (skinning) or non-mesh
                    // drawable. Use legacy state-machine draw. The GL
                    // FBO is already bound by ctx2->begin_pass above;
                    // glDraw calls land on it correctly.
                    ctx.ctx2->flush_pipeline();  // ensure cmd list is in a
                                                 // clean state before we
                                                 // poke raw GL

                    tc_shader_handle shader_handle = dc.final_shader;
                    TcShader shader_to_use(shader_handle);
                    shader_to_use.use();
                    shader_to_use.set_uniform_mat4("u_view", view_matrix.data, false);
                    shader_to_use.set_uniform_mat4("u_projection", proj_matrix.data, false);
                    shader_to_use.set_uniform_mat4("u_model", model.data, false);
                    legacy_ctx.current_tc_shader = shader_to_use;
                    legacy_shader_in_use = true;

                    tc_component_draw_geometry(dc.component, &legacy_ctx, dc.geometry_id);
                }
            }

            (void)legacy_shader_in_use;

            ctx.ctx2->end_pass();
            gl_dev->destroy(depth_tex2);

            results.emplace_back(fbo, light_space_matrix, light_index,
                                 c, cascade_near, cascade_far);
        }
    }

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
