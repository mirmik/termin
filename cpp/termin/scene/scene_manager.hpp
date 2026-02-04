// scene_manager.hpp - C++ SceneManager
#ifndef TC_SCENE_MANAGER_HPP
#define TC_SCENE_MANAGER_HPP

#include <string>
#include <unordered_map>
#include <vector>
#include <functional>

extern "C" {
#include "../../../core_c/include/tc_scene.h"
#include "../../../core_c/include/tc_scene_pool.h"
}

namespace termin {

// SceneManager - manages multiple scenes and their update cycles
class SceneManager {
public:
    SceneManager() = default;
    virtual ~SceneManager();

    // Disable copy
    SceneManager(const SceneManager&) = delete;
    SceneManager& operator=(const SceneManager&) = delete;

    // --- Scene lifecycle ---

    // Create a new scene in the pool and register it
    tc_scene_handle create_scene(const std::string& name);

    // Close and destroy a scene
    void close_scene(const std::string& name);

    // Close all scenes
    void close_all_scenes();

    // --- Scene registration (for external scenes) ---

    void register_scene(const std::string& name, tc_scene_handle scene);
    void unregister_scene(const std::string& name);

    // --- Scene access ---

    tc_scene_handle get_scene(const std::string& name) const;
    bool has_scene(const std::string& name) const;
    std::vector<std::string> scene_names() const;

    // --- Path management ---

    std::string get_scene_path(const std::string& name) const;
    void set_scene_path(const std::string& name, const std::string& path);

    // --- File I/O (JSON only, scene data handled by TcScene) ---

    // Read JSON file and return as string
    static std::string read_json_file(const std::string& path);

    // Write JSON string to file (atomic write)
    static void write_json_file(const std::string& path, const std::string& json);

    // --- Scene mode management ---

    tc_scene_mode get_mode(const std::string& name) const;
    void set_mode(const std::string& name, tc_scene_mode mode);

    // Check if any scene is in PLAY mode
    bool has_play_scenes() const;

    // --- Update cycle ---

    // Main update loop - updates all scenes based on their mode
    // Returns true if render is needed (has PLAY scenes or render_requested)
    virtual bool tick(double dt);

    // Before render - call before_render on all active scenes
    void before_render();

    // Render request flag
    void request_render();
    bool consume_render_request();

    // --- Callbacks ---
    using AfterRenderCallback = std::function<void()>;
    using BeforeSceneCloseCallback = std::function<void(const std::string&)>;

    void set_on_after_render(AfterRenderCallback callback);
    void set_on_before_scene_close(BeforeSceneCloseCallback callback);

    void invoke_after_render();
    void invoke_before_scene_close(const std::string& name);

    // --- Full tick with rendering ---
    // Calls tick(), before_render(), RenderingManager::render_all(), and after_render callback
    bool tick_and_render(double dt);

protected:
    // Registered scenes: name -> tc_scene_handle
    std::unordered_map<std::string, tc_scene_handle> _scenes;

    // Scene file paths: name -> path
    std::unordered_map<std::string, std::string> _paths;

    // Render request flag
    bool _render_requested = false;

    // Callbacks
    AfterRenderCallback _on_after_render;
    BeforeSceneCloseCallback _on_before_scene_close;
};

} // namespace termin

#endif // TC_SCENE_MANAGER_HPP
