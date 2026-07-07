#include <tcbase/tc_log.hpp>
#include <tgfx/tgfx_shader_handle.hpp>

#include <termin/render/id_pass.hpp>
#include "termin/camera/render_camera_utils.hpp"
#include "termin/render/frame_graph_debugger_core.hpp"
#include "termin/render/material_pipeline.hpp"
#include "termin/render/shader_abi.hpp"
#include "termin/render/tgfx2_bridge.hpp"

#include "tgfx2/builtin_shader_sources.hpp"
#include "tgfx2/render_context.hpp"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/tc_shader_bridge.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <optional>
#include <span>
#include <vector>

extern "C" {
#include "tc_picking.h"
#include <tgfx/resources/tc_shader_registry.h>
#include <tgfx/resources/tc_mesh_registry.h>
#include "core/tc_drawable_protocol.h"
}

#include <termin/camera/camera_component.hpp>

namespace termin {

constexpr const char* ID_ENGINE_SHADER_UUID = "termin-engine-id";

namespace {

// PerFrame UBO (binding 0): view + projection. 128 bytes std140.
struct IdPerFrameStd140 {
    float u_view[16];
    float u_projection[16];
};
static_assert(sizeof(IdPerFrameStd140) == 128,
              "IdPerFrameStd140 must be 2 * mat4");

// Draw-scope per-object model matrix + pick color. The shader resource
// layout maps it to backend storage; render code binds it by reflected name.
// 64 + 16 = 80 bytes. vec4 used for pickColor because std140 pads
// vec3 to 16-byte alignment anyway.
struct IdPushStd140 {
    float u_model[16];
    float u_pickColor[4];  // vec3 + pad
};
static_assert(sizeof(IdPushStd140) == 80,
              "IdPushStd140 must be mat4 + vec4");

static constexpr uint32_t ID_BONE_BLOCK_MAX_BONES = 128;
static constexpr uint64_t ID_BONE_BLOCK_SIZE =
    ID_BONE_BLOCK_MAX_BONES * 16u * sizeof(float) + 16u;

struct IdMeshTask {
    Entity entity;
    tc_render_item item{};
    tc_shader_handle final_shader = tc_shader_handle_invalid();
    int pick_id = 0;
};

MaterialPipelinePassContract id_material_pass_contract()
{
    MaterialPipelinePassContract contract;
    contract.debug_name = "id";
    contract.required_material_fragment_input = MaterialFragmentInterface{};
    contract.uses_material_fragment = true;

    MaterialFragmentInterface fragment_input =
        material_pipeline_standard_material_fragment_interface();
    contract.static_vertex_transform =
        material_pipeline_make_static_vertex_transform_contract(
            "static_id",
            material_pipeline_position_mesh_input(),
            fragment_input,
            material_pipeline_common_vertex_resources("id_draw", 80u));
    contract.skinned_vertex_transform =
        material_pipeline_make_skinned_vertex_transform_contract(
            *contract.static_vertex_transform,
            "skinned_id",
            "termin-engine-skinned-id",
            material_pipeline_skinned_position_mesh_input());
    return contract;
}

bool same_drawable_geometry(tc_component* component, int geometry_id, const IdMeshTask& task) {
    return task.item.component == component && task.item.geometry_id == geometry_id;
}

bool has_mesh_task_for(
    const std::vector<IdMeshTask>& tasks,
    tc_component* component,
    int geometry_id)
{
    return std::any_of(
        tasks.begin(),
        tasks.end(),
        [component, geometry_id](const IdMeshTask& task) {
            return same_drawable_geometry(component, geometry_id, task);
        });
}

std::vector<uint8_t> pack_id_bone_block(const tc_render_item& item) {
    std::vector<uint8_t> staging(ID_BONE_BLOCK_SIZE, 0);
    const uint32_t matrix_count = std::min<uint32_t>(
        item.payload.mesh.skinning_matrix_count,
        ID_BONE_BLOCK_MAX_BONES);
    if (matrix_count > 0 && item.payload.mesh.skinning_matrices) {
        std::memcpy(
            staging.data(),
            item.payload.mesh.skinning_matrices,
            matrix_count * 16u * sizeof(float));
    }
    int32_t count = static_cast<int32_t>(matrix_count);
    std::memcpy(
        staging.data() + ID_BONE_BLOCK_MAX_BONES * 16u * sizeof(float),
        &count,
        sizeof(int32_t));
    return staging;
}

tc_mesh* id_mesh_task_mesh(const IdMeshTask& task) {
    const tc_mesh_handle mesh_handle = task.item.payload.mesh.mesh_handle;
    if (tc_mesh_handle_is_invalid(mesh_handle)) {
        return nullptr;
    }
    return tc_mesh_get(mesh_handle);
}

bool validate_id_mesh_item_for_draw(const IdMeshTask& task, tc_mesh** out_mesh) {
    if (out_mesh) {
        *out_mesh = nullptr;
    }
    const char* entity_name = task.entity.name() ? task.entity.name() : "<unnamed>";
    const tc_mesh_handle mesh_handle = task.item.payload.mesh.mesh_handle;
    if (tc_mesh_handle_is_invalid(mesh_handle)) {
        tc::Log::error(
            "[IdPass] skip RenderItem mesh draw for '%s': mesh payload has no stable handle",
            entity_name);
        return false;
    }

    tc_mesh* mesh = id_mesh_task_mesh(task);
    if (!mesh) {
        tc::Log::error(
            "[IdPass] skip RenderItem mesh draw for '%s': mesh handle is stale or invalid",
            entity_name);
        return false;
    }
    if (mesh->submesh_count == 0) {
        tc::Log::error(
            "[IdPass] skip RenderItem mesh draw for '%s': mesh has no submeshes",
            entity_name);
        return false;
    }
    const tc_submesh* submesh = tc_mesh_get_submesh(mesh, task.item.payload.mesh.submesh_index);
    if (!submesh) {
        tc::Log::error(
            "[IdPass] skip RenderItem mesh draw for '%s': mesh has no submesh %zu (count=%zu)",
            entity_name,
            task.item.payload.mesh.submesh_index,
            mesh->submesh_count);
        return false;
    }
    if (submesh->index_count == 0 ||
        static_cast<size_t>(submesh->first_index) > mesh->index_count ||
        static_cast<size_t>(submesh->index_count) >
            mesh->index_count - static_cast<size_t>(submesh->first_index)) {
        tc::Log::error(
            "[IdPass] skip RenderItem mesh draw for '%s': invalid submesh %zu first=%u count=%u mesh_indices=%zu",
            entity_name,
            task.item.payload.mesh.submesh_index,
            submesh->first_index,
            submesh->index_count,
            mesh->index_count);
        return false;
    }
    if (out_mesh) {
        *out_mesh = mesh;
    }
    return true;
}

} // anonymous namespace

MaterialPipelinePassContract IdPass::shader_pass_contract() const {
    return id_material_pass_contract();
}

tc_shader_handle IdPass::shader_usage_base_shader() const {
    if (tc_shader_handle_is_invalid(id_shader_handle_)) {
        id_shader_handle_ = tgfx::register_builtin_shader_from_catalog(ID_ENGINE_SHADER_UUID);
    }
    return id_shader_handle_;
}

void IdPass::id_to_rgb(int id, float& r, float& g, float& b) {
    tc_picking_id_to_rgb_float(id, &r, &g, &b);
}

void IdPass::ensure_tgfx2_resources(tgfx::IRenderDevice& device) {
    device2_ = &device;

    // Engine-shader cache via TcShader registry (see ShadowPass for the
    // rationale): hash-based dedup keeps the same handle across pass
    // re-creations, and the render device cache keeps compiled shader
    // modules live for zero-compile subsequent binds.
    if (tc_shader_handle_is_invalid(id_shader_handle_)) {
        id_shader_handle_ = tgfx::register_builtin_shader_from_catalog(ID_ENGINE_SHADER_UUID);
    }

}

void IdPass::release_tgfx2_resources() {
    if (!device2_) return;
    // id_shader_handle_ is static engine shader — not released here.
    device2_ = nullptr;
}

// ----------------------------------------------------------------------------
// tgfx2 path — Stage 5.C.
// ----------------------------------------------------------------------------
//
// Writes a color attachment (RGBA-encoded pick IDs) and uses depth test +
// write for occlusion. Parameter block is a single 208-byte std140 UBO
// containing {model, view, projection, pickColor}. Mesh-backed drawables are
// submitted through RenderItems. Direct non-mesh drawables still use their
// typed override-color draw hook until line/text/etc. gain RenderItem encoders.
void IdPass::execute_with_data_tgfx2(
    ExecuteContext& ctx,
    const Rect4i& rect,
    tc_scene_handle scene,
    const Mat44f& view,
    const Mat44f& projection,
    const Vec3& camera_position,
    uint64_t layer_mask
) {
    if (!ctx.ctx2) {
        tc::Log::error("IdPass/tgfx2: ctx2 is null");
        return;
    }

    auto color_it = ctx.tex2_writes.find(output_res);
    if (color_it == ctx.tex2_writes.end() || !color_it->second) {
        tc::Log::error("IdPass/tgfx2: missing tgfx2 color texture for '%s'",
                       output_res.c_str());
        return;
    }
    tgfx::TextureHandle color_tex2 = color_it->second;

    auto depth_it = ctx.tex2_depth_writes.find(output_res);
    tgfx::TextureHandle depth_tex2 =
        (depth_it != ctx.tex2_depth_writes.end()) ? depth_it->second : tgfx::TextureHandle{};

    auto& device = ctx.ctx2->device();

    ensure_tgfx2_resources(device);

    const MaterialPipelinePassContract pass_contract = id_material_pass_contract();
    const char* pick_phase = phase_mark();

    std::vector<IdMeshTask> mesh_tasks;
    if (tc_scene_handle_valid(scene)) {
        struct CollectItemsContext {
            IdPass* pass = nullptr;
            std::vector<IdMeshTask>* tasks = nullptr;
            MaterialPipelinePassContract pass_contract;
            tc_shader_handle base_shader = tc_shader_handle_invalid();
            const char* phase_mark = nullptr;
            uint64_t layer_mask = 0;
            uint64_t render_category_mask = 0;
        };

        CollectItemsContext collect_context{
            this,
            &mesh_tasks,
            pass_contract,
            id_shader_handle_,
            pick_phase,
            layer_mask,
            ctx.render_category_mask};

        auto collect_callback = [](tc_component* component, void* user_data) -> bool {
            auto* data = static_cast<CollectItemsContext*>(user_data);
            if (!component || !data || !data->tasks || !data->phase_mark) {
                tc::Log::error("[IdPass] invalid RenderItem collection callback state");
                return true;
            }

            Entity entity(component->owner);
            if (!entity.valid() || !entity.pickable()) {
                return true;
            }

            tc_render_item_collect_context item_context{};
            item_context.phase_mark = data->phase_mark;
            item_context.flags = TC_RENDER_ITEM_COLLECT_FLAG_ALLOW_MISSING_MATERIAL_PHASE;
            item_context.layer_mask = data->layer_mask;
            item_context.render_category_mask = data->render_category_mask;
            item_context.debug_pass_name = data->pass ? data->pass->get_pass_name().c_str() : "IdPass";
            item_context.pass_contract = &data->pass_contract;

            std::vector<tc_render_item> items;
            if (!collect_drawable_render_items(component, item_context, items)) {
                return true;
            }

            for (const tc_render_item& item : items) {
                if (item.kind != TC_RENDER_ITEM_KIND_MESH) {
                    continue;
                }

                ShaderOverrideContext override_context;
                override_context.phase_mark = data->phase_mark;
                override_context.geometry_id = item.geometry_id;
                override_context.original_shader = TcShader(data->base_shader);
                override_context.pass_contract = data->pass_contract;

                IdMeshTask task;
                task.entity = entity;
                task.item = item;
                task.final_shader = override_drawable_shader(component, override_context).handle;
                task.pick_id = static_cast<int>(entity.pick_id());
                data->tasks->push_back(task);
            }
            return true;
        };

        int filter_flags = TC_SCENE_FILTER_ENABLED
                         | TC_SCENE_FILTER_VISIBLE
                         | TC_SCENE_FILTER_ENTITY_ENABLED;
        tc_scene_foreach_drawable(scene, collect_callback, &collect_context, filter_flags, layer_mask);
        std::sort(mesh_tasks.begin(), mesh_tasks.end(),
            [](const IdMeshTask& a, const IdMeshTask& b) {
                return a.final_shader.index < b.final_shader.index;
            });
    }

    // GeometryDrawCall collection is retained only to discover direct non-mesh
    // drawables until they grow typed RenderItems. Mesh-backed work is
    // submitted from mesh_tasks above.
    collect_draw_calls(scene, layer_mask, ctx.render_category_mask, id_shader_handle_);
    sort_draw_calls_by_shader();

    entity_names.clear();
    std::set<std::string> seen_entities;

    auto cc = clear_color();
    float clear_rgba[4] = {cc[0], cc[1], cc[2], cc[3]};

    ctx.ctx2->begin_pass(color_tex2, depth_tex2, clear_rgba, 1.0f, true);
    ctx.ctx2->set_viewport(0, 0, rect.width, rect.height);
    ctx.ctx2->set_depth_test(true);
    ctx.ctx2->set_depth_write(true);
    ctx.ctx2->set_blend(false);
    ctx.ctx2->set_cull(tgfx::CullMode::Back);

    MaterialPipelineShaderBinding id_shader{};
    if (!ensure_material_pipeline_shader(
            *ctx.ctx2,
            device,
            id_shader_handle_,
            "IdPass",
            id_shader)) {
        return;
    }

    // PerFrame UBO: view + projection, one write per pass via the ring.
    IdPerFrameStd140 per_frame{};
    std::memcpy(per_frame.u_view, view.data, sizeof(float) * 16);
    std::memcpy(per_frame.u_projection, projection.data, sizeof(float) * 16);
    std::array<MaterialPipelineUniformUpload, 1> per_frame_uniforms{{
        {
            tc_shader_find_resource_binding(id_shader.shader, "per_frame"),
            &per_frame,
            static_cast<uint32_t>(sizeof(per_frame)),
        },
    }};
    MaterialPipelineResourceView id_resources{};
    id_resources.uniforms = per_frame_uniforms.data();
    id_resources.uniform_count = static_cast<uint32_t>(per_frame_uniforms.size());
    prepare_material_pipeline_resources(
        *ctx.ctx2,
        device,
        id_shader.shader,
        nullptr,
        id_resources);

    auto restore_id_raster_state = [&]() {
        ctx.ctx2->set_depth_test(true);
        ctx.ctx2->set_depth_write(true);
        ctx.ctx2->set_blend(false);
        ctx.ctx2->set_cull(tgfx::CullMode::Back);
        ctx.ctx2->bind_shader(id_shader.vertex, id_shader.fragment);
        ctx.ctx2->use_shader_resource_layout(id_shader.shader);
    };

    const std::string& debug_symbol = get_debug_internal_point();
    int current_pick_id = -1;
    float pick_r = 0.0f;
    float pick_g = 0.0f;
    float pick_b = 0.0f;

    auto capture_debug_symbol = [&](const char* entity_name) {
        if (debug_symbol.empty() || !entity_name || debug_symbol != entity_name) {
            return;
        }
        FrameGraphCapture* capture = debug_capture();
        if (!capture) {
            return;
        }

        ctx.ctx2->end_pass();
        capture->capture_direct_via_ctx2(ctx.ctx2, color_tex2, rect.width, rect.height);
        ctx.ctx2->begin_pass(color_tex2, depth_tex2, nullptr, 1.0f, false);
        ctx.ctx2->set_viewport(0, 0, rect.width, rect.height);
        restore_id_raster_state();
        ctx.ctx2->clear_resource_bindings();
        prepare_material_pipeline_resources(
            *ctx.ctx2,
            device,
            id_shader.shader,
            nullptr,
            id_resources);
    };

    auto draw_mesh_task = [&](const IdMeshTask& task) {
        tc_mesh* mesh = nullptr;
        if (!validate_id_mesh_item_for_draw(task, &mesh)) {
            return;
        }

        const char* name = task.entity.name();
        if (name && seen_entities.insert(name).second) {
            entity_names.push_back(name);
        }

        if (task.pick_id != current_pick_id) {
            current_pick_id = task.pick_id;
            id_to_rgb(task.pick_id, pick_r, pick_g, pick_b);
        }

        bool override_is_base =
            tc_shader_handle_eq(task.final_shader, id_shader_handle_);

        // Push constants (u_model + u_pickColor) are shared between the
        // base and skinned paths. The skinned variant uses the same id shader
        // interface plus a reflected BoneBlock resource.
        IdPushStd140 push{};
        if (task.item.flags & TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX) {
            std::memcpy(push.u_model, task.item.model_matrix, sizeof(float) * 16);
        } else {
            Mat44f identity = Mat44f::identity();
            std::memcpy(push.u_model, identity.data, sizeof(float) * 16);
        }
        push.u_pickColor[0] = pick_r;
        push.u_pickColor[1] = pick_g;
        push.u_pickColor[2] = pick_b;
        push.u_pickColor[3] = 1.0f;

        std::array<MaterialPipelineUniformData, 2> base_draw_uniforms{{
            {"per_frame", &per_frame, static_cast<uint32_t>(sizeof(per_frame))},
            {"id_draw", &push, static_cast<uint32_t>(sizeof(push))},
        }};

        if (override_is_base) {
            MaterialPipelineResourceContext draw_resources{};
            draw_resources.uniforms = base_draw_uniforms;
            prepare_material_pipeline_resources(
                *ctx.ctx2,
                device,
                id_shader.shader,
                nullptr,
                draw_resources);
            draw_material_pipeline_submesh(
                *ctx.ctx2,
                mesh,
                task.item.payload.mesh.submesh_index,
                material_mesh_vertex_input_for_shader(
                    id_shader.shader,
                    MaterialMeshVertexInput::Position));
            capture_debug_symbol(name);
        } else {
            MaterialPipelineShaderBinding skinned_shader{};
            if (!ensure_material_pipeline_shader(
                    *ctx.ctx2,
                    device,
                    task.final_shader,
                    "IdPass/skinned",
                    skinned_shader)) {
                return;
            }

            std::array<MaterialPipelineUniformData, 3> skinned_draw_uniforms{{
                base_draw_uniforms[0],
                base_draw_uniforms[1],
                {},
            }};
            size_t skinned_draw_uniform_count = 2;
            std::vector<uint8_t> bone_block;
            if (task.item.flags & TC_RENDER_ITEM_FLAG_HAS_SKINNING_MATRICES) {
                if (!find_shader_abi_resource_binding(skinned_shader.shader, ShaderAbiResourceId::BoneBlock)) {
                    tc::Log::error(
                        "[IdPass] skip skinned RenderItem mesh draw for '%s': shader '%s' has no bone_block resource",
                        name ? name : "<unnamed>",
                        skinned_shader.shader && skinned_shader.shader->name
                            ? skinned_shader.shader->name
                            : "<unnamed>");
                    return;
                }
                bone_block = pack_id_bone_block(task.item);
                skinned_draw_uniforms[skinned_draw_uniform_count++] = {
                    TC_SHADER_RESOURCE_BONE_BLOCK,
                    bone_block.data(),
                    static_cast<uint32_t>(bone_block.size()),
                };
            }
            MaterialPipelineResourceContext draw_resources{};
            draw_resources.uniforms = std::span<const MaterialPipelineUniformData>(
                skinned_draw_uniforms.data(),
                skinned_draw_uniform_count);
            prepare_material_pipeline_resources(
                *ctx.ctx2,
                device,
                skinned_shader.shader,
                nullptr,
                draw_resources);

            draw_material_pipeline_submesh(
                *ctx.ctx2,
                mesh,
                task.item.payload.mesh.submesh_index,
                material_mesh_vertex_input_for_shader(
                    skinned_shader.shader,
                    MaterialMeshVertexInput::Position));
            capture_debug_symbol(name);

            ctx.ctx2->bind_shader(id_shader.vertex, id_shader.fragment);
            ctx.ctx2->use_shader_resource_layout(id_shader.shader);
            ctx.ctx2->clear_resource_bindings();
            prepare_material_pipeline_resources(
                *ctx.ctx2,
                device,
                id_shader.shader,
                nullptr,
                id_resources);
        }
    };

    for (const IdMeshTask& task : mesh_tasks) {
        draw_mesh_task(task);
    }

    for (const auto& dc : cached_draw_calls_) {
        if (has_mesh_task_for(mesh_tasks, dc.component, dc.geometry_id)) {
            continue;
        }

        Drawable* drawable = nullptr;
        if (tc_component_get_drawable_vtable(dc.component) == &Drawable::cxx_drawable_vtable()) {
            drawable = static_cast<Drawable*>(tc_component_get_drawable_userdata(dc.component));
        }
        if (!drawable) continue;

        const char* name = dc.entity.name();
        if (name && seen_entities.insert(name).second) {
            entity_names.push_back(name);
        }

        if (dc.pick_id != current_pick_id) {
            current_pick_id = dc.pick_id;
            id_to_rgb(dc.pick_id, pick_r, pick_g, pick_b);
        }

        MeshDrawGeometry mesh_geometry{};
        if (drawable->resolve_mesh_geometry(pick_phase, dc.geometry_id, mesh_geometry)) {
            tc::Log::error(
                "[IdPass] mesh drawable reached non-RenderItem path after migration for entity '%s' geometry=%d",
                name ? name : "<unnamed>",
                dc.geometry_id);
            continue;
        }
        if (!drawable->supports_direct_tgfx2_draw(
                pick_phase, dc.geometry_id, DirectTgfx2DrawKind::OverrideColor)) {
            continue;
        }

        RenderContext direct_context;
        direct_context.view = view;
        direct_context.projection = projection;
        direct_context.model = drawable->get_model_matrix(dc.entity);
        direct_context.phase = pick_phase;
        direct_context.pass_contract = pass_contract;
        direct_context.current_tc_shader = TcShader(dc.final_shader);
        direct_context.layer_mask = layer_mask;
        direct_context.render_category_mask = ctx.render_category_mask;
        direct_context.camera_position = camera_position;
        direct_context.viewport_width = rect.width;
        direct_context.viewport_height = rect.height;
        direct_context.has_override_color = true;
        direct_context.override_color = Vec4{pick_r, pick_g, pick_b, 1.0};

        drawable->draw_tgfx2(*ctx.ctx2, direct_context, pick_phase, nullptr, dc.geometry_id);
        capture_debug_symbol(name);
        restore_id_raster_state();
        ctx.ctx2->clear_resource_bindings();
        prepare_material_pipeline_resources(
            *ctx.ctx2,
            device,
            id_shader.shader,
            nullptr,
            id_resources);
    }

    ctx.ctx2->end_pass();
    // color_tex2/depth_tex2 are persistent FBOPool wrappers — do not destroy.
}

void IdPass::execute(ExecuteContext& ctx) {
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

    // Override rect with output texture size (may differ from ctx.render_rect if
    // the pipeline routes to a non-default-sized target).
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
    Vec3 camera_position = camera->get_position();

    if (!ctx.ctx2) {
        tc::Log::error("[IdPass] ctx.ctx2 is null — IdPass is tgfx2-only");
        return;
    }

    execute_with_data_tgfx2(
        ctx,
        rect,
        scene,
        view,
        projection,
        camera_position,
        ctx.layer_mask
    );
}

TC_REGISTER_FRAME_PASS_DERIVED(IdPass, GeometryPassBase);

} // namespace termin
