// entity_helpers.hpp - Common helpers for entity bindings
#pragma once

#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>

#include "termin/entity/entity.hpp"
#include "termin/geom/vec3.hpp"
#include "termin/geom/quat.hpp"
#include "trent/trent.h"

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
// trent <-> Python conversion
// ============================================================================

inline nos::trent py_to_trent(nb::object obj) {
    if (obj.is_none()) {
        return nos::trent::nil();
    }
    if (nb::isinstance<nb::bool_>(obj)) {
        return nos::trent(nb::cast<bool>(obj));
    }
    if (nb::isinstance<nb::int_>(obj)) {
        return nos::trent(nb::cast<int64_t>(obj));
    }
    if (nb::isinstance<nb::float_>(obj)) {
        return nos::trent(nb::cast<double>(obj));
    }
    if (nb::isinstance<nb::str>(obj)) {
        return nos::trent(nb::cast<std::string>(obj));
    }
    if (nb::isinstance<nb::list>(obj)) {
        nos::trent result;
        result.init(nos::trent_type::list);
        for (auto item : obj) {
            result.as_list().push_back(py_to_trent(nb::borrow<nb::object>(item)));
        }
        return result;
    }
    if (nb::isinstance<nb::dict>(obj)) {
        nos::trent result;
        result.init(nos::trent_type::dict);
        for (auto item : nb::cast<nb::dict>(obj)) {
            std::string key = nb::cast<std::string>(item.first);
            result[key] = py_to_trent(nb::borrow<nb::object>(item.second));
        }
        return result;
    }
    return nos::trent::nil();
}

inline nb::object trent_to_py(const nos::trent& t) {
    switch (t.get_type()) {
        case nos::trent_type::nil:
            return nb::none();
        case nos::trent_type::boolean:
            return nb::bool_(t.as_bool());
        case nos::trent_type::numer: {
            double val = t.as_numer();
            if (val == static_cast<int64_t>(val)) {
                return nb::int_(static_cast<int64_t>(val));
            }
            return nb::float_(val);
        }
        case nos::trent_type::string:
            return nb::str(t.as_string().c_str());
        case nos::trent_type::list: {
            nb::list result;
            for (const auto& item : t.as_list()) {
                result.append(trent_to_py(item));
            }
            return result;
        }
        case nos::trent_type::dict: {
            nb::dict result;
            for (const auto& [key, val] : t.as_dict()) {
                result[nb::str(key.c_str())] = trent_to_py(val);
            }
            return result;
        }
    }
    return nb::none();
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
