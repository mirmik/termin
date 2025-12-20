#pragma once

/**
 * @file physics_world.hpp
 * @brief Простой игровой физический мир.
 *
 * Цикл симуляции (Semi-Implicit Euler):
 * 1. integrate_forces — обновить скорости по силам
 * 2. detect_collisions — найти контакты
 * 3. solve_contacts — итеративно разрешить импульсами
 * 4. integrate_positions — обновить позиции по скоростям
 * 5. correct_positions — убрать остаточное проникновение
 *
 * Поддерживает fixed timestep с накоплением времени.
 */

#include "../geom/vec3.hpp"
#include "../geom/pose3.hpp"
#include "rigid_body.hpp"
#include "collider.hpp"
#include "contact_solver.hpp"
#include <vector>

namespace termin {
namespace physics {

using geom::Vec3;
using geom::Pose3;

class PhysicsWorld {
public:
    // --- Параметры симуляции ---
    Vec3 gravity{0, 0, -9.81};
    double fixed_dt = 1.0 / 60.0;
    int max_substeps = 8;

    // --- Параметры контактов ---
    double restitution = 0.3;
    double friction = 0.5;
    int solver_iterations = 10;

    // --- Земля ---
    bool ground_enabled = false;
    double ground_height = 0.0;

    // --- Тела ---
    std::vector<RigidBody> bodies;

private:
    double time_accumulator_ = 0.0;
    std::vector<Contact> contacts_;
    ContactSolver solver_;

public:
    // ==================== Управление телами ====================

    size_t add_body(const RigidBody& body) {
        bodies.push_back(body);
        return bodies.size() - 1;
    }

    RigidBody& get_body(size_t idx) { return bodies[idx]; }
    const RigidBody& get_body(size_t idx) const { return bodies[idx]; }
    size_t body_count() const { return bodies.size(); }

    void remove_body(size_t idx) {
        if (idx < bodies.size()) {
            bodies.erase(bodies.begin() + idx);
        }
    }

    void clear() {
        bodies.clear();
        contacts_.clear();
    }

    // ==================== Удобные фабрики ====================

    size_t add_box(double sx, double sy, double sz, double mass,
                   const Pose3& pose, bool is_static = false) {
        return add_body(RigidBody::create_box(sx, sy, sz, mass, pose, is_static));
    }

    size_t add_sphere(double radius, double mass,
                      const Pose3& pose, bool is_static = false) {
        return add_body(RigidBody::create_sphere(radius, mass, pose, is_static));
    }

    // ==================== Симуляция ====================

    /**
     * Главный шаг симуляции.
     * Использует fixed timestep для стабильности.
     */
    void step(double dt) {
        time_accumulator_ += dt;

        int substeps = 0;
        while (time_accumulator_ >= fixed_dt && substeps < max_substeps) {
            step_fixed(fixed_dt);
            time_accumulator_ -= fixed_dt;
            ++substeps;
        }

        // Защита от спирали смерти
        if (time_accumulator_ > fixed_dt * max_substeps) {
            time_accumulator_ = 0.0;
        }
    }

    /**
     * Один фиксированный шаг симуляции.
     */
    void step_fixed(double dt) {
        // 1. Интегрируем силы → скорости
        for (auto& body : bodies) {
            body.integrate_forces(dt, gravity);
        }

        // 2. Детектируем коллизии
        detect_collisions();

        // 3. Решаем контактные ограничения
        solver_.restitution = restitution;
        solver_.friction = friction;
        solver_.iterations = solver_iterations;
        solver_.prepare(contacts_);
        solver_.solve(dt);

        // 4. Интегрируем скорости → позиции
        for (auto& body : bodies) {
            body.integrate_positions(dt);
        }

        // 5. Позиционная коррекция
        solver_.solve_positions();
    }

    // ==================== Доступ к контактам ====================

    const std::vector<Contact>& contacts() const { return contacts_; }

private:
    void detect_collisions() {
        contacts_.clear();

        size_t n = bodies.size();

        for (size_t i = 0; i < n; ++i) {
            RigidBody& body = bodies[i];
            if (body.collider_type == 0) continue;

            // Коллизия с землёй
            if (ground_enabled) {
                add_ground_contacts(body);
            }

            // Коллизии с другими телами
            for (size_t j = i + 1; j < n; ++j) {
                RigidBody& other = bodies[j];
                if (body.is_static && other.is_static) continue;
                if (other.collider_type == 0) continue;

                add_body_contacts(body, other);
            }
        }
    }

    void add_ground_contacts(RigidBody& body) {
        CollisionResult result;

        if (body.collider_type == 1) {  // Box
            result = collide_box_ground(body.collider_half_size, body.pose, ground_height);
        } else if (body.collider_type == 2) {  // Sphere
            result = collide_sphere_ground(body.pose.lin, body.collider_radius, ground_height);
        }

        for (const auto& cp : result.contacts) {
            Contact c;
            c.body_a = nullptr;  // Земля
            c.body_b = &body;
            c.point = cp.point;
            c.normal = cp.normal;
            c.penetration = cp.penetration;
            contacts_.push_back(c);
        }
    }

    void add_body_contacts(RigidBody& a, RigidBody& b) {
        CollisionResult result;
        RigidBody* body_a_ptr = &a;
        RigidBody* body_b_ptr = &b;

        int type_a = a.collider_type;
        int type_b = b.collider_type;

        if (type_a == 1 && type_b == 1) {  // Box vs Box
            result = collide_box_box(
                a.collider_half_size, a.pose,
                b.collider_half_size, b.pose
            );
        } else if (type_a == 2 && type_b == 2) {  // Sphere vs Sphere
            result = collide_sphere_sphere(
                a.pose.lin, a.collider_radius,
                b.pose.lin, b.collider_radius
            );
        } else if (type_a == 2 && type_b == 1) {  // Sphere vs Box
            result = collide_sphere_box(
                a.pose.lin, a.collider_radius,
                b.collider_half_size, b.pose
            );
        } else if (type_a == 1 && type_b == 2) {  // Box vs Sphere
            result = collide_sphere_box(
                b.pose.lin, b.collider_radius,
                a.collider_half_size, a.pose
            );
            // Инвертируем нормаль и меняем порядок тел
            for (auto& cp : result.contacts) {
                cp.normal = cp.normal * (-1.0);
            }
            body_a_ptr = &b;
            body_b_ptr = &a;
        }

        for (const auto& cp : result.contacts) {
            Contact c;
            c.body_a = body_a_ptr;
            c.body_b = body_b_ptr;
            c.point = cp.point;
            c.normal = cp.normal;
            c.penetration = cp.penetration;
            contacts_.push_back(c);
        }
    }
};

} // namespace physics
} // namespace termin
