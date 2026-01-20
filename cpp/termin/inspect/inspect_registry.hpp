// inspect_registry.hpp - InspectRegistry for field introspection
//
// This file now wraps the C core implementation (tc_inspect).
// For migration details, see core_c/include/tc_inspect.hpp
//
#pragma once

#include "../../trent/trent.h"
#include "../../../core_c/include/tc_inspect.hpp"
#include "../../../core_c/include/inspect_registry_compat.hpp"

#include "../export.hpp"

namespace termin {

// Forward declaration for CxxComponent (kept for compatibility)
class CxxComponent;

// The new InspectRegistry is imported via inspect_registry_compat.hpp
// All types (EnumChoice, InspectFieldInfo, InspectRegistry)
// and macros (INSPECT_FIELD, INSPECT_FIELD_CALLBACK) are available.

// Additional compatibility: provide old-style trent methods on InspectRegistry
// These are kept inline for header-only compatibility

namespace compat {

// nb_to_trent - convert Python object to trent
inline nos::trent nb_to_trent(nb::object obj) {
    return tc::nb_to_trent_compat(obj);
}

// trent_to_nb - convert trent to Python object
inline nb::object trent_to_nb(const nos::trent& t) {
    return tc::trent_to_nb_compat(t);
}

// nb_dict_to_trent - convert Python dict to trent dict
inline nos::trent nb_dict_to_trent(nb::dict d) {
    return nb_to_trent(d);
}

// trent_to_nb_dict - convert trent dict to Python dict
inline nb::dict trent_to_nb_dict(const nos::trent& t) {
    nb::object result = trent_to_nb(t);
    if (nb::isinstance<nb::dict>(result)) {
        return nb::cast<nb::dict>(result);
    }
    return nb::dict();
}

// nb_list_to_trent - convert Python list to trent list
inline nos::trent nb_list_to_trent(nb::list lst) {
    return nb_to_trent(lst);
}

} // namespace compat

} // namespace termin
