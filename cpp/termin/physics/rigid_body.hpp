#pragma once

/**
 * @file rigid_body.hpp
 * @brief Простое твёрдое тело для игровой физики.
 *
 * Модель:
 * - pose: позиция центра масс + ориентация (SE(3))
 * - velocity: линейная + угловая скорости в мировой СК
 * - mass, inertia: масса и главные моменты инерции
 *
 * Угловая динамика учитывает гироскопический момент: τ_gyro = ω × (I·ω)
 */

#include "../geom/vec3.hpp"
#include "../geom/quat.hpp"
#include "../geom/pose3.hpp"
#include <cmath>

namespace termin {
namespace physics {


class RigidBody {
public:
    // --- Состояние ---
    Pose3 pose;
    Vec3 linear_velocity;
    Vec3 angular_velocity;

    // --- Масса и инерция ---
    double mass = 1.0;
    Vec3 inertia{1.0, 1.0, 1.0};  // I_xx, I_yy, I_zz в СК тела

    // --- Аккумуляторы сил ---
    Vec3 force;
    Vec3 torque;

    // --- Флаги ---
    bool is_static = false;
    bool is_kinematic = false;

    // --- Демпфирование ---
    double linear_damping = 0.01;
    double angular_damping = 0.01;

    RigidBody() = default;

    // ==================== Фабрики ====================

    /**
     * Создать тело с инерцией параллелепипеда.
     * @param sx, sy, sz — полные размеры (не half)
     */
    static RigidBody create_box(double sx, double sy, double sz, double m,
                                 const Pose3& p = Pose3(), bool stat = false) {
        RigidBody body;
        body.pose = p;
        body.mass = m;
        body.is_static = stat;

        // I = m/12 · (b² + c²)
        body.inertia.x = (m / 12.0) * (sy * sy + sz * sz);
        body.inertia.y = (m / 12.0) * (sx * sx + sz * sz);
        body.inertia.z = (m / 12.0) * (sx * sx + sy * sy);

        return body;
    }

    /**
     * Создать тело с инерцией сферы.
     */
    static RigidBody create_sphere(double radius, double m,
                                    const Pose3& p = Pose3(), bool stat = false) {
        RigidBody body;
        body.pose = p;
        body.mass = m;
        body.is_static = stat;

        // I = 2/5 · m · r²
        double I = 0.4 * m * radius * radius;
        body.inertia = Vec3(I, I, I);

        return body;
    }

    // ==================== Свойства ====================

    double inv_mass() const {
        return (is_static || is_kinematic || mass < 1e-10) ? 0.0 : 1.0 / mass;
    }

    Vec3 inv_inertia() const {
        if (is_static || is_kinematic) return Vec3(0, 0, 0);
        return Vec3(
            inertia.x > 1e-10 ? 1.0 / inertia.x : 0.0,
            inertia.y > 1e-10 ? 1.0 / inertia.y : 0.0,
            inertia.z > 1e-10 ? 1.0 / inertia.z : 0.0
        );
    }

    Vec3 position() const { return pose.lin; }

    // ==================== Мировой тензор инерции ====================

    /**
     * I_world⁻¹ = R · diag(I⁻¹_body) · R^T
     */
    void world_inertia_inv(double* Iinv) const {
        if (is_static || is_kinematic) {
            for (int i = 0; i < 9; ++i) Iinv[i] = 0.0;
            return;
        }

        double R[9];
        pose.rotation_matrix(R);

        Vec3 d = inv_inertia();

        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                Iinv[i * 3 + j] =
                    R[i * 3 + 0] * d.x * R[j * 3 + 0] +
                    R[i * 3 + 1] * d.y * R[j * 3 + 1] +
                    R[i * 3 + 2] * d.z * R[j * 3 + 2];
            }
        }
    }

    Vec3 apply_inv_inertia_world(const Vec3& v) const {
        double Iinv[9];
        world_inertia_inv(Iinv);
        return Vec3(
            Iinv[0] * v.x + Iinv[1] * v.y + Iinv[2] * v.z,
            Iinv[3] * v.x + Iinv[4] * v.y + Iinv[5] * v.z,
            Iinv[6] * v.x + Iinv[7] * v.y + Iinv[8] * v.z
        );
    }

