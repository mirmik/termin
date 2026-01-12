#pragma once

#include <set>
#include <string>
#include <vector>

#include <nanobind/nanobind.h>

#include "termin/render/render_frame_pass.hpp"
#include "termin/render/render_context.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/render/render_state.hpp"
#include "termin/render/shader_program.hpp"
#include "termin/render/drawable.hpp"
#include "termin/entity/entity.hpp"
#include "termin/entity/component.hpp"
#include "termin/geom/mat44.hpp"
#include "tc_log.hpp"
#include "tc_scene.h"

namespace nb = nanobind;

namespace termin {

class GeometryPassBase : public RenderFramePass {
public:
    using RenderFramePass::RenderFramePass;

    std::vector<std::string> entity_names;

    std::vector<std::string> get_internal_symbols() const override {
        return entity_names;
    }

protected:
    static Mat44f get_model_matrix(const Entity& entity) {
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

    void bind_and_clear(
        GraphicsBackend* graphics,
        FramebufferHandle* fb,
        const Rect4i& rect,
        float r,
        float g,
        float b,
        float a
    ) const {
        graphics->bind_framebuffer(fb);
        graphics->set_viewport(0, 0, rect.width, rect.height);
        graphics->clear_color_depth(r, g, b, a);
    }

    void apply_default_render_state(GraphicsBackend* graphics) const {
        RenderState state;
        state.depth_test = true;
        state.depth_write = true;
        state.blend = false;
        state.cull = true;
        graphics->apply_render_state(state);
    }

    void maybe_blit_to_debugger(
        GraphicsBackend* graphics,
        FramebufferHandle* fb,
        const std::string& entity_name,
        int width,
        int height
    ) {
        if (debugger_window.is_none()) {
            return;
        }

        try {
            debugger_window.attr("blit_from_pass")(
                nb::cast(fb, nb::rv_policy::reference),
                nb::cast(graphics, nb::rv_policy::reference),
                width,
                height,
                depth_capture_callback
            );
        } catch (const nb::python_error& e) {
            tc::Log::error(e, "GeometryPassBase::blit_to_debugger_window");
        }
    }

    template <typename EntityFilter, typename Emit>
    void collect_draw_calls_common(
        tc_scene* scene,
        uint64_t layer_mask,
        EntityFilter& entity_filter,
        Emit& emit
    ) const {
        if (!scene) {
            return;
        }

        tc_entity_pool* pool = tc_scene_entity_pool(scene);
        if (!pool) {
            return;
        }

        struct CollectContext {
            EntityFilter* filter;
            Emit* emit;
            uint64_t layer_mask;
        };

        auto callback = [](tc_entity_pool* pool, tc_entity_id id, void* user_data) -> bool {
            auto* data = static_cast<CollectContext*>(user_data);

            if (!tc_entity_pool_visible(pool, id) || !tc_entity_pool_enabled(pool, id)) {
                return true;
            }

            uint64_t entity_layer = tc_entity_pool_layer(pool, id);
            if (!(data->layer_mask & (1ULL << entity_layer))) {
                return true;
            }

            Entity ent(pool, id);
            if (!(*data->filter)(ent)) {
                return true;
            }

            size_t comp_count = ent.component_count();
            for (size_t ci = 0; ci < comp_count; ci++) {
                tc_component* tc = ent.component_at(ci);
                if (!tc || !tc->enabled) {
                    continue;
                }

                if (!tc_component_is_drawable(tc)) {
                    continue;
                }

                (*data->emit)(ent, tc);
            }

            return true;
        };

        CollectContext context{&entity_filter, &emit, layer_mask};
        tc_entity_pool_foreach(pool, callback, &context);
    }

    template <typename DrawCall, typename SetupUniforms, typename MaybeBlit>
    void render_draw_calls(
        const std::vector<DrawCall>& draw_calls,
        GraphicsBackend* graphics,
        ShaderProgram* base_shader,
        const Mat44f& view,
        const Mat44f& projection,
        int64_t context_key,
        const char* phase,
        nb::dict& extra_uniforms,
        const Rect4i& rect,
        SetupUniforms&& setup_uniforms,
        MaybeBlit&& maybe_blit
    ) {
        entity_names.clear();
        std::set<std::string> seen_entities;

        RenderContext context;
        context.view = view;
        context.projection = projection;
        context.context_key = context_key;
        context.graphics = graphics;
        context.phase = phase;
        context.current_shader = base_shader;
        context.extra_uniforms = extra_uniforms;

        const std::string& debug_symbol = get_debug_internal_point();

        for (const auto& dc : draw_calls) {
            Mat44f model = get_model_matrix(dc.entity);
            context.model = model;

            const char* name = dc.entity.name();
            if (name && seen_entities.insert(name).second) {
                entity_names.push_back(name);
            }

            ShaderProgram* shader_to_use = static_cast<ShaderProgram*>(
                tc_component_override_shader(dc.component, phase, 0, base_shader)
            );
            if (shader_to_use == nullptr) {
                shader_to_use = base_shader;
            }

            shader_to_use->ensure_ready([graphics](const char* v, const char* f, const char* g) {
                return graphics->create_shader(v, f, g);
            });
            shader_to_use->use();

            setup_uniforms(dc, shader_to_use, model, view, projection, context);

            context.current_shader = shader_to_use;

            tc_component_draw_geometry(dc.component, &context, 0);

            if (!debug_symbol.empty() && name && debug_symbol == name) {
                maybe_blit(name, rect.width, rect.height);
            }
        }
    }
};

} // namespace termin
