#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include "termin/geom/geom.hpp"
#include "termin/physics/physics.hpp"
#include "termin/collision/collision_world.hpp"

namespace nb = nanobind;
using namespace termin;
using namespace termin::physics;

NB_MODULE(_physics_native, m) {
    m.doc() = "Native C++ physics module for termin";

    // Import _geom_native for Vec3, Quat, Pose3
    nb::module_::import_("termin.geombase._geom_native");

    // ==================== RigidBody ====================
    nb::class_<RigidBody>(m, "RigidBody")
        .def(nb::init<>())

        // Состояние
        .def_rw("pose", &RigidBody::pose)
        .def_rw("linear_velocity", &RigidBody::linear_velocity)
        .def_rw("angular_velocity", &RigidBody::angular_velocity)

        // Масса и инерция
        .def_rw("mass", &RigidBody::mass)
        .def_rw("inertia", &RigidBody::inertia)

        // Силы
        .def_rw("force", &RigidBody::force)
        .def_rw("torque", &RigidBody::torque)

        // Флаги
        .def_rw("is_static", &RigidBody::is_static)
        .def_rw("is_kinematic", &RigidBody::is_kinematic)

        // Демпфирование
        .def_rw("linear_damping", &RigidBody::linear_damping)
        .def_rw("angular_damping", &RigidBody::angular_damping)

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
            nb::arg("sx"), nb::arg("sy"), nb::arg("sz"),
            nb::arg("mass"), nb::arg("pose") = Pose3(), nb::arg("is_static") = false)
        .def_static("create_sphere", &RigidBody::create_sphere,
            nb::arg("radius"), nb::arg("mass"),
            nb::arg("pose") = Pose3(), nb::arg("is_static") = false);

    // ==================== Contact ====================
    nb::class_<Contact>(m, "Contact")
        .def(nb::init<>())
        .def_ro("point", &Contact::point)
        .def_ro("normal", &Contact::normal)
        .def_ro("penetration", &Contact::penetration)
        .def_ro("accumulated_normal", &Contact::accumulated_normal)
        .def_ro("accumulated_tangent1", &Contact::accumulated_tangent1)
        .def_ro("accumulated_tangent2", &Contact::accumulated_tangent2);

    // ==================== PhysicsWorld ====================
    nb::class_<PhysicsWorld>(m, "PhysicsWorld")
        .def(nb::init<>())

        // Параметры симуляции
        .def_rw("gravity", &PhysicsWorld::gravity)
        .def_rw("solver_iterations", &PhysicsWorld::solver_iterations)

        // Параметры контактов
        .def_rw("restitution", &PhysicsWorld::restitution)
        .def_rw("friction", &PhysicsWorld::friction)

        // Земля
        .def_rw("ground_enabled", &PhysicsWorld::ground_enabled)
        .def_rw("ground_height", &PhysicsWorld::ground_height)

        // Collision world
        .def("set_collision_world", &PhysicsWorld::set_collision_world,
            nb::arg("collision_world"), nb::keep_alive<1, 2>())
        .def("collision_world", &PhysicsWorld::collision_world,
             nb::rv_policy::reference)

        // Управление телами
        .def("add_body", &PhysicsWorld::add_body)
        .def("register_collider", &PhysicsWorld::register_collider,
            nb::arg("body_idx"), nb::arg("collider"))
        .def("get_body", nb::overload_cast<size_t>(&PhysicsWorld::get_body),
             nb::rv_policy::reference)
        .def("body_count", &PhysicsWorld::body_count)
        .def("clear", &PhysicsWorld::clear)

        // Фабрики
        .def("add_box", &PhysicsWorld::add_box,
            nb::arg("sx"), nb::arg("sy"), nb::arg("sz"),
            nb::arg("mass"), nb::arg("pose"), nb::arg("is_static") = false)
        .def("add_sphere", &PhysicsWorld::add_sphere,
            nb::arg("radius"), nb::arg("mass"),
            nb::arg("pose"), nb::arg("is_static") = false)

        // Симуляция
        .def("step", &PhysicsWorld::step)

        // Массовый доступ к данным
        .def("get_positions", [](const PhysicsWorld& world) {
            size_t n = world.body_count();
            double* data = new double[n * 3];
            for (size_t i = 0; i < n; ++i) {
                const auto& pos = world.get_body(i).pose.lin;
                data[i * 3 + 0] = pos.x;
                data[i * 3 + 1] = pos.y;
                data[i * 3 + 2] = pos.z;
            }
            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
            size_t shape[2] = {n, 3};
            return nb::ndarray<nb::numpy, double>(data, 2, shape, owner);
        })
        .def("get_rotations", [](const PhysicsWorld& world) {
            size_t n = world.body_count();
            double* data = new double[n * 4];
            for (size_t i = 0; i < n; ++i) {
                const auto& q = world.get_body(i).pose.ang;
                data[i * 4 + 0] = q.x;
                data[i * 4 + 1] = q.y;
                data[i * 4 + 2] = q.z;
                data[i * 4 + 3] = q.w;
            }
            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
            size_t shape[2] = {n, 4};
            return nb::ndarray<nb::numpy, double>(data, 2, shape, owner);
        })
        .def("get_velocities", [](const PhysicsWorld& world) {
            size_t n = world.body_count();
            double* data = new double[n * 3];
            for (size_t i = 0; i < n; ++i) {
                const auto& v = world.get_body(i).linear_velocity;
                data[i * 3 + 0] = v.x;
                data[i * 3 + 1] = v.y;
                data[i * 3 + 2] = v.z;
            }
            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
            size_t shape[2] = {n, 3};
            return nb::ndarray<nb::numpy, double>(data, 2, shape, owner);
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
            double* data = new double[n * 3];
            for (size_t i = 0; i < n; ++i) {
                data[i * 3 + 0] = contacts[i].point.x;
                data[i * 3 + 1] = contacts[i].point.y;
                data[i * 3 + 2] = contacts[i].point.z;
            }
            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
            size_t shape[2] = {n, 3};
            return nb::ndarray<nb::numpy, double>(data, 2, shape, owner);
        });
}
