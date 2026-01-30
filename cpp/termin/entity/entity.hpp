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

// Entity - wrapper around pool_handle + entity_id.
// All data is stored in tc_entity_pool.
// Entity uses handle for safe access - pool may be destroyed.
class ENTITY_API Entity {
public:
    tc_entity_pool_handle _pool_handle = TC_ENTITY_POOL_HANDLE_INVALID;
    tc_entity_id _id = TC_ENTITY_ID_INVALID;

    // Default constructor - invalid entity
    Entity() = default;

    // Construct from pool handle + id
    Entity(tc_entity_pool_handle pool_handle, tc_entity_id id) : _pool_handle(pool_handle), _id(id) {}

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
        tc_entity_pool* pool = tc_entity_pool_registry_get(_pool_handle);
        return pool && tc_entity_pool_alive(pool, _id);
    }

    // Get pool pointer (may be NULL if pool destroyed)
    tc_entity_pool* pool_ptr() const {
        return tc_entity_pool_registry_get(_pool_handle);
    }

    // Explicit bool conversion
    explicit operator bool() const { return valid(); }

    // --- Identity ---

    const char* uuid() const { auto* p = pool_ptr(); return p ? tc_entity_pool_uuid(p, _id) : ""; }
    void set_uuid(const char* uuid) { if (auto* p = pool_ptr()) tc_entity_pool_set_uuid(p, _id, uuid); }
    uint64_t runtime_id() const { auto* p = pool_ptr(); return p ? tc_entity_pool_runtime_id(p, _id) : 0; }
    uint32_t pick_id() const { auto* p = pool_ptr(); return p ? tc_entity_pool_pick_id(p, _id) : 0; }

    // --- Name ---

    const char* name() const { auto* p = pool_ptr(); return p ? tc_entity_pool_name(p, _id) : ""; }
    void set_name(const std::string& n) { if (auto* p = pool_ptr()) tc_entity_pool_set_name(p, _id, n.c_str()); }

    // --- Transform ---

    // Get position/rotation/scale
    void get_local_position(double* xyz) const { if (auto* p = pool_ptr()) tc_entity_pool_get_local_position(p, _id, xyz); }
    void set_local_position(const double* xyz) { if (auto* p = pool_ptr()) tc_entity_pool_set_local_position(p, _id, xyz); }

    void get_local_rotation(double* xyzw) const { if (auto* p = pool_ptr()) tc_entity_pool_get_local_rotation(p, _id, xyzw); }
    void set_local_rotation(const double* xyzw) { if (auto* p = pool_ptr()) tc_entity_pool_set_local_rotation(p, _id, xyzw); }

    void get_local_scale(double* xyz) const { if (auto* p = pool_ptr()) tc_entity_pool_get_local_scale(p, _id, xyz); }
    void set_local_scale(const double* xyz) { if (auto* p = pool_ptr()) tc_entity_pool_set_local_scale(p, _id, xyz); }

    void get_global_position(double* xyz) const { if (auto* p = pool_ptr()) tc_entity_pool_get_global_position(p, _id, xyz); }
    void get_world_matrix(double* m16) const { if (auto* p = pool_ptr()) tc_entity_pool_get_world_matrix(p, _id, m16); }

    void mark_transform_dirty() { if (auto* p = pool_ptr()) tc_entity_pool_mark_dirty(p, _id); }

    // --- Transform view (creates GeneralTransform3 on same data) ---

    GeneralTransform3 transform() const {
        return GeneralTransform3(_pool_handle, _id);
    }

    // --- Flags ---

    bool visible() const { auto* p = pool_ptr(); return p ? tc_entity_pool_visible(p, _id) : false; }
    void set_visible(bool v) { if (auto* p = pool_ptr()) tc_entity_pool_set_visible(p, _id, v); }

    bool enabled() const { auto* p = pool_ptr(); return p ? tc_entity_pool_enabled(p, _id) : false; }
    void set_enabled(bool v) { if (auto* p = pool_ptr()) tc_entity_pool_set_enabled(p, _id, v); }

    bool pickable() const { auto* p = pool_ptr(); return p ? tc_entity_pool_pickable(p, _id) : false; }
    void set_pickable(bool v) { if (auto* p = pool_ptr()) tc_entity_pool_set_pickable(p, _id, v); }

    bool selectable() const { auto* p = pool_ptr(); return p ? tc_entity_pool_selectable(p, _id) : false; }
    void set_selectable(bool v) { if (auto* p = pool_ptr()) tc_entity_pool_set_selectable(p, _id, v); }

    bool serializable() const { auto* p = pool_ptr(); return p ? tc_entity_pool_serializable(p, _id) : false; }
    void set_serializable(bool v) { if (auto* p = pool_ptr()) tc_entity_pool_set_serializable(p, _id, v); }

    int priority() const { auto* p = pool_ptr(); return p ? tc_entity_pool_priority(p, _id) : 0; }
    void set_priority(int p) { if (auto* pool = pool_ptr()) tc_entity_pool_set_priority(pool, _id, p); }

    uint64_t layer() const { auto* p = pool_ptr(); return p ? tc_entity_pool_layer(p, _id) : 0; }
    void set_layer(uint64_t l) { if (auto* p = pool_ptr()) tc_entity_pool_set_layer(p, _id, l); }

    uint64_t flags() const { auto* p = pool_ptr(); return p ? tc_entity_pool_flags(p, _id) : 0; }
    void set_flags(uint64_t f) { if (auto* p = pool_ptr()) tc_entity_pool_set_flags(p, _id, f); }

    // --- Component management ---

    void add_component(Component* component);
    void add_component_ptr(tc_component* c);
    void remove_component(Component* component);
    void remove_component_ptr(tc_component* c);

    size_t component_count() const { auto* p = pool_ptr(); return p ? tc_entity_pool_component_count(p, _id) : 0; }
    tc_component* component_at(size_t index) const { auto* p = pool_ptr(); return p ? tc_entity_pool_component_at(p, _id, index) : nullptr; }

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
    tc_entity_id id() const { return _id; }

    // Get pool handle (safe, never dangling)
    tc_entity_pool_handle pool_handle() const { return _pool_handle; }

    // --- Comparison ---

    bool operator==(const Entity& other) const {
        return tc_entity_pool_handle_eq(_pool_handle, other._pool_handle) && tc_entity_id_eq(_id, other._id);
    }
    bool operator!=(const Entity& other) const { return !(*this == other); }
};

} // namespace termin
