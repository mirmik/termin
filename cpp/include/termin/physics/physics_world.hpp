#pragma once

#include "../geom/vec3.hpp"
#include "../geom/pose3.hpp"
#include "../colliders/box_collider.hpp"
#include "rigid_body.hpp"
#include "contact.hpp"
#include <vector>
#include <memory>

namespace termin {
namespace physics {

using geom::Vec3;
using geom::Pose3;
using colliders::BoxCollider;
using colliders::CollisionResult;

/**
 * Физический мир — полная симуляция твёрдых тел на C++.
 */
class PhysicsWorld {
public:
    Vec3 gravity;
    int iterations;
    double restitution;
    double friction;
    double ground_height;
    bool ground_enabled;

    // Fixed timestep
    double fixed_dt;
    int max_substeps;
    double time_accumulator;

    // Тела (владеем ими)
    std::vector<RigidBody> bodies;

    // Контакты (пересоздаются каждый шаг)
    std::vector<Contact> contacts;
    std::vector<ContactConstraint> constraints;

    PhysicsWorld()
        : gravity(0, 0, -9.81)
        , iterations(10)
        , restitution(0.3)
        , friction(0.5)
        , ground_height(0.0)
        , ground_enabled(false)
        , fixed_dt(1.0 / 60.0)
        , max_substeps(8)
        , time_accumulator(0.0)
    {}

    // Добавить тело, возвращает индекс
    size_t add_body(const RigidBody& body) {
        bodies.push_back(body);
        return bodies.size() - 1;
    }

    // Получить тело по индексу
    RigidBody& get_body(size_t idx) {
        return bodies[idx];
    }

    const RigidBody& get_body(size_t idx) const {
        return bodies[idx];
    }

    size_t body_count() const {
        return bodies.size();
    }

    /**
     * Главный шаг симуляции.
     */
    void step(double dt) {
        time_accumulator += dt;

        int substeps = 0;
        while (time_accumulator >= fixed_dt && substeps < max_substeps) {
            step_fixed(fixed_dt);
            time_accumulator -= fixed_dt;
            substeps++;
        }

        // Spiral of death protection
        if (time_accumulator > fixed_dt * max_substeps) {
            time_accumulator = 0.0;
        }
    }

private:
    void step_fixed(double dt) {
        // 1. Интегрирование сил
        for (auto& body : bodies) {
            body.integrate_forces(dt, gravity);
        }

        // 2. Интегрирование позиций
        for (auto& body : bodies) {
            body.integrate_positions(dt);
        }

        // 3. Обнаружение коллизий
        detect_collisions();

        // 4. Создание constraint'ов
        constraints.clear();
        for (auto& contact : contacts) {
            constraints.emplace_back(&contact, restitution, friction);
        }

        // 5. Решение (Sequential Impulses)
        for (int iter = 0; iter < iterations; ++iter) {
            for (auto& constraint : constraints) {
                constraint.solve_normal(dt);
                constraint.solve_friction();
            }
        }

        // 6. Коррекция позиций
        solve_position_constraints();
    }

    void detect_collisions() {
        contacts.clear();

        // Коллизии с землёй
        if (ground_enabled) {
            for (size_t i = 0; i < bodies.size(); ++i) {
                auto& body = bodies[i];
                if (body.is_static || !body.has_collider) continue;

                detect_ground_collision(i);
            }
        }

        // Коллизии между телами
        for (size_t i = 0; i < bodies.size(); ++i) {
            for (size_t j = i + 1; j < bodies.size(); ++j) {
                auto& body_a = bodies[i];
                auto& body_b = bodies[j];

                if (body_a.is_static && body_b.is_static) continue;
                if (!body_a.has_collider || !body_b.has_collider) continue;

                detect_body_collision(i, j);
            }
        }
    }

