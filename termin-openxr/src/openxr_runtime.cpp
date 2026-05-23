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
#include <memory>
#include <span>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.h>
#include <components/mesh_component.hpp>
#include <termin/camera/camera_component.hpp>
#include <termin/engine/engine_core.hpp>
#include <termin/entity/entity.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/geom/vec3.hpp>
#include <termin/lighting/light_component.hpp>
#include <termin/render/mesh_renderer.hpp>
#include <termin/render/render_engine.hpp>
#include <termin/render/render_pipeline.hpp>
#include <termin/render/rendering_manager.hpp>
#include <termin/runtime/runtime_package.hpp>
#include <termin/tc_scene.hpp>
#include <termin_collision/termin_collision.h>
#include <tgfx/tgfx_mesh_handle.hpp>
#include <tgfx/tgfx2_interop.h>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/i_command_list.hpp>
#include <tgfx2/render_state.hpp>
#include <tgfx2/vulkan/vulkan_render_device.hpp>

extern "C" {
void tc_inspect_kind_core_init(void);
#  include <core/tc_component.h>
#  include <core/tc_scene_render_mount.h>
#  include <core/tc_scene_render_state.h>
#  include <inspect/tc_inspect_pass_adapter.h>
#  include <render/tc_pass.h>
#  include <render/tc_pipeline.h>
#  include <termin_scene/termin_scene.h>
#  include <tgfx/resources/tc_mesh_registry.h>
#  include <tgfx/resources/tc_primitive_mesh.h>
}

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

const unsigned char kSmokeVertexSpv[] = {
  0x03, 0x02, 0x23, 0x07, 0x00, 0x05, 0x01, 0x00, 0x0b, 0x00, 0x0d, 0x00,
  0x27, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x11, 0x00, 0x02, 0x00,
  0x01, 0x00, 0x00, 0x00, 0x0b, 0x00, 0x06, 0x00, 0x01, 0x00, 0x00, 0x00,
  0x47, 0x4c, 0x53, 0x4c, 0x2e, 0x73, 0x74, 0x64, 0x2e, 0x34, 0x35, 0x30,
  0x00, 0x00, 0x00, 0x00, 0x0e, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x01, 0x00, 0x00, 0x00, 0x0f, 0x00, 0x0a, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x04, 0x00, 0x00, 0x00, 0x6d, 0x61, 0x69, 0x6e, 0x00, 0x00, 0x00, 0x00,
  0x09, 0x00, 0x00, 0x00, 0x0b, 0x00, 0x00, 0x00, 0x13, 0x00, 0x00, 0x00,
  0x19, 0x00, 0x00, 0x00, 0x1d, 0x00, 0x00, 0x00, 0x47, 0x00, 0x04, 0x00,
  0x09, 0x00, 0x00, 0x00, 0x1e, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x47, 0x00, 0x04, 0x00, 0x0b, 0x00, 0x00, 0x00, 0x1e, 0x00, 0x00, 0x00,
  0x01, 0x00, 0x00, 0x00, 0x48, 0x00, 0x05, 0x00, 0x11, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x0b, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x48, 0x00, 0x05, 0x00, 0x11, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00,
  0x0b, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x48, 0x00, 0x05, 0x00,
  0x11, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x0b, 0x00, 0x00, 0x00,
  0x03, 0x00, 0x00, 0x00, 0x48, 0x00, 0x05, 0x00, 0x11, 0x00, 0x00, 0x00,
  0x03, 0x00, 0x00, 0x00, 0x0b, 0x00, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00,
  0x47, 0x00, 0x03, 0x00, 0x11, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00,
  0x48, 0x00, 0x04, 0x00, 0x17, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x05, 0x00, 0x00, 0x00, 0x48, 0x00, 0x05, 0x00, 0x17, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x23, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x48, 0x00, 0x05, 0x00, 0x17, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x07, 0x00, 0x00, 0x00, 0x10, 0x00, 0x00, 0x00, 0x47, 0x00, 0x03, 0x00,
  0x17, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x47, 0x00, 0x04, 0x00,
  0x1d, 0x00, 0x00, 0x00, 0x1e, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x13, 0x00, 0x02, 0x00, 0x02, 0x00, 0x00, 0x00, 0x21, 0x00, 0x03, 0x00,
  0x03, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x16, 0x00, 0x03, 0x00,
  0x06, 0x00, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x17, 0x00, 0x04, 0x00,
  0x07, 0x00, 0x00, 0x00, 0x06, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00,
  0x20, 0x00, 0x04, 0x00, 0x08, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00,
  0x07, 0x00, 0x00, 0x00, 0x3b, 0x00, 0x04, 0x00, 0x08, 0x00, 0x00, 0x00,
  0x09, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x20, 0x00, 0x04, 0x00,
  0x0a, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00,
  0x3b, 0x00, 0x04, 0x00, 0x0a, 0x00, 0x00, 0x00, 0x0b, 0x00, 0x00, 0x00,
  0x01, 0x00, 0x00, 0x00, 0x17, 0x00, 0x04, 0x00, 0x0d, 0x00, 0x00, 0x00,
  0x06, 0x00, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00, 0x15, 0x00, 0x04, 0x00,
  0x0e, 0x00, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x2b, 0x00, 0x04, 0x00, 0x0e, 0x00, 0x00, 0x00, 0x0f, 0x00, 0x00, 0x00,
  0x01, 0x00, 0x00, 0x00, 0x1c, 0x00, 0x04, 0x00, 0x10, 0x00, 0x00, 0x00,
  0x06, 0x00, 0x00, 0x00, 0x0f, 0x00, 0x00, 0x00, 0x1e, 0x00, 0x06, 0x00,
  0x11, 0x00, 0x00, 0x00, 0x0d, 0x00, 0x00, 0x00, 0x06, 0x00, 0x00, 0x00,
  0x10, 0x00, 0x00, 0x00, 0x10, 0x00, 0x00, 0x00, 0x20, 0x00, 0x04, 0x00,
  0x12, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x11, 0x00, 0x00, 0x00,
  0x3b, 0x00, 0x04, 0x00, 0x12, 0x00, 0x00, 0x00, 0x13, 0x00, 0x00, 0x00,
  0x03, 0x00, 0x00, 0x00, 0x15, 0x00, 0x04, 0x00, 0x14, 0x00, 0x00, 0x00,
  0x20, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x2b, 0x00, 0x04, 0x00,
  0x14, 0x00, 0x00, 0x00, 0x15, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x18, 0x00, 0x04, 0x00, 0x16, 0x00, 0x00, 0x00, 0x0d, 0x00, 0x00, 0x00,
  0x04, 0x00, 0x00, 0x00, 0x1e, 0x00, 0x03, 0x00, 0x17, 0x00, 0x00, 0x00,
  0x16, 0x00, 0x00, 0x00, 0x20, 0x00, 0x04, 0x00, 0x18, 0x00, 0x00, 0x00,
  0x09, 0x00, 0x00, 0x00, 0x17, 0x00, 0x00, 0x00, 0x3b, 0x00, 0x04, 0x00,
  0x18, 0x00, 0x00, 0x00, 0x19, 0x00, 0x00, 0x00, 0x09, 0x00, 0x00, 0x00,
  0x20, 0x00, 0x04, 0x00, 0x1a, 0x00, 0x00, 0x00, 0x09, 0x00, 0x00, 0x00,
  0x16, 0x00, 0x00, 0x00, 0x3b, 0x00, 0x04, 0x00, 0x0a, 0x00, 0x00, 0x00,
  0x1d, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x2b, 0x00, 0x04, 0x00,
  0x06, 0x00, 0x00, 0x00, 0x1f, 0x00, 0x00, 0x00, 0x00, 0x00, 0x80, 0x3f,
  0x20, 0x00, 0x04, 0x00, 0x25, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00,
  0x0d, 0x00, 0x00, 0x00, 0x36, 0x00, 0x05, 0x00, 0x02, 0x00, 0x00, 0x00,
  0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00,
  0xf8, 0x00, 0x02, 0x00, 0x05, 0x00, 0x00, 0x00, 0x3d, 0x00, 0x04, 0x00,
  0x07, 0x00, 0x00, 0x00, 0x0c, 0x00, 0x00, 0x00, 0x0b, 0x00, 0x00, 0x00,
  0x3e, 0x00, 0x03, 0x00, 0x09, 0x00, 0x00, 0x00, 0x0c, 0x00, 0x00, 0x00,
  0x41, 0x00, 0x05, 0x00, 0x1a, 0x00, 0x00, 0x00, 0x1b, 0x00, 0x00, 0x00,
  0x19, 0x00, 0x00, 0x00, 0x15, 0x00, 0x00, 0x00, 0x3d, 0x00, 0x04, 0x00,
  0x16, 0x00, 0x00, 0x00, 0x1c, 0x00, 0x00, 0x00, 0x1b, 0x00, 0x00, 0x00,
  0x3d, 0x00, 0x04, 0x00, 0x07, 0x00, 0x00, 0x00, 0x1e, 0x00, 0x00, 0x00,
  0x1d, 0x00, 0x00, 0x00, 0x51, 0x00, 0x05, 0x00, 0x06, 0x00, 0x00, 0x00,
  0x20, 0x00, 0x00, 0x00, 0x1e, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x51, 0x00, 0x05, 0x00, 0x06, 0x00, 0x00, 0x00, 0x21, 0x00, 0x00, 0x00,
  0x1e, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x51, 0x00, 0x05, 0x00,
  0x06, 0x00, 0x00, 0x00, 0x22, 0x00, 0x00, 0x00, 0x1e, 0x00, 0x00, 0x00,
  0x02, 0x00, 0x00, 0x00, 0x50, 0x00, 0x07, 0x00, 0x0d, 0x00, 0x00, 0x00,
  0x23, 0x00, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x21, 0x00, 0x00, 0x00,
  0x22, 0x00, 0x00, 0x00, 0x1f, 0x00, 0x00, 0x00, 0x91, 0x00, 0x05, 0x00,
  0x0d, 0x00, 0x00, 0x00, 0x24, 0x00, 0x00, 0x00, 0x1c, 0x00, 0x00, 0x00,
  0x23, 0x00, 0x00, 0x00, 0x41, 0x00, 0x05, 0x00, 0x25, 0x00, 0x00, 0x00,
  0x26, 0x00, 0x00, 0x00, 0x13, 0x00, 0x00, 0x00, 0x15, 0x00, 0x00, 0x00,
  0x3e, 0x00, 0x03, 0x00, 0x26, 0x00, 0x00, 0x00, 0x24, 0x00, 0x00, 0x00,
  0xfd, 0x00, 0x01, 0x00, 0x38, 0x00, 0x01, 0x00
};

