#include <termin/qopt/multibody3d.hpp>

#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <cstdio>
#include <exception>
#include <string>
#include <utility>
#include <variant>
#include <vector>

namespace termin::qopt {
namespace {

using Matrix3 = std::array<double, 9>;
using Matrix6 = std::array<double, 36>;
using PointJacobian = std::array<double, 18>;
using RevoluteJacobian = std::array<double, 30>;

std::atomic<std::uint64_t> next_multibody3d_system_id{1};

[[nodiscard]] bool finite(double value) noexcept {
  return std::isfinite(value);
}

[[nodiscard]] bool finite(termin::Vec3 value) noexcept {
  return finite(value.x) && finite(value.y) && finite(value.z);
}

[[nodiscard]] bool finite(termin::Quat value) noexcept {
  return finite(value.x)
      && finite(value.y)
      && finite(value.z)
      && finite(value.w);
}

[[nodiscard]] bool finite(termin::Pose3 value) noexcept {
  return finite(value.ang) && finite(value.lin);
}

[[nodiscard]] bool finite(RigidBody3DState value) noexcept {
  return finite(value.pose)
      && finite(value.linear_velocity_world)
      && finite(value.angular_velocity_world);
}

[[nodiscard]] bool valid_inertia(const SpatialInertia3D& inertia) noexcept {
  return finite(inertia.mass)
      && inertia.mass > 0.0
      && finite(inertia.principal_moments)
      && inertia.principal_moments.x > 0.0
      && inertia.principal_moments.y > 0.0
      && inertia.principal_moments.z > 0.0
      && finite(inertia.inertia_frame_local)
      && inertia.inertia_frame_local.ang.norm() > 1e-10;
}

[[nodiscard]] double linf(termin::Vec3 value) noexcept {
  return std::max({
      std::abs(value.x),
      std::abs(value.y),
      std::abs(value.z),
  });
}

[[nodiscard]] Matrix3 rotation_matrix(termin::Quat orientation) noexcept {
  Matrix3 result{};
  orientation.normalized().to_matrix(result.data());
  return result;
}

[[nodiscard]] Matrix3 transpose(const Matrix3& matrix) noexcept {
  return {
      matrix[0], matrix[3], matrix[6],
      matrix[1], matrix[4], matrix[7],
      matrix[2], matrix[5], matrix[8],
  };
}

[[nodiscard]] Matrix3 multiply(
    const Matrix3& first, const Matrix3& second
) noexcept {
  Matrix3 result{};
  for (std::size_t row = 0; row < 3; ++row) {
    for (std::size_t column = 0; column < 3; ++column) {
      for (std::size_t inner = 0; inner < 3; ++inner) {
        result[row * 3 + column] +=
            first[row * 3 + inner] * second[inner * 3 + column];
      }
    }
  }
  return result;
}

[[nodiscard]] termin::Vec3 multiply(
    const Matrix3& matrix, termin::Vec3 vector
) noexcept {
  return {
      matrix[0] * vector.x + matrix[1] * vector.y
          + matrix[2] * vector.z,
      matrix[3] * vector.x + matrix[4] * vector.y
          + matrix[5] * vector.z,
      matrix[6] * vector.x + matrix[7] * vector.y
          + matrix[8] * vector.z,
  };
}

[[nodiscard]] Matrix3 central_inertia_world(
    const SpatialInertia3D& inertia,
    termin::Quat body_orientation
) noexcept {
  const termin::Quat principal_orientation =
      (body_orientation.normalized()
       * inertia.inertia_frame_local.ang.normalized())
          .normalized();
  const Matrix3 rotation = rotation_matrix(principal_orientation);
  const Matrix3 diagonal{
      inertia.principal_moments.x, 0.0, 0.0,
      0.0, inertia.principal_moments.y, 0.0,
      0.0, 0.0, inertia.principal_moments.z,
  };
  return multiply(multiply(rotation, diagonal), transpose(rotation));
}

[[nodiscard]] Matrix6 spatial_inertia_world(
    const SpatialInertia3D& inertia,
    termin::Quat body_orientation
) noexcept {
  const double mass = inertia.mass;
  const termin::Vec3 center = body_orientation.normalized().rotate(
      inertia.inertia_frame_local.lin
  );
  const Matrix3 central =
      central_inertia_world(inertia, body_orientation);
  Matrix6 result{};

  for (std::size_t axis = 0; axis < 3; ++axis) {
    result[axis * 6 + axis] = mass;
  }

  const Matrix3 skew{
      0.0, -center.z, center.y,
      center.z, 0.0, -center.x,
      -center.y, center.x, 0.0,
  };
  for (std::size_t row = 0; row < 3; ++row) {
    for (std::size_t column = 0; column < 3; ++column) {
      result[row * 6 + column + 3] =
          -mass * skew[row * 3 + column];
      result[(row + 3) * 6 + column] =
          mass * skew[row * 3 + column];
      const double parallel_axis =
          mass
          * ((row == column ? center.dot(center) : 0.0)
             - center[static_cast<int>(row)]
                 * center[static_cast<int>(column)]);
      result[(row + 3) * 6 + column + 3] =
          central[row * 3 + column] + parallel_axis;
    }
  }
  return result;
}

[[nodiscard]] termin::Quat rotation_vector_quaternion(
    termin::Vec3 rotation_vector
) noexcept {
  const double angle = rotation_vector.norm();
  if (angle < 1e-12) {
    return termin::Quat{
        rotation_vector.x * 0.5,
        rotation_vector.y * 0.5,
        rotation_vector.z * 0.5,
        1.0,
    }.normalized();
  }
  return termin::Quat::from_axis_angle(rotation_vector / angle, angle);
}

[[nodiscard]] PointJacobian point_jacobian(termin::Vec3 radius) noexcept {
  return {
      1.0, 0.0, 0.0, 0.0, radius.z, -radius.y,
      0.0, 1.0, 0.0, -radius.z, 0.0, radius.x,
      0.0, 0.0, 1.0, radius.y, -radius.x, 0.0,
  };
}

[[nodiscard]] ConstDenseMatrixView matrix_view(
    const Matrix6& values
) noexcept {
  return ConstDenseMatrixView::row_major(values.data(), 6, 6);
}

[[nodiscard]] ConstDenseMatrixView matrix_view(
    const PointJacobian& values
) noexcept {
  return ConstDenseMatrixView::row_major(values.data(), 3, 6);
}

[[nodiscard]] ConstDenseMatrixView matrix_view(
    const RevoluteJacobian& values
) noexcept {
  return ConstDenseMatrixView::row_major(values.data(), 5, 6);
}

[[nodiscard]] ConstDenseVectorView vector_view(
    const std::array<double, 6>& values
) noexcept {
  return {values.data(), values.size(), 1};
}

[[nodiscard]] ConstDenseVectorView vector_view(
    const std::array<double, 3>& values
) noexcept {
  return {values.data(), values.size(), 1};
}

[[nodiscard]] ConstDenseVectorView vector_view(
    const std::array<double, 5>& values
) noexcept {
  return {values.data(), values.size(), 1};
}

[[nodiscard]] Multibody3DStepResult failure(
    QpStatus status,
    Multibody3DDiagnostic diagnostic,
    QpSolveResult dynamics = {}
) noexcept {
  Multibody3DStepResult result;
  result.status = status;
  result.diagnostic = diagnostic;
  result.dynamics = dynamics;
  return result;
}

} // namespace

struct Multibody3DSystem::Impl {
  struct Body {
    SpatialInertia3D inertia;
    RigidBody3DState state;
    RigidBody3DAcceleration acceleration;
    RigidBody3DWrench wrench;
    DynamicsDofHandle dofs;
    std::string name;
  };

