#include "openxr_android_runtime_internal.hpp"

#include <array>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <sstream>
#include <stdexcept>

#include <tcbase/tc_log.h>
#include <tcbase/trent/json.h>
#include <termin/entity/entity.hpp>
#include <termin/geom/vec3.hpp>

#include "openxr_math.hpp"

#if defined(__ANDROID__)
#include <android/log.h>
#endif

namespace termin::openxr::detail {

#if defined(TERMIN_OPENXR_HAS_HEADERS) && defined(__ANDROID__)
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

void android_tc_log_callback(tc_log_level level, const char *message) {
    __android_log_print(android_log_priority(level), kLogTag, "%s", message ? message : "");
}

void install_android_tc_log_callback_once() {
    static std::once_flag once;
    std::call_once(once, []() { tc_log_set_callback(android_tc_log_callback); });
}

void log_info(const char *message) { __android_log_print(ANDROID_LOG_INFO, kLogTag, "%s", message ? message : ""); }

void log_error(const char *stage, const char *detail) {
    __android_log_print(ANDROID_LOG_ERROR, kLogTag, "%s: %s", stage ? stage : "OpenXR smoke", detail ? detail : "");
}

const unsigned char kSmokeVertexSpv[] = {
    0x03, 0x02, 0x23, 0x07, 0x00, 0x05, 0x01, 0x00, 0x0b, 0x00, 0x0d, 0x00, 0x27, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x11, 0x00, 0x02, 0x00, 0x01, 0x00, 0x00, 0x00, 0x0b, 0x00, 0x06, 0x00, 0x01, 0x00, 0x00, 0x00, 0x47, 0x4c,
    0x53, 0x4c, 0x2e, 0x73, 0x74, 0x64, 0x2e, 0x34, 0x35, 0x30, 0x00, 0x00, 0x00, 0x00, 0x0e, 0x00, 0x03, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x0f, 0x00, 0x0a, 0x00, 0x00, 0x00, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00,
    0x6d, 0x61, 0x69, 0x6e, 0x00, 0x00, 0x00, 0x00, 0x09, 0x00, 0x00, 0x00, 0x0b, 0x00, 0x00, 0x00, 0x13, 0x00, 0x00,
    0x00, 0x19, 0x00, 0x00, 0x00, 0x1d, 0x00, 0x00, 0x00, 0x47, 0x00, 0x04, 0x00, 0x09, 0x00, 0x00, 0x00, 0x1e, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x47, 0x00, 0x04, 0x00, 0x0b, 0x00, 0x00, 0x00, 0x1e, 0x00, 0x00, 0x00, 0x01,
    0x00, 0x00, 0x00, 0x48, 0x00, 0x05, 0x00, 0x11, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0b, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x48, 0x00, 0x05, 0x00, 0x11, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x0b, 0x00, 0x00,
    0x00, 0x01, 0x00, 0x00, 0x00, 0x48, 0x00, 0x05, 0x00, 0x11, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x0b, 0x00,
    0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x48, 0x00, 0x05, 0x00, 0x11, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x0b,
    0x00, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00, 0x47, 0x00, 0x03, 0x00, 0x11, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00,
    0x48, 0x00, 0x04, 0x00, 0x17, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x05, 0x00, 0x00, 0x00, 0x48, 0x00, 0x05,
    0x00, 0x17, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x23, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x48, 0x00,
    0x05, 0x00, 0x17, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00, 0x10, 0x00, 0x00, 0x00, 0x47,
    0x00, 0x03, 0x00, 0x17, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x47, 0x00, 0x04, 0x00, 0x1d, 0x00, 0x00, 0x00,
    0x1e, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x13, 0x00, 0x02, 0x00, 0x02, 0x00, 0x00, 0x00, 0x21, 0x00, 0x03,
    0x00, 0x03, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x16, 0x00, 0x03, 0x00, 0x06, 0x00, 0x00, 0x00, 0x20, 0x00,
    0x00, 0x00, 0x17, 0x00, 0x04, 0x00, 0x07, 0x00, 0x00, 0x00, 0x06, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x20,
    0x00, 0x04, 0x00, 0x08, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00, 0x3b, 0x00, 0x04, 0x00,
    0x08, 0x00, 0x00, 0x00, 0x09, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x20, 0x00, 0x04, 0x00, 0x0a, 0x00, 0x00,
    0x00, 0x01, 0x00, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00, 0x3b, 0x00, 0x04, 0x00, 0x0a, 0x00, 0x00, 0x00, 0x0b, 0x00,
    0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x17, 0x00, 0x04, 0x00, 0x0d, 0x00, 0x00, 0x00, 0x06, 0x00, 0x00, 0x00, 0x04,
    0x00, 0x00, 0x00, 0x15, 0x00, 0x04, 0x00, 0x0e, 0x00, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x2b, 0x00, 0x04, 0x00, 0x0e, 0x00, 0x00, 0x00, 0x0f, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x1c, 0x00, 0x04,
    0x00, 0x10, 0x00, 0x00, 0x00, 0x06, 0x00, 0x00, 0x00, 0x0f, 0x00, 0x00, 0x00, 0x1e, 0x00, 0x06, 0x00, 0x11, 0x00,
    0x00, 0x00, 0x0d, 0x00, 0x00, 0x00, 0x06, 0x00, 0x00, 0x00, 0x10, 0x00, 0x00, 0x00, 0x10, 0x00, 0x00, 0x00, 0x20,
    0x00, 0x04, 0x00, 0x12, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x11, 0x00, 0x00, 0x00, 0x3b, 0x00, 0x04, 0x00,
    0x12, 0x00, 0x00, 0x00, 0x13, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x15, 0x00, 0x04, 0x00, 0x14, 0x00, 0x00,
    0x00, 0x20, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x2b, 0x00, 0x04, 0x00, 0x14, 0x00, 0x00, 0x00, 0x15, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x18, 0x00, 0x04, 0x00, 0x16, 0x00, 0x00, 0x00, 0x0d, 0x00, 0x00, 0x00, 0x04,
    0x00, 0x00, 0x00, 0x1e, 0x00, 0x03, 0x00, 0x17, 0x00, 0x00, 0x00, 0x16, 0x00, 0x00, 0x00, 0x20, 0x00, 0x04, 0x00,
    0x18, 0x00, 0x00, 0x00, 0x09, 0x00, 0x00, 0x00, 0x17, 0x00, 0x00, 0x00, 0x3b, 0x00, 0x04, 0x00, 0x18, 0x00, 0x00,
    0x00, 0x19, 0x00, 0x00, 0x00, 0x09, 0x00, 0x00, 0x00, 0x20, 0x00, 0x04, 0x00, 0x1a, 0x00, 0x00, 0x00, 0x09, 0x00,
    0x00, 0x00, 0x16, 0x00, 0x00, 0x00, 0x3b, 0x00, 0x04, 0x00, 0x0a, 0x00, 0x00, 0x00, 0x1d, 0x00, 0x00, 0x00, 0x01,
    0x00, 0x00, 0x00, 0x2b, 0x00, 0x04, 0x00, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x00, 0x00, 0x00, 0x00, 0x00, 0x80, 0x3f,
    0x20, 0x00, 0x04, 0x00, 0x25, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x0d, 0x00, 0x00, 0x00, 0x36, 0x00, 0x05,
    0x00, 0x02, 0x00, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0xf8, 0x00,
    0x02, 0x00, 0x05, 0x00, 0x00, 0x00, 0x3d, 0x00, 0x04, 0x00, 0x07, 0x00, 0x00, 0x00, 0x0c, 0x00, 0x00, 0x00, 0x0b,
    0x00, 0x00, 0x00, 0x3e, 0x00, 0x03, 0x00, 0x09, 0x00, 0x00, 0x00, 0x0c, 0x00, 0x00, 0x00, 0x41, 0x00, 0x05, 0x00,
    0x1a, 0x00, 0x00, 0x00, 0x1b, 0x00, 0x00, 0x00, 0x19, 0x00, 0x00, 0x00, 0x15, 0x00, 0x00, 0x00, 0x3d, 0x00, 0x04,
    0x00, 0x16, 0x00, 0x00, 0x00, 0x1c, 0x00, 0x00, 0x00, 0x1b, 0x00, 0x00, 0x00, 0x3d, 0x00, 0x04, 0x00, 0x07, 0x00,
    0x00, 0x00, 0x1e, 0x00, 0x00, 0x00, 0x1d, 0x00, 0x00, 0x00, 0x51, 0x00, 0x05, 0x00, 0x06, 0x00, 0x00, 0x00, 0x20,
    0x00, 0x00, 0x00, 0x1e, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x51, 0x00, 0x05, 0x00, 0x06, 0x00, 0x00, 0x00,
    0x21, 0x00, 0x00, 0x00, 0x1e, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x51, 0x00, 0x05, 0x00, 0x06, 0x00, 0x00,
    0x00, 0x22, 0x00, 0x00, 0x00, 0x1e, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x50, 0x00, 0x07, 0x00, 0x0d, 0x00,
    0x00, 0x00, 0x23, 0x00, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x21, 0x00, 0x00, 0x00, 0x22, 0x00, 0x00, 0x00, 0x1f,
    0x00, 0x00, 0x00, 0x91, 0x00, 0x05, 0x00, 0x0d, 0x00, 0x00, 0x00, 0x24, 0x00, 0x00, 0x00, 0x1c, 0x00, 0x00, 0x00,
    0x23, 0x00, 0x00, 0x00, 0x41, 0x00, 0x05, 0x00, 0x25, 0x00, 0x00, 0x00, 0x26, 0x00, 0x00, 0x00, 0x13, 0x00, 0x00,
    0x00, 0x15, 0x00, 0x00, 0x00, 0x3e, 0x00, 0x03, 0x00, 0x26, 0x00, 0x00, 0x00, 0x24, 0x00, 0x00, 0x00, 0xfd, 0x00,
    0x01, 0x00, 0x38, 0x00, 0x01, 0x00};

const size_t kSmokeVertexSpvSize = sizeof(kSmokeVertexSpv);

const unsigned char kSmokeFragmentSpv[] = {
    0x03, 0x02, 0x23, 0x07, 0x00, 0x05, 0x01, 0x00, 0x0b, 0x00, 0x0d, 0x00, 0x13, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x11, 0x00, 0x02, 0x00, 0x01, 0x00, 0x00, 0x00, 0x0b, 0x00, 0x06, 0x00, 0x01, 0x00, 0x00, 0x00, 0x47, 0x4c,
    0x53, 0x4c, 0x2e, 0x73, 0x74, 0x64, 0x2e, 0x34, 0x35, 0x30, 0x00, 0x00, 0x00, 0x00, 0x0e, 0x00, 0x03, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x0f, 0x00, 0x07, 0x00, 0x04, 0x00, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00,
    0x6d, 0x61, 0x69, 0x6e, 0x00, 0x00, 0x00, 0x00, 0x09, 0x00, 0x00, 0x00, 0x0c, 0x00, 0x00, 0x00, 0x10, 0x00, 0x03,
    0x00, 0x04, 0x00, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00, 0x47, 0x00, 0x04, 0x00, 0x09, 0x00, 0x00, 0x00, 0x1e, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x47, 0x00, 0x04, 0x00, 0x0c, 0x00, 0x00, 0x00, 0x1e, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x13, 0x00, 0x02, 0x00, 0x02, 0x00, 0x00, 0x00, 0x21, 0x00, 0x03, 0x00, 0x03, 0x00, 0x00, 0x00,
    0x02, 0x00, 0x00, 0x00, 0x16, 0x00, 0x03, 0x00, 0x06, 0x00, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x17, 0x00, 0x04,
    0x00, 0x07, 0x00, 0x00, 0x00, 0x06, 0x00, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00, 0x20, 0x00, 0x04, 0x00, 0x08, 0x00,
    0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00, 0x3b, 0x00, 0x04, 0x00, 0x08, 0x00, 0x00, 0x00, 0x09,
    0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x17, 0x00, 0x04, 0x00, 0x0a, 0x00, 0x00, 0x00, 0x06, 0x00, 0x00, 0x00,
    0x03, 0x00, 0x00, 0x00, 0x20, 0x00, 0x04, 0x00, 0x0b, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x0a, 0x00, 0x00,
    0x00, 0x3b, 0x00, 0x04, 0x00, 0x0b, 0x00, 0x00, 0x00, 0x0c, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x2b, 0x00,
    0x04, 0x00, 0x06, 0x00, 0x00, 0x00, 0x0e, 0x00, 0x00, 0x00, 0x00, 0x00, 0x80, 0x3f, 0x36, 0x00, 0x05, 0x00, 0x02,
    0x00, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0xf8, 0x00, 0x02, 0x00,
    0x05, 0x00, 0x00, 0x00, 0x3d, 0x00, 0x04, 0x00, 0x0a, 0x00, 0x00, 0x00, 0x0d, 0x00, 0x00, 0x00, 0x0c, 0x00, 0x00,
    0x00, 0x51, 0x00, 0x05, 0x00, 0x06, 0x00, 0x00, 0x00, 0x0f, 0x00, 0x00, 0x00, 0x0d, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x51, 0x00, 0x05, 0x00, 0x06, 0x00, 0x00, 0x00, 0x10, 0x00, 0x00, 0x00, 0x0d, 0x00, 0x00, 0x00, 0x01,
    0x00, 0x00, 0x00, 0x51, 0x00, 0x05, 0x00, 0x06, 0x00, 0x00, 0x00, 0x11, 0x00, 0x00, 0x00, 0x0d, 0x00, 0x00, 0x00,
    0x02, 0x00, 0x00, 0x00, 0x50, 0x00, 0x07, 0x00, 0x07, 0x00, 0x00, 0x00, 0x12, 0x00, 0x00, 0x00, 0x0f, 0x00, 0x00,
    0x00, 0x10, 0x00, 0x00, 0x00, 0x11, 0x00, 0x00, 0x00, 0x0e, 0x00, 0x00, 0x00, 0x3e, 0x00, 0x03, 0x00, 0x09, 0x00,
    0x00, 0x00, 0x12, 0x00, 0x00, 0x00, 0xfd, 0x00, 0x01, 0x00, 0x38, 0x00, 0x01, 0x00};

const size_t kSmokeFragmentSpvSize = sizeof(kSmokeFragmentSpv);

const char *session_state_name(XrSessionState state) {
    switch (state) {
    case XR_SESSION_STATE_UNKNOWN:
        return "UNKNOWN";
    case XR_SESSION_STATE_IDLE:
        return "IDLE";
    case XR_SESSION_STATE_READY:
        return "READY";
    case XR_SESSION_STATE_SYNCHRONIZED:
        return "SYNCHRONIZED";
    case XR_SESSION_STATE_VISIBLE:
        return "VISIBLE";
    case XR_SESSION_STATE_FOCUSED:
        return "FOCUSED";
    case XR_SESSION_STATE_STOPPING:
        return "STOPPING";
    case XR_SESSION_STATE_LOSS_PENDING:
        return "LOSS_PENDING";
    case XR_SESSION_STATE_EXITING:
        return "EXITING";
    default:
        return "UNRECOGNIZED";
    }
}

bool load_instance_proc(const OpenXRDispatch &dispatch, XrInstance instance, const char *name,
                        PFN_xrVoidFunction *out) {
    XrResult result = dispatch.get_instance_proc_addr(instance, name, out);
    if (XR_FAILED(result) || !*out) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "xrGetInstanceProcAddr('%s') failed: %d", name,
                            static_cast<int>(result));
        return false;
    }
    return true;
}

