#pragma once

#include <string>
#include <vector>
#include <cstdint>
#include "../geom/general_transform3.hpp"
#include "../../../core_c/include/tc_entity_pool.h"
#include "../../../core_c/include/tc_entity_pool_registry.h"
#include "../../../core_c/include/tc_component.h"
#include "../../../core_c/include/tc_scene.h"

extern "C" {
#include "../../../core_c/include/tc_value.h"
}

#include "../export.hpp"

namespace termin {

class CxxComponent;
using Component = CxxComponent;

// Entity - wrapper around tc_entity_handle.
// All data is stored in tc_entity_pool.
// Entity uses handle for safe access - pool may be destroyed.
class ENTITY_API Entity {
public:
    tc_entity_handle _h = TC_ENTITY_HANDLE_INVALID;

    // Default constructor - invalid entity
    Entity() = default;

    // Construct from unified handle
    Entity(tc_entity_handle h) : _h(h) {}

    // Construct from pool handle + id
    Entity(tc_entity_pool_handle pool_handle, tc_entity_id id) : _h(tc_entity_handle_make(pool_handle, id)) {}

    // Legacy: Construct from pool pointer + id (finds handle in registry)
    Entity(tc_entity_pool* pool, tc_entity_id id);

    // Create new entity in pool
    static Entity create(tc_entity_pool_handle pool_handle, const std::string& name = "entity");
    static Entity create_with_uuid(tc_entity_pool_handle pool_handle, const std::string& name, const std::string& uuid);

    // Legacy: Create in pool pointer (finds handle)
    static Entity create(tc_entity_pool* pool, const std::string& name = "entity");
    static Entity create_with_uuid(tc_entity_pool* pool, const std::string& name, const std::string& uuid);

    // Get global standalone pool handle (for entities/transforms created outside of Scene)
    static tc_entity_pool_handle standalone_pool_handle();

    // Legacy: get raw pointer (deprecated, use pool_handle())
    static tc_entity_pool* standalone_pool();

    // Check if entity is valid (pool alive and id alive in pool)
    bool valid() const {
        return tc_entity_handle_valid(_h);
    }

    // Get pool pointer (may be NULL if pool destroyed)
    tc_entity_pool* pool_ptr() const {
        return tc_entity_pool_registry_get(_h.pool);
    }

    // Explicit bool conversion
    explicit operator bool() const { return valid(); }

    // Get unified handle
    tc_entity_handle handle() const { return _h; }

    // --- Identity ---

    const char* uuid() const { return tc_entity_uuid(_h); }
    void set_uuid(const char* uuid) { tc_entity_set_uuid(_h, uuid); }
    uint64_t runtime_id() const { auto* p = pool_ptr(); return p ? tc_entity_pool_runtime_id(p, _h.id) : 0; }
    uint32_t pick_id() const { auto* p = pool_ptr(); return p ? tc_entity_pool_pick_id(p, _h.id) : 0; }

    // --- Name ---

    const char* name() const { return tc_entity_name(_h); }
    void set_name(const std::string& n) { tc_entity_set_name(_h, n.c_str()); }

    // --- Transform ---

    // Get position/rotation/scale
    void get_local_position(double* xyz) const { tc_entity_get_local_position(_h, xyz); }
    void set_local_position(const double* xyz) { tc_entity_set_local_position(_h, xyz); }

    void get_local_rotation(double* xyzw) const { tc_entity_get_local_rotation(_h, xyzw); }
    void set_local_rotation(const double* xyzw) { tc_entity_set_local_rotation(_h, xyzw); }

    void get_local_scale(double* xyz) const { tc_entity_get_local_scale(_h, xyz); }
    void set_local_scale(const double* xyz) { tc_entity_set_local_scale(_h, xyz); }

    void get_global_position(double* xyz) const { auto* p = pool_ptr(); if (p) tc_entity_pool_get_global_position(p, _h.id, xyz); }
    void get_world_matrix(double* m16) const { tc_entity_get_world_matrix(_h, m16); }

