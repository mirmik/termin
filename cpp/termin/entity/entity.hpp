#pragma once

#include <string>
#include <vector>
#include <cstdint>
#include <memory>
#include <functional>
#include <pybind11/pybind11.h>
#include "../geom/general_transform3.hpp"
#include "../core/identifiable.hpp"
#include "../../trent/trent.h"

namespace py = pybind11;

namespace termin {

class Component;

/**
 * Entity - container of components with transform data.
 *
 * Unity-like architecture: Entity holds Components,
 * has a transform hierarchy, and belongs to a Scene.
 *
 * Inherits from Identifiable for uuid and runtime_id.
 */
class Entity : public Identifiable {
public:
    // Name (uuid comes from Identifiable)
    std::string name;

    // Transform (owned)
    std::unique_ptr<GeneralTransform3> transform;

    // Flags
    bool visible = true;
    bool active = true;
    bool pickable = true;
    bool selectable = true;
    bool serializable = true;

    // Rendering
    int priority = 0;      // lower values drawn first
    uint64_t layer = 1;    // 64-bit layer mask
    uint64_t flags = 0;    // custom flags

    // Scene (Python object for now, will migrate later)
    py::object scene;

    // Components (owned)
    std::vector<Component*> components;

    // Constructors
    Entity(const std::string& name = "entity", const std::string& uuid = "");
    Entity(const GeneralPose3& pose, const std::string& name = "entity", const std::string& uuid = "");

    ~Entity();

    // Disable copy
    Entity(const Entity&) = delete;
    Entity& operator=(const Entity&) = delete;

    // Move is allowed
    Entity(Entity&& other) noexcept;
    Entity& operator=(Entity&& other) noexcept;

    // --- Pick ID ---

    /**
     * Unique identifier for pick passes (hash from uuid).
     * Computed lazily and cached.
     */
    uint32_t pick_id();

    // --- Component management ---

    void add_component(Component* component);
    void remove_component(Component* component);

    Component* get_component_by_type(const std::string& type_name);

    template<typename T>
    T* get_component() {
        for (Component* comp : components) {
            T* typed = dynamic_cast<T*>(comp);
            if (typed) return typed;
        }
        return nullptr;
    }

    // --- Transform shortcuts ---

    const GeneralPose3& global_pose() const {
        return transform->global_pose();
    }

    void relocate(const GeneralPose3& pose) {
        transform->relocate(pose);
    }

    void relocate(const Pose3& pose) {
        transform->relocate(pose);
    }

    void relocate_global(const GeneralPose3& pose) {
        transform->relocate_global(pose);
    }

    /**
     * Get 4x4 model matrix (column-major, OpenGL convention).
     */
    void model_matrix(double* m) const {
        transform->world_matrix(m);
    }

    // --- Hierarchy shortcuts ---

    void set_parent(Entity* parent);
    Entity* parent() const;
    std::vector<Entity*> children() const;

    // --- Lifecycle ---

    void update(float dt);
    void on_added_to_scene(py::object scene);
    void on_removed_from_scene();

    // --- Serialization ---

    nos::trent serialize() const;
    static Entity* deserialize(const nos::trent& data);

private:
    uint32_t _pick_id = 0;
    bool _pick_id_computed = false;

    void _compute_pick_id();
};

} // namespace termin
