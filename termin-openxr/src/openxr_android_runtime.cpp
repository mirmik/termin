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

namespace {

#if defined(TERMIN_OPENXR_HAS_HEADERS) && defined(__ANDROID__)
constexpr const char* kLogTag = "TerminOpenXR";

int android_log_priority(tc_log_level level) {
    switch (level) {
        case TC_LOG_DEBUG:
            return ANDROID_LOG_DEBUG;
        case TC_LOG_INFO:
            return ANDROID_LOG_INFO;
        case TC_LOG_WARN:
            return ANDROID_LOG_WARN;
        case TC_LOG_ERROR:
            return ANDROID_LOG_ERROR;
    }
    return ANDROID_LOG_INFO;
}

void android_tc_log_callback(tc_log_level level, const char* message) {
    __android_log_print(
        android_log_priority(level),
        kLogTag,
        "%s",
        message ? message : ""
    );
}

void install_android_tc_log_callback_once() {
    static std::once_flag once;
    std::call_once(once, []() {
        tc_log_set_callback(android_tc_log_callback);
    });
}

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

bool openxr_instance_extension_available(OpenXRDispatch& xr, const char* extension_name) {
    if (!xr.enumerate_instance_extension_properties || !extension_name) {
        return false;
    }

    uint32_t extension_count = 0;
    XrResult result = xr.enumerate_instance_extension_properties(
        nullptr,
        0,
        &extension_count,
        nullptr
    );
    if (XR_FAILED(result)) {
        __android_log_print(
            ANDROID_LOG_WARN,
            kLogTag,
            "xrEnumerateInstanceExtensionProperties count failed: %d",
            result
        );
        return false;
    }

    std::vector<XrExtensionProperties> extensions(extension_count);
    for (XrExtensionProperties& extension : extensions) {
        extension.type = XR_TYPE_EXTENSION_PROPERTIES;
    }
    result = xr.enumerate_instance_extension_properties(
        nullptr,
        extension_count,
        &extension_count,
        extensions.data()
    );
    if (XR_FAILED(result)) {
        __android_log_print(
            ANDROID_LOG_WARN,
            kLogTag,
            "xrEnumerateInstanceExtensionProperties list failed: %d",
            result
        );
        return false;
    }

    for (const XrExtensionProperties& extension : extensions) {
        if (std::strcmp(extension.extensionName, extension_name) == 0) {
            return true;
        }
    }
    return false;
}

std::string format_refresh_rates(const std::vector<float>& rates) {
    std::ostringstream out;
    for (size_t i = 0; i < rates.size(); ++i) {
        if (i > 0) {
            out << ", ";
        }
        out << rates[i];
    }
    return out.str();
}

void configure_display_refresh_rate(OpenXRDispatch& xr, XrSession session) {
    if (!xr.enumerate_display_refresh_rates ||
        !xr.get_display_refresh_rate ||
        !xr.request_display_refresh_rate) {
        return;
    }

    uint32_t rate_count = 0;
    XrResult result = xr.enumerate_display_refresh_rates(session, 0, &rate_count, nullptr);
    if (XR_FAILED(result) || rate_count == 0) {
        __android_log_print(
            ANDROID_LOG_WARN,
            kLogTag,
            "xrEnumerateDisplayRefreshRatesFB count failed: %d count=%u",
            result,
            rate_count
        );
        return;
    }

    std::vector<float> rates(rate_count);
    result = xr.enumerate_display_refresh_rates(session, rate_count, &rate_count, rates.data());
    if (XR_FAILED(result)) {
        __android_log_print(
            ANDROID_LOG_WARN,
            kLogTag,
            "xrEnumerateDisplayRefreshRatesFB list failed: %d",
            result
        );
        return;
    }
    rates.resize(rate_count);

    float current_rate = 0.0f;
    result = xr.get_display_refresh_rate(session, &current_rate);
    if (XR_SUCCEEDED(result)) {
        __android_log_print(
            ANDROID_LOG_INFO,
            kLogTag,
            "OpenXR display refresh current=%.1f supported=[%s]",
            current_rate,
            format_refresh_rates(rates).c_str()
        );
    } else {
        __android_log_print(
            ANDROID_LOG_WARN,
            kLogTag,
            "xrGetDisplayRefreshRateFB failed: %d supported=[%s]",
            result,
            format_refresh_rates(rates).c_str()
        );
    }

    float requested_rate = 0.0f;
    for (float rate : rates) {
        if (std::fabs(rate - 72.0f) < 0.25f) {
            requested_rate = rate;
            break;
        }
    }
    if (requested_rate == 0.0f) {
        for (float rate : rates) {
            if (rate > requested_rate) {
                requested_rate = rate;
            }
        }
    }
    if (requested_rate == 0.0f) {
        return;
    }

    result = xr.request_display_refresh_rate(session, requested_rate);
    if (XR_SUCCEEDED(result)) {
        __android_log_print(
            ANDROID_LOG_INFO,
            kLogTag,
            "OpenXR requested display refresh %.1f Hz",
            requested_rate
        );
    } else {
        __android_log_print(
            ANDROID_LOG_WARN,
            kLogTag,
            "xrRequestDisplayRefreshRateFB %.1f Hz failed: %d",
            requested_rate,
            result
        );
    }
}

bool xr_string_to_path(
    OpenXRDispatch& xr,
    XrInstance instance,
    const char* path_text,
    XrPath& out
) {
    out = XR_NULL_PATH;
    if (!xr.string_to_path) {
        tc_log_error("[OpenXR input] xrStringToPath is unavailable");
        return false;
    }

    XrResult result = xr.string_to_path(instance, path_text, &out);
    if (XR_FAILED(result) || out == XR_NULL_PATH) {
        tc_log_error("[OpenXR input] xrStringToPath('%s') failed: %d", path_text, result);
        return false;
    }
    return true;
}



struct XrControllerActions {
    OpenXRDispatch* xr = nullptr;
    XrInstance instance = XR_NULL_HANDLE;
    XrActionSet action_set = XR_NULL_HANDLE;
    XrAction thumbstick_axis = XR_NULL_HANDLE;
    XrPath left_hand = XR_NULL_PATH;
    XrPath right_hand = XR_NULL_PATH;
    termin::xr::XrRigInputState rig_state;
    bool initialized = false;
    bool attached = false;
    bool registered = false;