  struct FixedPointJoint {
    std::size_t body = 0;
    termin::Vec3 body_anchor_local;
    termin::Vec3 world_anchor;
  };

  struct PointJoint {
    std::size_t body_a = 0;
    std::size_t body_b = 0;
    termin::Vec3 body_a_anchor_local;
    termin::Vec3 body_b_anchor_local;
  };

  struct FixedRevoluteJoint {
    std::size_t body = 0;
    termin::Vec3 body_anchor_local;
    termin::Vec3 body_axis_local;
    termin::Vec3 world_anchor;
    termin::Vec3 world_axis;
  };

  struct RevoluteJoint {
    std::size_t body_a = 0;
    std::size_t body_b = 0;
    termin::Vec3 body_a_anchor_local;
    termin::Vec3 body_a_axis_local;
    termin::Vec3 body_b_anchor_local;
    termin::Vec3 body_b_axis_local;
  };

  struct Joint {
    std::variant<
        FixedPointJoint,
        PointJoint,
        FixedRevoluteJoint,
        RevoluteJoint
    > model;
    DynamicsConstraintHandle constraint;
    termin::Vec3 force_reaction = termin::Vec3::zero();
    termin::Vec3 torque_reaction = termin::Vec3::zero();
    std::string name;
  };

  struct HingeFrame {
    termin::Vec3 axis_a;
    termin::Vec3 axis_b;
    termin::Vec3 tangent_1;
    termin::Vec3 tangent_2;
  };

  std::uint64_t id =
      next_multibody3d_system_id.fetch_add(1, std::memory_order_relaxed);
  DynamicsTopology topology;
  std::vector<Body> bodies;
  std::vector<Joint> joints;
  std::vector<double> mass;
  std::vector<double> load;
  std::vector<double> jacobian;
  std::vector<double> constraint_rhs;
  std::vector<double> acceleration;
  std::vector<double> reaction;
  bool finalized = false;

  [[nodiscard]] bool valid(RigidBody3DHandle handle) const noexcept {
    return handle.system_id == id && handle.index < bodies.size();
  }

  [[nodiscard]] bool valid(PointJoint3DHandle handle) const noexcept {
    return handle.system_id == id && handle.index < joints.size()
        && (
            std::holds_alternative<FixedPointJoint>(
                joints[handle.index].model
            )
            || std::holds_alternative<PointJoint>(
                joints[handle.index].model
            )
        );
  }

  [[nodiscard]] bool valid(RevoluteJoint3DHandle handle) const noexcept {
    return handle.system_id == id && handle.index < joints.size()
        && (
            std::holds_alternative<FixedRevoluteJoint>(
                joints[handle.index].model
            )
            || std::holds_alternative<RevoluteJoint>(
                joints[handle.index].model
            )
        );
  }

  [[nodiscard]] termin::Vec3 center_world(const Body& body) const noexcept {
    return body.state.pose.ang.rotate(
        body.inertia.inertia_frame_local.lin
    );
  }

  [[nodiscard]] Matrix6 body_mass(const Body& body) const noexcept {
    return spatial_inertia_world(body.inertia, body.state.pose.ang);
  }

  [[nodiscard]] std::array<double, 6> body_load(
      const Body& body, termin::Vec3 gravity
  ) const noexcept {
    const termin::Vec3 center = center_world(body);
    const Matrix3 central =
        central_inertia_world(body.inertia, body.state.pose.ang);
    const termin::Vec3 centrifugal_acceleration =
        body.state.angular_velocity_world.cross(
            body.state.angular_velocity_world.cross(center)
        );
    const termin::Vec3 angular_momentum_at_center =
        multiply(central, body.state.angular_velocity_world);
    const termin::Vec3 gyroscopic_torque =
        body.state.angular_velocity_world.cross(
            angular_momentum_at_center
        );
    const termin::Vec3 gravity_force = gravity * body.inertia.mass;
    const termin::Vec3 force =
        body.wrench.force_world
        + gravity_force
        - centrifugal_acceleration * body.inertia.mass;
    const termin::Vec3 torque =
        body.wrench.torque_about_origin_world
        + center.cross(gravity_force)
        - gyroscopic_torque
        - center.cross(
            centrifugal_acceleration * body.inertia.mass
        );
    return {
        force.x, force.y, force.z,
        torque.x, torque.y, torque.z,
    };
  }

  [[nodiscard]] termin::Vec3 radius_world(
      const Body& body, termin::Vec3 anchor_local
  ) const noexcept {
    return body.state.pose.ang.rotate(anchor_local);
  }

  [[nodiscard]] static HingeFrame hinge_frame(
      termin::Vec3 axis_a, termin::Vec3 axis_b
  ) noexcept {
    axis_a = axis_a / axis_a.norm();
    axis_b = axis_b / axis_b.norm();
    termin::Vec3 reference =
        std::abs(axis_a.x) <= std::abs(axis_a.y)
            && std::abs(axis_a.x) <= std::abs(axis_a.z)
        ? termin::Vec3{1.0, 0.0, 0.0}
        : (
              std::abs(axis_a.y) <= std::abs(axis_a.z)
                  ? termin::Vec3{0.0, 1.0, 0.0}
                  : termin::Vec3{0.0, 0.0, 1.0}
          );
    const termin::Vec3 tangent_1 =
        axis_a.cross(reference).normalized();
    return {
        axis_a,
        axis_b,
        tangent_1,
        axis_a.cross(tangent_1).normalized(),
    };
  }

  [[nodiscard]] HingeFrame hinge_frame(
      const FixedRevoluteJoint& joint
  ) const noexcept {
    return hinge_frame(
        bodies[joint.body].state.pose.ang.rotate(joint.body_axis_local),
        joint.world_axis
    );
  }

  [[nodiscard]] HingeFrame hinge_frame(
      const RevoluteJoint& joint
  ) const noexcept {
    return hinge_frame(
        bodies[joint.body_a].state.pose.ang.rotate(
            joint.body_a_axis_local
        ),
        bodies[joint.body_b].state.pose.ang.rotate(
            joint.body_b_axis_local
        )
    );
  }

  [[nodiscard]] static termin::Vec3 angular_axis_column(
      termin::Vec3 basis_axis,
      termin::Vec3 axis_a,
      termin::Vec3 axis_b,
      bool first_body
  ) noexcept {
    if (first_body) {
      return basis_axis.cross(axis_a).cross(axis_b);
    }
    return axis_a.cross(basis_axis.cross(axis_b));
  }

  static void set_orientation_rows(
      RevoluteJacobian& block,
      const HingeFrame& frame,
      bool first_body
  ) noexcept {
    const std::array<termin::Vec3, 3> basis{
        termin::Vec3{1.0, 0.0, 0.0},
        termin::Vec3{0.0, 1.0, 0.0},
        termin::Vec3{0.0, 0.0, 1.0},
    };
    for (std::size_t column = 0; column < 3; ++column) {
      const termin::Vec3 response = angular_axis_column(
          basis[column], frame.axis_a, frame.axis_b, first_body
      );
      block[3 * 6 + column + 3] = frame.tangent_1.dot(response);
      block[4 * 6 + column + 3] = frame.tangent_2.dot(response);
    }
  }

