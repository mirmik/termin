// tc_inspect_instance.cpp - InspectRegistry singleton and methods needing Component
// This file must be compiled into entity_lib to ensure single instance across all modules

#include "../../cpp/trent/trent.h"

// Include Component BEFORE tc_inspect.hpp so it's fully defined
#include "../../cpp/termin/entity/component.hpp"

#include "../include/tc_inspect.hpp"

namespace tc {

InspectRegistry& InspectRegistry::instance() {
    static InspectRegistry reg;
    return reg;
}

void InspectRegistry::register_python_fields(const std::string& type_name, nb::dict fields_dict) {
    _py_fields.erase(type_name);

    for (auto item : fields_dict) {
        std::string field_name = nb::cast<std::string>(item.first);
        nb::object field_obj = nb::borrow<nb::object>(item.second);

        InspectFieldInfo info;
        info.type_name = type_name;

        // Extract attributes
        info.path = field_name;
        if (nb::hasattr(field_obj, "path") && !field_obj.attr("path").is_none()) {
            info.path = nb::cast<std::string>(field_obj.attr("path"));
        }

        info.label = field_name;
        if (nb::hasattr(field_obj, "label") && !field_obj.attr("label").is_none()) {
            info.label = nb::cast<std::string>(field_obj.attr("label"));
        }

        info.kind = "float";
        if (nb::hasattr(field_obj, "kind")) {
            info.kind = nb::cast<std::string>(field_obj.attr("kind"));
        }

        if (nb::hasattr(field_obj, "min") && !field_obj.attr("min").is_none()) {
            info.min = nb::cast<double>(field_obj.attr("min"));
        }
        if (nb::hasattr(field_obj, "max") && !field_obj.attr("max").is_none()) {
            info.max = nb::cast<double>(field_obj.attr("max"));
        }
        if (nb::hasattr(field_obj, "step") && !field_obj.attr("step").is_none()) {
            info.step = nb::cast<double>(field_obj.attr("step"));
        }

        if (nb::hasattr(field_obj, "non_serializable")) {
            info.non_serializable = nb::cast<bool>(field_obj.attr("non_serializable"));
        }

        // Choices for enum
        if (nb::hasattr(field_obj, "choices") && !field_obj.attr("choices").is_none()) {
            for (auto c : field_obj.attr("choices")) {
                nb::tuple t = nb::cast<nb::tuple>(c);
                if (t.size() >= 2) {
                    EnumChoice choice;
                    choice.value = nb::borrow<nb::object>(t[0]);
                    choice.label = nb::cast<std::string>(t[1]);
                    info.choices.push_back(choice);
                }
            }
        }

        // Action for button
        if (nb::hasattr(field_obj, "action") && !field_obj.attr("action").is_none()) {
            info.action = field_obj.attr("action");
        }

        // Custom getter/setter
        nb::object py_getter = nb::none();
        nb::object py_setter = nb::none();
        if (nb::hasattr(field_obj, "getter") && !field_obj.attr("getter").is_none()) {
            py_getter = field_obj.attr("getter");
        }
        if (nb::hasattr(field_obj, "setter") && !field_obj.attr("setter").is_none()) {
            py_setter = field_obj.attr("setter");
        }

        std::string path_copy = info.path;

        info.py_getter = [path_copy, py_getter](void* obj) -> nb::object {
            // obj is PyObject* from get_raw_pointer for Python types
            nb::object py_obj = nb::borrow<nb::object>(
                nb::handle(static_cast<PyObject*>(obj)));
            if (!py_getter.is_none()) {
                return py_getter(py_obj);
            }
            // Use getattr for path resolution
            nb::object result = py_obj;
            size_t start = 0, end;
            while ((end = path_copy.find('.', start)) != std::string::npos) {
                result = nb::getattr(result, path_copy.substr(start, end - start).c_str());
                start = end + 1;
            }
            return nb::getattr(result, path_copy.substr(start).c_str());
        };

        info.py_setter = [path_copy, py_setter](void* obj, nb::object value) {
            try {
                // obj is PyObject* from get_raw_pointer for Python types
                nb::object py_obj = nb::borrow<nb::object>(
                    nb::handle(static_cast<PyObject*>(obj)));
                if (!py_setter.is_none()) {
                    py_setter(py_obj, value);
                    return;
                }
                // Use setattr for path resolution
                nb::object target = py_obj;
                std::vector<std::string> parts;
                size_t start = 0, end;
                while ((end = path_copy.find('.', start)) != std::string::npos) {
                    parts.push_back(path_copy.substr(start, end - start));
                    start = end + 1;
                }
                parts.push_back(path_copy.substr(start));

                for (size_t i = 0; i < parts.size() - 1; ++i) {
                    target = nb::getattr(target, parts[i].c_str());
                }
                nb::setattr(target, parts.back().c_str(), value);
            } catch (const std::exception& e) {
                std::cerr << "[Python setter error] path=" << path_copy
                          << " error=" << e.what() << std::endl;
            }
        };

        _py_fields[type_name].push_back(std::move(info));
    }

    _type_backends[type_name] = TypeBackend::Python;
}

} // namespace tc