    bool init(OpenXRDispatch& dispatch, XrInstance xr_instance) {
        xr = &dispatch;
        instance = xr_instance;

        if (!xr->create_action_set ||
            !xr->create_action ||
            !xr->suggest_interaction_profile_bindings ||
            !xr->string_to_path) {
            tc_log_error("[OpenXR input] required action functions are unavailable");
            return false;
        }

        if (!xr_string_to_path(*xr, instance, "/user/hand/left", left_hand) ||
            !xr_string_to_path(*xr, instance, "/user/hand/right", right_hand)) {
            return false;
        }

        XrActionSetCreateInfo action_set_info{};
        action_set_info.type = XR_TYPE_ACTION_SET_CREATE_INFO;
        std::strncpy(action_set_info.actionSetName, "termin_xr_controllers", XR_MAX_ACTION_SET_NAME_SIZE - 1);
        std::strncpy(action_set_info.localizedActionSetName, "Termin XR Controllers", XR_MAX_LOCALIZED_ACTION_SET_NAME_SIZE - 1);
        action_set_info.priority = 0;

        XrResult result = xr->create_action_set(instance, &action_set_info, &action_set);
        if (XR_FAILED(result) || action_set == XR_NULL_HANDLE) {
            tc_log_error("[OpenXR input] xrCreateActionSet failed: %d", result);
            return false;
        }

        XrPath subaction_paths[2] = {left_hand, right_hand};
        XrActionCreateInfo action_info{};
        action_info.type = XR_TYPE_ACTION_CREATE_INFO;
        action_info.actionType = XR_ACTION_TYPE_VECTOR2F_INPUT;
        action_info.countSubactionPaths = 2;
        action_info.subactionPaths = subaction_paths;
        std::strncpy(action_info.actionName, "thumbstick_axis", XR_MAX_ACTION_NAME_SIZE - 1);
        std::strncpy(action_info.localizedActionName, "Thumbstick Axis", XR_MAX_LOCALIZED_ACTION_NAME_SIZE - 1);

        result = xr->create_action(action_set, &action_info, &thumbstick_axis);
        if (XR_FAILED(result) || thumbstick_axis == XR_NULL_HANDLE) {
            tc_log_error("[OpenXR input] xrCreateAction thumbstick_axis failed: %d", result);
            return false;
        }

        XrPath oculus_touch_profile = XR_NULL_PATH;
        XrPath left_thumbstick = XR_NULL_PATH;
        XrPath right_thumbstick = XR_NULL_PATH;
        if (!xr_string_to_path(*xr, instance, "/interaction_profiles/oculus/touch_controller", oculus_touch_profile) ||
            !xr_string_to_path(*xr, instance, "/user/hand/left/input/thumbstick", left_thumbstick) ||
            !xr_string_to_path(*xr, instance, "/user/hand/right/input/thumbstick", right_thumbstick)) {
            return false;
        }

        XrActionSuggestedBinding suggested_bindings[2]{};
        suggested_bindings[0].action = thumbstick_axis;
        suggested_bindings[0].binding = left_thumbstick;
        suggested_bindings[1].action = thumbstick_axis;
        suggested_bindings[1].binding = right_thumbstick;

        XrInteractionProfileSuggestedBinding suggested_binding_info{};
        suggested_binding_info.type = XR_TYPE_INTERACTION_PROFILE_SUGGESTED_BINDING;
        suggested_binding_info.interactionProfile = oculus_touch_profile;
        suggested_binding_info.countSuggestedBindings = 2;
        suggested_binding_info.suggestedBindings = suggested_bindings;

        result = xr->suggest_interaction_profile_bindings(instance, &suggested_binding_info);
        if (XR_FAILED(result)) {
            tc_log_error("[OpenXR input] xrSuggestInteractionProfileBindings failed: %d", result);
            return false;
        }

        rig_state.id = "xr";
        termin::xr::XrInput::register_state(rig_state.id, &rig_state);
        registered = true;
        initialized = true;
        tc_log_info("[OpenXR input] XR controller action set initialized");
        return true;
    }

