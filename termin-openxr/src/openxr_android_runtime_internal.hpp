#pragma once

#include <array>
#include <cstddef>
#include <filesystem>
#include <string>
#include <vector>

#include <tcbase/trent/json.h>
#include <termin/entity/entity.hpp>
#include <termin/geom/mat44.hpp>
#include <termin/input/xr_input.hpp>
#include <termin/openxr/openxr_runtime.hpp>
#include <tgfx2/descriptors.hpp>

#if defined(TERMIN_OPENXR_HAS_HEADERS)
#if defined(__ANDROID__)
#include <jni.h>
#define XR_USE_PLATFORM_ANDROID
#endif
#define XR_USE_GRAPHICS_API_VULKAN
#include <vulkan/vulkan.h>
#include <openxr/openxr.h>
#include <openxr/openxr_platform.h>
#endif

namespace termin::openxr::detail {

#if defined(TERMIN_OPENXR_HAS_HEADERS) && defined(__ANDROID__)

inline constexpr const char *kLogTag = "TerminOpenXR";

struct OpenXRDispatch {
    PFN_xrGetInstanceProcAddr get_instance_proc_addr = nullptr;
    PFN_xrInitializeLoaderKHR initialize_loader = nullptr;
    PFN_xrEnumerateInstanceExtensionProperties enumerate_instance_extension_properties = nullptr;
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
    PFN_xrStringToPath string_to_path = nullptr;
    PFN_xrCreateActionSet create_action_set = nullptr;
    PFN_xrDestroyActionSet destroy_action_set = nullptr;
    PFN_xrCreateAction create_action = nullptr;
    PFN_xrDestroyAction destroy_action = nullptr;
    PFN_xrSuggestInteractionProfileBindings suggest_interaction_profile_bindings = nullptr;
    PFN_xrAttachSessionActionSets attach_session_action_sets = nullptr;
    PFN_xrSyncActions sync_actions = nullptr;
    PFN_xrGetActionStateVector2f get_action_state_vector2f = nullptr;
    PFN_xrGetVulkanInstanceExtensionsKHR get_vulkan_instance_extensions = nullptr;
    PFN_xrGetVulkanDeviceExtensionsKHR get_vulkan_device_extensions = nullptr;
    PFN_xrGetVulkanGraphicsDeviceKHR get_vulkan_graphics_device = nullptr;
    PFN_xrGetVulkanGraphicsRequirementsKHR get_vulkan_requirements = nullptr;
    PFN_xrEnumerateDisplayRefreshRatesFB enumerate_display_refresh_rates = nullptr;
    PFN_xrGetDisplayRefreshRateFB get_display_refresh_rate = nullptr;
    PFN_xrRequestDisplayRefreshRateFB request_display_refresh_rate = nullptr;
};

extern const unsigned char kSmokeVertexSpv[];
extern const size_t kSmokeVertexSpvSize;
extern const unsigned char kSmokeFragmentSpv[];
extern const size_t kSmokeFragmentSpvSize;

void install_android_tc_log_callback_once();
void log_info(const char *message);
void log_error(const char *stage, const char *detail);
const char *session_state_name(XrSessionState state);
bool load_instance_proc(const OpenXRDispatch &dispatch, XrInstance instance, const char *name, PFN_xrVoidFunction *out);
bool openxr_instance_extension_available(OpenXRDispatch &xr, const char *extension_name);
void configure_display_refresh_rate(OpenXRDispatch &xr, XrSession session);
bool xr_string_to_path(OpenXRDispatch &xr, XrInstance instance, const char *path_text, XrPath &out);

struct XrControllerActions {
    OpenXRDispatch *xr = nullptr;
    XrInstance instance = XR_NULL_HANDLE;
    XrActionSet action_set = XR_NULL_HANDLE;
    XrAction thumbstick_axis = XR_NULL_HANDLE;
    XrPath left_hand = XR_NULL_PATH;
    XrPath right_hand = XR_NULL_PATH;
    termin::xr::XrRigInputState rig_state;
    bool initialized = false;
    bool attached = false;
    bool registered = false;

    bool init(OpenXRDispatch &dispatch, XrInstance xr_instance);
    bool attach(XrSession session);
    void update_head_axes(const XrView &head_view, const termin::Mat44 &origin_from_xr_reference,
                          bool orientation_valid);
    void sync(XrSession session, uint64_t frame_index);
    void destroy();

  private:
    void update_thumbstick(XrSession session, XrPath subaction_path, termin::xr::XrAxis2State &out);
};

std::vector<std::string> split_openxr_extension_string(const std::string &text);
std::vector<const char *> extension_cstrs(const std::vector<std::string> &extensions);
bool query_openxr_vulkan_extensions(PFN_xrGetVulkanInstanceExtensionsKHR query, XrInstance instance,
                                    XrSystemId system_id, std::vector<std::string> &out);
tgfx::PixelFormat pixel_format_from_vk_format(VkFormat format);
bool is_supported_vulkan_color_format(int64_t format);
int64_t choose_vulkan_swapchain_format(const std::vector<int64_t> &formats);
bool cstr_nonempty(const char *value);
std::string read_runtime_text_file(const std::filesystem::path &path);
const nos::trent *trent_dict_get(const nos::trent &t, const char *key);
std::string trent_string_field(const nos::trent &t, const char *key);
std::filesystem::path runtime_package_path(const std::filesystem::path &root, const std::string &rel);
std::string normalized_pipeline_name(const char *value);
std::array<float, 16> make_scene_primitive_model_matrix(const termin::Entity &primitive, uint64_t frame_index);

#endif

OpenXRAndroidStartResult start_android_scene_smoke_internal(void *java_vm, void *activity_or_context,
                                                            const char *asset_root);
void stop_android_color_smoke_internal();

} // namespace termin::openxr::detail
