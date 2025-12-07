#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/operators.h>
#include <pybind11/stl.h>

#include "termin/geom/geom.hpp"
#include "termin/physics/spatial_inertia.hpp"
#include "termin/physics/rigid_body.hpp"
#include "termin/physics/contact.hpp"
#include "termin/physics/physics_world.hpp"
#include "termin/colliders/box_collider.hpp"
#include "termin/colliders/sphere_collider.hpp"

namespace py = pybind11;
using namespace termin;
using namespace termin::geom;
using namespace termin::physics;
using namespace termin::colliders;

// Helper to create numpy array from Vec3
py::array_t<double> vec3_to_numpy(const Vec3& v) {
    auto result = py::array_t<double>(3);
    auto buf = result.mutable_unchecked<1>();
    buf(0) = v.x;
    buf(1) = v.y;
    buf(2) = v.z;
    return result;
}

// Helper to create Vec3 from numpy array
Vec3 numpy_to_vec3(py::array_t<double> arr) {
    auto buf = arr.unchecked<1>();
    return {buf(0), buf(1), buf(2)};
}

// Helper to create numpy array from Quat
py::array_t<double> quat_to_numpy(const Quat& q) {
    auto result = py::array_t<double>(4);
    auto buf = result.mutable_unchecked<1>();
    buf(0) = q.x;
    buf(1) = q.y;
    buf(2) = q.z;
    buf(3) = q.w;
    return result;
}

// Helper to create Quat from numpy array
Quat numpy_to_quat(py::array_t<double> arr) {
    auto buf = arr.unchecked<1>();
    return {buf(0), buf(1), buf(2), buf(3)};
}

