#include "termin/render/render_topology.hpp"

#include "termin/render/render_attachment_context.hpp"
#include "termin/render/render_pipeline.hpp"
#include "termin/render/scene_pipeline_template.hpp"

#include <algorithm>
#include <cstdint>

extern "C" {
#include <tcbase/tc_log.h>
#include "core/tc_scene_render_mount.h"
}

namespace termin {

namespace {

const std::vector<std::string> empty_pipeline_targets;
const std::vector<tc_render_target_handle> empty_render_targets;
const std::vector<tc_viewport_handle> empty_viewports;

bool same_scene(tc_scene_handle left, tc_scene_handle right) {
    return tc_scene_handle_eq(left, right);
}

bool same_render_target(tc_render_target_handle left, tc_render_target_handle right) {
    return tc_render_target_handle_eq(left, right);
}

bool same_viewport(tc_viewport_handle left, tc_viewport_handle right) {
    return tc_viewport_handle_eq(left, right);
}

void destroy_pipeline_map(std::unordered_map<std::string, tc_pipeline_handle>& pipelines) {
    for (const auto& [name, pipeline] : pipelines) {
        (void)name;
        if (tc_pipeline_handle_valid(pipeline)) {
            tc_pipeline_destroy(pipeline);
        }
    }
    pipelines.clear();
}

} // namespace

RenderTopology::~RenderTopology() {
    clear_all();
}

uint64_t RenderTopology::scene_key(tc_scene_handle scene) {
    return (static_cast<uint64_t>(scene.index) << 32) | scene.generation;
}

RenderTopology::SceneRecord* RenderTopology::find_record(tc_scene_handle scene) {
    auto it = scenes_.find(scene_key(scene));
    return it == scenes_.end() ? nullptr : &it->second;
}

const RenderTopology::SceneRecord* RenderTopology::find_record(tc_scene_handle scene) const {
    auto it = scenes_.find(scene_key(scene));
    return it == scenes_.end() ? nullptr : &it->second;
}

RenderTopology::SceneRecord& RenderTopology::ensure_record(tc_scene_handle scene) {
    SceneRecord& record = scenes_[scene_key(scene)];
    record.scene = scene;
    return record;
}

bool RenderTopology::attach_scene(tc_scene_handle scene) {
    if (!tc_scene_handle_valid(scene)) {
        tc_log(TC_LOG_ERROR, "[RenderTopology] Cannot attach invalid scene");
        return false;
    }

    std::unordered_map<std::string, tc_pipeline_handle> candidate_pipelines;
    std::unordered_map<std::string, std::vector<std::string>> candidate_targets;
    tc_scene_render_mount* mount = tc_scene_render_mount_get(scene);
    const size_t template_count = mount ? mount->pipeline_template_count : 0;

    for (size_t i = 0; i < template_count; ++i) {
        const tc_spt_handle handle = mount->pipeline_templates[i];
        if (!tc_spt_is_valid(handle)) {
            tc_log(TC_LOG_ERROR, "[RenderTopology] Scene pipeline template %zu is invalid", i);
            destroy_pipeline_map(candidate_pipelines);
            return false;
        }

        TcScenePipelineTemplate pipeline_template(handle);
        if (!pipeline_template.is_loaded()) {
            tc_log(
                TC_LOG_ERROR,
                "[RenderTopology] Scene pipeline template '%s' is not loaded",
                pipeline_template.name().c_str()
            );
            destroy_pipeline_map(candidate_pipelines);
            return false;
        }

        RenderPipeline* compiled = pipeline_template.compile();
        if (!compiled) {
            tc_log(
                TC_LOG_ERROR,
                "[RenderTopology] Failed to compile scene pipeline template '%s'",
                pipeline_template.name().c_str()
            );
            destroy_pipeline_map(candidate_pipelines);
            return false;
        }

        const std::string name = pipeline_template.name();
        tc_pipeline_handle pipeline = compiled->handle();
        tc_pipeline_set_name(pipeline, name.c_str());
        delete compiled;

        auto previous = candidate_pipelines.find(name);
        if (previous != candidate_pipelines.end()) {
            tc_log(
                TC_LOG_ERROR,
                "[RenderTopology] Duplicate scene pipeline name '%s'",
                name.c_str()
            );
            tc_pipeline_destroy(pipeline);
            destroy_pipeline_map(candidate_pipelines);
            return false;
        }
        candidate_pipelines.emplace(name, pipeline);
        candidate_targets.emplace(name, pipeline_template.target_viewports());
    }

    SceneRecord& record = ensure_record(scene);
    destroy_pipelines(record);
    record.pipelines = std::move(candidate_pipelines);
    record.pipeline_targets = std::move(candidate_targets);
    if (!record.attached) {
        record.attached = true;
        attached_scenes_.push_back(scene);
    }
    RenderAttachmentContext context(*this, scene);
    tc_scene_notify_render_attach(
        scene,
        reinterpret_cast<const tc_render_attachment_context*>(&context)
    );
    context.invalidate();
    return true;
}

void RenderTopology::detach_scene(tc_scene_handle scene) {
    if (!tc_scene_handle_valid(scene)) {
        tc_log(TC_LOG_ERROR, "[RenderTopology] Cannot detach invalid scene");
        return;
    }
    SceneRecord* record = find_record(scene);
    if (record == nullptr || !record->attached) {
        tc_log(TC_LOG_ERROR, "[RenderTopology] Scene is not attached during detach");
        return;
    }

    RenderAttachmentContext context(*this, scene);
    tc_scene_notify_render_detach(
        scene,
        reinterpret_cast<const tc_render_attachment_context*>(&context)
    );
    context.invalidate();
    destroy_pipelines(*record);
    record->attached = false;
    attached_scenes_.erase(
        std::remove_if(
            attached_scenes_.begin(),
            attached_scenes_.end(),
            [scene](tc_scene_handle candidate) { return same_scene(candidate, scene); }
        ),
        attached_scenes_.end()
    );
    erase_record_if_empty(scene_key(scene));
}

bool RenderTopology::is_attached(tc_scene_handle scene) const {
    const SceneRecord* record = find_record(scene);
    return record != nullptr && record->attached;
}

tc_pipeline_handle RenderTopology::get_pipeline(
    tc_scene_handle scene,
    const std::string& name
) const {
    const SceneRecord* record = find_record(scene);
    if (record == nullptr) return TC_PIPELINE_HANDLE_INVALID;
    auto it = record->pipelines.find(name);
    return it == record->pipelines.end() ? TC_PIPELINE_HANDLE_INVALID : it->second;
}

std::vector<std::string> RenderTopology::get_pipeline_names(tc_scene_handle scene) const {
    std::vector<std::string> names;
    const SceneRecord* record = find_record(scene);
    if (record == nullptr) return names;
    names.reserve(record->pipelines.size());
    for (const auto& [name, pipeline] : record->pipelines) {
        (void)pipeline;
        names.push_back(name);
    }
    return names;
}

void RenderTopology::set_pipeline_targets(
    tc_scene_handle scene,
    const std::string& pipeline_name,
    const std::vector<std::string>& targets
) {
    if (!tc_scene_handle_valid(scene)) {
        tc_log(
            TC_LOG_ERROR,
            "[RenderTopology] Cannot set targets for invalid scene pipeline '%s'",
            pipeline_name.c_str()
        );
        return;
    }
    ensure_record(scene).pipeline_targets[pipeline_name] = targets;
}

const std::vector<std::string>& RenderTopology::get_pipeline_targets(
    tc_scene_handle scene,
    const std::string& pipeline_name
) const {
    const SceneRecord* record = find_record(scene);
    if (record == nullptr) return empty_pipeline_targets;
    auto it = record->pipeline_targets.find(pipeline_name);
    return it == record->pipeline_targets.end() ? empty_pipeline_targets : it->second;
}

bool RenderTopology::register_render_target(tc_render_target_handle render_target) {
    if (!tc_render_target_handle_valid(render_target)) {
        tc_log(TC_LOG_ERROR, "[RenderTopology] Cannot register invalid render target");
        return false;
    }
    tc_scene_handle scene = tc_render_target_get_scene(render_target);
    if (!tc_scene_handle_valid(scene)) {
        const char* target_name = tc_render_target_get_name(render_target);
        tc_log(
            TC_LOG_ERROR,
            "[RenderTopology] Render target '%s' has no valid owning scene",
            target_name ? target_name : "<unnamed>"
        );
        return false;
    }
    auto existing = std::find_if(
        managed_render_targets_.begin(),
        managed_render_targets_.end(),
        [render_target](tc_render_target_handle candidate) {
            return same_render_target(candidate, render_target);
        }
    );
    if (existing != managed_render_targets_.end()) return true;

    const char* target_name = tc_render_target_get_name(render_target);
    if (target_name != nullptr && target_name[0] != '\0') {
        tc_render_target_handle named_target = find_render_target(scene, target_name);
        if (tc_render_target_handle_valid(named_target)) {
            tc_log(
                TC_LOG_ERROR,
                "[RenderTopology] Scene already owns render target named '%s'",
                target_name
            );
            return false;
        }
    }

    managed_render_targets_.push_back(render_target);
    ensure_record(scene).render_targets.push_back(render_target);
    return true;
}

bool RenderTopology::unregister_render_target(tc_render_target_handle render_target) {
    auto existing = std::find_if(
        managed_render_targets_.begin(),
        managed_render_targets_.end(),
        [render_target](tc_render_target_handle candidate) {
            return same_render_target(candidate, render_target);
        }
    );
    if (existing == managed_render_targets_.end()) return false;

    managed_render_targets_.erase(existing);
    for (auto it = scenes_.begin(); it != scenes_.end(); ++it) {
        auto& targets = it->second.render_targets;
        auto target = std::find_if(
            targets.begin(),
            targets.end(),
            [render_target](tc_render_target_handle candidate) {
                return same_render_target(candidate, render_target);
            }
        );
        if (target == targets.end()) continue;
        targets.erase(target);
        const uint64_t key = it->first;
        erase_record_if_empty(key);
        return true;
    }
    tc_log(TC_LOG_ERROR, "[RenderTopology] Managed target is missing its scene index");
    return true;
}

tc_render_target_handle RenderTopology::find_render_target(
    tc_scene_handle scene,
    const std::string& name
) const {
    const SceneRecord* record = find_record(scene);
    if (record == nullptr) return TC_RENDER_TARGET_HANDLE_INVALID;
    for (tc_render_target_handle target : record->render_targets) {
        if (!tc_render_target_handle_valid(target)) continue;
        const char* target_name = tc_render_target_get_name(target);
        if (target_name != nullptr && name == target_name) return target;
    }
    return TC_RENDER_TARGET_HANDLE_INVALID;
}

const std::vector<tc_render_target_handle>& RenderTopology::render_targets(
    tc_scene_handle scene
) const {
    const SceneRecord* record = find_record(scene);
    return record == nullptr ? empty_render_targets : record->render_targets;
}

bool RenderTopology::register_viewport(
    tc_scene_handle scene,
    tc_viewport_handle viewport,
    tc_display* display,
    bool destroy_on_scene_detach
) {
    if (!tc_scene_handle_valid(scene) || !tc_viewport_handle_valid(viewport) || !display) {
        tc_log(TC_LOG_ERROR, "[RenderTopology] Cannot register incomplete viewport attachment");
        return false;
    }
    if (!same_scene(tc_viewport_get_scene(viewport), scene)) {
        tc_log(TC_LOG_ERROR, "[RenderTopology] Viewport scene does not match attachment scene");
        return false;
    }
    auto existing = std::find_if(
        viewport_attachments_.begin(),
        viewport_attachments_.end(),
        [viewport](const ViewportAttachment& attachment) {
            return same_viewport(attachment.viewport, viewport);
        }
    );
    if (existing != viewport_attachments_.end()) {
        if (!same_scene(existing->scene, scene) || existing->display != display
                || existing->destroy_on_scene_detach != destroy_on_scene_detach) {
            tc_log(TC_LOG_ERROR, "[RenderTopology] Viewport is already attached elsewhere");
            return false;
        }
        return true;
    }

    const char* name = tc_viewport_get_name(viewport);
    if (name && name[0] != '\0' && tc_viewport_handle_valid(find_viewport(scene, name))) {
        tc_log(TC_LOG_ERROR, "[RenderTopology] Scene already owns viewport named '%s'", name);
        return false;
    }

    viewport_attachments_.push_back(
        ViewportAttachment{scene, viewport, display, destroy_on_scene_detach}
    );
    ensure_record(scene).viewports.push_back(viewport);
    return true;
}

bool RenderTopology::unregister_viewport(tc_viewport_handle viewport) {
    auto existing = std::find_if(
        viewport_attachments_.begin(),
        viewport_attachments_.end(),
        [viewport](const ViewportAttachment& attachment) {
            return same_viewport(attachment.viewport, viewport);
        }
    );
    if (existing == viewport_attachments_.end()) return false;
    const tc_scene_handle scene = existing->scene;
    viewport_attachments_.erase(existing);

    SceneRecord* record = find_record(scene);
    if (!record) {
        tc_log(TC_LOG_ERROR, "[RenderTopology] Viewport attachment is missing its scene index");
        return true;
    }
    record->viewports.erase(
        std::remove_if(
            record->viewports.begin(),
            record->viewports.end(),
            [viewport](tc_viewport_handle candidate) { return same_viewport(candidate, viewport); }
        ),
        record->viewports.end()
    );
    erase_record_if_empty(scene_key(scene));
    return true;
}

const std::vector<tc_viewport_handle>& RenderTopology::viewports(tc_scene_handle scene) const {
    const SceneRecord* record = find_record(scene);
    return record == nullptr ? empty_viewports : record->viewports;
}

tc_viewport_handle RenderTopology::find_viewport(
    tc_scene_handle scene,
    const std::string& name
) const {
    for (tc_viewport_handle viewport : viewports(scene)) {
        if (!tc_viewport_handle_valid(viewport)) continue;
        const char* viewport_name = tc_viewport_get_name(viewport);
        if (viewport_name && name == viewport_name) return viewport;
    }
    return TC_VIEWPORT_HANDLE_INVALID;
}

tc_display* RenderTopology::display_for_viewport(tc_viewport_handle viewport) const {
    auto attachment = std::find_if(
        viewport_attachments_.begin(),
        viewport_attachments_.end(),
        [viewport](const ViewportAttachment& candidate) {
            return same_viewport(candidate.viewport, viewport);
        }
    );
    return attachment == viewport_attachments_.end() ? nullptr : attachment->display;
}

void RenderTopology::clear_scene_pipelines(tc_scene_handle scene, bool notify_detach) {
    SceneRecord* record = find_record(scene);
    if (record == nullptr) return;
    if (notify_detach && record->attached && tc_scene_handle_valid(scene)) {
        RenderAttachmentContext context(*this, scene);
        tc_scene_notify_render_detach(
            scene,
            reinterpret_cast<const tc_render_attachment_context*>(&context)
        );
        context.invalidate();
    }
    destroy_pipelines(*record);
    if (record->attached) {
        record->attached = false;
        attached_scenes_.erase(
            std::remove_if(
                attached_scenes_.begin(),
                attached_scenes_.end(),
                [scene](tc_scene_handle candidate) { return same_scene(candidate, scene); }
            ),
            attached_scenes_.end()
        );
    }
    erase_record_if_empty(scene_key(scene));
}

void RenderTopology::clear_all() {
    for (tc_scene_handle scene : attached_scenes_) {
        if (tc_scene_handle_valid(scene)) {
            RenderAttachmentContext context(*this, scene);
            tc_scene_notify_render_detach(
                scene,
                reinterpret_cast<const tc_render_attachment_context*>(&context)
            );
            context.invalidate();
        }
    }
    for (auto& [key, record] : scenes_) {
        (void)key;
        destroy_pipelines(record);
    }
    if (!managed_render_targets_.empty()) {
        tc_log(
            TC_LOG_ERROR,
            "[RenderTopology] Clearing topology with %zu registered render target(s)",
            managed_render_targets_.size()
        );
    }
    if (!viewport_attachments_.empty()) {
        tc_log(
            TC_LOG_ERROR,
            "[RenderTopology] Clearing topology with %zu viewport attachment(s)",
            viewport_attachments_.size()
        );
    }
    scenes_.clear();
    attached_scenes_.clear();
    managed_render_targets_.clear();
    viewport_attachments_.clear();
}

void RenderTopology::destroy_pipelines(SceneRecord& record) {
    destroy_pipeline_map(record.pipelines);
    record.pipeline_targets.clear();
}

void RenderTopology::erase_record_if_empty(uint64_t key) {
    auto it = scenes_.find(key);
    if (it == scenes_.end()) return;
    const SceneRecord& record = it->second;
    if (!record.attached && record.pipelines.empty() && record.pipeline_targets.empty()
            && record.render_targets.empty() && record.viewports.empty()) {
        scenes_.erase(it);
    }
}

} // namespace termin
