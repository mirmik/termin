#pragma once

#include <termin/render/geometry_pass_base.hpp>
#include "tgfx2/handles.hpp"
#include "tgfx2/i_render_device.hpp"
extern "C" {
#include <tgfx/resources/tc_shader_registry.h>
}

namespace termin {

extern ENTITY_API const char* DEPTH_PASS_VERT;
extern ENTITY_API const char* DEPTH_PASS_FRAG;

class DepthPass : public GeometryPassBase {
private:
    float _near_plane = 0.1f;
    float _far_plane = 1000.0f;

    // Lazy tgfx2 resources used by execute_with_data_tgfx2. Shader lives
    // on the tc_shader registry (hash-based dedup across pass re-creations)
    // so Play/Stop doesn't re-run shaderc — see ShadowPass for the same
    // pattern.
    tgfx::IRenderDevice* device2_ = nullptr;
    tc_shader_handle depth_shader_handle_ = tc_shader_handle_invalid();

    void ensure_tgfx2_resources(tgfx::IRenderDevice& device);
    void release_tgfx2_resources();

public:
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
        const Rect4i& rect,
        tc_scene_handle scene,
        const Mat44f& view,
        const Mat44f& projection,
        float near_plane,
        float far_plane,
        uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL
    );

    void execute(ExecuteContext& ctx) override;

    std::vector<ResourceSpec> get_resource_specs() const override {
        return make_resource_specs();
    }

protected:
    const char* vertex_shader_source() const override { return DEPTH_PASS_VERT; }
    const char* fragment_shader_source() const override { return DEPTH_PASS_FRAG; }
    std::array<float, 4> clear_color() const override { return {1.0f, 1.0f, 1.0f, 1.0f}; }
    const char* phase_name() const override { return "depth"; }
    std::optional<std::string> fbo_format() const override { return "r16f"; }
};

class DepthOnlyPass : public CxxFramePass {
public:
    struct DrawCall {
    public:
        Entity entity;
        tc_component* component = nullptr;
        tc_shader_handle final_shader = tc_shader_handle_invalid();
        int geometry_id = 0;
    };

public:
    std::string output_res = "depth_texture";
    std::string output_res_target;
    std::string camera_name;
    std::vector<std::string> entity_names;

private:
    float _near_plane = 0.1f;
    float _far_plane = 1000.0f;
    tgfx::IRenderDevice* device2_ = nullptr;
    tc_shader_handle depth_shader_handle_ = tc_shader_handle_invalid();
    mutable std::vector<DrawCall> cached_draw_calls_;

public:
    INSPECT_FIELD(DepthOnlyPass, output_res, "Output Resource", "string")
    INSPECT_FIELD(DepthOnlyPass, output_res_target, "Output Target", "string")
    INSPECT_FIELD(DepthOnlyPass, camera_name, "Camera Name", "string")
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

    void execute(ExecuteContext& ctx) override;

private:
    void ensure_tgfx2_resources(tgfx::IRenderDevice& device);
    void release_tgfx2_resources();
    CameraComponent* find_camera_by_name(tc_scene_handle scene, const std::string& name) const;
    void collect_draw_calls(tc_scene_handle scene, uint64_t layer_mask) const;
    void sort_draw_calls_by_shader() const;
};

class DepthToColorPass : public CxxFramePass {
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

class ColorToDepthPass : public CxxFramePass {
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
