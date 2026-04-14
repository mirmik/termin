#include <termin/render/normal_pass.hpp>

#include <termin/camera/camera_component.hpp>
#include <termin/camera/render_camera_utils.hpp>
#include <termin/render/tgfx2_bridge.hpp>

#include <tgfx2/render_context.hpp>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/enums.hpp>
#include <tgfx2/opengl/opengl_render_device.hpp>

#include <tcbase/tc_log.hpp>

#include <cstdlib>
#include <cstring>
#include <optional>
#include <span>

namespace termin {

namespace {

// PerFrame UBO (binding 0): view + projection. 128 bytes std140.
struct NormalPerFrameStd140 {
    float u_view[16];
    float u_projection[16];
};
static_assert(sizeof(NormalPerFrameStd140) == 128,
              "NormalPerFrameStd140 must be 2 * mat4");

// PushConstants (binding 14): per-object model matrix.
struct NormalPushStd140 {
    float u_model[16];
};
static_assert(sizeof(NormalPushStd140) == 64,
              "NormalPushStd140 must be exactly one mat4");

constexpr const char* NORMAL_PASS_VERT_UBO = R"(
#version 330 core
#extension GL_ARB_shading_language_420pack : require

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_texcoord;

layout(std140, binding = 0) uniform PerFrame {
    mat4 u_view;
    mat4 u_projection;
};

layout(std140, binding = 14) uniform PushConstants {
    mat4 u_model;
};

out vec3 v_world_normal;

void main() {
    mat3 normal_matrix = transpose(inverse(mat3(u_model)));
    v_world_normal = normalize(normal_matrix * a_normal);

    vec4 world_pos = u_model * vec4(a_position, 1.0);
    gl_Position = u_projection * u_view * world_pos;
}
)";

constexpr const char* NORMAL_PASS_FRAG_UBO = R"(
#version 330 core

in vec3 v_world_normal;
out vec4 FragColor;

void main() {
    vec3 encoded = normalize(v_world_normal) * 0.5 + 0.5;
    FragColor = vec4(encoded, 1.0);
}
)";

bool tgfx2_normal_enabled() {
    const char* env = std::getenv("TERMIN_TGFX2_NORMAL");
    return env && env[0] && env[0] != '0';
}

} // anonymous namespace

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

void NormalPass::ensure_tgfx2_resources(tgfx2::IRenderDevice& device) {
    if (device2_ == &device && normal_vs2_ && normal_fs2_ && per_frame_ubo_) {
        return;
    }
    if (device2_ && device2_ != &device) {
        release_tgfx2_resources();
    }
    device2_ = &device;

    tgfx2::ShaderDesc vs_desc;
    vs_desc.stage = tgfx2::ShaderStage::Vertex;
    vs_desc.source = NORMAL_PASS_VERT_UBO;
    normal_vs2_ = device.create_shader(vs_desc);

    tgfx2::ShaderDesc fs_desc;
    fs_desc.stage = tgfx2::ShaderStage::Fragment;
    fs_desc.source = NORMAL_PASS_FRAG_UBO;
    normal_fs2_ = device.create_shader(fs_desc);

    tgfx2::BufferDesc ubo_desc;
    ubo_desc.size = sizeof(NormalPerFrameStd140);
    ubo_desc.usage = tgfx2::BufferUsage::Uniform | tgfx2::BufferUsage::CopyDst;
    per_frame_ubo_ = device.create_buffer(ubo_desc);
}

void NormalPass::release_tgfx2_resources() {
    if (!device2_) return;
    if (normal_vs2_) { device2_->destroy(normal_vs2_); normal_vs2_ = {}; }
    if (normal_fs2_) { device2_->destroy(normal_fs2_); normal_fs2_ = {}; }
    if (per_frame_ubo_) { device2_->destroy(per_frame_ubo_); per_frame_ubo_ = {}; }
    device2_ = nullptr;
}

