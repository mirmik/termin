#pragma once

#include "termin/render/geometry_pass_base.hpp"
#include "termin/render/execute_context.hpp"

namespace termin {

// Normal shader sources
extern const char* NORMAL_PASS_VERT;
extern const char* NORMAL_PASS_FRAG;

/**
 * Normal pass - renders world-space normals to texture.
 *
 * Output: RGB texture with normals encoded as (normal * 0.5 + 0.5)
 */
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
        tc_scene* scene,
        const Mat44f& view,
        const Mat44f& projection,
        uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL
    ) {
        execute_geometry_pass(graphics, writes_fbos, rect, scene, view, projection, layer_mask);
    }

    // Execute using ExecuteContext - main entry point from Python
    void execute(ExecuteContext& ctx) {
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
            ctx.layer_mask
        );
    }

    void execute(
        GraphicsBackend* graphics,
        const FBOMap& reads_fbos,
        const FBOMap& writes_fbos,
        const Rect4i& rect,
        void* scene,
        void* camera,
        const std::vector<Light*>* lights = nullptr
    ) override {
        // Legacy - not used
    }

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