const unsigned char kSmokeFragmentSpv[] = {
  0x03, 0x02, 0x23, 0x07, 0x00, 0x05, 0x01, 0x00, 0x0b, 0x00, 0x0d, 0x00,
  0x13, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x11, 0x00, 0x02, 0x00,
  0x01, 0x00, 0x00, 0x00, 0x0b, 0x00, 0x06, 0x00, 0x01, 0x00, 0x00, 0x00,
  0x47, 0x4c, 0x53, 0x4c, 0x2e, 0x73, 0x74, 0x64, 0x2e, 0x34, 0x35, 0x30,
  0x00, 0x00, 0x00, 0x00, 0x0e, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x01, 0x00, 0x00, 0x00, 0x0f, 0x00, 0x07, 0x00, 0x04, 0x00, 0x00, 0x00,
  0x04, 0x00, 0x00, 0x00, 0x6d, 0x61, 0x69, 0x6e, 0x00, 0x00, 0x00, 0x00,
  0x09, 0x00, 0x00, 0x00, 0x0c, 0x00, 0x00, 0x00, 0x10, 0x00, 0x03, 0x00,
  0x04, 0x00, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00, 0x47, 0x00, 0x04, 0x00,
  0x09, 0x00, 0x00, 0x00, 0x1e, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x47, 0x00, 0x04, 0x00, 0x0c, 0x00, 0x00, 0x00, 0x1e, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x13, 0x00, 0x02, 0x00, 0x02, 0x00, 0x00, 0x00,
  0x21, 0x00, 0x03, 0x00, 0x03, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00,
  0x16, 0x00, 0x03, 0x00, 0x06, 0x00, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00,
  0x17, 0x00, 0x04, 0x00, 0x07, 0x00, 0x00, 0x00, 0x06, 0x00, 0x00, 0x00,
  0x04, 0x00, 0x00, 0x00, 0x20, 0x00, 0x04, 0x00, 0x08, 0x00, 0x00, 0x00,
  0x03, 0x00, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00, 0x3b, 0x00, 0x04, 0x00,
  0x08, 0x00, 0x00, 0x00, 0x09, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00,
  0x17, 0x00, 0x04, 0x00, 0x0a, 0x00, 0x00, 0x00, 0x06, 0x00, 0x00, 0x00,
  0x03, 0x00, 0x00, 0x00, 0x20, 0x00, 0x04, 0x00, 0x0b, 0x00, 0x00, 0x00,
  0x01, 0x00, 0x00, 0x00, 0x0a, 0x00, 0x00, 0x00, 0x3b, 0x00, 0x04, 0x00,
  0x0b, 0x00, 0x00, 0x00, 0x0c, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00,
  0x2b, 0x00, 0x04, 0x00, 0x06, 0x00, 0x00, 0x00, 0x0e, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x80, 0x3f, 0x36, 0x00, 0x05, 0x00, 0x02, 0x00, 0x00, 0x00,
  0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00,
  0xf8, 0x00, 0x02, 0x00, 0x05, 0x00, 0x00, 0x00, 0x3d, 0x00, 0x04, 0x00,
  0x0a, 0x00, 0x00, 0x00, 0x0d, 0x00, 0x00, 0x00, 0x0c, 0x00, 0x00, 0x00,
  0x51, 0x00, 0x05, 0x00, 0x06, 0x00, 0x00, 0x00, 0x0f, 0x00, 0x00, 0x00,
  0x0d, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x51, 0x00, 0x05, 0x00,
  0x06, 0x00, 0x00, 0x00, 0x10, 0x00, 0x00, 0x00, 0x0d, 0x00, 0x00, 0x00,
  0x01, 0x00, 0x00, 0x00, 0x51, 0x00, 0x05, 0x00, 0x06, 0x00, 0x00, 0x00,
  0x11, 0x00, 0x00, 0x00, 0x0d, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00,
  0x50, 0x00, 0x07, 0x00, 0x07, 0x00, 0x00, 0x00, 0x12, 0x00, 0x00, 0x00,
  0x0f, 0x00, 0x00, 0x00, 0x10, 0x00, 0x00, 0x00, 0x11, 0x00, 0x00, 0x00,
  0x0e, 0x00, 0x00, 0x00, 0x3e, 0x00, 0x03, 0x00, 0x09, 0x00, 0x00, 0x00,
  0x12, 0x00, 0x00, 0x00, 0xfd, 0x00, 0x01, 0x00, 0x38, 0x00, 0x01, 0x00
};

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
    PFN_xrGetVulkanInstanceExtensionsKHR get_vulkan_instance_extensions = nullptr;
    PFN_xrGetVulkanDeviceExtensionsKHR get_vulkan_device_extensions = nullptr;
    PFN_xrGetVulkanGraphicsDeviceKHR get_vulkan_graphics_device = nullptr;
    PFN_xrGetVulkanGraphicsRequirementsKHR get_vulkan_requirements = nullptr;
};

