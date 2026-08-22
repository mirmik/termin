#include "common.hpp"

#include <termin/camera/screen_ray.hpp>

namespace termin {

    void bind_screen_projection(nb::module_& m) {
        nb::class_<ProjectedScreenPoint>(m, "ProjectedScreenPoint")
            .def(nb::init<>())
            .def_rw("screen", &ProjectedScreenPoint::screen)
            .def_rw("depth", &ProjectedScreenPoint::depth)
            .def_rw("view_point", &ProjectedScreenPoint::view_point)
            .def("copy", [](const ProjectedScreenPoint& point) { return point; })
            .def("__repr__", [](const ProjectedScreenPoint& point) {
                return "ProjectedScreenPoint(screen=Vec2(" + std::to_string(point.screen.x) + ", " +
                       std::to_string(point.screen.y) + "), depth=" + std::to_string(point.depth) +
                       ", view_point=Vec3(" + std::to_string(point.view_point.x) + ", " +
                       std::to_string(point.view_point.y) + ", " + std::to_string(point.view_point.z) + "))";
            });
    }

} // namespace termin
