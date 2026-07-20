// rendering_manager.cpp - Global rendering manager implementation
#include "termin/render/rendering_manager.hpp"
#include "default_pipeline_factory.hpp"
#include "display_presenter.hpp"
#include "render_display_registry.hpp"
#include "render_frame_planner.hpp"
#include "rendering_manager_utils.hpp"
#include "render_state_store.hpp"
#include "render_target_context_builder.hpp"
#include "scene_light_collector.hpp"
#include <termin/entity/entity.hpp>
#include "termin/viewport/tc_viewport_handle.hpp"

extern "C" {
#include <tcbase/tc_log.h>
#include "tc_profiler.h"
#include "core/tc_scene.h"
#include "core/tc_scene_render_mount.h"
#include "core/tc_scene_pool.h"
#include "core/tc_entity_pool.h"
#include "core/tc_entity_pool_registry.h"
#include "tc_viewport_config.h"
#include "render/tc_viewport_pool.h"
#include "render/tc_viewport_input_manager.h"
#include "render/tc_pipeline.h"
#include "render/tc_render_target.h"
#include "render/tc_render_surface.h"
}

#include <algorithm>

namespace termin {

RenderingManager::RenderingManager(RenderTopology& topology)
    : topology_(topology) {
    display_registry_ = std::make_unique<rendering_manager_detail::RenderDisplayRegistry>();
    render_states_ = std::make_unique<rendering_manager_detail::RenderStateStore>();
}

RenderingManager::~RenderingManager() {
    shutdown();
}

// ============================================================================
// Configuration
// ============================================================================

void RenderingManager::set_render_engine(RenderEngine* engine) {
    render_engine_ = engine;
    owned_render_engine_.reset(); // Release owned engine if any
}

RenderEngine* RenderingManager::render_engine() {
    if (!render_engine_) {
        owned_render_engine_ = std::make_unique<RenderEngine>();
        render_engine_ = owned_render_engine_.get();
    }
    return render_engine_;
}

void RenderingManager::set_display_factory(DisplayFactory factory) {
    display_factory_ = std::move(factory);
}

void RenderingManager::set_pipeline_factory(PipelineFactory factory) {
    pipeline_factory_ = std::move(factory);
}

void RenderingManager::set_render_target_context_provider(
    tc_render_target_kind kind,
    RenderTargetContextProvider provider
) {
    if (!provider) {
        clear_render_target_context_provider(kind);
        return;
    }
    render_target_context_providers_[(int)kind] = std::move(provider);
    missing_render_target_provider_warnings_.clear();
}

void RenderingManager::clear_render_target_context_provider(tc_render_target_kind kind) {
    render_target_context_providers_.erase((int)kind);
    missing_render_target_provider_warnings_.clear();
}

tc_pipeline_handle RenderingManager::create_pipeline(const std::string& name) {
    if (name == "(Default)" || name == "Default" || name.empty()) {
        return make_default_pipeline();
    }
    if (pipeline_factory_) {
        return pipeline_factory_(name);
    }
    return TC_PIPELINE_HANDLE_INVALID;
}

size_t RenderingManager::recreate_render_target_pipelines_for_asset(
    const std::string& asset_name,
    const std::string& asset_uuid
) {
    if (asset_name.empty()) {
        tc_log(TC_LOG_WARN, "[RenderingManager] recreate pipeline requested with empty asset name");
        return 0;
    }
    if (!pipeline_factory_) {
        tc_log(TC_LOG_WARN,
            "[RenderingManager] cannot recreate pipeline asset '%s': pipeline factory is not set",
            asset_name.c_str());
        return 0;
    }

    const std::string create_key = asset_uuid.empty() ? asset_name : asset_uuid;
    struct TargetPipeline {
        tc_render_target_handle render_target;
        tc_pipeline_handle old_pipeline;
    };
    std::vector<TargetPipeline> targets;

    // Do not scan the global render-target pool here. RenderTopology owns
    // the render-target lifetime contract;
    // pool scans can accidentally touch stale or foreign editor/game targets.
    for (tc_render_target_handle rt : topology_.managed_render_targets()) {
        if (!tc_render_target_handle_valid(rt)) {
            continue;
        }
        tc_pipeline_handle old_pipeline = tc_render_target_get_pipeline(rt);
        if (!tc_pipeline_pool_alive(old_pipeline)) {
            continue;
        }

        const char* old_name = tc_pipeline_get_name(old_pipeline);
        if (!old_name || *old_name == '\0' || std::string(old_name) != asset_name) {
            continue;
        }

        targets.push_back(TargetPipeline{rt, old_pipeline});
    }

    size_t rebound = 0;
    std::vector<tc_pipeline_handle> old_pipelines;
    old_pipelines.reserve(targets.size());

    for (const TargetPipeline& target : targets) {
        tc_pipeline_handle new_pipeline = create_pipeline(create_key);
        if (!tc_pipeline_pool_alive(new_pipeline)) {
            const char* rt_name = tc_render_target_get_name(target.render_target);
            tc_log(TC_LOG_ERROR,
                "[RenderingManager] failed to recreate pipeline asset '%s' for render target '%s'",
                asset_name.c_str(),
                rt_name ? rt_name : "<unnamed>");
            continue;
        }

        tc_render_target_set_pipeline(target.render_target, new_pipeline);
        tc_scene_handle scene = tc_render_target_get_scene(target.render_target);
        if (tc_scene_handle_valid(scene)) {
            tc_scene_request_render(scene);
        }
        old_pipelines.push_back(target.old_pipeline);
        rebound++;

        const char* rt_name = tc_render_target_get_name(target.render_target);
        tc_log(TC_LOG_INFO,
            "[RenderingManager] rebound render target '%s' to reloaded pipeline '%s'",
            rt_name ? rt_name : "<unnamed>",
            asset_name.c_str());
    }

    for (tc_pipeline_handle old_pipeline : old_pipelines) {
        if (!tc_pipeline_pool_alive(old_pipeline)) {
            continue;
        }
        bool still_used = false;
        for (tc_render_target_handle rt : topology_.managed_render_targets()) {
            if (!tc_render_target_handle_valid(rt)) {
                continue;
            }
            if (tc_pipeline_handle_eq(tc_render_target_get_pipeline(rt), old_pipeline)) {
                still_used = true;
                break;
            }
        }
        if (!still_used) {
            tc_pipeline_destroy(old_pipeline);
        }
    }

    return rebound;
}

tc_pipeline_handle RenderingManager::make_default_pipeline() {
    return rendering_manager_detail::make_default_pipeline();
}

void RenderingManager::set_display_removed_callback(DisplayRemovedCallback callback) {
    display_removed_callback_ = std::move(callback);
}

const std::vector<tc_display*>& RenderingManager::displays() const {
    return display_registry_->displays();
}

const std::vector<tc_display*>& RenderingManager::editor_displays() const {
    return display_registry_->editor_displays();
}

// ============================================================================
// Display Management
// ============================================================================

void RenderingManager::add_display(tc_display* display) {
    display_registry_->add_display(display);
    if (!display) return;
    tc_viewport_handle viewport = tc_display_get_first_viewport(display);
    while (tc_viewport_handle_valid(viewport)) {
        if (tc_scene_handle_valid(tc_viewport_get_scene(viewport))) {
            register_viewport_attachment(display, viewport, true);
        }
        viewport = tc_viewport_get_display_next(viewport);
    }
}

void RenderingManager::remove_display(tc_display* display) {
    display_registry_->remove_display(
        display,
        [this](tc_viewport_handle viewport) {
            unregister_viewport_attachment(viewport);
            remove_viewport_state(viewport);
        },
        display_removed_callback_
    );
}

void RenderingManager::add_editor_display(tc_display* display) {
    display_registry_->add_editor_display(display);
    if (!display) return;
    tc_viewport_handle viewport = tc_display_get_first_viewport(display);
    while (tc_viewport_handle_valid(viewport)) {
        if (tc_scene_handle_valid(tc_viewport_get_scene(viewport))) {
            register_viewport_attachment(display, viewport, false);
        }
        viewport = tc_viewport_get_display_next(viewport);
    }
}

void RenderingManager::remove_editor_display(tc_display* display) {
    display_registry_->remove_editor_display(
        display,
        [this](tc_viewport_handle viewport) {
            unregister_viewport_attachment(viewport);
            remove_viewport_state(viewport);
        }
    );
}

bool RenderingManager::try_auto_remove_display(tc_display* display) {
    return display_registry_->try_auto_remove_display(
        display,
        [this](tc_viewport_handle viewport) {
            unregister_viewport_attachment(viewport);
            remove_viewport_state(viewport);
        },
        display_removed_callback_
    );
}

tc_input_manager* RenderingManager::display_input_endpoint(tc_display* display) {
    return display_registry_->display_input_endpoint(display);
}

tc_display* RenderingManager::get_display_by_name(const std::string& name) const {
    return display_registry_->get_display_by_name(name);
}

tc_display* RenderingManager::get_or_create_display(const std::string& name) {
    return display_registry_->get_or_create_display(name, display_factory_);
}

// ============================================================================
// Scene Mounting
// ============================================================================

tc_viewport_handle RenderingManager::mount_scene(const SceneMountRequest& request) {
    tc_scene_handle scene = request.scene;
    tc_display* display = request.display;
    tc_component* camera = request.camera;

    if (!tc_scene_handle_valid(scene) || !display || !camera) {
        return TC_VIEWPORT_HANDLE_INVALID;
    }

    tc_viewport_handle viewport = tc_viewport_pool_alloc(request.name.c_str());
    if (!tc_viewport_handle_valid(viewport)) {
        tc_log(TC_LOG_ERROR,
               "[RenderingManager] Failed to create viewport '%s'",
               request.name.c_str());
        return TC_VIEWPORT_HANDLE_INVALID;
    }

    tc_render_target_handle rt = tc_render_target_new(request.name.c_str());
    tc_render_target_set_scene(rt, scene);
    tc_render_target_set_camera(rt, camera);
    tc_render_target_set_pipeline(rt, request.pipeline);
    tc_render_target_set_dynamic_resolution(rt, true);
    if (!topology_.register_render_target(rt)) {
        tc_render_target_free(rt);
        tc_viewport_free(viewport);
        return TC_VIEWPORT_HANDLE_INVALID;
    }
    tc_viewport_set_render_target(viewport, rt);
    tc_viewport_set_scene(viewport, scene);

    // Set rect
    const Rect2f& region = request.region;
    tc_viewport_set_rect(viewport, region.x, region.y, region.width, region.height);

    // Add to display
    tc_display_add_viewport(display, viewport);
    if (!topology_.register_viewport(scene, viewport, display)) {
        tc_display_remove_viewport(display, viewport);
        unregister_managed_render_target(rt);
        tc_render_target_free(rt);
        tc_viewport_free(viewport);
        return TC_VIEWPORT_HANDLE_INVALID;
    }

    return viewport;
}

bool RenderingManager::register_viewport_attachment(
    tc_display* display,
    tc_viewport_handle viewport,
    bool destroy_on_scene_detach
) {
    if (!display || !tc_viewport_handle_valid(viewport)) return false;
    tc_scene_handle scene = tc_viewport_get_scene(viewport);
    if (!tc_scene_handle_valid(scene)) {
        tc_log(TC_LOG_ERROR, "[RenderingManager] Cannot attach viewport without an owning scene");
        return false;
    }
    return topology_.register_viewport(
        scene,
        viewport,
        display,
        destroy_on_scene_detach
    );
}

bool RenderingManager::unregister_viewport_attachment(tc_viewport_handle viewport) {
    return topology_.unregister_viewport(viewport);
}

void RenderingManager::unmount_scene(
    tc_scene_handle scene,
    tc_display* display,
    bool include_host_viewports
) {
    if (!display) return;

    // Collect from the canonical topology before mutating it.
    std::vector<tc_viewport_handle> to_remove;
    for (const auto& attachment : topology_.viewport_attachments()) {
        if (attachment.display == display && tc_scene_handle_eq(attachment.scene, scene)
                && (include_host_viewports || attachment.destroy_on_scene_detach)) {
            to_remove.push_back(attachment.viewport);
        }
    }

    // Remove them
    for (tc_viewport_handle viewport : to_remove) {
        tc_render_target_handle rt = tc_viewport_get_render_target(viewport);

        // Remove viewport state
        remove_viewport_state(viewport);
        unregister_viewport_attachment(viewport);

        // Remove from display
        tc_display_remove_viewport(display, viewport);

        // Free viewport
        tc_viewport_free(viewport);

        bool registered_managed = std::find_if(
            topology_.managed_render_targets().begin(),
            topology_.managed_render_targets().end(),
            [rt](tc_render_target_handle candidate) {
                return tc_render_target_handle_eq(candidate, rt);
            }
        ) != topology_.managed_render_targets().end();

        bool still_referenced = false;
        auto scan_display_list = [&still_referenced, rt](const std::vector<tc_display*>& displays) {
            for (tc_display* d : displays) {
                tc_viewport_handle scan = tc_display_get_first_viewport(d);
                while (tc_viewport_handle_valid(scan)) {
                    if (tc_render_target_handle_eq(tc_viewport_get_render_target(scan), rt)) {
                        still_referenced = true;
                        return;
                    }
                    scan = tc_viewport_get_display_next(scan);
                }
            }
        };
        scan_display_list(display_registry_->displays());
        if (!still_referenced) {
            scan_display_list(display_registry_->editor_displays());
        }

        if (tc_render_target_handle_valid(rt) && !registered_managed && !still_referenced) {
            render_states_->remove_render_target_state(rt);
            tc_pipeline_handle pipeline = tc_render_target_get_pipeline(rt);
            if (tc_pipeline_handle_valid(pipeline)) {
                tc_render_target_set_pipeline(rt, TC_PIPELINE_HANDLE_INVALID);
                tc_pipeline_destroy(pipeline);
            }
            tc_render_target_free(rt);
        }
    }
}

std::vector<tc_viewport_handle> RenderingManager::attach_scene_full(tc_scene_handle scene) {
    std::vector<tc_viewport_handle> viewports;

    if (!tc_scene_handle_valid(scene)) {
        tc_log(TC_LOG_ERROR, "[RenderingManager] attach_scene_full: invalid scene handle");
        return viewports;
    }
    if (topology_.is_attached(scene)) {
        tc_log(TC_LOG_ERROR, "[RenderingManager] attach_scene_full: scene is already attached");
        return viewports;
    }

    tc_scene_render_mount* mount = tc_scene_render_mount_get(scene);
    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    tc_entity_pool_handle pool_handle = pool ? tc_entity_pool_registry_find(pool) : TC_ENTITY_POOL_HANDLE_INVALID;

    // 1. Restore managed render targets from render_target_configs
    size_t rt_count = mount ? mount->render_target_config_count : 0;
    for (size_t i = 0; i < rt_count; i++) {
        tc_render_target_config* rtc = &mount->render_target_configs[i];
        std::string rt_name = rtc->name ? rtc->name : "";
        if (rt_name.empty()) continue;

        tc_render_target_handle rt = tc_render_target_new(rt_name.c_str());
        if (!tc_render_target_handle_valid(rt)) {
            tc_log(
                TC_LOG_ERROR,
                "[RenderingManager] Failed to allocate render target '%s'",
                rt_name.c_str()
            );
            detach_scene_full(scene);
            return {};
        }
        tc_render_target_set_scene(rt, scene);
        if (rtc->kind && rtc->kind[0] != '\0') {
            tc_render_target_kind kind;
            if (tc_render_target_kind_from_string(rtc->kind, &kind)) {
                tc_render_target_set_kind(rt, kind);
            } else {
                tc_log(TC_LOG_WARN, "[RenderingManager] unknown render target kind '%s'", rtc->kind);
            }
        }
        tc_render_target_set_dynamic_resolution(rt, rtc->dynamic_resolution);
        if (!rtc->dynamic_resolution) {
            tc_render_target_set_width(rt, rtc->width);
            tc_render_target_set_height(rt, rtc->height);
        }
        if (rtc->color_format && rtc->color_format[0] != '\0') {
            tc_texture_format format;
            if (tc_render_target_format_from_string(rtc->color_format, &format)) {
                tc_render_target_set_color_format(rt, format);
            } else {
                tc_log(TC_LOG_WARN, "[RenderingManager] unknown render target color_format '%s'", rtc->color_format);
            }
        }
        if (rtc->depth_format && rtc->depth_format[0] != '\0') {
            tc_texture_format format;
            if (tc_render_target_format_from_string(rtc->depth_format, &format)) {
                tc_render_target_set_depth_format(rt, format);
            } else {
                tc_log(TC_LOG_WARN, "[RenderingManager] unknown render target depth_format '%s'", rtc->depth_format);
            }
        }
        tc_render_target_set_layer_mask(rt, rtc->layer_mask);
        tc_render_target_set_enabled(rt, rtc->enabled);
        tc_render_target_set_clear_color_enabled(rt, rtc->clear_color);
        tc_render_target_set_clear_color_value(
            rt,
            rtc->clear_color_value[0],
            rtc->clear_color_value[1],
            rtc->clear_color_value[2],
            rtc->clear_color_value[3]);
        tc_render_target_set_clear_depth_enabled(rt, rtc->clear_depth);
        tc_render_target_set_clear_depth_value(rt, rtc->clear_depth_value);

        if (rtc->camera_uuid && rtc->camera_uuid[0] != '\0' && pool) {
            tc_entity_id eid = tc_entity_pool_find_by_uuid(pool, rtc->camera_uuid);
            if (tc_entity_id_valid(eid)) {
                tc_entity_handle eh = tc_entity_handle_make(pool_handle, eid);
                Entity entity(eh);
                tc_component* camera = entity.get_component_by_type_name("CameraComponent");
                if (camera) {
                    tc_render_target_set_camera(rt, camera);
                }
            }
        }
        if (rtc->xr_origin_uuid && rtc->xr_origin_uuid[0] != '\0' && pool) {
            tc_entity_id eid = tc_entity_pool_find_by_uuid(pool, rtc->xr_origin_uuid);
            if (tc_entity_id_valid(eid)) {
                tc_entity_handle eh = tc_entity_handle_make(pool_handle, eid);
                Entity entity(eh);
                tc_component* xr_origin = entity.get_component_by_type_name("XrOriginComponent");
                if (xr_origin) {
                    tc_render_target_set_xr_origin(rt, xr_origin);
                } else {
                    tc_log(
                        TC_LOG_ERROR,
                        "[RenderingManager] render target '%s' xr_origin_uuid '%s' has no XrOriginComponent",
                        rt_name.c_str(),
                        rtc->xr_origin_uuid
                    );
                }
            } else {
                tc_log(
                    TC_LOG_ERROR,
                    "[RenderingManager] render target '%s' xr_origin_uuid '%s' was not found",
                    rt_name.c_str(),
                    rtc->xr_origin_uuid
                );
            }
        }

        tc_pipeline_handle pipeline = TC_PIPELINE_HANDLE_INVALID;
        if (rtc->pipeline_uuid && rtc->pipeline_uuid[0] != '\0' && pipeline_factory_) {
            pipeline = pipeline_factory_(rtc->pipeline_uuid);
        }
        if (!tc_pipeline_handle_valid(pipeline) && rtc->pipeline_name && rtc->pipeline_name[0] != '\0') {
            pipeline = create_pipeline(rtc->pipeline_name);
        }
        if (tc_pipeline_handle_valid(pipeline)) {
            tc_render_target_set_pipeline(rt, pipeline);
        }
        if (rtc->pipeline_params.type == TC_VALUE_DICT
                && tc_value_dict_size(&rtc->pipeline_params) > 0) {
            tc_render_target_set_pipeline_params(rt, &rtc->pipeline_params);
        }

        if (!topology_.register_render_target(rt)) {
            tc_log(
                TC_LOG_ERROR,
                "[RenderingManager] Failed to register render target '%s' in scene topology",
                rt_name.c_str()
            );
            tc_render_target_free(rt);
            detach_scene_full(scene);
            return {};
        }
    }

    // 2. Create viewports from viewport_configs
    size_t vp_count = mount ? mount->viewport_config_count : 0;
    for (size_t i = 0; i < vp_count; i++) {
        tc_viewport_config* config = &mount->viewport_configs[i];

        std::string display_name = config->display_name ? config->display_name : "Main";
        tc_display* display = get_or_create_display(display_name);
        if (!display) {
            tc_log(TC_LOG_ERROR, "[RenderingManager] Cannot create display '%s'", display_name.c_str());
            detach_scene_full(scene);
            return {};
        }

        std::string vp_name = config->name ? config->name : "";
        tc_viewport_handle viewport = tc_viewport_pool_alloc(vp_name.c_str());
        if (!tc_viewport_handle_valid(viewport)) {
            tc_log(
                TC_LOG_ERROR,
                "[RenderingManager] Failed to allocate viewport '%s'",
                vp_name.c_str()
            );
            detach_scene_full(scene);
            return {};
        }

        tc_viewport_set_rect(viewport, config->region[0], config->region[1], config->region[2], config->region[3]);
        tc_viewport_set_depth(viewport, config->depth);
        tc_viewport_set_enabled(viewport, config->enabled);
        if (config->input_mode) {
            tc_viewport_set_input_mode(viewport, config->input_mode);
        }
        tc_viewport_set_block_input_in_editor(viewport, config->block_input_in_editor);

        tc_viewport_set_scene(viewport, scene);

        tc_render_target_handle rt = TC_RENDER_TARGET_HANDLE_INVALID;
        std::string rt_name = config->render_target_name ? config->render_target_name : "";
        if (!rt_name.empty()) {
            rt = topology_.find_render_target(scene, rt_name);
        }

        if (tc_render_target_handle_valid(rt)) {
            tc_viewport_set_render_target(viewport, rt);
        } else if (!rt_name.empty()) {
            tc_log(TC_LOG_WARN,
                   "[RenderingManager] viewport '%s' references missing render target '%s'",
                   vp_name.c_str(),
                   rt_name.c_str());
        }

        tc_display_add_viewport(display, viewport);
        if (!topology_.register_viewport(scene, viewport, display)) {
            tc_display_remove_viewport(display, viewport);
            tc_viewport_free(viewport);
            tc_log(TC_LOG_ERROR, "[RenderingManager] Failed to register viewport in scene topology");
            detach_scene_full(scene);
            return {};
        }
        viewports.push_back(viewport);
    }

    // Apply scene pipelines (compile templates, mark managed viewports)
    if (!apply_scene_pipelines(scene, viewports)) {
        tc_log(TC_LOG_ERROR, "[RenderingManager] Scene attach rolled back after topology failure");
        detach_scene_full(scene);
        return {};
    }

    return viewports;
}

void RenderingManager::detach_scene_full(tc_scene_handle scene, bool include_host_viewports) {
    // Lifecycle observers must see the complete live attachment. RenderTopology
    // notifies them before dropping pipelines; viewports and targets follow.
    if (topology_.is_attached(scene)) {
        detach_scene(scene);
    }

    // Unmount every scene viewport (including editor displays) through the
    // canonical topology exactly once.
    std::vector<tc_display*> scene_displays;
    for (const auto& attachment : topology_.viewport_attachments()) {
        if (!tc_scene_handle_eq(attachment.scene, scene)) continue;
        if (!include_host_viewports && !attachment.destroy_on_scene_detach) continue;
        if (std::find(scene_displays.begin(), scene_displays.end(), attachment.display)
                == scene_displays.end()) {
            scene_displays.push_back(attachment.display);
        }
    }
    for (tc_display* display : scene_displays) {
        unmount_scene(scene, display, include_host_viewports);
    }

    // Free managed render targets belonging to this scene.
    // Iterate the managed list — never scan the global pool.
    std::vector<tc_render_target_handle> to_free;
    for (tc_render_target_handle rt : topology_.managed_render_targets()) {
        if (!tc_render_target_handle_valid(rt)) continue;
        tc_scene_handle rt_scene = tc_render_target_get_scene(rt);
        if (tc_scene_handle_eq(rt_scene, scene)) {
            to_free.push_back(rt);
        }
    }
    for (tc_render_target_handle rt : to_free) {
        unregister_managed_render_target(rt);
        render_states_->remove_render_target_state(rt);
        tc_pipeline_handle pipeline = tc_render_target_get_pipeline(rt);
        if (tc_pipeline_handle_valid(pipeline)) {
            tc_render_target_set_pipeline(rt, TC_PIPELINE_HANDLE_INVALID);
            tc_pipeline_destroy(pipeline);
        }
        tc_render_target_free(rt);
    }

}

bool RenderingManager::apply_scene_pipelines(
    tc_scene_handle scene,
    const std::vector<tc_viewport_handle>& viewports
) {
    // Build viewport lookup by name
    std::unordered_map<std::string, tc_viewport_handle> viewport_by_name;
    for (tc_viewport_handle vp : viewports) {
        const char* name = tc_viewport_get_name(vp);
        if (name && name[0] != '\0') {
            viewport_by_name[name] = vp;
        }
    }
    for (tc_viewport_handle vp : topology_.viewports(scene)) {
        const char* name = tc_viewport_get_name(vp);
        if (name && name[0] != '\0' && viewport_by_name.find(name) == viewport_by_name.end()) {
            viewport_by_name[name] = vp;
        }
    }

    struct PipelineViewportAssignment {
        tc_viewport_handle viewport;
        std::string pipeline_name;
    };
    std::vector<PipelineViewportAssignment> assignments;

    // Validate every pipeline target before installing live topology or
    // emitting lifecycle callbacks.
    tc_scene_render_mount* mount = tc_scene_render_mount_get(scene);
    size_t pipeline_count = mount ? mount->pipeline_count : 0;
    for (size_t i = 0; i < pipeline_count; i++) {
        const tc_render_pipeline* resource = tc_render_pipeline_get(mount->pipelines[i]);
        if (!resource) {
            tc_log(TC_LOG_ERROR, "[RenderingManager] Scene contains a stale pipeline handle");
            return false;
        }

        std::string pipeline_name = resource->header.name;
        std::vector<std::string> targets;
        for (uint32_t target_index = 0; target_index < resource->target_count; ++target_index) {
            const char* viewport_name = resource->targets[target_index].viewport_name;
            if (!viewport_name || !viewport_name[0]) continue;
            if (std::find(targets.begin(), targets.end(), viewport_name) == targets.end()) {
                targets.emplace_back(viewport_name);
            }
        }

        for (const std::string& vp_name : targets) {
            auto it = viewport_by_name.find(vp_name);
            if (it == viewport_by_name.end()) {
                tc_log(TC_LOG_ERROR, "[RenderingManager] Scene pipeline '%s' targets viewport '%s' but not found",
                       pipeline_name.c_str(), vp_name.c_str());
                return false;
            }
            assignments.push_back(PipelineViewportAssignment{it->second, pipeline_name});
        }
    }

    if (!topology_.attach_scene(scene)) {
        return false;
    }
    for (const PipelineViewportAssignment& assignment : assignments) {
        tc_viewport_set_managed_by(
            assignment.viewport,
            assignment.pipeline_name.c_str()
        );
    }
    return true;
}

// ============================================================================
// Viewport State Management
// ============================================================================

ViewportRenderState* RenderingManager::get_viewport_state(tc_viewport_handle viewport) {
    return render_states_->get_viewport_state(viewport);
}

ViewportRenderState* RenderingManager::get_or_create_viewport_state(tc_viewport_handle viewport) {
    return render_states_->get_or_create_viewport_state(viewport);
}

void RenderingManager::remove_viewport_state(tc_viewport_handle viewport) {
    render_states_->remove_viewport_state(viewport);
}

// ============================================================================
// Render Target State
// ============================================================================

ViewportRenderState* RenderingManager::get_render_target_state(tc_render_target_handle rt) {
    return render_states_->get_render_target_state(rt);
}

ViewportRenderState* RenderingManager::get_or_create_render_target_state(tc_render_target_handle rt) {
    return render_states_->get_or_create_render_target_state(rt);
}

// ============================================================================
// Managed Render Target Management
// ============================================================================

void RenderingManager::register_managed_render_target(tc_render_target_handle rt) {
    topology_.register_render_target(rt);
}

void RenderingManager::unregister_managed_render_target(tc_render_target_handle rt) {
    topology_.unregister_render_target(rt);
}

// ============================================================================
// Rendering - Offscreen-First Model
// ============================================================================

void RenderingManager::render_all(bool present) {
    bool profile = tc_profiler_enabled();
    if (profile) tc_profiler_begin_section("RenderAll Offscreen");
    render_all_offscreen();
    if (profile) tc_profiler_end_section();
    if (present) {
        if (profile) tc_profiler_begin_section("RenderAll Present");
        present_all();
        if (profile) tc_profiler_end_section();
    }
}

void RenderingManager::render_all_offscreen() {
    RenderEngine* engine = render_engine();
    if (!engine) {
        tc_log(TC_LOG_WARN, "[RenderingManager] render_all_offscreen: no render engine");
        return;
    }

    rendering_manager_detail::update_viewport_rects(topology_.viewport_attachments());

    // 0. Sync dynamic-resolution render targets from their attached viewport.
    sync_viewport_resolutions();

    rendering_manager_detail::OffscreenRenderPlan render_plan =
        rendering_manager_detail::build_offscreen_render_plan(topology_.viewport_attachments());

    // 1. Render standalone managed render targets first. RTs attached to
    // viewports are intentionally delayed because we do not yet have a
    // dependency graph between render targets.
    for (tc_render_target_handle rt : topology_.managed_render_targets()) {
        if (tc_render_target_handle_valid(rt)
                && !rendering_manager_detail::contains_render_target(
                    render_plan.attached_viewport_render_targets, rt)) {
            render_render_target_offscreen(rt);
        }
    }

    // 2. Execute scene pipelines (can span multiple displays). These render
    // their viewport-bound render targets as a batch.
    for (tc_scene_handle scene : topology_.attached_scenes()) {
        if (!tc_scene_alive(scene)) continue;

        std::vector<std::string> pipeline_names = get_pipeline_names(scene);
        for (const std::string& pipeline_name : pipeline_names) {
            tc_pipeline_handle pipeline = get_scene_pipeline(scene, pipeline_name);
            if (tc_pipeline_handle_valid(pipeline)) {
                render_scene_pipeline_offscreen(scene, pipeline_name, pipeline);
            }
        }
    }

    // 3. Render viewport-bound render targets not owned by a scene pipeline.
    // Dedupe by RenderTarget: multiple viewports may display the same target,
    // but rendering it twice in one frame would race the same output textures.
    std::vector<tc_render_target_handle> rendered_viewport_targets =
        render_plan.scene_pipeline_render_targets;
    for (tc_viewport_handle vp : render_plan.viewport_render_target_viewports) {
        tc_render_target_handle rt = tc_viewport_get_render_target(vp);
        if (!tc_render_target_handle_valid(rt)) continue;
        if (rendering_manager_detail::contains_render_target(rendered_viewport_targets, rt)) continue;
        render_viewport_offscreen(vp);
        rendering_manager_detail::append_unique_render_target(rendered_viewport_targets, rt);
    }
}

void RenderingManager::render_display(tc_display* display) {
    if (!display) return;
    if (!tc_display_get_enabled(display)) return;

    tc_render_surface* surface = tc_display_get_surface(display);
    if (!surface) {
        tc_log(TC_LOG_WARN, "[RenderingManager] render_display: surface is null");
        return;
    }

    int width = 0;
    int height = 0;
    tc_render_surface_get_size(surface, &width, &height);
    if (width <= 0 || height <= 0) {
        return;
    }

    RenderEngine* engine = render_engine();
    if (!engine) {
        tc_log(TC_LOG_WARN, "[RenderingManager] render_display: no render engine");
        return;
    }

    rendering_manager_detail::update_viewport_rects(topology_.viewport_attachments(), display);
    rendering_manager_detail::sync_viewport_render_target_resolutions(
        topology_.viewport_attachments(),
        display
    );

    rendering_manager_detail::OffscreenRenderPlan render_plan =
        rendering_manager_detail::build_offscreen_render_plan(
            topology_.viewport_attachments(),
            display
        );

    for (tc_scene_handle scene : topology_.attached_scenes()) {
        if (!tc_scene_alive(scene)) continue;

        std::vector<std::string> pipeline_names = get_pipeline_names(scene);
        for (const std::string& pipeline_name : pipeline_names) {
            tc_pipeline_handle pipeline = get_scene_pipeline(scene, pipeline_name);
            if (tc_pipeline_handle_valid(pipeline)) {
                render_scene_pipeline_offscreen(scene, pipeline_name, pipeline, display);
            }
        }
    }

    std::vector<tc_render_target_handle> rendered_viewport_targets =
        render_plan.scene_pipeline_render_targets;
    for (tc_viewport_handle vp : render_plan.viewport_render_target_viewports) {
        tc_render_target_handle rt = tc_viewport_get_render_target(vp);
        if (!tc_render_target_handle_valid(rt)) continue;
        if (rendering_manager_detail::contains_render_target(rendered_viewport_targets, rt)) continue;
        render_viewport_offscreen(vp);
        rendering_manager_detail::append_unique_render_target(rendered_viewport_targets, rt);
    }

    present_display(display);
}

void RenderingManager::render_scene_pipeline_offscreen(
    tc_scene_handle scene,
    const std::string& pipeline_name,
    tc_pipeline_handle pipeline,
    tc_display* only_display
) {
    if (!tc_scene_handle_valid(scene) || !tc_pipeline_handle_valid(pipeline)) {
        return;
    }

    const std::vector<std::string>& target_names =
        topology_.get_pipeline_targets(scene, pipeline_name);
    if (target_names.empty()) {
        return;
    }

    // Collect render target contexts.
    std::unordered_map<std::string, RenderTargetContext> contexts;
    std::string first_viewport_name;

    for (const std::string& vp_name : target_names) {
        tc_viewport_handle viewport = topology_.find_viewport(scene, vp_name);
        if (!tc_viewport_handle_valid(viewport)) {
            tc_log(TC_LOG_ERROR, "[RenderingManager] Scene pipeline '%s' target viewport '%s' NOT FOUND",
                   pipeline_name.c_str(), vp_name.c_str());
            continue;
        }
        tc_display* viewport_display = topology_.display_for_viewport(viewport);
        if (only_display && viewport_display != only_display) {
            continue;
        }
        if (viewport_display && !tc_display_get_enabled(viewport_display)) {
            continue;
        }

        if (!tc_viewport_get_enabled(viewport)) {
            tc_log(TC_LOG_WARN, "[RenderingManager] Viewport '%s' is disabled, skipping", vp_name.c_str());
            continue;
        }

        tc_render_target_handle rt = tc_viewport_get_render_target(viewport);
        if (!tc_render_target_handle_valid(rt)) {
            tc_log(TC_LOG_WARN, "[RenderingManager] Viewport '%s' has no render target", vp_name.c_str());
            continue;
        }
        if (!tc_render_target_get_enabled(rt)) {
            continue;
        }

        // Get pixel rect
        int px, py, pw, ph;
        tc_viewport_get_pixel_rect(viewport, &px, &py, &pw, &ph);
        if (pw <= 0 || ph <= 0) {
            tc_log(TC_LOG_WARN, "[RenderingManager] Viewport '%s' has invalid pixel_rect: %dx%d",
                   vp_name.c_str(), pw, ph);
            continue;
        }

        int rw = pw;
        int rh = ph;
        rendering_manager_detail::resolve_render_target_size_for_viewport(rt, pw, ph, rw, rh);

        std::string default_context;
        if (build_render_target_contexts(
                rt,
                vp_name,
                tc_viewport_get_internal_entities(viewport),
                rw,
                rh,
                contexts,
                default_context)) {
            if (first_viewport_name.empty()) {
                first_viewport_name = default_context.empty() ? vp_name : default_context;
            }
        }
    }

    if (contexts.empty()) {
        return;
    }

    // Collect lights
    std::vector<Light> lights = collect_lights(scene);

    // Execute pipeline for all contexts
    RenderEngine* engine = render_engine();
    RenderPipeline pipeline_wrapper(pipeline);
    engine->render_scene_pipeline_offscreen(
        pipeline_wrapper,
        scene,
        contexts,
        lights,
        first_viewport_name
    );
}

bool RenderingManager::build_render_target_contexts(
    tc_render_target_handle rt,
    const std::string& base_context_name,
    tc_entity_handle internal_entities,
    int render_width,
    int render_height,
    std::unordered_map<std::string, RenderTargetContext>& contexts,
    std::string& default_context_name
) {
    rendering_manager_detail::RenderTargetContextBuildRequest request{
        *this,
        render_engine(),
        rt,
        base_context_name,
        internal_entities,
        render_width,
        render_height,
        topology_.managed_render_targets(),
        render_target_context_providers_,
        missing_render_target_provider_warnings_,
        contexts,
        default_context_name
    };
    return rendering_manager_detail::build_render_target_contexts(request);
}

void RenderingManager::render_viewport_offscreen(tc_viewport_handle viewport) {
    const char* vp_name = tc_viewport_get_name(viewport);

    if (!tc_viewport_handle_valid(viewport)) {
        tc_log(TC_LOG_WARN, "[RenderingManager] render_viewport_offscreen('%s'): invalid viewport",
               vp_name ? vp_name : "(null)");
        return;
    }

    tc_render_target_handle rt = tc_viewport_get_render_target(viewport);
    if (!tc_render_target_handle_valid(rt)) {
        return;
    }
    if (!tc_render_target_get_enabled(rt)) {
        return;
    }

    tc_scene_handle scene = tc_viewport_get_scene(viewport);
    tc_pipeline_handle pipeline = tc_render_target_get_pipeline(rt);

    if (!tc_scene_handle_valid(scene)) {
        return;
    }
    if (!tc_pipeline_handle_valid(pipeline)) {
        return;
    }

    // Wrap pipeline handle
    RenderPipeline render_pipeline(pipeline);

    // Get pixel rect
    int px, py, pw, ph;
    tc_viewport_get_pixel_rect(viewport, &px, &py, &pw, &ph);
    if (pw <= 0 || ph <= 0) return;

    int rw = pw;
    int rh = ph;
    rendering_manager_detail::resolve_render_target_size_for_viewport(rt, pw, ph, rw, rh);

    // Collect lights
    std::vector<Light> lights = collect_lights(scene);

    // Build one or more render target contexts and run scene pipeline.
    tc_entity_handle internal_entities = tc_viewport_get_internal_entities(viewport);
    std::unordered_map<std::string, RenderTargetContext> contexts;
    std::string default_context;
    if (!build_render_target_contexts(
            rt,
            vp_name ? vp_name : "",
            internal_entities,
            rw,
            rh,
            contexts,
            default_context)) {
        return;
    }

    RenderEngine* engine = render_engine();
    engine->render_scene_pipeline_offscreen(
        render_pipeline, scene, contexts, lights, default_context
    );
}

void RenderingManager::sync_viewport_resolutions() {
    rendering_manager_detail::sync_viewport_render_target_resolutions(
        topology_.viewport_attachments()
    );
}

void RenderingManager::render_render_target_offscreen(tc_render_target_handle rt) {
    if (!tc_render_target_handle_valid(rt)) return;
    if (!tc_render_target_get_enabled(rt)) return;

    const char* rt_name = tc_render_target_get_name(rt);

    tc_scene_handle scene = tc_render_target_get_scene(rt);
    tc_pipeline_handle pipeline = tc_render_target_get_pipeline(rt);

    if (!tc_scene_handle_valid(scene)) {
        tc_log(TC_LOG_WARN, "[RenderingManager] RT '%s': no scene", rt_name ? rt_name : "?");
        return;
    }
    if (!tc_pipeline_handle_valid(pipeline)) {
        return;
    }

    int w = tc_render_target_get_width(rt);
    int h = tc_render_target_get_height(rt);
    if (tc_render_target_get_kind(rt) == TC_RENDER_TARGET_TEXTURE_2D && (w <= 0 || h <= 0)) {
        tc_log(TC_LOG_WARN, "[RenderingManager] RT '%s': invalid size %dx%d", rt_name ? rt_name : "?", w, h);
        return;
    }

    RenderPipeline render_pipeline(pipeline);

    std::vector<Light> lights = collect_lights(scene);

    std::string name = rt_name ? rt_name : "";
    std::unordered_map<std::string, RenderTargetContext> contexts;
    std::string default_context;
    if (!build_render_target_contexts(
            rt,
            name,
            TC_ENTITY_HANDLE_INVALID,
            w,
            h,
            contexts,
            default_context)) {
        return;
    }

    RenderEngine* engine = render_engine();
    engine->render_scene_pipeline_offscreen(
        render_pipeline, scene, contexts, lights, default_context
    );
}

void RenderingManager::present_all() {
    for (tc_display* display : display_registry_->displays()) {
        if (tc_display_get_enabled(display)) {
            present_display(display);
        }
    }
    for (tc_display* display : display_registry_->editor_displays()) {
        if (tc_display_get_enabled(display)) {
            present_display(display);
        }
    }
}

void RenderingManager::present_display(tc_display* display) {
    rendering_manager_detail::present_display(*this, display);
}

// ============================================================================
// Scene Pipeline Management
// ============================================================================

void RenderingManager::attach_scene(tc_scene_handle scene) {
    if (!topology_.attach_scene(scene)) {
        tc_log(TC_LOG_ERROR, "[RenderingManager] Failed to attach scene pipeline topology");
    }
}

void RenderingManager::detach_scene(tc_scene_handle scene) {
    if (!tc_scene_handle_valid(scene)) return;
    topology_.detach_scene(scene);
}

tc_pipeline_handle RenderingManager::get_scene_pipeline(tc_scene_handle scene, const std::string& name) const {
    return topology_.get_pipeline(scene, name);
}

tc_pipeline_handle RenderingManager::get_scene_pipeline(const std::string& name) const {
    for (tc_scene_handle scene : topology_.attached_scenes()) {
        tc_pipeline_handle pipeline = topology_.get_pipeline(scene, name);
        if (tc_pipeline_handle_valid(pipeline)) return pipeline;
    }
    tc_log(TC_LOG_WARN, "[RenderingManager] get_scene_pipeline NOT FOUND: '%s'", name.c_str());
    return TC_PIPELINE_HANDLE_INVALID;
}

void RenderingManager::set_pipeline_targets(const std::string& pipeline_name, const std::vector<std::string>& targets) {
    tc_log(TC_LOG_ERROR,
           "[RenderingManager] set_pipeline_targets('%s') requires a scene-qualified API",
           pipeline_name.c_str());
    (void)targets;
}

const std::vector<std::string>& RenderingManager::get_pipeline_targets(const std::string& pipeline_name) const {
    tc_log(TC_LOG_ERROR,
           "[RenderingManager] get_pipeline_targets('%s') requires a scene-qualified API",
           pipeline_name.c_str());
    static const std::vector<std::string> empty;
    return empty;
}

std::vector<std::string> RenderingManager::get_pipeline_names(tc_scene_handle scene) const {
    return topology_.get_pipeline_names(scene);
}

void RenderingManager::clear_scene_pipelines(tc_scene_handle scene) {
    topology_.clear_scene_pipelines(scene);
}

void RenderingManager::clear_all_scene_pipelines() {
    topology_.clear_all();
}

// ============================================================================
// Shutdown
// ============================================================================

void RenderingManager::shutdown() {
    if (render_states_) {
        render_states_->clear_all();
    }

    // Clear engine-owned topology after hosts have detached live targets.
    clear_all_scene_pipelines();

    if (display_registry_) {
        display_registry_->clear();
    }

    // Clear callbacks
    display_factory_ = nullptr;
    pipeline_factory_ = nullptr;
    display_removed_callback_ = nullptr;

    // Release owned render engine
    owned_render_engine_.reset();
    render_engine_ = nullptr;
}

// ============================================================================
// Helpers
// ============================================================================

std::vector<Light> RenderingManager::collect_lights(tc_scene_handle scene) {
    return rendering_manager_detail::collect_lights(scene);
}

} // namespace termin
