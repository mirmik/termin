#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include <termin/entity/component.hpp>
#include <termin/qopt/articulation3d.hpp>
#include <termin/qopt/articulation3d_motor.hpp>
#include <termin/qopt/multibody3d.hpp>

extern "C"
{
#include <tc_types.h>
}

namespace termin
{

    class FEMPhysicsWorldComponent;
    class FEMRigidBodyComponent;
    class KinematicUnitComponent;
    class FEMArticulationMotorComponent;
    class FEMJointServoComponent;

    struct FEMPhysicsTelemetry
    {
        bool initialized = false;
        double simulated_time = 0.0;
        std::uint64_t successful_steps = 0;
        std::size_t body_count = 0;
        std::size_t joint_count = 0;
        std::size_t articulation_count = 0;
        std::size_t reduced_dof_count = 0;
        std::size_t motor_count = 0;
        std::size_t saturated_motor_count = 0;
        double motor_effort_linf = 0.0;
        double motor_power = 0.0;
        double motor_work = 0.0;
        double initial_total_energy = 0.0;
        double total_energy = 0.0;
    };

    class ENTITY_API FEMArticulationComponent final : public CxxComponent
    {
    public:
        FEMArticulationComponent();
        ~FEMArticulationComponent() override = default;

        static void register_type();
        void on_destroy() override;

        [[nodiscard]] bool initialized() const noexcept;
        [[nodiscard]] std::size_t link_count() const noexcept;
        [[nodiscard]] double total_energy() const noexcept;

    private:
        friend class FEMPhysicsWorldComponent;
        qopt::Articulation3DContribution* articulation_ = nullptr;
        FEMPhysicsWorldComponent* world_ = nullptr;
        std::vector<FEMRigidBodyComponent*> bodies_;
        std::vector<Entity> joint_entities_;
        std::vector<double> joint_coordinate_scales_;
        qopt::ArticulationMotorContribution* motor_ = nullptr;
        std::vector<FEMArticulationMotorComponent*> motors_;
        std::vector<FEMJointServoComponent*> servos_;
    };

    // A bounded physical effort channel for one reduced articulation DOF. It
    // may be commanded directly or by a separate controller component.
    class ENTITY_API FEMArticulationMotorComponent final : public CxxComponent
    {
    public:
        double commanded_effort = 0.0;
        double maximum_effort = 10.0;

        FEMArticulationMotorComponent();
        ~FEMArticulationMotorComponent() override = default;

        static void register_type();
        void on_destroy() override;

        [[nodiscard]] bool initialized() const noexcept;
        [[nodiscard]] double applied_effort() const noexcept;
        [[nodiscard]] double power() const noexcept;
        [[nodiscard]] bool saturated() const noexcept;

    private:
        friend class FEMPhysicsWorldComponent;
        FEMPhysicsWorldComponent* world_ = nullptr;
        qopt::Articulation3DContribution* articulation_ = nullptr;
        qopt::ArticulationMotorContribution* motor_ = nullptr;
        std::size_t dof_index_ = 0;
        std::size_t channel_index_ = 0;
    };

    // A PID control policy for a co-located articulation motor. Target state is
    // expressed in the neighboring kinematic component's authored units.
    class ENTITY_API FEMJointServoComponent final : public CxxComponent
    {
    public:
        bool position_control_enabled = true;
        bool integral_control_enabled = false;
        double target_coordinate = 0.0;
        double target_velocity = 0.0;
        double position_gain = 10.0;
        double integral_gain = 0.0;
        double maximum_integral_effort = 10.0;
        double velocity_gain = 1.0;
        double feed_forward_effort = 0.0;

        FEMJointServoComponent();
        ~FEMJointServoComponent() override = default;

        static void register_type();
        void on_destroy() override;

        [[nodiscard]] bool initialized() const noexcept;
        [[nodiscard]] double position_error() const noexcept;
        [[nodiscard]] double integral_effort() const noexcept;
        [[nodiscard]] double commanded_effort() const noexcept;

    private:
        friend class FEMPhysicsWorldComponent;
        FEMPhysicsWorldComponent* world_ = nullptr;
        KinematicUnitComponent* joint_ = nullptr;
        FEMArticulationMotorComponent* motor_component_ = nullptr;
        qopt::Articulation3DContribution* articulation_ = nullptr;
        std::size_t dof_index_ = 0;
        double coordinate_scale_ = 1.0;
        double integral_effort_ = 0.0;
        double commanded_effort_ = 0.0;
    };

