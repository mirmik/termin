#include "inspect_registry.hpp"
#include "../entity/component.hpp"

namespace termin {

InspectRegistry& InspectRegistry::instance() {
    static InspectRegistry reg;
    return reg;
}

std::vector<std::string> InspectRegistry::split_path(const std::string& path) {
    std::vector<std::string> parts;
    std::string current;
    for (char c : path) {
        if (c == '.') {
            if (!current.empty()) {
                parts.push_back(current);
                current.clear();
            }
        } else {
            current += c;
        }
    }
    if (!current.empty()) {
        parts.push_back(current);
    }
    return parts;
}

void InspectRegistry::register_python_fields(const std::string& type_name, py::dict fields_dict) {
    // Clear existing fields for this type (in case of re-registration)
    _fields.erase(type_name);

    for (auto item : fields_dict) {
        std::string field_name = item.first.cast<std::string>();
        py::object field_obj = py::reinterpret_borrow<py::object>(item.second);

        // Extract InspectField attributes
        std::string path = field_name;
        if (py::hasattr(field_obj, "path") && !field_obj.attr("path").is_none()) {
            path = field_obj.attr("path").cast<std::string>();
        }

        std::string label = field_name;
        if (py::hasattr(field_obj, "label") && !field_obj.attr("label").is_none()) {
            label = field_obj.attr("label").cast<std::string>();
        }

        std::string kind = "float";
        if (py::hasattr(field_obj, "kind")) {
            kind = field_obj.attr("kind").cast<std::string>();
        }

        double min_val = 0.0, max_val = 1.0, step_val = 0.01;
        if (py::hasattr(field_obj, "min") && !field_obj.attr("min").is_none()) {
            min_val = field_obj.attr("min").cast<double>();
        }
        if (py::hasattr(field_obj, "max") && !field_obj.attr("max").is_none()) {
            max_val = field_obj.attr("max").cast<double>();
        }
        if (py::hasattr(field_obj, "step") && !field_obj.attr("step").is_none()) {
            step_val = field_obj.attr("step").cast<double>();
        }

        bool non_serializable = false;
        if (py::hasattr(field_obj, "non_serializable")) {
            non_serializable = field_obj.attr("non_serializable").cast<bool>();
        }

        // Check for custom getter/setter
        py::object py_getter = py::none();
        py::object py_setter = py::none();
        if (py::hasattr(field_obj, "getter") && !field_obj.attr("getter").is_none()) {
            py_getter = field_obj.attr("getter");
        }
        if (py::hasattr(field_obj, "setter") && !field_obj.attr("setter").is_none()) {
            py_setter = field_obj.attr("setter");
        }

        // Create getter/setter functions
        std::string path_copy = path;
        py::object getter_copy = py_getter;
        py::object setter_copy = py_setter;

        auto getter_fn = [path_copy, getter_copy](void* obj) -> py::object {
            py::object py_obj = py::cast(static_cast<Component*>(obj),
                                         py::return_value_policy::reference);
            if (!getter_copy.is_none()) {
                return getter_copy(py_obj);
            }
            // Use getattr for path resolution
            py::object result = py_obj;
            for (const auto& part : split_path(path_copy)) {
                result = py::getattr(result, part.c_str());
            }
            return result;
        };

        auto setter_fn = [path_copy, setter_copy](void* obj, py::object value) {
            std::cerr << "[Python setter_fn] path=" << path_copy
                      << " has_custom=" << !setter_copy.is_none() << std::endl;
            try {
                py::object py_obj = py::cast(static_cast<Component*>(obj),
                                             py::return_value_policy::reference);
                if (!setter_copy.is_none()) {
                    std::cerr << "[Python setter_fn] calling custom setter" << std::endl;
                    setter_copy(py_obj, value);
                    return;
                }
                // Use setattr for path resolution
                auto parts = split_path(path_copy);
                py::object target = py_obj;
                for (size_t i = 0; i < parts.size() - 1; ++i) {
                    target = py::getattr(target, parts[i].c_str());
                }
                py::setattr(target, parts.back().c_str(), value);
            } catch (const std::exception& e) {
                std::cerr << "[Python setter error] path=" << path_copy << " error=" << e.what() << std::endl;
            }
        };

        _fields[type_name].push_back({
            .type_name = type_name,
            .path = path,
            .label = label,
            .kind = kind,
            .min = min_val,
            .max = max_val,
            .step = step_val,
            .non_serializable = non_serializable,
            .getter = getter_fn,
            .setter = setter_fn
        });
    }
}

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