struct SmokeControl {
    std::atomic<bool> running{false};
    std::thread thread;
};

SmokeControl g_smoke;

struct ScenePrimitiveSmoke {
    termin::TcSceneRef scene;
    termin::Entity primitive;
    tgfx::BufferHandle vbo;
    tgfx::BufferHandle ebo;
    tgfx::ShaderHandle vertex_shader;
    tgfx::ShaderHandle fragment_shader;
    tgfx::PipelineHandle pipeline;
    uint32_t index_count = 0;
    bool initialized = false;

    bool init(tgfx::IRenderDevice& device, tgfx::PixelFormat color_format, uint32_t sample_count) {
        if (initialized) {
            return true;
        }

        termin_scene_runtime_init();
        termin::MeshComponent::register_type();

        scene = termin::TcSceneRef::create("OpenXR tc_scene smoke", "openxr-tc-scene-smoke");
        if (!scene.valid()) {
            log_error("tc_scene", "failed to create scene");
            return false;
        }

        primitive = scene.create_entity("tc_scene sphere");
        primitive.transform().set_local_position(termin::Vec3{0.0, 2.0, 0.0});

        auto* mesh_component = new termin::MeshComponent();
        const tc_mesh_handle mesh_handle = tc_primitive_unit_sphere();
        if (!tc_mesh_is_valid(mesh_handle) || !tc_mesh_ensure_loaded(mesh_handle)) {
            log_error("tc_scene", "failed to create/load unit sphere mesh");
            delete mesh_component;
            scene.destroy();
            scene = {};
            primitive = {};
            return false;
        }
        mesh_component->set_mesh(termin::TcMesh(mesh_handle));
        primitive.add_component(mesh_component);

        const tc_mesh* mesh = tc_mesh_get(mesh_handle);
        if (!mesh || !mesh->vertices || !mesh->indices || mesh->vertex_count == 0 || mesh->index_count == 0) {
            log_error("tc_scene", "unit sphere mesh has no CPU geometry");
            scene.destroy();
            scene = {};
            primitive = {};
            return false;
        }

        const tc_vertex_attrib* position_attr = tc_vertex_layout_find(&mesh->layout, "position");
        const tc_vertex_attrib* normal_attr = tc_vertex_layout_find(&mesh->layout, "normal");
        if (!position_attr || !normal_attr) {
            log_error("tc_scene", "unit sphere mesh is missing position/normal attributes");
            destroy();
            return false;
        }

        index_count = static_cast<uint32_t>(mesh->index_count);

        tgfx::BufferDesc vbo_desc{};
        vbo_desc.size = mesh->vertex_count * mesh->layout.stride;
        vbo_desc.usage = tgfx::BufferUsage::Vertex | tgfx::BufferUsage::CopyDst;
        vbo = device.create_buffer(vbo_desc);
        device.upload_buffer(
            vbo,
            std::span<const uint8_t>(
                reinterpret_cast<const uint8_t*>(mesh->vertices),
                static_cast<size_t>(vbo_desc.size)
            )
        );

        tgfx::BufferDesc ebo_desc{};
        ebo_desc.size = mesh->index_count * sizeof(uint32_t);
        ebo_desc.usage = tgfx::BufferUsage::Index | tgfx::BufferUsage::CopyDst;
        ebo = device.create_buffer(ebo_desc);
        device.upload_buffer(
            ebo,
            std::span<const uint8_t>(
                reinterpret_cast<const uint8_t*>(mesh->indices),
                static_cast<size_t>(ebo_desc.size)
            )
        );

        tgfx::ShaderDesc vs_desc{};
        vs_desc.stage = tgfx::ShaderStage::Vertex;
        vs_desc.bytecode.assign(kSmokeVertexSpv, kSmokeVertexSpv + sizeof(kSmokeVertexSpv));
        vs_desc.debug_name = "openxr tc_scene sphere vs";
        vertex_shader = device.create_shader(vs_desc);

        tgfx::ShaderDesc fs_desc{};
        fs_desc.stage = tgfx::ShaderStage::Fragment;
        fs_desc.bytecode.assign(kSmokeFragmentSpv, kSmokeFragmentSpv + sizeof(kSmokeFragmentSpv));
        fs_desc.debug_name = "openxr tc_scene sphere fs";
        fragment_shader = device.create_shader(fs_desc);

        tgfx::VertexBufferLayout vertex_layout{};
        vertex_layout.stride = static_cast<uint32_t>(mesh->layout.stride);
        vertex_layout.attributes.push_back({
            0,
            tgfx::VertexFormat::Float3,
            static_cast<uint32_t>(position_attr->offset)
        });
        vertex_layout.attributes.push_back({
            1,
            tgfx::VertexFormat::Float3,
            static_cast<uint32_t>(normal_attr->offset)
        });

        tgfx::PipelineDesc pipeline_desc{};
        pipeline_desc.vertex_shader = vertex_shader;
        pipeline_desc.fragment_shader = fragment_shader;
        pipeline_desc.vertex_layouts.push_back(std::move(vertex_layout));
        pipeline_desc.color_formats.push_back(color_format);
        pipeline_desc.depth_format = tgfx::PixelFormat::D32F;
        pipeline_desc.sample_count = sample_count;
        pipeline_desc.depth_stencil.depth_test = true;
        pipeline_desc.depth_stencil.depth_write = true;
        pipeline_desc.depth_stencil.depth_compare = tgfx::CompareOp::LessEqual;
        pipeline_desc.raster.cull = tgfx::CullMode::Back;
        pipeline = device.create_pipeline(pipeline_desc);

        initialized = true;
        __android_log_print(
            ANDROID_LOG_INFO,
            kLogTag,
            "tc_scene sphere ready: vertices=%zu indices=%zu stride=%u",
            mesh->vertex_count,
            mesh->index_count,
            static_cast<unsigned>(mesh->layout.stride)
        );
        return true;
    }

