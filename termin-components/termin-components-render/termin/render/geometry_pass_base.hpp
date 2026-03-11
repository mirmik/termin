#pragma once

#include <array>
#include <memory>
#include <optional>
#include <set>
#include <string>
#include <vector>

#include <tc_inspect_cpp.hpp>
#include <tgfx/graphics_backend.hpp>
#include <tgfx/render_state.hpp>
#include <tgfx/tgfx_shader_handle.hpp>

#include <termin/entity/component.hpp>
#include <termin/entity/entity.hpp>
#include <termin/geom/mat44.hpp>
#include <termin/render/drawable.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/render/frame_graph_debugger_core.hpp>
#include <termin/render/frame_pass.hpp>
#include <termin/render/render_context.hpp>
#include <termin/render/resource_spec.hpp>

extern "C" {
#include "core/tc_drawable_protocol.h"
#include "core/tc_scene.h"
#include "core/tc_scene_drawable.h"
#include "core/tc_scene_pool.h"
}

namespace termin {

class CameraComponent;

class GeometryPassBase : public CxxFramePass {
public:
    struct DrawCall {
    public:
        Entity entity;
        tc_component* component = nullptr;
        tc_shader_handle final_shader = tc_shader_handle_invalid();
        int geometry_id = 0;
        int pick_id = 0;
    };

public:
    std::string input_res;
    std::string output_res;
    std::string camera_name;
    std::vector<std::string> entity_names;

    INSPECT_FIELD(GeometryPassBase, input_res, "Input Resource", "string")
    INSPECT_FIELD(GeometryPassBase, output_res, "Output Resource", "string")
    INSPECT_FIELD(GeometryPassBase, camera_name, "Camera Name", "string")

protected:
    TcShader _shader;
    mutable std::vector<DrawCall> cached_draw_calls_;

protected:
    GeometryPassBase(
        const std::string& name,
        const std::string& input,
        const std::string& output
    );

public:
    std::vector<std::string> get_internal_symbols() const override;
    std::set<const char*> compute_reads() const override;
    std::set<const char*> compute_writes() const override;
    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override;
    void destroy() override;
    CameraComponent* find_camera_by_name(tc_scene_handle scene, const std::string& name) const;

protected:
    virtual const char* vertex_shader_source() const = 0;
    virtual const char* fragment_shader_source() const = 0;
    virtual std::array<float, 4> clear_color() const = 0;
    virtual const char* phase_name() const = 0;
    virtual std::optional<std::string> fbo_format() const;

    virtual void setup_extra_uniforms(
        const DrawCall& dc,
        TcShader& shader,
        RenderContext& context
    );

    virtual bool entity_filter(const Entity& ent) const;
    virtual int get_pick_id(const Entity& ent) const;

    TcShader& get_shader(GraphicsBackend* graphics);
    void bind_and_clear(
        GraphicsBackend* graphics,
        FramebufferHandle* fb,
        const Rect4i& rect
    ) const;
    void apply_default_render_state(GraphicsBackend* graphics) const;
    void maybe_blit_to_debugger(
        GraphicsBackend* graphics,
        FramebufferHandle* fb,
        const std::string& entity_name,
        int width,
        int height
    );
    void collect_draw_calls(
        tc_scene_handle scene,
        uint64_t layer_mask,
        tc_shader_handle base_shader
    ) const;
    void sort_draw_calls_by_shader() const;
    void execute_geometry_pass(
        GraphicsBackend* graphics,
        const FBOMap& writes_fbos,
        const Rect4i& rect,
        tc_scene_handle scene,
        const Mat44f& view,
        const Mat44f& projection,
        uint64_t layer_mask
    );
    std::vector<ResourceSpec> make_resource_specs() const;
};

} // namespace termin