    bool attach(XrSession session) {
        if (!initialized || !xr || !xr->attach_session_action_sets || attached) {
            return initialized && attached;
        }

        XrSessionActionSetsAttachInfo attach_info{};
        attach_info.type = XR_TYPE_SESSION_ACTION_SETS_ATTACH_INFO;
        attach_info.countActionSets = 1;
        attach_info.actionSets = &action_set;

        XrResult result = xr->attach_session_action_sets(session, &attach_info);
        if (XR_FAILED(result)) {
            tc_log_error("[OpenXR input] xrAttachSessionActionSets failed: %d", result);
            return false;
        }
        attached = true;
        tc_log_info("[OpenXR input] XR controller action set attached");
        return true;
    }

    void update_head_axes(
        const XrView& view,
        const termin::Mat44& origin_from_xr_reference,
        bool orientation_valid
    ) {
        if (!orientation_valid) {
            rig_state.head_axes_active = false;
            return;
        }

        const XrQuaternionf& q = view.pose.orientation;
        const termin::Vec3 forward_in_reference = xr_direction_to_scene_direction(
            rotate_xr_vector(q, XrVector3f{0.0f, 0.0f, -1.0f})
        );
        const termin::Vec3 right_in_reference = xr_direction_to_scene_direction(
            rotate_xr_vector(q, XrVector3f{1.0f, 0.0f, 0.0f})
        );
        rig_state.head_forward_in_origin =
            origin_from_xr_reference.transform_direction(forward_in_reference).normalized();
        rig_state.head_right_in_origin =
            origin_from_xr_reference.transform_direction(right_in_reference).normalized();
        rig_state.head_axes_active = true;
    }

