#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "inspect/inspect_registry.hpp"
#include "render/material.hpp"
#include "render/mesh_renderer.hpp"
#include "render/skinned_mesh_renderer.hpp"
#include "render/skeleton_controller.hpp"

namespace py = pybind11;

namespace termin {

// Helper to extract raw pointer from Python object
// Works with both raw pointer holders and shared_ptr holders
static void* get_raw_pointer(py::object obj, const std::string& type_name) {
    // For shared_ptr types, we need to cast to the specific type first
    // pybind11 will automatically extract the raw pointer from shared_ptr

    if (type_name == "Material") {
        return static_cast<void*>(obj.cast<Material*>());
    }
    if (type_name == "MaterialPhase") {
        return static_cast<void*>(obj.cast<MaterialPhase*>());
    }
    if (type_name == "MeshRenderer") {
        return static_cast<void*>(obj.cast<MeshRenderer*>());
    }
    if (type_name == "SkinnedMeshRenderer") {
        return static_cast<void*>(obj.cast<SkinnedMeshRenderer*>());
    }
    if (type_name == "SkeletonController") {
        return static_cast<void*>(obj.cast<SkeletonController*>());
    }

    // Fallback for regular pointer types
    return py::cast<void*>(obj);
}

void bind_inspect(py::module_& m) {
    // InspectFieldInfo - read-only metadata
    py::class_<InspectFieldInfo>(m, "InspectFieldInfo")
        .def_readonly("type_name", &InspectFieldInfo::type_name)
        .def_readonly("path", &InspectFieldInfo::path)
        .def_readonly("label", &InspectFieldInfo::label)
        .def_readonly("kind", &InspectFieldInfo::kind)
        .def_readonly("min", &InspectFieldInfo::min)
        .def_readonly("max", &InspectFieldInfo::max)
        .def_readonly("step", &InspectFieldInfo::step)
        .def_readonly("non_serializable", &InspectFieldInfo::non_serializable);

    // InspectRegistry singleton
    py::class_<InspectRegistry>(m, "InspectRegistry")
        .def_static("instance", &InspectRegistry::instance,
                    py::return_value_policy::reference)
        .def("fields", &InspectRegistry::fields,
             py::arg("type_name"),
             py::return_value_policy::reference,
             "Get all fields for a type")
        .def("types", &InspectRegistry::types,
             "Get all registered type names")
        .def("register_python_fields", &InspectRegistry::register_python_fields,
             py::arg("type_name"), py::arg("fields_dict"),
             "Register fields from Python inspect_fields dict")
        .def("get", [](InspectRegistry& self, py::object obj, const std::string& field_path) {
            // Get type name from Python object
            std::string type_name = py::str(py::type::of(obj).attr("__name__")).cast<std::string>();
            void* ptr = get_raw_pointer(obj, type_name);
            return self.get(ptr, type_name, field_path);
        }, py::arg("obj"), py::arg("field"),
           "Get field value from object")
        .def("set", [](InspectRegistry& self, py::object obj, const std::string& field_path, py::object value) {
            std::string type_name = py::str(py::type::of(obj).attr("__name__")).cast<std::string>();
            void* ptr = get_raw_pointer(obj, type_name);
            self.set(ptr, type_name, field_path, value);
        }, py::arg("obj"), py::arg("field"), py::arg("value"),
           "Set field value on object");
}

} // namespace termin
