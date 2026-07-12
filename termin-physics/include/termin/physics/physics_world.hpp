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
#include <termin/physics/termin_physics_api.hpp>
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

class TERMIN_PHYSICS_API PhysicsWorld {
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
    void set_collision_world(CollisionWorld* cw);

    CollisionWorld* collision_world() const;

    CollisionWorld* ensure_collision_world();

    size_t add_body(const RigidBody& body);

    void register_collider(size_t body_idx, Collider* collider);

    RigidBody& get_body(size_t idx) { return bodies_[idx]; }
    const RigidBody& get_body(size_t idx) const { return bodies_[idx]; }
    size_t body_count() const { return bodies_.size(); }

    void clear();

    size_t add_box(double sx, double sy, double sz, double mass,
                   const Pose3& pose, bool is_static = false);

    size_t add_sphere(double radius, double mass,
                      const Pose3& pose, bool is_static = false);

    void step(double dt);

    const std::vector<Contact>& contacts() const { return contacts_; }
    std::vector<RigidBody>& bodies() { return bodies_; }
    const std::vector<RigidBody>& bodies() const { return bodies_; }

private:
    void sync_collider_velocities();
    void sync_collider_poses();

    RigidBody* find_body(Collider* collider);

    void detect_collisions();
    void add_ground_contacts(RigidBody& body, Collider* collider);
};

} // namespace physics
} // namespace termin
