#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/operators.h>
#include <pybind11/stl.h>

#include "termin/geom/geom.hpp"
#include "termin/geom/general_transform3.hpp"
#include "termin/colliders/colliders.hpp"

namespace py = pybind11;
using namespace termin;
using namespace termin::geom;
using namespace termin::colliders;
using geom::GeneralTransform3;

PYBIND11_MODULE(_colliders_native, m) {
    m.doc() = "Native C++ colliders module for termin";

    // Import _geom_native for Vec3, Quat, Pose3
    py::module_::import("termin.geombase._geom_native");

    // Helper to create Vec3 from numpy array
    auto numpy_to_vec3 = [](py::array_t<double> arr) {
        auto buf = arr.unchecked<1>();
        return Vec3{buf(0), buf(1), buf(2)};
    };

    // ==================== Ray3 ====================

    py::class_<Ray3>(m, "Ray3")
        .def(py::init<>())
        .def(py::init<const Vec3&, const Vec3&>(),
             py::arg("origin"), py::arg("direction"))
        .def(py::init([numpy_to_vec3](py::array_t<double> origin, py::array_t<double> direction) {
            return Ray3(numpy_to_vec3(origin), numpy_to_vec3(direction));
        }), py::arg("origin"), py::arg("direction"))
        .def_readwrite("origin", &Ray3::origin)
        .def_readwrite("direction", &Ray3::direction)
        .def("point_at", &Ray3::point_at, py::arg("t"));

    // ==================== Результаты запросов ====================

    py::class_<RayHit>(m, "RayHit")
        .def(py::init<>())
        .def_readwrite("point_on_collider", &RayHit::point_on_collider)
        .def_readwrite("point_on_ray", &RayHit::point_on_ray)
        .def_readwrite("distance", &RayHit::distance)
        .def("hit", &RayHit::hit);

    py::class_<ColliderHit>(m, "ColliderHit")
        .def(py::init<>())
        .def_readwrite("point_on_a", &ColliderHit::point_on_a)
        .def_readwrite("point_on_b", &ColliderHit::point_on_b)
        .def_readwrite("normal", &ColliderHit::normal)
        .def_readwrite("distance", &ColliderHit::distance)
        .def("colliding", &ColliderHit::colliding);

    // ==================== ColliderType ====================

    py::enum_<ColliderType>(m, "ColliderType")
        .value("Box", ColliderType::Box)
        .value("Sphere", ColliderType::Sphere)
        .value("Capsule", ColliderType::Capsule)
        .export_values();

    // ==================== Collider (базовый класс) ====================

    py::class_<Collider, ColliderPtr>(m, "Collider")
        .def("type", &Collider::type)
        .def("center", &Collider::center)
        .def("closest_to_ray", &Collider::closest_to_ray, py::arg("ray"))
        .def("closest_to_collider", &Collider::closest_to_collider, py::arg("other"))
        .def("transform_by", &Collider::transform_by, py::arg("pose"));

    // ==================== BoxCollider ====================

    py::class_<BoxCollider, Collider, std::shared_ptr<BoxCollider>>(m, "BoxCollider")
        .def(py::init<>())
        .def(py::init<const Vec3&, const Vec3&, const Pose3&>(),
             py::arg("center"), py::arg("half_size"), py::arg("pose") = Pose3())
        .def_static("from_size", &BoxCollider::from_size,
             py::arg("center"), py::arg("size"), py::arg("pose") = Pose3())
        .def_readwrite("local_center", &BoxCollider::local_center)
        .def_readwrite("half_size", &BoxCollider::half_size)
        .def_readwrite("pose", &BoxCollider::pose)
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
        .def("get_axes_world", [](const BoxCollider& b) {
            auto axes = b.get_axes_world();
            py::array_t<double> result({3, 3});
            auto buf = result.mutable_unchecked<2>();
            for (int i = 0; i < 3; i++) {
                buf(i, 0) = axes[i].x;
                buf(i, 1) = axes[i].y;
                buf(i, 2) = axes[i].z;
            }
            return result;
        })
        .def("collide_ground", &BoxCollider::collide_ground, py::arg("ground_height"));

    // BoxCollider::GroundContact
    py::class_<BoxCollider::GroundContact>(m, "BoxGroundContact")
        .def(py::init<>())
        .def_readwrite("point", &BoxCollider::GroundContact::point)
        .def_readwrite("penetration", &BoxCollider::GroundContact::penetration);

    // ==================== SphereCollider ====================

    py::class_<SphereCollider, Collider, std::shared_ptr<SphereCollider>>(m, "SphereCollider")
        .def(py::init<>())
        .def(py::init<const Vec3&, double, const Pose3&>(),
             py::arg("center"), py::arg("radius"), py::arg("pose") = Pose3())
        .def_readwrite("local_center", &SphereCollider::local_center)
        .def_readwrite("radius", &SphereCollider::radius)
        .def_readwrite("pose", &SphereCollider::pose)
        .def("collide_ground", &SphereCollider::collide_ground, py::arg("ground_height"));

    // SphereCollider::GroundContact
    py::class_<SphereCollider::GroundContact>(m, "SphereGroundContact")
        .def(py::init<>())
        .def_readwrite("point", &SphereCollider::GroundContact::point)
        .def_readwrite("normal", &SphereCollider::GroundContact::normal)
        .def_readwrite("penetration", &SphereCollider::GroundContact::penetration);

    // ==================== CapsuleCollider ====================

    py::class_<CapsuleCollider, Collider, std::shared_ptr<CapsuleCollider>>(m, "CapsuleCollider")
        .def(py::init<>())
        .def(py::init<const Vec3&, const Vec3&, double, const Pose3&>(),
             py::arg("a"), py::arg("b"), py::arg("radius"), py::arg("pose") = Pose3())
        .def_readwrite("local_a", &CapsuleCollider::local_a)
        .def_readwrite("local_b", &CapsuleCollider::local_b)
        .def_readwrite("radius", &CapsuleCollider::radius)
        .def_readwrite("pose", &CapsuleCollider::pose)
        .def("world_a", &CapsuleCollider::world_a)
        .def("world_b", &CapsuleCollider::world_b);

    // ==================== UnionCollider ====================

    py::class_<UnionCollider, Collider, std::shared_ptr<UnionCollider>>(m, "UnionCollider")
        .def(py::init<>())
        .def(py::init<std::vector<Collider*>>(),
             py::arg("colliders"),
             py::keep_alive<1, 2>())
        .def("colliders", &UnionCollider::colliders,
             py::return_value_policy::reference)
        .def("add", &UnionCollider::add, py::arg("collider"),
             py::keep_alive<1, 2>())
        .def("clear", &UnionCollider::clear)
        .def("center", &UnionCollider::center)
        .def("aabb", &UnionCollider::aabb)
        .def("closest_to_ray", &UnionCollider::closest_to_ray, py::arg("ray"))
        .def("closest_to_collider", &UnionCollider::closest_to_collider, py::arg("other"));

    // ==================== AttachedCollider ====================

    py::class_<AttachedCollider, Collider, std::shared_ptr<AttachedCollider>>(m, "AttachedCollider")
        .def(py::init<Collider*, GeneralTransform3*>(),
             py::arg("collider"), py::arg("transform"),
             py::keep_alive<1, 2>(),  // Keep collider alive
             py::keep_alive<1, 3>())  // Keep transform alive
        .def("collider", &AttachedCollider::collider,
             py::return_value_policy::reference)
        .def("transform", &AttachedCollider::transform,
             py::return_value_policy::reference)
        .def("world_pose", &AttachedCollider::world_pose)
        .def("center", &AttachedCollider::center)
        .def("aabb", &AttachedCollider::aabb)
        .def("closest_to_ray", &AttachedCollider::closest_to_ray, py::arg("ray"))
        .def("closest_to_collider", &AttachedCollider::closest_to_collider, py::arg("other"))
        .def("colliding", &AttachedCollider::colliding, py::arg("other"))
        .def("distance", &AttachedCollider::distance, py::arg("other"));
}
