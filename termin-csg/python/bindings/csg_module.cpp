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
        .def("rotated", &termin::csg::Solid::rotated,
             nb::arg("x_degrees"), nb::arg("y_degrees"), nb::arg("z_degrees"))
        .def("move",
             [](const termin::csg::Solid& self, double x, double y, double z) {
                 return self.translated(x, y, z);
             },
             nb::arg("x") = 0.0, nb::arg("y") = 0.0, nb::arg("z") = 0.0)
        .def("up",
             [](const termin::csg::Solid& self, double value) {
                 return self.translated(0.0, 0.0, value);
             },
             nb::arg("value"))
        .def("right",
             [](const termin::csg::Solid& self, double value) {
                 return self.translated(value, 0.0, 0.0);
             },
             nb::arg("value"))
        .def("forward",
             [](const termin::csg::Solid& self, double value) {
                 return self.translated(0.0, value, 0.0);
             },
             nb::arg("value"))
        .def("mX",
             [](const termin::csg::Solid& self, double value) {
                 return self.translated(value, 0.0, 0.0);
             },
             nb::arg("value"))
        .def("mY",
             [](const termin::csg::Solid& self, double value) {
                 return self.translated(0.0, value, 0.0);
             },
             nb::arg("value"))
        .def("mZ",
             [](const termin::csg::Solid& self, double value) {
                 return self.translated(0.0, 0.0, value);
             },
             nb::arg("value"))
        .def("scale",
             [](const termin::csg::Solid& self, double x, nb::object y, nb::object z) {
                 const double yy = y.is_none() ? x : nb::cast<double>(y);
                 const double zz = z.is_none() ? x : nb::cast<double>(z);
                 return self.scaled(x, yy, zz);
             },
             nb::arg("x"), nb::arg("y") = nb::none(), nb::arg("z") = nb::none())
        .def("rotate",
             [](const termin::csg::Solid& self, double x, double y, double z) {
                 return self.rotated(x, y, z);
             },
             nb::arg("x") = 0.0, nb::arg("y") = 0.0, nb::arg("z") = 0.0)
        .def("rX",
             [](const termin::csg::Solid& self, double degrees) {
                 return self.rotated(degrees, 0.0, 0.0);
             },
             nb::arg("degrees"))
        .def("rY",
             [](const termin::csg::Solid& self, double degrees) {
                 return self.rotated(0.0, degrees, 0.0);
             },
             nb::arg("degrees"))
        .def("rZ",
             [](const termin::csg::Solid& self, double degrees) {
                 return self.rotated(0.0, 0.0, degrees);
             },
             nb::arg("degrees"))
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
    m.def("make_cylinder", &termin::csg::make_cylinder,
          nb::arg("radius"), nb::arg("height"),
          nb::arg("circular_segments") = 0, nb::arg("centered") = true);
    m.def("make_cone", &termin::csg::make_cone,
          nb::arg("radius_low"), nb::arg("radius_high"), nb::arg("height"),
          nb::arg("circular_segments") = 0, nb::arg("centered") = true);
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
          nb::arg("solid"),
          nb::arg("name") = std::string(),
          nb::arg("uuid") = std::string(),
          nb::arg("flat_shading") = false);
    m.def("to_tc_mesh", &termin::csg::to_tc_mesh,
          nb::arg("solid"),
          nb::arg("name") = std::string(),
          nb::arg("uuid") = std::string(),
          nb::arg("flat_shading") = false);
}
