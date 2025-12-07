#pragma once

#include "../geom/vec3.hpp"
#include "rigid_body.hpp"
#include <cmath>
#include <algorithm>

namespace termin {
namespace physics {

/**
 * Точка контакта между двумя твёрдыми телами.
 */
struct Contact {
    RigidBody* body_a;  // Первое тело (nullptr для контакта с землёй)
    RigidBody* body_b;  // Второе тело
    geom::Vec3 point;   // Точка контакта в мировых координатах
    geom::Vec3 normal;  // Нормаль контакта (от A к B, или вверх для земли)
    double penetration; // Глубина проникновения

    // Для warm starting
    double accumulated_normal_impulse = 0.0;
    double accumulated_tangent_impulse1 = 0.0;
    double accumulated_tangent_impulse2 = 0.0;

    Contact() : body_a(nullptr), body_b(nullptr), penetration(0) {}

    Contact(RigidBody* a, RigidBody* b, const geom::Vec3& p,
            const geom::Vec3& n, double pen)
        : body_a(a), body_b(b), point(p), normal(n), penetration(pen) {}
};

/**
 * Решатель контактных ограничений методом Sequential Impulses.
 */
class ContactConstraint {
public:
    Contact* contact;
    double restitution;
    double friction;
    double baumgarte;
    double slop;

    // Предвычисленные данные
    double effective_mass_normal;
    double effective_mass_tangent1;
    double effective_mass_tangent2;
    geom::Vec3 tangent1;
    geom::Vec3 tangent2;

    // Начальная скорость сближения (для реституции)
    double initial_v_n;
    bool initial_v_n_computed;

    ContactConstraint(Contact* c, double rest = 0.3, double fric = 0.5,
                      double baum = 0.2, double sl = 0.005)
        : contact(c), restitution(rest), friction(fric),
          baumgarte(baum), slop(sl), initial_v_n(0), initial_v_n_computed(false) {
        precompute();
    }

    void precompute() {
        const geom::Vec3& n = contact->normal;

        // Эффективная масса для нормального импульса
        double w = 0.0;

        if (contact->body_a != nullptr && !contact->body_a->is_static) {
            geom::Vec3 r_a = contact->point - contact->body_a->pose.lin;
            geom::Vec3 rxn_a = r_a.cross(n);

            double Iinv_a[9];
            contact->body_a->world_inertia_inv(Iinv_a);

            // I⁻¹ @ rxn
            geom::Vec3 Iinv_rxn_a = {
                Iinv_a[0]*rxn_a.x + Iinv_a[1]*rxn_a.y + Iinv_a[2]*rxn_a.z,
                Iinv_a[3]*rxn_a.x + Iinv_a[4]*rxn_a.y + Iinv_a[5]*rxn_a.z,
                Iinv_a[6]*rxn_a.x + Iinv_a[7]*rxn_a.y + Iinv_a[8]*rxn_a.z
            };

            w += contact->body_a->inv_mass();
            w += n.dot(Iinv_rxn_a.cross(r_a));
        }

        if (contact->body_b != nullptr && !contact->body_b->is_static) {
            geom::Vec3 r_b = contact->point - contact->body_b->pose.lin;
            geom::Vec3 rxn_b = r_b.cross(n);

            double Iinv_b[9];
            contact->body_b->world_inertia_inv(Iinv_b);

            geom::Vec3 Iinv_rxn_b = {
                Iinv_b[0]*rxn_b.x + Iinv_b[1]*rxn_b.y + Iinv_b[2]*rxn_b.z,
                Iinv_b[3]*rxn_b.x + Iinv_b[4]*rxn_b.y + Iinv_b[5]*rxn_b.z,
                Iinv_b[6]*rxn_b.x + Iinv_b[7]*rxn_b.y + Iinv_b[8]*rxn_b.z
            };

            w += contact->body_b->inv_mass();
            w += n.dot(Iinv_rxn_b.cross(r_b));
        }

        effective_mass_normal = (w > 1e-10) ? 1.0 / w : 0.0;

        // Касательные направления
        if (std::abs(n.x) < 0.9) {
            tangent1 = n.cross(geom::Vec3(1, 0, 0));
        } else {
            tangent1 = n.cross(geom::Vec3(0, 1, 0));
        }
        tangent1 = tangent1.normalized();
        tangent2 = n.cross(tangent1);

        effective_mass_tangent1 = compute_effective_mass(tangent1);
        effective_mass_tangent2 = compute_effective_mass(tangent2);
    }