// ----------------------------------------------------------------------------
// tgfx2 path — Stage 5.E.
// ----------------------------------------------------------------------------
void NormalPass::execute_with_data_tgfx2(
    ExecuteContext& ctx,
    const Rect4i& rect,
    tc_scene_handle scene,
    const Mat44f& view,
    const Mat44f& projection,
    uint64_t layer_mask
) {
    if (!ctx.ctx2 || !ctx.graphics) {
        tc::Log::error("NormalPass/tgfx2: ctx2 or graphics is null");
        return;
    }

    auto it = ctx.writes_fbos.find(output_res);
    if (it == ctx.writes_fbos.end() || it->second == nullptr) {
        return;
    }
    FramebufferHandle* fb = dynamic_cast<FramebufferHandle*>(it->second);
    if (!fb) {
        return;
    }

    auto* gl_dev = dynamic_cast<tgfx2::OpenGLRenderDevice*>(&ctx.ctx2->device());
    if (!gl_dev) {
        tc::Log::error("NormalPass/tgfx2: device is not OpenGLRenderDevice");
        return;
    }

    ensure_tgfx2_resources(ctx.ctx2->device());

    TcShader& base_shader = get_shader(ctx.graphics);
    collect_draw_calls(scene, layer_mask, base_shader.handle);
    sort_draw_calls_by_shader();

    entity_names.clear();
    std::set<std::string> seen_entities;

    tgfx2::TextureHandle color_tex2 = wrap_fbo_color_as_tgfx2(*gl_dev, fb);
    tgfx2::TextureHandle depth_tex2 = wrap_fbo_depth_as_tgfx2(*gl_dev, fb);
    if (!color_tex2) {
        tc::Log::error("NormalPass/tgfx2: failed to wrap color texture");
        return;
    }

    auto cc = clear_color();
    float clear_rgba[4] = {cc[0], cc[1], cc[2], cc[3]};

    ctx.ctx2->begin_pass(color_tex2, depth_tex2, clear_rgba, 1.0f, true);
    ctx.ctx2->set_viewport(0, 0, rect.width, rect.height);
    ctx.ctx2->set_depth_test(true);
    ctx.ctx2->set_depth_write(true);
    ctx.ctx2->set_blend(false);
    ctx.ctx2->set_cull(tgfx2::CullMode::Back);
    ctx.ctx2->set_color_format(tgfx2::PixelFormat::RGBA8_UNorm);
    ctx.ctx2->set_depth_format(tgfx2::PixelFormat::D32F);
    ctx.ctx2->bind_shader(normal_vs2_, normal_fs2_);

    NormalPerFrameStd140 per_frame{};
    std::memcpy(per_frame.u_view, view.data, sizeof(float) * 16);
    std::memcpy(per_frame.u_projection, projection.data, sizeof(float) * 16);
    ctx.ctx2->device().upload_buffer(
        per_frame_ubo_,
        std::span<const uint8_t>(
            reinterpret_cast<const uint8_t*>(&per_frame),
            sizeof(per_frame)));
    ctx.ctx2->bind_uniform_buffer(0, per_frame_ubo_);

    RenderContext legacy_ctx;
    legacy_ctx.view = view;
    legacy_ctx.projection = projection;
    legacy_ctx.graphics = ctx.graphics;
    legacy_ctx.phase = phase_name();

    const std::string& debug_symbol = get_debug_internal_point();

    for (const auto& dc : cached_draw_calls_) {
        auto* drawable = static_cast<Drawable*>(tc_component_get_drawable_userdata(dc.component));
        if (!drawable) continue;

        Mat44f model = drawable->get_model_matrix(dc.entity);

        const char* name = dc.entity.name();
        if (name && seen_entities.insert(name).second) {
            entity_names.push_back(name);
        }

        tc_mesh* mesh = drawable->get_mesh_for_phase(phase_name(), dc.geometry_id);
        bool override_is_base = tc_shader_handle_eq(dc.final_shader, base_shader.handle);

        if (mesh && override_is_base) {
            NormalPushStd140 push{};
            std::memcpy(push.u_model, model.data, sizeof(float) * 16);
            ctx.ctx2->set_push_constants(&push, sizeof(push));

            Tgfx2MeshBinding bind = wrap_mesh_as_tgfx2(*gl_dev, mesh);
            if (bind.index_count == 0) continue;

            ctx.ctx2->set_vertex_layout(bind.layout);
            ctx.ctx2->set_topology(bind.topology);
            ctx.ctx2->draw(bind.vertex_buffer, bind.index_buffer,
                           bind.index_count, bind.index_type);

            gl_dev->destroy(bind.vertex_buffer);
            gl_dev->destroy(bind.index_buffer);
        } else {
            ctx.ctx2->flush_pipeline();

            tc_shader_handle shader_handle = dc.final_shader;
            TcShader shader_to_use(shader_handle);
            shader_to_use.use();
            shader_to_use.set_uniform_mat4("u_view", view.data, false);
            shader_to_use.set_uniform_mat4("u_projection", projection.data, false);
            shader_to_use.set_uniform_mat4("u_model", model.data, false);
            legacy_ctx.model = model;
            legacy_ctx.current_tc_shader = shader_to_use;

            tc_component_draw_geometry(dc.component, &legacy_ctx, dc.geometry_id);
        }

        if (!debug_symbol.empty() && name && debug_symbol == name) {
            ctx.ctx2->end_pass();
            maybe_blit_to_debugger(ctx.graphics, fb, name, rect.width, rect.height);
            ctx.ctx2->begin_pass(color_tex2, depth_tex2, nullptr, 1.0f, false);
            ctx.ctx2->set_viewport(0, 0, rect.width, rect.height);
            ctx.ctx2->set_depth_test(true);
            ctx.ctx2->set_depth_write(true);
            ctx.ctx2->set_blend(false);
            ctx.ctx2->set_cull(tgfx2::CullMode::Back);
            ctx.ctx2->bind_shader(normal_vs2_, normal_fs2_);
        }
    }

    ctx.ctx2->end_pass();
    gl_dev->destroy(color_tex2);
    if (depth_tex2) gl_dev->destroy(depth_tex2);
}

void NormalPass::execute(ExecuteContext& ctx) {
    tc_scene_handle scene = ctx.scene.handle();
    const RenderCamera* camera = ctx.camera;
    Rect4i rect = ctx.rect;
    std::optional<RenderCamera> named_camera_snapshot;

    if (!camera_name.empty()) {
        CameraComponent* named_camera = find_camera_by_name(scene, camera_name);
        if (!named_camera) {
            return;
        }
        named_camera_snapshot = make_render_camera(*named_camera);
        camera = &*named_camera_snapshot;
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
            if (!camera_name.empty()) {
                CameraComponent* named_camera = find_camera_by_name(scene, camera_name);
                if (named_camera) {
                    named_camera_snapshot = make_render_camera(*named_camera, static_cast<double>(fbo_size.width) / std::max(1, fbo_size.height));
                    camera = &*named_camera_snapshot;
                }
            }
        }
    }

    Mat44 view_d = camera->get_view_matrix();
    Mat44 proj_d = camera->get_projection_matrix();
    Mat44f view = view_d.to_float();
    Mat44f projection = proj_d.to_float();

    if (ctx.ctx2 && tgfx2_normal_enabled()) {
        execute_with_data_tgfx2(
            ctx,
            rect,
            scene,
            view,
            projection,
            ctx.layer_mask
        );
    } else {
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
}

TC_REGISTER_FRAME_PASS_DERIVED(NormalPass, GeometryPassBase);

} // namespace termin
