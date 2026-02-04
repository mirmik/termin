// scene_manager.cpp - SceneManager implementation
#include "scene_manager.hpp"

#include <fstream>
#include <sstream>
#include <filesystem>

extern "C" {
#include "../../../core_c/include/tc_profiler.h"
#include "../../../core_c/include/tc_log.h"
}

namespace termin {

SceneManager::~SceneManager() {
    close_all_scenes();
}

// --- Scene lifecycle ---

tc_scene_handle SceneManager::create_scene(const std::string& name) {
    if (_scenes.find(name) != _scenes.end()) {
        tc_log(TC_LOG_ERROR, "[SceneManager] create_scene: scene '%s' already exists", name.c_str());
        return TC_SCENE_HANDLE_INVALID;
    }

    tc_scene_handle h = tc_scene_new();
    if (!tc_scene_handle_valid(h)) {
        tc_log(TC_LOG_ERROR, "[SceneManager] create_scene: failed to create scene '%s'", name.c_str());
        return TC_SCENE_HANDLE_INVALID;
    }

    tc_scene_set_name(h, name.c_str());
    _scenes[name] = h;
    return h;
}

void SceneManager::close_scene(const std::string& name) {
    auto it = _scenes.find(name);
    if (it == _scenes.end()) {
        tc_log(TC_LOG_ERROR, "[SceneManager] close_scene: scene '%s' not found", name.c_str());
        return;
    }

    tc_scene_handle h = it->second;

    // Remove from maps first
    _scenes.erase(it);
    _paths.erase(name);

    // Destroy the scene
    tc_scene_free(h);
}

void SceneManager::close_all_scenes() {
    // Collect names first to avoid iterator invalidation
    std::vector<std::string> names;
    names.reserve(_scenes.size());
    for (const auto& [name, _] : _scenes) {
        names.push_back(name);
    }

    for (const auto& name : names) {
        close_scene(name);
    }
}

// --- Scene registration ---

void SceneManager::register_scene(const std::string& name, tc_scene_handle scene) {
    if (!tc_scene_handle_valid(scene)) {
        tc_log(TC_LOG_ERROR, "[SceneManager] register_scene: invalid handle for name '%s'", name.c_str());
        return;
    }
    _scenes[name] = scene;
}

void SceneManager::unregister_scene(const std::string& name) {
    _scenes.erase(name);
    _paths.erase(name);
}

// --- Path management ---

std::string SceneManager::get_scene_path(const std::string& name) const {
    auto it = _paths.find(name);
    return (it != _paths.end()) ? it->second : "";
}

void SceneManager::set_scene_path(const std::string& name, const std::string& path) {
    if (path.empty()) {
        _paths.erase(name);
    } else {
        _paths[name] = path;
    }
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

tc_scene_handle SceneManager::get_scene(const std::string& name) const {
    auto it = _scenes.find(name);
    return (it != _scenes.end()) ? it->second : TC_SCENE_HANDLE_INVALID;
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

// --- File I/O ---

std::string SceneManager::read_json_file(const std::string& path) {
    std::ifstream file(path);
    if (!file.is_open()) {
        tc_log(TC_LOG_ERROR, "[SceneManager] read_json_file: failed to open '%s'", path.c_str());
        return "";
    }

    std::stringstream buffer;
    buffer << file.rdbuf();
    return buffer.str();
}

// --- Callbacks ---

void SceneManager::set_on_after_render(AfterRenderCallback callback) {
    _on_after_render = std::move(callback);
}

void SceneManager::set_on_before_scene_close(BeforeSceneCloseCallback callback) {
    _on_before_scene_close = std::move(callback);
}

void SceneManager::invoke_after_render() {
    if (_on_after_render) {
        _on_after_render();
    }
}

void SceneManager::invoke_before_scene_close(const std::string& name) {
    if (_on_before_scene_close) {
        _on_before_scene_close(name);
    }
}

void SceneManager::write_json_file(const std::string& path, const std::string& json) {
    // Atomic write: write to temp file, then rename
    std::filesystem::path filepath(path);
    std::filesystem::path temp_path = filepath.parent_path() / (filepath.filename().string() + ".tmp");

    std::ofstream file(temp_path);
    if (!file.is_open()) {
        tc_log(TC_LOG_ERROR, "[SceneManager] write_json_file: failed to create temp file for '%s'", path.c_str());
        return;
    }

    file << json;
    file.close();

    if (!file) {
        tc_log(TC_LOG_ERROR, "[SceneManager] write_json_file: failed to write to '%s'", temp_path.string().c_str());
        std::filesystem::remove(temp_path);
        return;
    }

    std::error_code ec;
    std::filesystem::rename(temp_path, filepath, ec);
    if (ec) {
        tc_log(TC_LOG_ERROR, "[SceneManager] write_json_file: failed to rename temp file to '%s': %s",
               path.c_str(), ec.message().c_str());
        std::filesystem::remove(temp_path);
    }
}

} // namespace termin