    class ENTITY_API FEMRigidBodyComponent final : public CxxComponent
    {
    public:
        double mass = 1.0;
        tc_vec3 inertia_diagonal = {0.1, 0.1, 0.1};
        double linear_damping = 0.0;
        double angular_damping = 0.0;

        FEMRigidBodyComponent();
        ~FEMRigidBodyComponent() override = default;

        static void register_type();
        void on_destroy() override;

    private:
        friend class FEMPhysicsWorldComponent;
        qopt::RigidBody3DContribution* body_ = nullptr;
        qopt::ForceOnBody3DContribution* force_ = nullptr;
        FEMPhysicsWorldComponent* world_ = nullptr;
    };

    class ENTITY_API FEMFixedJointComponent final : public CxxComponent
    {
    public:
        std::string body_entity_name;
        tc_vec3 joint_axis_in_body = {0.0, 1.0, 0.0};
        double damping = 0.0;

        FEMFixedJointComponent();
        ~FEMFixedJointComponent() override = default;

        static void register_type();
        void on_destroy() override;

    private:
        friend class FEMPhysicsWorldComponent;
        qopt::FixedRevoluteJoint3DContribution* joint_ = nullptr;
        qopt::RigidBody3DContribution* body_ = nullptr;
        FEMPhysicsWorldComponent* world_ = nullptr;
    };

    class ENTITY_API FEMRevoluteJointComponent final : public CxxComponent
    {
    public:
        std::string body_a_entity_name;
        std::string body_b_entity_name;
        tc_vec3 joint_offset_in_body_a = {0.0, 0.0, 0.0};
        tc_vec3 joint_axis_in_body_a = {0.0, 1.0, 0.0};
        double damping = 0.0;

        FEMRevoluteJointComponent();
        ~FEMRevoluteJointComponent() override = default;

        static void register_type();
        void on_destroy() override;

    private:
        friend class FEMPhysicsWorldComponent;
        qopt::RevoluteJoint3DContribution* joint_ = nullptr;
        qopt::RigidBody3DContribution* body_a_ = nullptr;
        qopt::RigidBody3DContribution* body_b_ = nullptr;
        FEMPhysicsWorldComponent* world_ = nullptr;
    };

    class ENTITY_API FEMPhysicsWorldComponent final : public CxxComponent
    {
    public:
        tc_vec3 gravity = {0.0, 0.0, -9.81};
        double time_step = 0.01;
        int substeps = 1;

        FEMPhysicsWorldComponent();
        ~FEMPhysicsWorldComponent() override = default;

        static void register_type();

        void start() override;
        void update(float dt) override;
        void on_destroy() override;

        [[nodiscard]] FEMPhysicsTelemetry telemetry() const noexcept;

    private:
        friend class FEMArticulationComponent;
        friend class FEMArticulationMotorComponent;
        friend class FEMJointServoComponent;
        friend class FEMRigidBodyComponent;
        friend class FEMFixedJointComponent;
        friend class FEMRevoluteJointComponent;
        qopt::Multibody3DSystem system_;
        std::vector<FEMRigidBodyComponent*> bodies_;
        std::vector<FEMFixedJointComponent*> fixed_joints_;
        std::vector<FEMRevoluteJointComponent*> revolute_joints_;
        std::vector<FEMArticulationComponent*> articulations_;
        double accumulated_time_ = 0.0;
        double simulated_time_ = 0.0;
        double initial_total_energy_ = 0.0;
        double motor_work_ = 0.0;
        std::uint64_t successful_steps_ = 0;
        bool initialized_ = false;

        bool rebuild_simulation();
        bool register_body(FEMRigidBodyComponent& component);
        bool register_fixed_joint(FEMFixedJointComponent& component);
        bool register_revolute_joint(FEMRevoluteJointComponent& component);
        bool register_articulation(FEMArticulationComponent& component);
        void synchronize_articulations();
        bool update_motor_commands(double dt);
        void step_simulation(double dt);
        [[nodiscard]] double total_energy() const noexcept;
        void clear_runtime_links();
        void detach(FEMArticulationComponent& component) noexcept;
        void detach(FEMArticulationMotorComponent& component) noexcept;
        void detach(FEMJointServoComponent& component) noexcept;
        void detach(FEMRigidBodyComponent& component) noexcept;
        void detach(FEMFixedJointComponent& component) noexcept;
        void detach(FEMRevoluteJointComponent& component) noexcept;
    };

} // namespace termin
