#include "inspect_registry.hpp"

namespace termin {

py::object InspectRegistry::convert_value_for_kind(py::object value, const std::string& kind) {
    // Check for registered kind handler first
    auto* handler = instance().get_kind_handler(kind);
    if (handler && handler->convert) {
        return handler->convert(value);
    }

    // For unregistered kinds, return value as-is
    return value;
}

nos::trent InspectRegistry::py_to_trent_with_kind(py::object obj, const std::string& kind) {
    // Check for registered kind handler first
    auto* handler = instance().get_kind_handler(kind);
    if (handler && handler->serialize) {
        return handler->serialize(obj);
    }

    // Fallback to basic conversion
    return py_to_trent(obj);
}

py::object InspectRegistry::trent_to_py_with_kind(const nos::trent& t, const std::string& kind) {
    // Check for registered kind handler first
    auto* handler = instance().get_kind_handler(kind);
    if (handler && handler->deserialize) {
        return handler->deserialize(t);
    }

    // Fallback to basic conversion
    return trent_to_py(t);
}

} // namespace termin
