#include <termin/render/depth_pass.hpp>

#include <termin/camera/camera_component.hpp>
#include <termin/camera/render_camera_utils.hpp>
#include <termin/render/frame_graph_debugger_core.hpp>
#include <termin/render/material_pipeline.hpp>
#include <termin/render/tgfx2_bridge.hpp>

#include <tgfx2/builtin_shader_sources.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/enums.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

#include <tgfx/resources/tc_shader_registry.h>
#include <core/tc_drawable_protocol.h>

#include <tcbase/tc_log.hpp>

#include <algorithm>
#include <array>
#include <cstdlib>
#include <cstring>
#include <optional>
#include <span>

namespace termin {

constexpr const char* DEPTH_ENGINE_SHADER_UUID = "termin-engine-depth";
constexpr const char* DEPTH_ONLY_ENGINE_SHADER_UUID = "termin-engine-depth-only";
constexpr const char* DEPTH_TO_COLOR_ENGINE_SHADER_UUID = "termin-engine-depth-to-color";
constexpr const char* COLOR_TO_DEPTH_ENGINE_SHADER_UUID = "termin-engine-color-to-depth";

namespace {

// PerFrame UBO payload: view + projection + near/far plane. Uploaded once per
// execute and bound through the shader's reflected per_frame resource layout.
// std140:
//   u_view       mat4   offset 0    (64 B)
//   u_projection mat4   offset 64   (64 B)
//   u_near       float  offset 128  (4 B)
//   u_far        float  offset 132  (4 B)
//   u_depth_encoding    offset 136  (4 B)
//   pad                 offset 140  (4 B to 16-byte boundary)
// Total 144 bytes. Rounded up to 144 here; the GPU reads 16-byte
// aligned chunks so we pad the tail.
struct DepthPerFrameStd140 {
    float u_view[16];
    float u_projection[16];
    float u_near;
    float u_far;
    float u_depth_encoding;
    float _pad;
};
static_assert(sizeof(DepthPerFrameStd140) == 144,
              "DepthPerFrameStd140 must be 144 bytes");

// Draw-scope per-object model matrix. The shader resource layout maps it to
// backend storage; render code binds it by reflected resource name.
struct DepthDrawStd140 {
    float u_model[16];
};
static_assert(sizeof(DepthDrawStd140) == 64,
              "DepthDrawStd140 must be exactly one mat4");

float depth_encoding_mode(const std::string& encoding) {
    if (encoding == "linear") return 0.0f;
    if (encoding == "linear_inverse") return 1.0f;
    if (encoding == "perspective") return 2.0f;
    if (encoding == "perspective_inverse") return 3.0f;
    if (encoding == "logarithmic") return 4.0f;
    if (encoding == "logarithmic_inverse") return 5.0f;
    tc::Log::warn(
        "DepthPass: unknown depth_encoding '%s', using 'linear'",
        encoding.c_str()
    );
    return 0.0f;
}

bool depth_encoding_is_inverse(const std::string& encoding) {
    return encoding == "linear_inverse" ||
           encoding == "perspective_inverse" ||
           encoding == "logarithmic_inverse";
}

MaterialPipelinePassContract depth_material_pass_contract(const char* debug_name)
{
    MaterialPipelinePassContract contract;
    contract.debug_name = debug_name ? debug_name : "depth";
    contract.required_material_fragment_input = MaterialFragmentInterface{};
    contract.uses_material_fragment = true;

    MaterialFragmentInterface fragment_input =
        material_pipeline_standard_material_fragment_interface();
    contract.static_vertex_transform =
        material_pipeline_make_static_vertex_transform_contract(
            "static_depth",
            material_pipeline_position_mesh_input(),
            fragment_input,
            material_pipeline_common_vertex_resources("depth_draw"));
    contract.skinned_vertex_transform =
        material_pipeline_make_skinned_vertex_transform_contract(
            *contract.static_vertex_transform,
            "skinned_depth",
            "termin-engine-skinned-depth",
            material_pipeline_skinned_position_mesh_input());
    return contract;
}

} // anonymous namespace

MaterialPipelinePassContract DepthPass::shader_pass_contract() const {
    return depth_material_pass_contract("depth");
}

void DepthPass::ensure_tgfx2_resources(tgfx::IRenderDevice& device) {
    device2_ = &device;

    // Engine-shader: process-lifetime ownership via tc_shader registry.
    if (tc_shader_handle_is_invalid(depth_shader_handle_)) {
        depth_shader_handle_ =
            tgfx::register_builtin_shader_from_catalog(DEPTH_ENGINE_SHADER_UUID);
    }

}

void DepthPass::release_tgfx2_resources() {
    if (!device2_) return;
    // depth_shader_handle_ NOT released — static engine shader, outlives
    // pass teardown so the render-device shader cache can reuse compiled
    // modules across Play/Stop. See tc_shader_register_static docs.
    device2_ = nullptr;
}

std::array<float, 4> DepthPass::clear_color() const {
    float far = depth_encoding_is_inverse(depth_encoding) ? 0.0f : 1.0f;
    return {far, far, far, 1.0f};
}

// ----------------------------------------------------------------------------
// tgfx2 path — Stage 5.D.
// ----------------------------------------------------------------------------
void DepthPass::execute_with_data_tgfx2(
    ExecuteContext& ctx,
    const Rect4i& rect,
    tc_scene_handle scene,
    const Mat44f& view,
    const Mat44f& projection,
    float near_plane,
    float far_plane,
    uint64_t layer_mask
) {
    if (!ctx.ctx2) {
        tc::Log::error("DepthPass/tgfx2: ctx2 is null");
        return;
    }

    _near_plane = near_plane;
    _far_plane = far_plane;

    auto depth_it = ctx.tex2_depth_writes.find(output_res);
    tgfx::TextureHandle depth_tex2 =
        (depth_it != ctx.tex2_depth_writes.end()) ? depth_it->second : tgfx::TextureHandle{};

    auto& device = ctx.ctx2->device();

    auto color_it = ctx.tex2_writes.find(output_res);
    tgfx::TextureHandle color_tex2 =
        (color_it != ctx.tex2_writes.end()) ? color_it->second : tgfx::TextureHandle{};
    if (color_tex2 && device.texture_desc(color_tex2).format == tgfx::PixelFormat::D32F) {
        color_tex2 = {};
    }
    if (!color_tex2 && !depth_tex2) {
        tc::Log::error("DepthPass/tgfx2: missing tgfx2 output texture for '%s'",
                       output_res.c_str());
        return;
    }

    ensure_tgfx2_resources(device);

    // Use the UBO-based engine shader as base_shader for skinning override.
    // The old source-based GeometryPassBase shader path has been removed;
    // this handle is the only base shader key for depth overrides.
    collect_draw_calls(scene, layer_mask, ctx.render_category_mask, depth_shader_handle_);
    sort_draw_calls_by_shader();

    entity_names.clear();
    std::set<std::string> seen_entities;

    auto cc = clear_color();
    float clear_rgba[4] = {cc[0], cc[1], cc[2], cc[3]};

    ctx.ctx2->begin_pass(color_tex2, depth_tex2, clear_rgba, 1.0f, clear);
    ctx.ctx2->set_viewport(0, 0, rect.width, rect.height);
    ctx.ctx2->set_depth_test(true);
    ctx.ctx2->set_depth_write(true);
    ctx.ctx2->set_blend(false);
    ctx.ctx2->set_cull(tgfx::CullMode::Back);

    MaterialPipelineShaderBinding depth_shader{};
    if (!ensure_material_pipeline_shader(
            *ctx.ctx2,
            device,
            depth_shader_handle_,
            "DepthPass",
            depth_shader)) {
        return;
    }

    // PerFrame UBO — uploaded ONCE per execute. view + projection +
    // near/far plane. Bound by shader resource name so Slang scope metadata
    // owns the physical binding.
    DepthPerFrameStd140 per_frame{};
    std::memcpy(per_frame.u_view, view.data, sizeof(float) * 16);
    std::memcpy(per_frame.u_projection, projection.data, sizeof(float) * 16);
    per_frame.u_near = near_plane;
    per_frame.u_far = far_plane;
    per_frame.u_depth_encoding = depth_encoding_mode(depth_encoding);
    std::array<MaterialPipelineUniformData, 1> per_frame_uniforms{{
        {"per_frame", &per_frame, static_cast<uint32_t>(sizeof(per_frame))},
    }};
    MaterialPipelineResourceContext depth_resources{};
    depth_resources.uniforms = per_frame_uniforms;
    prepare_material_pipeline_resources(
        *ctx.ctx2,
        device,
        depth_shader.shader,
        nullptr,
        depth_resources);

    const std::string& debug_symbol = get_debug_internal_point();
    auto capture_debug_symbol = [&](const char* entity_name) {
        if (debug_symbol.empty() || !entity_name || debug_symbol != entity_name) {
            return;
        }
        FrameGraphCapture* capture = debug_capture();
        if (!capture) {
            return;
        }

        tgfx::TextureHandle capture_tex = color_tex2 ? color_tex2 : depth_tex2;
        if (!capture_tex) {
            return;
        }

        ctx.ctx2->end_pass();
        capture->capture_direct_via_ctx2(
            ctx.ctx2,
            capture_tex,
            rect.width,
            rect.height);
        ctx.ctx2->begin_pass(color_tex2, depth_tex2, clear_rgba, 1.0f, false);
        ctx.ctx2->set_viewport(0, 0, rect.width, rect.height);
        ctx.ctx2->set_depth_test(true);
        ctx.ctx2->set_depth_write(true);
        ctx.ctx2->set_blend(false);
        ctx.ctx2->set_cull(tgfx::CullMode::Back);
        ctx.ctx2->bind_shader(depth_shader.vertex, depth_shader.fragment);
        ctx.ctx2->use_shader_resource_layout(depth_shader.shader);
        prepare_material_pipeline_resources(
            *ctx.ctx2,
            device,
            depth_shader.shader,
            nullptr,
            depth_resources);
    };

    for (const auto& dc : cached_draw_calls_) {
        Drawable* drawable = nullptr;
        if (tc_component_get_drawable_vtable(dc.component) == &Drawable::cxx_drawable_vtable()) {
            drawable = static_cast<Drawable*>(tc_component_get_drawable_userdata(dc.component));
        }
        if (!drawable) continue;

        MeshDrawGeometry mesh_geometry{};
        if (!drawable->resolve_mesh_geometry(phase_mark(), dc.geometry_id, mesh_geometry)) {
            continue;  // non-mesh drawables skipped
        }

        Mat44f model = drawable->get_model_matrix(dc.entity);

        const char* name = dc.entity.name();
        if (name && seen_entities.insert(name).second) {
            entity_names.push_back(name);
        }

        bool override_is_base =
            tc_shader_handle_eq(dc.final_shader, depth_shader_handle_);
        tc_material_phase* material_phase = dc.resolve_material_phase();

        // Base, skinned, and material-phase override shaders share the same
        // draw-scope model matrix + PerFrame UBO. Skinning adds BoneBlock as
        // another reflected draw resource.
        DepthDrawStd140 draw{};
        std::memcpy(draw.u_model, model.data, sizeof(float) * 16);
        std::array<MaterialPipelineUniformData, 2> draw_uniforms{{
            {"per_frame", &per_frame, static_cast<uint32_t>(sizeof(per_frame))},
            {"depth_draw", &draw, static_cast<uint32_t>(sizeof(draw))},
        }};
        MaterialPipelineResourceContext draw_resources{};
        draw_resources.uniforms = draw_uniforms;

        if (override_is_base) {
            prepare_material_pipeline_resources(
                *ctx.ctx2,
                device,
                depth_shader.shader,
                nullptr,
                draw_resources);
            // Base depth VS only reads position.
            draw_material_pipeline_submesh(
                *ctx.ctx2,
                mesh_geometry.mesh,
                mesh_geometry.submesh_index,
                material_mesh_vertex_input_for_shader(
                    depth_shader.shader,
                    MaterialMeshVertexInput::Position));
            capture_debug_symbol(name);
        } else {
            // Non-base shader: compile via bridge, bind reflected resources,
            // and let the drawable upload optional per-draw data such as BoneBlock.
            MaterialPipelineShaderBinding skinned_shader{};
            if (!ensure_material_pipeline_shader(
                    *ctx.ctx2,
                    device,
                    dc.final_shader,
                    "DepthPass/skinned",
                    skinned_shader)) {
                continue;
            }
            prepare_material_pipeline_resources(
                *ctx.ctx2,
                device,
                skinned_shader.shader,
                material_phase,
                draw_resources);
            drawable->upload_per_draw_uniforms_tgfx2(*ctx.ctx2, dc.geometry_id);

            draw_material_pipeline_submesh(
                *ctx.ctx2,
                mesh_geometry.mesh,
                mesh_geometry.submesh_index,
                material_mesh_vertex_input_for_shader(
                    skinned_shader.shader,
                    MaterialMeshVertexInput::Position));
            capture_debug_symbol(name);

            ctx.ctx2->bind_shader(depth_shader.vertex, depth_shader.fragment);
            ctx.ctx2->use_shader_resource_layout(depth_shader.shader);
            prepare_material_pipeline_resources(
                *ctx.ctx2,
                device,
                depth_shader.shader,
                nullptr,
                depth_resources);
        }
    }

    ctx.ctx2->end_pass();
    // color_tex2/depth_tex2 are persistent FBOPool wrappers — do not destroy.
}

void DepthPass::execute(ExecuteContext& ctx) {
    tc_scene_handle scene = ctx.scene.handle();
    const RenderCamera* camera = ctx.camera;
    Rect4i rect = ctx.render_rect;
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

    if (ctx.ctx2) {
        auto it = ctx.tex2_writes.find(output_res);
        if (it != ctx.tex2_writes.end() && it->second) {
            auto desc = ctx.ctx2->device().texture_desc(it->second);
            int w = static_cast<int>(desc.width);
            int h = static_cast<int>(desc.height);
            if (w > 0 && h > 0) {
                rect = Rect4i(0, 0, w, h);
                if (!camera_name.empty()) {
                    CameraComponent* named_camera = find_camera_by_name(scene, camera_name);
                    if (named_camera) {
                        named_camera_snapshot = make_render_camera(
                            *named_camera, static_cast<double>(w) / std::max(1, h));
                        camera = &*named_camera_snapshot;
                    }
                }
            }
        }
    }

    Mat44 view_d = camera->get_view_matrix();
    Mat44 proj_d = camera->get_projection_matrix();
    Mat44f view = view_d.to_float();
    Mat44f projection = proj_d.to_float();

    float near_plane = static_cast<float>(camera->near_clip);
    float far_plane = static_cast<float>(camera->far_clip);

    if (!ctx.ctx2) {
        tc::Log::error("[DepthPass] ctx.ctx2 is null — DepthPass is tgfx2-only");
        return;
    }

    execute_with_data_tgfx2(
        ctx,
        rect,
        scene,
        view,
        projection,
        near_plane,
        far_plane,
        ctx.layer_mask
    );
}

void DepthOnlyPass::ensure_tgfx2_resources(tgfx::IRenderDevice& device) {
    device2_ = &device;
    if (tc_shader_handle_is_invalid(depth_shader_handle_)) {
        depth_shader_handle_ =
            tgfx::register_builtin_shader_from_catalog(DEPTH_ONLY_ENGINE_SHADER_UUID);
    }
}

void DepthOnlyPass::release_tgfx2_resources() {
    if (!device2_) return;
    device2_ = nullptr;
}

CameraComponent* DepthOnlyPass::find_camera_by_name(
    tc_scene_handle scene,
    const std::string& name
) const {
    if (name.empty() || !tc_scene_handle_valid(scene)) {
        return nullptr;
    }

    tc_entity_id eid = tc_scene_find_entity_by_name(scene, name.c_str());
    if (!tc_entity_id_valid(eid)) {
        return nullptr;
    }

    Entity ent(tc_scene_entity_pool(scene), eid);
    return ent.get_component<CameraComponent>();
}

void DepthOnlyPass::collect_draw_calls(
    tc_scene_handle scene,
    uint64_t layer_mask,
    uint64_t render_category_mask
) const {
    cached_draw_calls_.clear();

    if (!tc_scene_handle_valid(scene)) {
        return;
    }

    if (pass_phase_mark.empty()) {
        tc::Log::error(
            "[DepthOnlyPass] pass '%s' has empty phase mark; geometry collection requires an explicit phase",
            get_pass_name().c_str());
        return;
    }

    struct CollectContext {
    public:
        const DepthOnlyPass* pass = nullptr;
        std::vector<DepthOnlyPass::DrawCall>* draw_calls = nullptr;
        MaterialPipelinePassContract pass_contract;
        RenderContext* render_context = nullptr;
    };

    auto callback = [](tc_component* c, void* user_data) -> bool {
        auto* collect_ctx = static_cast<CollectContext*>(user_data);
        Entity ent(c->owner);

        std::vector<GeometryDrawCall> material_phase_draws;
        void* draws_ptr = tc_component_get_geometry_draws(
            c,
            collect_ctx->render_context,
            collect_ctx->pass->pass_phase_mark.c_str());
        if (!draws_ptr) {
            return true;
        }
        auto* geometry_draws = static_cast<std::vector<GeometryDrawCall>*>(draws_ptr);
        material_phase_draws = *geometry_draws;

        for (const GeometryDrawCall& geometry_draw : *geometry_draws) {
            int geometry_id = geometry_draw.geometry_id;
            tc_shader_handle original_shader =
                collect_ctx->pass->depth_shader_handle_;
            const GeometryDrawCall* selected_material_draw = nullptr;
            for (const GeometryDrawCall& draw : material_phase_draws) {
                tc_material_phase* phase = draw.resolve_phase();
                if (draw.geometry_id == geometry_id &&
                    phase &&
                    !tc_shader_handle_is_invalid(phase->shader)) {
                    original_shader = phase->shader;
                    selected_material_draw = &draw;
                    break;
                }
            }

            DrawCall dc;
            dc.entity = ent;
            dc.component = c;
            ShaderOverrideContext override_context;
            override_context.phase_mark = collect_ctx->pass->pass_phase_mark;
            override_context.geometry_id = geometry_id;
            override_context.original_shader = TcShader(original_shader);
            override_context.pass_contract = collect_ctx->pass_contract;
            dc.final_shader = override_drawable_shader(c, override_context).handle;
            dc.geometry_id = geometry_id;
            if (selected_material_draw) {
                dc.material_phase = selected_material_draw->phase;
                dc.material = selected_material_draw->material;
                dc.phase_index = selected_material_draw->phase_index;
            }
            collect_ctx->draw_calls->push_back(dc);
        }
        return true;
    };

    RenderContext render_context;
    render_context.phase = pass_phase_mark;
    render_context.pass_contract = depth_material_pass_contract("depth_only");
    render_context.layer_mask = layer_mask;
    render_context.render_category_mask = render_category_mask;
    render_context.scene = TcSceneRef(scene);

    CollectContext collect_ctx{
        this,
        &cached_draw_calls_,
        depth_material_pass_contract("depth_only"),
        &render_context};

    int filter_flags = TC_SCENE_FILTER_ENABLED
                     | TC_SCENE_FILTER_VISIBLE
                     | TC_SCENE_FILTER_ENTITY_ENABLED;
    tc_scene_foreach_drawable(scene, callback, &collect_ctx, filter_flags, layer_mask);
}

void DepthOnlyPass::sort_draw_calls_by_shader() const {
    if (cached_draw_calls_.size() <= 1) {
        return;
    }

    std::sort(cached_draw_calls_.begin(), cached_draw_calls_.end(),
        [](const DrawCall& a, const DrawCall& b) {
            return a.final_shader.index < b.final_shader.index;
        });
}

void DepthOnlyPass::execute(ExecuteContext& ctx) {
    if (!ctx.ctx2) {
        tc::Log::error("[DepthOnlyPass] ctx.ctx2 is null — DepthOnlyPass is tgfx2-only");
        return;
    }

    tc_scene_handle scene = ctx.scene.handle();
    const RenderCamera* camera = ctx.camera;
    Rect4i rect = ctx.render_rect;
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

    auto depth_it = ctx.tex2_depth_writes.find(output_res);
    tgfx::TextureHandle depth_tex2 =
        (depth_it != ctx.tex2_depth_writes.end()) ? depth_it->second : tgfx::TextureHandle{};
    if (!depth_tex2) {
        auto texture_it = ctx.tex2_writes.find(output_res);
        depth_tex2 = (texture_it != ctx.tex2_writes.end())
            ? texture_it->second
            : tgfx::TextureHandle{};
    }
    if (!depth_tex2) {
        tc::Log::error("DepthOnlyPass/tgfx2: missing tgfx2 depth texture for '%s'",
                       output_res.c_str());
        return;
    }

    auto desc = ctx.ctx2->device().texture_desc(depth_tex2);
    int w = static_cast<int>(desc.width);
    int h = static_cast<int>(desc.height);
    if (w > 0 && h > 0) {
        rect = Rect4i(0, 0, w, h);
        if (!camera_name.empty()) {
            CameraComponent* named_camera = find_camera_by_name(scene, camera_name);
            if (named_camera) {
                named_camera_snapshot = make_render_camera(
                    *named_camera, static_cast<double>(w) / std::max(1, h));
                camera = &*named_camera_snapshot;
            }
        }
    }

    Mat44 view_d = camera->get_view_matrix();
    Mat44 proj_d = camera->get_projection_matrix();
    Mat44f view = view_d.to_float();
    Mat44f projection = proj_d.to_float();

    float near_plane = static_cast<float>(camera->near_clip);
    float far_plane = static_cast<float>(camera->far_clip);
    _near_plane = near_plane;
    _far_plane = far_plane;

    auto& device = ctx.ctx2->device();
    ensure_tgfx2_resources(device);
    collect_draw_calls(scene, ctx.layer_mask, ctx.render_category_mask);
    sort_draw_calls_by_shader();

    entity_names.clear();
    std::set<std::string> seen_entities;

    ctx.ctx2->begin_pass({}, depth_tex2, nullptr, 1.0f, true);
    ctx.ctx2->set_viewport(0, 0, rect.width, rect.height);
    ctx.ctx2->set_depth_test(true);
    ctx.ctx2->set_depth_write(true);
    ctx.ctx2->set_blend(false);
    ctx.ctx2->set_cull(tgfx::CullMode::Back);

    MaterialPipelineShaderBinding depth_shader{};
    if (!ensure_material_pipeline_shader(
            *ctx.ctx2,
            device,
            depth_shader_handle_,
            "DepthOnlyPass",
            depth_shader)) {
        return;
    }

    DepthPerFrameStd140 per_frame{};
    std::memcpy(per_frame.u_view, view.data, sizeof(float) * 16);
    std::memcpy(per_frame.u_projection, projection.data, sizeof(float) * 16);
    per_frame.u_near = near_plane;
    per_frame.u_far = far_plane;
    std::array<MaterialPipelineUniformData, 1> per_frame_uniforms{{
        {"per_frame", &per_frame, static_cast<uint32_t>(sizeof(per_frame))},
    }};
    MaterialPipelineResourceContext depth_resources{};
    depth_resources.uniforms = per_frame_uniforms;
    prepare_material_pipeline_resources(
        *ctx.ctx2,
        device,
        depth_shader.shader,
        nullptr,
        depth_resources);

    const std::string& debug_symbol = get_debug_internal_point();
    auto capture_debug_symbol = [&](const char* entity_name) {
        if (debug_symbol.empty() || !entity_name || debug_symbol != entity_name) {
            return;
        }
        FrameGraphCapture* capture = debug_capture();
        if (!capture || !depth_tex2) {
            return;
        }

        ctx.ctx2->end_pass();
        capture->capture_direct_via_ctx2(
            ctx.ctx2,
            depth_tex2,
            rect.width,
            rect.height);
        ctx.ctx2->begin_pass({}, depth_tex2, nullptr, 1.0f, false);
        ctx.ctx2->set_viewport(0, 0, rect.width, rect.height);
        ctx.ctx2->set_depth_test(true);
        ctx.ctx2->set_depth_write(true);
        ctx.ctx2->set_blend(false);
        ctx.ctx2->set_cull(tgfx::CullMode::Back);
        ctx.ctx2->bind_shader(depth_shader.vertex, depth_shader.fragment);
        ctx.ctx2->use_shader_resource_layout(depth_shader.shader);
        prepare_material_pipeline_resources(
            *ctx.ctx2,
            device,
            depth_shader.shader,
            nullptr,
            depth_resources);
    };

    for (const auto& dc : cached_draw_calls_) {
        Drawable* drawable = nullptr;
        if (tc_component_get_drawable_vtable(dc.component) == &Drawable::cxx_drawable_vtable()) {
            drawable = static_cast<Drawable*>(tc_component_get_drawable_userdata(dc.component));
        }
        if (!drawable) continue;

        MeshDrawGeometry mesh_geometry{};
        if (!drawable->resolve_mesh_geometry(pass_phase_mark, dc.geometry_id, mesh_geometry)) {
            continue;
        }

        Mat44f model = drawable->get_model_matrix(dc.entity);

        const char* name = dc.entity.name();
        if (name && seen_entities.insert(name).second) {
            entity_names.push_back(name);
        }

        bool override_is_base =
            tc_shader_handle_eq(dc.final_shader, depth_shader_handle_);
        tc_material_phase* material_phase = dc.resolve_material_phase();

        DepthDrawStd140 draw{};
        std::memcpy(draw.u_model, model.data, sizeof(float) * 16);
        std::array<MaterialPipelineUniformData, 2> draw_uniforms{{
            {"per_frame", &per_frame, static_cast<uint32_t>(sizeof(per_frame))},
            {"depth_draw", &draw, static_cast<uint32_t>(sizeof(draw))},
        }};
        MaterialPipelineResourceContext draw_resources{};
        draw_resources.uniforms = draw_uniforms;

        if (override_is_base) {
            prepare_material_pipeline_resources(
                *ctx.ctx2,
                device,
                depth_shader.shader,
                nullptr,
                draw_resources);
            draw_material_pipeline_submesh(
                *ctx.ctx2,
                mesh_geometry.mesh,
                mesh_geometry.submesh_index,
                material_mesh_vertex_input_for_shader(
                    depth_shader.shader,
                    MaterialMeshVertexInput::Position));
            capture_debug_symbol(name);
        } else {
            MaterialPipelineShaderBinding skinned_shader{};
            if (!ensure_material_pipeline_shader(
                    *ctx.ctx2,
                    device,
                    dc.final_shader,
                    "DepthOnlyPass/skinned",
                    skinned_shader)) {
                continue;
            }
            prepare_material_pipeline_resources(
                *ctx.ctx2,
                device,
                skinned_shader.shader,
                material_phase,
                draw_resources);

            drawable->upload_per_draw_uniforms_tgfx2(*ctx.ctx2, dc.geometry_id);

            draw_material_pipeline_submesh(
                *ctx.ctx2,
                mesh_geometry.mesh,
                mesh_geometry.submesh_index,
                material_mesh_vertex_input_for_shader(
                    skinned_shader.shader,
                    MaterialMeshVertexInput::Position));
            capture_debug_symbol(name);

            ctx.ctx2->bind_shader(depth_shader.vertex, depth_shader.fragment);
            ctx.ctx2->use_shader_resource_layout(depth_shader.shader);
            prepare_material_pipeline_resources(
                *ctx.ctx2,
                device,
                depth_shader.shader,
                nullptr,
                depth_resources);
        }
    }

    ctx.ctx2->end_pass();
}

void DepthToColorPass::ensure_tgfx2_resources(tgfx::IRenderDevice& device) {
    device2_ = &device;
    if (tc_shader_handle_is_invalid(shader_handle_)) {
        shader_handle_ =
            tgfx::register_builtin_shader_from_catalog(DEPTH_TO_COLOR_ENGINE_SHADER_UUID);
    }
}

void DepthToColorPass::release_tgfx2_resources() {
    device2_ = nullptr;
}

void DepthToColorPass::execute(ExecuteContext& ctx) {
    if (!ctx.ctx2) {
        tc::Log::error("[DepthToColorPass] ctx.ctx2 is null");
        return;
    }

    auto depth_it = ctx.tex2_depth_reads.find(input_res);
    tgfx::TextureHandle depth_tex =
        (depth_it != ctx.tex2_depth_reads.end()) ? depth_it->second : tgfx::TextureHandle{};
    if (!depth_tex) {
        auto texture_it = ctx.tex2_reads.find(input_res);
        depth_tex = (texture_it != ctx.tex2_reads.end()) ? texture_it->second : tgfx::TextureHandle{};
    }
    if (!depth_tex) {
        tc::Log::error("[DepthToColorPass] missing depth input '%s'", input_res.c_str());
        return;
    }

    auto color_it = ctx.tex2_writes.find(output_res);
    tgfx::TextureHandle color_tex =
        (color_it != ctx.tex2_writes.end()) ? color_it->second : tgfx::TextureHandle{};
    if (!color_tex) {
        tc::Log::error("[DepthToColorPass] missing color output '%s'", output_res.c_str());
        return;
    }

    auto& device = ctx.ctx2->device();
    ensure_tgfx2_resources(device);

    tgfx::ShaderHandle fs;
    tc_shader* raw = tc_shader_get(shader_handle_);
    if (!raw || !tc_shader_ensure_tgfx2(raw, &device, nullptr, &fs)) {
        tc::Log::error("[DepthToColorPass] failed to prepare shader");
        return;
    }

    tgfx::TextureDesc desc = device.texture_desc(color_tex);
    int w = static_cast<int>(desc.width);
    int h = static_cast<int>(desc.height);
    if (w <= 0 || h <= 0) {
        tc::Log::error("[DepthToColorPass] invalid output size for '%s'", output_res.c_str());
        return;
    }

    ctx.ctx2->begin_pass(color_tex, {}, nullptr, 1.0f, false);
    ctx.ctx2->set_viewport(0, 0, w, h);
    ctx.ctx2->set_depth_test(false);
    ctx.ctx2->set_depth_write(false);
    ctx.ctx2->set_blend(false);
    ctx.ctx2->set_cull(tgfx::CullMode::None);
    ctx.ctx2->bind_shader(ctx.ctx2->fsq_vertex_shader(), fs);
    ctx.ctx2->use_shader_resource_layout(raw);
    ctx.ctx2->clear_resource_bindings();
    ctx.ctx2->bind_texture("u_depth_tex", depth_tex);
    ctx.ctx2->draw_fullscreen_quad();
    ctx.ctx2->end_pass();
}

void ColorToDepthPass::ensure_tgfx2_resources(tgfx::IRenderDevice& device) {
    device2_ = &device;
    if (tc_shader_handle_is_invalid(shader_handle_)) {
        shader_handle_ =
            tgfx::register_builtin_shader_from_catalog(COLOR_TO_DEPTH_ENGINE_SHADER_UUID);
    }
}

void ColorToDepthPass::release_tgfx2_resources() {
    device2_ = nullptr;
}

void ColorToDepthPass::execute(ExecuteContext& ctx) {
    if (!ctx.ctx2) {
        tc::Log::error("[ColorToDepthPass] ctx.ctx2 is null");
        return;
    }

    auto color_it = ctx.tex2_reads.find(input_res);
    tgfx::TextureHandle color_tex =
        (color_it != ctx.tex2_reads.end()) ? color_it->second : tgfx::TextureHandle{};
    if (!color_tex) {
        tc::Log::error("[ColorToDepthPass] missing color input '%s'", input_res.c_str());
        return;
    }

    auto depth_it = ctx.tex2_depth_writes.find(output_res);
    tgfx::TextureHandle depth_tex =
        (depth_it != ctx.tex2_depth_writes.end()) ? depth_it->second : tgfx::TextureHandle{};
    if (!depth_tex) {
        auto texture_it = ctx.tex2_writes.find(output_res);
        depth_tex = (texture_it != ctx.tex2_writes.end()) ? texture_it->second : tgfx::TextureHandle{};
    }
    if (!depth_tex) {
        tc::Log::error("[ColorToDepthPass] missing depth output '%s'", output_res.c_str());
        return;
    }

    auto& device = ctx.ctx2->device();
    ensure_tgfx2_resources(device);

    tgfx::ShaderHandle fs;
    tc_shader* raw = tc_shader_get(shader_handle_);
    if (!raw || !tc_shader_ensure_tgfx2(raw, &device, nullptr, &fs)) {
        tc::Log::error("[ColorToDepthPass] failed to prepare shader");
        return;
    }

    tgfx::TextureDesc desc = device.texture_desc(depth_tex);
    int w = static_cast<int>(desc.width);
    int h = static_cast<int>(desc.height);
    if (w <= 0 || h <= 0) {
        tc::Log::error("[ColorToDepthPass] invalid output size for '%s'", output_res.c_str());
        return;
    }

    ctx.ctx2->begin_pass({}, depth_tex, nullptr, 1.0f, true);
    ctx.ctx2->set_viewport(0, 0, w, h);
    ctx.ctx2->set_depth_test(false);
    ctx.ctx2->set_depth_write(true);
    ctx.ctx2->set_blend(false);
    ctx.ctx2->set_cull(tgfx::CullMode::None);
    ctx.ctx2->bind_shader(ctx.ctx2->fsq_vertex_shader(), fs);
    ctx.ctx2->use_shader_resource_layout(raw);
    ctx.ctx2->clear_resource_bindings();
    ctx.ctx2->bind_texture("u_color_tex", color_tex);
    ctx.ctx2->draw_fullscreen_quad();
    ctx.ctx2->end_pass();
}

TC_REGISTER_FRAME_PASS_DERIVED(DepthPass, GeometryPassBase);
TC_REGISTER_FRAME_PASS_DERIVED(DepthOnlyPass, CxxFramePass);
TC_REGISTER_FRAME_PASS_DERIVED(DepthToColorPass, CxxFramePass);
TC_REGISTER_FRAME_PASS_DERIVED(ColorToDepthPass, CxxFramePass);

} // namespace termin
