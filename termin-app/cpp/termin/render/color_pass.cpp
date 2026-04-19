#include "color_pass.hpp"
#include "termin/camera/render_camera_utils.hpp"
#include "termin/render/material_ubo_apply.hpp"
#include "termin/render/tgfx2_bridge.hpp"

#include <optional>
#include <cstdlib>
#include <tgfx/tgfx_shader_handle.hpp>
#include <tcbase/tc_log.hpp>
#include "termin/lighting/lighting_upload.hpp"
#include "tgfx2/render_context.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/tc_shader_bridge.hpp"
#include <termin/render/frame_graph_debugger_core.hpp>
extern "C" {
#include <tgfx/resources/tc_shader.h>
#include <tgfx/resources/tc_shader_registry.h>
#include "tc_profiler.h"
#include "core/tc_component.h"
#include "core/tc_drawable_protocol.h"
#include "core/tc_scene_drawable.h"
#include <tgfx/resources/tc_material.h>
#include <tgfx/tc_gpu.h>
#include "core/tc_scene_render_state.h"
}

#include <cmath>
#include <cstring>
#include <span>
#include <algorithm>
#include <numeric>
#include <chrono>

namespace termin {

namespace {

// Convert tc_render_state to C++ RenderState
inline RenderState convert_render_state(const tc_render_state& s) {
    RenderState rs;
    rs.polygon_mode = (s.polygon_mode == TC_POLYGON_LINE) ? PolygonMode::Line : PolygonMode::Fill;
    rs.cull = s.cull != 0;
    rs.depth_test = s.depth_test != 0;
    rs.depth_write = s.depth_write != 0;
    rs.blend = s.blend != 0;

    // Convert blend factors
    switch (s.blend_src) {
        case TC_BLEND_ZERO: rs.blend_src = BlendFactor::Zero; break;
        case TC_BLEND_ONE: rs.blend_src = BlendFactor::One; break;
        case TC_BLEND_ONE_MINUS_SRC_ALPHA: rs.blend_src = BlendFactor::OneMinusSrcAlpha; break;
        default: rs.blend_src = BlendFactor::SrcAlpha; break;
    }
    switch (s.blend_dst) {
        case TC_BLEND_ZERO: rs.blend_dst = BlendFactor::Zero; break;
        case TC_BLEND_ONE: rs.blend_dst = BlendFactor::One; break;
        case TC_BLEND_SRC_ALPHA: rs.blend_dst = BlendFactor::SrcAlpha; break;
        default: rs.blend_dst = BlendFactor::OneMinusSrcAlpha; break;
    }
    return rs;
}

// Get global position from Entity.
inline Vec3 get_global_position(const Entity& entity) {
    return entity.transform().global_pose().lin;
}

// Convert float distance to uint32 for radix-friendly sorting.
// Preserves order: smaller distance -> smaller uint value.
inline uint32_t float_to_sortable_uint(float f) {
    uint32_t bits;
    std::memcpy(&bits, &f, sizeof(bits));
    // If negative, flip all bits; if positive, flip sign bit only
    uint32_t mask = -int32_t(bits >> 31) | 0x80000000;
    return bits ^ mask;
}

} // anonymous namespace

ColorPass::ColorPass(
    const std::string& input_res,
    const std::string& output_res,
    const std::string& shadow_res,
    const std::string& phase_mark,
    const std::string& pass_name,
    const std::string& sort_mode,
    bool clear_depth,
    const std::string& camera_name
) : input_res(input_res),
    output_res(output_res),
    shadow_res(shadow_res),
    phase_mark(phase_mark),
    sort_mode(sort_mode),
    camera_name(camera_name),
    clear_depth(clear_depth)
{
    set_pass_name(pass_name);
}

std::set<const char*> ColorPass::compute_reads() const {
    std::set<const char*> result;
    result.insert(input_res.c_str());
    if (!shadow_res.empty()) {
        result.insert(shadow_res.c_str());
    }
    // Add extra texture resources
    for (const auto& [uniform_name, resource_name] : extra_textures) {
        result.insert(resource_name.c_str());
    }
    return result;
}

std::set<const char*> ColorPass::compute_writes() const {
    return {output_res.c_str()};
}

std::vector<std::pair<std::string, std::string>> ColorPass::get_inplace_aliases() const {
    return {{input_res, output_res}};
}

void ColorPass::add_extra_texture(const std::string& uniform_name, const std::string& resource_name) {
    if (resource_name.empty() || resource_name.find("empty_") == 0) {
        return;
    }
    // Ensure u_ prefix for uniform name
    std::string name = uniform_name;
    if (name.find("u_") != 0) {
        name = "u_" + name;
    }
    extra_textures[name] = resource_name;
}

void ColorPass::bind_extra_textures(
    const Tex2Map& tex2_reads,
    tgfx::RenderContext2* ctx2
) {
    // Clear previous frame's uniforms
    extra_texture_uniforms.clear();
    if (!ctx2) return;

    int i = 0;
    for (const auto& [uniform_name, resource_name] : extra_textures) {
        auto it = tex2_reads.find(resource_name);
        if (it == tex2_reads.end() || !it->second) {
            tc::Log::warn("[ColorPass:%s] tgfx2 texture not found for resource: %s",
                         get_pass_name().c_str(), resource_name.c_str());
            continue;
        }

        int unit = EXTRA_TEXTURE_UNIT_START + i;
        ctx2->bind_sampled_texture(unit, it->second);
        ctx2->set_uniform_int(uniform_name.c_str(), unit);
        extra_texture_uniforms[uniform_name] = unit;
        ++i;
    }
}

CameraComponent* ColorPass::find_camera_by_name(tc_scene_handle scene, const std::string& name) {
    if (name.empty() || !tc_scene_handle_valid(scene)) {
        return nullptr;
    }

    // Check cache - CmpRef.valid() checks entity liveness
    if (cached_camera_name_ == name && cached_camera_.valid()) {
        return cached_camera_.get();
    }

    // Search in scene entities
    // TODO: This requires iterating scene entities and finding CameraComponent
    // For now, return nullptr - camera lookup by name needs scene iteration support
    cached_camera_name_ = name;
    cached_camera_.reset();
    return nullptr;
}

std::vector<ResourceSpec> ColorPass::get_resource_specs() const {
    return {
        ResourceSpec{
            input_res,
            "fbo",                                          // resource_type
            std::nullopt,                                   // size
            std::array<double, 4>{0.2, 0.2, 0.2, 1.0},      // clear_color
            1.0f                                            // clear_depth
        }
    };
}

namespace {

// User data for drawable iteration callback
struct CollectDrawCallsData {
    std::vector<PhaseDrawCall>* draw_calls;
    const char* phase_mark;
};

// Callback for tc_scene_foreach_drawable
bool collect_drawable_draw_calls(tc_component* tc, void* user_data) {
    auto* data = static_cast<CollectDrawCallsData*>(user_data);

    // Filter by phase_mark
    if (data->phase_mark[0] != '\0' && !tc_component_has_phase(tc, data->phase_mark)) {
        return true;
    }

    // Get geometry draws via vtable
    void* draws_ptr = tc_component_get_geometry_draws(tc, data->phase_mark);
    if (!draws_ptr) {
        return true;
    }

    // Build Entity from component's owner
    Entity ent(tc->owner);

    auto* geometry_draws = static_cast<std::vector<GeometryDrawCall>*>(draws_ptr);
    for (const auto& gd : *geometry_draws) {
        if (gd.phase) {
            // Get final shader with overrides (skinning, etc.) applied
            tc_shader_handle base_shader = gd.phase->shader;
            tc_shader_handle final_shader = tc_component_override_shader(
                tc, data->phase_mark, gd.geometry_id, base_shader
            );

            data->draw_calls->push_back(PhaseDrawCall{
                ent,
                tc,
                gd.phase,
                final_shader,
                gd.phase->priority,
                gd.geometry_id
            });
        }
    }

    return true;
}

} // anonymous namespace

void ColorPass::collect_draw_calls(
    tc_scene_handle scene,
    const std::string& phase_mark,
    uint64_t layer_mask
) {
    // Clear but keep capacity
    cached_draw_calls_.clear();

    if (!tc_scene_handle_valid(scene)) {
        tc::Log::warn("[ColorPass] collect_draw_calls: scene is invalid!");
        return;
    }

    // Collect draw calls via drawable iteration
    CollectDrawCallsData data;
    data.draw_calls = &cached_draw_calls_;
    data.phase_mark = phase_mark.c_str();

    // Use tc_scene_foreach_drawable with filtering
    int filter_flags = TC_SCENE_FILTER_ENABLED
                     | TC_SCENE_FILTER_VISIBLE
                     | TC_SCENE_FILTER_ENTITY_ENABLED;
    tc_scene_foreach_drawable(scene, collect_drawable_draw_calls, &data, filter_flags, layer_mask);
}

void ColorPass::compute_sort_keys(const Vec3& camera_position) {
    const size_t n = cached_draw_calls_.size();
    sort_keys_.resize(n);

    // Determine sort direction from sort_mode
    // sort_key format: [priority:16][shader_id:16][distance:32]
    // This groups objects by shader to minimize state changes,
    // while preserving priority ordering and distance-based sorting within groups.
    // For near_to_far: lower distance = lower key
    // For far_to_near: lower distance = higher key (invert distance bits)
    bool invert_distance = (sort_mode == "far_to_near");

    for (size_t i = 0; i < n; ++i) {
        const PhaseDrawCall& dc = cached_draw_calls_[i];

        // Priority in upper 16 bits (offset to handle negative)
        uint64_t priority_bits = static_cast<uint16_t>((dc.priority + 0x8000) & 0xFFFF);

        // Shader ID in next 16 bits (from final shader after overrides)
        uint64_t shader_bits = 0;
        if (!tc_shader_handle_is_invalid(dc.final_shader)) {
            shader_bits = dc.final_shader.index & 0xFFFF;
        }

        // Distance in lower 32 bits
        Vec3 pos = get_global_position(dc.entity);
        double dx = pos.x - camera_position.x;
        double dy = pos.y - camera_position.y;
        double dz = pos.z - camera_position.z;
        float dist2 = static_cast<float>(dx*dx + dy*dy + dz*dz);

        uint32_t dist_bits = float_to_sortable_uint(dist2);
        if (invert_distance) {
            dist_bits = ~dist_bits;  // Invert for far-to-near
        }

        sort_keys_[i] = (priority_bits << 48) | (shader_bits << 32) | dist_bits;
    }
}

void ColorPass::sort_draw_calls() {
    const size_t n = cached_draw_calls_.size();
    if (n <= 1) return;

    // Resize index array (reuses capacity)
    sort_indices_.resize(n);
    std::iota(sort_indices_.begin(), sort_indices_.end(), size_t(0));

    // Sort indices by sort_keys
    std::sort(sort_indices_.begin(), sort_indices_.end(),
        [this](size_t a, size_t b) {
            return sort_keys_[a] < sort_keys_[b];
        });

    // Reorder using temp buffer (reuses capacity)
    sorted_draw_calls_.clear();
    sorted_draw_calls_.reserve(n);
    for (size_t i : sort_indices_) {
        sorted_draw_calls_.push_back(std::move(cached_draw_calls_[i]));
    }
    std::swap(cached_draw_calls_, sorted_draw_calls_);
}

// ----------------------------------------------------------------------------
// ColorPass draw loop — tgfx2 native.
// ----------------------------------------------------------------------------
//
// Uses ctx2 end-to-end for pass boundary, shader binding, resource set
// (material UBO + textures), mesh draws, and state. Legacy plain-uniform
// declarations in existing .shader files (u_view, u_projection, u_model,
// shadow sampler ints and matrices) are routed through RenderContext2's
// transitional set_uniform_* helpers — clearly marked as migration debt
// until all shaders move to UBO/push-constant based per-frame data.
//
// Intentionally skipped for now:
//   - non-MeshRenderer drawables (get_mesh_for_phase returns null)
//   - shader variants where tc_shader_ensure_tgfx2 fails
//   - extra_textures (reads_fbos wrapped as sampler input)
//   - maybe_blit_to_debugger for the selected debug symbol
//   - GPU timing queries
// These each get a log line when they are skipped.

void ColorPass::execute_with_data(
    ExecuteContext& ctx,
    const Rect4i& rect,
    tc_scene_handle scene,
    const Mat44f& view,
    const Mat44f& projection,
    const Vec3& camera_position,
    const std::vector<Light>& lights,
    const Vec3& ambient_color,
    float ambient_intensity,
    const std::vector<ShadowMapArrayEntry>& shadow_maps,
    const ShadowSettings& shadow_settings,
    uint64_t layer_mask)
{
    auto* ctx2 = ctx.ctx2;
    if (!ctx2) {
        tc::Log::error("[ColorPass/tgfx2] ctx2 is null");
        return;
    }

    auto& device = ctx2->device();

    // Resolve output textures from ctx.tex2_* — persistent FBOPool
    // wrappers, no per-frame wrap/destroy churn.
    auto color_it = ctx.tex2_writes.find(output_res);
    if (color_it == ctx.tex2_writes.end() || !color_it->second) {
        tc::Log::warn("[ColorPass/tgfx2] tgfx2 color texture for '%s' not available",
                      output_res.c_str());
        return;
    }
    tgfx::TextureHandle color_tex2 = color_it->second;

    auto depth_it = ctx.tex2_depth_writes.find(output_res);
    tgfx::TextureHandle depth_tex2 =
        (depth_it != ctx.tex2_depth_writes.end()) ? depth_it->second : tgfx::TextureHandle{};

    // --- Per-frame UBO (binding 2) ------------------------------------
    // Carries view / projection / view_projection / camera_position —
    // the matrices shaders used to read from plain `uniform mat4` decls.
    // Lazy-create once per device, refresh every frame. Uploaded BEFORE
    // begin_pass because upload_buffer on Vulkan routes through a
    // staging copy that must run outside any render pass.
    struct PerFrameStd140 {
        float u_view[16];
        float u_projection[16];
        float u_view_projection[16];
        float u_camera_position[4];  // vec3 + pad to vec4
    };
    static_assert(sizeof(PerFrameStd140) == 208,
                  "PerFrameStd140 must be exactly 3*mat4 + vec4");

    if (per_frame_device_ != &device) {
        if (per_frame_ubo_ && per_frame_device_) {
            per_frame_device_->destroy(per_frame_ubo_);
        }
        per_frame_ubo_ = {};
        per_frame_device_ = &device;
    }
    if (!per_frame_ubo_) {
        tgfx::BufferDesc bd;
        bd.size = sizeof(PerFrameStd140);
        bd.usage = tgfx::BufferUsage::Uniform | tgfx::BufferUsage::CopyDst;
        per_frame_ubo_ = device.create_buffer(bd);
    }
    {
        PerFrameStd140 pf{};
        std::memcpy(pf.u_view, view.data, sizeof(pf.u_view));
        std::memcpy(pf.u_projection, projection.data, sizeof(pf.u_projection));
        Mat44f vp = projection * view;
        std::memcpy(pf.u_view_projection, vp.data, sizeof(pf.u_view_projection));
        pf.u_camera_position[0] = static_cast<float>(camera_position.x);
        pf.u_camera_position[1] = static_cast<float>(camera_position.y);
        pf.u_camera_position[2] = static_cast<float>(camera_position.z);
        pf.u_camera_position[3] = 1.0f;
        device.upload_buffer(
            per_frame_ubo_,
            std::span<const uint8_t>(
                reinterpret_cast<const uint8_t*>(&pf), sizeof(pf)));
    }

    ctx2->begin_pass(color_tex2, depth_tex2,
                     /*clear_color=*/nullptr,
                     /*clear_depth=*/1.0f,
                     /*clear_depth_enabled=*/clear_depth);
    ctx2->set_viewport(0, 0, rect.width, rect.height);

    // Bind the per-frame UBO after the pass is open — ResourceSet
    // bindings are attached to the next pipeline flush anyway.
    constexpr uint32_t PER_FRAME_UBO_BINDING = 2;
    ctx2->bind_uniform_buffer(PER_FRAME_UBO_BINDING, per_frame_ubo_);

    // Collect + sort draw calls. Reuses the legacy helpers —
    // gathering logic is backend-agnostic.
    collect_draw_calls(scene, phase_mark, layer_mask);

    if (sort_mode != "none" && !cached_draw_calls_.empty()) {
        compute_sort_keys(camera_position);
        sort_draw_calls();
    } else if (!cached_draw_calls_.empty()) {
        std::sort(cached_draw_calls_.begin(), cached_draw_calls_.end(),
            [](const PhaseDrawCall& a, const PhaseDrawCall& b) {
                return a.priority < b.priority;
            });
    }

    // Decide whether any shader in this batch needs the lighting UBO.
    bool any_shader_needs_ubo = false;
    for (const auto& dc : cached_draw_calls_) {
        tc_shader* shader = tc_shader_get(dc.final_shader);
        if (shader && tc_shader_has_feature(shader, TC_SHADER_FEATURE_LIGHTING_UBO)) {
            any_shader_needs_ubo = true;
            break;
        }
    }

    // Allocate lighting UBO directly on the tgfx2 device and upload
    // this frame's data. The buffer is persistent — only the contents
    // change per frame.
    tgfx::BufferHandle lighting_ubo_tgfx2{};
    if (any_shader_needs_ubo) {
        lighting_ubo_.create(device);
        lighting_ubo_.update_from_lights(lights, ambient_color, ambient_intensity,
                                         camera_position, shadow_settings);
        lighting_ubo_.upload();
        lighting_ubo_tgfx2 = lighting_ubo_.buffer;
    }

    // Shadow maps are now native tgfx2 depth textures owned by
    // ShadowPass; no per-frame wrap needed.
    std::vector<tgfx::TextureHandle> shadow_tex2s;
    shadow_tex2s.reserve(shadow_maps.size());
    for (const auto& smap : shadow_maps) {
        shadow_tex2s.push_back(smap.depth_tex2);
    }

    entity_names.clear();
    entity_names.reserve(cached_draw_calls_.size());
    const std::string& debug_symbol = get_debug_internal_point();
    if (debug_symbol.empty()) {
        selected_symbol_timing = {};
    }

    // Base offset for shadow sampler slots — matches legacy
    // SHADOW_MAP_TEXTURE_UNIT_START so .shader files that still
    // declare `uniform sampler2D u_shadow_map_N` at binding N keep
    // reading from the right slot.
    constexpr uint32_t SHADOW_SLOT_BASE = 8;
    constexpr uint32_t MATERIAL_TEX_SLOT_BASE = 0;

    tc_shader_handle last_shader_handle = tc_shader_handle_invalid();

    for (const auto& dc : cached_draw_calls_) {
        const char* ename = dc.entity.name();
        entity_names.push_back(ename ? ename : "");

        // Only cast the drawable userdata to Drawable* when the component
        // actually installed the C++ drawable vtable. Python drawables use
        // the same capability slot with a PyObject* userdata and a
        // different C vtable — casting that to Drawable* and calling
        // virtual methods on it is undefined behaviour.
        Drawable* drawable = nullptr;
        if (tc_component_get_drawable_vtable(dc.component) == &Drawable::cxx_drawable_vtable()) {
            drawable = static_cast<Drawable*>(tc_component_get_drawable_userdata(dc.component));
        }
        if (!drawable) continue;

        tc_mesh* mesh = drawable->get_mesh_for_phase(phase_mark, dc.geometry_id);
        if (!mesh) {
            // Non-mesh drawables (immediate gizmos, NavMesh debug,
            // solid primitive helpers) belong in their own dedicated
            // passes (UnifiedGizmoPass, ColliderGizmoPass, ...), not
            // in ColorPass. Stage 8.1 removed the legacy fallback
            // that ran them through shader.use() + draw_geometry.
            continue;
        }

        Mat44f model = drawable->get_model_matrix(dc.entity);

        // Wrap the mesh's per-context VBO/EBO as tgfx2 buffers for
        // the duration of this draw. Destroyed right after draw —
        // wrap_mesh is cheap and avoids growing the HandlePool.
        Tgfx2MeshBinding bind = wrap_mesh_as_tgfx2(device, mesh);
        if (bind.index_count == 0) continue;

        // Compile the shader through the tc_shader_ensure_tgfx2 bridge.
        // This is a separate GL program from the legacy one — ctx2
        // binds it via bind_shader, legacy TcShader still has its own
        // program id which is now unused for this pass.
        tc_shader* raw_shader = tc_shader_get(dc.final_shader);
        if (!raw_shader) {
            release_mesh_binding(device, bind);
            continue;
        }
        tgfx::ShaderHandle vs2, fs2;
        if (!tc_shader_ensure_tgfx2(raw_shader, &device, &vs2, &fs2)) {
            tc::Log::error("[ColorPass/tgfx2] tc_shader_ensure_tgfx2 failed for shader '%s'",
                           raw_shader->name ? raw_shader->name : raw_shader->uuid);
            release_mesh_binding(device, bind);
            continue;
        }

        // Render state from the material phase.
        RenderState state = convert_render_state(dc.phase->state);
        if (wireframe) state.polygon_mode = PolygonMode::Line;

        ctx2->set_depth_test(state.depth_test);
        ctx2->set_depth_write(state.depth_write);
        ctx2->set_blend(state.blend);
        ctx2->set_cull(state.cull ? tgfx::CullMode::Back : tgfx::CullMode::None);
        ctx2->set_polygon_mode(state.polygon_mode == PolygonMode::Line
                               ? tgfx::PolygonMode::Line
                               : tgfx::PolygonMode::Fill);

        // Pipeline cache key — needs to match the FBO formats. This is
        // approximate because the wrapped textures retain their GL
        // internal format; the cache key just needs to be stable.
        ctx2->set_color_format(tgfx::PixelFormat::RGBA8_UNorm);
        ctx2->set_depth_format(tgfx::PixelFormat::D24_UNorm_S8_UInt);

        ctx2->bind_shader(vs2, fs2);
        ctx2->set_vertex_layout(bind.layout);
        ctx2->set_topology(bind.topology);

        // --- UBO bindings ---
        // Lighting UBO at slot 0.
        if (lighting_ubo_tgfx2 &&
            tc_shader_has_feature(raw_shader, TC_SHADER_FEATURE_LIGHTING_UBO)) {
            ctx2->bind_uniform_buffer(LIGHTING_UBO_BINDING, lighting_ubo_tgfx2);
        }

        // Material UBO + material textures through the dispatcher.
        // The C++ variant (not the _gl raw path) is used here because
        // we are inside a ctx2 pass.
        apply_material_phase_ubo(dc.phase, raw_shader,
                                 MATERIAL_UBO_BINDING,
                                 MATERIAL_TEX_SLOT_BASE,
                                 device, *ctx2);

        // Extra textures (nodegraph inputs) — bind into the currently
        // active pipeline after material textures are in place.
        if (!extra_textures.empty()) {
            bind_extra_textures(ctx.tex2_reads, ctx2);
        }

        // Tell the shader which texture unit each material sampler
        // reads from. Existing shaders declare `uniform sampler2D
        // u_albedo_texture` etc. without an explicit `layout(binding)`
        // qualifier, so GL defaults them to unit 0. We need to route
        // each named sampler to the slot apply_material_phase_ubo
        // bound it at (MATERIAL_TEX_SLOT_BASE + i in declaration
        // order). Without this, every sampler in the shader reads
        // unit 0 and extra material textures show up as black/wrong.
        for (size_t i = 0; i < dc.phase->texture_count; i++) {
            const tc_material_texture& mt = dc.phase->textures[i];
            ctx2->set_uniform_int(mt.name,
                                  static_cast<int>(MATERIAL_TEX_SLOT_BASE + i));
        }

        // Shadow maps as sampled textures at SHADOW_SLOT_BASE..
        for (size_t i = 0; i < shadow_tex2s.size() && i < MAX_SHADOW_MAPS; i++) {
            if (!shadow_tex2s[i]) continue;
            ctx2->bind_sampled_texture(SHADOW_SLOT_BASE + static_cast<uint32_t>(i),
                                       shadow_tex2s[i]);
        }

        // --- Per-draw data ---
        //
        // Vulkan-compatible path: push u_model through push_constants
        // (tgfx2 maps this to `layout(push_constant)` in Vulkan and to
        // the emulation UBO at binding TGFX2_PUSH_CONSTANTS_BINDING=14
        // on GL). Shaders that declare `ColorPushBlock { mat4 u_model; }`
        // pick up the value; shaders that don't simply ignore the push.
        //
        // Legacy GL path: set_uniform_mat4 still sets u_model/u_view/
        // u_projection on the currently-bound program for shaders that
        // kept their plain `uniform mat4 u_view` declarations. On Vulkan
        // these calls are no-ops — migrated shaders must read view and
        // projection from the PerFrame UBO at binding 2.
        struct ColorPushData {
            float u_model[16];
        };
        ColorPushData push{};
        std::memcpy(push.u_model, model.data, sizeof(push.u_model));
        ctx2->set_push_constants(&push, sizeof(push));

        ctx2->set_uniform_mat4("u_model",      model.data,      /*transpose=*/false);
        ctx2->set_uniform_mat4("u_view",       view.data,       /*transpose=*/false);
        ctx2->set_uniform_mat4("u_projection", projection.data, /*transpose=*/false);

        // Shader changes → link UBO block bindings and shadow sampler
        // uniforms once per shader in this batch.
        bool shader_changed =
            !tc_shader_handle_eq(dc.final_shader, last_shader_handle);
        if (shader_changed) {
            ctx2->set_block_binding("MaterialParams", MATERIAL_UBO_BINDING);
            if (tc_shader_has_feature(raw_shader, TC_SHADER_FEATURE_LIGHTING_UBO)) {
                ctx2->set_block_binding("LightingBlock", LIGHTING_UBO_BINDING);
            }

            // Shadow sampler uniforms and cascade metadata. Legacy path
            // uses upload_shadow_maps_to_shader / init_shadow_map_samplers
            // which hit the LEGACY program — we need to set on the
            // currently-bound ctx2 program instead.
            int sm_count = static_cast<int>(
                std::min(shadow_maps.size(), static_cast<size_t>(MAX_SHADOW_MAPS)));
            ctx2->set_uniform_int("u_shadow_map_count", sm_count);

            for (int i = 0; i < sm_count; ++i) {
                const ShadowMapArrayEntry& e = shadow_maps[i];
                ctx2->set_uniform_int(detail::shadow_map_names[i],
                                      SHADOW_SLOT_BASE + i);
                ctx2->set_uniform_mat4(detail::light_space_matrix_names[i],
                                       e.light_space_matrix.data, false);
                ctx2->set_uniform_int(detail::shadow_light_index_names[i],
                                      e.light_index);
                ctx2->set_uniform_int(detail::shadow_cascade_index_names[i],
                                      e.cascade_index);
                ctx2->set_uniform_float(detail::shadow_split_near_names[i],
                                        e.cascade_split_near);
                ctx2->set_uniform_float(detail::shadow_split_far_names[i],
                                        e.cascade_split_far);
            }
            // Remaining shadow samplers must still be set to their unit
            // (AMD requires no two sampler types share a unit).
            for (int i = sm_count; i < MAX_SHADOW_MAPS; ++i) {
                ctx2->set_uniform_int(detail::shadow_map_names[i],
                                      SHADOW_SLOT_BASE + i);
            }

            last_shader_handle = dc.final_shader;
        }

        // Per-draw uniforms that can't live in push-constants or the
        // material UBO yet — skinning bone matrices are the main case.
        // Default implementation is a no-op for non-skinned drawables.
        drawable->upload_per_draw_uniforms_tgfx2(*ctx2, dc.geometry_id);

        // Issue the draw. This flushes the pending ctx2 state into a
        // pipeline binding + glDrawElements inside the ctx2 render pass.
        ctx2->draw(bind.vertex_buffer, bind.index_buffer,
                   bind.index_count, bind.index_type);

        release_mesh_binding(device, bind);
    }

    ctx2->end_pass();
}

void ColorPass::execute(ExecuteContext& ctx) {
    bool profile = tc_profiler_enabled();
    if (profile) tc_profiler_begin_section(("ColorPass:" + get_pass_name()).c_str());

    // Use camera from context, or find by name if camera_name is set
    const RenderCamera* camera = ctx.camera;
    tc_scene_handle scene = ctx.scene.handle();
    if (!tc_scene_handle_valid(scene)) {
        tc::Log::error("[ColorPass] scene is invalid");
        if (profile) tc_profiler_end_section();
        return;
    }
    std::optional<RenderCamera> named_camera_snapshot;
    if (!camera_name.empty()) {
        CameraComponent* named_camera = find_camera_by_name(scene, camera_name);
        if (named_camera) {
            named_camera_snapshot = make_render_camera(*named_camera);
            camera = &*named_camera_snapshot;
        } else {
            // Camera not found, skip pass
            if (profile) tc_profiler_end_section();
            return;
        }
    }

    if (!camera) {
        if (profile) tc_profiler_end_section();
        return;
    }

    // extra_textures are resolved inside execute_with_data after a ctx2
    // shader is bound (bind_extra_textures needs an active pipeline to
    // call bind_sampled_texture + set_uniform_int).

    // Get output size from the tgfx2 color texture and update rect.
    Rect4i rect = ctx.rect;
    if (ctx.ctx2) {
        auto it = ctx.tex2_writes.find(output_res);
        if (it != ctx.tex2_writes.end() && it->second) {
            auto desc = ctx.ctx2->device().texture_desc(it->second);
            int w = static_cast<int>(desc.width);
            int h = static_cast<int>(desc.height);
            if (w > 0 && h > 0) {
                rect = Rect4i{0, 0, w, h};
                if (!camera_name.empty()) {
                    CameraComponent* named_camera = find_camera_by_name(scene, camera_name);
                    if (named_camera) {
                        named_camera_snapshot = make_render_camera(
                            *named_camera, static_cast<double>(w) / std::max(1, h));
                        camera = &*named_camera_snapshot;
                    }
                }
            }
        }
    }

    // Get camera matrices
    Mat44 view64 = camera->get_view_matrix();
    Mat44 proj64 = camera->get_projection_matrix();
    Mat44f view = view64.to_float();
    Mat44f projection = proj64.to_float();

    // Get camera position
    Vec3 camera_position = camera->get_position();

    // Get scene lighting properties
    Vec3 ambient_color{1.0, 1.0, 1.0};
    float ambient_intensity = 0.1f;
    ShadowSettings shadow_settings;

    if (tc_scene_handle_valid(scene)) {
        tc_scene_render_state* render_state = tc_scene_render_state_get(scene);
        tc_scene_lighting* lighting = render_state ? &render_state->lighting : nullptr;
        if (lighting) {
            ambient_color = Vec3{
                lighting->ambient_color[0],
                lighting->ambient_color[1],
                lighting->ambient_color[2]
            };
            ambient_intensity = lighting->ambient_intensity;
            shadow_settings.method = lighting->shadow_method;
            shadow_settings.softness = lighting->shadow_softness;
            shadow_settings.bias = lighting->shadow_bias;
        }
    }

    std::vector<ShadowMapArrayEntry> shadow_maps;
    if (!shadow_res.empty()) {
        auto shadow_it = ctx.shadow_arrays.find(shadow_res);
        if (shadow_it != ctx.shadow_arrays.end() && shadow_it->second != nullptr) {
            shadow_maps = shadow_it->second->entries;
        }
    }

    if (!ctx.ctx2) {
        tc::Log::error("[ColorPass] ctx.ctx2 is null — ColorPass is tgfx2-only");
        return;
    }

    execute_with_data(
        ctx,
        rect,
        scene,
        view,
        projection,
        camera_position,
        ctx.lights,
        ambient_color,
        ambient_intensity,
        shadow_maps,
        shadow_settings,
        ctx.layer_mask
    );

    if (profile) tc_profiler_end_section();
}

// Register ColorPass in tc_pass_registry for C#/standalone C++ usage
TC_REGISTER_FRAME_PASS(ColorPass);

} // namespace termin