    void destroy(tgfx::IRenderDevice* device = nullptr) {
        if (device) {
            if (pipeline) {
                device->destroy(pipeline);
            }
            if (fragment_shader) {
                device->destroy(fragment_shader);
            }
            if (vertex_shader) {
                device->destroy(vertex_shader);
            }
            if (ebo) {
                device->destroy(ebo);
            }
            if (vbo) {
                device->destroy(vbo);
            }
        }
        pipeline = {};
        fragment_shader = {};
        vertex_shader = {};
        ebo = {};
        vbo = {};
        index_count = 0;
        initialized = false;

        if (scene.valid()) {
            scene.destroy();
        }
        scene = {};
        primitive = {};
    }
};

const char* session_state_name(XrSessionState state) {
    switch (state) {
        case XR_SESSION_STATE_UNKNOWN: return "UNKNOWN";
        case XR_SESSION_STATE_IDLE: return "IDLE";
        case XR_SESSION_STATE_READY: return "READY";
        case XR_SESSION_STATE_SYNCHRONIZED: return "SYNCHRONIZED";
        case XR_SESSION_STATE_VISIBLE: return "VISIBLE";
        case XR_SESSION_STATE_FOCUSED: return "FOCUSED";
        case XR_SESSION_STATE_STOPPING: return "STOPPING";
        case XR_SESSION_STATE_LOSS_PENDING: return "LOSS_PENDING";
        case XR_SESSION_STATE_EXITING: return "EXITING";
        default: return "UNRECOGNIZED";
    }
}

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

std::vector<std::string> split_openxr_extension_string(const std::string& text) {
    std::vector<std::string> result;
    std::istringstream stream(text);
    std::string item;
    while (stream >> item) {
        result.push_back(item);
    }
    return result;
}

std::vector<const char*> extension_cstrs(const std::vector<std::string>& extensions) {
    std::vector<const char*> result;
    result.reserve(extensions.size());
    for (const std::string& extension : extensions) {
        result.push_back(extension.c_str());
    }
    return result;
}

bool query_openxr_vulkan_extensions(
    PFN_xrGetVulkanInstanceExtensionsKHR query,
    XrInstance instance,
    XrSystemId system_id,
    std::vector<std::string>& out
) {
    uint32_t size = 0;
    XrResult result = query(instance, system_id, 0, &size, nullptr);
    if (XR_FAILED(result)) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrGetVulkan*ExtensionsKHR size failed: %d", result);
        return false;
    }
    std::string buffer(size, '\0');
    result = query(instance, system_id, size, &size, buffer.data());
    if (XR_FAILED(result)) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrGetVulkan*ExtensionsKHR failed: %d", result);
        return false;
    }
    out = split_openxr_extension_string(buffer.c_str());
    return true;
}

tgfx::PixelFormat pixel_format_from_vk_format(VkFormat format) {
    switch (format) {
        case VK_FORMAT_R8G8B8A8_UNORM:
        case VK_FORMAT_R8G8B8A8_SRGB:
            return tgfx::PixelFormat::RGBA8_UNorm;
        case VK_FORMAT_B8G8R8A8_UNORM:
        case VK_FORMAT_B8G8R8A8_SRGB:
            return tgfx::PixelFormat::BGRA8_UNorm;
        default:
            return tgfx::PixelFormat::Undefined;
    }
}

bool is_supported_vulkan_color_format(int64_t format) {
    return pixel_format_from_vk_format(static_cast<VkFormat>(format)) != tgfx::PixelFormat::Undefined;
}

int64_t choose_vulkan_swapchain_format(const std::vector<int64_t>& formats) {
    for (int64_t format : formats) {
        if (format == VK_FORMAT_R8G8B8A8_UNORM || format == VK_FORMAT_B8G8R8A8_UNORM) {
            return format;
        }
    }
    for (int64_t format : formats) {
        if (is_supported_vulkan_color_format(format)) {
            return format;
        }
    }
    return formats.empty() ? 0 : formats.front();
}

std::array<float, 16> make_identity_matrix() {
    return {
        1.0f, 0.0f, 0.0f, 0.0f,
        0.0f, 1.0f, 0.0f, 0.0f,
        0.0f, 0.0f, 1.0f, 0.0f,
        0.0f, 0.0f, 0.0f, 1.0f,
    };
}

std::array<float, 16> make_xr_projection_matrix_vulkan(const XrFovf& fov, float near_z, float far_z) {
    const float tan_left = std::tan(fov.angleLeft);
    const float tan_right = std::tan(fov.angleRight);
    const float tan_down = std::tan(fov.angleDown);
    const float tan_up = std::tan(fov.angleUp);
    const float tan_width = tan_right - tan_left;
    const float tan_height = tan_down - tan_up;

    std::array<float, 16> m{};
    m[0] = 2.0f / tan_width;
    m[5] = 2.0f / tan_height;
    m[8] = (tan_right + tan_left) / tan_width;
    m[9] = (tan_up + tan_down) / tan_height;
    m[10] = far_z / (near_z - far_z);
    m[11] = -1.0f;
    m[14] = (far_z * near_z) / (near_z - far_z);
    return m;
}

std::array<float, 16> multiply_matrix(
    const std::array<float, 16>& a,
    const std::array<float, 16>& b
) {
    std::array<float, 16> out{};
    for (int col = 0; col < 4; ++col) {
        for (int row = 0; row < 4; ++row) {
            out[col * 4 + row] =
                a[0 * 4 + row] * b[col * 4 + 0] +
                a[1 * 4 + row] * b[col * 4 + 1] +
                a[2 * 4 + row] * b[col * 4 + 2] +
                a[3 * 4 + row] * b[col * 4 + 3];
        }
    }
    return out;
}

