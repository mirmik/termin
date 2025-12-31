#include "color_pass.hpp"
#include "tc_log.hpp"

#include <cmath>

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
Vec3 get_global_position(const Entity& entity) {
    return entity.transform().global_pose().lin;
}

} // anonymous namespace

ColorPass::ColorPass(
    const std::string& input_res,
    const std::string& output_res,
    const std::string& shadow_res,
    const std::string& phase_mark,
    const std::string& pass_name,
    bool sort_by_distance,
    bool clear_depth
) : RenderFramePass(pass_name, {input_res}, {output_res}),
    input_res(input_res),
    output_res(output_res),
    shadow_res(shadow_res),
    phase_mark(phase_mark),
    sort_by_distance(sort_by_distance),
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

std::vector<PhaseDrawCall> ColorPass::collect_draw_calls(
    const std::vector<Entity>& entities,
    const std::string& phase_mark
) {
    std::vector<PhaseDrawCall> draw_calls;

    for (const Entity& ent : entities) {
        if (!ent.active() || !ent.visible()) {
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
                    draw_calls.push_back(PhaseDrawCall{
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

    // Sort by priority
    std::sort(draw_calls.begin(), draw_calls.end(),
        [](const PhaseDrawCall& a, const PhaseDrawCall& b) {
            return a.priority < b.priority;
        });

    return draw_calls;
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
    graphics->set_viewport(0, 0, rect.width, rect.height);

    // Clear depth if requested
    if (clear_depth) {
        graphics->clear_depth();
    }

    // Create render context
    RenderContext context;
    context.view = view;
    context.projection = projection;
    context.context_key = context_key;
    context.graphics = graphics;
    context.phase = phase_mark;

    // Collect draw calls
    std::vector<PhaseDrawCall> draw_calls = collect_draw_calls(entities, phase_mark);

    // Sort by distance if requested (back-to-front for transparency)
    if (sort_by_distance) {
        std::sort(draw_calls.begin(), draw_calls.end(),
            [&camera_position](const PhaseDrawCall& a, const PhaseDrawCall& b) {
                Vec3 pos_a = get_global_position(a.entity);
                Vec3 pos_b = get_global_position(b.entity);
                double dist_a = (pos_a - camera_position).norm();
                double dist_b = (pos_b - camera_position).norm();
                return dist_a > dist_b;  // back-to-front
            });
    }

    // Clear entity names cache
    entity_names.clear();

    // Get debug symbol
    const std::string& debug_symbol = get_debug_internal_point();

    // Render each draw call
    for (const auto& dc : draw_calls) {
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

        // Apply material (binds shader, uploads MVP, textures, uniforms)
        dc.phase->apply(model, view, projection, graphics, context_key);

        // Upload camera position
        if (dc.phase->shader) {
            dc.phase->shader->set_uniform_vec3("u_camera_position",
                static_cast<float>(camera_position.x),
                static_cast<float>(camera_position.y),
                static_cast<float>(camera_position.z));

            // Upload lights with entity name for debugging
            upload_lights_to_shader(dc.phase->shader.get(), lights, ename);

            // Upload ambient
            upload_ambient_to_shader(dc.phase->shader.get(), ambient_color, ambient_intensity);

            // Upload shadow maps
            upload_shadow_maps_to_shader(dc.phase->shader.get(), shadow_maps);
            upload_shadow_settings_to_shader(dc.phase->shader.get(), shadow_settings);

            context.current_shader = dc.phase->shader.get();
        }

        // Draw geometry via vtable
        tc_component_draw_geometry(dc.component, &context, dc.geometry_id.c_str());

        // Check for debug blit
        if (!debug_symbol.empty() && ename && ename == debug_symbol) {
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
