// tc_kind_python_instance.cpp - KindRegistryPython and KindRegistry singleton implementation
// Compiled into entity_lib to ensure single instance across all modules

#include "tc_kind_python.hpp"

namespace tc {

KindRegistryPython& KindRegistryPython::instance() {
    static KindRegistryPython inst;
    return inst;
}

KindRegistry& KindRegistry::instance() {
    static KindRegistry inst;
    return inst;
}

} // namespace tc