std::array<float, 16> make_view_matrix_from_xr_pose(const XrPosef& pose) {
    const XrQuaternionf& q = pose.orientation;
    const float x2 = q.x + q.x;
    const float y2 = q.y + q.y;
    const float z2 = q.z + q.z;
    const float xx = q.x * x2;
    const float xy = q.x * y2;
    const float xz = q.x * z2;
    const float yy = q.y * y2;
    const float yz = q.y * z2;
    const float zz = q.z * z2;
    const float wx = q.w * x2;
    const float wy = q.w * y2;
    const float wz = q.w * z2;

    const float r00 = 1.0f - (yy + zz);
    const float r01 = xy - wz;
    const float r02 = xz + wy;
    const float r10 = xy + wz;
    const float r11 = 1.0f - (xx + zz);
    const float r12 = yz - wx;
    const float r20 = xz - wy;
    const float r21 = yz + wx;
    const float r22 = 1.0f - (xx + yy);

    const XrVector3f& p = pose.position;
    const float tx = -(r00 * p.x + r10 * p.y + r20 * p.z);
    const float ty = -(r01 * p.x + r11 * p.y + r21 * p.z);
    const float tz = -(r02 * p.x + r12 * p.y + r22 * p.z);

    return {
        r00, r01, r02, 0.0f,
        r10, r11, r12, 0.0f,
        r20, r21, r22, 0.0f,
        tx,  ty,  tz,  1.0f,
    };
}

termin::Mat44 mat44_from_float_array(const std::array<float, 16>& src) {
    termin::Mat44 out = termin::Mat44::identity();
    for (size_t i = 0; i < src.size(); ++i) {
        out.data[i] = static_cast<double>(src[i]);
    }
    return out;
}

termin::Mat44 make_scene_to_xr_matrix() {
    termin::Mat44 m = termin::Mat44::identity();
    m.data[0] = 1.0;
    m.data[1] = 0.0;
    m.data[2] = 0.0;
    m.data[4] = 0.0;
    m.data[5] = 0.0;
    m.data[6] = -1.0;
    m.data[8] = 0.0;
    m.data[9] = 1.0;
    m.data[10] = 0.0;
    return m;
}

termin::Vec3 xr_position_to_scene_position(const XrVector3f& p) {
    return termin::Vec3{
        static_cast<double>(p.x),
        static_cast<double>(-p.z),
        static_cast<double>(p.y)
    };
}

tc_pass* create_scene_pass(
    const char* type_name,
    const char* pass_name,
    std::initializer_list<std::pair<const char*, const char*>> fields
) {
    if (!tc_pass_registry_has(type_name)) {
        tc_log_error("[OpenXR scene] pass type is not registered: '%s'", type_name);
        return nullptr;
    }
    tc_pass* pass = tc_pass_registry_create(type_name);
    if (!pass) {
        tc_log_error("[OpenXR scene] failed to create pass '%s'", type_name);
        return nullptr;
    }
    tc_pass_set_name(pass, pass_name);
    for (const auto& [field, value] : fields) {
        tc_value field_value = tc_value_string(value);
        tc_pass_inspect_set(pass, field, field_value, nullptr);
        tc_value_free(&field_value);
    }
    return pass;
}

termin::RenderPipeline make_openxr_scene_pipeline() {
    tc_pipeline_handle ph = tc_pipeline_create("OpenXRScene");
    termin::RenderPipeline pipeline(ph);

    if (tc_pass* p = create_scene_pass("ColorPass", "Color", {
            {"input_res", "empty"},
            {"output_res", "color_opaque"},
            {"shadow_res", ""},
            {"phase_mark", "opaque"}
        })) {
        tc_pipeline_add_pass(ph, p);
    }
    if (tc_pass* p = create_scene_pass("ColorPass", "Transparent", {
            {"input_res", "color_opaque"},
            {"output_res", "color"},
            {"shadow_res", ""},
            {"phase_mark", "transparent"},
            {"sort_mode", "far_to_near"}
        })) {
        tc_pipeline_add_pass(ph, p);
    }
    if (tc_pass* p = create_scene_pass("PresentToScreenPass", "Present", {
            {"input_res", "color"},
            {"output_res", "OUTPUT"}
        })) {
        tc_pipeline_add_pass(ph, p);
    }

    const char* color_resources[] = {
        "empty",
        "color_opaque",
        "color",
    };
    for (const char* resource : color_resources) {
        termin::ResourceSpec spec;
        spec.resource = resource;
        spec.format = "render_target";
        pipeline.add_spec(spec);
    }
    return pipeline;
}

termin::CameraComponent* find_runtime_camera(termin::TcSceneRef scene) {
    tc_component* raw = tc_scene_first_component_of_type(scene.handle(), "CameraComponent");
    if (!raw) {
        return nullptr;
    }
    termin::CxxComponent* cxx = termin::CxxComponent::from_tc(raw);
    return dynamic_cast<termin::CameraComponent*>(cxx);
}

void register_openxr_scene_runtime() {
    static bool registered = false;
    if (registered) {
        return;
    }
    registered = true;

    termin_scene_runtime_init();
    tc_inspect_kind_core_init();
    tc_scene_render_mount_extension_init();
    tc_scene_render_state_extension_init();
    termin_collision_runtime_init();
    tc::KindRegistryCpp::instance();
    termin::MeshComponent::register_type();
}

struct OpenXRRuntimeScene {
    std::unique_ptr<termin::EngineCore> engine;
    termin::TcSceneRef scene;
    termin::RenderPipeline pipeline;
    termin::CameraComponent* authoring_camera = nullptr;
    bool ready = false;

    bool load(const std::string& asset_root) {
        if (ready) {
            return true;
        }
        if (asset_root.empty()) {
            log_error("OpenXR scene", "asset_root is empty");
            tc_log_error("[OpenXR scene] asset_root is empty");
            return false;
        }

        register_openxr_scene_runtime();

        const char* required_components[] = {
            "MeshComponent",
            "MeshRenderer",
            "CameraComponent",
            "LightComponent",
            "UnknownComponent",
        };
        for (const char* name : required_components) {
            if (!tc_component_registry_has(name)) {
                log_error("OpenXR scene", (std::string("required component is not registered: ") + name).c_str());
                tc_log_error("[OpenXR scene] required component is not registered: %s", name);
                return false;
            }
        }

        const std::filesystem::path manifest_path =
            std::filesystem::path(asset_root) / "manifest.json";
        if (!std::filesystem::is_regular_file(manifest_path)) {
            log_error("OpenXR scene", (std::string("runtime manifest not found at ") + manifest_path.string()).c_str());
            tc_log_error("[OpenXR scene] runtime manifest not found at '%s'", manifest_path.c_str());
            return false;
        }

        engine = std::make_unique<termin::EngineCore>();
        termin::runtime::RuntimePackageLoader loader;
        termin::runtime::RuntimePackageLoadResult package = loader.load(asset_root);
        if (!package.ok || !package.scene.valid()) {
            log_error("OpenXR scene", (std::string("runtime package load failed: ") + package.message).c_str());
            tc_log_error("[OpenXR scene] runtime package load failed: %s", package.message.c_str());
            engine.reset();
            return false;
        }

        authoring_camera = find_runtime_camera(package.scene);
        if (!authoring_camera) {
            log_error("OpenXR scene", "runtime package loaded but has no CameraComponent");
            tc_log_error("[OpenXR scene] runtime package loaded but has no CameraComponent");
            package.scene.destroy();
            engine.reset();
            return false;
        }

        pipeline = make_openxr_scene_pipeline();
        if (!pipeline.is_valid() || pipeline.pass_count() == 0) {
            log_error("OpenXR scene", "failed to create render pipeline");
            tc_log_error("[OpenXR scene] failed to create render pipeline");
            package.scene.destroy();
            engine.reset();
            return false;
        }

        scene = package.scene;
        ready = true;
        __android_log_print(
            ANDROID_LOG_INFO,
            kLogTag,
            "OpenXR runtime scene loaded root='%s' entities=%zu passes=%zu",
            asset_root.c_str(),
            scene.entity_count(),
            pipeline.pass_count()
        );
        return true;
    }

