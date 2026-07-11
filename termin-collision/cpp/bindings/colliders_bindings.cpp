#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/operators.h>
#include <nanobind/stl/optional.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/shared_ptr.h>

#include <termin/geom/geom.hpp>
#include <termin/geom/general_transform3.hpp>
#include "termin/colliders/colliders.hpp"

namespace nb = nanobind;
using namespace termin;
using namespace termin::colliders;

NB_MODULE(_colliders_native, m) {
    m.doc() = "Native C++ colliders module for termin";

    // Import _geom_native for Vec3, Quat, Pose3, GeneralPose3, Ray3
    nb::module_::import_("tcbase._geom_native");

    // ==================== Результаты запросов ====================

    nb::class_<RayHit>(m, "RayHit")
        .def(nb::init<>())
        .def_rw("point_on_collider", &RayHit::point_on_collider)
        .def_rw("point_on_ray", &RayHit::point_on_ray)
        .def_rw("distance", &RayHit::distance)
        .def("hit", &RayHit::hit);

    nb::class_<ColliderHit>(m, "ColliderHit")
        .def(nb::init<>())
        .def_rw("point_on_a", &ColliderHit::point_on_a)
        .def_rw("point_on_b", &ColliderHit::point_on_b)
        .def_rw("normal", &ColliderHit::normal)
        .def_rw("distance", &ColliderHit::distance)
        .def("colliding", &ColliderHit::colliding);

    // ==================== ColliderType ====================

    nb::enum_<ColliderType>(m, "ColliderType")
        .value("Box", ColliderType::Box)
        .value("Sphere", ColliderType::Sphere)
        .value("Capsule", ColliderType::Capsule)
        .export_values();

    // ==================== Collider (базовый интерфейс) ====================

    nb::class_<Collider>(m, "Collider")
        .def("type", &Collider::type)
        .def("center", &Collider::center)
        .def("aabb", &Collider::aabb)
        .def("closest_to_ray", &Collider::closest_to_ray, nb::arg("ray"))
        .def("closest_to_collider", &Collider::closest_to_collider, nb::arg("other"))
        // Velocity hints for physics systems
        .def_rw("linear_velocity", &Collider::linear_velocity)
        .def_rw("angular_velocity", &Collider::angular_velocity)
        .def("point_velocity", &Collider::point_velocity, nb::arg("world_point"));

    // ==================== ColliderPrimitive ====================

    nb::class_<ColliderPrimitive, Collider>(m, "ColliderPrimitive")
        .def_rw("transform", &ColliderPrimitive::transform)
        .def("uniform_scale", &ColliderPrimitive::uniform_scale)
        .def("pose", &ColliderPrimitive::pose);

    // ==================== BoxCollider ====================

    nb::class_<BoxCollider, ColliderPrimitive>(m, "BoxCollider")
        .def(nb::init<>())
        .def("__init__", [](BoxCollider* self, const Vec3& half_size,
                            std::optional<GeneralPose3> transform) {
            new (self) BoxCollider{half_size, transform.value_or(GeneralPose3{})};
        }, nb::arg("half_size"), nb::arg("transform").none() = nb::none())
        .def_static("from_size", [](const Vec3& size,
                                     std::optional<GeneralPose3> transform) {
            return BoxCollider::from_size(size, transform.value_or(GeneralPose3{}));
        }, nb::arg("size"), nb::arg("transform").none() = nb::none())
        .def_rw("half_size", &BoxCollider::half_size)
        .def("effective_half_size", &BoxCollider::effective_half_size)
        .def("get_corners_world", [](const BoxCollider& b) {
            auto corners = b.get_corners_world();
            double* data = new double[24];
            for (int i = 0; i < 8; i++) {
                data[i * 3 + 0] = corners[i].x;
                data[i * 3 + 1] = corners[i].y;
                data[i * 3 + 2] = corners[i].z;
            }
            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
            size_t shape[2] = {8, 3};
            return nb::ndarray<nb::numpy, double, nb::shape<8, 3>>(data, 2, shape, owner);
        })
        .def("get_axes_world", [](const BoxCollider& b) {
            auto axes = b.get_axes_world();
            double* data = new double[9];
            for (int i = 0; i < 3; i++) {
                data[i * 3 + 0] = axes[i].x;
                data[i * 3 + 1] = axes[i].y;
                data[i * 3 + 2] = axes[i].z;
            }
            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
            size_t shape[2] = {3, 3};
            return nb::ndarray<nb::numpy, double, nb::shape<3, 3>>(data, 2, shape, owner);
        })
        .def("collide_ground", &BoxCollider::collide_ground, nb::arg("ground_height"));

    // BoxCollider::GroundContact
    nb::class_<BoxCollider::GroundContact>(m, "BoxGroundContact")
        .def(nb::init<>())
        .def_rw("point", &BoxCollider::GroundContact::point)
        .def_rw("penetration", &BoxCollider::GroundContact::penetration);

    // ==================== SphereCollider ====================

    nb::class_<SphereCollider, ColliderPrimitive>(m, "SphereCollider")
        .def(nb::init<>())
        .def("__init__", [](SphereCollider* self, double radius,
                            std::optional<GeneralPose3> transform) {
            new (self) SphereCollider{radius, transform.value_or(GeneralPose3{})};
        }, nb::arg("radius"), nb::arg("transform").none() = nb::none())
        .def_rw("radius", &SphereCollider::radius)
        .def("effective_radius", &SphereCollider::effective_radius)
        .def("collide_ground", &SphereCollider::collide_ground, nb::arg("ground_height"));

    // SphereCollider::GroundContact
    nb::class_<SphereCollider::GroundContact>(m, "SphereGroundContact")
        .def(nb::init<>())
        .def_rw("point", &SphereCollider::GroundContact::point)
        .def_rw("normal", &SphereCollider::GroundContact::normal)
        .def_rw("penetration", &SphereCollider::GroundContact::penetration);

    // ==================== CapsuleCollider ====================

    nb::class_<CapsuleCollider, ColliderPrimitive>(m, "CapsuleCollider")
        .def(nb::init<>())
        .def("__init__", [](CapsuleCollider* self, double half_height, double radius,
                            std::optional<GeneralPose3> transform) {
            new (self) CapsuleCollider{
                half_height, radius, transform.value_or(GeneralPose3{})};
        }, nb::arg("half_height"), nb::arg("radius"),
           nb::arg("transform").none() = nb::none())
        .def_static("from_total_height", [](double total_height, double radius,
                                             std::optional<GeneralPose3> transform) {
            return CapsuleCollider::from_total_height(
                total_height, radius, transform.value_or(GeneralPose3{}));
        }, nb::arg("total_height"), nb::arg("radius"),
           nb::arg("transform").none() = nb::none())
        .def_rw("half_height", &CapsuleCollider::half_height)
        .def_rw("radius", &CapsuleCollider::radius)
        .def("effective_half_height", &CapsuleCollider::effective_half_height)
        .def("effective_radius", &CapsuleCollider::effective_radius)
        .def("axis_direction", &CapsuleCollider::axis_direction)
        .def("world_a", &CapsuleCollider::world_a)
        .def("world_b", &CapsuleCollider::world_b);

    // ==================== UnionCollider ====================

    nb::class_<UnionCollider, Collider>(m, "UnionCollider")
        .def(nb::init<>())
        .def("__init__", [](UnionCollider* self, std::vector<Collider*> colliders) {
            new (self) UnionCollider(colliders);
        }, nb::arg("colliders"), nb::keep_alive<1, 2>())
        .def("colliders", &UnionCollider::colliders,
             nb::rv_policy::reference)
        .def("add", &UnionCollider::add, nb::arg("collider"),
             nb::keep_alive<1, 2>())
        .def("clear", &UnionCollider::clear);

    // ==================== AttachedCollider ====================

    nb::class_<AttachedCollider, Collider>(m, "AttachedCollider")
        .def("__init__", [](AttachedCollider* self, ColliderPrimitive* collider, GeneralTransform3* transform) {
            new (self) AttachedCollider(collider, transform);
        }, nb::arg("collider"), nb::arg("transform"),
             nb::keep_alive<1, 2>(),  // Keep collider alive
             nb::keep_alive<1, 3>())  // Keep transform alive
        .def("collider", &AttachedCollider::collider,
             nb::rv_policy::reference)
        .def("transform", &AttachedCollider::transform,
             nb::rv_policy::reference)
        .def("world_transform", &AttachedCollider::world_transform)
        .def("colliding", &AttachedCollider::colliding, nb::arg("other"))
        .def("distance", &AttachedCollider::distance, nb::arg("other"));
}
