// soa_type.hpp - SOA_COMPONENT macro for registering SoA data components
//
// Usage:
//   struct Velocity {
//       float dx = 0.0f;
//       float dy = 0.0f;
//       float dz = 0.0f;
//   };
//   SOA_COMPONENT(Velocity);
//
// The macro registers the type in the global SoA registry at static init time.
// Use termin::SoaTypeId<T>::id to get the type id after registration.
#pragma once

#include <new>
#include <type_traits>

extern "C" {
#include "core/tc_archetype.h"
}

namespace termin {

// Maps C++ type to tc_soa_type_id. Filled by SoaRegistrar at static init.
template<typename T>
struct SoaTypeId {
    static tc_soa_type_id id;
};

// Static registrar — constructed at static init time, registers type in global registry.
template<typename T>
struct SoaRegistrar {
    SoaRegistrar(const char* name) {
        tc_soa_type_desc desc = {};
        desc.name = name;
        desc.element_size = sizeof(T);
        desc.alignment = alignof(T);
        if constexpr (!std::is_trivially_default_constructible_v<T>) {
            desc.init = [](void* ptr) { new (ptr) T(); };
        }
        if constexpr (!std::is_trivially_destructible_v<T>) {
            desc.destroy = [](void* ptr) { static_cast<T*>(ptr)->~T(); };
        }
        SoaTypeId<T>::id = tc_soa_register_type(tc_soa_global_registry(), &desc);
    }
};

} // namespace termin

// Place after struct definition at global scope (outside any namespace).
// Registers the type in the global SoA type registry at static init time.
// Safe to include in multiple translation units (dedup by name in registry).
#define SOA_COMPONENT(T) \
    template<> inline tc_soa_type_id termin::SoaTypeId<T>::id = TC_SOA_TYPE_INVALID; \
    static termin::SoaRegistrar<T> _soa_reg_##T(#T)