    void render_eye(
        tgfx::TextureHandle color_texture,
        tgfx::TextureHandle depth_texture,
        uint32_t width,
        uint32_t height,
        tgfx::PixelFormat color_format,
        const XrView& view
    ) {
        if (!ready || !engine || !authoring_camera) {
            return;
        }

        termin::RenderEngine* render_engine = engine->rendering_manager.render_engine();
        if (!render_engine) {
            tc_log_error("[OpenXR scene] RenderEngine is unavailable");
            return;
        }

        termin::RenderTargetContext target;
        target.name = "Main";
        target.render_rect = termin::Rect4i{
            0,
            0,
            static_cast<int>(width),
            static_cast<int>(height)
        };
        target.output_color_tex = color_texture;
        target.output_depth_tex = depth_texture;
        target.output_color_format = color_format;
        target.output_depth_format = tgfx::PixelFormat::D32F;
        target.clear_color_enabled = true;
        target.clear_color[0] = 0.015f;
        target.clear_color[1] = 0.018f;
        target.clear_color[2] = 0.024f;
        target.clear_color[3] = 1.0f;
        target.clear_depth_enabled = true;
        target.clear_depth = 1.0f;
        target.camera.view =
            mat44_from_float_array(make_view_matrix_from_xr_pose(view.pose)) *
            make_scene_to_xr_matrix();
        target.camera.projection =
            mat44_from_float_array(make_xr_projection_matrix_vulkan(
                view.fov,
                static_cast<float>(authoring_camera->near_clip),
                static_cast<float>(authoring_camera->far_clip)
            ));
        target.camera.position = xr_position_to_scene_position(view.pose.position);
        target.camera.near_clip = authoring_camera->near_clip;
        target.camera.far_clip = authoring_camera->far_clip;
        target.layer_mask = authoring_camera->layer_mask;

        std::unordered_map<std::string, termin::RenderTargetContext> targets;
        targets.emplace(target.name, target);
        std::vector<termin::Light> lights;

        render_engine->render_scene_pipeline_offscreen(
            pipeline,
            scene.handle(),
            targets,
            lights,
            target.name
        );
    }

    void destroy() {
        pipeline = {};
        authoring_camera = nullptr;
        if (scene.valid()) {
            scene.destroy();
        }
        scene = {};
        engine.reset();
        ready = false;
    }
};

std::array<float, 16> make_scene_primitive_model_matrix(
    const termin::Entity& primitive,
    uint64_t frame_index
) {
    std::array<float, 16> m = make_identity_matrix();
    const float angle = static_cast<float>(frame_index) * 0.012f;
    const float c = std::cos(angle);
    const float s = std::sin(angle);

    termin::Vec3 p = primitive.valid()
        ? primitive.transform().local_position()
        : termin::Vec3{0.0, 2.0, 0.0};

    // Termin scene space is X-right, Y-forward, Z-up. OpenXR view space
    // here uses X-right, Y-up, -Z-forward.
    m[0] = c;
    m[1] = 0.0f;
    m[2] = -s;
    m[4] = -s;
    m[5] = 0.0f;
    m[6] = -c;
    m[8] = 0.0f;
    m[9] = 1.0f;
    m[10] = 0.0f;
    m[12] = static_cast<float>(p.x);
    m[13] = static_cast<float>(p.z);
    m[14] = static_cast<float>(-p.y);
    return m;
}

