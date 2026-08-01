#include <termin/physics_fem/components.hpp>

#include <algorithm>
#include <cmath>
#include <string_view>

#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/geom/general_transform3.hpp>
#include <termin/tc_scene.hpp>

namespace termin
{
    namespace
    {

        constexpr const char* module_owner = "termin-components-physics-fem";

        Vec3 vec3(tc_vec3 value)
        {
            return {value.x, value.y, value.z};
        }

        tc_vec3 tcvec3(Vec3 value)
        {
            return {value.x, value.y, value.z};
        }

        template <typename Component>
        void stage_double(tc::InspectFacetBuilder& inspect,
                          double Component::*member,
                          const char* type_name,
                          const char* path,
                          const char* label,
                          double min,
                          double max,
                          double step)
        {
            tc::stage_inspect_field(inspect,
                                    member,
                                    type_name,
                                    path,
                                    label,
                                    "float",
                                    min,
                                    max,
                                    step);
        }

        FEMRigidBodyComponent*
        find_body_component(const TcSceneRef& scene,
                            const std::string& entity_name,
                            const char* joint_type)
        {
            if (entity_name.empty())
            {
                tc::Log::error("[%s] body entity name is empty", joint_type);
                return nullptr;
            }
            Entity entity = scene.find_entity_by_name(entity_name);
            if (!entity.valid())
            {
                tc::Log::error("[%s] body entity '%s' was not found",
                               joint_type,
                               entity_name.c_str());
                return nullptr;
            }
            FEMRigidBodyComponent* body =
                entity.get_component<FEMRigidBodyComponent>();
            if (body == nullptr)
            {
                tc::Log::error("[%s] entity '%s' has no FEMRigidBodyComponent",
                               joint_type,
                               entity_name.c_str());
            }
            return body;
        }

    } // namespace

    FEMRigidBodyComponent::FEMRigidBodyComponent()
        : CxxComponent("FEMRigidBodyComponent")
    {
    }

    void FEMRigidBodyComponent::register_type()
    {
        auto descriptor =
            ComponentTypeDescriptorBuilder::native<FEMRigidBodyComponent>(
                "FEMRigidBodyComponent", module_owner, "Component");
        descriptor.category("Physics");
        auto& inspect = descriptor.inspect();
        stage_double(inspect,
                     &FEMRigidBodyComponent::mass,
                     "FEMRigidBodyComponent",
                     "mass",
                     "Mass",
                     0.001,
                     1.0e9,
                     0.1);
        tc::stage_inspect_field(inspect,
                                &FEMRigidBodyComponent::inertia_diagonal,
                                "FEMRigidBodyComponent",
                                "inertia_diagonal",
                                "Inertia (diagonal)",
                                "vec3");
        stage_double(inspect,
                     &FEMRigidBodyComponent::linear_damping,
                     "FEMRigidBodyComponent",
                     "linear_damping",
                     "Linear Damping",
                     0.0,
                     1.0e9,
                     0.01);
        stage_double(inspect,
                     &FEMRigidBodyComponent::angular_damping,
                     "FEMRigidBodyComponent",
                     "angular_damping",
                     "Angular Damping",
                     0.0,
                     1.0e9,
                     0.01);
        (void)descriptor.commit();
    }

    FEMFixedJointComponent::FEMFixedJointComponent()
        : CxxComponent("FEMFixedJointComponent")
    {
    }

    void FEMFixedJointComponent::register_type()
    {
        auto descriptor =
            ComponentTypeDescriptorBuilder::native<FEMFixedJointComponent>(
                "FEMFixedJointComponent", module_owner, "Component");
        descriptor.category("Physics");
        auto& inspect = descriptor.inspect();
        tc::stage_inspect_field(inspect,
                                &FEMFixedJointComponent::body_entity_name,
                                "FEMFixedJointComponent",
                                "body_entity_name",
                                "Body Entity",
                                "string");
        tc::stage_inspect_field(inspect,
                                &FEMFixedJointComponent::joint_axis_in_body,
                                "FEMFixedJointComponent",
                                "joint_axis_in_body",
                                "Joint Axis (in Body)",
                                "vec3");
        stage_double(inspect,
                     &FEMFixedJointComponent::damping,
                     "FEMFixedJointComponent",
                     "damping",
                     "Angular Damping",
                     0.0,
                     1.0e9,
                     0.01);
        (void)descriptor.commit();
    }

