#pragma once

// @file physics_world.hpp
// @brief Простой игровой физический мир.
//
// Цикл симуляции (Semi-Implicit Euler):
// 1. integrate_forces - обновить скорости по силам
// 2. detect_collisions - найти контакты через CollisionWorld
// 3. solve_contacts - итеративно разрешить импульсами
// 4. integrate_positions - обновить позиции по скоростям
// 5. correct_positions - убрать остаточное проникновение
//
// Поддерживает fixed timestep с накоплением времени.

#include <termin/geom/vec3.hpp>
#include <termin/geom/pose3.hpp>
#include <termin/geom/general_pose3.hpp>
#include <termin/collision/collision_world.hpp>
#include <termin/physics/rigid_body.hpp>
#include <termin/physics/contact_solver.hpp>
#include <memory>
#include <unordered_map>
#include <vector>

namespace termin {
namespace physics {

using collision::CollisionWorld;
using collision::ContactManifold;
using colliders::BoxCollider;
using colliders::Collider;
using colliders::SphereCollider;

class PhysicsWorld {
public:
    Vec3 gravity{0, 0, -9.81};
    int solver_iterations = 10;
    double restitution = 0.3;
    double friction = 0.5;
    bool ground_enabled = false;
    double ground_height = 0.0;

private:
    std::vector<RigidBody> bodies_;
    std::vector<colliders::ColliderPtr> owned_colliders_;
    std::unordered_map<Collider*, size_t> collider_to_body_;
    std::unordered_map<size_t, Collider*> body_to_collider_;
    std::unique_ptr<CollisionWorld> owned_collision_world_;
    CollisionWorld* collision_world_ = nullptr;
    std::vector<Contact> contacts_;
    ContactSolver solver_;

public:
    void set_collision_world(CollisionWorld* cw) {
        collision_world_ = cw;
    }

    CollisionWorld* collision_world() const { return collision_world_; }

    CollisionWorld* ensure_collision_world() {
        if (!collision_world_) {
            owned_collision_world_ = std::make_unique<CollisionWorld>();
            collision_world_ = owned_collision_world_.get();
        }
        return collision_world_;
    }

    size_t add_body(const RigidBody& body) {
        bodies_.push_back(body);
        return bodies_.size() - 1;
    }

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

    size_t add_box(double sx, double sy, double sz, double mass,
                   const Pose3& pose, bool is_static = false) {
        size_t idx = add_body(RigidBody::create_box(sx, sy, sz, mass, pose, is_static));

        Vec3 half_size(sx / 2, sy / 2, sz / 2);
        auto collider = std::make_shared<BoxCollider>(half_size, GeneralPose3(pose.ang, pose.lin));
        owned_colliders_.push_back(collider);

        Collider* raw = collider.get();
        ensure_collision_world()->add(raw);
        register_collider(idx, raw);

        return idx;
    }

    size_t add_sphere(double radius, double mass,
                      const Pose3& pose, bool is_static = false) {
        size_t idx = add_body(RigidBody::create_sphere(radius, mass, pose, is_static));

        auto collider = std::make_shared<SphereCollider>(radius, GeneralPose3(pose.ang, pose.lin));
        owned_colliders_.push_back(collider);

        Collider* raw = collider.get();
        ensure_collision_world()->add(raw);
        register_collider(idx, raw);

        return idx;
    }

    void step(double dt) {
        for (auto& body : bodies_) {
            body.integrate_forces(dt, gravity);
        }

        sync_collider_poses();
        detect_collisions();

        solver_.restitution = restitution;
        solver_.friction = friction;
        solver_.iterations = solver_iterations;
        solver_.prepare(contacts_);
        solver_.solve(dt);

        for (auto& body : bodies_) {
            body.integrate_positions(dt);
        }

        solver_.solve_positions();
        sync_collider_velocities();
    }

    const std::vector<Contact>& contacts() const { return contacts_; }
    std::vector<RigidBody>& bodies() { return bodies_; }
    const std::vector<RigidBody>& bodies() const { return bodies_; }

private:
    void sync_collider_velocities() {
        for (auto& [body_idx, collider] : body_to_collider_) {
            if (body_idx >= bodies_.size()) continue;
            const RigidBody& body = bodies_[body_idx];
            collider->linear_velocity = body.linear_velocity;
            collider->angular_velocity = body.angular_velocity;
        }
    }

    void sync_collider_poses() {
        for (auto& [body_idx, collider] : body_to_collider_) {
            if (body_idx >= bodies_.size()) continue;

            if (auto* prim = dynamic_cast<colliders::ColliderPrimitive*>(collider)) {
                if (dynamic_cast<colliders::AttachedCollider*>(collider) == nullptr) {
                    const Pose3& pose = bodies_[body_idx].pose;
                    prim->transform = GeneralPose3(pose.ang, pose.lin, prim->transform.scale);
                }
            }

            if (collision_world_) {
                collision_world_->update_pose(collider);
            }
        }
    }

    RigidBody* find_body(Collider* collider) {
        auto it = collider_to_body_.find(collider);
        if (it != collider_to_body_.end() && it->second < bodies_.size()) {
            return &bodies_[it->second];
        }
        return nullptr;
    }

    void detect_collisions() {
        contacts_.clear();

        if (collision_world_) {
            auto manifolds = collision_world_->detect_contacts();

            for (const auto& m : manifolds) {
                RigidBody* body_a = find_body(m.collider_a);
                RigidBody* body_b = find_body(m.collider_b);

                if (!body_a && !body_b) continue;

                bool a_static = !body_a || body_a->is_static;
                bool b_static = !body_b || body_b->is_static;
                if (a_static && b_static) continue;

                for (int i = 0; i < m.point_count; ++i) {
                    const auto& cp = m.points[i];
                    Contact c;
                    c.body_a = body_a;
                    c.body_b = body_b;
                    c.collider_a = m.collider_a;
                    c.collider_b = m.collider_b;
                    c.point = cp.position;
                    c.normal = m.normal;
                    c.penetration = -cp.penetration;
                    contacts_.push_back(c);
                }
            }
        }

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
                    c.body_a = nullptr;
                    c.body_b = &body;
                    c.collider_a = nullptr;
                    c.collider_b = collider;
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
                c.collider_a = nullptr;
                c.collider_b = collider;
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
