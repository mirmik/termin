// entity_helpers.hpp - Common helpers for entity bindings
#pragma once

#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>

#include "termin/entity/entity.hpp"
#include "termin/geom/vec3.hpp"
#include "termin/geom/quat.hpp"
#include "termin/bindings/tc_value_helpers.hpp"

namespace nb = nanobind;

namespace termin {

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
