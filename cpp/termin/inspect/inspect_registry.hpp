// inspect_registry.hpp - InspectRegistry for field introspection
//
// This file now wraps the C core implementation (tc_inspect).
// For migration details, see core_c/include/tc_inspect.hpp
//
#pragma once

// Enable trent compatibility
#define TC_HAS_TRENT
#include "../../trent/trent.h"

// Include the new implementation
#include "../../../core_c/include/tc_inspect.hpp"
#include "../../../core_c/include/inspect_registry_compat.hpp"

// DLL export/import macros for Windows (kept for compatibility)
#ifdef _WIN32
    #ifdef ENTITY_LIB_EXPORTS
        #define ENTITY_API __declspec(dllexport)
    #else
        #define ENTITY_API __declspec(dllimport)
    #endif
#else
    #define ENTITY_API
#endif

namespace termin {

// Forward declaration for CxxComponent (kept for compatibility)
class CxxComponent;

// The new InspectRegistry is imported via inspect_registry_compat.hpp
// All types (EnumChoice, InspectFieldInfo, KindHandler, InspectRegistry)
// and macros (INSPECT_FIELD, INSPECT_FIELD_CALLBACK) are available.

// Additional compatibility: provide old-style trent methods on InspectRegistry
// These are kept inline for header-only compatibility

namespace compat {

// py_to_trent - convert Python object to trent
inline nos::trent py_to_trent(py::object obj) {
    return tc::py_to_trent_compat(obj);
}

// trent_to_py - convert trent to Python object
inline py::object trent_to_py(const nos::trent& t) {
    return tc::trent_to_py_compat(t);
}

// py_dict_to_trent - convert Python dict to trent dict
inline nos::trent py_dict_to_trent(py::dict d) {
    return py_to_trent(d);
}

// trent_to_py_dict - convert trent dict to Python dict
inline py::dict trent_to_py_dict(const nos::trent& t) {
    py::object result = trent_to_py(t);
    if (py::isinstance<py::dict>(result)) {
        return result.cast<py::dict>();
    }
    return py::dict();
}

// py_list_to_trent - convert Python list to trent list
inline nos::trent py_list_to_trent(py::list lst) {
    return py_to_trent(lst);
}

} // namespace compat

} // namespace termin