PYBIND11_MODULE(_geom_native, m) {
    m.doc() = "Native C++ geometry and physics module for termin";

    // Vec3
    py::class_<Vec3>(m, "Vec3")
        .def(py::init<>())
        .def(py::init<double, double, double>())
        .def(py::init([](py::array_t<double> arr) {
            return numpy_to_vec3(arr);
        }))
        .def_readwrite("x", &Vec3::x)
        .def_readwrite("y", &Vec3::y)
        .def_readwrite("z", &Vec3::z)
        .def("__getitem__", [](const Vec3& v, int i) { return v[i]; })
        .def("__setitem__", [](Vec3& v, int i, double val) { v[i] = val; })
        .def(py::self + py::self)
        .def(py::self - py::self)
        .def(py::self * double())
        .def(double() * py::self)
        .def(py::self / double())
        .def(-py::self)
        .def("dot", &Vec3::dot)
        .def("cross", &Vec3::cross)
        .def("norm", &Vec3::norm)
        .def("norm_squared", &Vec3::norm_squared)
        .def("normalized", &Vec3::normalized)
        .def_static("zero", &Vec3::zero)
        .def_static("unit_x", &Vec3::unit_x)
        .def_static("unit_y", &Vec3::unit_y)
        .def_static("unit_z", &Vec3::unit_z)
        .def("to_numpy", &vec3_to_numpy)
        .def("__repr__", [](const Vec3& v) {
            return "Vec3(" + std::to_string(v.x) + ", " +
                   std::to_string(v.y) + ", " + std::to_string(v.z) + ")";
        });

    // Quat
    py::class_<Quat>(m, "Quat")
        .def(py::init<>())
        .def(py::init<double, double, double, double>())
        .def(py::init([](py::array_t<double> arr) {
            return numpy_to_quat(arr);
        }))
        .def_readwrite("x", &Quat::x)
        .def_readwrite("y", &Quat::y)
        .def_readwrite("z", &Quat::z)
        .def_readwrite("w", &Quat::w)
        .def(py::self * py::self)
        .def("conjugate", &Quat::conjugate)
        .def("inverse", &Quat::inverse)
        .def("norm", &Quat::norm)
        .def("normalized", &Quat::normalized)
        .def("rotate", &Quat::rotate)
        .def("inverse_rotate", &Quat::inverse_rotate)
        .def_static("identity", &Quat::identity)
        .def_static("from_axis_angle", &Quat::from_axis_angle)
        .def("to_numpy", &quat_to_numpy)
        .def("__repr__", [](const Quat& q) {
            return "Quat(" + std::to_string(q.x) + ", " +
                   std::to_string(q.y) + ", " + std::to_string(q.z) + ", " +
                   std::to_string(q.w) + ")";
        });

    m.def("slerp", &slerp, "Spherical linear interpolation between quaternions");

    // Pose3
    py::class_<Pose3>(m, "Pose3")
        .def(py::init<>())
        .def(py::init<const Quat&, const Vec3&>())
        .def(py::init([](py::array_t<double> ang_arr, py::array_t<double> lin_arr) {
            return Pose3(numpy_to_quat(ang_arr), numpy_to_vec3(lin_arr));
        }))
        .def_readwrite("ang", &Pose3::ang)
        .def_readwrite("lin", &Pose3::lin)
        .def(py::self * py::self)
        .def("inverse", &Pose3::inverse)
        .def("transform_point", &Pose3::transform_point)
        .def("transform_vector", &Pose3::transform_vector)
        .def("rotate_point", &Pose3::rotate_point)
        .def("inverse_transform_point", &Pose3::inverse_transform_point)
        .def("inverse_transform_vector", &Pose3::inverse_transform_vector)
        .def("normalized", &Pose3::normalized)
        .def("with_translation", py::overload_cast<const Vec3&>(&Pose3::with_translation, py::const_))
        .def("with_rotation", &Pose3::with_rotation)
        .def("rotation_matrix", [](const Pose3& p) {
            auto result = py::array_t<double>({3, 3});
            auto buf = result.mutable_unchecked<2>();
            double m[9];
            p.rotation_matrix(m);
            for (int i = 0; i < 3; i++)
                for (int j = 0; j < 3; j++)
                    buf(i, j) = m[i * 3 + j];
            return result;
        })
        .def_static("identity", &Pose3::identity)
        .def_static("translation", py::overload_cast<double, double, double>(&Pose3::translation))
        .def_static("rotation", &Pose3::rotation)
        .def_static("rotate_x", &Pose3::rotate_x)
        .def_static("rotate_y", &Pose3::rotate_y)
        .def_static("rotate_z", &Pose3::rotate_z)
        .def("__repr__", [](const Pose3& p) {
            return "Pose3(ang=Quat(" + std::to_string(p.ang.x) + ", " +
                   std::to_string(p.ang.y) + ", " + std::to_string(p.ang.z) + ", " +
                   std::to_string(p.ang.w) + "), lin=Vec3(" +
                   std::to_string(p.lin.x) + ", " + std::to_string(p.lin.y) + ", " +
                   std::to_string(p.lin.z) + "))";
        });

    m.def("lerp", py::overload_cast<const Pose3&, const Pose3&, double>(&lerp),
          "Linear interpolation between poses");

    // Screw3
    py::class_<Screw3>(m, "Screw3")
        .def(py::init<>())
        .def(py::init<const Vec3&, const Vec3&>())
        .def(py::init([](py::array_t<double> ang_arr, py::array_t<double> lin_arr) {
            return Screw3(numpy_to_vec3(ang_arr), numpy_to_vec3(lin_arr));
        }))
        .def_readwrite("ang", &Screw3::ang)
        .def_readwrite("lin", &Screw3::lin)
        .def(py::self + py::self)
        .def(py::self - py::self)
        .def(py::self * double())
        .def(double() * py::self)
        .def(-py::self)
        .def("dot", &Screw3::dot)
        .def("cross_motion", &Screw3::cross_motion)
        .def("cross_force", &Screw3::cross_force)
        .def("transform_by", &Screw3::transform_by)
        .def("inverse_transform_by", &Screw3::inverse_transform_by)
        .def("to_pose", &Screw3::to_pose)
        .def("scaled", &Screw3::scaled)
        .def_static("zero", &Screw3::zero)
        .def("__repr__", [](const Screw3& s) {
            return "Screw3(ang=Vec3(" + std::to_string(s.ang.x) + ", " +
                   std::to_string(s.ang.y) + ", " + std::to_string(s.ang.z) +
                   "), lin=Vec3(" + std::to_string(s.lin.x) + ", " +
                   std::to_string(s.lin.y) + ", " + std::to_string(s.lin.z) + "))";
        });

    // SpatialInertia3D
    py::class_<SpatialInertia3D>(m, "SpatialInertia3D")
        .def(py::init<>())
        .def(py::init<double, const Vec3&, const Pose3&>(),
             py::arg("mass"), py::arg("I_diag"), py::arg("frame") = Pose3())
        .def_readwrite("mass", &SpatialInertia3D::mass)
        .def_readwrite("I_diag", &SpatialInertia3D::I_diag)
        .def_readwrite("frame", &SpatialInertia3D::frame)
        .def("inv_mass", &SpatialInertia3D::inv_mass)
        .def("inv_I_diag", &SpatialInertia3D::inv_I_diag)
        .def("com", &SpatialInertia3D::com)
        .def("apply", &SpatialInertia3D::apply)
        .def("solve", &SpatialInertia3D::solve)
        .def("gravity_wrench", &SpatialInertia3D::gravity_wrench)
        .def("bias_wrench", &SpatialInertia3D::bias_wrench);

    // RigidBody
    py::class_<RigidBody>(m, "RigidBody")
        .def(py::init<>())
        .def(py::init<const SpatialInertia3D&, const Pose3&, bool>(),
             py::arg("inertia"), py::arg("pose"), py::arg("is_static") = false)
        .def_readwrite("inertia", &RigidBody::inertia)
        .def_readwrite("pose", &RigidBody::pose)
        .def_readwrite("velocity", &RigidBody::velocity)
        .def_readwrite("wrench", &RigidBody::wrench)
        .def_readwrite("is_static", &RigidBody::is_static)
        .def_readwrite("half_extents", &RigidBody::half_extents)
        .def_readwrite("has_collider", &RigidBody::has_collider)
        .def("mass", &RigidBody::mass)
        .def("inv_mass", &RigidBody::inv_mass)
        .def("position", &RigidBody::position)
        .def("point_velocity", &RigidBody::point_velocity)
        .def("apply_impulse", &RigidBody::apply_impulse)
        .def("integrate_forces", &RigidBody::integrate_forces)
        .def("integrate_positions", &RigidBody::integrate_positions)
        .def("get_box_corners_world", [](const RigidBody& b) {
            py::array_t<double> result({8, 3});
            auto buf = result.mutable_unchecked<2>();
            double corners[24];
            b.get_box_corners_world(corners);
            for (int i = 0; i < 8; i++) {
                buf(i, 0) = corners[i*3 + 0];
                buf(i, 1) = corners[i*3 + 1];
                buf(i, 2) = corners[i*3 + 2];
            }
            return result;
        })
        .def_static("create_box", &RigidBody::create_box,
             py::arg("sx"), py::arg("sy"), py::arg("sz"),
             py::arg("mass"), py::arg("pose"), py::arg("is_static") = false);

    // Contact
    py::class_<Contact>(m, "Contact")
        .def(py::init<>())
        .def_readwrite("point", &Contact::point)
        .def_readwrite("normal", &Contact::normal)
        .def_readwrite("penetration", &Contact::penetration)
        .def_readwrite("accumulated_normal_impulse", &Contact::accumulated_normal_impulse)
        .def_readwrite("accumulated_tangent_impulse1", &Contact::accumulated_tangent_impulse1)
        .def_readwrite("accumulated_tangent_impulse2", &Contact::accumulated_tangent_impulse2);

    // ContactConstraint
    py::class_<ContactConstraint>(m, "ContactConstraint")
        .def(py::init<Contact*, double, double, double, double>(),
             py::arg("contact"), py::arg("restitution") = 0.3,
             py::arg("friction") = 0.5, py::arg("baumgarte") = 0.2,
             py::arg("slop") = 0.005)
        .def("precompute", &ContactConstraint::precompute)
        .def("relative_velocity", &ContactConstraint::relative_velocity)
        .def("solve_normal", &ContactConstraint::solve_normal)
        .def("solve_friction", &ContactConstraint::solve_friction)
        .def("apply_impulse", &ContactConstraint::apply_impulse);

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

    // PhysicsWorld
    py::class_<PhysicsWorld>(m, "PhysicsWorld")
        .def(py::init<>())
        .def_readwrite("gravity", &PhysicsWorld::gravity)
        .def_readwrite("iterations", &PhysicsWorld::iterations)
        .def_readwrite("restitution", &PhysicsWorld::restitution)
        .def_readwrite("friction", &PhysicsWorld::friction)
        .def_readwrite("ground_height", &PhysicsWorld::ground_height)
        .def_readwrite("ground_enabled", &PhysicsWorld::ground_enabled)
        .def_readwrite("fixed_dt", &PhysicsWorld::fixed_dt)
        .def_readwrite("max_substeps", &PhysicsWorld::max_substeps)
        .def("add_body", &PhysicsWorld::add_body)
        .def("get_body", py::overload_cast<size_t>(&PhysicsWorld::get_body),
             py::return_value_policy::reference)
        .def("body_count", &PhysicsWorld::body_count)
        .def("step", &PhysicsWorld::step)
        // Helper to add a box body directly
        .def("add_box", [](PhysicsWorld& world, double sx, double sy, double sz,
                          double mass, const Pose3& pose, bool is_static) {
            RigidBody body = RigidBody::create_box(sx, sy, sz, mass, pose, is_static);
            return world.add_body(body);
        }, py::arg("sx"), py::arg("sy"), py::arg("sz"),
           py::arg("mass"), py::arg("pose"), py::arg("is_static") = false)
        // Get body positions as numpy array
        .def("get_positions", [](const PhysicsWorld& world) {
            size_t n = world.body_count();
            py::array_t<double> result({(int)n, 3});
            auto buf = result.mutable_unchecked<2>();
            for (size_t i = 0; i < n; ++i) {
                const auto& pos = world.get_body(i).pose.lin;
                buf(i, 0) = pos.x;
                buf(i, 1) = pos.y;
                buf(i, 2) = pos.z;
            }
            return result;
        })
        // Get body quaternions as numpy array
        .def("get_rotations", [](const PhysicsWorld& world) {
            size_t n = world.body_count();
            py::array_t<double> result({(int)n, 4});
            auto buf = result.mutable_unchecked<2>();
            for (size_t i = 0; i < n; ++i) {
                const auto& q = world.get_body(i).pose.ang;
                buf(i, 0) = q.x;
                buf(i, 1) = q.y;
                buf(i, 2) = q.z;
                buf(i, 3) = q.w;
            }
            return result;
        });
}
