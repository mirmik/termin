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

void InspectRegistry::register_python_fields(const std::string& type_name, py::dict fields_dict) {
    _py_fields.erase(type_name);

    for (auto item : fields_dict) {
        std::string field_name = item.first.cast<std::string>();
        py::object field_obj = py::reinterpret_borrow<py::object>(item.second);

        InspectFieldInfo info;
        info.type_name = type_name;

        // Extract attributes
        info.path = field_name;
        if (py::hasattr(field_obj, "path") && !field_obj.attr("path").is_none()) {
            info.path = field_obj.attr("path").cast<std::string>();
        }

        info.label = field_name;
        if (py::hasattr(field_obj, "label") && !field_obj.attr("label").is_none()) {
            info.label = field_obj.attr("label").cast<std::string>();
        }

        info.kind = "float";
        if (py::hasattr(field_obj, "kind")) {
            info.kind = field_obj.attr("kind").cast<std::string>();
        }

        if (py::hasattr(field_obj, "min") && !field_obj.attr("min").is_none()) {
            info.min = field_obj.attr("min").cast<double>();
        }
        if (py::hasattr(field_obj, "max") && !field_obj.attr("max").is_none()) {
            info.max = field_obj.attr("max").cast<double>();
        }
        if (py::hasattr(field_obj, "step") && !field_obj.attr("step").is_none()) {
            info.step = field_obj.attr("step").cast<double>();
        }

        if (py::hasattr(field_obj, "non_serializable")) {
            info.non_serializable = field_obj.attr("non_serializable").cast<bool>();
        }

        // Choices for enum
        if (py::hasattr(field_obj, "choices") && !field_obj.attr("choices").is_none()) {
            for (auto c : field_obj.attr("choices")) {
                py::tuple t = c.cast<py::tuple>();
                if (t.size() >= 2) {
                    EnumChoice choice;
                    choice.value = py::reinterpret_borrow<py::object>(t[0]);
                    choice.label = t[1].cast<std::string>();
                    info.choices.push_back(choice);
                }
            }
        }

        // Action for button
        if (py::hasattr(field_obj, "action") && !field_obj.attr("action").is_none()) {
            info.action = field_obj.attr("action");
        }

        // Custom getter/setter
        py::object py_getter = py::none();
        py::object py_setter = py::none();
        if (py::hasattr(field_obj, "getter") && !field_obj.attr("getter").is_none()) {
            py_getter = field_obj.attr("getter");
        }
        if (py::hasattr(field_obj, "setter") && !field_obj.attr("setter").is_none()) {
            py_setter = field_obj.attr("setter");
        }

        std::string path_copy = info.path;

        info.py_getter = [path_copy, py_getter](void* obj) -> py::object {
            // obj is PyObject* from get_raw_pointer for Python types
            py::object py_obj = py::reinterpret_borrow<py::object>(
                py::handle(static_cast<PyObject*>(obj)));
            if (!py_getter.is_none()) {
                return py_getter(py_obj);
            }
            // Use getattr for path resolution
            py::object result = py_obj;
            size_t start = 0, end;
            while ((end = path_copy.find('.', start)) != std::string::npos) {
                result = py::getattr(result, path_copy.substr(start, end - start).c_str());
                start = end + 1;
            }
            return py::getattr(result, path_copy.substr(start).c_str());
        };

        info.py_setter = [path_copy, py_setter](void* obj, py::object value) {
            try {
                // obj is PyObject* from get_raw_pointer for Python types
                py::object py_obj = py::reinterpret_borrow<py::object>(
                    py::handle(static_cast<PyObject*>(obj)));
                if (!py_setter.is_none()) {
                    py_setter(py_obj, value);
                    return;
                }
                // Use setattr for path resolution
                py::object target = py_obj;
                std::vector<std::string> parts;
                size_t start = 0, end;
                while ((end = path_copy.find('.', start)) != std::string::npos) {
                    parts.push_back(path_copy.substr(start, end - start));
                    start = end + 1;
                }
                parts.push_back(path_copy.substr(start));

                for (size_t i = 0; i < parts.size() - 1; ++i) {
                    target = py::getattr(target, parts[i].c_str());
                }
                py::setattr(target, parts.back().c_str(), value);
            } catch (const std::exception& e) {
                std::cerr << "[Python setter error] path=" << path_copy
                          << " error=" << e.what() << std::endl;
            }
        };

        _py_fields[type_name].push_back(std::move(info));
    }

    _type_backends[type_name] = TypeBackend::Python;
}

KindHandler* InspectRegistry::try_generate_handler(const std::string& kind) {
    char container[64], element[64];
    if (!tc_kind_parse(kind.c_str(), container, sizeof(container),
                      element, sizeof(element))) {
        return nullptr;
    }

    if (std::string(container) == "list") {
        auto* elem_handler = KindRegistry::instance().get(element);
        if (!elem_handler) {
            return nullptr;
        }

        std::string elem_kind = element;
        auto& list_handler = KindRegistry::instance().get_or_create(kind);

        // serialize: py::object (list) -> py::object (list of serialized elements)
        list_handler.python.serialize = py::cpp_function([elem_kind](py::object obj) -> py::object {
            py::list result;
            if (obj.is_none()) {
                return result;
            }

            auto* elem_handler = KindRegistry::instance().get(elem_kind);

            for (auto item : obj) {
                py::object py_item = py::reinterpret_borrow<py::object>(item);
                if (elem_handler && elem_handler->has_python()) {
                    result.append(elem_handler->python.serialize(py_item));
                } else {
                    result.append(py_item);
                }
            }
            return result;
        });

        // deserialize: py::object (list) -> py::object (list of deserialized elements)
        list_handler.python.deserialize = py::cpp_function([elem_kind](py::object data) -> py::object {
            py::list result;
            if (!py::isinstance<py::list>(data)) return result;

            auto* elem_handler = KindRegistry::instance().get(elem_kind);
            for (auto item : data) {
                py::object py_item = py::reinterpret_borrow<py::object>(item);
                if (elem_handler && elem_handler->has_python()) {
                    result.append(elem_handler->python.deserialize(py_item));
                } else {
                    result.append(py_item);
                }
            }
            return result;
        });

        list_handler.python.convert = py::cpp_function([elem_kind](py::object value) -> py::object {
            if (value.is_none()) return py::list();

            auto* elem_handler = KindRegistry::instance().get(elem_kind);
            if (!elem_handler || !elem_handler->has_python()) {
                return value;
            }

            py::list result;
            for (auto item : value) {
                py::object py_item = py::reinterpret_borrow<py::object>(item);
                result.append(elem_handler->python.convert(py_item));
            }
            return result;
        });

        // Prevent Python GC from collecting these
        list_handler.python.serialize.inc_ref();
        list_handler.python.deserialize.inc_ref();
        list_handler.python.convert.inc_ref();
        list_handler._has_python = true;

        return &list_handler;
    }

    return nullptr;
}

} // namespace tc
