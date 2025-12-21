#pragma once

/**
 * @file contact_solver.hpp
 * @brief Решатель контактных ограничений методом Sequential Impulses.
 *
 * Алгоритм:
 * 1. Для каждого контакта вычисляем эффективную массу
 * 2. Итеративно решаем: j = M_eff · (v_target - v_current)
 * 3. Накапливаем импульсы с ограничением (clamping)
 */

#include "../geom/vec3.hpp"
#include "rigid_body.hpp"
#include <algorithm>
#include <cmath>

namespace termin {
namespace physics {

using geom::Vec3;

struct Contact {
    RigidBody* body_a = nullptr;  // nullptr = статика (земля)
    RigidBody* body_b = nullptr;
    Vec3 point;
    Vec3 normal;
    double penetration = 0;

    // Кэш импульсов для warm-starting
    double accumulated_normal = 0;
    double accumulated_tangent1 = 0;
    double accumulated_tangent2 = 0;
};

class ContactSolver {
public:
    double restitution = 0.3;  // Коэффициент восстановления
    double friction = 0.5;     // Коэффициент трения
    double baumgarte = 0.2;    // Коэффициент позиционной коррекции
    double slop = 0.005;       // Допустимое проникновение
    int iterations = 10;

private:
    // Предвычисленные данные для контакта
    struct CachedContact {
        Contact* contact;
        double eff_mass_n;
        double eff_mass_t1;
        double eff_mass_t2;
        Vec3 tangent1;
        Vec3 tangent2;
        double initial_vn;
        bool initial_vn_set = false;
    };

    std::vector<CachedContact> cache_;

public:
    void prepare(std::vector<Contact>& contacts) {
        cache_.clear();
        cache_.reserve(contacts.size());

        for (auto& c : contacts) {
            CachedContact cc;
            cc.contact = &c;

            // Эффективная масса по нормали
            cc.eff_mass_n = compute_effective_mass(c, c.normal);

            // Касательные направления
            if (std::abs(c.normal.x) < 0.9) {
                cc.tangent1 = c.normal.cross(Vec3(1, 0, 0)).normalized();
            } else {
                cc.tangent1 = c.normal.cross(Vec3(0, 1, 0)).normalized();
            }
            cc.tangent2 = c.normal.cross(cc.tangent1);

            cc.eff_mass_t1 = compute_effective_mass(c, cc.tangent1);
            cc.eff_mass_t2 = compute_effective_mass(c, cc.tangent2);

            cache_.push_back(cc);
        }
    }

    void solve(double dt) {
        for (int iter = 0; iter < iterations; ++iter) {
            for (auto& cc : cache_) {
                solve_normal(cc, dt);
                solve_friction(cc);
            }
        }
    }

    void solve_positions() {
        // Baumgarte stabilization уже включён в solve_normal через bias
        // Дополнительная позиционная коррекция (если нужна):
        for (auto& cc : cache_) {
            Contact& c = *cc.contact;
            if (c.penetration < slop) continue;

            double correction = (c.penetration - slop) * baumgarte;
            Vec3 impulse = c.normal * correction;

            double total_inv = 0;
            if (c.body_a && !c.body_a->is_static) total_inv += c.body_a->inv_mass();
            if (c.body_b && !c.body_b->is_static) total_inv += c.body_b->inv_mass();

            if (total_inv < 1e-10) continue;

            if (c.body_a && !c.body_a->is_static) {
                c.body_a->pose.lin -= impulse * (c.body_a->inv_mass() / total_inv);
            }
            if (c.body_b && !c.body_b->is_static) {
                c.body_b->pose.lin += impulse * (c.body_b->inv_mass() / total_inv);
            }
        }
    }

private:
    double compute_effective_mass(const Contact& c, const Vec3& dir) const {
        double w = 0;

        if (c.body_a && !c.body_a->is_static) {
            Vec3 r = c.point - c.body_a->pose.lin;
            Vec3 rxd = r.cross(dir);
            Vec3 Iinv_rxd = c.body_a->apply_inv_inertia_world(rxd);
            w += c.body_a->inv_mass();
            w += dir.dot(Iinv_rxd.cross(r));
        }

        if (c.body_b && !c.body_b->is_static) {
            Vec3 r = c.point - c.body_b->pose.lin;
            Vec3 rxd = r.cross(dir);
            Vec3 Iinv_rxd = c.body_b->apply_inv_inertia_world(rxd);
            w += c.body_b->inv_mass();
            w += dir.dot(Iinv_rxd.cross(r));
        }

        return w > 1e-10 ? 1.0 / w : 0.0;
    }

