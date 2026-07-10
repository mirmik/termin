#pragma once

#include <string>

#include "termin_modules/native_module_abi.h"
#include "termin_modules/termin_modules_api.hpp"

namespace termin_modules {

struct NativeModuleValidationResult {
    bool compatible = false;
    std::string error;
};

TERMIN_MODULES_API termin_native_module_host_v1 make_native_module_host_v1(
    const char* module_id,
    void* host_context = nullptr
);

TERMIN_MODULES_API NativeModuleValidationResult validate_native_module_descriptor_v1(
    const termin_native_module_descriptor_v1_data* descriptor,
    const std::string& expected_module_id = {}
);

} // namespace termin_modules
