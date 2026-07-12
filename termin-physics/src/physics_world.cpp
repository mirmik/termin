#include <termin/physics/physics_world.hpp>

namespace termin::physics {
void PhysicsWorld::set_collision_world(CollisionWorld *cw) {
  collision_world_ = cw;
}
CollisionWorld *PhysicsWorld::collision_world() const {
  return collision_world_;
}
CollisionWorld *PhysicsWorld::ensure_collision_world() {
  if (!collision_world_) {
    owned_collision_world_ = std::make_unique<CollisionWorld>();
    collision_world_ = owned_collision_world_.get();
  }
  return collision_world_;
}
size_t PhysicsWorld::add_body(const RigidBody &body) {
  bodies_.push_back(body);
  return bodies_.size() - 1;
}
void PhysicsWorld::register_collider(size_t i, Collider *c) {
  if (i >= bodies_.size() || !c)
    return;
  collider_to_body_[c] = i;
  body_to_collider_[i] = c;
}
void PhysicsWorld::clear() {
  bodies_.clear();
  owned_colliders_.clear();
  collider_to_body_.clear();
  body_to_collider_.clear();
  contacts_.clear();
}
size_t PhysicsWorld::add_box(double sx, double sy, double sz, double mass,
                             const Pose3 &p, bool stat) {
  size_t i = add_body(RigidBody::create_box(sx, sy, sz, mass, p, stat));
  auto c = std::make_shared<BoxCollider>(Vec3(sx / 2, sy / 2, sz / 2),
                                         GeneralPose3(p.ang, p.lin));
  owned_colliders_.push_back(c);
  Collider *raw = c.get();
  ensure_collision_world()->add(raw);
  register_collider(i, raw);
  return i;
}
size_t PhysicsWorld::add_sphere(double r, double mass, const Pose3 &p,
                                bool stat) {
  size_t i = add_body(RigidBody::create_sphere(r, mass, p, stat));
  auto c = std::make_shared<SphereCollider>(r, GeneralPose3(p.ang, p.lin));
  owned_colliders_.push_back(c);
  Collider *raw = c.get();
  ensure_collision_world()->add(raw);
  register_collider(i, raw);
  return i;
}
void PhysicsWorld::step(double dt) {
  for (auto &b : bodies_)
    b.integrate_forces(dt, gravity);
  sync_collider_poses();
  detect_collisions();
  solver_.restitution = restitution;
  solver_.friction = friction;
  solver_.iterations = solver_iterations;
  solver_.prepare(contacts_);
  solver_.solve(dt);
  for (auto &b : bodies_)
    b.integrate_positions(dt);
  solver_.solve_positions();
  sync_collider_velocities();
}
void PhysicsWorld::sync_collider_velocities() {
  for (auto &[i, c] : body_to_collider_)
    if (i < bodies_.size()) {
      c->linear_velocity = bodies_[i].linear_velocity;
      c->angular_velocity = bodies_[i].angular_velocity;
    }
}
void PhysicsWorld::sync_collider_poses() {
  for (auto &[i, c] : body_to_collider_)
    if (i < bodies_.size()) {
      if (auto *p = dynamic_cast<colliders::ColliderPrimitive *>(c);
          p && dynamic_cast<colliders::AttachedCollider *>(c) == nullptr) {
        const Pose3 &pose = bodies_[i].pose;
        p->transform = GeneralPose3(pose.ang, pose.lin, p->transform.scale);
      }
      if (collision_world_)
        collision_world_->update_pose(c);
    }
}
RigidBody *PhysicsWorld::find_body(Collider *c) {
  auto it = collider_to_body_.find(c);
  return it != collider_to_body_.end() && it->second < bodies_.size()
             ? &bodies_[it->second]
             : nullptr;
}
void PhysicsWorld::detect_collisions() {
  contacts_.clear();
  if (collision_world_)
    for (const auto &m : collision_world_->detect_contacts()) {
      RigidBody *a = find_body(m.collider_a);
      RigidBody *b = find_body(m.collider_b);
      if (!a && !b)
        continue;
      if ((!a || a->is_static) && (!b || b->is_static))
        continue;
      for (int i = 0; i < m.point_count; ++i) {
        Contact c;
        c.body_a = a;
        c.body_b = b;
        c.collider_a = m.collider_a;
        c.collider_b = m.collider_b;
        c.point = m.points[i].position;
        c.normal = m.normal;
        c.penetration = -m.points[i].penetration;
        contacts_.push_back(c);
      }
    }
  if (ground_enabled)
    for (size_t i = 0; i < bodies_.size(); ++i)
      if (!bodies_[i].is_static) {
        auto it = body_to_collider_.find(i);
        if (it != body_to_collider_.end())
          add_ground_contacts(bodies_[i], it->second);
      }
}
void PhysicsWorld::add_ground_contacts(RigidBody &b, Collider *c) {
  Vec3 n(0, 0, 1);
  if (auto *box = dynamic_cast<BoxCollider *>(c)) {
    for (const auto &p : box->get_corners_world())
      if (p.z < ground_height) {
        Contact x;
        x.body_b = &b;
        x.collider_b = c;
        x.point = Vec3(p.x, p.y, ground_height);
        x.normal = n;
        x.penetration = ground_height - p.z;
        contacts_.push_back(x);
      }
  } else if (auto *s = dynamic_cast<SphereCollider *>(c)) {
    Vec3 p = s->center();
    double d = p.z - s->effective_radius();
    if (d < ground_height) {
      Contact x;
      x.body_b = &b;
      x.collider_b = c;
      x.point = Vec3(p.x, p.y, ground_height);
      x.normal = n;
      x.penetration = ground_height - d;
      contacts_.push_back(x);
    }
  }
}
} // namespace termin::physics
