#include <termin/openxr/openxr_runtime.hpp>

#include "openxr_android_runtime_internal.hpp"

namespace termin::openxr {

    OpenXRAndroidStartResult start_android_color_smoke(void* java_vm, void* activity_or_context) {
        return start_android_scene_smoke(java_vm, activity_or_context, nullptr);
    }

    OpenXRAndroidStartResult
    start_android_scene_smoke(void* java_vm, void* activity_or_context, const char* asset_root) {
        OpenXRAndroidStartConfig config;
        config.asset_root = asset_root;
        return detail::start_android_scene_smoke_internal(java_vm, activity_or_context, config);
    }

    OpenXRAndroidStartResult
    start_android_scene_smoke(void* java_vm, void* activity_or_context, const OpenXRAndroidStartConfig& config) {
        return detail::start_android_scene_smoke_internal(java_vm, activity_or_context, config);
    }

    void stop_android_color_smoke() {
        detail::stop_android_color_smoke_internal();
    }

} // namespace termin::openxr
