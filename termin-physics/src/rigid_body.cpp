#include <cmath>
#include <termin/physics/rigid_body.hpp>

namespace termin::physics {

RigidBody RigidBody::create_box(double sx, double sy, double sz, double m,
                                const Pose3 &p, bool stat) {
  RigidBody body;
  body.pose = p;
  body.mass = m;
  body.is_static = stat;
  body.inertia.x = (m / 12.0) * (sy * sy + sz * sz);
  body.inertia.y = (m / 12.0) * (sx * sx + sz * sz);
  body.inertia.z = (m / 12.0) * (sx * sx + sy * sy);
  return body;
}

RigidBody RigidBody::create_sphere(double radius, double m, const Pose3 &p,
                                   bool stat) {
  RigidBody body;
  body.pose = p;
  body.mass = m;
  body.is_static = stat;
  const double I = 0.4 * m * radius * radius;
  body.inertia = Vec3(I, I, I);
  return body;
}

double RigidBody::inv_mass() const {
  return (is_static || is_kinematic || mass < 1e-10) ? 0.0 : 1.0 / mass;
}
Vec3 RigidBody::inv_inertia() const {
  if (is_static || is_kinematic)
    return Vec3(0, 0, 0);
  return Vec3(inertia.x > 1e-10 ? 1.0 / inertia.x : 0.0,
              inertia.y > 1e-10 ? 1.0 / inertia.y : 0.0,
              inertia.z > 1e-10 ? 1.0 / inertia.z : 0.0);
}
Vec3 RigidBody::position() const { return pose.lin; }
void RigidBody::world_inertia_inv(double *Iinv) const {
  if (is_static || is_kinematic) {
    for (int i = 0; i < 9; ++i)
      Iinv[i] = 0.0;
    return;
  }
  double R[9];
  pose.rotation_matrix(R);
  Vec3 d = inv_inertia();
  for (int i = 0; i < 3; ++i)
    for (int j = 0; j < 3; ++j)
      Iinv[i * 3 + j] = R[i * 3] * d.x * R[j * 3] +
                        R[i * 3 + 1] * d.y * R[j * 3 + 1] +
                        R[i * 3 + 2] * d.z * R[j * 3 + 2];
}
Vec3 RigidBody::apply_inv_inertia_world(const Vec3 &v) const {
  double m[9];
  world_inertia_inv(m);
  return Vec3(m[0] * v.x + m[1] * v.y + m[2] * v.z,
              m[3] * v.x + m[4] * v.y + m[5] * v.z,
              m[6] * v.x + m[7] * v.y + m[8] * v.z);
}
Vec3 RigidBody::point_velocity(const Vec3 &p) const {
  return linear_velocity + angular_velocity.cross(p - pose.lin);
}
void RigidBody::add_force(const Vec3 &f) {
  if (!is_static && !is_kinematic)
    force += f;
}
void RigidBody::add_torque(const Vec3 &t) {
  if (!is_static && !is_kinematic)
    torque += t;
}
void RigidBody::add_force_at_point(const Vec3 &f, const Vec3 &p) {
  if (!is_static && !is_kinematic) {
    force += f;
    torque += (p - pose.lin).cross(f);
  }
}
void RigidBody::apply_impulse(const Vec3 &i) {
  if (!is_static && !is_kinematic)
    linear_velocity += i * inv_mass();
}
void RigidBody::apply_angular_impulse(const Vec3 &i) {
  if (!is_static && !is_kinematic)
    angular_velocity += apply_inv_inertia_world(i);
}
void RigidBody::apply_impulse_at_point(const Vec3 &i, const Vec3 &p) {
  if (!is_static && !is_kinematic) {
    linear_velocity += i * inv_mass();
    angular_velocity += apply_inv_inertia_world((p - pose.lin).cross(i));
  }
}
void RigidBody::integrate_forces(double dt, const Vec3 &gravity) {
  if (is_static || is_kinematic) {
    force = Vec3();
    torque = Vec3();
    return;
  }
  linear_velocity += (gravity + force * inv_mass()) * dt;
  double R[9];
  pose.rotation_matrix(R);
  Vec3 wb(R[0] * angular_velocity.x + R[3] * angular_velocity.y +
              R[6] * angular_velocity.z,
          R[1] * angular_velocity.x + R[4] * angular_velocity.y +
              R[7] * angular_velocity.z,
          R[2] * angular_velocity.x + R[5] * angular_velocity.y +
              R[8] * angular_velocity.z);
  Vec3 lb(inertia.x * wb.x, inertia.y * wb.y, inertia.z * wb.z);
  Vec3 lw(R[0] * lb.x + R[1] * lb.y + R[2] * lb.z,
          R[3] * lb.x + R[4] * lb.y + R[5] * lb.z,
          R[6] * lb.x + R[7] * lb.y + R[8] * lb.z);
  angular_velocity +=
      apply_inv_inertia_world(torque - angular_velocity.cross(lw)) * dt;
  linear_velocity *= 1.0 - linear_damping * dt;
  angular_velocity *= 1.0 - angular_damping * dt;
  force = Vec3();
  torque = Vec3();
}
void RigidBody::integrate_positions(double dt) {
  if (is_static)
    return;
  pose.lin += linear_velocity * dt;
  const double theta = angular_velocity.norm() * dt;
  if (theta > 1e-10) {
    Vec3 axis = angular_velocity / angular_velocity.norm();
    const double h = theta * 0.5;
    pose.ang = (Quat(axis.x * std::sin(h), axis.y * std::sin(h),
                     axis.z * std::sin(h), std::cos(h)) *
                pose.ang)
                   .normalized();
  }
}
} // namespace termin::physics
