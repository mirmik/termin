#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include <termin/entity/component.hpp>
#include <termin/physics_qopt/articulation3d_motor.hpp>
#include <termin/physics_qopt/contact3d.hpp>
#include <termin/physics_qopt/multibody3d.hpp>
#include <termin/render/render_lifecycle.hpp>
#include <termin/robotics/articulation3d.hpp>
#include <termin/robotics/inverse_dynamics_control.hpp>

extern "C" {
#include <tc_types.h>
}

namespace termin {

    class FEMPhysicsWorldComponent;
    class FEMRigidBodyComponent;
    class KinematicUnitComponent;
    class ArticulationComponent;
    class FEMArticulationMotorComponent;
    class FEMJointLimitComponent;
    class FEMJointServoComponent;

    enum class FEMArticulationBaseMode : int {
        Fixed = 0,
        Floating = 1,
    };

    struct FEMPhysicsTelemetry {
        bool initialized = false;
        double simulated_time = 0.0;
        std::uint64_t successful_steps = 0;
        std::size_t body_count = 0;
        std::size_t joint_count = 0;
        std::size_t articulation_count = 0;
        std::size_t reduced_dof_count = 0;
        std::size_t motor_count = 0;
        std::size_t saturated_motor_count = 0;
        std::size_t contact_count = 0;
        std::size_t active_contact_count = 0;
        std::size_t sliding_contact_count = 0;
        std::size_t cached_contact_count = 0;
        std::size_t warm_started_contact_count = 0;
        double minimum_contact_gap = 0.0;
        double normal_impulse_sum = 0.0;
        double normal_reaction_sum = 0.0;
        double normal_reaction_linf = 0.0;
        double tangent_impulse_sum = 0.0;
        double tangent_speed_linf = 0.0;
        double friction_capacity_sum = 0.0;
        double friction_work = 0.0;
        double motor_effort_linf = 0.0;
        double motor_power = 0.0;
        double motor_work = 0.0;
        double initial_total_energy = 0.0;
        double total_energy = 0.0;
    };

    class ENTITY_API FEMArticulationComponent final : public CxxComponent {
    public:
        int base_mode = static_cast<int>(FEMArticulationBaseMode::Fixed);

        FEMArticulationComponent();
        ~FEMArticulationComponent() override = default;

        static void register_type();
        void on_destroy() override;

        [[nodiscard]] bool initialized() const noexcept;
        [[nodiscard]] std::size_t unit_count() const noexcept;
        [[nodiscard]] double total_energy() const noexcept;
        [[nodiscard]] robotics::Articulation3D* articulation() noexcept;
        [[nodiscard]] const robotics::Articulation3D* articulation() const noexcept;
        [[nodiscard]] Vec3 gravity_world() const noexcept;
        [[nodiscard]] std::vector<std::size_t> actuator_dof_indices() const;
        [[nodiscard]] std::vector<double> actuator_effort_limits() const;
        [[nodiscard]] bool
        apply_inverse_dynamics_control(const robotics::InverseDynamicsControlResult3D& control) noexcept;

    private:
        friend class FEMPhysicsWorldComponent;
        // ArticulationComponent owns the target model. legacy_articulation_
        // exists only while old joint/body scenes are being migrated.
        ArticulationComponent* articulation_owner_ = nullptr;
        std::shared_ptr<robotics::Articulation3D> shared_articulation_;
        std::unique_ptr<robotics::Articulation3D> legacy_articulation_;
        robotics::Articulation3D* articulation_ = nullptr;
        physics_qopt::Articulation3DDynamicsContribution* dynamics_ = nullptr;
        FEMPhysicsWorldComponent* world_ = nullptr;
        FEMRigidBodyComponent* base_body_ = nullptr;
        std::vector<FEMRigidBodyComponent*> bodies_;
        std::vector<Entity> joint_entities_;
        std::vector<double> joint_coordinate_scales_;
        physics_qopt::ArticulationMotorContribution* motor_ = nullptr;
        std::vector<FEMArticulationMotorComponent*> motors_;
        std::vector<FEMJointServoComponent*> servos_;
    };

    // A bounded physical effort channel for one reduced articulation DOF. It
    // may be commanded directly or by a separate controller component.
    class ENTITY_API FEMArticulationMotorComponent final : public CxxComponent {
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
        physics_qopt::Articulation3DDynamicsContribution* articulation_ = nullptr;
        physics_qopt::ArticulationMotorContribution* motor_ = nullptr;
        std::size_t dof_index_ = 0;
        std::size_t joint_index_ = 0;
        std::size_t channel_index_ = 0;
    };

    // Optional physical bounds for the reduced DOF authored by the
    // co-located RotatorComponent or ActuatorComponent. Coordinates use the
    // kinematic component's authored units and are converted by its explicit
    // coordinate_scale when the articulation is compiled.
    class ENTITY_API FEMJointLimitComponent final : public CxxComponent {
    public:
        bool minimum_enabled = false;
        bool maximum_enabled = false;
        double minimum_coordinate = 0.0;
        double maximum_coordinate = 0.0;

        FEMJointLimitComponent();
        ~FEMJointLimitComponent() override = default;

        static void register_type();
    };

