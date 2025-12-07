#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/operators.h>
#include <pybind11/stl.h>

#include "termin/geom/geom.hpp"
#include "termin/physics/spatial_inertia.hpp"
#include "termin/physics/rigid_body.hpp"
#include "termin/physics/contact.hpp"
#include "termin/physics/physics_world.hpp"

namespace py = pybind11;
using namespace termin;
using namespace termin::geom;
using namespace termin::physics;

PYBIND11_MODULE(_physics_native, m) {
    m.doc() = "Native C++ physics module for termin";

    // Import _geom_native for Vec3, Quat, Pose3, Screw3
    py::module_::import("termin.geombase._geom_native");

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