  [[nodiscard]] static RevoluteJacobian revolute_jacobian(
      termin::Vec3 radius,
      const HingeFrame& frame,
      bool first_body
  ) noexcept {
    RevoluteJacobian result{};
    const PointJacobian point = point_jacobian(radius);
    const double sign = first_body ? 1.0 : -1.0;
    for (std::size_t value = 0; value < point.size(); ++value) {
      result[(value / 6) * 6 + value % 6] = sign * point[value];
    }
    set_orientation_rows(result, frame, first_body);
    return result;
  }

  [[nodiscard]] static std::array<double, 2> orientation_rhs(
      const HingeFrame& frame,
      termin::Vec3 omega_a,
      termin::Vec3 omega_b
  ) noexcept {
    const termin::Vec3 axis_a_velocity = omega_a.cross(frame.axis_a);
    const termin::Vec3 axis_b_velocity = omega_b.cross(frame.axis_b);
    const termin::Vec3 bias =
        omega_a.cross(axis_a_velocity).cross(frame.axis_b)
        + axis_a_velocity.cross(axis_b_velocity) * 2.0
        + frame.axis_a.cross(omega_b.cross(axis_b_velocity));
    return {
        -frame.tangent_1.dot(bias),
        -frame.tangent_2.dot(bias),
    };
  }

  [[nodiscard]] AssemblyDiagnostic assemble(
      DynamicsAssembly& assembly, termin::Vec3 gravity
  ) noexcept {
    AssemblyDiagnostic diagnostic = assembly.clear();
    if (diagnostic != AssemblyDiagnostic::None) {
      return diagnostic;
    }
    for (const Body& body : bodies) {
      const Matrix6 mass_block = body_mass(body);
      diagnostic = assembly.add_mass(
          body.dofs, body.dofs, matrix_view(mass_block)
      );
      if (diagnostic != AssemblyDiagnostic::None) {
        return diagnostic;
      }
      const std::array<double, 6> load_block = body_load(body, gravity);
      diagnostic = assembly.add_load(body.dofs, vector_view(load_block));
      if (diagnostic != AssemblyDiagnostic::None) {
        return diagnostic;
      }
    }

    for (const Joint& joint : joints) {
      if (const auto* fixed = std::get_if<FixedPointJoint>(&joint.model)) {
        const Body& body = bodies[fixed->body];
        const termin::Vec3 radius =
            radius_world(body, fixed->body_anchor_local);
        const PointJacobian jacobian_block = point_jacobian(radius);
        diagnostic = assembly.add_constraint_jacobian(
            joint.constraint, body.dofs, matrix_view(jacobian_block)
        );
        if (diagnostic != AssemblyDiagnostic::None) {
          return diagnostic;
        }
        const termin::Vec3 bias =
            body.state.angular_velocity_world.cross(
                body.state.angular_velocity_world.cross(radius)
            );
        const std::array<double, 3> rhs{-bias.x, -bias.y, -bias.z};
        diagnostic =
            assembly.add_constraint_rhs(joint.constraint, vector_view(rhs));
      } else if (
          const auto* point = std::get_if<PointJoint>(&joint.model)
      ) {
        const Body& body_a = bodies[point->body_a];
        const Body& body_b = bodies[point->body_b];
        const termin::Vec3 radius_a =
            radius_world(body_a, point->body_a_anchor_local);
        const termin::Vec3 radius_b =
            radius_world(body_b, point->body_b_anchor_local);
        const PointJacobian jacobian_a = point_jacobian(radius_a);
        PointJacobian jacobian_b = point_jacobian(radius_b);
        for (double& value : jacobian_b) {
          value = -value;
        }
        diagnostic = assembly.add_constraint_jacobian(
            joint.constraint, body_a.dofs, matrix_view(jacobian_a)
        );
        if (diagnostic != AssemblyDiagnostic::None) {
          return diagnostic;
        }
        diagnostic = assembly.add_constraint_jacobian(
            joint.constraint, body_b.dofs, matrix_view(jacobian_b)
        );
        if (diagnostic != AssemblyDiagnostic::None) {
          return diagnostic;
        }
        const termin::Vec3 bias_a =
            body_a.state.angular_velocity_world.cross(
                body_a.state.angular_velocity_world.cross(radius_a)
            );
        const termin::Vec3 bias_b =
            body_b.state.angular_velocity_world.cross(
                body_b.state.angular_velocity_world.cross(radius_b)
            );
        const termin::Vec3 rhs_value = -bias_a + bias_b;
        const std::array<double, 3> rhs{
            rhs_value.x, rhs_value.y, rhs_value.z,
        };
        diagnostic =
            assembly.add_constraint_rhs(joint.constraint, vector_view(rhs));
      } else if (
          const auto* fixed =
              std::get_if<FixedRevoluteJoint>(&joint.model)
      ) {
        const Body& body = bodies[fixed->body];
        const termin::Vec3 radius =
            radius_world(body, fixed->body_anchor_local);
        const HingeFrame frame = hinge_frame(*fixed);
        const RevoluteJacobian jacobian_block =
            revolute_jacobian(radius, frame, true);
        diagnostic = assembly.add_constraint_jacobian(
            joint.constraint, body.dofs, matrix_view(jacobian_block)
        );
        if (diagnostic != AssemblyDiagnostic::None) {
          return diagnostic;
        }
        const termin::Vec3 point_bias =
            body.state.angular_velocity_world.cross(
                body.state.angular_velocity_world.cross(radius)
            );
        const std::array<double, 2> angular_rhs = orientation_rhs(
            frame,
            body.state.angular_velocity_world,
            termin::Vec3::zero()
        );
        const std::array<double, 5> rhs{
            -point_bias.x,
            -point_bias.y,
            -point_bias.z,
            angular_rhs[0],
            angular_rhs[1],
        };
        diagnostic =
            assembly.add_constraint_rhs(joint.constraint, vector_view(rhs));
      } else {
        const auto& revolute = std::get<RevoluteJoint>(joint.model);
        const Body& body_a = bodies[revolute.body_a];
        const Body& body_b = bodies[revolute.body_b];
        const termin::Vec3 radius_a =
            radius_world(body_a, revolute.body_a_anchor_local);
        const termin::Vec3 radius_b =
            radius_world(body_b, revolute.body_b_anchor_local);
        const HingeFrame frame = hinge_frame(revolute);
        const RevoluteJacobian jacobian_a =
            revolute_jacobian(radius_a, frame, true);
        const RevoluteJacobian jacobian_b =
            revolute_jacobian(radius_b, frame, false);
        diagnostic = assembly.add_constraint_jacobian(
            joint.constraint, body_a.dofs, matrix_view(jacobian_a)
        );
        if (diagnostic != AssemblyDiagnostic::None) {
          return diagnostic;
        }
        diagnostic = assembly.add_constraint_jacobian(
            joint.constraint, body_b.dofs, matrix_view(jacobian_b)
        );
        if (diagnostic != AssemblyDiagnostic::None) {
          return diagnostic;
        }
        const termin::Vec3 bias_a =
            body_a.state.angular_velocity_world.cross(
                body_a.state.angular_velocity_world.cross(radius_a)
            );
        const termin::Vec3 bias_b =
            body_b.state.angular_velocity_world.cross(
                body_b.state.angular_velocity_world.cross(radius_b)
            );
        const termin::Vec3 point_rhs = -bias_a + bias_b;
        const std::array<double, 2> angular_rhs = orientation_rhs(
            frame,
            body_a.state.angular_velocity_world,
            body_b.state.angular_velocity_world
        );
        const std::array<double, 5> rhs{
            point_rhs.x,
            point_rhs.y,
            point_rhs.z,
            angular_rhs[0],
            angular_rhs[1],
        };
        diagnostic =
            assembly.add_constraint_rhs(joint.constraint, vector_view(rhs));
      }
      if (diagnostic != AssemblyDiagnostic::None) {
        return diagnostic;
      }
    }
    return AssemblyDiagnostic::None;
  }

