#pragma once

#include <array>
#include <cstddef>
#include <memory>
#include <optional>
#include <set>
#include <string>
#include <vector>

#include <tc_inspect_cpp.hpp>
#include <tgfx/tgfx_shader_handle.hpp>

#include <termin/entity/component.hpp>
#include <termin/entity/entity.hpp>
#include <termin/geom/mat44.hpp>
#include <termin/render/drawable.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/render/frame_graph_debugger_core.hpp>
#include <termin/render/frame_pass.hpp>
#include <termin/render/resource_spec.hpp>

extern "C" {
#include "core/tc_drawable_protocol.h"
#include "core/tc_scene.h"
#include "core/tc_scene_drawable.h"
#include "core/tc_scene_pool.h"
}

namespace termin {

class CameraComponent;

class ENTITY_API GeometryPassBase : public CxxFramePass {
public:
    struct DrawCall {
    public:
        Entity entity;
        tc_component* component = nullptr;
        tc_shader_handle final_shader = tc_shader_handle_invalid();
        tc_material_phase* material_phase = nullptr;
        tc_material_handle material = tc_material_handle_invalid();
        tc_render_item item{};
        size_t phase_index = SIZE_MAX;
        int geometry_id = 0;
        int pick_id = 0;

        tc_material_phase* resolve_material_phase() const {
            if (!tc_material_handle_is_invalid(material) && phase_index != SIZE_MAX) {
                tc_material* mat = tc_material_get(material);
                if (mat && phase_index < mat->phase_count) {
                    return &mat->phases[phase_index];
                }
            }
            return material_phase;
        }
    };

public:
    std::string input_res;
    std::string output_res;
    std::string camera_name;
    std::vector<std::string> entity_names;

    INSPECT_FIELD(GeometryPassBase, input_res, "Input Resource", "string")
    INSPECT_FIELD(GeometryPassBase, output_res, "Output Resource", "string")
    INSPECT_FIELD(GeometryPassBase, camera_name, "Camera Name", "string")
    INSPECT_TYPE_METADATA(GeometryPassBase, graph, make_pass_graph_metadata(
        {{"input_res", "fbo"}},
        {{"output_res", "fbo"}},
        {{"input_res", "output_res"}}
    ))

protected:
    mutable std::vector<DrawCall> cached_draw_calls_;

protected:
    GeometryPassBase(
        const std::string& name,
        const std::string& input,
        const std::string& output
    );

public:
    std::vector<std::string> get_internal_symbols() const override;
    void collect_shader_usages(
        tc_scene_handle scene,
        const std::function<void(TcShader)>& emit
    ) const override;
    std::set<const char*> compute_reads() const override;
    std::set<const char*> compute_writes() const override;
    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override;
    void destroy() override;
    CameraComponent* find_camera_by_name(tc_scene_handle scene, const std::string& name) const;

protected:
    virtual std::array<float, 4> clear_color() const = 0;

    // Drawable/material routing label requested by this pass. It is mandatory
    // when asking drawables for geometry, but it is not a shader layout or pass
    // kind selector. Custom passes should use project-owned labels here freely
    // while describing vertex layout/resources through shader_pass_contract().
    virtual const char* phase_mark() const = 0;

    virtual bool uses_material_phase_shader_override() const;

    // Explicit pass-owned shader intent consumed by material pipeline and
    // drawable shader override paths. This is the only place GeometryPassBase
    // subclasses should declare vertex transform, skinned/foliage template,
    // fragment interface, and pass resource requirements.
    virtual MaterialPipelinePassContract shader_pass_contract() const = 0;

    virtual tc_shader_handle shader_usage_base_shader() const = 0;
    virtual std::optional<std::string> fbo_format() const;

    virtual bool entity_filter(const Entity& ent) const;
    virtual int get_pick_id(const Entity& ent) const;

    void collect_draw_calls(
        tc_scene_handle scene,
        uint64_t layer_mask,
        uint64_t render_category_mask,
        tc_shader_handle base_shader
    ) const;
    void sort_draw_calls_by_shader() const;
    std::vector<ResourceSpec> make_resource_specs() const;
};

} // namespace termin
