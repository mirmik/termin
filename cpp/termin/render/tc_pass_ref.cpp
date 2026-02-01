// tc_pass_ref.cpp - TcPassRef methods implementation
#include "tc_pass.hpp"
#include "frame_pass.hpp"

extern "C" {
#include "tc_inspect.h"
}

namespace termin {

void* TcPassRef::object_ptr() const {
    if (!_c) return nullptr;

    if (_c->kind == TC_NATIVE_PASS) {
        return CxxFramePass::from_tc(_c);
    } else {
        // External pass (Python) - body is the Python object
        return _c->body;
    }
}

bool TcPassRef::set_field(const std::string& field_name, const tc_value& value) {
    if (!_c) return false;

    const char* type = tc_pass_type_name(_c);
    if (!type) return false;

    // Check if field exists in registry before setting
    tc_field_info info;
    if (!tc_inspect_find_field_info(type, field_name.c_str(), &info)) {
        // Field not registered - silently skip (not all params are INSPECT_FIELDs)
        return false;
    }

    // tc_pass_inspect_set handles both C++ and Python passes via InspectRegistry::set_tc_value
    tc_pass_inspect_set(_c, field_name.c_str(), value, TC_SCENE_HANDLE_INVALID);
    return true;
}

} // namespace termin
