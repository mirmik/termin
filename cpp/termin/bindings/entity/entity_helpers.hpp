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

namespace nb = nanobind;

namespace termin {

// ============================================================================
// Component Python conversion
// ============================================================================

// Convert CxxComponent to Python object (creates binding wrapper)
inline nb::object component_to_python(CxxComponent* cxx) {
    if (!cxx) return nb::none();

    const char* type_name = cxx->type_name();

    // Dispatch to specific derived type for proper Python binding
    if (type_name && strcmp(type_name, "CameraComponent") == 0) {
        return nb::cast(static_cast<CameraComponent*>(cxx), nb::rv_policy::reference);
    } else {
        // Fallback to base CxxComponent
        return nb::cast(cxx, nb::rv_policy::reference);
    }
}

// Convert tc_component to Python object
// For Python-native components: returns body directly
// For C++-native components: creates Python binding wrapper
inline nb::object tc_component_to_python(tc_component* c) {
    if (!c) return nb::none();

    // Check if component is native Python - return body directly
    if (c->native_language == TC_LANGUAGE_PYTHON) {
        if (!c->body) return nb::none();
        return nb::borrow<nb::object>(reinterpret_cast<PyObject*>(c->body));
    }

    // Component is native C++ - create Python binding wrapper
    if (c->kind == TC_NATIVE_COMPONENT) {
        CxxComponent* cxx = CxxComponent::from_tc(c);
        if (!cxx) return nb::none();
        return component_to_python(cxx);
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
