// entity_helpers.hpp - Common helpers for entity bindings
#pragma once

#include <nanobind/nanobind.h>
#include <cstring>
#include <stdexcept>

#include <termin/entity/entity.hpp>
#include <termin/entity/component.hpp>
#include <termin/geom/vec3.hpp>
#include <termin/geom/quat.hpp>
#include <termin/bindings/tc_value_helpers.hpp>
#include <tcbase/tc_log.hpp>
#include "core/tc_entity_pool_registry.h"

namespace nb = nanobind;

namespace termin {

// ============================================================================
// Python ref_vtable for CxxComponents created from Python
// ============================================================================

// retain = Py_INCREF(body), release = Py_DECREF(body), drop = NULL (Python GC owns object)
inline void py_component_ref_retain(tc_component* c) {
    if (c && c->body) Py_INCREF(reinterpret_cast<PyObject*>(c->body));
}

inline void py_component_ref_release(tc_component* c) {
    if (c && c->body) Py_DECREF(reinterpret_cast<PyObject*>(c->body));
}

inline const tc_component_ref_vtable g_py_component_ref_vtable = {
    py_component_ref_retain,
    py_component_ref_release,
    nullptr,  // drop: Python GC owns the object, no forced destroy
};

// ============================================================================
// CxxComponent Python init helper
// ============================================================================

// Initialize CxxComponent from Python __init__
// Handles placement new, body setup, and instance marking
template<typename T, typename... Args>
void cxx_component_init(nb::handle self, Args&&... args) {
    static_assert(std::is_base_of_v<CxxComponent, T>, "T must derive from CxxComponent");
    T* cpp = nb::inst_ptr<T>(self);
    new (cpp) T(std::forward<Args>(args)...);
    cpp->c_component()->body = self.ptr();
    cpp->c_component()->native_language = TC_LANGUAGE_PYTHON;
    cpp->c_component()->ref_vtable = &g_py_component_ref_vtable;
    nb::inst_mark_ready(self);
}

// ============================================================================
// Component Python conversion
// ============================================================================

// Convert CxxComponent to Python object (creates binding wrapper)
// Throws if C++ component has no Python bindings
inline nb::object component_to_python(CxxComponent* cxx) {
    if (!cxx) return nb::none();

    const char* type_name = cxx->type_name();
    nb::object result = nb::cast(cxx, nb::rv_policy::reference);

    // Check if nanobind returned the correct type
    std::string result_type = nb::type_name(result.type()).c_str();
    if (type_name && result_type.find(type_name) == std::string::npos) {
        throw std::runtime_error(
            std::string("C++ component '") + type_name + "' has no Python bindings. "
            "Either add Python bindings for this type or avoid accessing it from Python."
        );
    }

    return result;
}

// Convert tc_component to Python object
// For Python-native components: returns body directly
// For C++-native components: creates new Python wrapper each time
inline nb::object tc_component_to_python(tc_component* c) {
    if (!c) return nb::none();

    // Check if component is native Python - return body directly
    if (c->native_language == TC_LANGUAGE_PYTHON) {
        if (!c->body) return nb::none();
        return nb::borrow<nb::object>(reinterpret_cast<PyObject*>(c->body));
    }

    // Component is native C++ - create Python wrapper
    if (c->kind == TC_CXX_COMPONENT) {
        CxxComponent* cxx = CxxComponent::from_tc(c);
        if (!cxx) return nb::none();
        return component_to_python(cxx);
    }

    return nb::none();
}

// ============================================================================
// Pool helpers
// ============================================================================

inline tc_entity_pool_handle get_standalone_pool_handle() {
    return Entity::standalone_pool_handle();
}

// Legacy: get raw pointer (prefer get_standalone_pool_handle())
inline tc_entity_pool* get_standalone_pool() {
    return Entity::standalone_pool();
}

inline Entity migrate_entity_to_pool(Entity& entity, tc_entity_pool* dst_pool) {
    if (!entity.valid() || !dst_pool) {
        return Entity();
    }

    tc_entity_pool* src_pool = entity.pool();
    if (src_pool == dst_pool) {
        return entity;
    }

    tc_entity_id new_id = tc_entity_pool_migrate(src_pool, entity.id(), dst_pool);
    if (!tc_entity_id_valid(new_id)) {
        return Entity();
    }

    // Use handle-based constructor
    tc_entity_pool_handle dst_handle = tc_entity_pool_registry_find(dst_pool);
    return Entity(dst_handle, new_id);
}

inline nb::tuple mat44_row_tuple(const double* data) {
    return nb::make_tuple(
        nb::make_tuple(data[0], data[1], data[2], data[3]),
        nb::make_tuple(data[4], data[5], data[6], data[7]),
        nb::make_tuple(data[8], data[9], data[10], data[11]),
        nb::make_tuple(data[12], data[13], data[14], data[15])
    );
}

} // namespace termin
