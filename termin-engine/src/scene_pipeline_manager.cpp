#include "scene_pipeline_manager.hpp"

#include "termin/render/render_pipeline.hpp"
#include "termin/render/scene_pipeline_template.hpp"

#include <cstdint>

extern "C" {
#include <tcbase/tc_log.h>
#include "core/tc_scene_render_mount.h"
}

namespace termin::rendering_manager_detail {

uint64_t ScenePipelineManager::scene_key(tc_scene_handle h) {
    return (static_cast<uint64_t>(h.index) << 32) | h.generation;
}

void ScenePipelineManager::attach_scene(tc_scene_handle scene) {
    if (!tc_scene_handle_valid(scene)) return;

    // Recompile replaces old pipeline handles, but the scene is still render-attached.
    destroy_scene_pipelines(scene, false);

    tc_scene_render_mount* mount = tc_scene_render_mount_get(scene);
    size_t template_count = mount ? mount->pipeline_template_count : 0;
    uint64_t key = scene_key(scene);

    for (size_t i = 0; i < template_count; i++) {
        tc_spt_handle spt_handle = mount->pipeline_templates[i];
        if (!tc_spt_is_valid(spt_handle)) continue;

        TcScenePipelineTemplate templ(spt_handle);
        if (!templ.is_loaded()) {
            tc_log(TC_LOG_WARN, "[RenderingManager] Template not loaded: '%s'", templ.name().c_str());
            continue;
        }

        RenderPipeline* compiled = templ.compile();
        if (!compiled) {
            tc_log(TC_LOG_WARN, "[RenderingManager] Failed to compile template: '%s'", templ.name().c_str());
            continue;
        }

        std::string name = templ.name();
        tc_pipeline_handle ph = compiled->handle();
        tc_pipeline_set_name(ph, name.c_str());
        delete compiled; // RenderPipeline no longer owns; handle stays in pool.

        scene_pipelines_[key][name] = ph;
        pipeline_targets_[key][name] = templ.target_viewports();
    }

    tc_scene_notify_render_attach(scene);
}

void ScenePipelineManager::detach_scene(tc_scene_handle scene) {
    if (!tc_scene_handle_valid(scene)) return;
    tc_scene_notify_render_detach(scene);
    destroy_scene_pipelines(scene, false);
}

tc_pipeline_handle ScenePipelineManager::get_scene_pipeline(
    tc_scene_handle scene,
    const std::string& name
) const {
    if (!tc_scene_handle_valid(scene)) return TC_PIPELINE_HANDLE_INVALID;
    uint64_t key = scene_key(scene);
    auto scene_it = scene_pipelines_.find(key);
    if (scene_it == scene_pipelines_.end()) return TC_PIPELINE_HANDLE_INVALID;
    auto pipe_it = scene_it->second.find(name);
    return (pipe_it != scene_it->second.end()) ? pipe_it->second : TC_PIPELINE_HANDLE_INVALID;
}

tc_pipeline_handle ScenePipelineManager::get_scene_pipeline(const std::string& name) const {
    for (const auto& [key, pipelines] : scene_pipelines_) {
        (void)key;
        auto it = pipelines.find(name);
        if (it != pipelines.end()) {
            return it->second;
        }
    }
    tc_log(TC_LOG_WARN, "[RenderingManager] get_scene_pipeline NOT FOUND: '%s'", name.c_str());
    return TC_PIPELINE_HANDLE_INVALID;
}

void ScenePipelineManager::set_pipeline_targets(
    tc_scene_handle scene,
    const std::string& pipeline_name,
    const std::vector<std::string>& targets
) {
    if (!tc_scene_handle_valid(scene)) {
        tc_log(TC_LOG_ERROR, "[RenderingManager] cannot set targets for invalid scene pipeline '%s'", pipeline_name.c_str());
        return;
    }
    pipeline_targets_[scene_key(scene)][pipeline_name] = targets;
}

static const std::vector<std::string> empty_targets;

const std::vector<std::string>& ScenePipelineManager::get_pipeline_targets(
    tc_scene_handle scene,
    const std::string& pipeline_name
) const {
    if (!tc_scene_handle_valid(scene)) return empty_targets;
    auto scene_it = pipeline_targets_.find(scene_key(scene));
    if (scene_it == pipeline_targets_.end()) return empty_targets;
    auto target_it = scene_it->second.find(pipeline_name);
    return target_it != scene_it->second.end() ? target_it->second : empty_targets;
}

std::vector<std::string> ScenePipelineManager::get_pipeline_names(tc_scene_handle scene) const {
    std::vector<std::string> names;
    if (!tc_scene_handle_valid(scene)) return names;

    uint64_t key = scene_key(scene);
    auto scene_it = scene_pipelines_.find(key);
    if (scene_it != scene_pipelines_.end()) {
        for (const auto& [name, ptr] : scene_it->second) {
            (void)ptr;
            names.push_back(name);
        }
    }
    return names;
}

void ScenePipelineManager::clear_scene_pipelines(tc_scene_handle scene) {
    destroy_scene_pipelines(scene, true);
}

void ScenePipelineManager::destroy_scene_pipelines(tc_scene_handle scene, bool notify_detach) {
    if (!tc_scene_handle_valid(scene)) return;
    uint64_t key = scene_key(scene);

    auto scene_it = scene_pipelines_.find(key);
    if (scene_it == scene_pipelines_.end()) {
        pipeline_targets_.erase(key);
        return;
    }

    if (notify_detach) {
        tc_scene_notify_render_detach(scene);
    }

    pipeline_targets_.erase(key);

    for (const auto& [name, ph] : scene_it->second) {
        (void)name;
        tc_pipeline_destroy(ph);
    }
    scene_pipelines_.erase(key);
}

void ScenePipelineManager::clear_all_scene_pipelines() {
    for (const auto& [key, pipelines] : scene_pipelines_) {
        (void)pipelines;
        tc_scene_handle scene;
        scene.index = static_cast<uint32_t>(key >> 32);
        scene.generation = static_cast<uint32_t>(key & 0xFFFFFFFF);
        if (tc_scene_handle_valid(scene)) {
            tc_scene_notify_render_detach(scene);
        }
    }

    for (auto& [key, pipelines] : scene_pipelines_) {
        (void)key;
        for (auto& [name, ph] : pipelines) {
            (void)name;
            tc_pipeline_destroy(ph);
        }
    }
    scene_pipelines_.clear();
    pipeline_targets_.clear();
}

} // namespace termin::rendering_manager_detail