    void sync(XrSession session, uint64_t frame_index) {
        if (!initialized || !attached || !xr || !xr->sync_actions || !xr->get_action_state_vector2f) {
            return;
        }

        XrActiveActionSet active_action_set{};
        active_action_set.actionSet = action_set;
        active_action_set.subactionPath = XR_NULL_PATH;

        XrActionsSyncInfo sync_info{};
        sync_info.type = XR_TYPE_ACTIONS_SYNC_INFO;
        sync_info.countActiveActionSets = 1;
        sync_info.activeActionSets = &active_action_set;

        XrResult result = xr->sync_actions(session, &sync_info);
        if (XR_FAILED(result)) {
            tc_log_error("[OpenXR input] xrSyncActions failed: %d", result);
            rig_state.left.thumbstick.active = false;
            rig_state.right.thumbstick.active = false;
            return;
        }

        update_thumbstick(session, left_hand, rig_state.left.thumbstick);
        update_thumbstick(session, right_hand, rig_state.right.thumbstick);
        rig_state.frame_index = frame_index;
    }

    void update_thumbstick(
        XrSession session,
        XrPath subaction_path,
        termin::xr::XrAxis2State& out
    ) {
        XrActionStateGetInfo get_info{};
        get_info.type = XR_TYPE_ACTION_STATE_GET_INFO;
        get_info.action = thumbstick_axis;
        get_info.subactionPath = subaction_path;

        XrActionStateVector2f state{};
        state.type = XR_TYPE_ACTION_STATE_VECTOR2F;
        XrResult result = xr->get_action_state_vector2f(session, &get_info, &state);
        if (XR_FAILED(result)) {
            tc_log_error("[OpenXR input] xrGetActionStateVector2f failed: %d", result);
            out.active = false;
            out.value = termin::Vec2::zero();
            return;
        }

        out.active = state.isActive == XR_TRUE;
        out.changed_since_last_sync = state.changedSinceLastSync == XR_TRUE;
        out.value = termin::Vec2{
            static_cast<double>(state.currentState.x),
            static_cast<double>(state.currentState.y)
        };
    }