bool openxr_instance_extension_available(OpenXRDispatch &xr, const char *extension_name) {
    if (!xr.enumerate_instance_extension_properties || !extension_name) {
        return false;
    }

    uint32_t extension_count = 0;
    XrResult result = xr.enumerate_instance_extension_properties(nullptr, 0, &extension_count, nullptr);
    if (XR_FAILED(result)) {
        __android_log_print(ANDROID_LOG_WARN, kLogTag, "xrEnumerateInstanceExtensionProperties count failed: %d",
                            result);
        return false;
    }

    std::vector<XrExtensionProperties> extensions(extension_count);
    for (XrExtensionProperties &extension : extensions) {
        extension.type = XR_TYPE_EXTENSION_PROPERTIES;
    }
    result = xr.enumerate_instance_extension_properties(nullptr, extension_count, &extension_count, extensions.data());
    if (XR_FAILED(result)) {
        __android_log_print(ANDROID_LOG_WARN, kLogTag, "xrEnumerateInstanceExtensionProperties list failed: %d",
                            result);
        return false;
    }

    for (const XrExtensionProperties &extension : extensions) {
        if (std::strcmp(extension.extensionName, extension_name) == 0) {
            return true;
        }
    }
    return false;
}

std::string format_refresh_rates(const std::vector<float> &rates) {
    std::ostringstream out;
    for (size_t i = 0; i < rates.size(); ++i) {
        if (i > 0) {
            out << ", ";
        }
        out << rates[i];
    }
    return out.str();
}

