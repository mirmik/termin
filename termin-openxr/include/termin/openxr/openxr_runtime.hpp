#pragma once

#include <cstdint>

#include "termin/openxr/termin_openxr_api.h"

namespace termin::openxr {

struct OpenXRBuildInfo {
    bool has_openxr_headers = false;
    uint16_t api_version_major = 0;
    uint16_t api_version_minor = 0;
    uint32_t api_version_patch = 0;
    const char* android_create_instance_extension = "";
    const char* vulkan_enable_extension = "";
    const char* vulkan_enable2_extension = "";
};

TERMIN_OPENXR_API OpenXRBuildInfo build_info();
TERMIN_OPENXR_API const char* runtime_intent();

} // namespace termin::openxr
