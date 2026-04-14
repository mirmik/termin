#pragma once

#include <termin/render/geometry_pass_base.hpp>
#include "tgfx2/handles.hpp"
#include "tgfx2/i_render_device.hpp"

namespace termin {

extern ENTITY_API const char* DEPTH_PASS_VERT;
extern ENTITY_API const char* DEPTH_PASS_FRAG;

class DepthPass : public GeometryPassBase {
private:
    float _near_plane = 0.1f;
    float _far_plane = 1000.0f;

    // Lazy tgfx2 resources used by execute_with_data_tgfx2. Lifetime
    // tied to device2_; released in destroy()/dtor.
    tgfx2::IRenderDevice* device2_ = nullptr;
    tgfx2::ShaderHandle depth_vs2_;
    tgfx2::ShaderHandle depth_fs2_;
    tgfx2::BufferHandle params_ubo_;

    void ensure_tgfx2_resources(tgfx2::IRenderDevice& device);
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

    void execute_with_data(
        GraphicsBackend* graphics,
        const FBOMap& reads_fbos,
        const FBOMap& writes_fbos,
        const Rect4i& rect,
        tc_scene_handle scene,
        const Mat44f& view,
        const Mat44f& projection,
        float near_plane,
        float far_plane,
        uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL
    );

    // tgfx2 variant — gated by TERMIN_TGFX2_DEPTH env var.
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

    void setup_extra_uniforms(
        const DrawCall& dc,
        TcShader& shader,
        RenderContext& context
    ) override {
        (void)dc;
        (void)context;
        shader.set_uniform_float("u_near", _near_plane);
        shader.set_uniform_float("u_far", _far_plane);
    }
};

} // namespace termin