    FEMRevoluteJointComponent::FEMRevoluteJointComponent()
        : CxxComponent("FEMRevoluteJointComponent")
    {
    }

    void FEMRevoluteJointComponent::register_type()
    {
        auto descriptor =
            ComponentTypeDescriptorBuilder::native<FEMRevoluteJointComponent>(
                "FEMRevoluteJointComponent", module_owner, "Component");
        descriptor.category("Physics");
        auto& inspect = descriptor.inspect();
        tc::stage_inspect_field(inspect,
                                &FEMRevoluteJointComponent::body_a_entity_name,
                                "FEMRevoluteJointComponent",
                                "body_a_entity_name",
                                "Body A",
                                "string");
        tc::stage_inspect_field(inspect,
                                &FEMRevoluteJointComponent::body_b_entity_name,
                                "FEMRevoluteJointComponent",
                                "body_b_entity_name",
                                "Body B",
                                "string");
        tc::stage_inspect_field(
            inspect,
            &FEMRevoluteJointComponent::joint_offset_in_body_a,
            "FEMRevoluteJointComponent",
            "joint_offset_in_body_a",
            "Joint Offset (in Body A)",
            "vec3");
        tc::stage_inspect_field(
            inspect,
            &FEMRevoluteJointComponent::joint_axis_in_body_a,
            "FEMRevoluteJointComponent",
            "joint_axis_in_body_a",
            "Joint Axis (in Body A)",
            "vec3");
        stage_double(inspect,
                     &FEMRevoluteJointComponent::damping,
                     "FEMRevoluteJointComponent",
                     "damping",
                     "Damping",
                     0.0,
                     1.0e9,
                     0.01);
        (void)descriptor.commit();
    }

    FEMPhysicsWorldComponent::FEMPhysicsWorldComponent()
        : CxxComponent("FEMPhysicsWorldComponent")
    {
        set_has_update(true);
    }

    void FEMPhysicsWorldComponent::register_type()
    {
        auto descriptor =
            ComponentTypeDescriptorBuilder::native<FEMPhysicsWorldComponent>(
                "FEMPhysicsWorldComponent", module_owner, "Component");
        descriptor.category("Physics");
        auto& inspect = descriptor.inspect();
        tc::stage_inspect_field(inspect,
                                &FEMPhysicsWorldComponent::gravity,
                                "FEMPhysicsWorldComponent",
                                "gravity",
                                "Gravity",
                                "vec3");
        stage_double(inspect,
                     &FEMPhysicsWorldComponent::time_step,
                     "FEMPhysicsWorldComponent",
                     "time_step",
                     "Time Step",
                     0.000001,
                     1.0,
                     0.001);
        tc::stage_inspect_field(inspect,
                                &FEMPhysicsWorldComponent::substeps,
                                "FEMPhysicsWorldComponent",
                                "substeps",
                                "Substeps",
                                "int",
                                1,
                                100,
                                1);
        tc::stage_inspect_field(inspect,
                                &FEMPhysicsWorldComponent::energy_stabilization,
                                "FEMPhysicsWorldComponent",
                                "energy_stabilization",
                                "Energy Stabilization",
                                "bool");
        tc::stage_inspect_field(inspect,
                                &FEMPhysicsWorldComponent::strict_energy_mode,
                                "FEMPhysicsWorldComponent",
                                "strict_energy_mode",
                                "Strict Energy Mode",
                                "bool");
        (void)descriptor.commit();
    }

    void FEMPhysicsWorldComponent::start()
    {
        CxxComponent::start();
        initialized_ = rebuild_simulation();
        if (!initialized_)
        {
            tc::Log::error("[FEMPhysicsWorldComponent] failed to build native "
                           "multibody model");
        }
    }