  [[nodiscard]] termin::Vec3 position_error(
      const Joint& joint
  ) const noexcept {
    if (const auto* fixed = std::get_if<FixedPointJoint>(&joint.model)) {
      return bodies[fixed->body].state.pose.transform_point(
                 fixed->body_anchor_local
             )
          - fixed->world_anchor;
    }
    if (const auto* point = std::get_if<PointJoint>(&joint.model)) {
      return bodies[point->body_a].state.pose.transform_point(
                 point->body_a_anchor_local
             )
          - bodies[point->body_b].state.pose.transform_point(
              point->body_b_anchor_local
          );
    }
    if (const auto* fixed =
            std::get_if<FixedRevoluteJoint>(&joint.model)) {
      return bodies[fixed->body].state.pose.transform_point(
                 fixed->body_anchor_local
             )
          - fixed->world_anchor;
    }
    const auto& revolute = std::get<RevoluteJoint>(joint.model);
    return bodies[revolute.body_a].state.pose.transform_point(
               revolute.body_a_anchor_local
           )
        - bodies[revolute.body_b].state.pose.transform_point(
            revolute.body_b_anchor_local
        );
  }

  [[nodiscard]] std::array<double, 2> orientation_position_error(
      const Joint& joint
  ) const noexcept {
    HingeFrame frame;
    if (const auto* fixed =
            std::get_if<FixedRevoluteJoint>(&joint.model)) {
      frame = hinge_frame(*fixed);
    } else if (
        const auto* revolute = std::get_if<RevoluteJoint>(&joint.model)
    ) {
      frame = hinge_frame(*revolute);
    } else {
      return {0.0, 0.0};
    }
    const termin::Vec3 error = frame.axis_a.cross(frame.axis_b);
    return {
        frame.tangent_1.dot(error),
        frame.tangent_2.dot(error),
    };
  }

  [[nodiscard]] termin::Vec3 velocity_error(
      const Joint& joint
  ) const noexcept {
    const auto point_velocity = [&](const Body& body, termin::Vec3 local) {
      const termin::Vec3 radius = radius_world(body, local);
      return body.state.linear_velocity_world
          + body.state.angular_velocity_world.cross(radius);
    };
    if (const auto* fixed = std::get_if<FixedPointJoint>(&joint.model)) {
      return point_velocity(
          bodies[fixed->body], fixed->body_anchor_local
      );
    }
    if (const auto* point = std::get_if<PointJoint>(&joint.model)) {
      return point_velocity(
                 bodies[point->body_a], point->body_a_anchor_local
             )
          - point_velocity(
              bodies[point->body_b], point->body_b_anchor_local
          );
    }
    if (const auto* fixed =
            std::get_if<FixedRevoluteJoint>(&joint.model)) {
      return point_velocity(
          bodies[fixed->body], fixed->body_anchor_local
      );
    }
    const auto& revolute = std::get<RevoluteJoint>(joint.model);
    return point_velocity(
               bodies[revolute.body_a],
               revolute.body_a_anchor_local
           )
        - point_velocity(
            bodies[revolute.body_b],
            revolute.body_b_anchor_local
        );
  }

  [[nodiscard]] std::array<double, 2> orientation_velocity_error(
      const Joint& joint
  ) const noexcept {
    HingeFrame frame;
    termin::Vec3 omega_a = termin::Vec3::zero();
    termin::Vec3 omega_b = termin::Vec3::zero();
    if (const auto* fixed =
            std::get_if<FixedRevoluteJoint>(&joint.model)) {
      frame = hinge_frame(*fixed);
      omega_a = bodies[fixed->body].state.angular_velocity_world;
    } else if (
        const auto* revolute = std::get_if<RevoluteJoint>(&joint.model)
    ) {
      frame = hinge_frame(*revolute);
      omega_a =
          bodies[revolute->body_a].state.angular_velocity_world;
      omega_b =
          bodies[revolute->body_b].state.angular_velocity_world;
    } else {
      return {0.0, 0.0};
    }
    const termin::Vec3 derivative =
        omega_a.cross(frame.axis_a).cross(frame.axis_b)
        + frame.axis_a.cross(omega_b.cross(frame.axis_b));
    return {
        frame.tangent_1.dot(derivative),
        frame.tangent_2.dot(derivative),
    };
  }

  [[nodiscard]] double max_position_error() const noexcept {
    double result = 0.0;
    for (const Joint& joint : joints) {
      result = std::max(result, linf(position_error(joint)));
      const auto angular = orientation_position_error(joint);
      result = std::max(
          result, std::max(std::abs(angular[0]), std::abs(angular[1]))
      );
    }
    return result;
  }

  [[nodiscard]] double max_velocity_error() const noexcept {
    double result = 0.0;
    for (const Joint& joint : joints) {
      result = std::max(result, linf(velocity_error(joint)));
      const auto angular = orientation_velocity_error(joint);
      result = std::max(
          result, std::max(std::abs(angular[0]), std::abs(angular[1]))
      );
    }
    return result;
  }

  void apply_generalized_state(
      ConstDenseVectorView values, bool velocity
  ) noexcept {
    for (Body& body : bodies) {
      const DenseBlockInfo info =
          topology.dof_topology().block_info(body.dofs.block);
      const termin::Vec3 linear{
          values[info.offset],
          values[info.offset + 1],
          values[info.offset + 2],
      };
      const termin::Vec3 angular{
          values[info.offset + 3],
          values[info.offset + 4],
          values[info.offset + 5],
      };
      if (velocity) {
        body.state.linear_velocity_world = linear;
        body.state.angular_velocity_world = angular;
      } else {
        body.state.pose.lin += linear;
        body.state.pose.ang =
            (rotation_vector_quaternion(angular) * body.state.pose.ang)
                .normalized();
      }
    }
  }

  [[nodiscard]] QpSolveResult project_positions(
      DynamicsAssembly& assembly,
      QpTolerance tolerance
  ) noexcept {
    std::vector<double> target(constraint_rhs.size());
    for (const Joint& joint : joints) {
      const DenseBlockInfo info =
          topology.constraint_topology().block_info(joint.constraint.block);
      const termin::Vec3 error = position_error(joint);
      target[info.offset] = -error.x;
      target[info.offset + 1] = -error.y;
      target[info.offset + 2] = -error.z;
      const std::array<double, 2> angular =
          orientation_position_error(joint);
      if (
          std::holds_alternative<FixedRevoluteJoint>(joint.model)
          || std::holds_alternative<RevoluteJoint>(joint.model)
      ) {
        target[info.offset + 3] = -angular[0];
        target[info.offset + 4] = -angular[1];
      }
    }
    std::vector<double> gradient(load.size(), 0.0);
    std::vector<double> delta(load.size());
    std::vector<double> dual(constraint_rhs.size());
    const ConstDynamicsSystemView system = assembly.system();
    const QpSolveResult result = solve_equality_qp(
        {
            system.mass,
            {gradient.data(), gradient.size(), 1},
            system.constraint_jacobian,
            {target.data(), target.size(), 1},
        },
        {
            {delta.data(), delta.size(), 1},
            {dual.data(), dual.size(), 1},
        },
        tolerance
    );
    if (result.status == QpStatus::Optimal) {
      apply_generalized_state({delta.data(), delta.size(), 1}, false);
    }
    return result;
  }

