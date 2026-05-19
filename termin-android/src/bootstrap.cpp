#include "termin/android/bootstrap.h"

#include <mutex>
#include <memory>
#include <string>
#include <stdexcept>
#include <cstdarg>

#ifdef __ANDROID__
#include <android/log.h>
#endif

#include <tcbase/tc_log.h>
#include <tgfx2/tc_shader_bridge.hpp>

#ifdef __ANDROID__
#ifndef VK_USE_PLATFORM_ANDROID_KHR
#define VK_USE_PLATFORM_ANDROID_KHR
#endif
#include <vulkan/vulkan.h>
#include <vulkan/vulkan_android.h>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/vulkan/vulkan_render_device.hpp>
#include <tgfx2/vulkan/vulkan_swapchain.hpp>
#endif

namespace {

struct AndroidBootstrapState {
    std::string app_data_dir;
    std::string asset_root;
    std::string native_lib_dir;
    ANativeWindow* window = nullptr;
    int32_t surface_width = 0;
    int32_t surface_height = 0;
    bool initialized = false;
#ifdef __ANDROID__
    std::unique_ptr<tgfx::VulkanRenderDevice> smoke_device;
    uint32_t smoke_width = 0;
    uint32_t smoke_height = 0;
    uint32_t smoke_frame = 0;
    bool smoke_create_failed = false;
#endif
};

std::mutex g_state_mutex;
AndroidBootstrapState g_state;

#ifdef __ANDROID__
constexpr const char* kAndroidLogTag = "TerminAndroid";

void android_log_info(const char* fmt, ...) {
    va_list args;
    va_start(args, fmt);
    __android_log_vprint(ANDROID_LOG_INFO, kAndroidLogTag, fmt, args);
    va_end(args);
}

void android_log_error(const char* fmt, ...) {
    va_list args;
    va_start(args, fmt);
    __android_log_vprint(ANDROID_LOG_ERROR, kAndroidLogTag, fmt, args);
    va_end(args);
}
#else
void android_log_info(const char*, ...) {}
void android_log_error(const char*, ...) {}
#endif

void destroy_smoke_renderer_locked() {
#ifdef __ANDROID__
    if (g_state.smoke_device) {
        android_log_info("smoke: destroy renderer");
        try {
            g_state.smoke_device->wait_idle();
        } catch (const std::exception& e) {
            android_log_error("smoke: destroy failed: %s", e.what());
            tc_log_error("termin_android_smoke: destroy failed: %s", e.what());
        }
    }
    g_state.smoke_device.reset();
    g_state.smoke_width = 0;
    g_state.smoke_height = 0;
    g_state.smoke_frame = 0;
#endif
}

void release_window_locked() {
    destroy_smoke_renderer_locked();
#ifdef __ANDROID__
    if (g_state.window) {
        ANativeWindow_release(g_state.window);
    }
#endif
    g_state.window = nullptr;
    g_state.surface_width = 0;
    g_state.surface_height = 0;
#ifdef __ANDROID__
    g_state.smoke_create_failed = false;
#endif
}

#ifdef __ANDROID__
bool create_smoke_renderer_locked() {
    if (g_state.smoke_create_failed) {
        android_log_info("smoke: create skipped after earlier failure on this surface");
        return false;
    }
    if (!g_state.window) {
        android_log_error("smoke: cannot create renderer without ANativeWindow");
        tc_log_error("termin_android_smoke: cannot create renderer without ANativeWindow");
        return false;
    }
    if (g_state.surface_width <= 0 || g_state.surface_height <= 0) {
        android_log_error(
            "smoke: invalid surface size %dx%d",
            static_cast<int>(g_state.surface_width),
            static_cast<int>(g_state.surface_height)
        );
        tc_log_error(
            "termin_android_smoke: invalid surface size %dx%d",
            static_cast<int>(g_state.surface_width),
            static_cast<int>(g_state.surface_height)
        );
        return false;
    }

    destroy_smoke_renderer_locked();

    try {
        android_log_info(
            "smoke: create Vulkan renderer for surface=%p size=%dx%d",
            static_cast<void*>(g_state.window),
            static_cast<int>(g_state.surface_width),
            static_cast<int>(g_state.surface_height)
        );
        tgfx::VulkanDeviceCreateInfo info{};
        info.enable_validation = false;
        info.instance_extensions = {
            VK_KHR_SURFACE_EXTENSION_NAME,
            VK_KHR_ANDROID_SURFACE_EXTENSION_NAME,
        };
        info.swapchain_width = static_cast<uint32_t>(g_state.surface_width);
        info.swapchain_height = static_cast<uint32_t>(g_state.surface_height);
        ANativeWindow* window = g_state.window;
        info.surface_factory = [window](VkInstance instance) -> VkSurfaceKHR {
            VkAndroidSurfaceCreateInfoKHR ci{};
            ci.sType = VK_STRUCTURE_TYPE_ANDROID_SURFACE_CREATE_INFO_KHR;
            ci.window = window;
            VkSurfaceKHR surface = VK_NULL_HANDLE;
            VkResult result = vkCreateAndroidSurfaceKHR(instance, &ci, nullptr, &surface);
            if (result != VK_SUCCESS) {
                android_log_error(
                    "smoke: vkCreateAndroidSurfaceKHR failed result=%d",
                    static_cast<int>(result)
                );
                tc_log_error(
                    "termin_android_smoke: vkCreateAndroidSurfaceKHR failed result=%d",
                    static_cast<int>(result)
                );
                return VK_NULL_HANDLE;
            }
            return surface;
        };

        g_state.smoke_device = std::make_unique<tgfx::VulkanRenderDevice>(info);

        g_state.smoke_width = g_state.smoke_device->swapchain()->width();
        g_state.smoke_height = g_state.smoke_device->swapchain()->height();

        android_log_info(
            "smoke: Vulkan renderer created swapchain=%ux%u images=%u",
            g_state.smoke_width,
            g_state.smoke_height,
            g_state.smoke_device->swapchain()->image_count()
        );
        tc_log_info(
            "termin_android_smoke: Vulkan renderer created swapchain=%ux%u images=%u",
            g_state.smoke_width,
            g_state.smoke_height,
            g_state.smoke_device->swapchain()->image_count()
        );
        return true;
    } catch (const std::exception& e) {
        android_log_error("smoke: create failed: %s", e.what());
        tc_log_error("termin_android_smoke: create failed: %s", e.what());
        destroy_smoke_renderer_locked();
        g_state.smoke_create_failed = true;
        return false;
    }
}

int render_smoke_frame_locked() {
    if (!g_state.smoke_device) {
        if (!create_smoke_renderer_locked()) {
            return 0;
        }
    }
    if (!g_state.smoke_device || !g_state.smoke_device->swapchain()) {
        android_log_error("smoke: renderer is not ready");
        tc_log_error("termin_android_smoke: renderer is not ready");
        return 0;
    }

    try {
        const uint32_t phase = g_state.smoke_frame % 3;
        const float r = phase == 0 ? 1.0f : 0.0f;
        const float g = phase == 1 ? 1.0f : 0.0f;
        const float b = phase == 2 ? 1.0f : 0.0f;
        bool recreate = g_state.smoke_device->swapchain()->clear_and_present(r, g, b, 1.0f);
        ++g_state.smoke_frame;
        android_log_info(
            "smoke: rendered frame=%u color=(%.2f, %.2f, %.2f) recreate=%d",
            g_state.smoke_frame,
            r, g, b,
            recreate ? 1 : 0
        );
        tc_log_info(
            "termin_android_smoke: rendered frame=%u color=(%.2f, %.2f, %.2f) recreate=%d",
            g_state.smoke_frame,
            r, g, b,
            recreate ? 1 : 0
        );
        if (recreate) {
            destroy_smoke_renderer_locked();
        }
        return 1;
    } catch (const std::exception& e) {
        android_log_error("smoke: render failed: %s", e.what());
        tc_log_error("termin_android_smoke: render failed: %s", e.what());
        destroy_smoke_renderer_locked();
        return 0;
    }
}
#endif

} // namespace

