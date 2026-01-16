#include "color_pass.hpp"
#include "tc_shader_handle.hpp"
#include "tc_log.hpp"
#include "termin/lighting/lighting_upload.hpp"
extern "C" {
#include "tc_shader.h"
#include "tc_shader_registry.h"
#include "tc_profiler.h"
#include "tc_component.h"
#include "tc_material.h"
#include "tc_gpu.h"
}

#include <cmath>
#include <cstring>
#include <algorithm>
#include <numeric>

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

// Get model matrix from Entity as Mat44f.
// GeneralTransform3::world_matrix outputs row-major double[16], Mat44f is column-major float.
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
    bool clear_depth
) : RenderFramePass(pass_name, {input_res}, {output_res}),
    input_res(input_res),
    output_res(output_res),
    shadow_res(shadow_res),
    phase_mark(phase_mark),
    sort_mode(sort_mode),
    clear_depth(clear_depth)
{
    // Add shadow_res to reads if not empty
    if (!shadow_res.empty()) {
        reads.insert(shadow_res);
    }
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
    Entity ent(tc->owner_pool, tc->owner_entity_id);

    auto* geometry_draws = static_cast<std::vector<GeometryDrawCall>*>(draws_ptr);
    for (const auto& gd : *geometry_draws) {
        if (gd.phase) {
            data->draw_calls->push_back(PhaseDrawCall{
                ent,
                tc,
                gd.phase,
                gd.phase->priority,
                gd.geometry_id
            });
        }
    }

    return true;
}

} // anonymous namespace

