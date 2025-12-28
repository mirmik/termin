#include "log_bindings.hpp"
#include <pybind11/pybind11.h>
#include <pybind11/functional.h>
#include "../../core_c/include/tc_log.h"

namespace py = pybind11;

static py::function g_py_callback;

static void py_log_callback_wrapper(tc_log_level level, const char* message) {
    if (g_py_callback) {
        py::gil_scoped_acquire acquire;
        try {
            g_py_callback(static_cast<int>(level), std::string(message));
        } catch (const py::error_already_set& e) {
            // Don't recurse if callback fails
            fprintf(stderr, "[LOG CALLBACK ERROR] %s\n", e.what());
        }
    }
}

namespace termin {

void bind_log(py::module_& m) {
    py::enum_<tc_log_level>(m, "Level")
        .value("DEBUG", TC_LOG_DEBUG)
        .value("INFO", TC_LOG_INFO)
        .value("WARN", TC_LOG_WARN)
        .value("ERROR", TC_LOG_ERROR)
        .export_values();

    m.def("set_level", &tc_log_set_level, py::arg("level"),
        "Set minimum log level");

    m.def("set_callback", [](py::object callback) {
        if (callback.is_none()) {
            g_py_callback = py::function();
            tc_log_set_callback(nullptr);
        } else {
            g_py_callback = callback.cast<py::function>();
            tc_log_set_callback(py_log_callback_wrapper);
        }
    }, py::arg("callback"),
        "Set callback for log interception. Callback signature: (level: int, message: str)");

    m.def("debug", [](const std::string& msg) {
        tc_log_debug("%s", msg.c_str());
    }, py::arg("message"), "Log debug message");

    m.def("info", [](const std::string& msg) {
        tc_log_info("%s", msg.c_str());
    }, py::arg("message"), "Log info message");

    m.def("warn", [](const std::string& msg) {
        tc_log_warn("%s", msg.c_str());
    }, py::arg("message"), "Log warning message");

    m.def("error", [](const std::string& msg) {
        tc_log_error("%s", msg.c_str());
    }, py::arg("message"), "Log error message");
}

} // namespace termin
