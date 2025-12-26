#include "color_pass.hpp"

#include <cmath>

namespace termin {

namespace {

/**
 * Get model matrix from Entity as Mat44f.
 * Entity::model_matrix outputs row-major double[16], Mat44f is column-major float.
 */
Mat44f get_model_matrix(Entity* entity) {
    double m_row[16];
    entity->model_matrix(m_row);

    // Transpose from row-major to column-major
    Mat44f result;
    for (int col = 0; col < 4; ++col) {
        for (int row = 0; row < 4; ++row) {
            result(col, row) = static_cast<float>(m_row[row * 4 + col]);
        }
    }
    return result;
}

/**
 * Get global position from Entity.
 */
Vec3 get_global_position(Entity* entity) {
    return entity->global_pose().lin;
}

} // anonymous namespace

ColorPass::ColorPass(
    const std::string& input_res,
    const std::string& output_res,
    const std::string& phase_mark,
    const std::string& pass_name,
    bool sort_by_distance,
    bool clear_depth
) : RenderFramePass(pass_name, {input_res}, {output_res}),
    input_res(input_res),
    output_res(output_res),
    phase_mark(phase_mark),
    sort_by_distance(sort_by_distance),
    clear_depth(clear_depth)
{
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
    const std::vector<Entity*>& entities,
    const std::string& phase_mark
) {
    std::vector<PhaseDrawCall> draw_calls;

    for (Entity* entity : entities) {
        if (!entity->active || !entity->visible) {
            continue;
        }

        // Get drawable components from entity
        for (Component* component : entity->components) {
            if (!component->enabled) {
                continue;
            }

            // Try to cast to Drawable
            Drawable* drawable = dynamic_cast<Drawable*>(component);
            if (!drawable) {
                continue;
            }

            // Filter by phase_mark
            if (!phase_mark.empty() && !drawable->has_phase(phase_mark)) {
                continue;
            }

            // Get geometry draws
            std::vector<GeometryDrawCall> geometry_draws = drawable->get_geometry_draws(&phase_mark);

            for (const auto& gd : geometry_draws) {
                if (gd.phase) {
                    draw_calls.push_back(PhaseDrawCall{
                        entity,
                        drawable,
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
    const std::vector<Entity*>& entities,
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
        entity_names.push_back(dc.entity->name);

        // Get model matrix
        Mat44f model = get_model_matrix(dc.entity);
        context.model = model;

        // Apply render state
        graphics->apply_render_state(dc.phase->render_state);

        // Apply material (binds shader, uploads MVP, textures, uniforms)
        dc.phase->apply(model, view, projection, graphics, context_key);

        // Upload camera position
        if (dc.phase->shader) {
            dc.phase->shader->set_uniform_vec3("u_camera_position",
                static_cast<float>(camera_position.x),
                static_cast<float>(camera_position.y),
                static_cast<float>(camera_position.z));

            // Upload lights
            upload_lights_to_shader(dc.phase->shader.get(), lights);

            // Upload ambient
            upload_ambient_to_shader(dc.phase->shader.get(), ambient_color, ambient_intensity);

            // Upload shadow maps
            upload_shadow_maps_to_shader(dc.phase->shader.get(), shadow_maps);
            upload_shadow_settings_to_shader(dc.phase->shader.get(), shadow_settings);

            context.current_shader = dc.phase->shader.get();
        }

        // Draw geometry
        dc.drawable->draw_geometry(context, dc.geometry_id);

        // Check for debug blit
        if (!debug_symbol.empty() && dc.entity->name == debug_symbol) {
            maybe_blit_to_debugger(graphics, fb, dc.entity->name, rect.width, rect.height);
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
            py::cast(fb, py::return_value_policy::reference),
            py::cast(graphics, py::return_value_policy::reference),
            width,
            height,
            depth_capture_callback
        );
    } catch (const py::error_already_set& e) {
        // Log error but don't crash rendering
        // In production, you might want proper logging
    }
}

} // namespace termin
