#include <nanobind/nanobind.h>
#include <nanobind/stl/pair.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include <termin/csg/csg.hpp>

namespace nb = nanobind;

NB_MODULE(_csg_native, m) {
    m.doc() = "termin-csg native Python bindings";

    nb::module_::import_("tmesh._tmesh_native");

    nb::class_<termin::csg::Point2>(m, "Point2")
        .def(nb::init<>())
        .def(nb::init<double, double>(), nb::arg("x"), nb::arg("y"))
        .def_rw("x", &termin::csg::Point2::x)
        .def_rw("y", &termin::csg::Point2::y)
        .def("__repr__", [](const termin::csg::Point2& p) {
            return "Point2(" + std::to_string(p.x) + ", " + std::to_string(p.y) + ")";
        });

    nb::class_<termin::csg::Solid>(m, "Solid")
        .def(nb::init<>())
        .def_prop_ro("is_empty", &termin::csg::Solid::is_empty)
        .def_prop_ro("vertex_count", &termin::csg::Solid::vertex_count)
        .def_prop_ro("triangle_count", &termin::csg::Solid::triangle_count)
        .def_prop_ro("volume", &termin::csg::Solid::volume)
        .def_prop_ro("status", &termin::csg::Solid::status_string)
        .def("translated", &termin::csg::Solid::translated,
             nb::arg("x"), nb::arg("y"), nb::arg("z"))
        .def("scaled", &termin::csg::Solid::scaled,
             nb::arg("x"), nb::arg("y"), nb::arg("z"))
        .def("__add__", &termin::csg::unite, nb::is_operator())
        .def("__sub__", &termin::csg::subtract, nb::is_operator())
        .def("__xor__", &termin::csg::intersect, nb::is_operator())
        .def("__repr__", [](const termin::csg::Solid& s) {
            return "<Solid status=\"" + std::string(s.status_string()) +
                   "\" vertices=" + std::to_string(s.vertex_count()) +
                   " triangles=" + std::to_string(s.triangle_count()) +
                   " volume=" + std::to_string(s.volume()) + ">";
        });

    m.def("make_box", &termin::csg::make_box,
          nb::arg("x"), nb::arg("y"), nb::arg("z"), nb::arg("centered") = true);
    m.def("make_sphere", &termin::csg::make_sphere,
          nb::arg("radius"), nb::arg("circular_segments") = 0);
    m.def("unite", &termin::csg::unite, nb::arg("a"), nb::arg("b"));
    m.def("subtract", &termin::csg::subtract, nb::arg("a"), nb::arg("b"));
    m.def("intersect", &termin::csg::intersect, nb::arg("a"), nb::arg("b"));
    m.def("_extrude_points",
          [](const termin::csg::Polygon2& outer,
             double height,
             const std::vector<termin::csg::Polygon2>& holes) {
              return termin::csg::extrude(outer, holes, height);
          },
          nb::arg("outer"), nb::arg("height"),
          nb::arg("holes") = std::vector<termin::csg::Polygon2>());
    m.def("_extrude_pairs",
          [](const std::vector<std::pair<double, double>>& outer,
             double height,
             const std::vector<std::vector<std::pair<double, double>>>& holes) {
              termin::csg::Polygon2 out;
              out.reserve(outer.size());
              for (const auto& p : outer) {
                  out.push_back({p.first, p.second});
              }

              std::vector<termin::csg::Polygon2> hole_polygons;
              hole_polygons.reserve(holes.size());
              for (const auto& hole : holes) {
                  termin::csg::Polygon2 converted;
                  converted.reserve(hole.size());
                  for (const auto& p : hole) {
                      converted.push_back({p.first, p.second});
                  }
                  hole_polygons.push_back(std::move(converted));
              }

              return termin::csg::extrude(out, hole_polygons, height);
          },
          nb::arg("outer"), nb::arg("height"),
          nb::arg("holes") = std::vector<std::vector<std::pair<double, double>>>());
    m.def("to_mesh3", &termin::csg::to_mesh3,
          nb::arg("solid"), nb::arg("name") = std::string(), nb::arg("uuid") = std::string());
    m.def("to_tc_mesh", &termin::csg::to_tc_mesh,
          nb::arg("solid"), nb::arg("name") = std::string(), nb::arg("uuid") = std::string());
}
