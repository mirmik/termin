#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/operators.h>
#include <pybind11/stl.h>

#include "termin/geom/geom.hpp"
#include "termin/colliders/box_collider.hpp"
#include "termin/colliders/sphere_collider.hpp"

namespace py = pybind11;
using namespace termin;
using namespace termin::geom;
using namespace termin::colliders;

PYBIND11_MODULE(_colliders_native, m) {
    m.doc() = "Native C++ colliders module for termin";

    // Import _geom_native for Vec3, Quat, Pose3
    py::module_::import("termin.geombase._geom_native");

    // CollisionResult
    py::class_<CollisionResult>(m, "CollisionResult")
        .def(py::init<>())
        .def_readwrite("point", &CollisionResult::point)
        .def_readwrite("normal", &CollisionResult::normal)
        .def_readwrite("distance", &CollisionResult::distance)
        .def_readwrite("colliding", &CollisionResult::colliding);

    // BoxCollider::GroundContact
    py::class_<BoxCollider::GroundContact>(m, "GroundContact")
        .def(py::init<>())
        .def_readwrite("point", &BoxCollider::GroundContact::point)
        .def_readwrite("penetration", &BoxCollider::GroundContact::penetration);

    // BoxCollider
    py::class_<BoxCollider>(m, "BoxCollider")
        .def(py::init<>())
        .def(py::init<const Vec3&, const Vec3&, const Pose3&>(),
             py::arg("center"), py::arg("half_size"), py::arg("pose") = Pose3())
        .def_static("from_size", &BoxCollider::from_size,
             py::arg("center"), py::arg("size"), py::arg("pose") = Pose3())
        .def_readwrite("center", &BoxCollider::center)
        .def_readwrite("half_size", &BoxCollider::half_size)
        .def_readwrite("pose", &BoxCollider::pose)
        .def("transform_by", &BoxCollider::transform_by)
        .def("world_center", &BoxCollider::world_center)
        .def("get_corners_world", [](const BoxCollider& b) {
            auto corners = b.get_corners_world();
            py::array_t<double> result({8, 3});
            auto buf = result.mutable_unchecked<2>();
            for (int i = 0; i < 8; i++) {
                buf(i, 0) = corners[i].x;
                buf(i, 1) = corners[i].y;
                buf(i, 2) = corners[i].z;
            }
            return result;
        })
        .def("collide_box", &BoxCollider::collide_box)
        .def("collide_ground", &BoxCollider::collide_ground);

    // SphereCollider
    py::class_<SphereCollider>(m, "SphereCollider")
        .def(py::init<>())
        .def(py::init<const Vec3&, double>(),
             py::arg("center"), py::arg("radius"))
        .def_readwrite("center", &SphereCollider::center)
        .def_readwrite("radius", &SphereCollider::radius)
        .def("transform_by", &SphereCollider::transform_by)
        .def("collide_sphere", &SphereCollider::collide_sphere)
        .def("collide_box", &SphereCollider::collide_box)
        .def("collide_ground", &SphereCollider::collide_ground);
}