void ColorPass::collect_draw_calls(
    tc_scene* scene,
    const std::string& phase_mark,
    uint64_t layer_mask
) {
    // Clear but keep capacity
    cached_draw_calls_.clear();

    if (!scene) {
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
    // sort_key format: [priority:32][distance:32]
    // For near_to_far: lower distance = lower key
    // For far_to_near: lower distance = higher key (invert distance bits)
    bool invert_distance = (sort_mode == "far_to_near");

    for (size_t i = 0; i < n; ++i) {
        const PhaseDrawCall& dc = cached_draw_calls_[i];

        // Priority in upper 32 bits
        uint64_t priority_bits = static_cast<uint32_t>(dc.priority + 0x80000000); // offset to handle negative

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

        sort_keys_[i] = (priority_bits << 32) | dist_bits;
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
    tc_scene* scene,
    const Mat44f& view,
    const Mat44f& projection,
    const Vec3& camera_position,
    int64_t context_key,
    const std::vector<Light>& lights,
    const Vec3& ambient_color,
    float ambient_intensity,
    const std::vector<ShadowMapEntry>& shadow_maps,
    const ShadowSettings& shadow_settings,
    uint64_t layer_mask
) {
    // Get output framebuffer
    auto it = writes_fbos.find(output_res);
    if (it == writes_fbos.end() || it->second == nullptr) {
        return;
    }
    FramebufferHandle* fb = it->second;

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
    context.context_key = context_key;
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

    // Render each draw call
    if (detailed) {
        tc_profiler_begin_section("DrawCalls");
    }

    // Clear any accumulated GL errors before rendering
    graphics->clear_gl_errors();

    // Track last shader to avoid redundant shadow map uploads
    tc_shader_handle last_shader_handle = tc_shader_handle_invalid();

    for (const auto& dc : cached_draw_calls_)
    {
        if (detailed) {
            tc_profiler_begin_section("Prep.ModelMatrix");
        }

        // Cache entity name
        const char* ename = dc.entity.name();
        entity_names.push_back(ename ? ename : "");

        // Get model matrix
        Mat44f model = get_model_matrix(dc.entity);
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
        graphics->apply_render_state(state);

        if (detailed) {
            tc_profiler_end_section();
            tc_profiler_begin_section("Prep.OverrideShader");
        }

        // Get shader handle and apply override
        tc_shader_handle base_handle = dc.phase->shader;

        // Debug: trace shader source for skinned meshes
        static int shader_trace_count = 0;
        if (shader_trace_count < 10) {
            const char* type_name = tc_component_type_name(dc.component);
            if (type_name && std::strcmp(type_name, "SkinnedMeshRenderer") == 0) {
                TcShader base_shader(base_handle);
                // Also check shader sources
                const char* vert_src = base_shader.vertex_source();
                const char* frag_src = base_shader.fragment_source();
                size_t vert_len = vert_src ? std::strlen(vert_src) : 0;
                size_t frag_len = frag_src ? std::strlen(frag_src) : 0;
                tc::Log::info("[ColorPass] SkinnedMesh: entity='%s' base_shader='%s' uuid='%.8s' valid=%d vert_len=%zu frag_len=%zu phase_mark='%s'",
                              ename ? ename : "(null)",
                              base_shader.name() ? base_shader.name() : "(null)",
                              base_shader.uuid() ? base_shader.uuid() : "(null)",
                              base_shader.is_valid() ? 1 : 0,
                              vert_len, frag_len,
                              dc.phase->phase_mark);
                shader_trace_count++;
            }
        }

        tc_shader_handle shader_handle = tc_component_override_shader(
            dc.component, phase_mark.c_str(), dc.geometry_id, base_handle
        );

        // Use TcShader for everything
        TcShader shader_to_use(shader_handle);

        if (detailed) {
            tc_profiler_end_section();
            tc_profiler_begin_section("Prep.ApplyMaterial");
        }

        // Compile and use shader
        shader_to_use.use();
        if (graphics->check_gl_error("after shader.use()")) {
            tc::Log::error("  shader: %s, program=%u", shader_to_use.name(), shader_to_use.gpu_program());
        }

        // Apply material uniforms (textures, uniforms, MVP matrices)
        tc_shader* raw_shader = tc_shader_get(shader_handle);
        if (raw_shader) {
            // Clear any pending GL errors before apply
            graphics->clear_gl_errors();

            tc_material_phase_apply_with_mvp(
                dc.phase,
                raw_shader,
                model.data,
                view.data,
                projection.data
            );
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
        static int ubo_debug_count = 0;
        if (ubo_active) {
            bool has_ubo_feature = shader_to_use.has_feature(TC_SHADER_FEATURE_LIGHTING_UBO);
            if (ubo_debug_count < 5) {
                tc::Log::info("[ColorPass] shader='%s' has_lighting_ubo=%d features=%u",
                             shader_to_use.name(), has_ubo_feature ? 1 : 0, shader_to_use.features());
                ubo_debug_count++;
            }
            if (has_ubo_feature) {
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

        // Draw geometry via vtable
        tc_component_draw_geometry(dc.component, &context, dc.geometry_id);
        if (graphics->check_gl_error("after draw_geometry")) {
            tc::Log::error("  entity: %s, shader: %s", ename ? ename : "(null)", shader_to_use.name());
        }

        if (detailed) {
            tc_profiler_end_section(); // DrawGeometry
        }

        // Check for debug blit (use std::string comparison to avoid pointer issues)
        if (!debug_symbol.empty() && ename && debug_symbol == ename) {
            maybe_blit_to_debugger(graphics, fb, ename, rect.width, rect.height);
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

void ColorPass::execute(
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

void ColorPass::maybe_blit_to_debugger(
    GraphicsBackend* graphics,
    FramebufferHandle* fb,
    const std::string& entity_name,
    int width,
    int height
) {
    // Check if debugger window is set
    if (debugger_window.is_none()) {
        return;
    }

    try {
        // Call Python debugger_window.blit_from_pass(fb, width, height, depth_callback)
        debugger_window.attr("blit_from_pass")(
            nb::cast(fb, nb::rv_policy::reference),
            nb::cast(graphics, nb::rv_policy::reference),
            width,
            height,
            depth_capture_callback
        );
    } catch (const nb::python_error& e) {
        tc::Log::error(e, "ColorPass::blit_to_debugger_window");
    }
}

} // namespace termin
