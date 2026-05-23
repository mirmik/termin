#include "termin/openxr/openxr_runtime.hpp"

#if defined(TERMIN_OPENXR_HAS_HEADERS)
#  if defined(__ANDROID__)
#    include <jni.h>
#    define XR_USE_PLATFORM_ANDROID
#    define XR_USE_PLATFORM_EGL
#    include <dlfcn.h>
#  endif
#  define XR_USE_GRAPHICS_API_VULKAN
#  define XR_USE_GRAPHICS_API_OPENGL_ES
#  include <EGL/egl.h>
#  include <GLES3/gl3.h>
#  include <vulkan/vulkan.h>
#  include <openxr/openxr.h>
#  include <openxr/openxr_platform.h>
#endif

#include <cstring>
#include <atomic>
#include <chrono>
#include <thread>
#include <vector>

#if defined(__ANDROID__)
#  include <android/log.h>
#endif

namespace termin::openxr {

namespace {

#if defined(TERMIN_OPENXR_HAS_HEADERS) && defined(__ANDROID__)
constexpr const char* kLogTag = "TerminOpenXR";

void log_info(const char* message) {
    __android_log_print(ANDROID_LOG_INFO, kLogTag, "%s", message ? message : "");
}

void log_error(const char* stage, const char* detail) {
    __android_log_print(
        ANDROID_LOG_ERROR,
        kLogTag,
        "%s: %s",
        stage ? stage : "OpenXR smoke",
        detail ? detail : ""
    );
}

struct OpenXRDispatch {
    PFN_xrGetInstanceProcAddr get_instance_proc_addr = nullptr;
    PFN_xrInitializeLoaderKHR initialize_loader = nullptr;
    PFN_xrCreateInstance create_instance = nullptr;
    PFN_xrDestroyInstance destroy_instance = nullptr;
    PFN_xrGetSystem get_system = nullptr;
    PFN_xrCreateSession create_session = nullptr;
    PFN_xrDestroySession destroy_session = nullptr;
    PFN_xrCreateReferenceSpace create_reference_space = nullptr;
    PFN_xrDestroySpace destroy_space = nullptr;
    PFN_xrEnumerateViewConfigurationViews enumerate_view_configuration_views = nullptr;
    PFN_xrEnumerateEnvironmentBlendModes enumerate_environment_blend_modes = nullptr;
    PFN_xrEnumerateSwapchainFormats enumerate_swapchain_formats = nullptr;
    PFN_xrCreateSwapchain create_swapchain = nullptr;
    PFN_xrDestroySwapchain destroy_swapchain = nullptr;
    PFN_xrEnumerateSwapchainImages enumerate_swapchain_images = nullptr;
    PFN_xrAcquireSwapchainImage acquire_swapchain_image = nullptr;
    PFN_xrWaitSwapchainImage wait_swapchain_image = nullptr;
    PFN_xrReleaseSwapchainImage release_swapchain_image = nullptr;
    PFN_xrPollEvent poll_event = nullptr;
    PFN_xrBeginSession begin_session = nullptr;
    PFN_xrEndSession end_session = nullptr;
    PFN_xrWaitFrame wait_frame = nullptr;
    PFN_xrBeginFrame begin_frame = nullptr;
    PFN_xrEndFrame end_frame = nullptr;
    PFN_xrLocateViews locate_views = nullptr;
    PFN_xrGetOpenGLESGraphicsRequirementsKHR get_gles_requirements = nullptr;
};

struct EGLState {
    EGLDisplay display = EGL_NO_DISPLAY;
    EGLConfig config = nullptr;
    EGLContext context = EGL_NO_CONTEXT;
    EGLSurface surface = EGL_NO_SURFACE;
};

struct SmokeControl {
    std::atomic<bool> running{false};
    std::thread thread;
};

SmokeControl g_smoke;

bool load_instance_proc(
    const OpenXRDispatch& dispatch,
    XrInstance instance,
    const char* name,
    PFN_xrVoidFunction* out
) {
    XrResult result = dispatch.get_instance_proc_addr(instance, name, out);
    if (XR_FAILED(result) || !*out) {
        __android_log_print(
            ANDROID_LOG_ERROR,
            kLogTag,
            "xrGetInstanceProcAddr('%s') failed: %d",
            name,
            static_cast<int>(result)
        );
        return false;
    }
    return true;
}

bool init_egl(EGLState& egl) {
    egl.display = eglGetDisplay(EGL_DEFAULT_DISPLAY);
    if (egl.display == EGL_NO_DISPLAY) {
        log_error("EGL", "eglGetDisplay failed");
        return false;
    }
    if (!eglInitialize(egl.display, nullptr, nullptr)) {
        log_error("EGL", "eglInitialize failed");
        return false;
    }

    const EGLint config_attribs[] = {
        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT,
        EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
        EGL_RED_SIZE, 8,
        EGL_GREEN_SIZE, 8,
        EGL_BLUE_SIZE, 8,
        EGL_ALPHA_SIZE, 8,
        EGL_DEPTH_SIZE, 0,
        EGL_STENCIL_SIZE, 0,
        EGL_NONE
    };
    EGLint config_count = 0;
    if (!eglChooseConfig(egl.display, config_attribs, &egl.config, 1, &config_count) ||
        config_count < 1) {
        log_error("EGL", "eglChooseConfig failed");
        return false;
    }

    const EGLint context_attribs[] = {
        EGL_CONTEXT_CLIENT_VERSION, 3,
        EGL_NONE
    };
    egl.context = eglCreateContext(egl.display, egl.config, EGL_NO_CONTEXT, context_attribs);
    if (egl.context == EGL_NO_CONTEXT) {
        log_error("EGL", "eglCreateContext failed");
        return false;
    }

    const EGLint surface_attribs[] = {
        EGL_WIDTH, 16,
        EGL_HEIGHT, 16,
        EGL_NONE
    };
    egl.surface = eglCreatePbufferSurface(egl.display, egl.config, surface_attribs);
    if (egl.surface == EGL_NO_SURFACE) {
        log_error("EGL", "eglCreatePbufferSurface failed");
        return false;
    }
    if (!eglMakeCurrent(egl.display, egl.surface, egl.surface, egl.context)) {
        log_error("EGL", "eglMakeCurrent failed");
        return false;
    }
    return true;
}

void shutdown_egl(EGLState& egl) {
    if (egl.display != EGL_NO_DISPLAY) {
        eglMakeCurrent(egl.display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
        if (egl.context != EGL_NO_CONTEXT) {
            eglDestroyContext(egl.display, egl.context);
        }
        if (egl.surface != EGL_NO_SURFACE) {
            eglDestroySurface(egl.display, egl.surface);
        }
        eglTerminate(egl.display);
    }
    egl = {};
}

bool is_supported_format(int64_t format) {
    return format == GL_RGBA8 || format == GL_SRGB8_ALPHA8;
}

int64_t choose_swapchain_format(const std::vector<int64_t>& formats) {
    for (int64_t format : formats) {
        if (format == GL_RGBA8) {
            return format;
        }
    }
    for (int64_t format : formats) {
        if (is_supported_format(format)) {
            return format;
        }
    }
    return formats.empty() ? 0 : formats.front();
}

void smoke_thread_main(void* java_vm, void* activity_or_context) {
    log_info("OpenXR color smoke thread start");

    OpenXRDispatch xr{};
    void* loader = dlopen("libopenxr_loader.so", RTLD_NOW | RTLD_LOCAL);
    if (!loader) {
        log_error("dlopen", dlerror());
        g_smoke.running.store(false);
        return;
    }

    xr.get_instance_proc_addr = reinterpret_cast<PFN_xrGetInstanceProcAddr>(
        dlsym(loader, "xrGetInstanceProcAddr")
    );
    if (!xr.get_instance_proc_addr) {
        log_error("dlsym", "xrGetInstanceProcAddr not found");
        g_smoke.running.store(false);
        return;
    }

    if (!load_instance_proc(xr, XR_NULL_HANDLE, "xrInitializeLoaderKHR",
            reinterpret_cast<PFN_xrVoidFunction*>(&xr.initialize_loader))) {
        g_smoke.running.store(false);
        return;
    }

    XrLoaderInitInfoAndroidKHR loader_init{};
    loader_init.type = XR_TYPE_LOADER_INIT_INFO_ANDROID_KHR;
    loader_init.applicationVM = java_vm;
    loader_init.applicationContext = activity_or_context;
    XrResult result = xr.initialize_loader(
        reinterpret_cast<const XrLoaderInitInfoBaseHeaderKHR*>(&loader_init)
    );
    if (XR_FAILED(result)) {
        log_error("xrInitializeLoaderKHR", "loader initialization failed");
        g_smoke.running.store(false);
        return;
    }

    const char* enabled_extensions[] = {
        XR_KHR_ANDROID_CREATE_INSTANCE_EXTENSION_NAME,
        XR_KHR_OPENGL_ES_ENABLE_EXTENSION_NAME,
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
        "Termin OpenXR Color Smoke",
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

    if (!load_instance_proc(xr, XR_NULL_HANDLE, "xrCreateInstance",
            reinterpret_cast<PFN_xrVoidFunction*>(&xr.create_instance))) {
        g_smoke.running.store(false);
        return;
    }

    XrInstance instance = XR_NULL_HANDLE;
    result = xr.create_instance(&instance_create_info, &instance);
    if (XR_FAILED(result) || instance == XR_NULL_HANDLE) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrCreateInstance failed: %d", result);
        g_smoke.running.store(false);
        return;
    }

    load_instance_proc(xr, instance, "xrDestroyInstance", reinterpret_cast<PFN_xrVoidFunction*>(&xr.destroy_instance));
    load_instance_proc(xr, instance, "xrGetSystem", reinterpret_cast<PFN_xrVoidFunction*>(&xr.get_system));
    load_instance_proc(xr, instance, "xrCreateSession", reinterpret_cast<PFN_xrVoidFunction*>(&xr.create_session));
    load_instance_proc(xr, instance, "xrDestroySession", reinterpret_cast<PFN_xrVoidFunction*>(&xr.destroy_session));
    load_instance_proc(xr, instance, "xrCreateReferenceSpace", reinterpret_cast<PFN_xrVoidFunction*>(&xr.create_reference_space));
    load_instance_proc(xr, instance, "xrDestroySpace", reinterpret_cast<PFN_xrVoidFunction*>(&xr.destroy_space));
    load_instance_proc(xr, instance, "xrEnumerateViewConfigurationViews", reinterpret_cast<PFN_xrVoidFunction*>(&xr.enumerate_view_configuration_views));
    load_instance_proc(xr, instance, "xrEnumerateEnvironmentBlendModes", reinterpret_cast<PFN_xrVoidFunction*>(&xr.enumerate_environment_blend_modes));
    load_instance_proc(xr, instance, "xrEnumerateSwapchainFormats", reinterpret_cast<PFN_xrVoidFunction*>(&xr.enumerate_swapchain_formats));
    load_instance_proc(xr, instance, "xrCreateSwapchain", reinterpret_cast<PFN_xrVoidFunction*>(&xr.create_swapchain));
    load_instance_proc(xr, instance, "xrDestroySwapchain", reinterpret_cast<PFN_xrVoidFunction*>(&xr.destroy_swapchain));
    load_instance_proc(xr, instance, "xrEnumerateSwapchainImages", reinterpret_cast<PFN_xrVoidFunction*>(&xr.enumerate_swapchain_images));
    load_instance_proc(xr, instance, "xrAcquireSwapchainImage", reinterpret_cast<PFN_xrVoidFunction*>(&xr.acquire_swapchain_image));
    load_instance_proc(xr, instance, "xrWaitSwapchainImage", reinterpret_cast<PFN_xrVoidFunction*>(&xr.wait_swapchain_image));
    load_instance_proc(xr, instance, "xrReleaseSwapchainImage", reinterpret_cast<PFN_xrVoidFunction*>(&xr.release_swapchain_image));
    load_instance_proc(xr, instance, "xrPollEvent", reinterpret_cast<PFN_xrVoidFunction*>(&xr.poll_event));
    load_instance_proc(xr, instance, "xrBeginSession", reinterpret_cast<PFN_xrVoidFunction*>(&xr.begin_session));
    load_instance_proc(xr, instance, "xrEndSession", reinterpret_cast<PFN_xrVoidFunction*>(&xr.end_session));
    load_instance_proc(xr, instance, "xrWaitFrame", reinterpret_cast<PFN_xrVoidFunction*>(&xr.wait_frame));
    load_instance_proc(xr, instance, "xrBeginFrame", reinterpret_cast<PFN_xrVoidFunction*>(&xr.begin_frame));
    load_instance_proc(xr, instance, "xrEndFrame", reinterpret_cast<PFN_xrVoidFunction*>(&xr.end_frame));
    load_instance_proc(xr, instance, "xrLocateViews", reinterpret_cast<PFN_xrVoidFunction*>(&xr.locate_views));
    load_instance_proc(xr, instance, "xrGetOpenGLESGraphicsRequirementsKHR", reinterpret_cast<PFN_xrVoidFunction*>(&xr.get_gles_requirements));

    XrSystemGetInfo system_info{};
    system_info.type = XR_TYPE_SYSTEM_GET_INFO;
    system_info.formFactor = XR_FORM_FACTOR_HEAD_MOUNTED_DISPLAY;
    XrSystemId system_id = XR_NULL_SYSTEM_ID;
    result = xr.get_system(instance, &system_info, &system_id);
    if (XR_FAILED(result) || system_id == XR_NULL_SYSTEM_ID) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrGetSystem failed: %d", result);
        xr.destroy_instance(instance);
        g_smoke.running.store(false);
        return;
    }

    EGLState egl{};
    if (!init_egl(egl)) {
        xr.destroy_instance(instance);
        g_smoke.running.store(false);
        return;
    }

    XrGraphicsRequirementsOpenGLESKHR gles_requirements{};
    gles_requirements.type = XR_TYPE_GRAPHICS_REQUIREMENTS_OPENGL_ES_KHR;
    result = xr.get_gles_requirements(instance, system_id, &gles_requirements);
    if (XR_FAILED(result)) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrGetOpenGLESGraphicsRequirementsKHR failed: %d", result);
        shutdown_egl(egl);
        xr.destroy_instance(instance);
        g_smoke.running.store(false);
        return;
    }