void smoke_thread_main(void* java_vm, void* activity_or_context, std::string asset_root) {
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
        XR_KHR_VULKAN_ENABLE_EXTENSION_NAME,
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
    load_instance_proc(xr, instance, "xrGetVulkanInstanceExtensionsKHR", reinterpret_cast<PFN_xrVoidFunction*>(&xr.get_vulkan_instance_extensions));
    load_instance_proc(xr, instance, "xrGetVulkanDeviceExtensionsKHR", reinterpret_cast<PFN_xrVoidFunction*>(&xr.get_vulkan_device_extensions));
    load_instance_proc(xr, instance, "xrGetVulkanGraphicsDeviceKHR", reinterpret_cast<PFN_xrVoidFunction*>(&xr.get_vulkan_graphics_device));
    load_instance_proc(xr, instance, "xrGetVulkanGraphicsRequirementsKHR", reinterpret_cast<PFN_xrVoidFunction*>(&xr.get_vulkan_requirements));

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

    XrGraphicsRequirementsVulkanKHR vulkan_requirements{};
    vulkan_requirements.type = XR_TYPE_GRAPHICS_REQUIREMENTS_VULKAN_KHR;
    result = xr.get_vulkan_requirements(instance, system_id, &vulkan_requirements);
    if (XR_FAILED(result)) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrGetVulkanGraphicsRequirementsKHR failed: %d", result);
        xr.destroy_instance(instance);
        g_smoke.running.store(false);
        return;
    }

    std::vector<std::string> instance_extension_storage;
    std::vector<std::string> device_extension_storage;
    if (!query_openxr_vulkan_extensions(
            xr.get_vulkan_instance_extensions,
            instance,
            system_id,
            instance_extension_storage) ||
        !query_openxr_vulkan_extensions(
            xr.get_vulkan_device_extensions,
            instance,
            system_id,
            device_extension_storage)) {
        xr.destroy_instance(instance);
        g_smoke.running.store(false);
        return;
    }
    std::vector<const char*> instance_extensions = extension_cstrs(instance_extension_storage);
    std::vector<const char*> device_extensions = extension_cstrs(device_extension_storage);

    std::unique_ptr<tgfx::VulkanRenderDevice> render_device;
    try {
        tgfx::VulkanDeviceCreateInfo device_info{};
        device_info.enable_validation = false;
        device_info.instance_extensions = instance_extensions;
        device_info.device_extensions = device_extensions;
        device_info.physical_device_selector = [&](VkInstance vk_instance) -> VkPhysicalDevice {
            VkPhysicalDevice physical_device = VK_NULL_HANDLE;
            XrResult select_result = xr.get_vulkan_graphics_device(
                instance,
                system_id,
                vk_instance,
                &physical_device
            );
            if (XR_FAILED(select_result)) {
                __android_log_print(
                    ANDROID_LOG_ERROR,
                    kLogTag,
                    "xrGetVulkanGraphicsDeviceKHR failed: %d",
                    select_result
                );
                return VK_NULL_HANDLE;
            }
            return physical_device;
        };
        render_device = std::make_unique<tgfx::VulkanRenderDevice>(device_info);
        tgfx2_interop_set_device(render_device.get());
    } catch (const std::exception& e) {
        log_error("tgfx2 Vulkan", e.what());
        xr.destroy_instance(instance);
        g_smoke.running.store(false);
        return;
    }

    XrGraphicsBindingVulkanKHR graphics_binding{};
    graphics_binding.type = XR_TYPE_GRAPHICS_BINDING_VULKAN_KHR;
    graphics_binding.instance = render_device->instance();
    graphics_binding.physicalDevice = render_device->physical_device();
    graphics_binding.device = render_device->device();
    graphics_binding.queueFamilyIndex = render_device->graphics_queue_family();
    graphics_binding.queueIndex = 0;

    XrSessionCreateInfo session_create_info{};
    session_create_info.type = XR_TYPE_SESSION_CREATE_INFO;
    session_create_info.next = &graphics_binding;
    session_create_info.systemId = system_id;

    XrSession session = XR_NULL_HANDLE;
    result = xr.create_session(instance, &session_create_info, &session);
    if (XR_FAILED(result) || session == XR_NULL_HANDLE) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrCreateSession failed: %d", result);
        render_device.reset();
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
        render_device.reset();
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
    int64_t color_format = choose_vulkan_swapchain_format(formats);
    tgfx::PixelFormat tgfx_color_format = pixel_format_from_vk_format(static_cast<VkFormat>(color_format));
    if (tgfx_color_format == tgfx::PixelFormat::Undefined) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "unsupported Vulkan swapchain format: 0x%llx", static_cast<long long>(color_format));
        if (app_space != XR_NULL_HANDLE) {
            xr.destroy_space(app_space);
        }
        xr.destroy_session(session);
        render_device.reset();
        xr.destroy_instance(instance);
        g_smoke.running.store(false);
        return;
    }
    __android_log_print(ANDROID_LOG_INFO, kLogTag, "OpenXR smoke color format: 0x%llx", static_cast<long long>(color_format));

    XrSwapchainCreateInfo swapchain_create_info{};
    swapchain_create_info.type = XR_TYPE_SWAPCHAIN_CREATE_INFO;
    swapchain_create_info.usageFlags =
        XR_SWAPCHAIN_USAGE_COLOR_ATTACHMENT_BIT |
        XR_SWAPCHAIN_USAGE_TRANSFER_DST_BIT;
    swapchain_create_info.format = color_format;
    swapchain_create_info.sampleCount = view_configs[0].recommendedSwapchainSampleCount;
    swapchain_create_info.width = view_configs[0].recommendedImageRectWidth;
    swapchain_create_info.height = view_configs[0].recommendedImageRectHeight;
    swapchain_create_info.faceCount = 1;
    swapchain_create_info.arraySize = 1;
    swapchain_create_info.mipCount = 1;

    std::vector<XrSwapchain> color_swapchains(view_count, XR_NULL_HANDLE);
    std::vector<std::vector<XrSwapchainImageVulkanKHR>> swapchain_images(view_count);
    std::vector<std::vector<tgfx::TextureHandle>> swapchain_textures(view_count);
    tgfx::TextureDesc color_desc{};
    color_desc.width = swapchain_create_info.width;
    color_desc.height = swapchain_create_info.height;
    color_desc.mip_levels = 1;
    color_desc.sample_count = swapchain_create_info.sampleCount;
    color_desc.format = tgfx_color_format;
    color_desc.usage = tgfx::TextureUsage::ColorAttachment |
                       tgfx::TextureUsage::CopySrc |
                       tgfx::TextureUsage::CopyDst;
    for (uint32_t eye = 0; eye < view_count; ++eye) {
        result = xr.create_swapchain(session, &swapchain_create_info, &color_swapchains[eye]);
        if (XR_FAILED(result) || color_swapchains[eye] == XR_NULL_HANDLE) {
            __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrCreateSwapchain[%u] failed: %d", eye, result);
            for (XrSwapchain swapchain : color_swapchains) {
                if (swapchain != XR_NULL_HANDLE) {
                    xr.destroy_swapchain(swapchain);
                }
            }
            if (app_space != XR_NULL_HANDLE) {
                xr.destroy_space(app_space);
            }
            xr.destroy_session(session);
            render_device.reset();
            xr.destroy_instance(instance);
            g_smoke.running.store(false);
            return;
        }

        uint32_t image_count = 0;
        xr.enumerate_swapchain_images(color_swapchains[eye], 0, &image_count, nullptr);
        swapchain_images[eye].resize(image_count);
        for (XrSwapchainImageVulkanKHR& image : swapchain_images[eye]) {
            image.type = XR_TYPE_SWAPCHAIN_IMAGE_VULKAN_KHR;
        }
        xr.enumerate_swapchain_images(
            color_swapchains[eye],
            image_count,
            &image_count,
            reinterpret_cast<XrSwapchainImageBaseHeader*>(swapchain_images[eye].data())
        );
        swapchain_textures[eye].reserve(image_count);
        for (const XrSwapchainImageVulkanKHR& image : swapchain_images[eye]) {
            swapchain_textures[eye].push_back(
                render_device->register_external_texture(
                    reinterpret_cast<uintptr_t>(image.image),
                    color_desc
                )
            );
        }
    }

    tgfx::TextureDesc depth_desc{};
    depth_desc.width = swapchain_create_info.width;
    depth_desc.height = swapchain_create_info.height;
    depth_desc.mip_levels = 1;
    depth_desc.sample_count = swapchain_create_info.sampleCount;
    depth_desc.format = tgfx::PixelFormat::D32F;
    depth_desc.usage = tgfx::TextureUsage::DepthStencilAttachment |
                       tgfx::TextureUsage::CopySrc |
                       tgfx::TextureUsage::Sampled;
    tgfx::TextureHandle depth_texture = render_device->create_texture(depth_desc);

    OpenXRRuntimeScene runtime_scene;
    const bool runtime_scene_requested = !asset_root.empty();
    const bool runtime_scene_ready =
        runtime_scene_requested && runtime_scene.load(asset_root);
    ScenePrimitiveSmoke scene_primitive;
    const bool scene_primitive_ready =
        !runtime_scene_requested &&
        scene_primitive.init(
            *render_device,
            tgfx_color_format,
            swapchain_create_info.sampleCount
        );
    if (runtime_scene_requested && !runtime_scene_ready) {
        __android_log_print(
            ANDROID_LOG_ERROR,
            kLogTag,
            "OpenXR runtime scene is not ready; rendering clear frames only"
        );
    }

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
                __android_log_print(
                    ANDROID_LOG_INFO,
                    kLogTag,
                    "session state: %s",
                    session_state_name(state_event->state)
                );
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
                for (uint32_t eye = 0; eye < view_count; ++eye) {
                    uint32_t image_index = 0;
                    XrSwapchainImageAcquireInfo acquire_info{};
                    acquire_info.type = XR_TYPE_SWAPCHAIN_IMAGE_ACQUIRE_INFO;
                    result = xr.acquire_swapchain_image(color_swapchains[eye], &acquire_info, &image_index);
                    if (XR_FAILED(result)) {
                        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrAcquireSwapchainImage[%u] failed: %d", eye, result);
                        continue;
                    }

                    XrSwapchainImageWaitInfo wait_swapchain_info{};
                    wait_swapchain_info.type = XR_TYPE_SWAPCHAIN_IMAGE_WAIT_INFO;
                    wait_swapchain_info.timeout = XR_INFINITE_DURATION;
                    result = xr.wait_swapchain_image(color_swapchains[eye], &wait_swapchain_info);
                    if (XR_FAILED(result)) {
                        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrWaitSwapchainImage[%u] failed: %d", eye, result);
                        continue;
                    }

                    const tgfx::TextureHandle color_texture = swapchain_textures[eye][image_index];
                    if (auto* color_resource = render_device->get_texture(color_texture)) {
                        color_resource->current_layout = VK_IMAGE_LAYOUT_UNDEFINED;
                    }
                    if (auto* depth_resource = render_device->get_texture(depth_texture)) {
                        depth_resource->current_layout = VK_IMAGE_LAYOUT_UNDEFINED;
                    }

                    if (runtime_scene_ready) {
                        runtime_scene.render_eye(
                            color_texture,
                            depth_texture,
                            swapchain_create_info.width,
                            swapchain_create_info.height,
                            tgfx_color_format,
                            views[eye]
                        );
                    } else {
                        auto cmd = render_device->create_command_list();
                        cmd->begin();
                        tgfx::RenderPassDesc pass{};
                        tgfx::ColorAttachmentDesc color_attachment{};
                        color_attachment.texture = color_texture;
                        color_attachment.load = tgfx::LoadOp::Clear;
                        color_attachment.store = tgfx::StoreOp::Store;
                        color_attachment.clear_color[0] = 0.015f;
                        color_attachment.clear_color[1] = 0.018f;
                        color_attachment.clear_color[2] = 0.024f;
                        color_attachment.clear_color[3] = 1.0f;
                        pass.colors.push_back(color_attachment);
                        pass.has_depth = true;
                        pass.depth.texture = depth_texture;
                        pass.depth.load = tgfx::LoadOp::Clear;
                        pass.depth.store = tgfx::StoreOp::DontCare;
                        pass.depth.clear_depth = 1.0f;
                        cmd->begin_render_pass(pass);
                        cmd->set_viewport(
                            0,
                            0,
                            static_cast<int>(swapchain_create_info.width),
                            static_cast<int>(swapchain_create_info.height)
                        );
                        cmd->set_scissor(
                            0,
                            0,
                            static_cast<int>(swapchain_create_info.width),
                            static_cast<int>(swapchain_create_info.height)
                        );
                        if (scene_primitive_ready) {
                            const auto projection = make_xr_projection_matrix_vulkan(views[eye].fov, 0.05f, 100.0f);
                            const auto view = make_view_matrix_from_xr_pose(views[eye].pose);
                            const auto model = make_scene_primitive_model_matrix(
                                scene_primitive.primitive,
                                frame_index
                            );
                            const std::array<float, 16> push =
                                multiply_matrix(projection, multiply_matrix(view, model));
                            cmd->bind_pipeline(scene_primitive.pipeline);
                            cmd->set_push_constants(push.data(), static_cast<uint32_t>(push.size() * sizeof(float)));
                            cmd->bind_vertex_buffer(0, scene_primitive.vbo);
                            cmd->bind_index_buffer(scene_primitive.ebo, tgfx::IndexType::Uint32);
                            cmd->draw_indexed(scene_primitive.index_count);
                        }
                        cmd->end_render_pass();
                        cmd->end();
                        render_device->submit(*cmd);
                    }
                    render_device->wait_idle();

                    layer_views[eye].pose = views[eye].pose;
                    layer_views[eye].fov = views[eye].fov;
                    layer_views[eye].subImage.swapchain = color_swapchains[eye];
                    layer_views[eye].subImage.imageRect.offset = {0, 0};
                    layer_views[eye].subImage.imageRect.extent = {
                        static_cast<int32_t>(swapchain_create_info.width),
                        static_cast<int32_t>(swapchain_create_info.height)
                    };
                    layer_views[eye].subImage.imageArrayIndex = 0;

                    XrSwapchainImageReleaseInfo release_info{};
                    release_info.type = XR_TYPE_SWAPCHAIN_IMAGE_RELEASE_INFO;
                    xr.release_swapchain_image(color_swapchains[eye], &release_info);
                }

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
    runtime_scene.destroy();
    scene_primitive.destroy(render_device.get());
    if (depth_texture) {
        render_device->destroy(depth_texture);
    }
    for (const std::vector<tgfx::TextureHandle>& eye_textures : swapchain_textures) {
        for (tgfx::TextureHandle texture : eye_textures) {
            if (texture) {
                render_device->destroy(texture);
            }
        }
    }
    render_device->wait_idle();
    for (XrSwapchain swapchain : color_swapchains) {
        if (swapchain != XR_NULL_HANDLE) {
            xr.destroy_swapchain(swapchain);
        }
    }
    if (app_space != XR_NULL_HANDLE) {
        xr.destroy_space(app_space);
    }
    xr.destroy_session(session);
    if (tgfx2_interop_get_device() == render_device.get()) {
        tgfx2_interop_set_device(nullptr);
    }
    render_device.reset();
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
    return start_android_scene_smoke(java_vm, activity_or_context, nullptr);
}

OpenXRAndroidStartResult start_android_scene_smoke(
    void* java_vm,
    void* activity_or_context,
    const char* asset_root
) {
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
        g_smoke.thread = std::thread(
            smoke_thread_main,
            java_vm,
            activity_or_context,
            std::string(asset_root ? asset_root : "")
        );
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
