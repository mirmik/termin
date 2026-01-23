#pragma once

#include <set>
#include <string>
#include <vector>
#include <memory>
#include <optional>
#include <array>

#include "termin/render/render_frame_pass.hpp"
#include "termin/render/resource_spec.hpp"
#include "termin/render/render_context.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/render/render_state.hpp"
#include "termin/render/tc_shader_handle.hpp"
#include "termin/render/drawable.hpp"
#include "termin/entity/entity.hpp"
#include "termin/entity/component.hpp"
#include "termin/geom/mat44.hpp"
#include "tc_log.hpp"
#include "tc_scene.h"
#ifdef TERMIN_HAS_NANOBIND
#include "tc_inspect.hpp"
#else
#include "tc_inspect_cpp.hpp"
#endif

namespace termin {

class GeometryPassBase : public RenderFramePass {
public:
    // Pass configuration
    std::string input_res;
    std::string output_res;

    INSPECT_FIELD(GeometryPassBase, input_res, "Input Resource", "string")
    INSPECT_FIELD(GeometryPassBase, output_res, "Output Resource", "string")

    struct DrawCall {
        Entity entity;
        tc_component* component;
        int geometry_id = 0;
        int pick_id = 0;
    };

    std::vector<std::string> entity_names;

    std::vector<std::string> get_internal_symbols() const override {
        return entity_names;
    }

    void destroy() override {
        _shader = TcShader();
    }

protected:
    // Cached shader
    TcShader _shader;

    GeometryPassBase(
        const std::string& name,
        const std::string& input,
        const std::string& output
    ) : RenderFramePass(name, {input}, {output})
      , input_res(input)
      , output_res(output)
    {}

    // --- Virtual methods for customization ---

    // Return vertex shader source
    virtual const char* vertex_shader_source() const = 0;

    // Return fragment shader source
    virtual const char* fragment_shader_source() const = 0;

    // Return clear color (RGBA)
    virtual std::array<float, 4> clear_color() const = 0;

    // Return phase name for shader override
    virtual const char* phase_name() const = 0;

    // Return FBO format (nullopt = default RGBA8)
    virtual std::optional<std::string> fbo_format() const { return std::nullopt; }

    // Setup uniforms for each draw call
    virtual void setup_draw_uniforms(
        const DrawCall& dc,
        TcShader& shader,
        const Mat44f& model,
        const Mat44f& view,
        const Mat44f& projection,
        RenderContext& context
    ) {
        shader.set_uniform_mat4("u_model", model.data, false);
        shader.set_uniform_mat4("u_view", view.data, false);
        shader.set_uniform_mat4("u_projection", projection.data, false);
    }

    // Entity filter (return false to skip entity)
    virtual bool entity_filter(const Entity& ent) const {
        (void)ent;
        return true;
    }

    // Get pick ID for entity
    virtual int get_pick_id(const Entity& ent) const {
        (void)ent;
        return 0;
    }

    // --- Helper methods ---

    TcShader& get_shader(GraphicsBackend* graphics) {
        if (!_shader.is_valid()) {
            _shader = TcShader::from_sources(
                vertex_shader_source(),
                fragment_shader_source(),
                "",
                pass_name
            );
            _shader.ensure_ready();
        }
        return _shader;
    }

    // world_matrix outputs column-major, same as Mat44f
    static Mat44f get_model_matrix(const Entity& entity) {
        double m[16];
        entity.transform().world_matrix(m);

        Mat44f result;
        for (int i = 0; i < 16; ++i) {
            result.data[i] = static_cast<float>(m[i]);
        }
        return result;
    }

