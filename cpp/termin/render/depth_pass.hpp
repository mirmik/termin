#pragma once

#include "termin/render/geometry_pass_base.hpp"

namespace termin {

// Depth shader sources
extern const char* DEPTH_PASS_VERT;
extern const char* DEPTH_PASS_FRAG;

/**
 * Depth pass - renders linear depth to texture.
 *
 * Output: R16F texture with linear depth normalized to [0, 1]
 */
class DepthPass : public GeometryPassBase {
public:
    DepthPass(
        const std::string& input_res = "empty_depth",
        const std::string& output_res = "depth",
        const std::string& pass_name = "Depth"
    ) : GeometryPassBase(pass_name, input_res, output_res) {}

    void execute_with_data(
        GraphicsBackend* graphics,
        const FBOMap& reads_fbos,
        const FBOMap& writes_fbos,
        const Rect4i& rect,
        tc_scene* scene,
        const Mat44f& view,
        const Mat44f& projection,
        int64_t context_key,
        float near_plane,
        float far_plane,
        uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL
    ) {
        _near_plane = near_plane;
        _far_plane = far_plane;
        execute_geometry_pass(graphics, writes_fbos, rect, scene, view, projection, context_key, layer_mask);
    }

    void execute(
        GraphicsBackend* graphics,
        const FBOMap& reads_fbos,
        const FBOMap& writes_fbos,
        const Rect4i& rect,
        void* scene,
        void* camera,
        int64_t context_key,
        const std::vector<Light*>* lights = nullptr
    ) override {
        // Legacy - not used
    }

    std::vector<ResourceSpec> get_resource_specs() const override {
        return make_resource_specs();
    }

protected:
    const char* vertex_shader_source() const override { return DEPTH_PASS_VERT; }
    const char* fragment_shader_source() const override { return DEPTH_PASS_FRAG; }
    std::array<float, 4> clear_color() const override { return {1.0f, 1.0f, 1.0f, 1.0f}; }
    const char* phase_name() const override { return "depth"; }
    std::optional<std::string> fbo_format() const override { return "r16f"; }

    void setup_extra_uniforms(nb::dict& extra_uniforms) override {
        extra_uniforms["u_near"] = nb::make_tuple("float", _near_plane);
        extra_uniforms["u_far"] = nb::make_tuple("float", _far_plane);
    }

    void setup_draw_uniforms(
        const DrawCall& dc,
        ShaderProgram* shader,
        const Mat44f& model,
        const Mat44f& view,
        const Mat44f& projection,
        RenderContext& context,
        nb::dict& extra_uniforms
    ) override {
        GeometryPassBase::setup_draw_uniforms(dc, shader, model, view, projection, context, extra_uniforms);
        shader->set_uniform_float("u_near", _near_plane);
        shader->set_uniform_float("u_far", _far_plane);
    }

private:
    float _near_plane = 0.1f;
    float _far_plane = 1000.0f;
};

} // namespace termin
