#pragma once

#include "termin/render/geometry_pass_base.hpp"
#include "termin/render/execute_context.hpp"

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
        float near_plane,
        float far_plane,
        uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL
    ) {
        _near_plane = near_plane;
        _far_plane = far_plane;
        execute_geometry_pass(graphics, writes_fbos, rect, scene, view, projection, layer_mask);
    }

    // Override from CxxFramePass
    void execute(ExecuteContext& ctx) override {
        tc_scene* scene = ctx.scene.ptr();
        CameraComponent* camera = ctx.camera;
        Rect4i rect = ctx.rect;

        // If camera_name is set, use it (overrides passed camera)
        if (!camera_name.empty()) {
            camera = find_camera_by_name(scene, camera_name);
            if (!camera) return;
        }

        if (!camera) return;

        // Get output FBO and use its size
        auto it = ctx.writes_fbos.find(output_res);
        if (it != ctx.writes_fbos.end() && it->second != nullptr) {
            FramebufferHandle* fb = dynamic_cast<FramebufferHandle*>(it->second);
            if (fb) {
                auto fbo_size = fb->get_size();
                rect = Rect4i(0, 0, fbo_size.width, fbo_size.height);
                camera->set_aspect(static_cast<double>(fbo_size.width) / std::max(1, fbo_size.height));
            }
        }

        Mat44 view_d = camera->get_view_matrix();
        Mat44 proj_d = camera->get_projection_matrix();
        Mat44f view = view_d.to_float();
        Mat44f projection = proj_d.to_float();

        execute_with_data(
            ctx.graphics,
            ctx.reads_fbos,
            ctx.writes_fbos,
            rect,
            scene,
            view,
            projection,
            static_cast<float>(camera->near_clip),
            static_cast<float>(camera->far_clip),
            ctx.layer_mask
        );
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

    void setup_draw_uniforms(
        const DrawCall& dc,
        TcShader& shader,
        const Mat44f& model,
        const Mat44f& view,
        const Mat44f& projection,
        RenderContext& context
    ) override {
        GeometryPassBase::setup_draw_uniforms(dc, shader, model, view, projection, context);
        shader.set_uniform_float("u_near", _near_plane);
        shader.set_uniform_float("u_far", _far_plane);
    }

private:
    float _near_plane = 0.1f;
    float _far_plane = 1000.0f;
};

} // namespace termin
