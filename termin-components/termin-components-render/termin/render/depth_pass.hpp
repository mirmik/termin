#pragma once

#include <cstddef>

#include <termin/render/geometry_pass_base.hpp>
#include "tgfx2/handles.hpp"
#include "tgfx2/i_render_device.hpp"
extern "C" {
#include <tgfx/resources/tc_shader_registry.h>
}

namespace termin {

struct DepthPassExecuteData {
    Rect2i rect;
    tc_scene_handle scene = {};
    Mat44f view;
    Mat44f projection;
    float near_plane = 0.1f;
    float far_plane = 1000.0f;
    uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL;
};

class ENTITY_API DepthPass : public GeometryPassBase {
private:
    float _near_plane = 0.1f;
    float _far_plane = 1000.0f;

    // Lazy tgfx2 resources used by execute_with_data_tgfx2. Shader lives
    // on the tc_shader registry (hash-based dedup across pass re-creations)
    // so Play/Stop doesn't re-run shaderc — see ShadowPass for the same
    // pattern.
    tgfx::IRenderDevice* device2_ = nullptr;
    mutable tc_shader_handle depth_shader_handle_ = tc_shader_handle_invalid();

    void ensure_tgfx2_resources(tgfx::IRenderDevice& device);
    void release_tgfx2_resources();

public:
    std::string depth_encoding = "linear";
    // Drawable/material representation requested by depth passes. The depth
    // shader ABI is declared by shader_pass_contract(), not inferred from the
    // label value.
    std::string pass_phase_mark = "depth";
    bool clear = true;

    INSPECT_FIELD_ACCESSORS(DepthPass, std::string, phase_mark, "Phase Mark", "string",
        ([](DepthPass* self) { return self->pass_phase_mark; }),
        ([](DepthPass* self, std::string value) { self->pass_phase_mark = value; }))
    INSPECT_FIELD_CHOICES(DepthPass, depth_encoding, "Depth Encoding", "string",
        {"linear", "Linear"},
        {"linear_inverse", "Linear Inverse"},
        {"perspective", "Perspective"},
        {"perspective_inverse", "Perspective Inverse"},
        {"logarithmic", "Logarithmic"},
        {"logarithmic_inverse", "Logarithmic Inverse"}
    )
    INSPECT_FIELD(DepthPass, clear, "Clear", "bool")

    DepthPass(
        const std::string& input_res = "empty_depth",
        const std::string& output_res = "depth",
        const std::string& pass_name = "Depth"
    ) : GeometryPassBase(pass_name, input_res, output_res) {}

    ~DepthPass() override { release_tgfx2_resources(); }

    void destroy() override {
        GeometryPassBase::destroy();
        release_tgfx2_resources();
    }

    // tgfx2-native DepthPass entry — requires ctx.ctx2 to be non-null.
    void execute_with_data_tgfx2(
        ExecuteContext& ctx,
        const DepthPassExecuteData& data
    );

    void execute(ExecuteContext& ctx) override;

    std::vector<ResourceSpec> get_resource_specs() const override {
        return make_resource_specs();
    }

protected:
    std::array<float, 4> clear_color() const override;
    const char* phase_mark() const override {
        return pass_phase_mark.c_str();
    }
    bool uses_material_phase_shader_override() const override { return true; }
    MaterialPipelinePassContract shader_pass_contract() const override;
    tc_shader_handle shader_usage_base_shader() const override;
    std::optional<std::string> fbo_format() const override { return "r16f"; }
};

class ENTITY_API DepthOnlyPass : public CxxFramePass {
public:
    struct DrawCall {
    public:
        Entity entity;
        tc_component* component = nullptr;
        tc_shader_handle final_shader = tc_shader_handle_invalid();
        tc_material_phase* material_phase = nullptr;
        tc_material_handle material = tc_material_handle_invalid();
        size_t phase_index = SIZE_MAX;
        int geometry_id = 0;

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
    std::string output_res = "depth_texture";
    std::string output_res_target;
    std::string camera_name;
    // Drawable/material representation requested by DepthOnlyPass; kept
    // separate from the explicit depth shader contract.
    std::string pass_phase_mark = "depth";
    std::vector<std::string> entity_names;

private:
    float _near_plane = 0.1f;
    float _far_plane = 1000.0f;
    tgfx::IRenderDevice* device2_ = nullptr;
    mutable tc_shader_handle depth_shader_handle_ = tc_shader_handle_invalid();
    mutable std::vector<DrawCall> cached_draw_calls_;

public:
    INSPECT_FIELD(DepthOnlyPass, output_res, "Output Resource", "string")
    INSPECT_FIELD(DepthOnlyPass, output_res_target, "Output Target", "string")
    INSPECT_FIELD(DepthOnlyPass, camera_name, "Camera Name", "string")
    INSPECT_FIELD_ACCESSORS(DepthOnlyPass, std::string, phase_mark, "Phase Mark", "string",
        ([](DepthOnlyPass* self) { return self->pass_phase_mark; }),
        ([](DepthOnlyPass* self, std::string value) { self->pass_phase_mark = value; }))
    INSPECT_TYPE_METADATA(DepthOnlyPass, graph, make_pass_graph_metadata(
        {{"output_res_target", "depth_texture"}},
        {{"output_res", "depth_texture"}},
        {{"output_res_target", "output_res"}}
    ))

    DepthOnlyPass(
        const std::string& output_res = "depth_texture",
        const std::string& pass_name = "DepthOnly"
    ) : output_res(output_res) {
        set_pass_name(pass_name);
    }

    ~DepthOnlyPass() override { release_tgfx2_resources(); }

    void destroy() override {
        release_tgfx2_resources();
    }