    void mark_transform_dirty() { tc_entity_mark_dirty(_h); }

    // --- Transform view (creates GeneralTransform3 on same data) ---

    GeneralTransform3 transform() const {
        return GeneralTransform3(_h);
    }

    // --- Flags ---

    bool visible() const { return tc_entity_visible(_h); }
    void set_visible(bool v) { tc_entity_set_visible(_h, v); }

    bool enabled() const { return tc_entity_enabled(_h); }
    void set_enabled(bool v) { tc_entity_set_enabled(_h, v); }

    bool pickable() const { return tc_entity_pickable(_h); }
    void set_pickable(bool v) { tc_entity_set_pickable(_h, v); }

    bool selectable() const { return tc_entity_selectable(_h); }
    void set_selectable(bool v) { tc_entity_set_selectable(_h, v); }

    bool serializable() const { return tc_entity_serializable(_h); }
    void set_serializable(bool v) { tc_entity_set_serializable(_h, v); }

    int priority() const { return tc_entity_priority(_h); }
    void set_priority(int p) { tc_entity_set_priority(_h, p); }

    uint64_t layer() const { return tc_entity_layer(_h); }
    void set_layer(uint64_t l) { tc_entity_set_layer(_h, l); }

    uint64_t flags() const { return tc_entity_flags(_h); }
    void set_flags(uint64_t f) { tc_entity_set_flags(_h, f); }

    // --- Component management ---

    void add_component(Component* component);
    void add_component_ptr(tc_component* c);
    void remove_component(Component* component);
    void remove_component_ptr(tc_component* c);

    size_t component_count() const { return tc_entity_component_count(_h); }
    tc_component* component_at(size_t index) const { return tc_entity_component_at(_h, index); }

    // Validate all components - returns true if all ok, prints errors if not
    bool validate_components() const;

    CxxComponent* get_component_by_type(const std::string& type_name);

    // Get any component (C++ or Python) by type name - returns tc_component*
    tc_component* get_component_by_type_name(const std::string& type_name);

    // Note: get_component<T>() is defined in component.hpp after CxxComponent is fully defined
    template<typename T>
    T* get_component();

    // --- Hierarchy ---

    void set_parent(const Entity& parent);
    Entity parent() const;
    std::vector<Entity> children() const;
    Entity find_child(const std::string& name) const;

    // --- Lifecycle ---

    void update(float dt);
    void on_added_to_scene(tc_scene_handle scene);
    void on_removed_from_scene();

    // --- Serialization ---

    // Serialize for kind registry (uuid only)
    tc_value serialize_to_value() const {
        tc_value d = tc_value_dict_new();
        if (valid()) {
            tc_value_dict_set(&d, "uuid", tc_value_string(uuid()));
        }
        return d;
    }

    // Serialize base entity data (returns tc_value dict, caller must free)
    tc_value serialize_base() const;
    static Entity deserialize(tc_entity_pool_handle pool_handle, const tc_value* data);
    static Entity deserialize(tc_entity_pool* pool, const tc_value* data);

    // Deserialize from tc_value with scene context for entity resolution
    void deserialize_from(const tc_value* data, tc_scene_handle scene = TC_SCENE_HANDLE_INVALID);

    // --- Pool/ID access ---

    // Get pool pointer (may be NULL if pool destroyed) - prefer pool_ptr()
    tc_entity_pool* pool() const { return pool_ptr(); }
    tc_entity_id id() const { return _h.id; }

    // Get pool handle (safe, never dangling)
    tc_entity_pool_handle pool_handle() const { return _h.pool; }

    // --- Comparison ---

    bool operator==(const Entity& other) const {
        return tc_entity_handle_eq(_h, other._h);
    }
    bool operator!=(const Entity& other) const { return !(*this == other); }
};

} // namespace termin
