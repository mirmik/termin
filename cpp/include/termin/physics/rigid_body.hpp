#pragma once

#include "../geom/vec3.hpp"
#include "../geom/quat.hpp"
#include "../geom/pose3.hpp"
#include "../geom/screw3.hpp"
#include "spatial_inertia.hpp"
#include <cmath>

namespace termin {
namespace physics {

/**
 * Твёрдое тело в формализме spatial algebra (нотация Фезерстоуна).
 *
 * Состояние:
 * - pose: Pose3 — система координат тела относительно мира (X_WB)
 * - velocity: Screw3 — пространственная скорость в МИРОВОЙ СК (ang=ω, lin=v)
 *
 * Динамика:
 * - inertia: SpatialInertia3D — в системе координат тела
 * - wrench: Screw3 — накопленный внешний винт сил в мировой СК
 */
class RigidBody {
public:
    SpatialInertia3D inertia;
    geom::Pose3 pose;
    geom::Screw3 velocity;
    geom::Screw3 wrench;
    bool is_static;

    // Для коллайдера храним half-extents (для box) или radius (для sphere)
    // Упрощённая версия: только box collider
    geom::Vec3 half_extents;  // Половинные размеры box collider'а
    bool has_collider;

    RigidBody()
        : inertia(), pose(), velocity(), wrench(), is_static(false),
          half_extents(0.5, 0.5, 0.5), has_collider(false) {}

    RigidBody(const SpatialInertia3D& i, const geom::Pose3& p, bool stat = false)
        : inertia(i), pose(p), velocity(), wrench(), is_static(stat),
          half_extents(0.5, 0.5, 0.5), has_collider(false) {}

    // Вспомогательные свойства
    double mass() const { return inertia.mass; }
    double inv_mass() const { return is_static ? 0.0 : inertia.inv_mass(); }
    geom::Vec3 position() const { return pose.lin; }

    // Матрица поворота (3x3) как 9 элементов
    void rotation_matrix(double* R) const {
        // R = quat_to_matrix
        const auto& q = pose.ang;
        double xx = q.x * q.x, yy = q.y * q.y, zz = q.z * q.z;
        double xy = q.x * q.y, xz = q.x * q.z, yz = q.y * q.z;
        double wx = q.w * q.x, wy = q.w * q.y, wz = q.w * q.z;

        R[0] = 1 - 2*(yy + zz);  R[1] = 2*(xy - wz);      R[2] = 2*(xz + wy);
        R[3] = 2*(xy + wz);      R[4] = 1 - 2*(xx + zz);  R[5] = 2*(yz - wx);
        R[6] = 2*(xz - wy);      R[7] = 2*(yz + wx);      R[8] = 1 - 2*(xx + yy);
    }

    /**
     * Обратный тензор инерции 3x3 в мировой СК (для импульсов).
     * I_world_inv = R @ diag(1/I_diag) @ R.T
     */
    void world_inertia_inv(double* Iinv) const {
        if (is_static || mass() <= 0) {
            for (int i = 0; i < 9; ++i) Iinv[i] = 0.0;
            return;
        }

        double R[9];
        rotation_matrix(R);

        geom::Vec3 inv_I = inertia.inv_I_diag();

        // Iinv = R @ diag(inv_I) @ R.T
        // Iinv[i][j] = sum_k R[i][k] * inv_I[k] * R[j][k]
        double d[3] = {inv_I.x, inv_I.y, inv_I.z};

        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                double sum = 0;
                for (int k = 0; k < 3; ++k) {
                    sum += R[i*3+k] * d[k] * R[j*3+k];
                }
                Iinv[i*3+j] = sum;
            }
        }
    }

    /**
     * Скорость точки, закреплённой на теле (мировые координаты).
     * v_point = v + ω × r
     */
    geom::Vec3 point_velocity(const geom::Vec3& point) const {
        geom::Vec3 r = point - pose.lin;
        return velocity.lin + velocity.ang.cross(r);
    }

