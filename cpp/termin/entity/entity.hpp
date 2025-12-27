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
#include "../../../core_c/include/tc_entity.h"

// DLL export/import macros for Windows
#ifdef _WIN32
    #ifdef ENTITY_LIB_EXPORTS
        #define ENTITY_API __declspec(dllexport)
    #else
        #define ENTITY_API __declspec(dllimport)
    #endif
#else
    #define ENTITY_API
#endif

namespace py = pybind11;

namespace termin {

class Component;

// Entity - container of components with transform data.
// Unity-like architecture: Entity holds Components,
// has a transform hierarchy, and belongs to a Scene.
// Inherits from Identifiable for uuid and runtime_id.
class ENTITY_API Entity : public Identifiable {
public:
    // Name (uuid comes from Identifiable)
    std::string name;

    // Transform - returns view wrapper over tc_entity's tc_transform
    GeneralTransform3 transform;

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

    // Note: Components are stored in tc_entity (_e), not here.
    // Use component_count() and component_at() to access them.

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

    // Add C++ component (stores in tc_entity)
    void add_component(Component* component);

    // Add component by tc_component pointer (for PythonComponent)
    void add_component_ptr(tc_component* c);

    void remove_component(Component* component);
    void remove_component_ptr(tc_component* c);

    // Component access (delegates to tc_entity)
    size_t component_count() const;
    tc_component* component_at(size_t index) const;

    // Get C++ Component by type name
    Component* get_component_by_type(const std::string& type_name);

    template<typename T>
    T* get_component() {
        size_t count = component_count();
        for (size_t i = 0; i < count; i++) {
            tc_component* tc = component_at(i);
            if (tc && tc->is_native) {
                Component* comp = static_cast<Component*>(tc->data);
                T* typed = dynamic_cast<T*>(comp);
                if (typed) return typed;
            }
        }
        return nullptr;
    }

    // --- Transform shortcuts ---

    const GeneralPose3& global_pose() const {
        return transform.global_pose();
    }

    void relocate(const GeneralPose3& pose) {
        transform.relocate(pose);
    }

    void relocate(const Pose3& pose) {
        transform.relocate(pose);
    }

    void relocate_global(const GeneralPose3& pose) {
        transform.relocate_global(pose);
    }

    /**
     * Get 4x4 model matrix (column-major, OpenGL convention).
     */
    void model_matrix(double* m) const {
        transform.world_matrix(m);
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

    // --- C Core Integration ---

    // Get tc_entity pointer (creates lazily if needed)
    tc_entity* c_entity();

    // Sync C++ fields to C structure (call before C code uses _e)
    void sync_to_c();

    // Sync C structure back to C++ fields (call after C code modifies _e)
    void sync_from_c();

private:
    uint32_t _pick_id = 0;
    bool _pick_id_computed = false;

    // C entity pointer (created lazily for tc_scene integration)
    tc_entity* _e = nullptr;

    void _compute_pick_id();
    void _ensure_c_entity();
};

} // namespace termin
