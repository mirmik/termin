#include "color_pass.hpp"
#include "tc_log.hpp"

#include <cmath>
#include <cstring>
#include <algorithm>
#include <numeric>

namespace termin {

namespace {

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

void ColorPass::collect_draw_calls(
    const std::vector<Entity>& entities,
    const std::string& phase_mark
) {
    // Clear but keep capacity
    cached_draw_calls_.clear();

    // Estimate capacity: ~2 draw calls per entity on average
    cached_draw_calls_.reserve(entities.size() * 2);

    for (const Entity& ent : entities) {
        if (!ent.visible() || !ent.enabled()) {
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

            // Filter by phase_mark
            if (!phase_mark.empty() && !tc_component_has_phase(tc, phase_mark.c_str())) {
                continue;
            }

            // Get geometry draws via vtable
            void* draws_ptr = tc_component_get_geometry_draws(tc, phase_mark.c_str());
            if (!draws_ptr) {
                continue;
            }

            auto* geometry_draws = static_cast<std::vector<GeometryDrawCall>*>(draws_ptr);
            for (const auto& gd : *geometry_draws) {
                if (gd.phase) {
                    cached_draw_calls_.push_back(PhaseDrawCall{
                        ent,
                        tc,
                        gd.phase,
                        gd.phase->priority,
                        gd.geometry_id
                    });
                }
            }
        }
    }
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
        float dist = static_cast<float>(std::sqrt(dx*dx + dy*dy + dz*dz));

        uint32_t dist_bits = float_to_sortable_uint(dist);
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
    const std::vector<Entity>& entities,
    const Mat44f& view,
    const Mat44f& projection,
    const Vec3& camera_position,
    int64_t context_key,
    const std::vector<Light>& lights,
    const Vec3& ambient_color,
    float ambient_intensity,
    const std::vector<ShadowMapEntry>& shadow_maps,
    const ShadowSettings& shadow_settings
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

    // Collect draw calls into cached vector
    collect_draw_calls(entities, phase_mark);

    // Compute sort keys and sort (single pass with combined priority+distance key)
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

    // Clear entity names cache but keep capacity
    entity_names.clear();
    entity_names.reserve(cached_draw_calls_.size());

    // Get debug symbol
    const std::string& debug_symbol = get_debug_internal_point();

    // Render each draw call
    for (const auto& dc : cached_draw_calls_) {
        // Cache entity name
        const char* ename = dc.entity.name();
        entity_names.push_back(ename ? ename : "");

        // Get model matrix
        Mat44f model = get_model_matrix(dc.entity);
        context.model = model;

        // Apply render state (override polygon mode if wireframe enabled)
        RenderState state = dc.phase->render_state;
        if (wireframe) {
            state.polygon_mode = PolygonMode::Line;
        }
        graphics->apply_render_state(state);

        // Get shader (allow drawable to override for skinning etc.)
        ShaderProgram* shader_to_use = dc.phase->shader.get();
        ShaderProgram* overridden = static_cast<ShaderProgram*>(
            tc_component_override_shader(dc.component, phase_mark.c_str(), dc.geometry_id, shader_to_use)
        );
        if (overridden != nullptr) {
            shader_to_use = overridden;
        }

        // Apply material uniforms to the (possibly overridden) shader
        dc.phase->apply_to_shader(shader_to_use, model, view, projection, graphics, context_key);

        // Upload camera position
        if (shader_to_use) {
            shader_to_use->set_uniform_vec3("u_camera_position",
                static_cast<float>(camera_position.x),
                static_cast<float>(camera_position.y),
                static_cast<float>(camera_position.z));

            // Upload view matrix (needed for cascade depth calculation in shader)
            shader_to_use->set_uniform_matrix4("u_view", view, false);

            // Upload lights with entity name for debugging
            upload_lights_to_shader(shader_to_use, lights, ename);

            // Upload ambient
            upload_ambient_to_shader(shader_to_use, ambient_color, ambient_intensity);

            // Upload shadow maps and cascade settings
            upload_shadow_maps_to_shader(shader_to_use, shadow_maps);
            upload_shadow_settings_to_shader(shader_to_use, shadow_settings);
            upload_cascade_settings_to_shader(shader_to_use, lights);

            // Debug: log shadow settings (once per frame, first entity only)
            static bool logged_shadow_settings = false;
            if (!logged_shadow_settings && !shadow_maps.empty()) {
                tc::Log::info("Shadow settings: method=%d, softness=%.3f, bias=%.5f, maps=%zu",
                    shadow_settings.method, shadow_settings.softness, shadow_settings.bias,
                    shadow_maps.size());
                logged_shadow_settings = true;
            }

            context.current_shader = shader_to_use;
        }

        // Draw geometry via vtable
        tc_component_draw_geometry(dc.component, &context, dc.geometry_id);
        graphics->check_gl_error(ename ? ename : "ColorPass: draw_geometry");

        // Check for debug blit (use std::string comparison to avoid pointer issues)
        if (!debug_symbol.empty() && ename && debug_symbol == ename) {
            maybe_blit_to_debugger(graphics, fb, ename, rect.width, rect.height);
        }
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
