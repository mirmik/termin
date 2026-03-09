// component_bindings.cpp - CxxComponent + ComponentRegistry bindings
#include <termin/bindings/component_bindings.hpp>
#include <termin/bindings/entity_helpers.hpp>

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/entity/component_registry_python.hpp>
#include <termin/entity/entity.hpp>
#include "core/tc_component.h"

namespace nb = nanobind;

namespace termin {

void bind_cxx_component(nb::module_& m) {
    nb::class_<CxxComponent>(m, "Component", nb::dynamic_attr())
        .def("__init__", [](nb::handle self) {
            cxx_component_init<CxxComponent>(self);
        })
        .def("start", &CxxComponent::start)
        .def("update", &CxxComponent::update)
        .def("fixed_update", &CxxComponent::fixed_update)
        .def("on_destroy", &CxxComponent::on_destroy)
        .def("on_editor_start", &CxxComponent::on_editor_start)
        .def("setup_editor_defaults", &CxxComponent::setup_editor_defaults)
        .def("on_added_to_entity", &CxxComponent::on_added_to_entity)
        .def("on_removed_from_entity", &CxxComponent::on_removed_from_entity)
        .def("on_added", &CxxComponent::on_added)
        .def("on_removed", &CxxComponent::on_removed)
        .def("on_scene_inactive", &CxxComponent::on_scene_inactive)
        .def("on_scene_active", &CxxComponent::on_scene_active)
        .def("type_name", &CxxComponent::type_name)
        .def_prop_rw("enabled", &CxxComponent::enabled, &CxxComponent::set_enabled)
        .def_prop_rw("active_in_editor", &CxxComponent::active_in_editor, &CxxComponent::set_active_in_editor)
        .def_prop_ro("started", &CxxComponent::started)
        .def_prop_rw("has_update", &CxxComponent::has_update, &CxxComponent::set_has_update)
        .def_prop_rw("has_fixed_update", &CxxComponent::has_fixed_update, &CxxComponent::set_has_fixed_update)
        .def_prop_ro("is_input_handler", &CxxComponent::is_input_handler)
        .def_prop_ro("entity",
            [](CxxComponent& c) -> nb::object {
                Entity ent = c.entity();
                if (ent.valid()) {
                    return nb::cast(ent);
                }
                return nb::none();
            })
        .def("c_component_ptr", [](CxxComponent& c) -> uintptr_t {
            return reinterpret_cast<uintptr_t>(c.c_component());
        })
        .def("serialize", [](CxxComponent& c) -> nb::dict {
            tc_value v = c.serialize();
            nb::object result = tc_value_to_py(&v);
            tc_value_free(&v);
            return nb::cast<nb::dict>(result);
        })
        .def("serialize_data", [](CxxComponent& c) -> nb::dict {
            tc_value v = c.serialize_data();
            nb::object result = tc_value_to_py(&v);
            tc_value_free(&v);
            return nb::cast<nb::dict>(result);
        })
        .def("deserialize_data", [](CxxComponent& c, nb::dict data) {
            tc_value v = py_to_tc_value(data);
            c.deserialize_data(&v);
            tc_value_free(&v);
        }, nb::arg("data"))
        .def("__eq__", [](CxxComponent& self, nb::object other) -> bool {
            if (!nb::isinstance<CxxComponent>(other)) return false;
            CxxComponent& other_c = nb::cast<CxxComponent&>(other);
            return self.c_component() == other_c.c_component();
        })
        .def("__hash__", [](CxxComponent& self) -> size_t {
            return reinterpret_cast<size_t>(self.c_component());
        });
}

void bind_component_registry(nb::module_& m) {
    nb::class_<ComponentRegistry>(m, "ComponentRegistry")
        .def_static("instance", &ComponentRegistry::instance, nb::rv_policy::reference)
        .def("register_python", [](ComponentRegistry&, const std::string& name, nb::object cls, nb::object parent) {
            if (parent.is_none()) {
                ComponentRegistryPython::register_python(name, cls, nullptr);
            } else {
                std::string parent_str = nb::cast<std::string>(parent);
                ComponentRegistryPython::register_python(name, cls, parent_str.c_str());
            }
        }, nb::arg("name"), nb::arg("cls"), nb::arg("parent") = nb::none())
        .def("unregister", &ComponentRegistry::unregister, nb::arg("name"))
        .def("has", &ComponentRegistry::has, nb::arg("name"))
        .def_prop_ro("component_names", [](ComponentRegistry& reg) {
            return reg.list_all();
        })
        .def("list_all", &ComponentRegistry::list_all)
        .def("list_native", &ComponentRegistry::list_native)
        .def("list_python", [](ComponentRegistry& /*self*/) {
            return ComponentRegistryPython::list_python();
        })
        .def("clear", &ComponentRegistry::clear)
        .def_static("set_drawable", &ComponentRegistry::set_drawable,
            nb::arg("name"), nb::arg("is_drawable"),
            "Mark a component type as drawable (can render geometry)")
        .def_static("set_input_handler", &ComponentRegistry::set_input_handler,
            nb::arg("name"), nb::arg("is_input_handler"),
            "Mark a component type as input handler")
        .def_static("get_input_handler_types", []() {
            const char* types[64];
            size_t count = tc_component_registry_get_input_handler_types(types, 64);
            std::vector<std::string> result;
            for (size_t i = 0; i < count; i++) {
                result.push_back(types[i]);
            }
            return result;
        }, "Get all input handler type names");

    // component_registry_get_all_info for debug viewer
    m.def("component_registry_get_all_info", []() {
        nb::list result;
        size_t count = tc_component_registry_type_count();
        for (size_t i = 0; i < count; i++) {
            const char* type_name = tc_component_registry_type_at(i);
            if (!type_name) continue;

            nb::dict info;
            info["name"] = type_name;
            info["language"] = tc_component_registry_get_kind(type_name) == TC_CXX_COMPONENT ? "C++" : "Python";

            const char* parent = tc_component_registry_get_parent(type_name);
            info["parent"] = parent ? nb::str(parent) : nb::none();

            const char* descendants[64];
            size_t desc_count = tc_component_registry_get_type_and_descendants(type_name, descendants, 64);
            nb::list desc_list;
            for (size_t j = 1; j < desc_count; j++) {
                desc_list.append(descendants[j]);
            }
            info["descendants"] = desc_list;
            info["is_drawable"] = tc_component_registry_is_drawable(type_name);

            result.append(info);
        }
        return result;
    });

    m.def("component_registry_type_count", []() {
        return tc_component_registry_type_count();
    });
}

} // namespace termin