    Vec3 relative_velocity(const Contact& c) const {
        Vec3 v_b = c.body_b ? c.body_b->point_velocity(c.point) : Vec3();
        Vec3 v_a = c.body_a ? c.body_a->point_velocity(c.point) : Vec3();
        return v_b - v_a;
    }

    /**
     * Относительная скорость центров масс (без учёта вращения).
     * Используется для трения, чтобы избежать артефактов при множественных контактах.
     */
    Vec3 relative_velocity_linear_only(const Contact& c) const {
        Vec3 v_b = c.body_b ? c.body_b->linear_velocity : Vec3();
        Vec3 v_a = c.body_a ? c.body_a->linear_velocity : Vec3();
        return v_b - v_a;
    }

    void solve_normal(CachedContact& cc, double dt) {
        Contact& c = *cc.contact;

        Vec3 v_rel = relative_velocity(c);
        double vn = v_rel.dot(c.normal);

        // Сохраняем начальную скорость для реституции
        if (!cc.initial_vn_set) {
            cc.initial_vn = vn;
            cc.initial_vn_set = true;
        }

        // Целевая скорость (реституция только при достаточной скорости удара)
        double target_vn = 0;
        if (cc.initial_vn < -1.0) {
            target_vn = -restitution * cc.initial_vn;
        }

        // Bias для Baumgarte stabilization
        double bias = 0;
        if (c.penetration > slop) {
            bias = baumgarte * (c.penetration - slop) / dt;
        }

        double impulse = cc.eff_mass_n * (target_vn - vn + bias);

        // Clamping: накопленный импульс >= 0
        double old = c.accumulated_normal;
        c.accumulated_normal = std::max(0.0, old + impulse);
        impulse = c.accumulated_normal - old;

        apply_impulse(c, c.normal * impulse);
    }

    void solve_friction(CachedContact& cc) {
        Contact& c = *cc.contact;
        double max_friction = friction * c.accumulated_normal;
        
        // Порог скорости для трения — избегаем численных артефактов
        const double friction_velocity_threshold = 0.01;

        // Используем линейную скорость (без учёта вращения) для более стабильного трения
        Vec3 v_rel = relative_velocity_linear_only(c);

        // Tangent 1
        {
            double vt = v_rel.dot(cc.tangent1);
            
            // Не применяем трение при очень малых скоростях
            if (std::abs(vt) < friction_velocity_threshold) {
                // Пропускаем
            } else {
                double impulse = cc.eff_mass_t1 * (-vt);

                double old = c.accumulated_tangent1;
                c.accumulated_tangent1 = std::clamp(old + impulse, -max_friction, max_friction);
                impulse = c.accumulated_tangent1 - old;

                apply_impulse(c, cc.tangent1 * impulse);
            }
        }

        // Tangent 2
        {
            double vt = v_rel.dot(cc.tangent2);
            
            if (std::abs(vt) < friction_velocity_threshold) {
                // Пропускаем
            } else {
                double impulse = cc.eff_mass_t2 * (-vt);

                double old = c.accumulated_tangent2;
                c.accumulated_tangent2 = std::clamp(old + impulse, -max_friction, max_friction);
                impulse = c.accumulated_tangent2 - old;

                apply_impulse(c, cc.tangent2 * impulse);
            }
        }
    }

    void apply_impulse(Contact& c, const Vec3& impulse) {
        if (c.body_a && !c.body_a->is_static) {
            c.body_a->apply_impulse_at_point(impulse * (-1.0), c.point);
        }
        if (c.body_b && !c.body_b->is_static) {
            c.body_b->apply_impulse_at_point(impulse, c.point);
        }
    }
};

} // namespace physics
} // namespace termin
