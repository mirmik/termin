#pragma once

#include <set>
#include <string>
#include <vector>
#include <memory>
#include <optional>
#include <array>
#include <algorithm>

#include "termin/render/frame_pass.hpp"
#include "termin/render/resource_spec.hpp"
#include "termin/render/render_context.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/render/render_state.hpp"
#include "termin/editor/frame_graph_debugger_core.hpp"
#include "termin/render/tc_shader_handle.hpp"
#include "termin/render/drawable.hpp"
#include "termin/entity/entity.hpp"
#include "termin/entity/component.hpp"
#include "termin/entity/cmp_ref.hpp"
#include "termin/camera/camera_component.hpp"
#include "termin/geom/mat44.hpp"
#include "tc_log.hpp"
#include "core/tc_scene.h"
#include "core/tc_scene_pool.h"
#include "tc_inspect_cpp.hpp"

namespace termin {

class GeometryPassBase : public CxxFramePass {
public:
    // Pass configuration
    std::string input_res;
    std::string output_res;
    std::string camera_name;  // Optional camera entity name for standalone use

    INSPECT_FIELD(GeometryPassBase, input_res, "Input Resource", "string")
    INSPECT_FIELD(GeometryPassBase, output_res, "Output Resource", "string")
    INSPECT_FIELD(GeometryPassBase, camera_name, "Camera Name", "string")

    struct DrawCall {
        Entity entity;
        tc_component* component;
        tc_shader_handle final_shader;  // Shader after override (skinning, etc.)
        int geometry_id = 0;
        int pick_id = 0;
    };

    std::vector<std::string> entity_names;

    std::vector<std::string> get_internal_symbols() const override {
        return entity_names;
    }

    // Dynamic resource computation based on current input_res/output_res values
    std::set<const char*> compute_reads() const override {
        return {input_res.c_str()};
    }

    std::set<const char*> compute_writes() const override {
        return {output_res.c_str()};
    }

    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override {
        return {{input_res, output_res}};
    }

    void destroy() override {
        _shader = TcShader();
    }

    // Find camera by entity name in scene
    // Returns nullptr if not found
    CameraComponent* find_camera_by_name(tc_scene_handle scene, const std::string& name) {
        if (name.empty() || !tc_scene_handle_valid(scene)) return nullptr;

        // Check cache - CmpRef.valid() checks entity liveness
        if (_cached_camera_name == name && _cached_camera.valid()) {
            return _cached_camera.get();
        }

        // Find entity by name
        tc_entity_id eid = tc_scene_find_entity_by_name(scene, name.c_str());
        if (!tc_entity_id_valid(eid)) {
            _cached_camera_name = name;
            _cached_camera.reset();
            return nullptr;
        }

        // Get CameraComponent from entity
        Entity ent(tc_scene_entity_pool(scene), eid);
        _cached_camera.reset(ent.get_component<CameraComponent>());
        _cached_camera_name = name;
        return _cached_camera.get();
    }

protected:
    // Cached camera lookup (CmpRef validates entity liveness)
    std::string _cached_camera_name;
    CmpRef<CameraComponent> _cached_camera;

    // Cached shader
    TcShader _shader;

    // Cached draw calls (reused between frames)
    mutable std::vector<DrawCall> cached_draw_calls_;

    GeometryPassBase(
        const std::string& name,
        const std::string& input,
        const std::string& output
    ) : input_res(input)
      , output_res(output)
    {
        set_pass_name(name);
    }

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

