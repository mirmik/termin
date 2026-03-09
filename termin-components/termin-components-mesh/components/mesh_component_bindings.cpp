#include <nanobind/nanobind.h>

#include <components/mesh_component.hpp>
#include <termin/bindings/entity_helpers.hpp>

namespace nb = nanobind;
using namespace termin;

NB_MODULE(_components_mesh_native, m) {
    m.doc() = "Native mesh component bindings";

    nb::module_::import_("termin.entity._entity_native");

    nb::class_<MeshComponent, CxxComponent>(m, "MeshComponent")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<MeshComponent>(self);
        })
        .def_prop_rw("mesh",
            [](MeshComponent& c) -> TcMesh& { return c.mesh; },
            [](MeshComponent& c, const TcMesh& v) { c.set_mesh(v); })
        .def("get_mesh", [](MeshComponent& c) -> TcMesh& {
            return c.get_mesh();
        })
        .def("set_mesh", &MeshComponent::set_mesh)
        .def("set_mesh_by_name", &MeshComponent::set_mesh_by_name);
}
