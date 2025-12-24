#include "common.hpp"
#include "termin/render/drawable.hpp"
#include "termin/entity/entity.hpp"

namespace termin {

void bind_drawable(py::module_& m) {
    py::class_<GeometryDrawCall>(m, "GeometryDrawCall")
        .def(py::init<>())
        .def(py::init([](MaterialPhase* phase, const std::string& geometry_id) {
            return GeometryDrawCall{phase, geometry_id};
        }), py::arg("phase"), py::arg("geometry_id") = "")
        .def_readwrite("phase", &GeometryDrawCall::phase)
        .def_readwrite("geometry_id", &GeometryDrawCall::geometry_id);

    py::class_<PhaseDrawCall>(m, "PhaseDrawCall")
        .def(py::init<>())
        .def_readwrite("entity", &PhaseDrawCall::entity)
        .def_readwrite("phase", &PhaseDrawCall::phase)
        .def_readwrite("priority", &PhaseDrawCall::priority)
        .def_readwrite("geometry_id", &PhaseDrawCall::geometry_id);
}

} // namespace termin
