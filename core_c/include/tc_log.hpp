#pragma once

#include "tc_log.h"
#include <string>

namespace tc {

inline void log_debug(const std::string& msg) {
    tc_log_debug("%s", msg.c_str());
}

inline void log_info(const std::string& msg) {
    tc_log_info("%s", msg.c_str());
}

inline void log_warn(const std::string& msg) {
    tc_log_warn("%s", msg.c_str());
}

inline void log_error(const std::string& msg) {
    tc_log_error("%s", msg.c_str());
}

inline void set_log_level(tc_log_level level) {
    tc_log_set_level(level);
}

inline void set_log_callback(tc_log_callback callback) {
    tc_log_set_callback(callback);
}

} // namespace tc
