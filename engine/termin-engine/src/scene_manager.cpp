#include "termin/scene/scene_manager.hpp"

#include <filesystem>
#include <fstream>
#include <sstream>

extern "C" {
#include "core/tc_scene_extension.h"
#include "tc_profiler.h"
#include <tcbase/tc_log.h>
}

namespace termin {
    namespace {
        const char* role_name(SceneRole role) {
            return role == SceneRole::Authoring ? "authoring" : "runtime";
        }
    }

    std::size_t SceneKeyHash::operator()(const SceneKey& key) const noexcept {
        const auto identity_hash = std::hash<std::string>{}(key.identity);
        const auto role_hash = std::hash<std::uint8_t>{}(static_cast<std::uint8_t>(key.role));
        return identity_hash ^ (role_hash + 0x9e3779b9U + (identity_hash << 6U) + (identity_hash >> 2U));
    }

    SceneManager::SceneManager() = default;
    SceneManager::~SceneManager() { close_all_scenes(); }

    tc_scene_handle SceneManager::create_scene(const SceneKey& key,
                                               const std::vector<tc_scene_ext_type_id>& extensions) {
        if (key.identity.empty()) {
            tc_log(TC_LOG_ERROR, "[SceneManager] create_scene: empty scene identity");
            return TC_SCENE_HANDLE_INVALID;
        }
        if (has_scene(key)) {
            tc_log(TC_LOG_ERROR, "[SceneManager] create_scene: scene '%s' (%s) already exists",
                   key.identity.c_str(), role_name(key.role));
            return TC_SCENE_HANDLE_INVALID;
        }
        const tc_scene_handle handle = tc_scene_new();
        if (!tc_scene_handle_valid(handle)) {
            tc_log(TC_LOG_ERROR, "[SceneManager] create_scene: failed to create scene '%s'", key.identity.c_str());
            return TC_SCENE_HANDLE_INVALID;
        }
        tc_scene_set_name(handle, key.identity.c_str());
        for (tc_scene_ext_type_id type_id : extensions) {
            if (!tc_scene_ext_attach(handle, type_id)) {
                tc_log(TC_LOG_ERROR, "[SceneManager] failed to attach scene extension %llu to scene '%s'",
                       (unsigned long long)type_id, key.identity.c_str());
            }
        }
        if (!register_scene(key, handle)) {
            tc_log(TC_LOG_ERROR, "[SceneManager] create_scene: failed to register scene '%s' (%s)",
                   key.identity.c_str(), role_name(key.role));
            tc_scene_free(handle);
            return TC_SCENE_HANDLE_INVALID;
        }
        return handle;
    }

    bool SceneManager::close_scene(const SceneKey& key) {
        auto it = _scenes.find(key);
        if (it == _scenes.end()) {
            tc_log(TC_LOG_ERROR, "[SceneManager] close_scene: scene '%s' (%s) not found",
                   key.identity.c_str(), role_name(key.role));
            return false;
        }
        const tc_scene_handle handle = it->second.handle;
        invoke_before_scene_close(key);
        if (_before_scene_destroy_guard) {
            _before_scene_destroy_guard(handle);
        }
        _scenes.erase(it);
        tc_scene_free(handle);
        return true;
    }

    bool SceneManager::close_scene(tc_scene_handle scene) {
        const auto key = key_of(scene);
        if (!key) {
            tc_log(TC_LOG_ERROR, "[SceneManager] close_scene: scene handle is not registered");
            return false;
        }
        return close_scene(*key);
    }

    void SceneManager::close_all_scenes() {
        std::vector<SceneKey> keys;
        keys.reserve(_scenes.size());
        for (const auto& [key, record] : _scenes) {
            (void)record;
            keys.push_back(key);
        }
        for (const SceneKey& key : keys) {
            close_scene(key);
        }
    }

    void SceneManager::close_scenes(SceneRole role) {
        std::vector<SceneKey> keys;
        for (const auto& [key, record] : _scenes) {
            (void)record;
            if (key.role == role) keys.push_back(key);
        }
        for (const SceneKey& key : keys) close_scene(key);
    }

