#pragma once

#include <termin/render/geometry_pass_base.hpp>

namespace termin {

extern ENTITY_API const char* NORMAL_PASS_VERT;
extern ENTITY_API const char* NORMAL_PASS_FRAG;

class NormalPass : public GeometryPassBase {
public:
    NormalPass(
        const std::string& input_res = "empty_normal",
        const std::string& output_res = "normal",
        const std::string& pass_name = "Normal"
    ) : GeometryPassBase(pass_name, input_res, output_res) {}

    void execute_with_data(
        GraphicsBackend* graphics,
        const FBOMap& reads_fbos,
        const FBOMap& writes_fbos,
        const Rect4i& rect,
        tc_scene_handle scene,
        const Mat44f& view,
        const Mat44f& projection,
        uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL
    );

    void execute(ExecuteContext& ctx) override;

    std::vector<ResourceSpec> get_resource_specs() const override {
        return make_resource_specs();
    }

protected:
    const char* vertex_shader_source() const override { return NORMAL_PASS_VERT; }
    const char* fragment_shader_source() const override { return NORMAL_PASS_FRAG; }
    std::array<float, 4> clear_color() const override { return {0.5f, 0.5f, 0.5f, 1.0f}; }
    const char* phase_name() const override { return "normal"; }
};

} // namespace termin
