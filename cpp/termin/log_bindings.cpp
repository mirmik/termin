#include "log_bindings.hpp"
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include "tc_log.hpp"

namespace nb = nanobind;

static nb::callable g_py_callback;

static void py_log_callback_wrapper(tc_log_level level, const char* message) {
    if (g_py_callback.is_valid()) {
        nb::gil_scoped_acquire acquire;
        try {
            g_py_callback(static_cast<int>(level), std::string(message));
        } catch (const std::exception&) {
            // Don't recurse if callback fails - silently drop
            // Can't log here or we'd infinite loop
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

    // Helper to format Python exception
    auto format_exception = [](nb::object exc, const std::string& context) -> std::string {
        std::string exc_str;
        try {
            exc_str = nb::cast<std::string>(nb::str(exc));
        } catch (...) {
            exc_str = "<unknown exception>";
        }
        if (context.empty()) {
            return exc_str;
        }
        return context + ": " + exc_str;
    };

    m.def("debug", [](const std::string& msg) {
        tc_log_debug("%s", msg.c_str());
    }, nb::arg("message"), "Log debug message");

    m.def("debug", [format_exception](nb::object exc, const std::string& context) {
        std::string msg = format_exception(exc, context);
        tc_log_debug("%s", msg.c_str());
    }, nb::arg("exception"), nb::arg("context") = "", "Log debug with exception");

    m.def("info", [](const std::string& msg) {
        tc_log_info("%s", msg.c_str());
    }, nb::arg("message"), "Log info message");

    m.def("info", [format_exception](nb::object exc, const std::string& context) {
        std::string msg = format_exception(exc, context);
        tc_log_info("%s", msg.c_str());
    }, nb::arg("exception"), nb::arg("context") = "", "Log info with exception");

    m.def("warn", [](const std::string& msg) {
        tc_log_warn("%s", msg.c_str());
    }, nb::arg("message"), "Log warning message");

    m.def("warn", [format_exception](nb::object exc, const std::string& context) {
        std::string msg = format_exception(exc, context);
        tc_log_warn("%s", msg.c_str());
    }, nb::arg("exception"), nb::arg("context") = "", "Log warning with exception");

    m.def("error", [](const std::string& msg) {
        tc_log_error("%s", msg.c_str());
    }, nb::arg("message"), "Log error message");

    m.def("error", [format_exception](nb::object exc, const std::string& context) {
        std::string msg = format_exception(exc, context);
        tc_log_error("%s", msg.c_str());
    }, nb::arg("exception"), nb::arg("context") = "", "Log error with exception");

    // Alias for consistency with Python's logging module
    m.def("warning", [](const std::string& msg) {
        tc_log_warn("%s", msg.c_str());
    }, nb::arg("message"), "Log warning message (alias for warn)");

    // Log error with exception traceback (like Python's logging.exception)
    m.def("exception", [](const std::string& msg) {
        // Get current exception info via Python's traceback module
        nb::module_ traceback = nb::module_::import_("traceback");
        nb::object format_exc = traceback.attr("format_exc");
        std::string tb = nb::cast<std::string>(format_exc());

        // Log message + traceback
        tc_log_error("%s\n%s", msg.c_str(), tb.c_str());
    }, nb::arg("message"), "Log error message with current exception traceback");

    // Log with optional exc_info (like Python's logging)
    m.def("error", [](const std::string& msg, bool exc_info) {
        if (exc_info) {
            nb::module_ traceback = nb::module_::import_("traceback");
            nb::object format_exc = traceback.attr("format_exc");
            std::string tb = nb::cast<std::string>(format_exc());
            tc_log_error("%s\n%s", msg.c_str(), tb.c_str());
        } else {
            tc_log_error("%s", msg.c_str());
        }
    }, nb::arg("message"), nb::arg("exc_info"), "Log error message with optional traceback");

    m.def("warning", [](const std::string& msg, bool exc_info) {
        if (exc_info) {
            nb::module_ traceback = nb::module_::import_("traceback");
            nb::object format_exc = traceback.attr("format_exc");
            std::string tb = nb::cast<std::string>(format_exc());
            tc_log_warn("%s\n%s", msg.c_str(), tb.c_str());
        } else {
            tc_log_warn("%s", msg.c_str());
        }
    }, nb::arg("message"), nb::arg("exc_info"), "Log warning message with optional traceback");
}

} // namespace termin
