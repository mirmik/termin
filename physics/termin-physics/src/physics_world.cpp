#include <termin/physics/physics_world.hpp>

namespace termin::physics {
    void PhysicsWorld::set_collision_world(CollisionWorld* cw) {
        collision_world_ = cw;
    }
    CollisionWorld* PhysicsWorld::collision_world() const {
        return collision_world_;
    }
    CollisionWorld* PhysicsWorld::ensure_collision_world() {
        if (!collision_world_) {
            owned_collision_world_ = std::make_unique<CollisionWorld>();
            collision_world_ = owned_collision_world_.get();
        }
        return collision_world_;
    }
    size_t PhysicsWorld::add_body(const RigidBody& body) {
        bodies_.push_back(body);
        return bodies_.size() - 1;
    }
    void PhysicsWorld::register_collider(size_t i, Collider* c) {
        if (i >= bodies_.size() || !c)
            return;
        unregister_collider(i);
        collider_to_body_[c] = i;
        body_to_collider_[i] = c;
    }
    void PhysicsWorld::unregister_collider(size_t i) {
        auto it = body_to_collider_.find(i);
        if (it == body_to_collider_.end())
            return;
        collider_to_body_.erase(it->second);
        body_to_collider_.erase(it);
    }
    void PhysicsWorld::clear() {
        bodies_.clear();
        owned_colliders_.clear();
        collider_to_body_.clear();
        body_to_collider_.clear();
        contacts_.clear();
    }
    size_t PhysicsWorld::add_box(const Vec3& size, double mass, const Pose3& p, bool stat) {
        size_t i = add_body(RigidBody::create_box(size, mass, p, stat));
        auto c = std::make_shared<BoxCollider>(size * 0.5, GeneralPose3(p.ang, p.lin));
        owned_colliders_.push_back(c);
        Collider* raw = c.get();
        ensure_collision_world()->add(raw);
        register_collider(i, raw);
        return i;
    }
    size_t PhysicsWorld::add_sphere(double r, double mass, const Pose3& p, bool stat) {
        size_t i = add_body(RigidBody::create_sphere(r, mass, p, stat));
        auto c = std::make_shared<SphereCollider>(r, GeneralPose3(p.ang, p.lin));
        owned_colliders_.push_back(c);
        Collider* raw = c.get();
        ensure_collision_world()->add(raw);
        register_collider(i, raw);
        return i;
    }
    void PhysicsWorld::step(double dt) {
        for (auto& b : bodies_)
            b.integrate_forces(dt, gravity);
        sync_collider_poses();
        detect_collisions();
        solver_.restitution = restitution;
        solver_.friction = friction;
        solver_.iterations = solver_iterations;
        solver_.prepare(contacts_);
        solver_.solve(dt);
        for (auto& b : bodies_)
            b.integrate_positions(dt);
        solver_.solve_positions();
        sync_collider_velocities();
    }
    void PhysicsWorld::sync_collider_velocities() {
        for (auto& [i, c] : body_to_collider_)
            if (i < bodies_.size()) {
                c->linear_velocity = bodies_[i].linear_velocity;
                c->angular_velocity = bodies_[i].angular_velocity;
            }
    }
    void PhysicsWorld::sync_collider_poses() {
        for (auto& [i, c] : body_to_collider_)
            if (i < bodies_.size()) {
                if (auto* p = dynamic_cast<colliders::ColliderPrimitive*>(c);
                    p && dynamic_cast<colliders::AttachedCollider*>(c) == nullptr) {
                    const Pose3 pose = bodies_[i].shape_pose();
                    p->transform = GeneralPose3(pose.ang, pose.lin, p->transform.scale);
                }
                if (collision_world_)
                    collision_world_->update_pose(c);
            }
    }
    RigidBody* PhysicsWorld::find_body(Collider* c) {
        auto it = collider_to_body_.find(c);
        return it != collider_to_body_.end() && it->second < bodies_.size() ? &bodies_[it->second] : nullptr;
    }
    void PhysicsWorld::detect_collisions() {
        contacts_.clear();
        if (collision_world_)
            for (const auto& patch : collision_world_->detect_contacts()) {
                RigidBody* a = find_body(patch.collider_a);
                RigidBody* b = find_body(patch.collider_b);
                if (!a && !b)
                    continue;
                if ((!a || a->is_static) && (!b || b->is_static))
                    continue;
                for (const auto& point : patch.points) {
                    Contact c;
                    c.body_a = a;
                    c.body_b = b;
                    c.collider_a = patch.collider_a;
                    c.collider_b = patch.collider_b;
                    c.point = point.representative_point_world();
                    c.normal = patch.normal_world;
                    c.penetration = -point.signed_gap;
                    contacts_.push_back(c);
                }
            }
    }
} // namespace termin::physics
