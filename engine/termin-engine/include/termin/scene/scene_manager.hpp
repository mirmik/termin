// scene_manager.hpp - C++ SceneManager
#ifndef TC_SCENE_MANAGER_HPP
#define TC_SCENE_MANAGER_HPP

#include "termin/engine/termin_engine_api.hpp"

#include <cstdint>
#include <functional>
#include <optional>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

extern "C" {
#include "core/tc_scene.h"
#include "core/tc_scene_extension.h"
#include "core/tc_scene_pool.h"
}

namespace termin {

    enum class SceneRole : std::uint8_t { Authoring, Runtime };

    struct TERMIN_ENGINE_API SceneKey {
        std::string identity;
        SceneRole role;

        explicit SceneKey(std::string identity_, SceneRole role_)
            : identity(std::move(identity_)), role(role_) {}

        bool operator==(const SceneKey&) const = default;
    };

    struct TERMIN_ENGINE_API SceneKeyHash {
        std::size_t operator()(const SceneKey& key) const noexcept;
    };

    struct TERMIN_ENGINE_API ManagedSceneInfo {
        SceneKey key;
        tc_scene_handle handle;
        std::string path;

        ManagedSceneInfo(SceneKey key_, tc_scene_handle handle_, std::string path_)
            : key(std::move(key_)), handle(handle_), path(std::move(path_)) {}
    };

    class TERMIN_ENGINE_API SceneManager {
    public:
        using AfterRenderCallback = std::function<void()>;
        using BeforeSceneCloseCallback = std::function<void(const SceneKey&)>;
        using BeforeSceneDestroyGuard = std::function<void(tc_scene_handle)>;

    protected:
        struct SceneRecord {
            tc_scene_handle handle = TC_SCENE_HANDLE_INVALID;
            std::string path;
        };

        std::unordered_map<SceneKey, SceneRecord, SceneKeyHash> _scenes;
        bool _render_requested = false;
        AfterRenderCallback _on_after_render;
        BeforeSceneCloseCallback _on_before_scene_close;
        BeforeSceneDestroyGuard _before_scene_destroy_guard;

    public:
        SceneManager();
        virtual ~SceneManager();

        SceneManager(const SceneManager&) = delete;
        SceneManager& operator=(const SceneManager&) = delete;

        tc_scene_handle create_scene(const SceneKey& key,
                                     const std::vector<tc_scene_ext_type_id>& extensions = {});
        bool close_scene(const SceneKey& key);
        bool close_scene(tc_scene_handle scene);
        void close_all_scenes();
        void close_scenes(SceneRole role);

        bool register_scene(const SceneKey& key, tc_scene_handle scene);
        bool unregister_scene(const SceneKey& key);

        tc_scene_handle get_scene(const SceneKey& key) const;
        bool has_scene(const SceneKey& key) const;
        bool is_registered(tc_scene_handle scene) const noexcept;
        std::optional<SceneKey> key_of(tc_scene_handle scene) const;
        std::vector<ManagedSceneInfo> scene_entries() const;

        std::string get_scene_path(const SceneKey& key) const;
        std::string get_scene_path(tc_scene_handle scene) const;
        bool set_scene_path(const SceneKey& key, const std::string& path);
        bool set_scene_path(tc_scene_handle scene, const std::string& path);

        static std::string read_json_file(const std::string& path);
        static void write_json_file(const std::string& path, const std::string& json);

        tc_scene_mode get_mode(const SceneKey& key) const;
        tc_scene_mode get_mode(tc_scene_handle scene) const;
        bool set_mode(const SceneKey& key, tc_scene_mode mode);
        bool set_mode(tc_scene_handle scene, tc_scene_mode mode);
        bool has_play_scenes() const;

        virtual bool tick(double dt);
        void request_render();
        bool consume_render_request();

        void set_on_after_render(AfterRenderCallback callback);
        void set_on_before_scene_close(BeforeSceneCloseCallback callback);
        void set_before_scene_destroy_guard(BeforeSceneDestroyGuard guard);
        void invoke_after_render();
        void invoke_before_scene_close(const SceneKey& key);
    };

} // namespace termin

#endif // TC_SCENE_MANAGER_HPP
