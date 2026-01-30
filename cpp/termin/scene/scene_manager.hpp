// scene_manager.hpp - C++ SceneManager base class
#ifndef TC_SCENE_MANAGER_HPP
#define TC_SCENE_MANAGER_HPP

#include <string>
#include <unordered_map>
#include <vector>

extern "C" {
#include "../../../core_c/include/tc_scene.h"
}

namespace termin {

// Forward declaration
class TcScene;

// SceneManager - manages multiple scenes and their update cycles
// Python SceneManager inherits from this class
class SceneManager {
public:
    SceneManager() = default;
    virtual ~SceneManager() = default;

    // Disable copy
    SceneManager(const SceneManager&) = delete;
    SceneManager& operator=(const SceneManager&) = delete;

    // Scene registration (called by Python SceneManager)
    void register_scene(const std::string& name, tc_scene* scene);
    void unregister_scene(const std::string& name);

    // Scene mode management
    tc_scene_mode get_mode(const std::string& name) const;
    void set_mode(const std::string& name, tc_scene_mode mode);

    // Scene access
    tc_scene* get_scene(const std::string& name) const;
    bool has_scene(const std::string& name) const;
    std::vector<std::string> scene_names() const;

    // Check if any scene is in PLAY mode
    bool has_play_scenes() const;

    // Main update loop - updates all scenes based on their mode
    // Returns true if render is needed (has PLAY scenes or render_requested)
    virtual bool tick(double dt);

    // Before render - call before_render on all active scenes
    void before_render();

    // Render request flag
    void request_render();
    bool consume_render_request();

protected:
    // Registered scenes: name -> tc_scene*
    // Note: TcScene objects are owned by Python, we just store raw pointers
    std::unordered_map<std::string, tc_scene*> _scenes;

    // Render request flag
    bool _render_requested = false;
};

} // namespace termin

#endif // TC_SCENE_MANAGER_HPP
