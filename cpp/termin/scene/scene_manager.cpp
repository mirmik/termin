// scene_manager.cpp - SceneManager implementation
#include "scene_manager.hpp"

extern "C" {
#include "../../../core_c/include/tc_profiler.h"
#include "../../../core_c/include/tc_log.h"
}

namespace termin {

void SceneManager::register_scene(const std::string& name, tc_scene* scene) {
    if (!scene) {
        tc_log(TC_LOG_ERROR, "[SceneManager] register_scene: scene is null for name '%s'", name.c_str());
        return;
    }
    _scenes[name] = scene;
}

void SceneManager::unregister_scene(const std::string& name) {
    _scenes.erase(name);
}

tc_scene_mode SceneManager::get_mode(const std::string& name) const {
    auto it = _scenes.find(name);
    if (it == _scenes.end()) {
        return TC_SCENE_MODE_INACTIVE;
    }
    return tc_scene_get_mode(it->second);
}

void SceneManager::set_mode(const std::string& name, tc_scene_mode mode) {
    auto it = _scenes.find(name);
    if (it == _scenes.end()) {
        tc_log(TC_LOG_ERROR, "[SceneManager] set_mode: scene '%s' not found", name.c_str());
        return;
    }
    tc_scene_set_mode(it->second, mode);
}

tc_scene* SceneManager::get_scene(const std::string& name) const {
    auto it = _scenes.find(name);
    return (it != _scenes.end()) ? it->second : nullptr;
}

bool SceneManager::has_scene(const std::string& name) const {
    return _scenes.find(name) != _scenes.end();
}

std::vector<std::string> SceneManager::scene_names() const {
    std::vector<std::string> names;
    names.reserve(_scenes.size());
    for (const auto& [name, scene] : _scenes) {
        names.push_back(name);
    }
    return names;
}

bool SceneManager::has_play_scenes() const {
    for (const auto& [name, scene] : _scenes) {
        if (tc_scene_get_mode(scene) == TC_SCENE_MODE_PLAY) {
            return true;
        }
    }
    return false;
}

bool SceneManager::tick(double dt) {
    bool profile = tc_profiler_enabled();

    for (const auto& [name, scene] : _scenes) {
        tc_scene_mode mode = tc_scene_get_mode(scene);

        if (mode == TC_SCENE_MODE_INACTIVE) {
            continue;
        } else if (mode == TC_SCENE_MODE_STOP) {
            // Editor mode: minimal update for gizmos, etc.
            if (profile) tc_profiler_begin_section(("Scene Editor Update: " + name).c_str());
            tc_scene_editor_update(scene, dt);
            if (profile) tc_profiler_end_section();
        } else if (mode == TC_SCENE_MODE_PLAY) {
            // Game mode: full simulation
            if (profile) tc_profiler_begin_section(("Scene Update: " + name).c_str());
            tc_scene_update(scene, dt);
            if (profile) tc_profiler_end_section();
        }
    }

    bool has_play = has_play_scenes();
    bool should_render = has_play || _render_requested;

    if (should_render) {
        _render_requested = false;
    }

    return should_render;
}

void SceneManager::before_render() {
    bool profile = tc_profiler_enabled();

    for (const auto& [name, scene] : _scenes) {
        tc_scene_mode mode = tc_scene_get_mode(scene);
        if (mode != TC_SCENE_MODE_INACTIVE) {
            if (profile) tc_profiler_begin_section(("Scene: " + name).c_str());
            tc_scene_before_render(scene);
            if (profile) tc_profiler_end_section();
        }
    }
}

void SceneManager::request_render() {
    _render_requested = true;
}

bool SceneManager::consume_render_request() {
    bool was_requested = _render_requested;
    _render_requested = false;
    return was_requested;
}

} // namespace termin