    // A PID control policy for a co-located articulation motor. Target state is
    // expressed in the neighboring kinematic component's authored units.
    class ENTITY_API FEMJointServoComponent final : public CxxComponent {
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
        [[nodiscard]] double position_effort() const noexcept;
        [[nodiscard]] double velocity_effort() const noexcept;
        [[nodiscard]] double integral_effort() const noexcept;
        [[nodiscard]] double commanded_effort() const noexcept;

    private:
        friend class FEMPhysicsWorldComponent;
        FEMPhysicsWorldComponent* world_ = nullptr;
        KinematicUnitComponent* joint_ = nullptr;
        FEMArticulationMotorComponent* motor_component_ = nullptr;
        physics_qopt::Articulation3DDynamicsContribution* articulation_ = nullptr;
        std::size_t dof_index_ = 0;
        double coordinate_scale_ = 1.0;
        double position_effort_ = 0.0;
        double velocity_effort_ = 0.0;
        double integral_effort_ = 0.0;
        double commanded_effort_ = 0.0;
    };

    class ENTITY_API FEMRigidBodyComponent final : public CxxComponent {
    public:
        double mass = 1.0;
        tc_vec3 inertia_diagonal = {0.1, 0.1, 0.1};
        double linear_damping = 0.0;
        double angular_damping = 0.0;

        FEMRigidBodyComponent();
        ~FEMRigidBodyComponent() override = default;

        static void register_type();
        void on_destroy() override;

        [[nodiscard]] bool initialized() const noexcept;
        [[nodiscard]] Screw3 velocity_local() const noexcept;
        bool set_velocity_local(Screw3 velocity) noexcept;

    private:
        friend class FEMPhysicsWorldComponent;
        physics_qopt::RigidBody3DContribution* body_ = nullptr;
        physics_qopt::ForceOnBody3DContribution* force_ = nullptr;
        physics_qopt::Articulation3DDynamicsContribution* articulation_ = nullptr;
        std::size_t articulation_unit_index_ = robotics::articulation_root_frame;
        bool articulation_base_ = false;
        FEMPhysicsWorldComponent* world_ = nullptr;
    };

    class ENTITY_API FEMFixedJointComponent final : public CxxComponent, public RenderLifecycle {
    public:
        std::string body_entity_name;
        tc_vec3 joint_axis_in_body = {0.0, 1.0, 0.0};
        double damping = 0.0;

        FEMFixedJointComponent();
        ~FEMFixedJointComponent() override = default;

        static void register_type();
        void on_destroy() override;
        void prepare_render(const RenderPrepareContext& context) override;

    private:
        friend class FEMPhysicsWorldComponent;
        physics_qopt::FixedRevoluteJoint3DContribution* joint_ = nullptr;
        physics_qopt::RigidBody3DContribution* body_ = nullptr;
        FEMPhysicsWorldComponent* world_ = nullptr;
    };

    class ENTITY_API FEMRevoluteJointComponent final : public CxxComponent, public RenderLifecycle {
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
        void prepare_render(const RenderPrepareContext& context) override;

    private:
        friend class FEMPhysicsWorldComponent;
        physics_qopt::RevoluteJoint3DContribution* joint_ = nullptr;
        physics_qopt::RigidBody3DContribution* body_a_ = nullptr;
        physics_qopt::RigidBody3DContribution* body_b_ = nullptr;
        FEMPhysicsWorldComponent* world_ = nullptr;
    };

    class ENTITY_API FEMPhysicsWorldComponent final : public CxxComponent {
    public:
        tc_vec3 gravity = {0.0, 0.0, -9.81};
        // Default remains frictionless for scene compatibility. This is the
        // combined coefficient assigned to every generated contact; collider
        // material mixing can replace this policy later without changing qopt.
        double contact_friction_coefficient = 0.0;
        // Even-sided inscribed approximation of each Coulomb friction disk.
        int contact_friction_cone_facets = 6;
        std::uint64_t collision_layer_mask = ~std::uint64_t{0};
        bool adjacent_unit_collision_enabled = false;

        FEMPhysicsWorldComponent();
        ~FEMPhysicsWorldComponent() override = default;

        static void register_type();

        void start() override;
        void fixed_update(float dt) override;
        void on_destroy() override;

        [[nodiscard]] FEMPhysicsTelemetry telemetry() const noexcept;

    private:
        struct ContactRefreshState;

        friend class FEMArticulationComponent;
        friend class FEMArticulationMotorComponent;
        friend class FEMJointServoComponent;
        friend class FEMRigidBodyComponent;
        friend class FEMFixedJointComponent;
        friend class FEMRevoluteJointComponent;
        physics_qopt::Multibody3DSystem system_;
        std::vector<FEMRigidBodyComponent*> bodies_;
        std::vector<FEMFixedJointComponent*> fixed_joints_;
        std::vector<FEMRevoluteJointComponent*> revolute_joints_;
        std::vector<FEMArticulationComponent*> articulations_;
        physics_qopt::ContactSet3DContribution* contacts_ = nullptr;
        std::vector<const void*> warned_contact_colliders_;
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
        bool collect_contact_endpoints(const TcSceneRef& scene, ContactRefreshState& state);
        void warn_contact_collider_once(const void* collider, const char* message, const char* entity_name);
        bool refresh_contacts();
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