    bool SceneManager::register_scene(const SceneKey& key, tc_scene_handle scene) {
        if (key.identity.empty()) {
            tc_log(TC_LOG_ERROR, "[SceneManager] register_scene: empty scene identity");
            return false;
        }
        if (!tc_scene_alive(scene)) {
            tc_log(TC_LOG_ERROR, "[SceneManager] register_scene: invalid or dead handle for scene '%s' (%s)",
                   key.identity.c_str(), role_name(key.role));
            return false;
        }
        if (has_scene(key)) {
            tc_log(TC_LOG_ERROR, "[SceneManager] register_scene: scene '%s' (%s) already exists",
                   key.identity.c_str(), role_name(key.role));
            return false;
        }
        if (const auto existing = key_of(scene)) {
            tc_log(TC_LOG_ERROR, "[SceneManager] register_scene: handle is already registered as '%s' (%s)",
                   existing->identity.c_str(), role_name(existing->role));
            return false;
        }
        _scenes.emplace(key, SceneRecord{scene, {}});
        return true;
    }

    bool SceneManager::unregister_scene(const SceneKey& key) {
        if (_scenes.erase(key) == 0) {
            tc_log(TC_LOG_ERROR, "[SceneManager] unregister_scene: scene '%s' (%s) not found",
                   key.identity.c_str(), role_name(key.role));
            return false;
        }
        return true;
    }

    bool SceneManager::rekey_scene(const SceneKey& source, const SceneKey& destination) {
        if (destination.identity.empty()) {
            tc_log(TC_LOG_ERROR, "[SceneManager] rekey_scene: empty destination identity");
            return false;
        }
        auto source_it = _scenes.find(source);
        if (source_it == _scenes.end()) {
            tc_log(TC_LOG_ERROR, "[SceneManager] rekey_scene: source scene '%s' (%s) not found",
                   source.identity.c_str(), role_name(source.role));
            return false;
        }
        if (source == destination) return true;
        if (source.role != destination.role) {
            tc_log(TC_LOG_ERROR, "[SceneManager] rekey_scene: cannot change scene role from %s to %s",
                   role_name(source.role), role_name(destination.role));
            return false;
        }
        if (_scenes.contains(destination)) {
            tc_log(TC_LOG_ERROR, "[SceneManager] rekey_scene: destination scene '%s' (%s) already exists",
                   destination.identity.c_str(), role_name(destination.role));
            return false;
        }

        auto node = _scenes.extract(source_it);
        node.key() = destination;
        _scenes.insert(std::move(node));
        return true;
    }

    tc_scene_handle SceneManager::get_scene(const SceneKey& key) const {
        const auto it = _scenes.find(key);
        return it != _scenes.end() ? it->second.handle : TC_SCENE_HANDLE_INVALID;
    }

    bool SceneManager::has_scene(const SceneKey& key) const { return _scenes.contains(key); }

    bool SceneManager::is_registered(tc_scene_handle scene) const noexcept {
        if (!tc_scene_alive(scene)) return false;
        for (const auto& [key, record] : _scenes) {
            (void)key;
            if (tc_scene_handle_eq(scene, record.handle)) return true;
        }
        return false;
    }

    std::optional<SceneKey> SceneManager::key_of(tc_scene_handle scene) const {
        if (!tc_scene_alive(scene)) return std::nullopt;
        for (const auto& [key, record] : _scenes) {
            if (tc_scene_handle_eq(scene, record.handle)) return key;
        }
        return std::nullopt;
    }

    std::vector<ManagedSceneInfo> SceneManager::scene_entries() const {
        std::vector<ManagedSceneInfo> result;
        result.reserve(_scenes.size());
        for (const auto& [key, record] : _scenes) result.push_back({key, record.handle, record.path});
        return result;
    }

    std::string SceneManager::get_scene_path(const SceneKey& key) const {
        const auto it = _scenes.find(key);
        return it != _scenes.end() ? it->second.path : "";
    }

    std::string SceneManager::get_scene_path(tc_scene_handle scene) const {
        const auto key = key_of(scene);
        return key ? get_scene_path(*key) : "";
    }

    bool SceneManager::set_scene_path(const SceneKey& key, const std::string& path) {
        auto it = _scenes.find(key);
        if (it == _scenes.end()) {
            tc_log(TC_LOG_ERROR, "[SceneManager] set_scene_path: scene '%s' (%s) not found",
                   key.identity.c_str(), role_name(key.role));
            return false;
        }
        it->second.path = path;
        tc_scene_set_source_path(it->second.handle, path.empty() ? nullptr : path.c_str());
        return true;
    }

