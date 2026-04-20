#pragma once

#include <termin/render/geometry_pass_base.hpp>
#include "tgfx2/handles.hpp"
#include "tgfx2/i_render_device.hpp"
extern "C" {
#include <tgfx/resources/tc_shader_registry.h>
}

namespace termin {

extern ENTITY_API const char* NORMAL_PASS_VERT;
extern ENTITY_API const char* NORMAL_PASS_FRAG;

class NormalPass : public GeometryPassBase {
private:
    // Lazy tgfx2 resources used by execute_with_data_tgfx2. Shader lives
    // on the tc_shader registry (hash-based dedup) so Play/Stop doesn't
    // re-run shaderc — see ShadowPass for the pattern + rationale.
    tgfx::IRenderDevice* device2_ = nullptr;
    tc_shader_handle normal_shader_handle_ = tc_shader_handle_invalid();

    void ensure_tgfx2_resources(tgfx::IRenderDevice& device);
    void release_tgfx2_resources();

public:
    NormalPass(
        const std::string& input_res = "empty_normal",
        const std::string& output_res = "normal",
        const std::string& pass_name = "Normal"
    ) : GeometryPassBase(pass_name, input_res, output_res) {}

    ~NormalPass() override { release_tgfx2_resources(); }

    void destroy() override {
        GeometryPassBase::destroy();
        release_tgfx2_resources();
    }

    // tgfx2-native NormalPass entry — requires ctx.ctx2 to be non-null.
    void execute_with_data_tgfx2(
        ExecuteContext& ctx,
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
