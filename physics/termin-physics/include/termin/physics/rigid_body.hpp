#pragma once

// @file rigid_body.hpp
// @brief Простое твердое тело для игровой физики.
//
// Модель:
// - pose: позиция центра масс + ориентация (SE(3))
// - velocity: линейная + угловая скорости в мировой СК
// - mass, inertia: масса и главные моменты инерции
//
// Угловая динамика учитывает гироскопический момент: tau_gyro = omega x (I·omega)

#include <termin/geom/mat33.hpp>
#include <termin/geom/pose3.hpp>
#include <termin/geom/quat.hpp>
#include <termin/geom/vec3.hpp>
#include <termin/physics/mass_properties.hpp>
#include <termin/physics/termin_physics_api.hpp>

namespace termin {
    namespace physics {

        class TERMIN_PHYSICS_API RigidBody {
        public:
            // Состояние
            Pose3 pose;
            Vec3 linear_velocity;
            Vec3 angular_velocity;

            // Масса и инерция. pose.lin хранит мировой центр масс, pose.ang —
            // ориентацию authored shape frame. inertia_frame_local задаёт центр масс
            // и главные оси относительно authored frame.
            double mass = 1.0;
            Vec3 inertia{1.0, 1.0, 1.0};
            Pose3 inertia_frame_local{};

            // Аккумуляторы сил
            Vec3 force;
            Vec3 torque;

            // Флаги
            bool is_static = false;
            bool is_kinematic = false;

            // Демпфирование
            double linear_damping = 0.01;
            double angular_damping = 0.01;

        public:
            RigidBody() = default;

            // Создать тело с инерцией параллелепипеда.
            // @param size - полные размеры (не half)
            static RigidBody
            create_box(const Vec3& size, double m, const Pose3& p = Pose3(), bool stat = false);

            // Создать тело с инерцией сферы.
            static RigidBody create_sphere(double radius, double m, const Pose3& p = Pose3(), bool stat = false);

            // Создать тело из mass properties и мировой позы authored shape frame.
            static RigidBody create_with_mass_properties(const SpatialInertia3& properties,
                                                         const Pose3& shape_pose = Pose3(),
                                                         bool stat = false);

            // Мировая поза authored shape frame. В отличие от pose, translation здесь
            // является entity/shape origin, а не центром масс.
            Pose3 shape_pose() const;

            // Обновить authored shape pose, сохранив локальную inertia frame.
            void set_shape_pose(const Pose3& shape_pose);

            double inv_mass() const;

            Vec3 inv_inertia() const;

            Vec3 position() const;

            // I_world^-1 = R_principal * diag(I^-1) * R_principal^T
            Mat33 world_inertia_inv() const;

            Vec3 apply_inv_inertia_world(const Vec3& v) const;

            Vec3 point_velocity(const Vec3& world_point) const;

            void add_force(const Vec3& f);

            void add_torque(const Vec3& t);

            void add_force_at_point(const Vec3& f, const Vec3& world_point);

            void apply_impulse(const Vec3& impulse);

            void apply_angular_impulse(const Vec3& ang_impulse);

            void apply_impulse_at_point(const Vec3& impulse, const Vec3& world_point);

            // Интеграция сил -> скорости.
            //
            // Линейная: v += (g + F/m) * dt
            // Угловая: omega += I_world^-1 * (tau - omega x L) * dt
            void integrate_forces(double dt, const Vec3& gravity);

            // Интеграция скоростей -> позиции.
            void integrate_positions(double dt);
        };

    } // namespace physics
} // namespace termin
