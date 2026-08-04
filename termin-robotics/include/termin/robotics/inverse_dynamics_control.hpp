#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

#include <termin/qopt/hqp.hpp>
#include <termin/robotics/tasks.hpp>
#include <termin/robotics/termin_robotics_api.hpp>

namespace termin::robotics
{
    struct InverseDynamicsActuator3D
    {
        std::size_t dof_index = 0;
        std::optional<double> minimum_effort;
        std::optional<double> maximum_effort;
        std::string diagnostic_name;
    };

    // A solver-neutral block of unknown environmental forces. The row-major
    // generalized-force basis G maps block variables lambda to effort G*lambda.
    // Optional inequalities use C*lambda <= d and may express unilateral
    // bounds or a polyhedral friction cone without introducing physics types.
    struct InverseDynamicsForceVariableBlock3D
    {
        std::size_t variable_count = 0;
        std::vector<double> generalized_force_basis_storage;
        std::size_t inequality_row_count = 0;
        std::vector<double> inequality_matrix_storage;
        std::vector<double> inequality_target_storage;
        std::string diagnostic_name;
    };

    enum class InverseDynamicsControlDiagnostic3D : std::uint8_t
    {
        None,
        InvalidModel,
        InvalidTimeStep,
        InvalidGravity,
        InvalidActuator,
        DuplicateActuator,
        NullTask,
        TaskLinearizationFailure,
        UnsupportedDerivativeOrder,
        DimensionMismatch,
        NonFiniteInput,
        InvalidForceVariableBlock,
        DynamicsFailure,
        RegistrationFailure,
        SolveFailure,
        InternalFailure,
    };

    [[nodiscard]] TERMIN_ROBOTICS_API std::string_view
    inverse_dynamics_control_diagnostic_name(
        InverseDynamicsControlDiagnostic3D diagnostic) noexcept;

    struct InverseDynamicsControlOptions3D
    {
        double time_step = 1.0 / 60.0;
        // Known generalized effort applied by the environment, in the same
        // vw layout as Articulation3D. Empty means zero. Contact-force decision
        // layout. This value is for already known loads; unknown contact loads
        // belong in force_variable_blocks.
        std::vector<double> external_generalized_effort;
        std::vector<InverseDynamicsForceVariableBlock3D> force_variable_blocks;
        bool use_primal_warm_start = true;
        qopt::HqpOptions hqp;
    };

    struct TERMIN_ROBOTICS_API InverseDynamicsControlResult3D
    {
        std::vector<double> generalized_acceleration;
        // M*qdd + bias - known_external - G*lambda. Unactuated entries are
        // constrained to zero.
        std::vector<double> required_generalized_effort;
        std::vector<double> force_variable_values;
        // One offset per declared block, followed by the final total size.
        std::vector<std::size_t> force_variable_block_offsets;
        std::vector<double> force_variable_generalized_effort;
        // One entry per controller actuator, in actuator declaration order.
        std::vector<std::size_t> actuator_dofs;
        std::vector<double> actuator_effort;
        std::vector<int> level_priorities;
        std::vector<double> level_task_residual_l2;
        qopt::QpStatus status = qopt::QpStatus::InvalidInput;
        InverseDynamicsControlDiagnostic3D diagnostic =
            InverseDynamicsControlDiagnostic3D::None;
        TaskDiagnostic3D task_diagnostic = TaskDiagnostic3D::None;
        qopt::HqpDiagnostic hqp_diagnostic = qopt::HqpDiagnostic::None;
        qopt::HqpSolveResult hqp_result;
        std::size_t failed_task = std::numeric_limits<std::size_t>::max();
        std::string failed_task_name;
        std::size_t active_task_count = 0;
        double unactuated_residual_linf = 0.0;
        bool primal_warm_start_used = false;

        [[nodiscard]] bool ok() const noexcept;
    };

    // Solver-neutral inverse-dynamics formulation over generalized
    // acceleration. The default actuator set contains every scalar joint and
    // intentionally excludes the six floating-base DOFs.
    class TERMIN_ROBOTICS_API InverseDynamicsHqpController3D
    {
    public:
        explicit InverseDynamicsHqpController3D(
            Articulation3D& articulation,
            termin::Vec3 gravity_world = termin::Vec3::zero());
        InverseDynamicsHqpController3D(
            Articulation3D& articulation,
            std::vector<InverseDynamicsActuator3D> actuators,
            termin::Vec3 gravity_world = termin::Vec3::zero());

        [[nodiscard]] const std::vector<InverseDynamicsActuator3D>&
        actuators() const noexcept;
        [[nodiscard]] termin::Vec3 gravity_world() const noexcept;
        [[nodiscard]] InverseDynamicsControlDiagnostic3D
        set_gravity_world(termin::Vec3 gravity_world) noexcept;

        [[nodiscard]] InverseDynamicsControlResult3D
        solve(std::span<const ArticulationTask3D* const> tasks,
              InverseDynamicsControlOptions3D options = {}) noexcept;

        void reset_primal_warm_start() noexcept;
        [[nodiscard]] const std::vector<double>&
        primal_warm_start() const noexcept;

    private:
        Articulation3D* articulation_ = nullptr;
        std::vector<InverseDynamicsActuator3D> actuators_;
        termin::Vec3 gravity_world_ = termin::Vec3::zero();
        std::vector<double> primal_warm_start_;
        bool primal_warm_start_valid_ = false;
    };

} // namespace termin::robotics
