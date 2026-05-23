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
    const char* opengles_enable_extension = "";
};

struct OpenXRAndroidProbeResult {
    bool loader_loaded = false;
    bool loader_initialized = false;
    bool instance_created = false;
    bool system_found = false;
    int32_t last_result = 0;
    const char* stage = "";
    const char* detail = "";
};

struct OpenXRAndroidStartResult {
    bool started = false;
    const char* stage = "";
    const char* detail = "";
};

TERMIN_OPENXR_API OpenXRBuildInfo build_info();
TERMIN_OPENXR_API const char* runtime_intent();
TERMIN_OPENXR_API OpenXRAndroidProbeResult probe_android_runtime(void* java_vm, void* activity_or_context);
TERMIN_OPENXR_API OpenXRAndroidStartResult start_android_color_smoke(void* java_vm, void* activity_or_context);
TERMIN_OPENXR_API OpenXRAndroidStartResult start_android_scene_smoke(
    void* java_vm,
    void* activity_or_context,
    const char* asset_root
);
TERMIN_OPENXR_API void stop_android_color_smoke();

} // namespace termin::openxr