    // Setup extra uniforms for each draw call (MVP already set by base class)
    virtual void setup_extra_uniforms(
        const DrawCall& dc,
        TcShader& shader,
        RenderContext& context
    ) {
        // Default: no extra uniforms
        (void)dc;
        (void)shader;
        (void)context;
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
                get_pass_name()
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
        // New path: FrameGraphCapture (no context switch needed)
        auto* cap = debug_capture();
        if (cap) {
            cap->capture(this, fb, graphics);
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

    void collect_draw_calls(
        tc_scene_handle scene,
        uint64_t layer_mask,
        tc_shader_handle base_shader
    ) const {
        cached_draw_calls_.clear();

        if (!tc_scene_handle_valid(scene)) {
            return;
        }

        struct CollectContext {
            const GeometryPassBase* pass;
            std::vector<DrawCall>* draw_calls;
            tc_shader_handle base_shader;
        };

        auto callback = [](tc_component* c, void* user_data) -> bool {
            auto* ctx = static_cast<CollectContext*>(user_data);
            Entity ent(c->owner);

            if (!ctx->pass->entity_filter(ent)) {
                return true;
            }

            // Compute final shader with override (skinning, etc.)
            tc_shader_handle final_shader = tc_component_override_shader(
                c, ctx->pass->phase_name(), 0, ctx->base_shader
            );

            DrawCall dc;
            dc.entity = ent;
            dc.component = c;
            dc.final_shader = final_shader;
            dc.geometry_id = 0;
            dc.pick_id = ctx->pass->get_pick_id(ent);
            ctx->draw_calls->push_back(dc);
            return true;
        };

        CollectContext context{this, &cached_draw_calls_, base_shader};

        int filter_flags = TC_DRAWABLE_FILTER_ENABLED
                         | TC_DRAWABLE_FILTER_VISIBLE
                         | TC_DRAWABLE_FILTER_ENTITY_ENABLED;
        tc_scene_foreach_drawable(scene, callback, &context, filter_flags, layer_mask);
    }

    void sort_draw_calls_by_shader() const {
        if (cached_draw_calls_.size() <= 1) return;

        std::sort(cached_draw_calls_.begin(), cached_draw_calls_.end(),
            [](const DrawCall& a, const DrawCall& b) {
                return a.final_shader.index < b.final_shader.index;
            });
    }

    // Main execution method - call from derived execute_with_data
    void execute_geometry_pass(
        GraphicsBackend* graphics,
        const FBOMap& writes_fbos,
        const Rect4i& rect,
        tc_scene_handle scene,
        const Mat44f& view,
        const Mat44f& projection,
        uint64_t layer_mask
    ) {
        // Find output FBO
        auto it = writes_fbos.find(output_res);
        if (it == writes_fbos.end() || it->second == nullptr) {
            tc::Log::error("[GeometryPassBase] '%s': output FBO '%s' not found!",
                get_pass_name().c_str(), output_res.c_str());
            return;
        }
        FramebufferHandle* fb = dynamic_cast<FramebufferHandle*>(it->second);
        if (!fb) {
            tc::Log::error("[GeometryPassBase] '%s': output '%s' is not FramebufferHandle!",
                get_pass_name().c_str(), output_res.c_str());
            return;
        }

        // Bind and clear
        bind_and_clear(graphics, fb, rect);
        apply_default_render_state(graphics);

        // Get base shader
        TcShader& base_shader = get_shader(graphics);

        // Collect draw calls (computes final_shader during collection)
        collect_draw_calls(scene, layer_mask, base_shader.handle);

        // Sort by shader to minimize state changes
        sort_draw_calls_by_shader();

        // Render
        entity_names.clear();

        RenderContext context;
        context.view = view;
        context.projection = projection;
        context.graphics = graphics;
        context.phase = phase_name();

        const std::string& debug_symbol = get_debug_internal_point();

        // Track last shader to avoid redundant bindings
        tc_shader_handle last_shader = tc_shader_handle_invalid();
        std::set<std::string> seen_entities;

        for (const auto& dc : cached_draw_calls_) {
            Mat44f model = get_model_matrix(dc.entity);
            context.model = model;

            const char* name = dc.entity.name();
            if (name && seen_entities.insert(name).second) {
                entity_names.push_back(name);
            }

            // Use final shader (override already computed during collect)
            tc_shader_handle shader_handle = dc.final_shader;
            bool shader_changed = !tc_shader_handle_eq(shader_handle, last_shader);

            TcShader shader_to_use(shader_handle);

            if (shader_changed) {
                shader_to_use.use();
                // Set view/projection only when shader changes
                shader_to_use.set_uniform_mat4("u_view", view.data, false);
                shader_to_use.set_uniform_mat4("u_projection", projection.data, false);
                last_shader = shader_handle;
            }

            context.current_tc_shader = shader_to_use;

            // Set model matrix (always changes per object)
            shader_to_use.set_uniform_mat4("u_model", model.data, false);

            // Call virtual for any extra uniforms (e.g., near/far for depth pass)
            setup_extra_uniforms(dc, shader_to_use, context);

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
