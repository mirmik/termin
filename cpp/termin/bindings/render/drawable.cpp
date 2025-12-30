#include "common.hpp"
#include "termin/render/drawable.hpp"
#include "termin/entity/entity.hpp"

namespace termin {

void bind_drawable(nb::module_& m) {
    nb::class_<GeometryDrawCall>(m, "GeometryDrawCall")
        .def(nb::init<>())
        .def("__init__", [](GeometryDrawCall* self, MaterialPhase* phase, const std::string& geometry_id) {
            new (self) GeometryDrawCall{phase, geometry_id};
        }, nb::arg("phase"), nb::arg("geometry_id") = "")
        .def_rw("phase", &GeometryDrawCall::phase)
        .def_rw("geometry_id", &GeometryDrawCall::geometry_id);

    nb::class_<PhaseDrawCall>(m, "PhaseDrawCall")
        .def(nb::init<>())
        .def_rw("entity", &PhaseDrawCall::entity)
        .def_rw("phase", &PhaseDrawCall::phase)
        .def_rw("priority", &PhaseDrawCall::priority)
        .def_rw("geometry_id", &PhaseDrawCall::geometry_id);
}

} // namespace termin
