#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include "termin/geom/geom.hpp"
#include "termin/physics/physics.hpp"
#include "termin/collision/collision_world.hpp"

namespace py = pybind11;
using namespace termin;
using namespace termin;
using namespace termin::physics;

PYBIND11_MODULE(_physics_native, m) {
    m.doc() = "Native C++ physics module for termin";

    // Import _geom_native for Vec3, Quat, Pose3
    py::module_::import("termin.geombase._geom_native");

    // ==================== RigidBody ====================
    py::class_<RigidBody>(m, "RigidBody")
        .def(py::init<>())

        // Состояние
        .def_readwrite("pose", &RigidBody::pose)
        .def_readwrite("linear_velocity", &RigidBody::linear_velocity)
        .def_readwrite("angular_velocity", &RigidBody::angular_velocity)

        // Масса и инерция
        .def_readwrite("mass", &RigidBody::mass)
        .def_readwrite("inertia", &RigidBody::inertia)

        // Силы
        .def_readwrite("force", &RigidBody::force)
        .def_readwrite("torque", &RigidBody::torque)

        // Флаги
        .def_readwrite("is_static", &RigidBody::is_static)
        .def_readwrite("is_kinematic", &RigidBody::is_kinematic)

        // Демпфирование
        .def_readwrite("linear_damping", &RigidBody::linear_damping)
        .def_readwrite("angular_damping", &RigidBody::angular_damping)

        // Методы
        .def("inv_mass", &RigidBody::inv_mass)
        .def("inv_inertia", &RigidBody::inv_inertia)
        .def("position", &RigidBody::position)
        .def("point_velocity", &RigidBody::point_velocity)

        .def("add_force", &RigidBody::add_force)
        .def("add_torque", &RigidBody::add_torque)
        .def("add_force_at_point", &RigidBody::add_force_at_point)

        .def("apply_impulse", &RigidBody::apply_impulse)
        .def("apply_angular_impulse", &RigidBody::apply_angular_impulse)
        .def("apply_impulse_at_point", &RigidBody::apply_impulse_at_point)

        .def("integrate_forces", &RigidBody::integrate_forces)
        .def("integrate_positions", &RigidBody::integrate_positions)

        // Фабрики
        .def_static("create_box", &RigidBody::create_box,
            py::arg("sx"), py::arg("sy"), py::arg("sz"),
            py::arg("mass"), py::arg("pose") = Pose3(), py::arg("is_static") = false)
        .def_static("create_sphere", &RigidBody::create_sphere,
            py::arg("radius"), py::arg("mass"),
            py::arg("pose") = Pose3(), py::arg("is_static") = false);

    // ==================== Contact ====================
    py::class_<Contact>(m, "Contact")
        .def(py::init<>())
        .def_readonly("point", &Contact::point)
        .def_readonly("normal", &Contact::normal)
        .def_readonly("penetration", &Contact::penetration)
        .def_readonly("accumulated_normal", &Contact::accumulated_normal)
        .def_readonly("accumulated_tangent1", &Contact::accumulated_tangent1)
        .def_readonly("accumulated_tangent2", &Contact::accumulated_tangent2);

    // ==================== PhysicsWorld ====================
    py::class_<PhysicsWorld>(m, "PhysicsWorld")
        .def(py::init<>())

        // Параметры симуляции
        .def_readwrite("gravity", &PhysicsWorld::gravity)
        .def_readwrite("solver_iterations", &PhysicsWorld::solver_iterations)

        // Параметры контактов
        .def_readwrite("restitution", &PhysicsWorld::restitution)
        .def_readwrite("friction", &PhysicsWorld::friction)

        // Земля
        .def_readwrite("ground_enabled", &PhysicsWorld::ground_enabled)
        .def_readwrite("ground_height", &PhysicsWorld::ground_height)

        // Collision world
        .def("set_collision_world", &PhysicsWorld::set_collision_world,
            py::arg("collision_world"), py::keep_alive<1, 2>())
        .def("collision_world", &PhysicsWorld::collision_world,
             py::return_value_policy::reference)

        // Управление телами
        .def("add_body", &PhysicsWorld::add_body)
        .def("register_collider", &PhysicsWorld::register_collider,
            py::arg("body_idx"), py::arg("collider"))
        .def("get_body", py::overload_cast<size_t>(&PhysicsWorld::get_body),
             py::return_value_policy::reference)
        .def("body_count", &PhysicsWorld::body_count)
        .def("clear", &PhysicsWorld::clear)

        // Фабрики
        .def("add_box", &PhysicsWorld::add_box,
            py::arg("sx"), py::arg("sy"), py::arg("sz"),
            py::arg("mass"), py::arg("pose"), py::arg("is_static") = false)
        .def("add_sphere", &PhysicsWorld::add_sphere,
            py::arg("radius"), py::arg("mass"),
            py::arg("pose"), py::arg("is_static") = false)

        // Симуляция
        .def("step", &PhysicsWorld::step)

        // Массовый доступ к данным
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
        })
        .def("get_velocities", [](const PhysicsWorld& world) {
            size_t n = world.body_count();
            py::array_t<double> result({(int)n, 3});
            auto buf = result.mutable_unchecked<2>();
            for (size_t i = 0; i < n; ++i) {
                const auto& v = world.get_body(i).linear_velocity;
                buf(i, 0) = v.x;
                buf(i, 1) = v.y;
                buf(i, 2) = v.z;
            }
            return result;
        })

        // Доступ к контактам
        .def("contact_count", [](const PhysicsWorld& world) {
            return world.contacts().size();
        })
        .def("contacts", [](const PhysicsWorld& world) {
            return world.contacts();
        })
        .def("get_contact_points", [](const PhysicsWorld& world) {
            const auto& contacts = world.contacts();
            size_t n = contacts.size();
            py::array_t<double> result({(int)n, 3});
            auto buf = result.mutable_unchecked<2>();
            for (size_t i = 0; i < n; ++i) {
                buf(i, 0) = contacts[i].point.x;
                buf(i, 1) = contacts[i].point.y;
                buf(i, 2) = contacts[i].point.z;
            }
            return result;
        });
}
