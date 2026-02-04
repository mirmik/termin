// tc_scene.hpp - C++ wrapper for tc_scene_handle
#pragma once

#include <memory>
#include <string>
#include <tuple>
#include <vector>

#include <trent/trent.h>
#include <trent/json.h>

#include "tc_scene.h"
#include "tc_scene_pool.h"
#include "tc_entity_pool.h"
#include "viewport_config.hpp"
#include "geom/vec3.hpp"
#include "geom/vec4.hpp"

namespace termin {

// Forward declarations
class Entity;
class CxxComponent;
class TcScenePipelineTemplate;
class RenderPipeline;
class RenderingManager;
class ColliderComponent;
struct Ray3;

namespace collision {
    class CollisionWorld;
}

// Result of scene raycast
struct SceneRaycastHit {
    tc_entity_handle entity = TC_ENTITY_HANDLE_INVALID;
    ColliderComponent* component = nullptr;
    double point_on_ray[3] = {0, 0, 0};
    double point_on_collider[3] = {0, 0, 0};
    double distance = 0.0;

    bool valid() const { return component != nullptr; }
};

// C++ wrapper for tc_scene_handle (non-owning reference)
// Scene lifetime is managed by tc_scene_pool, not by TcSceneRef instances.
// Use TcSceneRef::create() to create a new scene, destroy() to explicitly free it.
class TcSceneRef {
public:
    tc_scene_handle _h = TC_SCENE_HANDLE_INVALID;

    // Default constructor - creates invalid reference
    TcSceneRef() = default;

    // Construct from existing handle (non-owning)
    explicit TcSceneRef(tc_scene_handle h) : _h(h) {}

    // Destructor does NOT destroy the scene (it's in the pool)
    ~TcSceneRef() = default;

    // Factory method to create a new scene in the pool
    static TcSceneRef create(const std::string& name = "", const std::string& uuid = "");

    // Explicitly destroy the scene (removes from pool)
    void destroy();

    // Get scene handle
    tc_scene_handle handle() const { return _h; }

    // Check if scene is alive (not destroyed)
    bool is_alive() const { return tc_scene_alive(_h); }
    bool valid() const { return is_alive(); }

    // Check if handles point to same scene
    bool operator==(const TcSceneRef& other) const {
        return tc_scene_handle_eq(_h, other._h);
    }
    bool operator!=(const TcSceneRef& other) const { return !(*this == other); }

    // Copy is allowed (non-owning reference)
    TcSceneRef(const TcSceneRef&) = default;
    TcSceneRef& operator=(const TcSceneRef&) = default;

    // Move is also allowed (invalidates source)
    TcSceneRef(TcSceneRef&& other) noexcept : _h(other._h) {
        other._h = TC_SCENE_HANDLE_INVALID;
    }
    TcSceneRef& operator=(TcSceneRef&& other) noexcept {
        if (this != &other) {
            _h = other._h;
            other._h = TC_SCENE_HANDLE_INVALID;
        }
        return *this;
    }

    // Entity management
    void add_entity(const Entity& e);
    void remove_entity(const Entity& e);
    size_t entity_count() const;

    // Component registration (C++ Component)
    void register_component(CxxComponent* c);
    void unregister_component(CxxComponent* c);

    // Component registration by pointer (for TcComponent/pure Python components)
    void register_component_ptr(uintptr_t ptr);
    void unregister_component_ptr(uintptr_t ptr);

    // Update loop
    void update(double dt);
    void editor_update(double dt);
    void before_render();

    // Fixed timestep
    double fixed_timestep() const;
    void set_fixed_timestep(double dt);
    double accumulated_time() const;
    void reset_accumulated_time();

    // Component queries
    size_t pending_start_count() const;
    size_t update_list_count() const;
    size_t fixed_update_list_count() const;

    // Get entity pool owned by this scene
    tc_entity_pool* entity_pool() const;

    // Create a new entity directly in scene's pool
    Entity create_entity(const std::string& name = "");

