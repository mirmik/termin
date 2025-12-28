#pragma once

#include <string>
#include <vector>
#include <cstdint>
#include <pybind11/pybind11.h>
#include "../geom/general_transform3.hpp"
#include "../../trent/trent.h"
#include "../../../core_c/include/tc_entity_pool.h"
#include "../../../core_c/include/tc_component.h"

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

class CxxComponent;
using Component = CxxComponent;

// Entity - wrapper around pool + entity_id.
// All data is stored in tc_entity_pool.
// Entity knows its pool and can access all data through it.
class ENTITY_API Entity {
public:
    tc_entity_pool* _pool = nullptr;
    tc_entity_id _id = TC_ENTITY_ID_INVALID;

    // Default constructor - invalid entity
    Entity() = default;

    // Construct from pool + id (for internal use)
    Entity(tc_entity_pool* pool, tc_entity_id id) : _pool(pool), _id(id) {}

    // Create new entity in pool
    static Entity create(tc_entity_pool* pool, const std::string& name = "entity");

    // Check if entity is valid (pool exists and id is alive)
    bool valid() const {
        return _pool && tc_entity_pool_alive(_pool, _id);
    }

    // Explicit bool conversion
    explicit operator bool() const { return valid(); }

    // --- Identity ---

    const char* uuid() const { return tc_entity_pool_uuid(_pool, _id); }
    uint64_t runtime_id() const { return tc_entity_pool_runtime_id(_pool, _id); }
    uint32_t pick_id() const { return tc_entity_pool_pick_id(_pool, _id); }

    // --- Name ---

    const char* name() const { return tc_entity_pool_name(_pool, _id); }
    void set_name(const std::string& n) { tc_entity_pool_set_name(_pool, _id, n.c_str()); }

    // --- Transform ---

    // Get position/rotation/scale
    void get_local_position(double* xyz) const { tc_entity_pool_get_local_position(_pool, _id, xyz); }
    void set_local_position(const double* xyz) { tc_entity_pool_set_local_position(_pool, _id, xyz); }

    void get_local_rotation(double* xyzw) const { tc_entity_pool_get_local_rotation(_pool, _id, xyzw); }
    void set_local_rotation(const double* xyzw) { tc_entity_pool_set_local_rotation(_pool, _id, xyzw); }

    void get_local_scale(double* xyz) const { tc_entity_pool_get_local_scale(_pool, _id, xyz); }
    void set_local_scale(const double* xyz) { tc_entity_pool_set_local_scale(_pool, _id, xyz); }

    void get_world_position(double* xyz) const { tc_entity_pool_get_world_position(_pool, _id, xyz); }
    void get_world_matrix(double* m16) const { tc_entity_pool_get_world_matrix(_pool, _id, m16); }

    void mark_transform_dirty() { tc_entity_pool_mark_dirty(_pool, _id); }

    // --- Transform view (creates GeneralTransform3 on same data) ---

    GeneralTransform3 transform() const {
        return GeneralTransform3(_pool, _id);
    }

    // --- Flags ---

    bool visible() const { return tc_entity_pool_visible(_pool, _id); }
    void set_visible(bool v) { tc_entity_pool_set_visible(_pool, _id, v); }

    bool active() const { return tc_entity_pool_active(_pool, _id); }
    void set_active(bool v) { tc_entity_pool_set_active(_pool, _id, v); }

    bool pickable() const { return tc_entity_pool_pickable(_pool, _id); }
    void set_pickable(bool v) { tc_entity_pool_set_pickable(_pool, _id, v); }

    bool selectable() const { return tc_entity_pool_selectable(_pool, _id); }
    void set_selectable(bool v) { tc_entity_pool_set_selectable(_pool, _id, v); }

    bool serializable() const { return tc_entity_pool_serializable(_pool, _id); }
    void set_serializable(bool v) { tc_entity_pool_set_serializable(_pool, _id, v); }

    int priority() const { return tc_entity_pool_priority(_pool, _id); }
    void set_priority(int p) { tc_entity_pool_set_priority(_pool, _id, p); }

    uint64_t layer() const { return tc_entity_pool_layer(_pool, _id); }
    void set_layer(uint64_t l) { tc_entity_pool_set_layer(_pool, _id, l); }

    uint64_t flags() const { return tc_entity_pool_flags(_pool, _id); }
    void set_flags(uint64_t f) { tc_entity_pool_set_flags(_pool, _id, f); }

    // --- Component management ---

    void add_component(Component* component);
    void add_component_ptr(tc_component* c);
    void remove_component(Component* component);
    void remove_component_ptr(tc_component* c);

    size_t component_count() const { return tc_entity_pool_component_count(_pool, _id); }
    tc_component* component_at(size_t index) const { return tc_entity_pool_component_at(_pool, _id, index); }

    CxxComponent* get_component_by_type(const std::string& type_name);

    // Note: get_component<T>() is defined in component.hpp after CxxComponent is fully defined
    template<typename T>
    T* get_component();

    // --- Hierarchy ---

    void set_parent(const Entity& parent);
    Entity parent() const;
    std::vector<Entity> children() const;

    // --- Lifecycle ---

    void update(float dt);
    void on_added_to_scene(py::object scene);
    void on_removed_from_scene();

    // --- Serialization ---

    nos::trent serialize() const;
    static Entity deserialize(tc_entity_pool* pool, const nos::trent& data);

    // --- User data (for back-pointer if needed) ---

    void* data() const { return tc_entity_pool_data(_pool, _id); }
    void set_data(void* d) { tc_entity_pool_set_data(_pool, _id, d); }

    // --- Pool/ID access ---

    tc_entity_pool* pool() const { return _pool; }
    tc_entity_id id() const { return _id; }

    // --- Comparison ---

    bool operator==(const Entity& other) const {
        return _pool == other._pool && tc_entity_id_eq(_id, other._id);
    }
    bool operator!=(const Entity& other) const { return !(*this == other); }
};

} // namespace termin