    /**
     * Приложить импульс в точке. Меняет скорость напрямую.
     */
    void apply_impulse(const geom::Vec3& impulse, const geom::Vec3& point) {
        if (is_static) return;

        geom::Vec3 r = point - pose.lin;
        geom::Vec3 tau = r.cross(impulse);

        // Δv_lin = impulse / m
        if (inertia.mass > 0) {
            velocity.lin = velocity.lin + impulse * (1.0 / inertia.mass);
        }

        // Δω = I⁻¹_world @ τ
        double Iinv[9];
        world_inertia_inv(Iinv);

        geom::Vec3 dw = {
            Iinv[0]*tau.x + Iinv[1]*tau.y + Iinv[2]*tau.z,
            Iinv[3]*tau.x + Iinv[4]*tau.y + Iinv[5]*tau.z,
            Iinv[6]*tau.x + Iinv[7]*tau.y + Iinv[8]*tau.z
        };

        velocity.ang = velocity.ang + dw;
    }

    /**
     * Интегрирование сил для обновления скорости.
     * Использует spatial algebra в СК тела (нотация Фезерстоуна).
     */
    void integrate_forces(double dt, const geom::Vec3& gravity) {
        if (is_static) {
            wrench = geom::Screw3();
            return;
        }

        // Всё в СК тела
        geom::Screw3 v_body = velocity.inverse_transform_by(pose);
        geom::Vec3 g_body = pose.inverse_transform_vector(gravity);
        geom::Screw3 f_ext_body = wrench.inverse_transform_by(pose);

        // Суммарный винт: внешний + гравитация - bias
        geom::Screw3 f_gravity = inertia.gravity_wrench(g_body);
        geom::Screw3 f_bias = inertia.bias_wrench(v_body);
        geom::Screw3 f_total(
            f_ext_body.ang + f_gravity.ang - f_bias.ang,
            f_ext_body.lin + f_gravity.lin - f_bias.lin
        );

        // Ускорение: a = I⁻¹ * f
        geom::Screw3 a_body = inertia.solve(f_total);

        // В мировую СК и обновляем скорость
        geom::Screw3 a_world = a_body.transform_by(pose);
        velocity.ang = velocity.ang + a_world.ang * dt;
        velocity.lin = velocity.lin + a_world.lin * dt;

        wrench = geom::Screw3();
    }

    /**
     * Интегрирование скорости для обновления позы.
     * Простой Эйлер: позиция и ориентация интегрируются отдельно в мировой СК.
     */
    void integrate_positions(double dt) {
        if (is_static) return;

        // Интегрируем позицию в мировой СК
        pose.lin = pose.lin + velocity.lin * dt;

        // Интегрируем ориентацию: q' = dq * q
        // где dq = exp(ω * dt / 2) как кватернион
        double theta = velocity.ang.norm() * dt;
        if (theta > 1e-10) {
            geom::Vec3 axis = velocity.ang * (1.0 / velocity.ang.norm());
            double half = theta * 0.5;
            geom::Quat dq = {
                axis.x * std::sin(half),
                axis.y * std::sin(half),
                axis.z * std::sin(half),
                std::cos(half)
            };
            // Композиция: новая ориентация = dq * текущая
            pose.ang = (dq * pose.ang).normalized();
        }
    }

    /**
     * Получить вершины box collider'а в мировых координатах.
     * Записывает 8 вершин (24 double) в corners.
     */
    void get_box_corners_world(double* corners) const {
        double hx = half_extents.x;
        double hy = half_extents.y;
        double hz = half_extents.z;

        // 8 вершин в локальных координатах
        geom::Vec3 local[8] = {
            {-hx, -hy, -hz}, {+hx, -hy, -hz}, {-hx, +hy, -hz}, {+hx, +hy, -hz},
            {-hx, -hy, +hz}, {+hx, -hy, +hz}, {-hx, +hy, +hz}, {+hx, +hy, +hz}
        };

        for (int i = 0; i < 8; ++i) {
            geom::Vec3 world = pose.transform_point(local[i]);
            corners[i*3 + 0] = world.x;
            corners[i*3 + 1] = world.y;
            corners[i*3 + 2] = world.z;
        }
    }

    // Фабричный метод для создания куба
    static RigidBody create_box(double sx, double sy, double sz, double m,
                                 const geom::Pose3& p, bool stat = false) {
        // Главные моменты инерции кубоида
        double Ixx = (m / 12.0) * (sy*sy + sz*sz);
        double Iyy = (m / 12.0) * (sx*sx + sz*sz);
        double Izz = (m / 12.0) * (sx*sx + sy*sy);

        SpatialInertia3D inertia(m, geom::Vec3(Ixx, Iyy, Izz));

        RigidBody body(inertia, p, stat);
        body.half_extents = geom::Vec3(sx/2, sy/2, sz/2);
        body.has_collider = true;

        return body;
    }
};

} // namespace physics
} // namespace termin
