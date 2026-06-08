#include "render_target_context_builder.hpp"

#include "rendering_manager_utils.hpp"
#include "termin/render/render_camera.hpp"
#include "termin/render/tgfx2_bridge.hpp"

#include <algorithm>
#include <cstring>

#include <tgfx2/i_render_device.hpp>

extern "C" {
#include <tcbase/tc_log.h>
#include "core/tc_camera_capability.h"
#include "core/tc_scene.h"
#include "render/tc_render_target.h"
#include "tgfx/resources/tc_texture_registry.h"
}

namespace termin::rendering_manager_detail {

static uint64_t render_target_key(tc_render_target_handle h) {
    return (static_cast<uint64_t>(h.index) << 32) | h.generation;
}

static RenderCamera render_camera_from_cap(const tc_camera_data& cd) {
    RenderCamera rc;
    std::memcpy(rc.view.data, cd.view, sizeof(cd.view));
    std::memcpy(rc.projection.data, cd.projection, sizeof(cd.projection));
    rc.position = Vec3(cd.position[0], cd.position[1], cd.position[2]);
    rc.near_clip = cd.near_clip;
    rc.far_clip = cd.far_clip;
    return rc;
}

static uint64_t effective_layer_mask(uint64_t camera_mask, tc_render_target_handle rt) {
    uint64_t target_mask = tc_render_target_handle_valid(rt)
        ? tc_render_target_get_layer_mask(rt)
        : 0xFFFFFFFFFFFFFFFFULL;
    return camera_mask & target_mask;
}

static void fill_render_target_clear_settings(RenderTargetContext& ctx, tc_render_target_handle rt) {
    if (!tc_render_target_handle_valid(rt)) return;
    ctx.clear_color_enabled = tc_render_target_get_clear_color_enabled(rt);
    tc_render_target_get_clear_color_value(rt, ctx.clear_color);
    ctx.clear_depth_enabled = tc_render_target_get_clear_depth_enabled(rt);
    ctx.clear_depth = tc_render_target_get_clear_depth_value(rt);
}

void resolve_render_target_size_for_viewport(
    tc_render_target_handle rt,
    int viewport_width,
    int viewport_height,
    int& render_width,
    int& render_height
) {
    render_width = viewport_width;
    render_height = viewport_height;

    if (!tc_render_target_handle_valid(rt)) {
        return;
    }

    if (tc_render_target_get_dynamic_resolution(rt)) {
        tc_render_target_set_width(rt, viewport_width);
        tc_render_target_set_height(rt, viewport_height);
        return;
    }

    int fixed_width = tc_render_target_get_width(rt);
    int fixed_height = tc_render_target_get_height(rt);
    if (fixed_width > 0 && fixed_height > 0) {
        render_width = fixed_width;
        render_height = fixed_height;
    }
}

static tc_render_target_handle find_render_target_by_name(
    const char* name,
    tc_scene_handle preferred_scene,
    const std::vector<tc_render_target_handle>& render_targets
) {
    if (!name || name[0] == '\0') {
        return TC_RENDER_TARGET_HANDLE_INVALID;
    }

    for (tc_render_target_handle rt : render_targets) {
        if (!tc_render_target_handle_valid(rt)) {
            continue;
        }
        const char* candidate = tc_render_target_get_name(rt);
        if (!candidate || std::strcmp(candidate, name) != 0) {
            continue;
        }

        if (tc_scene_handle_valid(preferred_scene)) {
            tc_scene_handle scene = tc_render_target_get_scene(rt);
            if (!tc_scene_handle_eq(scene, preferred_scene)) {
                continue;
            }
        }
        return rt;
    }

    return TC_RENDER_TARGET_HANDLE_INVALID;
}

static tgfx::TextureHandle resolve_pipeline_texture_ref(
    tgfx::IRenderDevice& device,
    tc_scene_handle preferred_scene,
    const std::vector<tc_render_target_handle>& render_targets,
    const char* ref
) {
    if (!ref || ref[0] == '\0') {
        return {};
    }

    constexpr const char* file_prefix = "file:";
    const char* texture_name = ref;
    if (std::strncmp(ref, file_prefix, std::strlen(file_prefix)) == 0) {
        texture_name = ref + std::strlen(file_prefix);
        tc_texture_handle tex = tc_texture_find(texture_name);
        if (tc_texture_handle_is_invalid(tex)) {
            tex = tc_texture_find_by_name(texture_name);
        }
        if (tc_texture_handle_is_invalid(tex)) {
            tc_log(TC_LOG_WARN, "[RenderingManager] pipeline texture ref '%s' not found", ref);
            return {};
        }
        return wrap_tc_texture_as_tgfx2(device, tex);
    }

    tc_render_target_handle rt = find_render_target_by_name(ref, preferred_scene, render_targets);
    if (tc_render_target_handle_valid(rt)) {
        tc_render_target_ensure_textures(rt);
        return wrap_tc_texture_as_tgfx2(device, tc_render_target_get_color_texture(rt));
    }

    tc_texture_handle tex = tc_texture_find_by_name(texture_name);
    if (tc_texture_handle_is_invalid(tex)) {
        tex = tc_texture_find(texture_name);
    }
    if (tc_texture_handle_is_invalid(tex)) {
        tc_log(TC_LOG_WARN, "[RenderingManager] pipeline texture ref '%s' not found", ref);
        return {};
    }
    return wrap_tc_texture_as_tgfx2(device, tex);
}

static void fill_external_textures_from_render_target(
    RenderTargetContext& ctx,
    tc_render_target_handle rt,
    tgfx::IRenderDevice& device,
    const std::vector<tc_render_target_handle>& render_targets
) {
    const tc_value* params = tc_render_target_get_pipeline_params(rt);
    if (!params || params->type != TC_VALUE_DICT) {
        return;
    }

    for (size_t i = 0; i < params->data.dict.count; i++) {
        const char* slot = params->data.dict.entries[i].key;
        tc_value* value = params->data.dict.entries[i].value;
        if (!slot || slot[0] == '\0' || !value || value->type != TC_VALUE_STRING) {
            continue;
        }

        tc_scene_handle scene = tc_render_target_get_scene(rt);
        tgfx::TextureHandle tex = resolve_pipeline_texture_ref(device, scene, render_targets, value->data.s);
        if (tex) {
            ctx.external_textures[slot] = tex;
        }
    }
}

static bool get_render_camera(
    tc_component* cam_comp,
    double aspect,
    RenderCamera* out,
    uint64_t* layer_mask
) {
    const tc_camera_capability* cap = tc_camera_capability_get(cam_comp);
    if (!cap || !cap->vtable || !cap->vtable->get_camera_data) return false;
    tc_camera_data cd{};
    if (!cap->vtable->get_camera_data(cam_comp, aspect, &cd)) return false;
    *out = render_camera_from_cap(cd);
    if (layer_mask) {
        *layer_mask = cd.layer_mask;
    }
    return true;
}

bool build_render_target_contexts(
    RenderingManager& manager,
    RenderEngine* engine,
    tc_render_target_handle rt,
    const std::string& base_context_name,
    tc_entity_handle internal_entities,
    int render_width,
    int render_height,
    const std::vector<tc_render_target_handle>& managed_render_targets,
    std::unordered_map<int, RenderTargetContextProvider>& providers,
    std::unordered_set<uint64_t>& missing_provider_warnings,
    std::unordered_map<std::string, RenderTargetContext>& contexts,
    std::string& default_context_name
) {
    if (!tc_render_target_handle_valid(rt)) {
        return false;
    }
    if (!tc_render_target_get_enabled(rt)) {
        return false;
    }

    const tc_render_target_kind kind = tc_render_target_get_kind(rt);
    if (kind != TC_RENDER_TARGET_TEXTURE_2D) {
        auto it = providers.find((int)kind);
        if (it == providers.end() || !it->second) {
            const char* rt_name = tc_render_target_get_name(rt);
            const uint64_t warning_key = render_target_key(rt);
            if (missing_provider_warnings.insert(warning_key).second) {
                tc_log(
                    TC_LOG_WARN,
                    "[RenderingManager] render target '%s' kind '%s' has no context provider",
                    rt_name ? rt_name : "(unnamed)",
                    tc_render_target_kind_to_string(kind)
                );
            }
            return false;
        }
        const bool ok = it->second(
            manager,
            rt,
            base_context_name,
            internal_entities,
            contexts,
            default_context_name
        );
        if (ok && default_context_name.empty() && !contexts.empty()) {
            default_context_name = contexts.begin()->first;
        }
        return ok;
    }

    const char* rt_name = tc_render_target_get_name(rt);
    tc_component* camera_comp = tc_render_target_get_camera(rt);
    if (!camera_comp) {
        return false;
    }

    if (render_width <= 0 || render_height <= 0) {
        tc_log(
            TC_LOG_WARN,
            "[RenderingManager] RT '%s': invalid size %dx%d",
            rt_name ? rt_name : "?",
            render_width,
            render_height
        );
        return false;
    }

    double aspect = static_cast<double>(render_width) / std::max(1, render_height);
    RenderCamera render_camera;
    uint64_t camera_layer_mask = 0xFFFFFFFFFFFFFFFFULL;
    if (!get_render_camera(camera_comp, aspect, &render_camera, &camera_layer_mask)) {
        tc_log(
            TC_LOG_WARN,
            "[RenderingManager] render target '%s': no camera capability",
            rt_name ? rt_name : "(null)"
        );
        return false;
    }

    if (engine) engine->ensure_tgfx2();
    tgfx::IRenderDevice* device = engine ? engine->tgfx2_device() : nullptr;
    if (!device) {
        tc_log(TC_LOG_WARN, "[RenderingManager] RT '%s': tgfx2 device unavailable",
               rt_name ? rt_name : "?");
        return false;
    }

    tc_render_target_ensure_textures(rt);
    tgfx::TextureHandle out_color = wrap_tc_texture_as_tgfx2(
        *device, tc_render_target_get_color_texture(rt));
    tgfx::TextureHandle out_depth = wrap_tc_texture_as_tgfx2(
        *device, tc_render_target_get_depth_texture(rt));

    const std::string context_name = base_context_name.empty()
        ? (rt_name ? rt_name : "")
        : base_context_name;

    RenderTargetContext ctx;
    ctx.name = context_name;
    ctx.camera = render_camera;
    ctx.render_rect = {0, 0, render_width, render_height};
    ctx.internal_entities = internal_entities;
    ctx.layer_mask = effective_layer_mask(camera_layer_mask, rt);
    ctx.output_color_tex = out_color;
    ctx.output_depth_tex = out_depth;
    ctx.output_color_format = render_target_format_to_tgfx2(
        tc_render_target_get_color_format(rt));
    ctx.output_depth_format = render_target_format_to_tgfx2(
        tc_render_target_get_depth_format(rt));
    fill_render_target_clear_settings(ctx, rt);
    fill_external_textures_from_render_target(ctx, rt, *device, managed_render_targets);
    contexts[context_name] = std::move(ctx);

    if (default_context_name.empty()) {
        default_context_name = context_name;
    }
    return true;
}

} // namespace termin::rendering_manager_detail
