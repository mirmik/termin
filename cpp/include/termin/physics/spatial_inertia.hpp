#pragma once

#include "../geom/vec3.hpp"
#include "../geom/quat.hpp"
#include "../geom/pose3.hpp"
#include "../geom/screw3.hpp"
#include <cmath>

namespace termin {
namespace physics {

/**
 * Пространственная инерция твёрдого тела (в стиле Фезерстоуна).
 *
 * Хранит:
 * - mass: масса
 * - I_diag: главные моменты инерции (диагональ)
 * - frame: Pose3 — СК эллипсоида инерции (lin = COM, ang = ориентация главных осей)
 */
class SpatialInertia3D {
public:
    double mass;
    geom::Vec3 I_diag;  // Главные моменты инерции
    geom::Pose3 frame;  // СК эллипсоида (COM + ориентация)

    SpatialInertia3D()
        : mass(0.0), I_diag(0, 0, 0), frame() {}

    SpatialInertia3D(double m, const geom::Vec3& i_diag, const geom::Pose3& f = geom::Pose3())
        : mass(m), I_diag(i_diag), frame(f) {}

    // Обратная масса (0 для статических)
    double inv_mass() const {
        return (mass > 1e-10) ? 1.0 / mass : 0.0;
    }

    // Обратные моменты инерции (диагональ)
    geom::Vec3 inv_I_diag() const {
        return {
            (I_diag.x > 1e-10) ? 1.0 / I_diag.x : 0.0,
            (I_diag.y > 1e-10) ? 1.0 / I_diag.y : 0.0,
            (I_diag.z > 1e-10) ? 1.0 / I_diag.z : 0.0
        };
    }

    // Центр масс (позиция frame)
    geom::Vec3 com() const { return frame.lin; }

    /**
     * I @ twist -> momentum (h = I * v)
     *
     * 1. Переводим twist в СК эллипсоида
     * 2. Умножаем на диагональную инерцию
     * 3. Переводим обратно
     */
    geom::Screw3 apply(const geom::Screw3& twist) const {
        // В СК эллипсоида
        geom::Screw3 t_local = twist.inverse_transform_by(frame);

        // h = I @ v (диагональное умножение)
        geom::Vec3 h_lin = t_local.lin * mass;
        geom::Vec3 h_ang = {
            I_diag.x * t_local.ang.x,
            I_diag.y * t_local.ang.y,
            I_diag.z * t_local.ang.z
        };

        geom::Screw3 h_local(h_ang, h_lin);

        // Обратно в исходную СК
        return h_local.transform_by(frame);
    }

    /**
     * I⁻¹ @ wrench -> twist (a = I⁻¹ * f)
     */
    geom::Screw3 solve(const geom::Screw3& wrench) const {
        // В СК эллипсоида
        geom::Screw3 w_local = wrench.inverse_transform_by(frame);

        // a = I⁻¹ @ f (диагональное деление)
        geom::Vec3 a_lin = (mass > 1e-10) ? w_local.lin * (1.0 / mass) : geom::Vec3(0, 0, 0);
        geom::Vec3 inv_I = inv_I_diag();
        geom::Vec3 a_ang = {
            inv_I.x * w_local.ang.x,
            inv_I.y * w_local.ang.y,
            inv_I.z * w_local.ang.z
        };

        geom::Screw3 a_local(a_ang, a_lin);

        // Обратно в исходную СК
        return a_local.transform_by(frame);
    }

    /**
     * Винт гравитации (F, τ) в локальной системе.
     * g_local — вектор гравитации в СК тела.
     */
    geom::Screw3 gravity_wrench(const geom::Vec3& g_local) const {
        geom::Vec3 c = frame.lin;  // COM
        geom::Vec3 F = g_local * mass;
        geom::Vec3 tau = c.cross(F);
        return geom::Screw3(tau, F);
    }

    /**
     * Bias wrench: v ×* (I @ v)
     */
    geom::Screw3 bias_wrench(const geom::Screw3& velocity) const {
        geom::Screw3 h = apply(velocity);
        return velocity.cross_force(h);
    }
};

} // namespace physics
} // namespace termin