    void bind_and_clear(
        GraphicsBackend* graphics,
        FramebufferHandle* fb,
        const Rect4i& rect
    ) const {
        auto cc = clear_color();
        graphics->bind_framebuffer(fb);
        graphics->set_viewport(0, 0, rect.width, rect.height);
        graphics->clear_color_depth(cc[0], cc[1], cc[2], cc[3]);
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

    std::vector<DrawCall> collect_draw_calls(
        tc_scene* scene,
        uint64_t layer_mask
    ) const {
        std::vector<DrawCall> draw_calls;

        if (!scene) {
            return draw_calls;
        }

        struct CollectContext {
            const GeometryPassBase* pass;
            std::vector<DrawCall>* draw_calls;
        };

        auto callback = [](tc_component* c, void* user_data) -> bool {
            auto* ctx = static_cast<CollectContext*>(user_data);
            Entity ent(c->owner_pool, c->owner_entity_id);

            if (!ctx->pass->entity_filter(ent)) {
                return true;
            }

            DrawCall dc;
            dc.entity = ent;
            dc.component = c;
            dc.geometry_id = 0;
            dc.pick_id = ctx->pass->get_pick_id(ent);
            ctx->draw_calls->push_back(dc);
            return true;
        };

        CollectContext context{this, &draw_calls};

        int filter_flags = TC_DRAWABLE_FILTER_ENABLED
                         | TC_DRAWABLE_FILTER_VISIBLE
                         | TC_DRAWABLE_FILTER_ENTITY_ENABLED;
        tc_scene_foreach_drawable(scene, callback, &context, filter_flags, layer_mask);

        return draw_calls;
    }

    // Main execution method - call from derived execute_with_data
    void execute_geometry_pass(
        GraphicsBackend* graphics,
        const FBOMap& writes_fbos,
        const Rect4i& rect,
        tc_scene* scene,
        const Mat44f& view,
        const Mat44f& projection,
        int64_t context_key,
        uint64_t layer_mask
    ) {
        // Find output FBO
        auto it = writes_fbos.find(output_res);
        if (it == writes_fbos.end() || it->second == nullptr) {
            return;
        }
        FramebufferHandle* fb = it->second;

        // Bind and clear
        bind_and_clear(graphics, fb, rect);
        apply_default_render_state(graphics);

        // Get shader
        TcShader& shader = get_shader(graphics);

        // Collect draw calls
        auto draw_calls = collect_draw_calls(scene, layer_mask);

        // Render
        entity_names.clear();
        std::set<std::string> seen_entities;

        RenderContext context;
        context.view = view;
        context.projection = projection;
        context.context_key = context_key;
        context.graphics = graphics;
        context.phase = phase_name();
        context.current_tc_shader = shader;

        const std::string& debug_symbol = get_debug_internal_point();

        for (const auto& dc : draw_calls) {
            Mat44f model = get_model_matrix(dc.entity);
            context.model = model;

            const char* name = dc.entity.name();
            if (name && seen_entities.insert(name).second) {
                entity_names.push_back(name);
            }

            // Get shader handle and apply override
            tc_shader_handle base_handle = shader.handle;
            tc_shader_handle shader_handle = tc_component_override_shader(
                dc.component, phase_name(), dc.geometry_id, base_handle
            );

            // Use TcShader for everything
            TcShader shader_to_use(shader_handle);
            shader_to_use.use();

            context.current_tc_shader = shader_to_use;

            // Set uniforms via virtual method (allows derived classes to add custom uniforms)
            setup_draw_uniforms(dc, shader_to_use, model, view, projection, context);

            tc_component_draw_geometry(dc.component, &context, dc.geometry_id);

            if (!debug_symbol.empty() && name && debug_symbol == name) {
                maybe_blit_to_debugger(graphics, fb, name, rect.width, rect.height);
            }
        }
    }

    // Generate resource spec with pass-specific settings
    std::vector<ResourceSpec> make_resource_specs() const {
        auto format = fbo_format();
        return {
            ResourceSpec(
                input_res,
                "fbo",
                std::nullopt,
                std::array<double, 4>{
                    clear_color()[0],
                    clear_color()[1],
                    clear_color()[2],
                    clear_color()[3]
                },
                1.0f,
                format,
                1
            )
        };
    }
};

} // namespace termin
