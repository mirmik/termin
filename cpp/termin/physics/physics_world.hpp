#pragma once

/**
 * @file physics_world.hpp
 * @brief Простой игровой физический мир.
 *
 * Цикл симуляции (Semi-Implicit Euler):
 * 1. integrate_forces — обновить скорости по силам
 * 2. detect_collisions — найти контакты через CollisionWorld
 * 3. solve_contacts — итеративно разрешить импульсами
 * 4. integrate_positions — обновить позиции по скоростям
 * 5. correct_positions — убрать остаточное проникновение
 *
 * Поддерживает fixed timestep с накоплением времени.
 */

#include "../geom/vec3.hpp"
#include "../geom/pose3.hpp"
#include "../collision/collision_world.hpp"
#include "rigid_body.hpp"
#include "contact_solver.hpp"
#include <vector>
#include <unordered_map>

namespace termin {
namespace physics {

using geom::Vec3;
using geom::Pose3;
using geom::GeneralPose3;
using collision::CollisionWorld;
using collision::ContactManifold;
using colliders::Collider;
using colliders::BoxCollider;
using colliders::SphereCollider;

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

    // --- Земля (временно, пока нет PlaneCollider) ---
    bool ground_enabled = false;
    double ground_height = 0.0;

private:
    // Тела хранятся по значению
    std::vector<RigidBody> bodies_;

    // Коллайдеры, созданные через add_box/add_sphere (владение)
    std::vector<colliders::ColliderPtr> owned_colliders_;

    // Маппинг: collider → индекс тела
    std::unordered_map<Collider*, size_t> collider_to_body_;

    // Маппинг: индекс тела → collider (для синхронизации позы)
    std::unordered_map<size_t, Collider*> body_to_collider_;

    // Внешний CollisionWorld (не владеем)
    CollisionWorld* collision_world_ = nullptr;

    double time_accumulator_ = 0.0;
    std::vector<Contact> contacts_;
    ContactSolver solver_;

public:
    // ==================== Collision World ====================

    /**
     * Установить внешний CollisionWorld.
     * PhysicsWorld не владеет им.
     */
    void set_collision_world(CollisionWorld* cw) {
        collision_world_ = cw;
    }

    CollisionWorld* collision_world() const { return collision_world_; }

    // ==================== Управление телами ====================

    /**
     * Добавить тело (без коллайдера).
     */
    size_t add_body(const RigidBody& body) {
        bodies_.push_back(body);
        return bodies_.size() - 1;
    }

    /**
     * Связать тело с коллайдером.
     * Коллайдер должен быть уже добавлен в CollisionWorld.
     */
    void register_collider(size_t body_idx, Collider* collider) {
        if (body_idx >= bodies_.size() || !collider) return;

        collider_to_body_[collider] = body_idx;
        body_to_collider_[body_idx] = collider;
    }

    RigidBody& get_body(size_t idx) { return bodies_[idx]; }
    const RigidBody& get_body(size_t idx) const { return bodies_[idx]; }
    size_t body_count() const { return bodies_.size(); }

    void clear() {
        bodies_.clear();
        owned_colliders_.clear();
        collider_to_body_.clear();
        body_to_collider_.clear();
        contacts_.clear();
    }

    // ==================== Удобные фабрики ====================

    /**
     * Добавить box: создаёт RigidBody + BoxCollider, регистрирует в CollisionWorld.
     */
    size_t add_box(double sx, double sy, double sz, double mass,
                   const Pose3& pose, bool is_static = false) {
        // Создаём тело
        size_t idx = add_body(RigidBody::create_box(sx, sy, sz, mass, pose, is_static));

        // Создаём коллайдер
        Vec3 half_size(sx / 2, sy / 2, sz / 2);
        auto collider = std::make_shared<BoxCollider>(half_size, GeneralPose3(pose.ang, pose.lin));
        owned_colliders_.push_back(collider);

        // Регистрируем
        Collider* raw = collider.get();
        if (collision_world_) {
            collision_world_->add(raw);
        }
        register_collider(idx, raw);

        return idx;
    }

    /**
     * Добавить sphere: создаёт RigidBody + SphereCollider, регистрирует в CollisionWorld.
     */
    size_t add_sphere(double radius, double mass,
                      const Pose3& pose, bool is_static = false) {
        size_t idx = add_body(RigidBody::create_sphere(radius, mass, pose, is_static));

        auto collider = std::make_shared<SphereCollider>(radius, GeneralPose3(pose.ang, pose.lin));
        owned_colliders_.push_back(collider);

        Collider* raw = collider.get();
        if (collision_world_) {
            collision_world_->add(raw);
        }
        register_collider(idx, raw);

        return idx;
    }

