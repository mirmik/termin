// tc_kind_python_instance.cpp - KindRegistryPython and KindRegistry singleton implementation
// Compiled into entity_lib to ensure single instance across all modules

#include "tc_kind_python.hpp"

namespace tc {

// Global callback for lazy list handler creation
// Set by inspect_bindings.cpp at Python module init
EnsureListHandlerFn g_ensure_list_handler = nullptr;

KindRegistryPython& KindRegistryPython::instance() {
    static KindRegistryPython inst;
    return inst;
}

KindRegistry& KindRegistry::instance() {
    static KindRegistry inst;
    return inst;
}

} // namespace tc
