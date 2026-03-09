// tc_kind.hpp - Unified kind registry (combines C++ and Python)
// This is the main header for code that needs both C++ and Python support.
// For C++-only code, use tc_kind_cpp.hpp instead.
#pragma once

#include "termin/inspect/tc_kind_cpp_ext.hpp"
#include "inspect/tc_kind_python.hpp"

namespace tc {

// Register builtin kinds (both C++ and Python compatible)
inline void register_builtin_kinds() {
    register_builtin_cpp_kinds();
}

} // namespace tc