    double compute_effective_mass(const geom::Vec3& direction) const {
        double w = 0.0;

        if (contact->body_a != nullptr && !contact->body_a->is_static) {
            geom::Vec3 r_a = contact->point - contact->body_a->pose.lin;
            geom::Vec3 rxd_a = r_a.cross(direction);

            double Iinv_a[9];
            contact->body_a->world_inertia_inv(Iinv_a);

            geom::Vec3 Iinv_rxd_a = {
                Iinv_a[0]*rxd_a.x + Iinv_a[1]*rxd_a.y + Iinv_a[2]*rxd_a.z,
                Iinv_a[3]*rxd_a.x + Iinv_a[4]*rxd_a.y + Iinv_a[5]*rxd_a.z,
                Iinv_a[6]*rxd_a.x + Iinv_a[7]*rxd_a.y + Iinv_a[8]*rxd_a.z
            };

            w += contact->body_a->inv_mass();
            w += direction.dot(Iinv_rxd_a.cross(r_a));
        }

        if (contact->body_b != nullptr && !contact->body_b->is_static) {
            geom::Vec3 r_b = contact->point - contact->body_b->pose.lin;
            geom::Vec3 rxd_b = r_b.cross(direction);

            double Iinv_b[9];
            contact->body_b->world_inertia_inv(Iinv_b);

            geom::Vec3 Iinv_rxd_b = {
                Iinv_b[0]*rxd_b.x + Iinv_b[1]*rxd_b.y + Iinv_b[2]*rxd_b.z,
                Iinv_b[3]*rxd_b.x + Iinv_b[4]*rxd_b.y + Iinv_b[5]*rxd_b.z,
                Iinv_b[6]*rxd_b.x + Iinv_b[7]*rxd_b.y + Iinv_b[8]*rxd_b.z
            };

            w += contact->body_b->inv_mass();
            w += direction.dot(Iinv_rxd_b.cross(r_b));
        }

        return (w > 1e-10) ? 1.0 / w : 0.0;
    }

    geom::Vec3 relative_velocity() const {
        geom::Vec3 v_b(0, 0, 0);
        if (contact->body_b != nullptr) {
            v_b = contact->body_b->point_velocity(contact->point);
        }

        geom::Vec3 v_a(0, 0, 0);
        if (contact->body_a != nullptr) {
            v_a = contact->body_a->point_velocity(contact->point);
        }

        return v_b - v_a;
    }

    void solve_normal(double dt) {
        const geom::Vec3& n = contact->normal;

        geom::Vec3 v_rel = relative_velocity();
        double v_n = v_rel.dot(n);

        // Сохраняем начальную скорость
        if (!initial_v_n_computed) {
            initial_v_n = v_n;
            initial_v_n_computed = true;
        }

        double target_v_n = 0.0;
        if (initial_v_n < -1.0) {
            target_v_n = -restitution * initial_v_n;
        }

        double impulse = effective_mass_normal * (target_v_n - v_n);

        // Ограничиваем накопленный импульс
        double old_accumulated = contact->accumulated_normal_impulse;
        contact->accumulated_normal_impulse = std::max(0.0, old_accumulated + impulse);
        impulse = contact->accumulated_normal_impulse - old_accumulated;

        // Применяем импульс
        geom::Vec3 impulse_vec = n * impulse;
        apply_impulse(impulse_vec);
    }

    void solve_friction() {
        double max_friction = friction * contact->accumulated_normal_impulse;

        // Tangent1
        geom::Vec3 v_rel = relative_velocity();
        double v_t1 = v_rel.dot(tangent1);
        double impulse_t1 = effective_mass_tangent1 * (-v_t1);

        double old_t1 = contact->accumulated_tangent_impulse1;
        contact->accumulated_tangent_impulse1 = std::clamp(
            old_t1 + impulse_t1, -max_friction, max_friction
        );
        impulse_t1 = contact->accumulated_tangent_impulse1 - old_t1;

        // Tangent2
        v_rel = relative_velocity();
        double v_t2 = v_rel.dot(tangent2);
        double impulse_t2 = effective_mass_tangent2 * (-v_t2);

        double old_t2 = contact->accumulated_tangent_impulse2;
        contact->accumulated_tangent_impulse2 = std::clamp(
            old_t2 + impulse_t2, -max_friction, max_friction
        );
        impulse_t2 = contact->accumulated_tangent_impulse2 - old_t2;

        // Применяем импульсы трения
        geom::Vec3 impulse_vec = tangent1 * impulse_t1 + tangent2 * impulse_t2;
        apply_impulse(impulse_vec);
    }

    void apply_impulse(const geom::Vec3& impulse) {
        if (contact->body_a != nullptr && !contact->body_a->is_static) {
            contact->body_a->apply_impulse(impulse * (-1.0), contact->point);
        }
        if (contact->body_b != nullptr && !contact->body_b->is_static) {
            contact->body_b->apply_impulse(impulse, contact->point);
        }
    }
};

} // namespace physics
} // namespace termin