extern "C" int termin_android_initialize(const termin_android_config* config) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    if (!config) {
        android_log_error("initialize: config is NULL");
        tc_log_error("termin_android_initialize: config is NULL");
        return 0;
    }

    g_state.app_data_dir = config->app_data_dir ? config->app_data_dir : "";
    g_state.asset_root = config->asset_root ? config->asset_root : "";
    g_state.native_lib_dir = config->native_lib_dir ? config->native_lib_dir : "";
    g_state.initialized = true;

    if (!g_state.asset_root.empty()) {
        termin::tgfx2_set_shader_artifact_root(g_state.asset_root.c_str());
    }

    android_log_info(
        "initialize: app_data_dir='%s', asset_root='%s', native_lib_dir='%s'",
        g_state.app_data_dir.c_str(),
        g_state.asset_root.c_str(),
        g_state.native_lib_dir.c_str()
    );
    tc_log_info(
        "termin_android_initialize: app_data_dir='%s', asset_root='%s', native_lib_dir='%s'",
        g_state.app_data_dir.c_str(),
        g_state.asset_root.c_str(),
        g_state.native_lib_dir.c_str()
    );
    return 1;
}

extern "C" void termin_android_shutdown(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    release_window_locked();
    g_state.app_data_dir.clear();
    g_state.asset_root.clear();
    g_state.native_lib_dir.clear();
    g_state.initialized = false;
    termin::tgfx2_set_shader_artifact_root(nullptr);
    android_log_info("shutdown");
    tc_log_info("termin_android_shutdown");
}