    bool SceneManager::set_scene_path(tc_scene_handle scene, const std::string& path) {
        const auto key = key_of(scene);
        if (!key) {
            tc_log(TC_LOG_ERROR, "[SceneManager] set_scene_path: scene handle is not registered");
            return false;
        }
        return set_scene_path(*key, path);
    }

    tc_scene_mode SceneManager::get_mode(const SceneKey& key) const {
        const auto it = _scenes.find(key);
        return it == _scenes.end() ? TC_SCENE_MODE_INACTIVE : tc_scene_get_mode(it->second.handle);
    }

    tc_scene_mode SceneManager::get_mode(tc_scene_handle scene) const {
        const auto key = key_of(scene);
        return key ? get_mode(*key) : TC_SCENE_MODE_INACTIVE;
    }

    bool SceneManager::set_mode(const SceneKey& key, tc_scene_mode mode) {
        const auto it = _scenes.find(key);
        if (it == _scenes.end()) {
            tc_log(TC_LOG_ERROR, "[SceneManager] set_mode: scene '%s' (%s) not found",
                   key.identity.c_str(), role_name(key.role));
            return false;
        }
        tc_scene_set_mode(it->second.handle, mode);
        return true;
    }

    bool SceneManager::set_mode(tc_scene_handle scene, tc_scene_mode mode) {
        const auto key = key_of(scene);
        if (!key) {
            tc_log(TC_LOG_ERROR, "[SceneManager] set_mode: scene handle is not registered");
            return false;
        }
        return set_mode(*key, mode);
    }

    bool SceneManager::has_play_scenes() const {
        for (const auto& [key, record] : _scenes) {
            (void)key;
            if (tc_scene_get_mode(record.handle) == TC_SCENE_MODE_PLAY) return true;
        }
        return false;
    }

    bool SceneManager::tick(double dt) {
        const bool profile = tc_profiler_enabled();
        for (const auto& [key, record] : _scenes) {
            const tc_scene_mode mode = tc_scene_get_mode(record.handle);
            if (mode == TC_SCENE_MODE_INACTIVE) continue;
            const std::string section =
                (mode == TC_SCENE_MODE_STOP ? "Scene Editor Update: " : "Scene Update: ") + key.identity;
            if (profile) tc_profiler_begin_section(section.c_str());
            if (mode == TC_SCENE_MODE_STOP) tc_scene_editor_update(record.handle, dt);
            else if (mode == TC_SCENE_MODE_PLAY) tc_scene_update(record.handle, dt);
            if (profile) tc_profiler_end_section();
        }
        bool scene_requested = false;
        for (const auto& [key, record] : _scenes) {
            (void)key;
            scene_requested = tc_scene_consume_render_request(record.handle) || scene_requested;
        }
        const bool should_render = has_play_scenes() || _render_requested || scene_requested;
        if (should_render) _render_requested = false;
        return should_render;
    }

    void SceneManager::request_render() { _render_requested = true; }
    bool SceneManager::consume_render_request() {
        const bool requested = _render_requested;
        _render_requested = false;
        return requested;
    }

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

    void SceneManager::write_json_file(const std::string& path, const std::string& json) {
        const std::filesystem::path filepath(path);
        const std::filesystem::path temp_path = filepath.parent_path() / (filepath.filename().string() + ".tmp");
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

    void SceneManager::set_on_after_render(AfterRenderCallback callback) { _on_after_render = std::move(callback); }
    void SceneManager::set_on_before_scene_close(BeforeSceneCloseCallback callback) {
        _on_before_scene_close = std::move(callback);
    }
    void SceneManager::set_before_scene_destroy_guard(BeforeSceneDestroyGuard guard) {
        _before_scene_destroy_guard = std::move(guard);
    }
    void SceneManager::invoke_after_render() { if (_on_after_render) _on_after_render(); }
    void SceneManager::invoke_before_scene_close(const SceneKey& key) {
        if (_on_before_scene_close) _on_before_scene_close(key);
    }
} // namespace termin
