#include "termin/openxr/openxr_runtime.hpp"

#if defined(TERMIN_OPENXR_HAS_HEADERS)
#  if defined(__ANDROID__)
#    include <jni.h>
#    define XR_USE_PLATFORM_ANDROID
#    include <dlfcn.h>
#  endif
#  define XR_USE_GRAPHICS_API_VULKAN
#  include <vulkan/vulkan.h>
#  include <openxr/openxr.h>
#  include <openxr/openxr_platform.h>
#endif

#include <cstring>
#include <atomic>
#include <array>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <memory>
#include <mutex>
#include <span>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.h>
#include <tcbase/trent/json.h>
#include <components/mesh_component.hpp>
#include <termin/engine/engine_core.hpp>
#include <termin/entity/entity.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/geom/mat44.hpp>
#include <termin/geom/vec3.hpp>
#include <termin/lighting/light_component.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/render/graph_compiler.hpp>
#include <termin/render/mesh_renderer.hpp>
#include <termin/render/render_engine.hpp>
#include <termin/render/render_pipeline.hpp>
#include <termin/render/rendering_manager.hpp>
#include <termin/runtime/runtime_package.hpp>
#include <termin/tc_scene.hpp>
#include <termin/input/xr_input.hpp>
#include <termin/xr/xr_origin_component.hpp>
#include <termin/xr/xr_thumbstick_locomotion_component.hpp>
#include <termin_collision/termin_collision.h>
#include <tgfx/tgfx_mesh_handle.hpp>
#include <tgfx/tgfx2_interop.h>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/i_command_list.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/render_state.hpp>
#include <tgfx2/vulkan/vulkan_render_device.hpp>

#include "openxr_math.hpp"

extern "C" {
void tc_inspect_kind_core_init(void);
#  include <core/tc_component.h>
#  include <core/tc_entity_pool.h>
#  include <core/tc_entity_pool_registry.h>
#  include <core/tc_scene_render_mount.h>
#  include <core/tc_scene_render_state.h>
#  include <inspect/tc_inspect_pass_adapter.h>
#  include <render/tc_pass.h>
#  include <render/tc_pipeline.h>
#  include <render/tc_render_target.h>
#  include <termin_scene/termin_scene.h>
#  include <tgfx/resources/tc_mesh_registry.h>
#  include <tgfx/resources/tc_primitive_mesh.h>
}

#if defined(__ANDROID__)
#  include <android/log.h>
#endif

