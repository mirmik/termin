#include "log_bindings.hpp"
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include "../../core_c/include/tc_log.h"

namespace nb = nanobind;

static nb::callable g_py_callback;

static void py_log_callback_wrapper(tc_log_level level, const char* message) {
    if (g_py_callback.is_valid()) {
        nb::gil_scoped_acquire acquire;
        try {
            g_py_callback(static_cast<int>(level), std::string(message));
        } catch (const std::exception& e) {
            // Don't recurse if callback fails
            fprintf(stderr, "[LOG CALLBACK ERROR] %s\n", e.what());
        }
    }
}

namespace termin {

void bind_log(nb::module_& m) {
    nb::enum_<tc_log_level>(m, "Level")
        .value("DEBUG", TC_LOG_DEBUG)
        .value("INFO", TC_LOG_INFO)
        .value("WARN", TC_LOG_WARN)
        .value("ERROR", TC_LOG_ERROR)
        .export_values();

    m.def("set_level", &tc_log_set_level, nb::arg("level"),
        "Set minimum log level");

    m.def("set_callback", [](nb::object callback) {
        if (callback.is_none()) {
            g_py_callback = nb::callable();
            tc_log_set_callback(nullptr);
        } else {
            g_py_callback = nb::cast<nb::callable>(callback);
            tc_log_set_callback(py_log_callback_wrapper);
        }
    }, nb::arg("callback"),
        "Set callback for log interception. Callback signature: (level: int, message: str)");

    m.def("debug", [](const std::string& msg) {
        tc_log_debug("%s", msg.c_str());
    }, nb::arg("message"), "Log debug message");

    m.def("info", [](const std::string& msg) {
        tc_log_info("%s", msg.c_str());
    }, nb::arg("message"), "Log info message");

    m.def("warn", [](const std::string& msg) {
        tc_log_warn("%s", msg.c_str());
    }, nb::arg("message"), "Log warning message");

    m.def("error", [](const std::string& msg) {
        tc_log_error("%s", msg.c_str());
    }, nb::arg("message"), "Log error message");
}

} // namespace termin
