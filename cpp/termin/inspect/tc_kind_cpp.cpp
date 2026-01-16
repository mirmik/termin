// tc_kind_cpp.cpp - KindRegistryCpp singleton implementation
// Compiled into entity_lib to ensure single instance across all modules

#include "tc_kind_cpp.hpp"

namespace tc {

KindRegistryCpp& KindRegistryCpp::instance() {
    static KindRegistryCpp inst;
    return inst;
}

} // namespace tc
