// tc_kind_instance.cpp - KindRegistry singleton
// This file must be compiled into entity_lib to ensure single instance across all modules

#include "../include/tc_kind.hpp"

namespace tc {

KindRegistry& KindRegistry::instance() {
    static KindRegistry reg;
    return reg;
}

} // namespace tc
