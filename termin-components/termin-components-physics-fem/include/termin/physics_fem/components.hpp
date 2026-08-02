#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include <termin/entity/component.hpp>
#include <termin/qopt/multibody3d.hpp>

extern "C"
{
#include <tc_types.h>
}

namespace termin
{

    class FEMPhysicsWorldComponent;

    struct FEMPhysicsTelemetry
    {
        bool initialized = false;
        double simulated_time = 0.0;
        std::uint64_t successful_steps = 0;
        std::size_t body_count = 0;
        std::size_t joint_count = 0;
        double initial_total_energy = 0.0;
        double total_energy = 0.0;
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
        // Retained in the serialized contract. Native constrained integration
        // does not use the legacy global velocity-rescaling energy correction.
        bool energy_stabilization = true;
        bool strict_energy_mode = false;

        FEMPhysicsWorldComponent();
        ~FEMPhysicsWorldComponent() override = default;

        static void register_type();

        void start() override;
        void update(float dt) override;
        void on_destroy() override;

        [[nodiscard]] FEMPhysicsTelemetry telemetry() const noexcept;

    private:
        qopt::Multibody3DSystem system_;
        std::vector<FEMRigidBodyComponent*> bodies_;
        std::vector<FEMFixedJointComponent*> fixed_joints_;
        std::vector<FEMRevoluteJointComponent*> revolute_joints_;
        double accumulated_time_ = 0.0;
        double simulated_time_ = 0.0;
        double initial_total_energy_ = 0.0;
        std::uint64_t successful_steps_ = 0;
        bool initialized_ = false;

        bool rebuild_simulation();
        bool register_body(FEMRigidBodyComponent& component);
        bool register_fixed_joint(FEMFixedJointComponent& component);
        bool register_revolute_joint(FEMRevoluteJointComponent& component);
        void step_simulation(double dt);
        [[nodiscard]] double total_energy() const noexcept;
        void clear_runtime_links();
    };

} // namespace termin
