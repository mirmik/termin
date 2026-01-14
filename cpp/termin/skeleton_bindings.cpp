// Skeleton bindings - now mostly in _skeleton_native module.
// This file kept for API compatibility (bind_skeleton function).

#include <nanobind/nanobind.h>
#include "skeleton_bindings.hpp"

namespace nb = nanobind;

namespace termin {

void bind_skeleton(nb::module_& m) {
    // skeleton_handle kind is now registered in _skeleton_native module
    // This function is kept for compatibility but does nothing
}

} // namespace termin
