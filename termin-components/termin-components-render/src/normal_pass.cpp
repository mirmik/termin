#include <termin/render/normal_pass.hpp>

#include <termin/camera/camera_component.hpp>

namespace termin {

const char* NORMAL_PASS_VERT = R"(
#version 330 core

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_texcoord;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_world_normal;

void main()
{
    mat3 normal_matrix = transpose(inverse(mat3(u_model)));
    v_world_normal = normalize(normal_matrix * a_normal);

    vec4 world_pos = u_model * vec4(a_position, 1.0);
    gl_Position = u_projection * u_view * world_pos;
}
)";

const char* NORMAL_PASS_FRAG = R"(
#version 330 core

in vec3 v_world_normal;
out vec4 FragColor;

void main()
{
    vec3 encoded = normalize(v_world_normal) * 0.5 + 0.5;
    FragColor = vec4(encoded, 1.0);
}
)";

void NormalPass::execute_with_data(
    GraphicsBackend* graphics,
    const FBOMap& reads_fbos,
    const FBOMap& writes_fbos,
    const Rect4i& rect,
    tc_scene_handle scene,
    const Mat44f& view,
    const Mat44f& projection,
    uint64_t layer_mask
) {
    (void)reads_fbos;
    execute_geometry_pass(graphics, writes_fbos, rect, scene, view, projection, layer_mask);
}

void NormalPass::execute(ExecuteContext& ctx) {
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
        ctx.layer_mask
    );
}

TC_REGISTER_FRAME_PASS_DERIVED(NormalPass, GeometryPassBase);

} // namespace termin
