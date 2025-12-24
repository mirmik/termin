#pragma once

#include <vector>
#include <string>
#include <cstdint>
#include <functional>
#include <pybind11/pybind11.h>

#include "termin/geom/vec3.hpp"
#include "termin/lighting/light.hpp"
#include "termin/lighting/shadow_settings.hpp"
#include "termin/core/identifiable.hpp"

namespace py = pybind11;

namespace termin {

class Entity;
class Component;

/**
 * Skybox rendering type.
 */
enum class SkyboxType {
    None,
    Solid,
    Gradient
};

inline const char* skybox_type_to_string(SkyboxType t) {
    switch (t) {
        case SkyboxType::None: return "none";
        case SkyboxType::Solid: return "solid";
        case SkyboxType::Gradient: return "gradient";
    }
    return "gradient";
}

inline SkyboxType skybox_type_from_string(const std::string& s) {
    if (s == "none") return SkyboxType::None;
    if (s == "solid") return SkyboxType::Solid;
    if (s == "gradient") return SkyboxType::Gradient;
    return SkyboxType::Gradient;
}

/**
 * Scene - container for entities and rendering parameters.
 *
 * Unity-like architecture: Scene contains Entities which contain Components.
 * Manages:
 * - Entity hierarchy
 * - Lighting (lights, ambient, shadows)
 * - Skybox settings
 * - Update loops (component start/update/fixed_update)
 */
class Scene : public Identifiable {
public:
    // --- Construction ---

    Scene(const std::string& uuid = "");
    ~Scene();

    // Disable copy
    Scene(const Scene&) = delete;
    Scene& operator=(const Scene&) = delete;

    // --- Background ---

    Vec3 background_color{0.05, 0.05, 0.08};
    double background_alpha = 1.0;

    // --- Lighting ---

    std::vector<Light> lights;
    Vec3 ambient_color{1.0, 1.0, 1.0};
    double ambient_intensity = 0.1;
    Vec3 light_direction{0.3, 1.0, -0.5};
    Vec3 light_color{1.0, 1.0, 1.0};
    ShadowSettings shadow_settings;

    // --- Skybox ---

    SkyboxType skybox_type = SkyboxType::Gradient;
    Vec3 skybox_color{0.5, 0.7, 0.9};
    Vec3 skybox_top_color{0.4, 0.6, 0.9};
    Vec3 skybox_bottom_color{0.6, 0.5, 0.4};

    // --- Entity Management ---

    /**
     * Add entity to scene (sorted by priority).
     * Also adds all children recursively.
     */
    void add(Entity* entity);

    /**
     * Add entity without recursing into children.
     */
    void add_non_recurse(Entity* entity);

    /**
     * Remove entity from scene.
     */
    void remove(Entity* entity);

    /**
     * Find entity by UUID.
     */
    Entity* find_entity_by_uuid(const std::string& uuid) const;

    /**
     * Get all entities (read-only).
     */
    const std::vector<Entity*>& get_entities() const { return entities_; }

    /**
     * Get entity count.
     */
    size_t entity_count() const { return entities_.size(); }

    // --- Component Registration ---

    /**
     * Register component for updates (called by Entity when component is added).
     */
    void register_component(Component* component);

    /**
     * Unregister component (called by Entity when component is removed).
     */
    void unregister_component(Component* component);

    // --- Update Loop ---

    /**
     * Fixed timestep for physics (default 1/60).
     */
    double fixed_timestep = 1.0 / 60.0;

    /**
     * Update scene: call start() on pending components, then update/fixed_update.
     */
    void update(double dt);

    // --- Events (Python callbacks) ---

    py::object on_entity_added;
    py::object on_entity_removed;

private:
    std::vector<Entity*> entities_;

    // Components with update/fixed_update
    std::vector<Component*> update_list_;
    std::vector<Component*> fixed_update_list_;
    std::vector<Component*> pending_start_;

    // Fixed timestep accumulator
    double accumulated_time_ = 0.0;

    // Helper for recursive entity search
    Entity* find_entity_recursive(Entity* entity, const std::string& uuid) const;
};

} // namespace termin