void configure_display_refresh_rate(OpenXRDispatch &xr, XrSession session) {
    if (!xr.enumerate_display_refresh_rates || !xr.get_display_refresh_rate || !xr.request_display_refresh_rate) {
        return;
    }

    uint32_t rate_count = 0;
    XrResult result = xr.enumerate_display_refresh_rates(session, 0, &rate_count, nullptr);
    if (XR_FAILED(result) || rate_count == 0) {
        __android_log_print(ANDROID_LOG_WARN, kLogTag, "xrEnumerateDisplayRefreshRatesFB count failed: %d count=%u",
                            result, rate_count);
        return;
    }

    std::vector<float> rates(rate_count);
    result = xr.enumerate_display_refresh_rates(session, rate_count, &rate_count, rates.data());
    if (XR_FAILED(result)) {
        __android_log_print(ANDROID_LOG_WARN, kLogTag, "xrEnumerateDisplayRefreshRatesFB list failed: %d", result);
        return;
    }
    rates.resize(rate_count);

    float current_rate = 0.0f;
    result = xr.get_display_refresh_rate(session, &current_rate);
    if (XR_SUCCEEDED(result)) {
        __android_log_print(ANDROID_LOG_INFO, kLogTag, "OpenXR display refresh current=%.1f supported=[%s]",
                            current_rate, format_refresh_rates(rates).c_str());
    } else {
        __android_log_print(ANDROID_LOG_WARN, kLogTag, "xrGetDisplayRefreshRateFB failed: %d supported=[%s]", result,
                            format_refresh_rates(rates).c_str());
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
        __android_log_print(ANDROID_LOG_INFO, kLogTag, "OpenXR requested display refresh %.1f Hz", requested_rate);
    } else {
        __android_log_print(ANDROID_LOG_WARN, kLogTag, "xrRequestDisplayRefreshRateFB %.1f Hz failed: %d",
                            requested_rate, result);
    }
}