    XrGraphicsBindingOpenGLESAndroidKHR graphics_binding{};
    graphics_binding.type = XR_TYPE_GRAPHICS_BINDING_OPENGL_ES_ANDROID_KHR;
    graphics_binding.display = egl.display;
    graphics_binding.config = egl.config;
    graphics_binding.context = egl.context;

    XrSessionCreateInfo session_create_info{};
    session_create_info.type = XR_TYPE_SESSION_CREATE_INFO;
    session_create_info.next = &graphics_binding;
    session_create_info.systemId = system_id;

    XrSession session = XR_NULL_HANDLE;
    result = xr.create_session(instance, &session_create_info, &session);
    if (XR_FAILED(result) || session == XR_NULL_HANDLE) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrCreateSession failed: %d", result);
        shutdown_egl(egl);
        xr.destroy_instance(instance);
        g_smoke.running.store(false);
        return;
    }

    XrReferenceSpaceCreateInfo space_create_info{};
    space_create_info.type = XR_TYPE_REFERENCE_SPACE_CREATE_INFO;
    space_create_info.referenceSpaceType = XR_REFERENCE_SPACE_TYPE_LOCAL;
    space_create_info.poseInReferenceSpace.orientation.w = 1.0f;
    XrSpace app_space = XR_NULL_HANDLE;
    result = xr.create_reference_space(session, &space_create_info, &app_space);
    if (XR_FAILED(result)) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrCreateReferenceSpace failed: %d", result);
    }

    uint32_t view_count = 0;
    xr.enumerate_view_configuration_views(instance, system_id, XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO, 0, &view_count, nullptr);
    std::vector<XrViewConfigurationView> view_configs(view_count);
    for (XrViewConfigurationView& view_config : view_configs) {
        view_config.type = XR_TYPE_VIEW_CONFIGURATION_VIEW;
    }
    xr.enumerate_view_configuration_views(
        instance,
        system_id,
        XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO,
        view_count,
        &view_count,
        view_configs.data()
    );
    if (view_count == 0) {
        log_error("OpenXR", "runtime returned zero primary stereo views");
        if (app_space != XR_NULL_HANDLE) {
            xr.destroy_space(app_space);
        }
        xr.destroy_session(session);
        shutdown_egl(egl);
        xr.destroy_instance(instance);
        g_smoke.running.store(false);
        return;
    }

    uint32_t blend_count = 0;
    xr.enumerate_environment_blend_modes(instance, system_id, XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO, 0, &blend_count, nullptr);
    std::vector<XrEnvironmentBlendMode> blend_modes(blend_count);
    xr.enumerate_environment_blend_modes(
        instance,
        system_id,
        XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO,
        blend_count,
        &blend_count,
        blend_modes.data()
    );
    XrEnvironmentBlendMode blend_mode = blend_count > 0 ? blend_modes[0] : XR_ENVIRONMENT_BLEND_MODE_OPAQUE;

    uint32_t format_count = 0;
    xr.enumerate_swapchain_formats(session, 0, &format_count, nullptr);
    std::vector<int64_t> formats(format_count);
    xr.enumerate_swapchain_formats(session, format_count, &format_count, formats.data());
    int64_t color_format = choose_swapchain_format(formats);
    __android_log_print(ANDROID_LOG_INFO, kLogTag, "OpenXR smoke color format: 0x%llx", static_cast<long long>(color_format));

    XrSwapchainCreateInfo swapchain_create_info{};
    swapchain_create_info.type = XR_TYPE_SWAPCHAIN_CREATE_INFO;
    swapchain_create_info.usageFlags = XR_SWAPCHAIN_USAGE_COLOR_ATTACHMENT_BIT;
    swapchain_create_info.format = color_format;
    swapchain_create_info.sampleCount = view_configs[0].recommendedSwapchainSampleCount;
    swapchain_create_info.width = view_configs[0].recommendedImageRectWidth;
    swapchain_create_info.height = view_configs[0].recommendedImageRectHeight;
    swapchain_create_info.faceCount = 1;
    swapchain_create_info.arraySize = view_count;
    swapchain_create_info.mipCount = 1;

    XrSwapchain color_swapchain = XR_NULL_HANDLE;
    result = xr.create_swapchain(session, &swapchain_create_info, &color_swapchain);
    if (XR_FAILED(result) || color_swapchain == XR_NULL_HANDLE) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrCreateSwapchain failed: %d", result);
        if (app_space != XR_NULL_HANDLE) {
            xr.destroy_space(app_space);
        }
        xr.destroy_session(session);
        shutdown_egl(egl);
        xr.destroy_instance(instance);
        g_smoke.running.store(false);
        return;
    }

    uint32_t image_count = 0;
    xr.enumerate_swapchain_images(color_swapchain, 0, &image_count, nullptr);
    std::vector<XrSwapchainImageOpenGLESKHR> images(image_count);
    for (XrSwapchainImageOpenGLESKHR& image : images) {
        image.type = XR_TYPE_SWAPCHAIN_IMAGE_OPENGL_ES_KHR;
    }
    xr.enumerate_swapchain_images(
        color_swapchain,
        image_count,
        &image_count,
        reinterpret_cast<XrSwapchainImageBaseHeader*>(images.data())
    );

    GLuint framebuffer = 0;
    glGenFramebuffers(1, &framebuffer);

    std::vector<XrView> views(view_count);
    for (XrView& view : views) {
        view.type = XR_TYPE_VIEW;
    }
    std::vector<XrCompositionLayerProjectionView> layer_views(view_count);
    for (XrCompositionLayerProjectionView& layer_view : layer_views) {
        layer_view.type = XR_TYPE_COMPOSITION_LAYER_PROJECTION_VIEW;
    }
    bool session_running = false;
    uint64_t frame_index = 0;

    log_info("OpenXR color smoke loop ready");
    while (g_smoke.running.load()) {
        XrEventDataBuffer event{};
        event.type = XR_TYPE_EVENT_DATA_BUFFER;
        while (xr.poll_event(instance, &event) == XR_SUCCESS) {
            if (event.type == XR_TYPE_EVENT_DATA_SESSION_STATE_CHANGED) {
                const auto* state_event = reinterpret_cast<const XrEventDataSessionStateChanged*>(&event);
                if (state_event->state == XR_SESSION_STATE_READY) {
                    XrSessionBeginInfo begin_info{};
                    begin_info.type = XR_TYPE_SESSION_BEGIN_INFO;
                    begin_info.primaryViewConfigurationType = XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO;
                    result = xr.begin_session(session, &begin_info);
                    session_running = XR_SUCCEEDED(result);
                    __android_log_print(ANDROID_LOG_INFO, kLogTag, "xrBeginSession result=%d", result);
                } else if (state_event->state == XR_SESSION_STATE_STOPPING) {
                    if (session_running) {
                        xr.end_session(session);
                    }
                    session_running = false;
                } else if (state_event->state == XR_SESSION_STATE_EXITING ||
                           state_event->state == XR_SESSION_STATE_LOSS_PENDING) {
                    g_smoke.running.store(false);
                }
            }
            event = {};
            event.type = XR_TYPE_EVENT_DATA_BUFFER;
        }

        if (!session_running || app_space == XR_NULL_HANDLE) {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            continue;
        }

        XrFrameWaitInfo wait_info{};
        wait_info.type = XR_TYPE_FRAME_WAIT_INFO;
        XrFrameState frame_state{};
        frame_state.type = XR_TYPE_FRAME_STATE;
        result = xr.wait_frame(session, &wait_info, &frame_state);
        if (XR_FAILED(result)) {
            __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrWaitFrame failed: %d", result);
            continue;
        }

        XrFrameBeginInfo begin_frame_info{};
        begin_frame_info.type = XR_TYPE_FRAME_BEGIN_INFO;
        xr.begin_frame(session, &begin_frame_info);

        XrCompositionLayerBaseHeader* layers[1] = {};
        uint32_t layer_count = 0;
        XrCompositionLayerProjection projection_layer{};
        projection_layer.type = XR_TYPE_COMPOSITION_LAYER_PROJECTION;
        projection_layer.space = app_space;
        projection_layer.viewCount = view_count;
        projection_layer.views = layer_views.data();

        if (frame_state.shouldRender) {
            XrViewLocateInfo locate_info{};
            locate_info.type = XR_TYPE_VIEW_LOCATE_INFO;
            locate_info.viewConfigurationType = XR_VIEW_CONFIGURATION_TYPE_PRIMARY_STEREO;
            locate_info.displayTime = frame_state.predictedDisplayTime;
            locate_info.space = app_space;
            XrViewState view_state{};
            view_state.type = XR_TYPE_VIEW_STATE;
            uint32_t located_view_count = 0;
            result = xr.locate_views(
                session,
                &locate_info,
                &view_state,
                view_count,
                &located_view_count,
                views.data()
            );
            if (XR_SUCCEEDED(result) && located_view_count == view_count) {
                uint32_t image_index = 0;
                XrSwapchainImageAcquireInfo acquire_info{};
                acquire_info.type = XR_TYPE_SWAPCHAIN_IMAGE_ACQUIRE_INFO;
                xr.acquire_swapchain_image(color_swapchain, &acquire_info, &image_index);

                XrSwapchainImageWaitInfo wait_swapchain_info{};
                wait_swapchain_info.type = XR_TYPE_SWAPCHAIN_IMAGE_WAIT_INFO;
                wait_swapchain_info.timeout = XR_INFINITE_DURATION;
                xr.wait_swapchain_image(color_swapchain, &wait_swapchain_info);

                glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);
                for (uint32_t eye = 0; eye < view_count; ++eye) {
                    glFramebufferTextureLayer(
                        GL_FRAMEBUFFER,
                        GL_COLOR_ATTACHMENT0,
                        images[image_index].image,
                        0,
                        static_cast<GLint>(eye)
                    );
                    glViewport(
                        0,
                        0,
                        static_cast<GLsizei>(swapchain_create_info.width),
                        static_cast<GLsizei>(swapchain_create_info.height)
                    );
                    const float phase = static_cast<float>((frame_index / 60 + eye) % 3);
                    glClearColor(phase == 0.0f ? 1.0f : 0.0f, phase == 1.0f ? 1.0f : 0.0f, phase == 2.0f ? 1.0f : 0.0f, 1.0f);
                    glClear(GL_COLOR_BUFFER_BIT);

                    layer_views[eye].pose = views[eye].pose;
                    layer_views[eye].fov = views[eye].fov;
                    layer_views[eye].subImage.swapchain = color_swapchain;
                    layer_views[eye].subImage.imageRect.offset = {0, 0};
                    layer_views[eye].subImage.imageRect.extent = {
                        static_cast<int32_t>(swapchain_create_info.width),
                        static_cast<int32_t>(swapchain_create_info.height)
                    };
                    layer_views[eye].subImage.imageArrayIndex = eye;
                }
                glBindFramebuffer(GL_FRAMEBUFFER, 0);
                glFlush();

                XrSwapchainImageReleaseInfo release_info{};
                release_info.type = XR_TYPE_SWAPCHAIN_IMAGE_RELEASE_INFO;
                xr.release_swapchain_image(color_swapchain, &release_info);

                layers[0] = reinterpret_cast<XrCompositionLayerBaseHeader*>(&projection_layer);
                layer_count = 1;
                ++frame_index;
            }
        }

        XrFrameEndInfo end_info{};
        end_info.type = XR_TYPE_FRAME_END_INFO;
        end_info.displayTime = frame_state.predictedDisplayTime;
        end_info.environmentBlendMode = blend_mode;
        end_info.layerCount = layer_count;
        end_info.layers = layer_count ? layers : nullptr;
        result = xr.end_frame(session, &end_info);
        if (XR_FAILED(result)) {
            __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrEndFrame failed: %d", result);
        }
    }

    if (session_running) {
        xr.end_session(session);
    }
    glDeleteFramebuffers(1, &framebuffer);
    xr.destroy_swapchain(color_swapchain);
    if (app_space != XR_NULL_HANDLE) {
        xr.destroy_space(app_space);
    }
    xr.destroy_session(session);
    shutdown_egl(egl);
    xr.destroy_instance(instance);
    log_info("OpenXR color smoke thread stop");
}
#endif

} // namespace

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

