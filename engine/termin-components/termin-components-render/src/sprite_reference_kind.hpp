#pragma once

#include <inspect/tc_kind_cpp.hpp>

namespace termin {
    // The inspector edits a UUID string. The component's scene serializer adds
    // the resource kind/role envelope used for package dependency discovery.
    inline void register_sprite_reference_kind(const char* name) {
        auto& kinds = tc::KindRegistryCpp::instance();
        if (!kinds.has(name)) {
            const auto* string_kind = kinds.get("string");
            kinds.register_kind(name, string_kind->serialize, string_kind->deserialize);
        }
    }
} // namespace termin