bool xr_string_to_path(OpenXRDispatch &xr, XrInstance instance, const char *path_text, XrPath &out) {
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

bool XrControllerActions::init(OpenXRDispatch &dispatch, XrInstance xr_instance) {
    xr = &dispatch;
    instance = xr_instance;

    if (!xr->create_action_set || !xr->create_action || !xr->suggest_interaction_profile_bindings ||
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
    std::strncpy(action_set_info.localizedActionSetName, "Termin XR Controllers",
                 XR_MAX_LOCALIZED_ACTION_SET_NAME_SIZE - 1);
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

bool XrControllerActions::attach(XrSession session) {
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

void XrControllerActions::update_head_axes(const XrView &view, const termin::Mat44 &origin_from_xr_reference,
                                           bool orientation_valid) {
    if (!orientation_valid) {
        rig_state.head_axes_active = false;
        return;
    }

    const XrQuaternionf &q = view.pose.orientation;
    const termin::Vec3 forward_in_reference =
        xr_direction_to_scene_direction(rotate_xr_vector(q, XrVector3f{0.0f, 0.0f, -1.0f}));
    const termin::Vec3 right_in_reference =
        xr_direction_to_scene_direction(rotate_xr_vector(q, XrVector3f{1.0f, 0.0f, 0.0f}));
    rig_state.head_forward_in_origin = origin_from_xr_reference.transform_direction(forward_in_reference).normalized();
    rig_state.head_right_in_origin = origin_from_xr_reference.transform_direction(right_in_reference).normalized();
    rig_state.head_axes_active = true;
}

void XrControllerActions::sync(XrSession session, uint64_t frame_index) {
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

void XrControllerActions::update_thumbstick(XrSession session, XrPath subaction_path, termin::xr::XrAxis2State &out) {
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
    out.value = termin::Vec2{static_cast<double>(state.currentState.x), static_cast<double>(state.currentState.y)};
}

void XrControllerActions::destroy() {
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

std::vector<std::string> split_openxr_extension_string(const std::string &text) {
    std::vector<std::string> result;
    std::istringstream stream(text);
    std::string item;
    while (stream >> item) {
        result.push_back(item);
    }
    return result;
}

std::vector<const char *> extension_cstrs(const std::vector<std::string> &extensions) {
    std::vector<const char *> result;
    result.reserve(extensions.size());
    for (const std::string &extension : extensions) {
        result.push_back(extension.c_str());
    }
    return result;
}

bool query_openxr_vulkan_extensions(PFN_xrGetVulkanInstanceExtensionsKHR query, XrInstance instance,
                                    XrSystemId system_id, std::vector<std::string> &out) {
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

int64_t choose_vulkan_swapchain_format(const std::vector<int64_t> &formats) {
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

std::array<float, 16> make_scene_primitive_model_matrix(const termin::Entity &primitive, uint64_t frame_index) {
    std::array<float, 16> m = make_identity_matrix();
    const float angle = static_cast<float>(frame_index) * 0.012f;
    const float c = std::cos(angle);
    const float s = std::sin(angle);

    termin::Vec3 p = primitive.valid() ? primitive.transform().local_position() : termin::Vec3{0.0, 2.0, 0.0};

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

bool cstr_nonempty(const char *value) { return value && value[0] != '\0'; }

std::string read_runtime_text_file(const std::filesystem::path &path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        throw std::runtime_error("failed to open file: " + path.string());
    }
    std::ostringstream out;
    out << in.rdbuf();
    if (!in.good() && !in.eof()) {
        throw std::runtime_error("failed to read file: " + path.string());
    }
    return out.str();
}

const nos::trent *trent_dict_get(const nos::trent &t, const char *key) {
    if (!t.is_dict()) {
        return nullptr;
    }
    return t._get(key);
}

std::string trent_string_field(const nos::trent &t, const char *key) {
    const nos::trent *value = trent_dict_get(t, key);
    if (!value || !value->is_string()) {
        return "";
    }
    return value->as_string();
}

std::filesystem::path runtime_package_path(const std::filesystem::path &root, const std::string &rel) {
    std::filesystem::path path(rel);
    if (path.is_absolute()) {
        throw std::runtime_error("runtime package path must be relative: " + rel);
    }
    return root / path;
}

std::string normalized_pipeline_name(const char *value) {
    if (!cstr_nonempty(value) || std::strcmp(value, "(Default)") == 0) {
        return "Default";
    }
    return value;
}

#endif

} // namespace termin::openxr::detail