namespace termin::openxr {


OpenXRBuildInfo build_info() {
    OpenXRBuildInfo info{};
#if defined(TERMIN_OPENXR_HAS_HEADERS)
    info.has_openxr_headers = true;
    info.api_version_major = XR_VERSION_MAJOR(XR_CURRENT_API_VERSION);
    info.api_version_minor = XR_VERSION_MINOR(XR_CURRENT_API_VERSION);
    info.api_version_patch = XR_VERSION_PATCH(XR_CURRENT_API_VERSION);
#  if defined(XR_KHR_ANDROID_CREATE_INSTANCE_EXTENSION_NAME)
    info.android_create_instance_extension = XR_KHR_ANDROID_CREATE_INSTANCE_EXTENSION_NAME;
#  endif
#  if defined(XR_KHR_VULKAN_ENABLE_EXTENSION_NAME)
    info.vulkan_enable_extension = XR_KHR_VULKAN_ENABLE_EXTENSION_NAME;
#  endif
#  if defined(XR_KHR_VULKAN_ENABLE2_EXTENSION_NAME)
    info.vulkan_enable2_extension = XR_KHR_VULKAN_ENABLE2_EXTENSION_NAME;
#  endif
#  if defined(XR_KHR_OPENGL_ES_ENABLE_EXTENSION_NAME)
    info.opengles_enable_extension = XR_KHR_OPENGL_ES_ENABLE_EXTENSION_NAME;
#  endif
#endif
    return info;
}

const char* runtime_intent() {
    return "Quest/OpenXR runtime integration placeholder: create XrInstance/XrSession, render into XR swapchains, then submit with xrEndFrame.";
}

OpenXRAndroidProbeResult probe_android_runtime(void* java_vm, void* activity_or_context) {
    OpenXRAndroidProbeResult result{};
    result.stage = "unsupported";
    result.detail = "OpenXR Android probe is only available in Android builds with OpenXR headers";

#if defined(TERMIN_OPENXR_HAS_HEADERS) && defined(__ANDROID__)
    result.stage = "dlopen";
    result.detail = "loading libopenxr_loader.so";

    void* loader = dlopen("libopenxr_loader.so", RTLD_NOW | RTLD_LOCAL);
    if (!loader) {
        result.detail = dlerror();
        return result;
    }
    result.loader_loaded = true;

    auto xr_get_instance_proc_addr = reinterpret_cast<PFN_xrGetInstanceProcAddr>(
        dlsym(loader, "xrGetInstanceProcAddr")
    );
    if (!xr_get_instance_proc_addr) {
        result.stage = "dlsym";
        result.detail = "xrGetInstanceProcAddr not found in libopenxr_loader.so";
        return result;
    }

    PFN_xrInitializeLoaderKHR xr_initialize_loader = nullptr;
    result.stage = "xrGetInstanceProcAddr:xrInitializeLoaderKHR";
    result.last_result = xr_get_instance_proc_addr(
        XR_NULL_HANDLE,
        "xrInitializeLoaderKHR",
        reinterpret_cast<PFN_xrVoidFunction*>(&xr_initialize_loader)
    );
    if (XR_FAILED(static_cast<XrResult>(result.last_result)) || !xr_initialize_loader) {
        result.detail = "xrInitializeLoaderKHR is unavailable";
        return result;
    }

    if (!java_vm || !activity_or_context) {
        result.stage = "loader init input";
        result.detail = "JavaVM or Android context/activity is null";
        return result;
    }

    XrLoaderInitInfoAndroidKHR loader_init{};
    loader_init.type = XR_TYPE_LOADER_INIT_INFO_ANDROID_KHR;
    loader_init.applicationVM = java_vm;
    loader_init.applicationContext = activity_or_context;

    result.stage = "xrInitializeLoaderKHR";
    result.last_result = xr_initialize_loader(
        reinterpret_cast<const XrLoaderInitInfoBaseHeaderKHR*>(&loader_init)
    );
    if (XR_FAILED(static_cast<XrResult>(result.last_result))) {
        result.detail = "xrInitializeLoaderKHR failed";
        return result;
    }
    result.loader_initialized = true;

    const char* enabled_extensions[] = {
        XR_KHR_ANDROID_CREATE_INSTANCE_EXTENSION_NAME,
    };

    XrInstanceCreateInfoAndroidKHR android_create_info{};
    android_create_info.type = XR_TYPE_INSTANCE_CREATE_INFO_ANDROID_KHR;
    android_create_info.applicationVM = java_vm;
    android_create_info.applicationActivity = activity_or_context;

    XrInstanceCreateInfo instance_create_info{};
    instance_create_info.type = XR_TYPE_INSTANCE_CREATE_INFO;
    instance_create_info.next = &android_create_info;
    std::strncpy(
        instance_create_info.applicationInfo.applicationName,
        "Termin Quest OpenXR Smoke",
        XR_MAX_APPLICATION_NAME_SIZE - 1
    );
    std::strncpy(
        instance_create_info.applicationInfo.engineName,
        "Termin",
        XR_MAX_ENGINE_NAME_SIZE - 1
    );
    instance_create_info.applicationInfo.applicationVersion = 1;
    instance_create_info.applicationInfo.engineVersion = 1;
    instance_create_info.applicationInfo.apiVersion = XR_CURRENT_API_VERSION;
    instance_create_info.enabledExtensionCount =
        static_cast<uint32_t>(sizeof(enabled_extensions) / sizeof(enabled_extensions[0]));
    instance_create_info.enabledExtensionNames = enabled_extensions;

    XrInstance instance = XR_NULL_HANDLE;
    PFN_xrCreateInstance xr_create_instance = nullptr;
    PFN_xrDestroyInstance xr_destroy_instance = nullptr;
    result.stage = "xrGetInstanceProcAddr:xrCreateInstance";
    result.last_result = xr_get_instance_proc_addr(
        XR_NULL_HANDLE,
        "xrCreateInstance",
        reinterpret_cast<PFN_xrVoidFunction*>(&xr_create_instance)
    );
    if (XR_FAILED(static_cast<XrResult>(result.last_result)) || !xr_create_instance) {
        result.detail = "xrCreateInstance is unavailable";
        return result;
    }

    result.stage = "xrCreateInstance";
    result.last_result = xr_create_instance(&instance_create_info, &instance);
    if (XR_FAILED(static_cast<XrResult>(result.last_result)) || instance == XR_NULL_HANDLE) {
        result.detail = "xrCreateInstance failed";
        return result;
    }
    result.instance_created = true;

    xr_get_instance_proc_addr(
        instance,
        "xrDestroyInstance",
        reinterpret_cast<PFN_xrVoidFunction*>(&xr_destroy_instance)
    );

    PFN_xrGetSystem xr_get_system = nullptr;
    result.stage = "xrGetInstanceProcAddr:xrGetSystem";
    result.last_result = xr_get_instance_proc_addr(
        instance,
        "xrGetSystem",
        reinterpret_cast<PFN_xrVoidFunction*>(&xr_get_system)
    );
    if (XR_SUCCEEDED(static_cast<XrResult>(result.last_result)) && xr_get_system) {
        XrSystemGetInfo system_info{};
        system_info.type = XR_TYPE_SYSTEM_GET_INFO;
        system_info.formFactor = XR_FORM_FACTOR_HEAD_MOUNTED_DISPLAY;

        XrSystemId system_id = XR_NULL_SYSTEM_ID;
        result.stage = "xrGetSystem";
        result.last_result = xr_get_system(instance, &system_info, &system_id);
        result.system_found =
            XR_SUCCEEDED(static_cast<XrResult>(result.last_result)) && system_id != XR_NULL_SYSTEM_ID;
        result.detail = result.system_found
            ? "OpenXR HMD system is available"
            : "xrGetSystem failed or returned XR_NULL_SYSTEM_ID";
    } else {
        result.detail = "xrGetSystem is unavailable";
    }

    if (xr_destroy_instance) {
        xr_destroy_instance(instance);
    }
    return result;
#endif

    return result;
}


} // namespace termin::openxr