    // ==================== Скорость точки ====================

    Vec3 point_velocity(const Vec3& world_point) const {
        Vec3 r = world_point - pose.lin;
        return linear_velocity + angular_velocity.cross(r);
    }

    // ==================== Силы ====================

    void add_force(const Vec3& f) {
        if (!is_static && !is_kinematic) force += f;
    }

    void add_torque(const Vec3& t) {
        if (!is_static && !is_kinematic) torque += t;
    }

    void add_force_at_point(const Vec3& f, const Vec3& world_point) {
        if (is_static || is_kinematic) return;
        force += f;
        torque += (world_point - pose.lin).cross(f);
    }

    // ==================== Импульсы ====================

    void apply_impulse(const Vec3& impulse) {
        if (!is_static && !is_kinematic) {
            linear_velocity += impulse * inv_mass();
        }
    }

    void apply_angular_impulse(const Vec3& ang_impulse) {
        if (!is_static && !is_kinematic) {
            angular_velocity += apply_inv_inertia_world(ang_impulse);
        }
    }

    void apply_impulse_at_point(const Vec3& impulse, const Vec3& world_point) {
        if (is_static || is_kinematic) return;
        linear_velocity += impulse * inv_mass();
        angular_velocity += apply_inv_inertia_world((world_point - pose.lin).cross(impulse));
    }

    // ==================== Интеграция ====================

    /**
     * Интеграция сил → скорости.
     *
     * Линейная: v += (g + F/m) · dt
     * Угловая:  ω += I_world⁻¹ · (τ - ω × L) · dt
     */
    void integrate_forces(double dt, const Vec3& gravity) {
        if (is_static || is_kinematic) {
            force = Vec3();
            torque = Vec3();
            return;
        }

        // Линейная часть
        linear_velocity += (gravity + force * inv_mass()) * dt;

        // Угловая часть с гироскопическим эффектом
        double R[9];
        pose.rotation_matrix(R);

        // ω_body = R^T · ω_world
        Vec3 omega_body(
            R[0] * angular_velocity.x + R[3] * angular_velocity.y + R[6] * angular_velocity.z,
            R[1] * angular_velocity.x + R[4] * angular_velocity.y + R[7] * angular_velocity.z,
            R[2] * angular_velocity.x + R[5] * angular_velocity.y + R[8] * angular_velocity.z
        );

        // L_body = I · ω_body
        Vec3 L_body(inertia.x * omega_body.x, inertia.y * omega_body.y, inertia.z * omega_body.z);

        // L_world = R · L_body
        Vec3 L_world(
            R[0] * L_body.x + R[1] * L_body.y + R[2] * L_body.z,
            R[3] * L_body.x + R[4] * L_body.y + R[5] * L_body.z,
            R[6] * L_body.x + R[7] * L_body.y + R[8] * L_body.z
        );

        // τ_eff = τ - ω × L (вычитаем гироскопический момент)
        Vec3 tau_eff = torque - angular_velocity.cross(L_world);
        angular_velocity += apply_inv_inertia_world(tau_eff) * dt;

        // Демпфирование
        linear_velocity *= (1.0 - linear_damping * dt);
        angular_velocity *= (1.0 - angular_damping * dt);

        force = Vec3();
        torque = Vec3();
    }

    /**
     * Интеграция скоростей → позиции.
     */
    void integrate_positions(double dt) {
        if (is_static) return;

        pose.lin += linear_velocity * dt;

        double theta = angular_velocity.norm() * dt;
        if (theta > 1e-10) {
            Vec3 axis = angular_velocity / angular_velocity.norm();
            double half = theta * 0.5;
            Quat dq(
                axis.x * std::sin(half),
                axis.y * std::sin(half),
                axis.z * std::sin(half),
                std::cos(half)
            );
            pose.ang = (dq * pose.ang).normalized();
        }
    }

};

} // namespace physics
} // namespace termin
