// soa_bindings.cpp - SoA type registry bindings
#include <termin/bindings/soa_bindings.hpp>

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>

extern "C" {
#include "core/tc_archetype.h"
}

namespace nb = nanobind;

namespace termin {

void bind_soa_registry(nb::module_& m) {
    m.def("soa_registry_get_all_info", []() {
        nb::list result;
        tc_soa_type_registry* reg = tc_soa_global_registry();
        for (size_t i = 0; i < reg->count; i++) {
            nb::dict info;
            info["id"] = (int)i;
            info["name"] = reg->types[i].name ? reg->types[i].name : "(unnamed)";
            info["element_size"] = (int)reg->types[i].element_size;
            info["alignment"] = (int)reg->types[i].alignment;
            info["has_init"] = reg->types[i].init != nullptr;
            info["has_destroy"] = reg->types[i].destroy != nullptr;
            result.append(info);
        }
        return result;
    });

    m.def("soa_registry_type_count", []() {
        return (int)tc_soa_global_registry()->count;
    });
}

} // namespace termin
