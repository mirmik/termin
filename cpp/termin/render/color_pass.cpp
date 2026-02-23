#include "color_pass.hpp"
#include "tc_shader_handle.hpp"
#include <tcbase/tc_log.hpp>
#include "termin/lighting/lighting_upload.hpp"
#include "termin/editor/frame_graph_debugger_core.hpp"
extern "C" {
#include <tgfx/resources/tc_shader.h>
#include <tgfx/resources/tc_shader_registry.h>
#include "tc_profiler.h"
#include "core/tc_component.h"
#include <tgfx/resources/tc_material.h>
#include "tc_gpu.h"
#include "core/tc_scene_lighting.h"
}

#include <cmath>
#include <cstring>
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

void ColorPass::bind_extra_textures(const FBOMap& reads_fbos) {
    // Clear previous frame's uniforms
    extra_texture_uniforms.clear();

    int i = 0;
    for (const auto& [uniform_name, resource_name] : extra_textures) {
        auto it = reads_fbos.find(resource_name);
        if (it == reads_fbos.end() || it->second == nullptr) {
            tc::Log::warn("[ColorPass:%s] FBO not found for resource: %s",
                         get_pass_name().c_str(), resource_name.c_str());
            continue;
        }

        // Get FBO and its color texture
        FrameGraphResource* resource = it->second;

        FramebufferHandle* fbo = nullptr;
        try {
            fbo = dynamic_cast<FramebufferHandle*>(resource);
        } catch (const std::exception& e) {
            tc::Log::error("[ColorPass:%s] dynamic_cast failed: %s", get_pass_name().c_str(), e.what());
            continue;
        }

        if (!fbo) {
            tc::Log::warn("[ColorPass:%s] Resource %s is not a FramebufferHandle (cast returned nullptr)",
                         get_pass_name().c_str(), resource_name.c_str());
            continue;
        }

        GPUTextureHandle* tex = fbo->color_texture();
        if (!tex) {
            tc::Log::warn("[ColorPass:%s] No color_texture on FBO %s",
                         get_pass_name().c_str(), resource_name.c_str());
            continue;
        }

        // Bind to texture unit
        int unit = EXTRA_TEXTURE_UNIT_START + i;
        tex->bind(unit);

        // Register uniform->unit mapping for shader
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
    int filter_flags = TC_DRAWABLE_FILTER_ENABLED
                     | TC_DRAWABLE_FILTER_VISIBLE
                     | TC_DRAWABLE_FILTER_ENTITY_ENABLED;
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

void ColorPass::execute_with_data(
    GraphicsBackend* graphics,
    const FBOMap& reads_fbos,
    const FBOMap& writes_fbos,
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
    uint64_t layer_mask
) {
    // Get output framebuffer
    auto it = writes_fbos.find(output_res);
    if (it == writes_fbos.end() || it->second == nullptr) {
        tc::Log::warn("[ColorPass] FBO '%s' not found in writes_fbos (size=%zu)", output_res.c_str(), writes_fbos.size());
        for (auto& p : writes_fbos) {
            tc::Log::warn("  - '%s': %p", p.first.c_str(), p.second);
        }
        return;
    }
    FrameGraphResource* resource = it->second;

    FramebufferHandle* fb = nullptr;
    try {
        fb = dynamic_cast<FramebufferHandle*>(resource);
    } catch (const std::exception& e) {
        tc::Log::error("[ColorPass] dynamic_cast failed: %s", e.what());
        return;
    }

    if (!fb) {
        tc::Log::warn("[ColorPass] FBO '%s' is not a FramebufferHandle (cast returned nullptr)", output_res.c_str());
        return;
    }

    // Bind framebuffer and set viewport
    graphics->bind_framebuffer(fb);
    graphics->check_gl_error("ColorPass: after bind_framebuffer");
    graphics->set_viewport(0, 0, rect.width, rect.height);

    // Clear depth if requested
    if (clear_depth) {
        graphics->clear_depth();
    }
    graphics->check_gl_error("ColorPass: after setup");

    // Create render context
    RenderContext context;
    context.view = view;
    context.projection = projection;
    context.graphics = graphics;
    context.phase = phase_mark;

    // Detailed profiling mode
    bool detailed = tc_profiler_detailed_rendering();

    // Collect draw calls into cached vector
    if (detailed) tc_profiler_begin_section("Collect");
    collect_draw_calls(scene, phase_mark, layer_mask);
    if (detailed) tc_profiler_end_section();

    // Compute sort keys and sort (single pass with combined priority+distance key)
    if (detailed) tc_profiler_begin_section("Sort");
    if (sort_mode != "none" && !cached_draw_calls_.empty()) {
        compute_sort_keys(camera_position);
        sort_draw_calls();
    } else if (!cached_draw_calls_.empty()) {
        // Sort by priority only
        std::sort(cached_draw_calls_.begin(), cached_draw_calls_.end(),
            [](const PhaseDrawCall& a, const PhaseDrawCall& b) {
                return a.priority < b.priority;
            });
    }
    if (detailed) tc_profiler_end_section();

    // Clear entity names cache but keep capacity
    entity_names.clear();
    entity_names.reserve(cached_draw_calls_.size());

    // Get debug symbol
    const std::string& debug_symbol = get_debug_internal_point();

    // Clear timing if no debug symbol selected
    if (debug_symbol.empty()) {
        selected_symbol_timing = {};
    }

    // Check if any shader needs UBO (has lighting_ubo feature)
    bool any_shader_needs_ubo = false;
    for (const auto& dc : cached_draw_calls_) {
        if (dc.phase && !tc_shader_handle_is_invalid(dc.phase->shader)) {
            tc_shader* shader = tc_shader_get(dc.phase->shader);
            if (shader && tc_shader_has_feature(shader, TC_SHADER_FEATURE_LIGHTING_UBO)) {
                any_shader_needs_ubo = true;
                break;
            }
        }
    }

    // Setup lighting UBO if any shader needs it (or if manually enabled)
    bool ubo_active = use_ubo || any_shader_needs_ubo;

    if (detailed) tc_profiler_begin_section("UBO");
    if (ubo_active) {
        lighting_ubo_.create(graphics);
        graphics->check_gl_error("ColorPass: after UBO create");
        lighting_ubo_.update_from_lights(lights, ambient_color, ambient_intensity,
                                          camera_position, shadow_settings);
        lighting_ubo_.upload();
        graphics->check_gl_error("ColorPass: after UBO upload");
    }
    if (detailed) tc_profiler_end_section();

    // Bind shadow textures to texture units (once per frame)
    // Skip entirely when no shadow resource — no shader expects sampler2DShadow
    if (detailed) tc_profiler_begin_section("ShadowBind");
    if (!shadow_res.empty()) {
        bind_shadow_textures(shadow_maps);
        graphics->check_gl_error("ColorPass: after bind_shadow_textures");
    }
    if (detailed) tc_profiler_end_section();

    // Render each draw call
    if (detailed) {
        tc_profiler_begin_section("DrawCalls");
    }

    // Clear any accumulated GL errors before rendering
    graphics->clear_gl_errors();

    // Track last shader/material to avoid redundant state changes
    tc_shader_handle last_shader_handle = tc_shader_handle_invalid();
    tc_material_phase* last_material_phase = nullptr;
    RenderState last_render_state;

    size_t draw_idx = 0;
    for (const auto& dc : cached_draw_calls_)
    {
        ++draw_idx;
        if (detailed) {
            tc_profiler_begin_section("Prep.ModelMatrix");
        }

        // Cache entity name
        const char* ename = dc.entity.name();
        entity_names.push_back(ename ? ename : "");

        // Get model matrix
        Mat44f model = static_cast<Drawable*>(dc.component->drawable_ptr)->get_model_matrix(dc.entity);
        context.model = model;

        if (detailed) {
            tc_profiler_end_section();
            tc_profiler_begin_section("Prep.RenderState");
        }

        // Apply render state (override polygon mode if wireframe enabled)
        RenderState state = convert_render_state(dc.phase->state);
        if (wireframe) {
            state.polygon_mode = PolygonMode::Line;
        }
        // Only apply if state changed
        if (state != last_render_state) {
            graphics->apply_render_state(state);
            last_render_state = state;
        }

        if (detailed) {
            tc_profiler_end_section();
            tc_profiler_begin_section("Prep.Shader");
        }

        // Use final shader (override already applied during collect)
        tc_shader_handle shader_handle = dc.final_shader;
        TcShader shader_to_use(shader_handle);

        if (detailed) {
            tc_profiler_end_section();
            tc_profiler_begin_section("Prep.ApplyMaterial");
        }

        // Check if shader changed
        bool shader_changed = !tc_shader_handle_eq(shader_handle, last_shader_handle);

        // Compile and use shader (only if changed)
        if (shader_changed) {
            shader_to_use.use();
            if (graphics->check_gl_error("after shader.use()")) {
                tc::Log::error("  shader: %s, program=%u", shader_to_use.name(), shader_to_use.gpu_program());
            }
        }

        // Apply material uniforms
        tc_shader* raw_shader = tc_shader_get(shader_handle);
        if (raw_shader) {
            // Clear any pending GL errors before apply
            graphics->clear_gl_errors();

            // If same material phase, only update MVP matrices (textures/uniforms already set)
            if (dc.phase == last_material_phase && !shader_changed) {
                // Just update model matrix (view/projection unchanged within frame)
                tc_shader_set_mat4(raw_shader, "u_model", model.data, false);
            } else {
                // Full material apply (textures, uniforms, MVP)
                tc_material_phase_apply_with_mvp(
                    dc.phase,
                    raw_shader,
                    model.data,
                    view.data,
                    projection.data
                );
                last_material_phase = dc.phase;
            }
        }
        if (graphics->check_gl_error("after tc_material_phase_apply_with_mvp")) {
            tc::Log::error("  shader: %s, phase->uniform_count=%zu, phase->texture_count=%zu",
                          shader_to_use.name(),
                          dc.phase->uniform_count,
                          dc.phase->texture_count);
        }

        if (detailed) {
            tc_profiler_end_section();
            tc_profiler_begin_section("Prep.Uniforms");
        }

        // Extra texture uniforms
        if (!extra_texture_uniforms.empty()) {
            for (const auto& [uniform_name, unit] : extra_texture_uniforms) {
                shader_to_use.set_uniform_int(uniform_name.c_str(), unit);
            }
        }

        // Lighting UBO binding
        // Note: AMD requires glBindBufferBase AFTER glUniformBlockBinding
        // Also AMD requires UBO to be unbound when shader doesn't use it
        if (ubo_active) {
            if (shader_to_use.has_feature(TC_SHADER_FEATURE_LIGHTING_UBO)) {
                shader_to_use.set_block_binding("LightingBlock", LIGHTING_UBO_BINDING);
                lighting_ubo_.bind();
            } else {
                // Unbind UBO for shaders that don't use it (AMD compatibility)
                lighting_ubo_.unbind();
            }
        }
        graphics->check_gl_error("after UBO operations");

        // Initialize/upload shadow maps uniforms when shader changes
        // CRITICAL: Must always initialize shadow samplers to prevent AMD sampler type conflicts
        // (sampler2DShadow defaults to unit 0, conflicting with material sampler2D textures)
        if (shader_handle.index != last_shader_handle.index ||
            shader_handle.generation != last_shader_handle.generation) {
            if (!shadow_maps.empty()) {
                upload_shadow_maps_to_shader(shader_to_use, shadow_maps);
            } else {
                init_shadow_map_samplers(shader_to_use);
            }
            last_shader_handle = shader_handle;
        }
        graphics->check_gl_error("after shadow_maps upload");

        context.current_tc_shader = shader_to_use;

        if (detailed) {
            tc_profiler_end_section();
            tc_profiler_begin_section("DrawGeometry");
        }

        // Check if we should measure timing for this entity
        bool measure_timing = !debug_symbol.empty() && ename && debug_symbol == ename;

        // Start timing if this is the selected debug symbol
        std::chrono::high_resolution_clock::time_point cpu_start;
        if (measure_timing) {
            // Read GPU result from PREVIOUS frame before starting new query
            // (GPU query results are not available until the next frame)
            double prev_gpu_ms = graphics->get_gpu_query_ms("ColorPass_DebugSymbol");
            if (prev_gpu_ms >= 0) {
                selected_symbol_timing.gpu_time_ms = prev_gpu_ms;
            }

            cpu_start = std::chrono::high_resolution_clock::now();
            graphics->begin_gpu_query("ColorPass_DebugSymbol");
        }

        // Draw geometry via vtable
        tc_component_draw_geometry(dc.component, &context, dc.geometry_id);
        if (graphics->check_gl_error("after draw_geometry")) {
            tc::Log::error("  entity: %s, shader: %s", ename ? ename : "(null)", shader_to_use.name());
        }

        // End timing and store results
        if (measure_timing) {
            graphics->end_gpu_query();
            auto cpu_end = std::chrono::high_resolution_clock::now();
            double cpu_ms = std::chrono::duration<double, std::milli>(cpu_end - cpu_start).count();

            selected_symbol_timing.name = ename;
            selected_symbol_timing.cpu_time_ms = cpu_ms;
            // GPU time is read at the start of the NEXT frame (see above)

            maybe_blit_to_debugger(graphics, fb, ename, rect.width, rect.height);
        }

        if (detailed) {
            tc_profiler_end_section(); // DrawGeometry
        }
    }

    if (detailed) {
        tc_profiler_end_section();
    }

    // Unbind lighting UBO
    if (ubo_active) {
        lighting_ubo_.unbind();
    }

    // Reset render state
    graphics->apply_render_state(RenderState());
}

void ColorPass::execute(ExecuteContext& ctx) {
    bool profile = tc_profiler_enabled();
    if (profile) tc_profiler_begin_section(("ColorPass:" + get_pass_name()).c_str());

    // Use camera from context, or find by name if camera_name is set
    CameraComponent* camera = ctx.camera;
    tc_scene_handle scene = ctx.scene.handle();
    if (!tc_scene_handle_valid(scene)) {
        tc::Log::error("[ColorPass] scene is invalid");
        if (profile) tc_profiler_end_section();
        return;
    }
    if (!camera_name.empty()) {
        CameraComponent* named_camera = find_camera_by_name(scene, camera_name);
        if (named_camera) {
            camera = named_camera;
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

    // Bind extra textures (if any)
    if (!extra_textures.empty()) {
        bind_extra_textures(ctx.reads_fbos);
    }

    // Get output FBO and update rect to match its size
    Rect4i rect = ctx.rect;
    auto it = ctx.writes_fbos.find(output_res);
    if (it != ctx.writes_fbos.end() && it->second != nullptr) {
        FramebufferHandle* output_fbo = dynamic_cast<FramebufferHandle*>(it->second);
        if (output_fbo) {
            int w = output_fbo->get_width();
            int h = output_fbo->get_height();
            rect = Rect4i{0, 0, w, h};
            // Update camera aspect ratio
            camera->set_aspect(static_cast<double>(w) / std::max(1, h));
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
        tc_scene_lighting* lighting = tc_scene_get_lighting(scene);
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

    // Get shadow maps from reads_fbos
    std::vector<ShadowMapArrayEntry> shadow_maps;
    if (!shadow_res.empty()) {
        auto shadow_it = ctx.reads_fbos.find(shadow_res);
        if (shadow_it != ctx.reads_fbos.end() && shadow_it->second != nullptr) {
            ShadowMapArrayResource* shadow_array = dynamic_cast<ShadowMapArrayResource*>(shadow_it->second);
            if (shadow_array) {
                shadow_maps = shadow_array->entries;
            }
        }
    }

    execute_with_data(
        ctx.graphics,
        ctx.reads_fbos,
        ctx.writes_fbos,
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

void ColorPass::maybe_blit_to_debugger(
    GraphicsBackend* graphics,
    FramebufferHandle* fb,
    const std::string& entity_name,
    int width,
    int height
) {
    // New path: FrameGraphCapture (no context switch needed)
    // debug_internal_symbol already filters which entity to capture,
    // so we use capture_direct (no caller check needed)
    auto* cap = debug_capture();
    if (cap) {
        cap->capture_direct(fb, graphics);
        return;
    }

    // Old path: callback-based (for backward compatibility)
    if (!debugger_callbacks.is_set()) {
        return;
    }

    debugger_callbacks.blit_from_pass(
        debugger_callbacks.user_data,
        fb,
        graphics,
        width,
        height
    );
}

// Register ColorPass in tc_pass_registry for C#/standalone C++ usage
TC_REGISTER_FRAME_PASS(ColorPass);

} // namespace termin
