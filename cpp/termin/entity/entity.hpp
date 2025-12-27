#pragma once

#include <string>
#include <vector>
#include <cstdint>
#include <pybind11/pybind11.h>
#include "../geom/general_transform3.hpp"
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

// Entity - thin wrapper around tc_entity*.
// All data is stored in tc_entity (C core).
// Entity is created via new/delete for Python binding compatibility.
// tc_entity->data points back to this Entity* for reverse lookup.
class ENTITY_API Entity {
public:
    // The underlying C entity (owned by this wrapper)
    tc_entity* _e = nullptr;

    // Constructors
    Entity(const std::string& name = "entity", const std::string& uuid = "");
    Entity(const GeneralPose3& pose, const std::string& name = "entity", const std::string& uuid = "");

    // Wrap existing tc_entity (takes ownership)
    explicit Entity(tc_entity* e);

    ~Entity();

    // Disable copy
    Entity(const Entity&) = delete;
    Entity& operator=(const Entity&) = delete;

    // Move is allowed
    Entity(Entity&& other) noexcept;
    Entity& operator=(Entity&& other) noexcept;

    // --- Identity (delegated to tc_entity) ---

    const char* uuid() const { return tc_entity_uuid(_e); }
    uint64_t runtime_id() const { return tc_entity_runtime_id(_e); }
    uint32_t pick_id() { return tc_entity_pick_id(_e); }

    // --- Name ---

    const char* name() const { return tc_entity_name(_e); }
    void set_name(const std::string& n) { tc_entity_set_name(_e, n.c_str()); }

    // --- Transform ---

    GeneralTransform3 transform() const {
        return GeneralTransform3(tc_entity_transform(_e));
    }

    // --- Flags ---

    bool visible() const { return tc_entity_visible(_e); }
    void set_visible(bool v) { tc_entity_set_visible(_e, v); }

    bool active() const { return tc_entity_active(_e); }
    void set_active(bool v) { tc_entity_set_active(_e, v); }

    bool pickable() const { return tc_entity_pickable(_e); }
    void set_pickable(bool v) { tc_entity_set_pickable(_e, v); }

    bool selectable() const { return tc_entity_selectable(_e); }
    void set_selectable(bool v) { tc_entity_set_selectable(_e, v); }

    bool serializable() const { return tc_entity_serializable(_e); }
    void set_serializable(bool v) { tc_entity_set_serializable(_e, v); }

    int priority() const { return tc_entity_priority(_e); }
    void set_priority(int p) { tc_entity_set_priority(_e, p); }

    uint64_t layer() const { return tc_entity_layer(_e); }
    void set_layer(uint64_t l) { tc_entity_set_layer(_e, l); }

    uint64_t flags() const { return tc_entity_flags(_e); }
    void set_flags(uint64_t f) { tc_entity_set_flags(_e, f); }

    // --- Component management ---

    void add_component(Component* component);
    void add_component_ptr(tc_component* c);
    void remove_component(Component* component);
    void remove_component_ptr(tc_component* c);

    size_t component_count() const { return tc_entity_component_count(_e); }
    tc_component* component_at(size_t index) const { return tc_entity_component_at(_e, index); }

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
        return transform().global_pose();
    }

    void relocate(const GeneralPose3& pose) {
        transform().relocate(pose);
    }

    void relocate(const Pose3& pose) {
        transform().relocate(pose);
    }

    void relocate_global(const GeneralPose3& pose) {
        transform().relocate_global(pose);
    }

    void model_matrix(double* m) const {
        transform().world_matrix(m);
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

    // --- Raw access ---

    tc_entity* c_entity() { return _e; }
    const tc_entity* c_entity() const { return _e; }
};

// Get Entity* from tc_entity* (via data pointer)
inline Entity* entity_from_tc(tc_entity* e) {
    return e ? static_cast<Entity*>(tc_entity_data(e)) : nullptr;
}

} // namespace termin
