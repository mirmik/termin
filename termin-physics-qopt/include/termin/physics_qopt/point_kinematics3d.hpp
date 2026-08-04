#pragma once

#include <cstddef>
#include <cstdint>
#include <string_view>
#include <vector>

#include <termin/geom/vec3.hpp>
#include <termin/physics_qopt/dynamics.hpp>
#include <termin/physics_qopt/termin_physics_qopt_api.hpp>

namespace termin::physics_qopt
{

    enum class PointKinematics3DDiagnostic : std::uint8_t
    {
        None,
        InvalidModel,
        InvalidUnit,
        NonFinitePoint,
        NonFiniteForce,
        InvalidOutput,
        InternalFailure,
    };

    [[nodiscard]] TERMIN_PHYSICS_QOPT_API std::string_view
    point_kinematics3d_diagnostic_name(
        PointKinematics3DDiagnostic diagnostic) noexcept;

    // Solver-facing kinematics of one material point. The Jacobian maps the
    // owner's local generalized velocity block to world linear velocity:
    //
    //     velocity_world = linear_jacobian_world * generalized_velocity
    //
    // Storage is row-major with three rows and dof_count() columns. A static
    // world point has zero columns and an invalid DOF handle by construction.
    struct TERMIN_PHYSICS_QOPT_API PointKinematics3D
    {
        termin::Vec3 position_world = termin::Vec3::zero();
        termin::Vec3 velocity_world = termin::Vec3::zero();
        DynamicsDofHandle dofs;
        std::vector<double> linear_jacobian_world_storage;

        [[nodiscard]] std::size_t dof_count() const noexcept;
        [[nodiscard]] bool is_static() const noexcept;
        [[nodiscard]] ConstDenseMatrixView
        linear_jacobian_world() const noexcept;

        // Overwrites generalized_effort with J^T * force_world.
        [[nodiscard]] PointKinematics3DDiagnostic
        map_force_to_generalized_effort(
            termin::Vec3 force_world,
            DenseVectorView generalized_effort) const noexcept;
    };

    struct TERMIN_PHYSICS_QOPT_API PointKinematics3DResult
    {
        PointKinematics3D value;
        PointKinematics3DDiagnostic diagnostic =
            PointKinematics3DDiagnostic::None;

        [[nodiscard]] bool ok() const noexcept;
    };

    // A fixed material point in the inertial world frame. It participates in
    // the same endpoint contract as dynamic points but owns no generalized
    // coordinates.
    [[nodiscard]] TERMIN_PHYSICS_QOPT_API PointKinematics3DResult
    static_point_kinematics(termin::Vec3 position_world) noexcept;

} // namespace termin::physics_qopt
