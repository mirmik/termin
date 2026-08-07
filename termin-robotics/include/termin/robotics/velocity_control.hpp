#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>
#include <span>
#include <string>
#include <string_view>
#include <vector>

#include <termin/qopt/hqp.hpp>
#include <termin/robotics/tasks.hpp>
#include <termin/robotics/termin_robotics_api.hpp>

namespace termin::robotics {

    enum class VelocityControlDiagnostic3D : std::uint8_t {
        None,
        InvalidModel,
        InvalidTimeStep,
        NullTask,
        TaskLinearizationFailure,
        UnsupportedDerivativeOrder,
        DimensionMismatch,
        NonFiniteInput,
        RegistrationFailure,
        SolveFailure,
        InternalFailure,
    };

    [[nodiscard]] TERMIN_ROBOTICS_API std::string_view
    velocity_control_diagnostic_name(VelocityControlDiagnostic3D diagnostic) noexcept;

    struct VelocityControlOptions3D {
        // The control interval used by predictive task linearizations.
        double time_step = 1.0 / 60.0;
        bool use_primal_warm_start = true;
        qopt::HqpOptions hqp;
    };

    struct TERMIN_ROBOTICS_API VelocityControlResult3D {
        std::vector<double> generalized_velocity;
        std::vector<int> level_priorities;
        std::vector<double> level_task_residual_l2;
        qopt::QpStatus status = qopt::QpStatus::InvalidInput;
        VelocityControlDiagnostic3D diagnostic = VelocityControlDiagnostic3D::None;
        TaskDiagnostic3D task_diagnostic = TaskDiagnostic3D::None;
        qopt::HqpDiagnostic hqp_diagnostic = qopt::HqpDiagnostic::None;
        qopt::HqpSolveResult hqp_result;
        std::size_t failed_task = std::numeric_limits<std::size_t>::max();
        std::string failed_task_name;
        std::size_t active_task_count = 0;
        bool primal_warm_start_used = false;

        [[nodiscard]] bool ok() const noexcept;
    };

    // Stateless task assembly around a borrowed articulation. The only state
    // retained between calls is the previous optimal primal solution, used as
    // an optional warm start. Solving never changes the articulation.
    class TERMIN_ROBOTICS_API VelocityHqpController3D {
    public:
        explicit VelocityHqpController3D(Articulation3D& articulation) noexcept;

        [[nodiscard]] VelocityControlResult3D solve(std::span<const ArticulationTask3D* const> tasks,
                                                    VelocityControlOptions3D options = {}) noexcept;

        void reset_primal_warm_start() noexcept;
        [[nodiscard]] const std::vector<double>& primal_warm_start() const noexcept;

    private:
        Articulation3D* articulation_ = nullptr;
        std::vector<double> primal_warm_start_;
        bool primal_warm_start_valid_ = false;
    };

    enum class VelocityIntegrationDiagnostic3D : std::uint8_t {
        None,
        InvalidModel,
        InvalidTimeStep,
        DimensionMismatch,
        NonFiniteVelocity,
        StateUpdateFailure,
        InternalFailure,
    };

    [[nodiscard]] TERMIN_ROBOTICS_API std::string_view
    velocity_integration_diagnostic_name(VelocityIntegrationDiagnostic3D diagnostic) noexcept;

    struct TERMIN_ROBOTICS_API VelocityIntegrationResult3D {
        VelocityIntegrationDiagnostic3D diagnostic = VelocityIntegrationDiagnostic3D::None;
        Articulation3DDiagnostic articulation_diagnostic = Articulation3DDiagnostic::None;

        [[nodiscard]] bool ok() const noexcept;
    };

    // Explicit Euler integration for scalar joints and right-trivialized SE(3)
    // integration for a floating base. No joint-limit clamping is performed;
    // limits belong to the optimization problem.
    [[nodiscard]] TERMIN_ROBOTICS_API VelocityIntegrationResult3D integrate_articulation_velocity(
        Articulation3D& articulation, qopt::ConstDenseVectorView generalized_velocity, double time_step) noexcept;

} // namespace termin::robotics