    // Find entity by UUID in scene's pool
    Entity get_entity(const std::string& uuid) const;

    // Find entity by pick_id in scene's pool
    Entity get_entity_by_pick_id(uint32_t pick_id) const;

    // Find entity by name in scene's pool
    Entity find_entity_by_name(const std::string& name) const;

    // Scene name
    std::string name() const;
    void set_name(const std::string& n);

    // Scene UUID
    std::string uuid() const;
    void set_uuid(const std::string& u);

    // Layer names (0-63)
    std::string get_layer_name(int index) const;
    void set_layer_name(int index, const std::string& name);

    // Flag names (0-63)
    std::string get_flag_name(int index) const;
    void set_flag_name(int index, const std::string& name);

    // Background color (RGBA)
    std::tuple<float, float, float, float> get_background_color() const;
    void set_background_color(float r, float g, float b, float a);

    // Background color as Vec4
    Vec4 background_color() const;
    void set_background_color(const Vec4& color);

    // Skybox colors as Vec3
    Vec3 skybox_color() const;
    void set_skybox_color(const Vec3& color);
    Vec3 skybox_top_color() const;
    void set_skybox_top_color(const Vec3& color);
    Vec3 skybox_bottom_color() const;
    void set_skybox_bottom_color(const Vec3& color);

    // Ambient color as Vec3
    Vec3 ambient_color() const;
    void set_ambient_color(const Vec3& color);
    float ambient_intensity() const;
    void set_ambient_intensity(float intensity);

    // Viewport configurations (stored in tc_scene C API)
    void add_viewport_config(const ViewportConfig& config);
    void remove_viewport_config(size_t index);
    void clear_viewport_configs();
    size_t viewport_config_count() const;
    ViewportConfig viewport_config_at(size_t index) const;
    std::vector<ViewportConfig> viewport_configs() const;

    // Metadata access (converted from tc_value on each call)
    nos::trent metadata() const;

    // Metadata value access by path (e.g. "termin.editor.camera_name")
    // Returns nil trent if path not found
    nos::trent get_metadata_at_path(const std::string& path) const;
    void set_metadata_at_path(const std::string& path, const nos::trent& value);
    bool has_metadata_at_path(const std::string& path) const;

    // Metadata JSON serialization
    std::string metadata_to_json() const;
    void metadata_from_json(const std::string& json_str);

    // Lighting properties
    tc_scene_lighting* lighting();

    // Get all entities in scene's pool
    std::vector<Entity> get_all_entities() const;

    // Migrate entity to this scene's pool
    Entity migrate_entity(Entity& entity);

    // Collision world access
    collision::CollisionWorld* collision_world() const;

    // Raycast - find first intersection (distance == 0)
    SceneRaycastHit raycast(const Ray3& ray) const;

    // Closest to ray - find closest object (minimum distance)
    SceneRaycastHit closest_to_ray(const Ray3& ray) const;

    // Pipeline Templates (stored in tc_scene, compiled by RenderingManager)
    void add_pipeline_template(const TcScenePipelineTemplate& templ);
    void clear_pipeline_templates();
    size_t pipeline_template_count() const;
    TcScenePipelineTemplate pipeline_template_at(size_t index) const;

    // Get compiled pipeline by name (from RenderingManager)
    RenderPipeline* get_pipeline(const std::string& name) const;

    // Get all pipeline names (from RenderingManager)
    std::vector<std::string> get_pipeline_names() const;

    // Get pipeline targets (from RenderingManager)
    const std::vector<std::string>& get_pipeline_targets(const std::string& name) const;

    // --- Serialization ---

    // Serialize scene to trent (entities, settings, metadata)
    nos::trent serialize() const;

    // Load data into existing scene
    // Returns number of loaded entities
    int load_from_data(const nos::trent& data, bool update_settings = true);

    // Serialize to JSON string
    std::string to_json_string() const;

    // Load from JSON string
    void from_json_string(const std::string& json);
};

} // namespace termin
