// entity_helpers.hpp - Common helpers for entity bindings
#pragma once

#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <cstring>

#include "termin/entity/entity.hpp"
#include "termin/entity/component.hpp"
#include "termin/camera/camera_component.hpp"
#include "termin/geom/vec3.hpp"
#include "termin/geom/quat.hpp"
#include "termin/bindings/tc_value_helpers.hpp"
#include "tc_log.hpp"

namespace nb = nanobind;

namespace termin {

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
    nb::inst_mark_ready(self);
}

// ============================================================================
// Component Python conversion
// ============================================================================

// Convert CxxComponent to Python object (creates binding wrapper)
inline nb::object component_to_python(CxxComponent* cxx) {
    if (!cxx) return nb::none();

    const char* type_name = cxx->type_name();
    nb::object result = nb::cast(cxx, nb::rv_policy::reference);

    // Check if nanobind returned the correct type
    std::string result_type = nb::type_name(result.type()).c_str();
    if (type_name && result_type.find(type_name) == std::string::npos) {
        printf("[ERROR] component_to_python: type mismatch! ptr=%p, expected='%s', got='%s'. "
               "Module with bindings for '%s' may not be loaded.\n",
               (void*)cxx, type_name, result_type.c_str(), type_name);
    }

    return result;
}

// Convert tc_component to Python object
// For Python-native components: returns body directly
// For C++-native components: creates or reuses Python binding wrapper
inline nb::object tc_component_to_python(tc_component* c) {
    if (!c) return nb::none();

    // Check if component is native Python - return body directly
    if (c->native_language == TC_LANGUAGE_PYTHON) {
        if (!c->body) return nb::none();
        // Validate: Python-native component should not have Python binding
        PyObject* binding = static_cast<PyObject*>(tc_component_get_binding(c, TC_LANGUAGE_PYTHON));
        if (binding) {
            tc::Log::error(
                "[tc_component_to_python] BUG: Python-native component has Python binding! "
                "type='%s', ptr=%p, body=%p, binding=%p",
                tc_component_type_name(c), (void*)c, c->body, (void*)binding);
        }
        return nb::borrow<nb::object>(reinterpret_cast<PyObject*>(c->body));
    }

    // Component is native C++ - create or reuse Python binding wrapper
    if (c->kind == TC_NATIVE_COMPONENT) {
        // Check if we already have a binding
        PyObject* existing = static_cast<PyObject*>(tc_component_get_binding(c, TC_LANGUAGE_PYTHON));
        if (existing) {
            // Reuse existing binding
            return nb::borrow<nb::object>(existing);
        }

        CxxComponent* cxx = CxxComponent::from_tc(c);
        if (!cxx) return nb::none();

        nb::object result = component_to_python(cxx);
        if (!result.is_none()) {
            // Mark as binding (not body owner) and store reference
            result.attr("_is_binding") = true;
            result.attr("_is_destroyed") = false;

            // Store binding in tc_component (prevent GC while C++ alive)
            PyObject* py_obj = result.ptr();
            Py_INCREF(py_obj);
            tc_component_set_binding(c, TC_LANGUAGE_PYTHON, py_obj);
        }
        return result;
    }

    return nb::none();
}

// ============================================================================
// Pool helpers
// ============================================================================

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

    return Entity(dst_pool, new_id);
}

// ============================================================================
// numpy <-> geometry conversion
// ============================================================================

inline Vec3 numpy_to_vec3(nb::ndarray<double, nb::c_contig, nb::device::cpu> arr) {
    const double* data = arr.data();
    return Vec3{data[0], data[1], data[2]};
}

inline nb::object vec3_to_numpy(const Vec3& v) {
    double* buf = new double[3];
    buf[0] = v.x;
    buf[1] = v.y;
    buf[2] = v.z;
    nb::capsule owner(buf, [](void* p) noexcept { delete[] static_cast<double*>(p); });
    size_t shape[1] = {3};
    return nb::cast(nb::ndarray<nb::numpy, double>(buf, 1, shape, owner));
}

inline Quat numpy_to_quat(nb::ndarray<double, nb::c_contig, nb::device::cpu> arr) {
    const double* data = arr.data();
    return Quat{data[0], data[1], data[2], data[3]};
}

} // namespace termin
