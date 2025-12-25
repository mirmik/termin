#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

#include "termin/mesh_bindings.hpp"
#include "termin/assets/handles.hpp"
#include "termin/inspect/inspect_registry.hpp"

namespace py = pybind11;

namespace {

void bind_mesh_handle(py::module_& m) {
    py::class_<termin::MeshHandle>(m, "MeshHandle")
        .def(py::init<>())
        .def(py::init<py::object>(), py::arg("asset"))
        .def_static("from_name", &termin::MeshHandle::from_name, py::arg("name"))
        .def_static("from_asset", &termin::MeshHandle::from_asset, py::arg("asset"))
        .def_static("from_mesh3", &termin::MeshHandle::from_mesh3,
            py::arg("mesh"), py::arg("name") = "mesh", py::arg("source_path") = "")
        .def_static("from_mesh", &termin::MeshHandle::from_mesh3,  // alias
            py::arg("mesh"), py::arg("name") = "mesh", py::arg("source_path") = "")
        .def_static("from_vertices_indices", &termin::MeshHandle::from_vertices_indices,
            py::arg("vertices"), py::arg("indices"), py::arg("name") = "mesh")
        .def_static("deserialize", &termin::MeshHandle::deserialize, py::arg("data"))
        .def_readwrite("asset", &termin::MeshHandle::asset)
        .def_property_readonly("is_valid", &termin::MeshHandle::is_valid)
        .def_property_readonly("name", &termin::MeshHandle::name)
        .def_property_readonly("version", &termin::MeshHandle::version)
        .def_property_readonly("mesh", &termin::MeshHandle::mesh)
        .def_property_readonly("gpu", &termin::MeshHandle::gpu, py::return_value_policy::reference)
        .def("get", &termin::MeshHandle::get, py::return_value_policy::reference)
        .def("get_mesh", &termin::MeshHandle::mesh)
        .def("get_mesh_or_none", &termin::MeshHandle::mesh)
        .def("get_asset", [](const termin::MeshHandle& self) { return self.asset; })
        .def("serialize", &termin::MeshHandle::serialize);
}

void register_mesh_kind() {
    auto& registry = termin::InspectRegistry::instance();

    registry.register_kind("mesh_handle", termin::KindHandler{
        // serialize
        [](py::object obj) -> nos::trent {
            if (py::hasattr(obj, "serialize")) {
                py::dict d = obj.attr("serialize")();
                return termin::InspectRegistry::py_dict_to_trent(d);
            }
            return nos::trent::nil();
        },
        // deserialize
        [](const nos::trent& t) -> py::object {
            if (!t.is_dict()) {
                return py::cast(termin::MeshHandle());
            }
            py::dict d = termin::InspectRegistry::trent_to_py_dict(t);
            return py::cast(termin::MeshHandle::deserialize(d));
        },
        // convert
        [](py::object value) -> py::object {
            if (value.is_none()) {
                return py::cast(termin::MeshHandle());
            }
            if (py::isinstance<termin::MeshHandle>(value)) {
                return value;
            }
            return value;
        }
    });
}

} // anonymous namespace

PYBIND11_MODULE(_mesh_native, m) {
    m.doc() = "Native C++ mesh module (Mesh3, SkinnedMesh3, MeshHandle)";

    // Bind Mesh3 and SkinnedMesh3
    termin::bind_mesh(m);

    // Bind MeshHandle
    bind_mesh_handle(m);

    // Register mesh kind handler for InspectRegistry
    register_mesh_kind();
}
