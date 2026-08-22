#include <cmath>
#include <termin/physics/rigid_body.hpp>

namespace termin::physics {

    RigidBody RigidBody::create_box(const Vec3& size, double m, const Pose3& p, bool stat) {
        RigidBody body;
        body.pose = p;
        body.mass = m;
        body.is_static = stat;
        body.inertia.x = (m / 12.0) * (size.y * size.y + size.z * size.z);
        body.inertia.y = (m / 12.0) * (size.x * size.x + size.z * size.z);
        body.inertia.z = (m / 12.0) * (size.x * size.x + size.y * size.y);
        return body;
    }

    RigidBody RigidBody::create_sphere(double radius, double m, const Pose3& p, bool stat) {
        RigidBody body;
        body.pose = p;
        body.mass = m;
        body.is_static = stat;
        const double I = 0.4 * m * radius * radius;
        body.inertia = Vec3(I, I, I);
        return body;
    }

    RigidBody
    RigidBody::create_with_mass_properties(const SpatialInertia3& properties, const Pose3& shape_pose, bool stat) {
        RigidBody body;
        body.mass = properties.mass;
        body.inertia = properties.principal_moments;
        body.inertia_frame_local = properties.inertia_frame;
        body.is_static = stat;
        body.set_shape_pose(shape_pose);
        return body;
    }

    Pose3 RigidBody::shape_pose() const {
        return Pose3(pose.ang, pose.lin - pose.ang.rotate(inertia_frame_local.lin));
    }

    void RigidBody::set_shape_pose(const Pose3& shape_pose_value) {
        pose.ang = shape_pose_value.ang;
        pose.lin = shape_pose_value.transform_point(inertia_frame_local.lin);
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
    Vec3 RigidBody::position() const {
        return pose.lin;
    }
    Mat33 RigidBody::world_inertia_inv() const {
        const Mat33 principal_rotation = Mat33::rotation(pose.ang * inertia_frame_local.ang);
        return principal_rotation * Mat33::scale(inv_inertia()) * principal_rotation.transposed();
    }
    Vec3 RigidBody::apply_inv_inertia_world(const Vec3& v) const {
        return world_inertia_inv().transform(v);
    }
    Vec3 RigidBody::point_velocity(const Vec3& p) const {
        return linear_velocity + angular_velocity.cross(p - pose.lin);
    }
    void RigidBody::add_force(const Vec3& f) {
        if (!is_static && !is_kinematic)
            force += f;
    }
    void RigidBody::add_torque(const Vec3& t) {
        if (!is_static && !is_kinematic)
            torque += t;
    }
    void RigidBody::add_force_at_point(const Vec3& f, const Vec3& p) {
        if (!is_static && !is_kinematic) {
            force += f;
            torque += (p - pose.lin).cross(f);
        }
    }
    void RigidBody::apply_impulse(const Vec3& i) {
        if (!is_static && !is_kinematic)
            linear_velocity += i * inv_mass();
    }
    void RigidBody::apply_angular_impulse(const Vec3& i) {
        if (!is_static && !is_kinematic)
            angular_velocity += apply_inv_inertia_world(i);
    }
    void RigidBody::apply_impulse_at_point(const Vec3& i, const Vec3& p) {
        if (!is_static && !is_kinematic) {
            linear_velocity += i * inv_mass();
            angular_velocity += apply_inv_inertia_world((p - pose.lin).cross(i));
        }
    }
    void RigidBody::integrate_forces(double dt, const Vec3& gravity) {
        if (is_static || is_kinematic) {
            force = Vec3();
            torque = Vec3();
            return;
        }
        linear_velocity += (gravity + force * inv_mass()) * dt;
        const Mat33 principal_rotation = Mat33::rotation(pose.ang * inertia_frame_local.ang);
        const Vec3 body_angular_velocity = principal_rotation.transposed().transform(angular_velocity);
        const Vec3 world_angular_momentum =
            principal_rotation.transform(inertia.cwise_product(body_angular_velocity));
        angular_velocity +=
            apply_inv_inertia_world(torque - angular_velocity.cross(world_angular_momentum)) * dt;
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
            pose.ang = (Quat(axis.x * std::sin(h), axis.y * std::sin(h), axis.z * std::sin(h), std::cos(h)) * pose.ang)
                           .normalized();
        }
    }
} // namespace termin::physics
