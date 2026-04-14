#pragma once

#include <termin/render/geometry_pass_base.hpp>
#include "tgfx2/handles.hpp"
#include "tgfx2/i_render_device.hpp"

namespace termin {

extern ENTITY_API const char* NORMAL_PASS_VERT;
extern ENTITY_API const char* NORMAL_PASS_FRAG;

class NormalPass : public GeometryPassBase {
private:
    // Lazy tgfx2 resources used by execute_with_data_tgfx2. Lifetime
    // tied to device2_; released in destroy()/dtor.
    tgfx2::IRenderDevice* device2_ = nullptr;
    tgfx2::ShaderHandle normal_vs2_;
    tgfx2::ShaderHandle normal_fs2_;
    tgfx2::BufferHandle per_frame_ubo_;

    void ensure_tgfx2_resources(tgfx2::IRenderDevice& device);
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
