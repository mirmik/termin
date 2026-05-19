#include "termin/openxr/openxr_runtime.hpp"

#if defined(TERMIN_OPENXR_HAS_HEADERS)
#  if defined(__ANDROID__)
#    include <jni.h>
#    define XR_USE_PLATFORM_ANDROID
#  endif
#  define XR_USE_GRAPHICS_API_VULKAN
#  include <vulkan/vulkan.h>
#  include <openxr/openxr.h>
#  include <openxr/openxr_platform.h>
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
#endif
    return info;
}

const char* runtime_intent() {
    return "Quest/OpenXR runtime integration placeholder: create XrInstance/XrSession, render into XR swapchains, then submit with xrEndFrame.";
}

} // namespace termin::openxr