    std::set<const char*> compute_reads() const override {
        return output_res_target.empty()
            ? std::set<const char*>{}
            : std::set<const char*>{output_res_target.c_str()};
    }

    std::set<const char*> compute_writes() const override {
        return {output_res.c_str()};
    }

    std::vector<ResourceSpec> get_resource_specs() const override {
        ResourceSpec spec;
        spec.resource = output_res;
        spec.resource_type = "depth_texture";
        spec.format = "depth32f";
        return {spec};
    }

    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override {
        return output_res_target.empty()
            ? std::vector<std::pair<std::string, std::string>>{}
            : std::vector<std::pair<std::string, std::string>>{{output_res_target, output_res}};
    }

    std::vector<std::string> get_internal_symbols() const override {
        return entity_names;
    }

    void collect_shader_usages(
        tc_scene_handle scene,
        const std::function<void(TcShader)>& emit
    ) const override;
    void execute(ExecuteContext& ctx) override;

private:
    void ensure_tgfx2_resources(tgfx::IRenderDevice& device);
    void release_tgfx2_resources();
    CameraComponent* find_camera_by_name(tc_scene_handle scene, const std::string& name) const;
    void collect_draw_calls(
        tc_scene_handle scene,
        uint64_t layer_mask,
        uint64_t render_category_mask
    ) const;
    void sort_draw_calls_by_shader() const;
};

class ENTITY_API DepthToColorPass : public CxxFramePass {
public:
    std::string input_res = "depth_texture";
    std::string output_res = "depth_color";
    std::string output_res_target;

private:
    tgfx::IRenderDevice* device2_ = nullptr;
    tc_shader_handle shader_handle_ = tc_shader_handle_invalid();

public:
    INSPECT_FIELD(DepthToColorPass, input_res, "Input Depth", "string")
    INSPECT_FIELD(DepthToColorPass, output_res, "Output Color", "string")
    INSPECT_FIELD(DepthToColorPass, output_res_target, "Output Target", "string")
    INSPECT_TYPE_METADATA(DepthToColorPass, graph, make_pass_graph_metadata(
        {{"input_res", "depth_texture"}, {"output_res_target", "color_texture"}},
        {{"output_res", "color_texture"}},
        {{"output_res_target", "output_res"}}
    ))

    DepthToColorPass(
        const std::string& input_res = "depth_texture",
        const std::string& output_res = "depth_color",
        const std::string& pass_name = "DepthToColor"
    ) : input_res(input_res), output_res(output_res) {
        set_pass_name(pass_name);
    }

    ~DepthToColorPass() override { release_tgfx2_resources(); }

    void destroy() override { release_tgfx2_resources(); }

    std::set<const char*> compute_reads() const override {
        std::set<const char*> result{input_res.c_str()};
        if (!output_res_target.empty()) {
            result.insert(output_res_target.c_str());
        }
        return result;
    }

    std::set<const char*> compute_writes() const override {
        return {output_res.c_str()};
    }

    std::vector<ResourceSpec> get_resource_specs() const override {
        ResourceSpec spec;
        spec.resource = output_res;
        spec.resource_type = "color_texture";
        spec.format = "rgba8";
        return {spec};
    }

    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override {
        return output_res_target.empty()
            ? std::vector<std::pair<std::string, std::string>>{}
            : std::vector<std::pair<std::string, std::string>>{{output_res_target, output_res}};
    }

    void execute(ExecuteContext& ctx) override;

private:
    void ensure_tgfx2_resources(tgfx::IRenderDevice& device);
    void release_tgfx2_resources();
};

class ENTITY_API ColorToDepthPass : public CxxFramePass {
public:
    std::string input_res = "color_texture";
    std::string output_res = "depth_texture";
    std::string output_res_target;

private:
    tgfx::IRenderDevice* device2_ = nullptr;
    tc_shader_handle shader_handle_ = tc_shader_handle_invalid();

public:
    INSPECT_FIELD(ColorToDepthPass, input_res, "Input Color", "string")
    INSPECT_FIELD(ColorToDepthPass, output_res, "Output Depth", "string")
    INSPECT_FIELD(ColorToDepthPass, output_res_target, "Output Target", "string")
    INSPECT_TYPE_METADATA(ColorToDepthPass, graph, make_pass_graph_metadata(
        {{"input_res", "color_texture"}, {"output_res_target", "depth_texture"}},
        {{"output_res", "depth_texture"}},
        {{"output_res_target", "output_res"}}
    ))

    ColorToDepthPass(
        const std::string& input_res = "color_texture",
        const std::string& output_res = "depth_texture",
        const std::string& pass_name = "ColorToDepth"
    ) : input_res(input_res), output_res(output_res) {
        set_pass_name(pass_name);
    }

    ~ColorToDepthPass() override { release_tgfx2_resources(); }

    void destroy() override { release_tgfx2_resources(); }

    std::set<const char*> compute_reads() const override {
        std::set<const char*> result{input_res.c_str()};
        if (!output_res_target.empty()) {
            result.insert(output_res_target.c_str());
        }
        return result;
    }

    std::set<const char*> compute_writes() const override {
        return {output_res.c_str()};
    }

    std::vector<ResourceSpec> get_resource_specs() const override {
        ResourceSpec spec;
        spec.resource = output_res;
        spec.resource_type = "depth_texture";
        spec.format = "depth32f";
        return {spec};
    }

    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override {
        return output_res_target.empty()
            ? std::vector<std::pair<std::string, std::string>>{}
            : std::vector<std::pair<std::string, std::string>>{{output_res_target, output_res}};
    }

    void execute(ExecuteContext& ctx) override;

private:
    void ensure_tgfx2_resources(tgfx::IRenderDevice& device);
    void release_tgfx2_resources();
};

} // namespace termin