extern "C" void termin_android_set_shader_artifact_root(const char* root) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    g_state.asset_root = root ? root : "";
    termin::tgfx2_set_shader_artifact_root(g_state.asset_root.c_str());
    tc_log_info("termin_android_set_shader_artifact_root: '%s'", g_state.asset_root.c_str());
}

extern "C" const char* termin_android_get_shader_artifact_root(void) {
    return termin::tgfx2_get_shader_artifact_root();
}

extern "C" void termin_android_on_surface_created(ANativeWindow* window) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    release_window_locked();
    if (!window) {
        android_log_error("surface_created: window is NULL");
        tc_log_error("termin_android_on_surface_created: window is NULL");
        return;
    }

#ifdef __ANDROID__
    ANativeWindow_acquire(window);
    g_state.surface_width = ANativeWindow_getWidth(window);
    g_state.surface_height = ANativeWindow_getHeight(window);
#endif
    g_state.window = window;
#ifdef __ANDROID__
    g_state.smoke_create_failed = false;
#endif
    android_log_info(
        "surface_created: window=%p size=%dx%d; waiting for surfaceChanged before render",
        static_cast<void*>(window),
        static_cast<int>(g_state.surface_width),
        static_cast<int>(g_state.surface_height)
    );
    tc_log_info(
        "termin_android_on_surface_created: window=%p size=%dx%d",
        static_cast<void*>(window),
        static_cast<int>(g_state.surface_width),
        static_cast<int>(g_state.surface_height)
    );
}

extern "C" void termin_android_on_surface_changed(int32_t width, int32_t height) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    bool size_changed = g_state.surface_width != width || g_state.surface_height != height;
    g_state.surface_width = width;
    g_state.surface_height = height;
    android_log_info(
        "surface_changed: size=%dx%d size_changed=%d",
        static_cast<int>(width),
        static_cast<int>(height),
        size_changed ? 1 : 0
    );
    tc_log_info(
        "termin_android_on_surface_changed: size=%dx%d",
        static_cast<int>(width),
        static_cast<int>(height)
    );
    if (size_changed) {
        destroy_smoke_renderer_locked();
    }
    render_smoke_frame_locked();
}

extern "C" void termin_android_on_surface_destroyed(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    release_window_locked();
    android_log_info("surface_destroyed");
    tc_log_info("termin_android_on_surface_destroyed");
}

extern "C" int termin_android_smoke_render(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
#ifdef __ANDROID__
    android_log_info("smoke_render requested");
    return render_smoke_frame_locked();
#else
    tc_log_error("termin_android_smoke_render: only supported on Android");
    return 0;
#endif
}

extern "C" ANativeWindow* termin_android_native_window(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    return g_state.window;
}

extern "C" int32_t termin_android_surface_width(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    return g_state.surface_width;
}

extern "C" int32_t termin_android_surface_height(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    return g_state.surface_height;
}