OpenXRAndroidStartResult start_android_color_smoke(void* java_vm, void* activity_or_context) {
    OpenXRAndroidStartResult result{};
    result.stage = "unsupported";
    result.detail = "OpenXR color smoke is only available in Android builds with OpenXR headers";

#if defined(TERMIN_OPENXR_HAS_HEADERS) && defined(__ANDROID__)
    if (!java_vm || !activity_or_context) {
        result.stage = "input";
        result.detail = "JavaVM or Android activity/context is null";
        log_error(result.stage, result.detail);
        return result;
    }
    if (g_smoke.running.exchange(true)) {
        result.started = true;
        result.stage = "already-running";
        result.detail = "OpenXR color smoke thread is already running";
        return result;
    }
    if (g_smoke.thread.joinable()) {
        g_smoke.thread.join();
    }
    try {
        g_smoke.thread = std::thread(smoke_thread_main, java_vm, activity_or_context);
    } catch (...) {
        g_smoke.running.store(false);
        result.stage = "thread";
        result.detail = "failed to create OpenXR color smoke thread";
        log_error(result.stage, result.detail);
        return result;
    }
    result.started = true;
    result.stage = "started";
    result.detail = "OpenXR color smoke thread started";
#endif

    return result;
}

void stop_android_color_smoke() {
#if defined(TERMIN_OPENXR_HAS_HEADERS) && defined(__ANDROID__)
    g_smoke.running.store(false);
    if (g_smoke.thread.joinable()) {
        g_smoke.thread.join();
    }
#endif
}

} // namespace termin::openxr