    void detect_ground_collision(size_t body_idx) {
        auto& body = bodies[body_idx];

        // Получаем box collider из body
        BoxCollider collider(
            Vec3(0, 0, 0),
            body.half_extents,
            body.pose
        );

        auto ground_contacts = collider.collide_ground(ground_height);

        Vec3 ground_normal(0, 0, 1);

        for (const auto& gc : ground_contacts) {
            Contact contact;
            contact.body_a = nullptr;  // Земля
            contact.body_b = &body;
            contact.point = gc.point;
            contact.normal = ground_normal;
            contact.penetration = gc.penetration;
            contacts.push_back(contact);
        }
    }

    void detect_body_collision(size_t idx_a, size_t idx_b) {
        auto& body_a = bodies[idx_a];
        auto& body_b = bodies[idx_b];

        BoxCollider collider_a(Vec3(0, 0, 0), body_a.half_extents, body_a.pose);
        BoxCollider collider_b(Vec3(0, 0, 0), body_b.half_extents, body_b.pose);

        auto result = collider_a.collide_box(collider_b);

        if (result.colliding) {
            Contact contact;
            contact.body_a = &body_a;
            contact.body_b = &body_b;
            contact.point = result.point;
            contact.normal = result.normal;
            contact.penetration = -result.distance;  // distance отрицательный при пенетрации
            contacts.push_back(contact);
        }
    }

    void solve_position_constraints() {
        // Повторно обнаруживаем коллизии для position correction
        std::vector<Contact> pos_contacts;

        if (ground_enabled) {
            for (size_t i = 0; i < bodies.size(); ++i) {
                auto& body = bodies[i];
                if (body.is_static || !body.has_collider) continue;

                BoxCollider collider(Vec3(0, 0, 0), body.half_extents, body.pose);
                auto ground_contacts = collider.collide_ground(ground_height);

                for (const auto& gc : ground_contacts) {
                    if (gc.penetration > 0.001) {
                        Contact c;
                        c.body_a = nullptr;
                        c.body_b = &body;
                        c.point = gc.point;
                        c.normal = Vec3(0, 0, 1);
                        c.penetration = gc.penetration;
                        pos_contacts.push_back(c);
                    }
                }
            }
        }

        // Body-body
        for (size_t i = 0; i < bodies.size(); ++i) {
            for (size_t j = i + 1; j < bodies.size(); ++j) {
                auto& body_a = bodies[i];
                auto& body_b = bodies[j];

                if (body_a.is_static && body_b.is_static) continue;
                if (!body_a.has_collider || !body_b.has_collider) continue;

                BoxCollider collider_a(Vec3(0, 0, 0), body_a.half_extents, body_a.pose);
                BoxCollider collider_b(Vec3(0, 0, 0), body_b.half_extents, body_b.pose);

                auto result = collider_a.collide_box(collider_b);

                if (result.colliding && -result.distance > 0.001) {
                    Contact c;
                    c.body_a = &body_a;
                    c.body_b = &body_b;
                    c.point = result.point;
                    c.normal = result.normal;
                    c.penetration = -result.distance;
                    pos_contacts.push_back(c);
                }
            }
        }

        // Применяем коррекцию
        for (auto& contact : pos_contacts) {
            Vec3 n = contact.normal;
            double correction = contact.penetration * 0.8;

            if (contact.body_a == nullptr) {
                // Контакт с землёй
                if (!contact.body_b->is_static) {
                    contact.body_b->pose.lin = contact.body_b->pose.lin + n * correction;
                }
            } else {
                // Контакт между телами
                double total_inv_mass = 0.0;
                if (!contact.body_a->is_static) {
                    total_inv_mass += contact.body_a->inv_mass();
                }
                if (!contact.body_b->is_static) {
                    total_inv_mass += contact.body_b->inv_mass();
                }

                if (total_inv_mass > 1e-10) {
                    if (!contact.body_a->is_static) {
                        double ratio_a = contact.body_a->inv_mass() / total_inv_mass;
                        contact.body_a->pose.lin = contact.body_a->pose.lin - n * (correction * ratio_a);
                    }
                    if (!contact.body_b->is_static) {
                        double ratio_b = contact.body_b->inv_mass() / total_inv_mass;
                        contact.body_b->pose.lin = contact.body_b->pose.lin + n * (correction * ratio_b);
                    }
                }
            }
        }
    }
};

} // namespace physics
} // namespace termin