  [[nodiscard]] QpSolveResult project_velocities(
      DynamicsAssembly& assembly,
      QpTolerance tolerance
  ) noexcept {
    std::vector<double> current(load.size());
    for (const Body& body : bodies) {
      const DenseBlockInfo info =
          topology.dof_topology().block_info(body.dofs.block);
      current[info.offset] = body.state.linear_velocity_world.x;
      current[info.offset + 1] = body.state.linear_velocity_world.y;
      current[info.offset + 2] = body.state.linear_velocity_world.z;
      current[info.offset + 3] = body.state.angular_velocity_world.x;
      current[info.offset + 4] = body.state.angular_velocity_world.y;
      current[info.offset + 5] = body.state.angular_velocity_world.z;
    }
    const ConstDynamicsSystemView system = assembly.system();
    std::vector<double> target_load(load.size(), 0.0);
    for (std::size_t row = 0; row < system.mass.rows; ++row) {
      for (std::size_t column = 0; column < system.mass.columns; ++column) {
        target_load[row] += system.mass(row, column) * current[column];
      }
    }
    std::vector<double> projected(load.size());
    std::vector<double> projected_reaction(constraint_rhs.size());
    std::vector<double> zero_rhs(constraint_rhs.size(), 0.0);
    const QpSolveResult result = solve_constrained_dynamics(
        {
            system.mass,
            {target_load.data(), target_load.size(), 1},
            system.constraint_jacobian,
            {zero_rhs.data(), zero_rhs.size(), 1},
        },
        {
            {projected.data(), projected.size(), 1},
            {
                projected_reaction.data(),
                projected_reaction.size(),
                1,
            },
        },
        tolerance
    );
    if (result.status == QpStatus::Optimal) {
      apply_generalized_state(
          {projected.data(), projected.size(), 1}, true
      );
    }
    return result;
  }
};

std::string_view multibody3d_diagnostic_name(
    Multibody3DDiagnostic diagnostic
) noexcept {
  switch (diagnostic) {
    case Multibody3DDiagnostic::None:
      return "none";
    case Multibody3DDiagnostic::ModelFinalized:
      return "model_finalized";
    case Multibody3DDiagnostic::ModelNotFinalized:
      return "model_not_finalized";
    case Multibody3DDiagnostic::InvalidBody:
      return "invalid_body";
    case Multibody3DDiagnostic::InvalidJoint:
      return "invalid_joint";
    case Multibody3DDiagnostic::InvalidMass:
      return "invalid_mass";
    case Multibody3DDiagnostic::InvalidInertia:
      return "invalid_inertia";
    case Multibody3DDiagnostic::NonFiniteInput:
      return "non_finite_input";
    case Multibody3DDiagnostic::InvalidMatrixView:
      return "invalid_matrix_view";
    case Multibody3DDiagnostic::DuplicateBody:
      return "duplicate_body";
    case Multibody3DDiagnostic::InvalidJointAxis:
      return "invalid_joint_axis";
    case Multibody3DDiagnostic::InvalidTimeStep:
      return "invalid_time_step";
    case Multibody3DDiagnostic::InvalidProjectionOptions:
      return "invalid_projection_options";
    case Multibody3DDiagnostic::AssemblyFailure:
      return "assembly_failure";
    case Multibody3DDiagnostic::DynamicsFailure:
      return "dynamics_failure";
    case Multibody3DDiagnostic::PositionProjectionFailure:
      return "position_projection_failure";
    case Multibody3DDiagnostic::VelocityProjectionFailure:
      return "velocity_projection_failure";
    case Multibody3DDiagnostic::InternalFailure:
      return "internal_failure";
  }
  return "unknown";
}

Multibody3DDiagnostic write_spatial_inertia3d_matrix_world(
    const SpatialInertia3D& inertia,
    termin::Quat body_orientation_world,
    DenseMatrixView destination
) noexcept {
  if (!valid_inertia(inertia)) {
    return finite(inertia.mass) && inertia.mass > 0.0
        ? Multibody3DDiagnostic::InvalidInertia
        : Multibody3DDiagnostic::InvalidMass;
  }
  if (!finite(body_orientation_world)
      || body_orientation_world.norm() <= 1e-10) {
    return Multibody3DDiagnostic::NonFiniteInput;
  }
  if (destination.rows != 6
      || destination.columns != 6
      || destination.data == nullptr
      || destination.row_stride <= 0
      || destination.column_stride <= 0) {
    return Multibody3DDiagnostic::InvalidMatrixView;
  }
  const Matrix6 matrix =
      spatial_inertia_world(inertia, body_orientation_world);
  for (std::size_t row = 0; row < 6; ++row) {
    for (std::size_t column = 0; column < 6; ++column) {
      destination(row, column) = matrix[row * 6 + column];
    }
  }
  return Multibody3DDiagnostic::None;
}

Multibody3DSystem::Multibody3DSystem()
    : impl_(std::make_unique<Impl>()) {}

Multibody3DSystem::~Multibody3DSystem() = default;
Multibody3DSystem::Multibody3DSystem(Multibody3DSystem&&) noexcept = default;
Multibody3DSystem& Multibody3DSystem::operator=(
    Multibody3DSystem&&
) noexcept = default;

Multibody3DRegistrationResult<RigidBody3DHandle>
Multibody3DSystem::add_body(
    SpatialInertia3D inertia,
    RigidBody3DState initial_state,
    std::string_view diagnostic_name
) noexcept {
  if (impl_ == nullptr) {
    return {{}, Multibody3DDiagnostic::InternalFailure};
  }
  if (impl_->finalized) {
    return {{}, Multibody3DDiagnostic::ModelFinalized};
  }
  if (!finite(inertia.mass) || inertia.mass <= 0.0) {
    return {{}, Multibody3DDiagnostic::InvalidMass};
  }
  if (!valid_inertia(inertia)) {
    return {{}, Multibody3DDiagnostic::InvalidInertia};
  }
  if (!finite(initial_state)
      || initial_state.pose.ang.norm() <= 1e-10) {
    return {{}, Multibody3DDiagnostic::NonFiniteInput};
  }
  inertia.inertia_frame_local.ang =
      inertia.inertia_frame_local.ang.normalized();
  initial_state.pose.ang = initial_state.pose.ang.normalized();

  const auto registration =
      impl_->topology.register_dofs(6, diagnostic_name);
  if (!registration.ok()) {
    return {{}, Multibody3DDiagnostic::DuplicateBody};
  }
  try {
    const std::size_t index = impl_->bodies.size();
    impl_->bodies.push_back({
        inertia,
        initial_state,
        {},
        {},
        registration.handle,
        std::string(diagnostic_name),
    });
    return {{impl_->id, index}, Multibody3DDiagnostic::None};
  } catch (const std::exception& error) {
    std::fprintf(
        stderr, "[termin-qopt] add 3D body failed: %s\n", error.what()
    );
  } catch (...) {
    std::fprintf(
        stderr, "[termin-qopt] add 3D body failed with unknown exception\n"
    );
  }
  return {{}, Multibody3DDiagnostic::InternalFailure};
}

Multibody3DRegistrationResult<PointJoint3DHandle>
Multibody3DSystem::add_fixed_point_joint(
    RigidBody3DHandle body,
    termin::Vec3 body_anchor_local,
    termin::Vec3 world_anchor,
    std::string_view diagnostic_name
) noexcept {
  if (impl_ == nullptr) {
    return {{}, Multibody3DDiagnostic::InternalFailure};
  }
  if (impl_->finalized) {
    return {{}, Multibody3DDiagnostic::ModelFinalized};
  }
  if (!impl_->valid(body)) {
    return {{}, Multibody3DDiagnostic::InvalidBody};
  }
  if (!finite(body_anchor_local) || !finite(world_anchor)) {
    return {{}, Multibody3DDiagnostic::NonFiniteInput};
  }
  const auto registration =
      impl_->topology.register_constraint(3, diagnostic_name);
  if (!registration.ok()) {
    return {{}, Multibody3DDiagnostic::InvalidJoint};
  }
  try {
    const std::size_t index = impl_->joints.size();
    impl_->joints.push_back({
        Impl::FixedPointJoint{
            body.index, body_anchor_local, world_anchor,
        },
        registration.handle,
        {},
        {},
        std::string(diagnostic_name),
    });
    return {{impl_->id, index}, Multibody3DDiagnostic::None};
  } catch (const std::exception& error) {
    std::fprintf(
        stderr,
        "[termin-qopt] add fixed 3D point joint failed: %s\n",
        error.what()
    );
  } catch (...) {
    std::fprintf(
        stderr,
        "[termin-qopt] add fixed 3D point joint failed with unknown exception\n"
    );
  }
  return {{}, Multibody3DDiagnostic::InternalFailure};
}

Multibody3DRegistrationResult<PointJoint3DHandle>
Multibody3DSystem::add_point_joint(
    RigidBody3DHandle body_a,
    termin::Vec3 body_a_anchor_local,
    RigidBody3DHandle body_b,
    termin::Vec3 body_b_anchor_local,
    std::string_view diagnostic_name
) noexcept {
  if (impl_ == nullptr) {
    return {{}, Multibody3DDiagnostic::InternalFailure};
  }
  if (impl_->finalized) {
    return {{}, Multibody3DDiagnostic::ModelFinalized};
  }
  if (!impl_->valid(body_a)
      || !impl_->valid(body_b)
      || body_a.index == body_b.index) {
    return {{}, Multibody3DDiagnostic::InvalidBody};
  }
  if (!finite(body_a_anchor_local) || !finite(body_b_anchor_local)) {
    return {{}, Multibody3DDiagnostic::NonFiniteInput};
  }
  const auto registration =
      impl_->topology.register_constraint(3, diagnostic_name);
  if (!registration.ok()) {
    return {{}, Multibody3DDiagnostic::InvalidJoint};
  }
  try {
    const std::size_t index = impl_->joints.size();
    impl_->joints.push_back({
        Impl::PointJoint{
            body_a.index,
            body_b.index,
            body_a_anchor_local,
            body_b_anchor_local,
        },
        registration.handle,
        {},
        {},
        std::string(diagnostic_name),
    });
    return {{impl_->id, index}, Multibody3DDiagnostic::None};
  } catch (const std::exception& error) {
    std::fprintf(
        stderr, "[termin-qopt] add 3D point joint failed: %s\n", error.what()
    );
  } catch (...) {
    std::fprintf(
        stderr, "[termin-qopt] add 3D point joint failed with unknown exception\n"
    );
  }
  return {{}, Multibody3DDiagnostic::InternalFailure};
}

Multibody3DRegistrationResult<RevoluteJoint3DHandle>
Multibody3DSystem::add_fixed_revolute_joint(
    RigidBody3DHandle body,
    termin::Vec3 body_anchor_local,
    termin::Vec3 body_axis_local,
    termin::Vec3 world_anchor,
    termin::Vec3 world_axis,
    std::string_view diagnostic_name
) noexcept {
  if (impl_ == nullptr) {
    return {{}, Multibody3DDiagnostic::InternalFailure};
  }
  if (impl_->finalized) {
    return {{}, Multibody3DDiagnostic::ModelFinalized};
  }
  if (!impl_->valid(body)) {
    return {{}, Multibody3DDiagnostic::InvalidBody};
  }
  if (!finite(body_anchor_local)
      || !finite(body_axis_local)
      || !finite(world_anchor)
      || !finite(world_axis)) {
    return {{}, Multibody3DDiagnostic::NonFiniteInput};
  }
  if (body_axis_local.norm() <= 1e-10 || world_axis.norm() <= 1e-10) {
    std::fprintf(
        stderr,
        "[termin-qopt] fixed 3D revolute joint has a rank-deficient axis\n"
    );
    return {{}, Multibody3DDiagnostic::InvalidJointAxis};
  }
  body_axis_local = body_axis_local.normalized();
  world_axis = world_axis.normalized();
  const termin::Vec3 initial_body_axis =
      impl_->bodies[body.index].state.pose.ang.rotate(body_axis_local);
  if (initial_body_axis.dot(world_axis) < 0.0) {
    world_axis = -world_axis;
  }
  const auto registration =
      impl_->topology.register_constraint(5, diagnostic_name);
  if (!registration.ok()) {
    return {{}, Multibody3DDiagnostic::InvalidJoint};
  }
  try {
    const std::size_t index = impl_->joints.size();
    impl_->joints.push_back({
        Impl::FixedRevoluteJoint{
            body.index,
            body_anchor_local,
            body_axis_local,
            world_anchor,
            world_axis,
        },
        registration.handle,
        {},
        {},
        std::string(diagnostic_name),
    });
    return {{impl_->id, index}, Multibody3DDiagnostic::None};
  } catch (const std::exception& error) {
    std::fprintf(
        stderr,
        "[termin-qopt] add fixed 3D revolute joint failed: %s\n",
        error.what()
    );
  } catch (...) {
    std::fprintf(
        stderr,
        "[termin-qopt] add fixed 3D revolute joint failed with unknown exception\n"
    );
  }
  return {{}, Multibody3DDiagnostic::InternalFailure};
}

Multibody3DRegistrationResult<RevoluteJoint3DHandle>
Multibody3DSystem::add_revolute_joint(
    RigidBody3DHandle body_a,
    termin::Vec3 body_a_anchor_local,
    termin::Vec3 body_a_axis_local,
    RigidBody3DHandle body_b,
    termin::Vec3 body_b_anchor_local,
    termin::Vec3 body_b_axis_local,
    std::string_view diagnostic_name
) noexcept {
  if (impl_ == nullptr) {
    return {{}, Multibody3DDiagnostic::InternalFailure};
  }
  if (impl_->finalized) {
    return {{}, Multibody3DDiagnostic::ModelFinalized};
  }
  if (!impl_->valid(body_a)
      || !impl_->valid(body_b)
      || body_a.index == body_b.index) {
    return {{}, Multibody3DDiagnostic::InvalidBody};
  }
  if (!finite(body_a_anchor_local)
      || !finite(body_a_axis_local)
      || !finite(body_b_anchor_local)
      || !finite(body_b_axis_local)) {
    return {{}, Multibody3DDiagnostic::NonFiniteInput};
  }
  if (body_a_axis_local.norm() <= 1e-10
      || body_b_axis_local.norm() <= 1e-10) {
    std::fprintf(
        stderr,
        "[termin-qopt] 3D revolute joint has a rank-deficient axis\n"
    );
    return {{}, Multibody3DDiagnostic::InvalidJointAxis};
  }
  body_a_axis_local = body_a_axis_local.normalized();
  body_b_axis_local = body_b_axis_local.normalized();
  const termin::Vec3 initial_axis_a =
      impl_->bodies[body_a.index].state.pose.ang.rotate(
          body_a_axis_local
      );
  const termin::Vec3 initial_axis_b =
      impl_->bodies[body_b.index].state.pose.ang.rotate(
          body_b_axis_local
      );
  if (initial_axis_a.dot(initial_axis_b) < 0.0) {
    body_b_axis_local = -body_b_axis_local;
  }
  const auto registration =
      impl_->topology.register_constraint(5, diagnostic_name);
  if (!registration.ok()) {
    return {{}, Multibody3DDiagnostic::InvalidJoint};
  }
  try {
    const std::size_t index = impl_->joints.size();
    impl_->joints.push_back({
        Impl::RevoluteJoint{
            body_a.index,
            body_b.index,
            body_a_anchor_local,
            body_a_axis_local,
            body_b_anchor_local,
            body_b_axis_local,
        },
        registration.handle,
        {},
        {},
        std::string(diagnostic_name),
    });
    return {{impl_->id, index}, Multibody3DDiagnostic::None};
  } catch (const std::exception& error) {
    std::fprintf(
        stderr,
        "[termin-qopt] add 3D revolute joint failed: %s\n",
        error.what()
    );
  } catch (...) {
    std::fprintf(
        stderr,
        "[termin-qopt] add 3D revolute joint failed with unknown exception\n"
    );
  }
  return {{}, Multibody3DDiagnostic::InternalFailure};
}

Multibody3DDiagnostic Multibody3DSystem::finalize() noexcept {
  if (impl_ == nullptr) {
    return Multibody3DDiagnostic::InternalFailure;
  }
  if (impl_->finalized) {
    return Multibody3DDiagnostic::ModelFinalized;
  }
  if (impl_->bodies.empty()) {
    return Multibody3DDiagnostic::InvalidBody;
  }
  try {
    const std::size_t dofs = impl_->topology.dof_count();
    const std::size_t constraints = impl_->topology.constraint_count();
    std::vector<double> mass(dofs * dofs, 0.0);
    std::vector<double> load(dofs, 0.0);
    std::vector<double> jacobian(constraints * dofs, 0.0);
    std::vector<double> constraint_rhs(constraints, 0.0);
    std::vector<double> acceleration(dofs, 0.0);
    std::vector<double> reaction(constraints, 0.0);
    if (impl_->topology.finalize() != AssemblyDiagnostic::None) {
      return Multibody3DDiagnostic::AssemblyFailure;
    }
    impl_->mass = std::move(mass);
    impl_->load = std::move(load);
    impl_->jacobian = std::move(jacobian);
    impl_->constraint_rhs = std::move(constraint_rhs);
    impl_->acceleration = std::move(acceleration);
    impl_->reaction = std::move(reaction);
    impl_->finalized = true;
    return Multibody3DDiagnostic::None;
  } catch (const std::exception& error) {
    std::fprintf(
        stderr, "[termin-qopt] finalize 3D model failed: %s\n", error.what()
    );
  } catch (...) {
    std::fprintf(
        stderr, "[termin-qopt] finalize 3D model failed with unknown exception\n"
    );
  }
  return Multibody3DDiagnostic::InternalFailure;
}

bool Multibody3DSystem::finalized() const noexcept {
  return impl_ != nullptr && impl_->finalized;
}

std::size_t Multibody3DSystem::body_count() const noexcept {
  return impl_ == nullptr ? 0 : impl_->bodies.size();
}

std::size_t Multibody3DSystem::joint_count() const noexcept {
  return impl_ == nullptr ? 0 : impl_->joints.size();
}

Multibody3DDiagnostic Multibody3DSystem::set_body_state(
    RigidBody3DHandle body, RigidBody3DState state
) noexcept {
  if (impl_ == nullptr || !impl_->valid(body)) {
    return Multibody3DDiagnostic::InvalidBody;
  }
  if (!finite(state) || state.pose.ang.norm() <= 1e-10) {
    return Multibody3DDiagnostic::NonFiniteInput;
  }
  state.pose.ang = state.pose.ang.normalized();
  impl_->bodies[body.index].state = state;
  return Multibody3DDiagnostic::None;
}

Multibody3DDiagnostic Multibody3DSystem::set_body_wrench(
    RigidBody3DHandle body, RigidBody3DWrench wrench
) noexcept {
  if (impl_ == nullptr || !impl_->valid(body)) {
    return Multibody3DDiagnostic::InvalidBody;
  }
  if (!finite(wrench.force_world)
      || !finite(wrench.torque_about_origin_world)) {
    return Multibody3DDiagnostic::NonFiniteInput;
  }
  impl_->bodies[body.index].wrench = wrench;
  return Multibody3DDiagnostic::None;
}

RigidBody3DState Multibody3DSystem::body_state(
    RigidBody3DHandle body
) const noexcept {
  if (impl_ == nullptr || !impl_->valid(body)) {
    return {};
  }
  return impl_->bodies[body.index].state;
}

RigidBody3DAcceleration Multibody3DSystem::body_acceleration(
    RigidBody3DHandle body
) const noexcept {
  if (impl_ == nullptr || !impl_->valid(body)) {
    return {};
  }
  return impl_->bodies[body.index].acceleration;
}

termin::Vec3 Multibody3DSystem::joint_reaction(
    PointJoint3DHandle joint
) const noexcept {
  if (impl_ == nullptr || !impl_->valid(joint)) {
    return termin::Vec3::zero();
  }
  return impl_->joints[joint.index].force_reaction;
}

RevoluteJoint3DReaction Multibody3DSystem::revolute_joint_reaction(
    RevoluteJoint3DHandle joint
) const noexcept {
  if (impl_ == nullptr || !impl_->valid(joint)) {
    return {};
  }
  return {
      impl_->joints[joint.index].force_reaction,
      impl_->joints[joint.index].torque_reaction,
  };
}

Multibody3DStepResult Multibody3DSystem::step(
    termin::Vec3 gravity_world, Multibody3DStepOptions options
) noexcept {
  if (impl_ == nullptr || !impl_->finalized) {
    return failure(
        QpStatus::InvalidInput, Multibody3DDiagnostic::ModelNotFinalized
    );
  }
  if (!finite(gravity_world)) {
    return failure(
        QpStatus::InvalidInput, Multibody3DDiagnostic::NonFiniteInput
    );
  }
  if (!finite(options.time_step) || options.time_step <= 0.0) {
    return failure(
        QpStatus::InvalidInput, Multibody3DDiagnostic::InvalidTimeStep
    );
  }
  if (!finite(options.position_tolerance)
      || !finite(options.velocity_tolerance)
      || options.position_tolerance < 0.0
      || options.velocity_tolerance < 0.0
      || (!impl_->joints.empty()
          && options.max_position_iterations == 0)) {
    return failure(
        QpStatus::InvalidInput,
        Multibody3DDiagnostic::InvalidProjectionOptions
    );
  }

  std::vector<Impl::Body> original_bodies;
  std::vector<Impl::Joint> original_joints;
  std::vector<double> original_acceleration;
  std::vector<double> original_reaction;
  bool snapshot_ready = false;
  const auto restore = [&]() noexcept {
    if (!snapshot_ready) {
      return;
    }
    impl_->bodies = std::move(original_bodies);
    impl_->joints = std::move(original_joints);
    impl_->acceleration = std::move(original_acceleration);
    impl_->reaction = std::move(original_reaction);
    snapshot_ready = false;
  };

  try {
    original_bodies = impl_->bodies;
    original_joints = impl_->joints;
    original_acceleration = impl_->acceleration;
    original_reaction = impl_->reaction;
    snapshot_ready = true;

    DynamicsAssembly assembly(
        impl_->topology,
        {
            DenseMatrixView::row_major(
                impl_->mass.data(),
                impl_->topology.dof_count(),
                impl_->topology.dof_count()
            ),
            {impl_->load.data(), impl_->load.size(), 1},
            DenseMatrixView::row_major(
                impl_->jacobian.data(),
                impl_->topology.constraint_count(),
                impl_->topology.dof_count()
            ),
            {
                impl_->constraint_rhs.data(),
                impl_->constraint_rhs.size(),
                1,
            },
        }
    );
    if (!assembly.valid()
        || impl_->assemble(assembly, gravity_world)
            != AssemblyDiagnostic::None) {
      restore();
      return failure(
          QpStatus::InvalidInput, Multibody3DDiagnostic::AssemblyFailure
      );
    }

    const QpSolveResult dynamics = solve_constrained_dynamics(
        assembly.system(),
        {
            {
                impl_->acceleration.data(),
                impl_->acceleration.size(),
                1,
            },
            {impl_->reaction.data(), impl_->reaction.size(), 1},
        },
        options.qp_tolerance
    );
    if (dynamics.status != QpStatus::Optimal) {
      restore();
      return failure(
          dynamics.status,
          Multibody3DDiagnostic::DynamicsFailure,
          dynamics
      );
    }

    for (Impl::Body& body : impl_->bodies) {
      const DenseBlockInfo info =
          impl_->topology.dof_topology().block_info(body.dofs.block);
      body.acceleration.linear_world = {
          impl_->acceleration[info.offset],
          impl_->acceleration[info.offset + 1],
          impl_->acceleration[info.offset + 2],
      };
      body.acceleration.angular_world = {
          impl_->acceleration[info.offset + 3],
          impl_->acceleration[info.offset + 4],
          impl_->acceleration[info.offset + 5],
      };
      body.state.linear_velocity_world +=
          body.acceleration.linear_world * options.time_step;
      body.state.angular_velocity_world +=
          body.acceleration.angular_world * options.time_step;
      body.state.pose.lin +=
          body.state.linear_velocity_world * options.time_step;
      body.state.pose.ang =
          (
              rotation_vector_quaternion(
                  body.state.angular_velocity_world * options.time_step
              )
              * body.state.pose.ang
          )
              .normalized();
    }
    for (Impl::Joint& joint : impl_->joints) {
      const DenseBlockInfo info =
          impl_->topology.constraint_topology().block_info(
              joint.constraint.block
          );
      joint.force_reaction = {
          impl_->reaction[info.offset],
          impl_->reaction[info.offset + 1],
          impl_->reaction[info.offset + 2],
      };
      joint.torque_reaction = termin::Vec3::zero();
      std::size_t body_index = impl_->bodies.size();
      if (const auto* fixed =
              std::get_if<Impl::FixedRevoluteJoint>(&joint.model)) {
        body_index = fixed->body;
      } else if (
          const auto* revolute =
              std::get_if<Impl::RevoluteJoint>(&joint.model)
      ) {
        body_index = revolute->body_a;
      }
      if (body_index < impl_->bodies.size()) {
        const DenseBlockInfo body_info =
            impl_->topology.dof_topology().block_info(
                impl_->bodies[body_index].dofs.block
            );
        const std::size_t dofs = impl_->topology.dof_count();
        for (std::size_t axis = 0; axis < 3; ++axis) {
          for (std::size_t row = 3; row < 5; ++row) {
            joint.torque_reaction[static_cast<int>(axis)] +=
                impl_->jacobian[
                    (info.offset + row) * dofs
                    + body_info.offset + 3 + axis
                ]
                * impl_->reaction[info.offset + row];
          }
        }
      }
    }

    Multibody3DStepResult result;
    result.status = QpStatus::Optimal;
    result.diagnostic = Multibody3DDiagnostic::None;
    result.dynamics = dynamics;

    for (std::size_t iteration = 0;
         iteration < options.max_position_iterations;
         ++iteration) {
      result.position_constraint_linf = impl_->max_position_error();
      if (result.position_constraint_linf <= options.position_tolerance) {
        break;
      }
      if (impl_->assemble(assembly, gravity_world)
          != AssemblyDiagnostic::None) {
        restore();
        return failure(
            QpStatus::InvalidInput,
            Multibody3DDiagnostic::AssemblyFailure,
            dynamics
        );
      }
      const QpSolveResult projection =
          impl_->project_positions(assembly, options.qp_tolerance);
      ++result.position_iterations;
      if (projection.status != QpStatus::Optimal) {
        restore();
        return failure(
            projection.status,
            Multibody3DDiagnostic::PositionProjectionFailure,
            dynamics
        );
      }
    }
    result.position_constraint_linf = impl_->max_position_error();
    if (result.position_constraint_linf > options.position_tolerance) {
      restore();
      return failure(
          QpStatus::NumericalFailure,
          Multibody3DDiagnostic::PositionProjectionFailure,
          dynamics
      );
    }

    if (!impl_->joints.empty()) {
      if (impl_->assemble(assembly, gravity_world)
          != AssemblyDiagnostic::None) {
        restore();
        return failure(
            QpStatus::InvalidInput,
            Multibody3DDiagnostic::AssemblyFailure,
            dynamics
        );
      }
      const QpSolveResult velocity_projection =
          impl_->project_velocities(assembly, options.qp_tolerance);
      if (velocity_projection.status != QpStatus::Optimal) {
        restore();
        return failure(
            velocity_projection.status,
            Multibody3DDiagnostic::VelocityProjectionFailure,
            dynamics
        );
      }
    }
    result.velocity_constraint_linf = impl_->max_velocity_error();
    if (result.velocity_constraint_linf > options.velocity_tolerance) {
      restore();
      return failure(
          QpStatus::NumericalFailure,
          Multibody3DDiagnostic::VelocityProjectionFailure,
          dynamics
      );
    }
    snapshot_ready = false;
    return result;
  } catch (const std::exception& error) {
    std::fprintf(
        stderr, "[termin-qopt] 3D model step failed: %s\n", error.what()
    );
  } catch (...) {
    std::fprintf(
        stderr, "[termin-qopt] 3D model step failed with unknown exception\n"
    );
  }
  restore();
  return failure(
      QpStatus::NumericalFailure, Multibody3DDiagnostic::InternalFailure
  );
}

double Multibody3DSystem::max_position_constraint_error() const noexcept {
  return impl_ == nullptr ? 0.0 : impl_->max_position_error();
}

double Multibody3DSystem::max_velocity_constraint_error() const noexcept {
  return impl_ == nullptr ? 0.0 : impl_->max_velocity_error();
}

double Multibody3DSystem::total_energy(
    termin::Vec3 gravity_world
) const noexcept {
  if (impl_ == nullptr || !finite(gravity_world)) {
    return std::numeric_limits<double>::quiet_NaN();
  }
  double energy = 0.0;
  for (const Impl::Body& body : impl_->bodies) {
    const Matrix6 inertia = impl_->body_mass(body);
    const std::array<double, 6> velocity{
        body.state.linear_velocity_world.x,
        body.state.linear_velocity_world.y,
        body.state.linear_velocity_world.z,
        body.state.angular_velocity_world.x,
        body.state.angular_velocity_world.y,
        body.state.angular_velocity_world.z,
    };
    double kinetic = 0.0;
    for (std::size_t row = 0; row < 6; ++row) {
      for (std::size_t column = 0; column < 6; ++column) {
        kinetic += 0.5
            * velocity[row]
            * inertia[row * 6 + column]
            * velocity[column];
      }
    }
    const termin::Vec3 center_position =
        body.state.pose.transform_point(
            body.inertia.inertia_frame_local.lin
        );
    energy += kinetic
        - body.inertia.mass * gravity_world.dot(center_position);
  }
  return energy;
}

} // namespace termin::qopt