    // ==================== Симуляция ====================

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

    void step_fixed(double dt) {
        // 1. Интегрируем силы → скорости
        for (auto& body : bodies_) {
            body.integrate_forces(dt, gravity);
        }

        // 2. Синхронизируем позы коллайдеров
        sync_collider_poses();

        // 3. Детектируем коллизии
        detect_collisions();

        // 4. Решаем контактные ограничения
        solver_.restitution = restitution;
        solver_.friction = friction;
        solver_.iterations = solver_iterations;
        solver_.prepare(contacts_);
        solver_.solve(dt);

        // 5. Интегрируем скорости → позиции
        for (auto& body : bodies_) {
            body.integrate_positions(dt);
        }

        // 6. Позиционная коррекция
        solver_.solve_positions();
    }

    const std::vector<Contact>& contacts() const { return contacts_; }

    // Для совместимости со старым API
    std::vector<RigidBody>& bodies() { return bodies_; }
    const std::vector<RigidBody>& bodies() const { return bodies_; }

private:
    /**
     * Синхронизировать позы коллайдеров с позами тел.
     */
    void sync_collider_poses() {
        for (auto& [body_idx, collider] : body_to_collider_) {
            if (body_idx >= bodies_.size()) continue;

            const Pose3& pose = bodies_[body_idx].pose;

            // Обновляем позу коллайдера (ColliderPrimitive)
            if (auto* prim = dynamic_cast<colliders::ColliderPrimitive*>(collider)) {
                // Сохраняем scale, обновляем только позицию и ориентацию
                prim->transform = GeneralPose3(pose.ang, pose.lin, prim->transform.scale);
            }

            // Обновляем BVH
            if (collision_world_) {
                collision_world_->update_pose(collider);
            }
        }
    }

    /**
     * Найти RigidBody по коллайдеру.
     */
    RigidBody* find_body(Collider* collider) {
        auto it = collider_to_body_.find(collider);
        if (it != collider_to_body_.end() && it->second < bodies_.size()) {
            return &bodies_[it->second];
        }
        return nullptr;
    }

    void detect_collisions() {
        contacts_.clear();

        // Коллизии через CollisionWorld
        if (collision_world_) {
            auto manifolds = collision_world_->detect_contacts();

            for (const auto& m : manifolds) {
                RigidBody* body_a = find_body(m.collider_a);
                RigidBody* body_b = find_body(m.collider_b);

                // Обрабатываем только если хотя бы одно тело наше
                if (!body_a && !body_b) continue;

                // Пропускаем статика-статика
                bool a_static = !body_a || body_a->is_static;
                bool b_static = !body_b || body_b->is_static;
                if (a_static && b_static) continue;

                // Конвертируем ContactManifold → Contact
                for (int i = 0; i < m.point_count; ++i) {
                    const auto& cp = m.points[i];
                    Contact c;
                    c.body_a = body_a;
                    c.body_b = body_b;
                    c.point = cp.position;
                    c.normal = m.normal;
                    c.penetration = -cp.penetration;  // ContactManifold: negative = penetrating
                    contacts_.push_back(c);
                }
            }
        }

        // Коллизии с землёй (временно, пока нет PlaneCollider)
        if (ground_enabled) {
            for (size_t i = 0; i < bodies_.size(); ++i) {
                RigidBody& body = bodies_[i];
                if (body.is_static) continue;

                auto it = body_to_collider_.find(i);
                if (it == body_to_collider_.end()) continue;

                add_ground_contacts(body, it->second);
            }
        }
    }

    void add_ground_contacts(RigidBody& body, Collider* collider) {
        Vec3 ground_normal(0, 0, 1);

        if (auto* box = dynamic_cast<BoxCollider*>(collider)) {
            auto corners = box->get_corners_world();
            for (const auto& corner : corners) {
                if (corner.z < ground_height) {
                    Contact c;
                    c.body_a = nullptr;  // Земля
                    c.body_b = &body;
                    c.point = Vec3(corner.x, corner.y, ground_height);
                    c.normal = ground_normal;
                    c.penetration = ground_height - corner.z;
                    contacts_.push_back(c);
                }
            }
        } else if (auto* sphere = dynamic_cast<SphereCollider*>(collider)) {
            Vec3 center = sphere->center();
            double bottom = center.z - sphere->effective_radius();
            if (bottom < ground_height) {
                Contact c;
                c.body_a = nullptr;
                c.body_b = &body;
                c.point = Vec3(center.x, center.y, ground_height);
                c.normal = ground_normal;
                c.penetration = ground_height - bottom;
                contacts_.push_back(c);
            }
        }
    }
};

} // namespace physics
} // namespace termin
