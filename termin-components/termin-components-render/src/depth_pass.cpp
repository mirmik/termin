#include <termin/render/depth_pass.hpp>

#include <termin/camera/camera_component.hpp>

namespace termin {

const char* DEPTH_PASS_VERT = R"(
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;
uniform float u_near;
uniform float u_far;

out float v_linear_depth;

void main()
{
    vec4 world_pos = u_model * vec4(a_position, 1.0);
    vec4 view_pos  = u_view * world_pos;

    float y = view_pos.y;
    float depth = (y - u_near) / (u_far - u_near);

    v_linear_depth = depth;
    gl_Position = u_projection * view_pos;
}
)";

const char* DEPTH_PASS_FRAG = R"(
#version 330 core

in float v_linear_depth;
out vec4 FragColor;

void main()
{
    float d = clamp(v_linear_depth, 0.0, 1.0);
    FragColor = vec4(d, d, d, 1.0);
}
)";

void DepthPass::execute_with_data(
    GraphicsBackend* graphics,
    const FBOMap& reads_fbos,
    const FBOMap& writes_fbos,
    const Rect4i& rect,
    tc_scene_handle scene,
    const Mat44f& view,
    const Mat44f& projection,
    float near_plane,
    float far_plane,
    uint64_t layer_mask
) {
    (void)reads_fbos;
    _near_plane = near_plane;
    _far_plane = far_plane;
    execute_geometry_pass(graphics, writes_fbos, rect, scene, view, projection, layer_mask);
}

void DepthPass::execute(ExecuteContext& ctx) {
    tc_scene_handle scene = ctx.scene.handle();
    CameraComponent* camera = ctx.camera;
    Rect4i rect = ctx.rect;

    if (!camera_name.empty()) {
        camera = find_camera_by_name(scene, camera_name);
        if (!camera) {
            return;
        }
    }

    if (!camera) {
        return;
    }

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

TC_REGISTER_FRAME_PASS_DERIVED(DepthPass, GeometryPassBase);

} // namespace termin