    void FEMPhysicsWorldComponent::update(float dt)
    {
        if (!initialized_ || !enabled())
        {
            return;
        }
        if (!std::isfinite(dt) || dt < 0.0f)
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] received invalid frame dt=%g",
                static_cast<double>(dt));
            initialized_ = false;
            return;
        }
        const int step_count = std::max(substeps, 1);
        const double step_dt = time_step / static_cast<double>(step_count);
        if (!std::isfinite(step_dt) || step_dt <= 0.0)
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] invalid time_step=%g substeps=%d",
                time_step,
                substeps);
            initialized_ = false;
            return;
        }
        accumulated_time_ += static_cast<double>(dt);
        while (initialized_ && accumulated_time_ >= step_dt)
        {
            step_simulation(step_dt);
            accumulated_time_ -= step_dt;
        }
    }

    void FEMPhysicsWorldComponent::on_destroy()
    {
        initialized_ = false;
        clear_runtime_links();
        system_ = qopt::Multibody3DSystem();
        CxxComponent::on_destroy();
    }

    bool FEMPhysicsWorldComponent::rebuild_simulation()
    {
        clear_runtime_links();
        system_ = qopt::Multibody3DSystem();
        accumulated_time_ = 0.0;

        Entity owner = entity();
        if (!owner.valid())
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] owner entity is invalid");
            return false;
        }
        TcSceneRef scene = owner.scene();
        if (!scene.valid())
        {
            tc::Log::error("[FEMPhysicsWorldComponent] owner scene is invalid");
            return false;
        }

        const std::vector<Entity> entities = scene.get_all_entities();
        for (Entity candidate : entities)
        {
            if (auto* body = candidate.get_component<FEMRigidBodyComponent>();
                body != nullptr && body->enabled())
            {
                bodies_.push_back(body);
            }
            if (auto* joint = candidate.get_component<FEMFixedJointComponent>();
                joint != nullptr && joint->enabled())
            {
                fixed_joints_.push_back(joint);
            }
            if (auto* joint =
                    candidate.get_component<FEMRevoluteJointComponent>();
                joint != nullptr && joint->enabled())
            {
                revolute_joints_.push_back(joint);
            }
        }
        if (bodies_.empty())
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] scene contains no FEM bodies");
            clear_runtime_links();
            return false;
        }
        for (FEMRigidBodyComponent* body : bodies_)
        {
            if (!register_body(*body))
            {
                clear_runtime_links();
                return false;
            }
        }
        for (FEMFixedJointComponent* joint : fixed_joints_)
        {
            if (!register_fixed_joint(*joint))
            {
                clear_runtime_links();
                return false;
            }
        }
        for (FEMRevoluteJointComponent* joint : revolute_joints_)
        {
            if (!register_revolute_joint(*joint))
            {
                clear_runtime_links();
                return false;
            }
        }
        const qopt::DynamicsSystemDiagnostic finalized = system_.finalize();
        if (finalized != qopt::DynamicsSystemDiagnostic::None)
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] native model finalize failed: %s",
                qopt::dynamics_system_diagnostic_name(finalized).data());
            clear_runtime_links();
            return false;
        }
        return true;
    }

    bool
    FEMPhysicsWorldComponent::register_body(FEMRigidBodyComponent& component)
    {
        Entity body_entity = component.entity();
        const std::optional<Pose3> pose =
            body_entity.transform().try_rigid_pose();
        if (!pose.has_value())
        {
            tc::Log::error("[FEMPhysicsWorldComponent] body '%s' requires a "
                           "rigid world transform",
                           body_entity.name());
            return false;
        }
        qopt::SpatialInertia3D inertia;
        inertia.mass = component.mass;
        inertia.principal_moments = vec3(component.inertia_diagonal);
        inertia.inertia_frame_local = Pose3::identity();
        qopt::RigidBody3DState state;
        state.pose = *pose;
        auto body = std::make_unique<qopt::RigidBody3DContribution>(
            inertia,
            state,
            vec3(gravity),
            body_entity.name() ? body_entity.name() : "body");
        if (body->diagnostic() != qopt::Multibody3DDiagnostic::None)
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] body '%s' registration failed: %s",
                body_entity.name(),
                qopt::multibody3d_diagnostic_name(body->diagnostic()).data());
            return false;
        }
        component.body_ = body.get();
        if (system_.add_contribution(std::move(body)) !=
            qopt::DynamicsSystemDiagnostic::None)
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] failed to add body contribution");
            component.body_ = nullptr;
            return false;
        }
        auto force =
            std::make_unique<qopt::ForceOnBody3DContribution>(*component.body_);
        component.force_ = force.get();
        if (system_.add_contribution(std::move(force)) !=
            qopt::DynamicsSystemDiagnostic::None)
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] failed to add force contribution");
            component.force_ = nullptr;
            return false;
        }
        component.world_ = this;
        return true;
    }

    bool FEMPhysicsWorldComponent::register_fixed_joint(
        FEMFixedJointComponent& component)
    {
        const TcSceneRef scene = entity().scene();
        FEMRigidBodyComponent* body = find_body_component(
            scene, component.body_entity_name, "FEMFixedJointComponent");
        if (body == nullptr || body->world_ != this || body->body_ == nullptr)
        {
            tc::Log::error("[FEMFixedJointComponent] body '%s' is not "
                           "registered in this world",
                           component.body_entity_name.c_str());
            return false;
        }
        const Vec3 world_anchor =
            component.entity().transform().global_position();
        const Vec3 local_anchor =
            body->entity().transform().transform_point_inverse(world_anchor);
        const Vec3 local_axis = vec3(component.joint_axis_in_body);
        if (local_axis.norm() <= 1.0e-10)
        {
            tc::Log::error("[FEMFixedJointComponent] joint axis is degenerate");
            return false;
        }
        const Vec3 world_axis = body->entity().transform().transform_direction(
            local_axis.normalized());
        auto joint = std::make_unique<qopt::FixedRevoluteJoint3DContribution>(
            *body->body_,
            local_anchor,
            local_axis,
            world_anchor,
            world_axis,
            component.entity().name() ? component.entity().name()
                                      : "fixed_joint");
        if (joint->diagnostic() != qopt::Multibody3DDiagnostic::None)
        {
            tc::Log::error(
                "[FEMFixedJointComponent] registration failed: %s",
                qopt::multibody3d_diagnostic_name(joint->diagnostic()).data());
            return false;
        }
        component.joint_ = joint.get();
        if (system_.add_contribution(std::move(joint)) !=
            qopt::DynamicsSystemDiagnostic::None)
        {
            tc::Log::error(
                "[FEMFixedJointComponent] failed to add contribution");
            component.joint_ = nullptr;
            return false;
        }
        component.body_ = body->body_;
        component.world_ = this;
        return true;
    }

    bool FEMPhysicsWorldComponent::register_revolute_joint(
        FEMRevoluteJointComponent& component)
    {
        const TcSceneRef scene = entity().scene();
        FEMRigidBodyComponent* body_a = find_body_component(
            scene, component.body_a_entity_name, "FEMRevoluteJointComponent");
        FEMRigidBodyComponent* body_b = find_body_component(
            scene, component.body_b_entity_name, "FEMRevoluteJointComponent");
        if (body_a == nullptr || body_b == nullptr || body_a->world_ != this ||
            body_b->world_ != this || body_a->body_ == nullptr ||
            body_b->body_ == nullptr)
        {
            tc::Log::error("[FEMRevoluteJointComponent] both bodies must be "
                           "registered in this world");
            return false;
        }
        const Vec3 local_anchor_a = vec3(component.joint_offset_in_body_a);
        const Vec3 world_anchor =
            body_a->entity().transform().transform_point(local_anchor_a);
        const Vec3 local_anchor_b =
            body_b->entity().transform().transform_point_inverse(world_anchor);
        const Vec3 local_axis_a = vec3(component.joint_axis_in_body_a);
        if (local_axis_a.norm() <= 1.0e-10)
        {
            tc::Log::error(
                "[FEMRevoluteJointComponent] joint axis is degenerate");
            return false;
        }
        const Vec3 world_axis =
            body_a->entity().transform().transform_direction(
                local_axis_a.normalized());
        const Vec3 local_axis_b =
            body_b->entity().transform().transform_direction_inverse(
                world_axis);
        auto joint = std::make_unique<qopt::RevoluteJoint3DContribution>(
            *body_a->body_,
            local_anchor_a,
            local_axis_a,
            *body_b->body_,
            local_anchor_b,
            local_axis_b,
            component.entity().name() ? component.entity().name()
                                      : "revolute_joint");
        if (joint->diagnostic() != qopt::Multibody3DDiagnostic::None)
        {
            tc::Log::error(
                "[FEMRevoluteJointComponent] registration failed: %s",
                qopt::multibody3d_diagnostic_name(joint->diagnostic()).data());
            return false;
        }
        component.joint_ = joint.get();
        if (system_.add_contribution(std::move(joint)) !=
            qopt::DynamicsSystemDiagnostic::None)
        {
            tc::Log::error(
                "[FEMRevoluteJointComponent] failed to add contribution");
            component.joint_ = nullptr;
            return false;
        }
        component.body_a_ = body_a->body_;
        component.body_b_ = body_b->body_;
        component.world_ = this;
        return true;
    }

    void FEMPhysicsWorldComponent::step_simulation(double dt)
    {
        std::vector<Screw3> wrenches_world(bodies_.size());
        const auto body_index =
            [this](qopt::RigidBody3DContribution* contribution)
        {
            for (std::size_t index = 0; index < bodies_.size(); ++index)
            {
                if (bodies_[index]->body_ == contribution)
                {
                    return index;
                }
            }
            return bodies_.size();
        };
        for (std::size_t index = 0; index < bodies_.size(); ++index)
        {
            FEMRigidBodyComponent* body = bodies_[index];
            if (body->body_ == nullptr || body->force_ == nullptr)
            {
                continue;
            }
            const Screw3 velocity_world = body->body_->velocity_world();
            wrenches_world[index] -= {
                velocity_world.ang * body->angular_damping,
                velocity_world.lin * body->linear_damping,
            };
        }
        for (FEMFixedJointComponent* joint : fixed_joints_)
        {
            const std::size_t index = body_index(joint->body_);
            if (index == bodies_.size())
            {
                continue;
            }
            const Screw3 velocity_world = joint->body_->velocity_world();
            wrenches_world[index] -= {
                velocity_world.ang * joint->damping,
                Vec3::zero(),
            };
        }
        for (FEMRevoluteJointComponent* joint : revolute_joints_)
        {
            const std::size_t index_a = body_index(joint->body_a_);
            const std::size_t index_b = body_index(joint->body_b_);
            if (index_a == bodies_.size() || index_b == bodies_.size())
            {
                continue;
            }
            const Screw3 relative_velocity_world =
                joint->body_a_->velocity_world() -
                joint->body_b_->velocity_world();
            const Screw3 damping_wrench{
                relative_velocity_world.ang * joint->damping,
                Vec3::zero(),
            };
            wrenches_world[index_a] -= damping_wrench;
            wrenches_world[index_b] += damping_wrench;
        }
        for (std::size_t index = 0; index < bodies_.size(); ++index)
        {
            bodies_[index]->force_->set_wrench_world(wrenches_world[index]);
        }

        qopt::Multibody3DStepOptions options;
        options.time_step = dt;
        options.position_tolerance = 1.0e-8;
        options.velocity_tolerance = 1.0e-8;
        options.max_position_iterations = 8;
        const qopt::Multibody3DStepResult result = system_.step(options);
        if (result.status != qopt::QpStatus::Optimal ||
            result.diagnostic != qopt::DynamicsSystemDiagnostic::None)
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] native step failed: status=%s "
                "diagnostic=%s",
                qopt::qp_status_name(result.status).data(),
                qopt::dynamics_system_diagnostic_name(result.diagnostic)
                    .data());
            initialized_ = false;
            return;
        }

        for (FEMRigidBodyComponent* body : bodies_)
        {
            body->entity().transform().set_global_pose(
                body->body_->state().pose);
        }
    }

    void FEMPhysicsWorldComponent::clear_runtime_links()
    {
        for (FEMRigidBodyComponent* body : bodies_)
        {
            if (body != nullptr && body->world_ == this)
            {
                body->world_ = nullptr;
                body->body_ = nullptr;
                body->force_ = nullptr;
            }
        }
        for (FEMFixedJointComponent* joint : fixed_joints_)
        {
            if (joint != nullptr && joint->world_ == this)
            {
                joint->world_ = nullptr;
                joint->joint_ = nullptr;
                joint->body_ = nullptr;
            }
        }
        for (FEMRevoluteJointComponent* joint : revolute_joints_)
        {
            if (joint != nullptr && joint->world_ == this)
            {
                joint->world_ = nullptr;
                joint->joint_ = nullptr;
                joint->body_a_ = nullptr;
                joint->body_b_ = nullptr;
            }
        }
        bodies_.clear();
        fixed_joints_.clear();
        revolute_joints_.clear();
    }

} // namespace termin