    void destroy() {
        if (registered) {
            termin::xr::XrInput::unregister_state(rig_state.id);
            registered = false;
        }
        if (xr && thumbstick_axis != XR_NULL_HANDLE && xr->destroy_action) {
            xr->destroy_action(thumbstick_axis);
        }
        if (xr && action_set != XR_NULL_HANDLE && xr->destroy_action_set) {
            xr->destroy_action_set(action_set);
        }
        thumbstick_axis = XR_NULL_HANDLE;
        action_set = XR_NULL_HANDLE;
        initialized = false;
        attached = false;
    }
};

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



#include "openxr_android_scene_runtime.hpp"
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
    install_android_tc_log_callback_once();
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
    if (!load_instance_proc(xr, XR_NULL_HANDLE, "xrEnumerateInstanceExtensionProperties",
            reinterpret_cast<PFN_xrVoidFunction*>(&xr.enumerate_instance_extension_properties))) {
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

    std::vector<const char*> enabled_extensions = {
        XR_KHR_ANDROID_CREATE_INSTANCE_EXTENSION_NAME,
        XR_KHR_VULKAN_ENABLE_EXTENSION_NAME,
    };
    const bool display_refresh_rate_available =
        openxr_instance_extension_available(xr, XR_FB_DISPLAY_REFRESH_RATE_EXTENSION_NAME);
    if (display_refresh_rate_available) {
        enabled_extensions.push_back(XR_FB_DISPLAY_REFRESH_RATE_EXTENSION_NAME);
        __android_log_print(
            ANDROID_LOG_INFO,
            kLogTag,
            "OpenXR extension enabled: %s",
            XR_FB_DISPLAY_REFRESH_RATE_EXTENSION_NAME
        );
    } else {
        __android_log_print(
            ANDROID_LOG_INFO,
            kLogTag,
            "OpenXR extension unavailable: %s",
            XR_FB_DISPLAY_REFRESH_RATE_EXTENSION_NAME
        );
    }

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
        static_cast<uint32_t>(enabled_extensions.size());
    instance_create_info.enabledExtensionNames = enabled_extensions.data();

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
    load_instance_proc(xr, instance, "xrStringToPath", reinterpret_cast<PFN_xrVoidFunction*>(&xr.string_to_path));
    load_instance_proc(xr, instance, "xrCreateActionSet", reinterpret_cast<PFN_xrVoidFunction*>(&xr.create_action_set));
    load_instance_proc(xr, instance, "xrDestroyActionSet", reinterpret_cast<PFN_xrVoidFunction*>(&xr.destroy_action_set));
    load_instance_proc(xr, instance, "xrCreateAction", reinterpret_cast<PFN_xrVoidFunction*>(&xr.create_action));
    load_instance_proc(xr, instance, "xrDestroyAction", reinterpret_cast<PFN_xrVoidFunction*>(&xr.destroy_action));
    load_instance_proc(xr, instance, "xrSuggestInteractionProfileBindings", reinterpret_cast<PFN_xrVoidFunction*>(&xr.suggest_interaction_profile_bindings));
    load_instance_proc(xr, instance, "xrAttachSessionActionSets", reinterpret_cast<PFN_xrVoidFunction*>(&xr.attach_session_action_sets));
    load_instance_proc(xr, instance, "xrSyncActions", reinterpret_cast<PFN_xrVoidFunction*>(&xr.sync_actions));
    load_instance_proc(xr, instance, "xrGetActionStateVector2f", reinterpret_cast<PFN_xrVoidFunction*>(&xr.get_action_state_vector2f));
    load_instance_proc(xr, instance, "xrGetVulkanInstanceExtensionsKHR", reinterpret_cast<PFN_xrVoidFunction*>(&xr.get_vulkan_instance_extensions));
    load_instance_proc(xr, instance, "xrGetVulkanDeviceExtensionsKHR", reinterpret_cast<PFN_xrVoidFunction*>(&xr.get_vulkan_device_extensions));
    load_instance_proc(xr, instance, "xrGetVulkanGraphicsDeviceKHR", reinterpret_cast<PFN_xrVoidFunction*>(&xr.get_vulkan_graphics_device));
    load_instance_proc(xr, instance, "xrGetVulkanGraphicsRequirementsKHR", reinterpret_cast<PFN_xrVoidFunction*>(&xr.get_vulkan_requirements));
    if (display_refresh_rate_available) {
        load_instance_proc(xr, instance, "xrEnumerateDisplayRefreshRatesFB", reinterpret_cast<PFN_xrVoidFunction*>(&xr.enumerate_display_refresh_rates));
        load_instance_proc(xr, instance, "xrGetDisplayRefreshRateFB", reinterpret_cast<PFN_xrVoidFunction*>(&xr.get_display_refresh_rate));
        load_instance_proc(xr, instance, "xrRequestDisplayRefreshRateFB", reinterpret_cast<PFN_xrVoidFunction*>(&xr.request_display_refresh_rate));
    }

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
    configure_display_refresh_rate(xr, session);

    OpenXRRuntimeScene runtime_scene;
    const bool runtime_scene_requested = !asset_root.empty();
    const bool runtime_scene_ready =
        runtime_scene_requested && runtime_scene.load(asset_root);

    XrReferenceSpaceCreateInfo space_create_info{};
    space_create_info.type = XR_TYPE_REFERENCE_SPACE_CREATE_INFO;
    space_create_info.referenceSpaceType =
        runtime_scene_ready &&
        runtime_scene.xr_origin &&
        runtime_scene.xr_origin->reference_space == termin::XrReferenceSpace::Stage
            ? XR_REFERENCE_SPACE_TYPE_STAGE
            : XR_REFERENCE_SPACE_TYPE_LOCAL;
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
        runtime_scene.destroy();
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
        runtime_scene.destroy();
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
    __android_log_print(
        ANDROID_LOG_INFO,
        kLogTag,
        "OpenXR swapchain: views=%u size=%ux%u samples=%u recommendedSamples=%u maxSamples=%u",
        view_count,
        swapchain_create_info.width,
        swapchain_create_info.height,
        swapchain_create_info.sampleCount,
        view_configs[0].recommendedSwapchainSampleCount,
        view_configs[0].maxSwapchainSampleCount
    );

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
            runtime_scene.destroy();
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

    XrControllerActions controller_actions;
    if (controller_actions.init(xr, instance)) {
        controller_actions.attach(session);
    } else {
        tc_log_error("[OpenXR input] XR controller actions are disabled");
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
    XrSessionState current_session_state = XR_SESSION_STATE_UNKNOWN;
    uint64_t frame_index = 0;
    using FrameClock = std::chrono::steady_clock;
    auto fps_window_start = FrameClock::now();
    XrTime fps_window_first_display_time = 0;
    XrTime fps_window_last_display_time = 0;
    uint64_t fps_window_frames = 0;
    uint64_t fps_window_rendered_frames = 0;
    uint64_t fps_window_should_skip_frames = 0;
    double fps_window_wait_frame_ms = 0.0;
    double fps_window_wait_frame_min_ms = -1.0;
    double fps_window_wait_frame_max_ms = 0.0;
    double fps_window_swapchain_wait_ms = 0.0;
    double fps_window_render_ms = 0.0;
    double fps_window_frame_cpu_ms = 0.0;
    double fps_window_predicted_period_ms = 0.0;
    double fps_window_predicted_delta_ms = 0.0;
    double fps_window_predicted_delta_min_ms = -1.0;
    double fps_window_predicted_delta_max_ms = 0.0;
    uint64_t fps_window_predicted_delta_count = 0;
    XrTime last_predicted_display_time = 0;
    auto millis_between = [](FrameClock::time_point begin, FrameClock::time_point end) {
        return std::chrono::duration<double, std::milli>(end - begin).count();
    };
    auto xr_duration_to_ms = [](XrDuration duration) {
        return static_cast<double>(duration) * 1e-6;
    };

    log_info("OpenXR color smoke loop ready");
    while (g_smoke.running.load()) {
        const auto frame_cpu_start = FrameClock::now();
        double frame_wait_frame_ms = 0.0;
        double frame_swapchain_wait_ms = 0.0;
        double frame_render_ms = 0.0;
        bool frame_rendered = false;

        XrEventDataBuffer event{};
        event.type = XR_TYPE_EVENT_DATA_BUFFER;
        while (xr.poll_event(instance, &event) == XR_SUCCESS) {
            if (event.type == XR_TYPE_EVENT_DATA_SESSION_STATE_CHANGED) {
                const auto* state_event = reinterpret_cast<const XrEventDataSessionStateChanged*>(&event);
                current_session_state = state_event->state;
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
        const auto wait_frame_begin = FrameClock::now();
        result = xr.wait_frame(session, &wait_info, &frame_state);
        frame_wait_frame_ms = millis_between(wait_frame_begin, FrameClock::now());
        if (fps_window_wait_frame_min_ms < 0.0 || frame_wait_frame_ms < fps_window_wait_frame_min_ms) {
            fps_window_wait_frame_min_ms = frame_wait_frame_ms;
        }
        if (frame_wait_frame_ms > fps_window_wait_frame_max_ms) {
            fps_window_wait_frame_max_ms = frame_wait_frame_ms;
        }
        if (XR_FAILED(result)) {
            __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrWaitFrame failed: %d", result);
            continue;
        }

        fps_window_predicted_period_ms += xr_duration_to_ms(frame_state.predictedDisplayPeriod);
        if (last_predicted_display_time != 0 &&
            frame_state.predictedDisplayTime > last_predicted_display_time) {
            const double predicted_delta_ms =
                static_cast<double>(frame_state.predictedDisplayTime - last_predicted_display_time) * 1e-6;
            fps_window_predicted_delta_ms += predicted_delta_ms;
            ++fps_window_predicted_delta_count;
            if (fps_window_predicted_delta_min_ms < 0.0 ||
                predicted_delta_ms < fps_window_predicted_delta_min_ms) {
                fps_window_predicted_delta_min_ms = predicted_delta_ms;
            }
            if (predicted_delta_ms > fps_window_predicted_delta_max_ms) {
                fps_window_predicted_delta_max_ms = predicted_delta_ms;
            }
        }
        last_predicted_display_time = frame_state.predictedDisplayTime;

        XrFrameBeginInfo begin_frame_info{};
        begin_frame_info.type = XR_TYPE_FRAME_BEGIN_INFO;
        result = xr.begin_frame(session, &begin_frame_info);
        if (XR_FAILED(result)) {
            __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrBeginFrame failed: %d", result);
            continue;
        }

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
                const bool head_orientation_valid =
                    (view_state.viewStateFlags & XR_VIEW_STATE_ORIENTATION_VALID_BIT) != 0;
                if (located_view_count > 0) {
                    if (runtime_scene_ready) {
                        runtime_scene.update_reference_alignment(views[0], view_state.viewStateFlags);
                    }
                    controller_actions.update_head_axes(
                        views[0],
                        runtime_scene_ready
                            ? runtime_scene.origin_from_xr_reference
                            : termin::Mat44::identity(),
                        head_orientation_valid
                    );
                }
                controller_actions.sync(session, frame_index);
                if (runtime_scene_ready) {
                    const double frame_dt =
                        std::max(1e-6, static_cast<double>(frame_state.predictedDisplayPeriod) * 1e-9);
                    runtime_scene.update(frame_dt);
                }

                std::vector<XrSwapchain> swapchains_to_release;
                swapchains_to_release.reserve(view_count);
                const bool runtime_scene_frame_open = runtime_scene_ready && runtime_scene.begin_render_frame();
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
                    const auto wait_swapchain_begin = FrameClock::now();
                    result = xr.wait_swapchain_image(color_swapchains[eye], &wait_swapchain_info);
                    frame_swapchain_wait_ms += millis_between(wait_swapchain_begin, FrameClock::now());
                    if (XR_FAILED(result)) {
                        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrWaitSwapchainImage[%u] failed: %d", eye, result);
                        continue;
                    }
                    swapchains_to_release.push_back(color_swapchains[eye]);

                    const tgfx::TextureHandle color_texture = swapchain_textures[eye][image_index];
                    if (auto* color_resource = render_device->get_texture(color_texture)) {
                        color_resource->current_layout = VK_IMAGE_LAYOUT_UNDEFINED;
                    }
                    if (auto* depth_resource = render_device->get_texture(depth_texture)) {
                        depth_resource->current_layout = VK_IMAGE_LAYOUT_UNDEFINED;
                    }

                    const auto render_begin = FrameClock::now();
                    if (runtime_scene_ready) {
                        runtime_scene.render_eye(
                            color_texture,
                            depth_texture,
                            swapchain_create_info.width,
                            swapchain_create_info.height,
                            tgfx_color_format,
                            views[eye],
                            eye
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
                    frame_render_ms += millis_between(render_begin, FrameClock::now());

                    layer_views[eye].pose = views[eye].pose;
                    layer_views[eye].fov = views[eye].fov;
                    layer_views[eye].subImage.swapchain = color_swapchains[eye];
                    layer_views[eye].subImage.imageRect.offset = {0, 0};
                    layer_views[eye].subImage.imageRect.extent = {
                        static_cast<int32_t>(swapchain_create_info.width),
                        static_cast<int32_t>(swapchain_create_info.height)
                    };
                    layer_views[eye].subImage.imageArrayIndex = 0;
                }

                if (runtime_scene_frame_open) {
                    const auto render_submit_begin = FrameClock::now();
                    runtime_scene.end_render_frame();
                    frame_render_ms += millis_between(render_submit_begin, FrameClock::now());
                }

                for (XrSwapchain swapchain : swapchains_to_release) {
                    XrSwapchainImageReleaseInfo release_info{};
                    release_info.type = XR_TYPE_SWAPCHAIN_IMAGE_RELEASE_INFO;
                    result = xr.release_swapchain_image(swapchain, &release_info);
                    if (XR_FAILED(result)) {
                        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrReleaseSwapchainImage failed: %d", result);
                    }
                }

                layers[0] = reinterpret_cast<XrCompositionLayerBaseHeader*>(&projection_layer);
                layer_count = 1;
                ++frame_index;
                frame_rendered = true;
            }
        } else {
            ++fps_window_should_skip_frames;
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

        const auto frame_cpu_end = FrameClock::now();
        ++fps_window_frames;
        if (frame_rendered) {
            ++fps_window_rendered_frames;
        }
        if (fps_window_first_display_time == 0) {
            fps_window_first_display_time = frame_state.predictedDisplayTime;
        }
        fps_window_last_display_time = frame_state.predictedDisplayTime;
        fps_window_wait_frame_ms += frame_wait_frame_ms;
        fps_window_swapchain_wait_ms += frame_swapchain_wait_ms;
        fps_window_render_ms += frame_render_ms;
        fps_window_frame_cpu_ms += millis_between(frame_cpu_start, frame_cpu_end);

        const double wall_seconds =
            std::chrono::duration<double>(frame_cpu_end - fps_window_start).count();
        if (wall_seconds >= 2.0 && fps_window_frames > 0) {
            const double wall_fps = static_cast<double>(fps_window_frames) / wall_seconds;
            const double rendered_fps = static_cast<double>(fps_window_rendered_frames) / wall_seconds;
            double predicted_hz = 0.0;
            if (fps_window_last_display_time > fps_window_first_display_time) {
                const double predicted_seconds =
                    static_cast<double>(fps_window_last_display_time - fps_window_first_display_time) * 1e-9;
                if (predicted_seconds > 0.0) {
                    predicted_hz =
                        static_cast<double>(fps_window_frames - 1) / predicted_seconds;
                }
            }
            const double inv_frames = 1.0 / static_cast<double>(fps_window_frames);
            const double inv_predicted_delta =
                fps_window_predicted_delta_count > 0
                    ? 1.0 / static_cast<double>(fps_window_predicted_delta_count)
                    : 0.0;
            __android_log_print(
                ANDROID_LOG_INFO,
                kLogTag,
                "XR FPS: state=%s wall=%.1f rendered=%.1f predictedHz=%.1f "
                "avgMs{frame=%.2f waitFrame=%.2f waitMin=%.2f waitMax=%.2f swapWait=%.2f render=%.2f period=%.2f predDelta=%.2f predDeltaMin=%.2f predDeltaMax=%.2f} "
                "frames=%llu renderedFrames=%llu shouldSkip=%llu",
                session_state_name(current_session_state),
                wall_fps,
                rendered_fps,
                predicted_hz,
                fps_window_frame_cpu_ms * inv_frames,
                fps_window_wait_frame_ms * inv_frames,
                fps_window_wait_frame_min_ms < 0.0 ? 0.0 : fps_window_wait_frame_min_ms,
                fps_window_wait_frame_max_ms,
                fps_window_swapchain_wait_ms * inv_frames,
                fps_window_render_ms * inv_frames,
                fps_window_predicted_period_ms * inv_frames,
                fps_window_predicted_delta_ms * inv_predicted_delta,
                fps_window_predicted_delta_min_ms < 0.0 ? 0.0 : fps_window_predicted_delta_min_ms,
                fps_window_predicted_delta_max_ms,
                static_cast<unsigned long long>(fps_window_frames),
                static_cast<unsigned long long>(fps_window_rendered_frames),
                static_cast<unsigned long long>(fps_window_should_skip_frames)
            );

            fps_window_start = frame_cpu_end;
            fps_window_first_display_time = 0;
            fps_window_last_display_time = 0;
            fps_window_frames = 0;
            fps_window_rendered_frames = 0;
            fps_window_should_skip_frames = 0;
            fps_window_wait_frame_ms = 0.0;
            fps_window_wait_frame_min_ms = -1.0;
            fps_window_wait_frame_max_ms = 0.0;
            fps_window_swapchain_wait_ms = 0.0;
            fps_window_render_ms = 0.0;
            fps_window_frame_cpu_ms = 0.0;
            fps_window_predicted_period_ms = 0.0;
            fps_window_predicted_delta_ms = 0.0;
            fps_window_predicted_delta_min_ms = -1.0;
            fps_window_predicted_delta_max_ms = 0.0;
            fps_window_predicted_delta_count = 0;
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
    controller_actions.destroy();
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
    install_android_tc_log_callback_once();
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
