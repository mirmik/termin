#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include <termin/physics_qopt/dynamics.hpp>
#include <termin/physics_qopt/point_kinematics3d.hpp>
#include <termin/physics_qopt/termin_physics_qopt_api.hpp>
#include <termin/robotics/articulation3d.hpp>

namespace termin::physics_qopt
{
    struct ArticulationUnitLimitState3D
    {
        double minimum_reaction = 0.0;
        double maximum_reaction = 0.0;
        bool minimum_active = false;
        bool maximum_active = false;

        [[nodiscard]] constexpr double signed_effort() const noexcept
        {
            return minimum_reaction - maximum_reaction;
        }
    };

    struct ArticulationDynamicsAssemblyCounters
    {
        std::size_t mass_matrix_evaluations = 0;
        std::size_t bias_evaluations = 0;
    };

    // Dynamic adapter for a reduced fixed- or floating-base robotics tree.
    // Internal joints are satisfied by construction. The adapter borrows the
    // Articulation3D and adds only physical-solver state and equations.
    class TERMIN_PHYSICS_QOPT_API Articulation3DDynamicsContribution final
        : public DynamicsContribution
    {
    public:
        Articulation3DDynamicsContribution(
            robotics::Articulation3D& articulation,
            termin::Vec3 gravity_world = termin::Vec3::zero(),
            std::string_view diagnostic_name = {});

        [[nodiscard]] robotics::Articulation3D& articulation() noexcept;
        [[nodiscard]] const robotics::Articulation3D&
        articulation() const noexcept;
        [[nodiscard]] robotics::Articulation3DDiagnostic
        diagnostic() const noexcept;
        [[nodiscard]] std::size_t unit_count() const noexcept;
        [[nodiscard]] std::size_t dof_count() const noexcept;
        [[nodiscard]] const std::vector<robotics::ArticulationUnit3D>&
        units() const noexcept;
        [[nodiscard]] const robotics::Articulation3DState&
        state() const noexcept;
        [[nodiscard]] bool has_floating_base() const noexcept;
        [[nodiscard]] const std::optional<robotics::ArticulationFloatingBase3D>&
        floating_base() const noexcept;
        [[nodiscard]] const std::vector<double>& accelerations() const noexcept;
        [[nodiscard]] const std::vector<termin::Pose3>&
        unit_poses_world() const noexcept;
        [[nodiscard]] const std::vector<termin::Screw3>&
        unit_velocities_local() const noexcept;
        [[nodiscard]] const std::vector<ArticulationUnitLimitState3D>&
        unit_limit_states() const noexcept;
        [[nodiscard]] DynamicsDofHandle dofs() const noexcept;
        [[nodiscard]] termin::Vec3 gravity_world() const noexcept;
        [[nodiscard]] ArticulationDynamicsAssemblyCounters
        assembly_counters() const noexcept;
        void reset_assembly_counters() noexcept;
        [[nodiscard]] PointKinematics3DResult
        point_kinematics(std::size_t unit_index,
                         termin::Vec3 point_local) const noexcept;
        [[nodiscard]] PointKinematics3DResult
        floating_base_point_kinematics(termin::Vec3 point_local) const noexcept;

        [[nodiscard]] robotics::Articulation3DDiagnostic
        set_state(robotics::Articulation3DState state) noexcept;
        [[nodiscard]] robotics::Articulation3DDiagnostic
        set_floating_base_state(termin::Pose3 pose_world,
                                termin::Screw3 velocity_local) noexcept;
        [[nodiscard]] robotics::Articulation3DDiagnostic
        set_gravity_world(termin::Vec3 gravity) noexcept;
        [[nodiscard]] double total_energy() const noexcept;

        AssemblyDiagnostic
        register_topology(DynamicsTopology& topology) noexcept override;
        AssemblyDiagnostic
        register_unilateral_constraints(DynamicsUnilateralTopology& topology,
                                        double time_step) noexcept override;
        AssemblyDiagnostic
        assemble(DynamicsAssembly& assembly,
                 DynamicsAssemblyPhase phase) noexcept override;
        AssemblyDiagnostic begin_step() noexcept override;
        void commit_step() noexcept override;
        void rollback_step() noexcept override;
        void apply_solution(
            DynamicsAssemblyPhase phase,
            const DynamicsTopology& topology,
            ConstDenseVectorView dof_values,
            ConstDenseVectorView constraint_reactions) noexcept override;
        void apply_unilateral_solution(
            const DynamicsTopology& topology,
            const DynamicsUnilateralTopology& unilateral_topology,
            ConstDenseVectorView reactions,
            ConstDenseVectorView tight_mask) noexcept override;
        AssemblyDiagnostic
        write_velocity(const DynamicsTopology& topology,
                       DenseVectorView destination) const noexcept override;
        AssemblyDiagnostic
        set_velocity(const DynamicsTopology& topology,
                     ConstDenseVectorView velocity) noexcept override;
        AssemblyDiagnostic
        set_trial_configuration(const DynamicsTopology& topology,
                                ConstDenseVectorView midpoint_velocity,
                                double time_step) noexcept override;
        AssemblyDiagnostic write_corrected_midpoint_velocity(
            const DynamicsTopology& topology,
            ConstDenseVectorView midpoint_velocity,
            ConstDenseVectorView trial_tangent_correction,
            double time_step,
            DenseVectorView destination) const noexcept override;

    private:
        robotics::Articulation3D& articulation_;
        std::vector<double> accelerations_;
        termin::Vec3 gravity_world_;
        std::string diagnostic_name_;
        DynamicsDofHandle dofs_;
        robotics::Articulation3DDiagnostic diagnostic_ =
            robotics::Articulation3DDiagnostic::None;

        struct UnitLimitRows
        {
            DynamicsUnilateralConstraintHandle minimum;
            DynamicsUnilateralConstraintHandle maximum;
        };

        std::vector<UnitLimitRows> unit_limit_rows_;
        std::vector<ArticulationUnitLimitState3D> unit_limit_states_;
        double unilateral_time_step_ = 0.0;

        std::vector<double> mass_matrix_cache_;
        std::vector<double> bias_work_;
        std::vector<double> load_work_;
        std::vector<double> generalized_velocity_work_;
        std::vector<double> limit_row_work_;
        std::vector<double> zero_acceleration_work_;
        ArticulationDynamicsAssemblyCounters assembly_counters_;
        bool mass_matrix_cache_valid_ = false;

        robotics::Articulation3DState state_snapshot_;
        std::optional<robotics::ArticulationFloatingBase3D>
            floating_base_snapshot_;
        std::vector<double> acceleration_snapshot_;
        std::vector<ArticulationUnitLimitState3D> unit_limit_state_snapshot_;
        bool snapshot_ready_ = false;

        void invalidate_mass_matrix_cache() noexcept;
        [[nodiscard]] bool prepare_mass_matrix();
        [[nodiscard]] bool prepare_bias();
    };

} // namespace termin::physics_qopt
