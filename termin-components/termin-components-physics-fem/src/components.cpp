#include <termin/physics_fem/articulation_scene.hpp>
#include <termin/physics_fem/components.hpp>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <string_view>

#include <components/kinematic_unit_component.hpp>
#include <components/articulation_component.hpp>
#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/geom/general_transform3.hpp>
#include <termin/physics_qopt/robotics_control.hpp>
#include <termin/render/debug_geometry.hpp>
#include <termin/tc_scene.hpp>

namespace termin
{
    namespace
    {

        constexpr const char* module_owner = "termin-components-physics-fem";

        DebugGeometryTypeRegistration& fem_joint_debug_geometry_type()
        {
            static DebugGeometryTypeRegistration registration(
                "physics.fem.joints", "FEM Joints", "Physics", true);
            return registration;
        }

        Vec3 vec3(tc_vec3 value)
        {
            return {value.x, value.y, value.z};
        }

        tc_vec3 tcvec3(Vec3 value)
        {
            return {value.x, value.y, value.z};
        }

        void
        register_collision_layer_mask_field(tc::InspectFacetBuilder& inspect)
        {
            tc::InspectFieldInfo info;
            info.type_name = "FEMPhysicsWorldComponent";
            info.path = "collision_layer_mask";
            info.label = "Collision Layers";
            info.kind = "layer_mask";
            info.getter = [](void* object) -> tc_value
            {
                auto* world = static_cast<FEMPhysicsWorldComponent*>(object);
                char buffer[32];
                std::snprintf(buffer,
                              sizeof(buffer),
                              "0x%llx",
                              static_cast<unsigned long long>(
                                  world->collision_layer_mask));
                return tc_value_string(buffer);
            };
            info.setter = [](void* object, tc_value value, void*) -> bool
            {
                auto* world = static_cast<FEMPhysicsWorldComponent*>(object);
                if (value.type == TC_VALUE_STRING && value.data.s != nullptr)
                {
                    world->collision_layer_mask =
                        std::strtoull(value.data.s, nullptr, 0);
                    return true;
                }
                if (value.type == TC_VALUE_INT)
                {
                    world->collision_layer_mask =
                        static_cast<std::uint64_t>(value.data.i);
                    return true;
                }
                return false;
            };
            (void)inspect.add_field(std::move(info));
        }

        template <typename Component>
        void stage_double(tc::InspectFacetBuilder& inspect,
                          double Component::* member,
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
                                    "double",
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

    FEMArticulationComponent::FEMArticulationComponent()
        : CxxComponent("FEMArticulationComponent")
    {
    }

    void FEMArticulationComponent::register_type()
    {
        auto descriptor =
            ComponentTypeDescriptorBuilder::native<FEMArticulationComponent>(
                "FEMArticulationComponent", module_owner, "Component");
        descriptor.category("Physics");
        tc::stage_inspect_field_choices(descriptor.inspect(),
                                        &FEMArticulationComponent::base_mode,
                                        "FEMArticulationComponent",
                                        "base_mode",
                                        "Base Mode",
                                        "enum",
                                        {{"0", "Fixed"}, {"1", "Floating"}});
        (void)descriptor.commit();
    }

    void FEMArticulationComponent::on_destroy()
    {
        if (world_ != nullptr)
        {
            world_->detach(*this);
        }
        shared_articulation_.reset();
        legacy_articulation_.reset();
        CxxComponent::on_destroy();
    }

    bool FEMArticulationComponent::initialized() const noexcept
    {
        return articulation_ != nullptr && dynamics_ != nullptr;
    }

    std::size_t FEMArticulationComponent::unit_count() const noexcept
    {
        return articulation_ != nullptr ? articulation_->unit_count() : 0;
    }

    double FEMArticulationComponent::total_energy() const noexcept
    {
        return dynamics_ != nullptr ? dynamics_->total_energy()
                                    : std::numeric_limits<double>::quiet_NaN();
    }

    robotics::Articulation3D* FEMArticulationComponent::articulation() noexcept
    {
        return articulation_;
    }

    const robotics::Articulation3D*
    FEMArticulationComponent::articulation() const noexcept
    {
        return articulation_;
    }

    Vec3 FEMArticulationComponent::gravity_world() const noexcept
    {
        return dynamics_ != nullptr ? dynamics_->gravity_world()
                                    : Vec3::zero();
    }

    std::vector<std::size_t>
    FEMArticulationComponent::actuator_dof_indices() const
    {
        std::vector<std::size_t> result;
        if (motor_ == nullptr)
        {
            return result;
        }
        result.reserve(motor_->channel_count());
        for (const physics_qopt::ArticulationMotorChannel& channel :
             motor_->channels())
        {
            result.push_back(channel.dof_index);
        }
        return result;
    }

    std::vector<double>
    FEMArticulationComponent::actuator_effort_limits() const
    {
        std::vector<double> result;
        if (motor_ == nullptr)
        {
            return result;
        }
        result.reserve(motor_->channel_count());
        for (const physics_qopt::ArticulationMotorChannel& channel :
             motor_->channels())
        {
            result.push_back(channel.effort_limit);
        }
        return result;
    }

    bool FEMArticulationComponent::apply_inverse_dynamics_control(
        const robotics::InverseDynamicsControlResult3D& control) noexcept
    {
        if (motor_ == nullptr ||
            motor_->channel_count() != motors_.size() ||
            control.actuator_effort.size() != motors_.size())
        {
            tc::Log::error(
                "[FEMArticulationComponent] rejected inverse-dynamics "
                "motor commands");
            return false;
        }
        for (std::size_t index = 0; index < motors_.size(); ++index)
        {
            FEMArticulationMotorComponent* motor = motors_[index];
            if (motor == nullptr ||
                !std::isfinite(control.actuator_effort[index]))
            {
                tc::Log::error(
                    "[FEMArticulationComponent] invalid actuator binding");
                return false;
            }
        }
        if (physics_qopt::apply_inverse_dynamics_motor_commands(
                *motor_, control) !=
            physics_qopt::RoboticsControlAdapterDiagnostic3D::None)
        {
            tc::Log::error(
                "[FEMArticulationComponent] rejected inverse-dynamics "
                "motor commands");
            return false;
        }
        for (std::size_t index = 0; index < motors_.size(); ++index)
        {
            motors_[index]->commanded_effort = control.actuator_effort[index];
        }
        return true;
    }

    FEMArticulationMotorComponent::FEMArticulationMotorComponent()
        : CxxComponent("FEMArticulationMotorComponent")
    {
    }

    void FEMArticulationMotorComponent::register_type()
    {
        auto descriptor = ComponentTypeDescriptorBuilder::native<
            FEMArticulationMotorComponent>(
            "FEMArticulationMotorComponent", module_owner, "Component");
        descriptor.category("Physics");
        auto& inspect = descriptor.inspect();
        stage_double(inspect,
                     &FEMArticulationMotorComponent::commanded_effort,
                     "FEMArticulationMotorComponent",
                     "commanded_effort",
                     "Commanded Effort",
                     -1.0e9,
                     1.0e9,
                     0.1);
        stage_double(inspect,
                     &FEMArticulationMotorComponent::maximum_effort,
                     "FEMArticulationMotorComponent",
                     "maximum_effort",
                     "Maximum Effort",
                     0.0,
                     1.0e9,
                     0.1);
        (void)descriptor.commit();
    }

    void FEMArticulationMotorComponent::on_destroy()
    {
        if (world_ != nullptr)
        {
            world_->detach(*this);
        }
        CxxComponent::on_destroy();
    }

    bool FEMArticulationMotorComponent::initialized() const noexcept
    {
        return world_ != nullptr && articulation_ != nullptr &&
               motor_ != nullptr;
    }

    double FEMArticulationMotorComponent::applied_effort() const noexcept
    {
        return initialized() ? motor_->applied_effort(channel_index_)
                             : std::numeric_limits<double>::quiet_NaN();
    }

    double FEMArticulationMotorComponent::power() const noexcept
    {
        if (!initialized())
        {
            return std::numeric_limits<double>::quiet_NaN();
        }
        const robotics::Articulation3DState& state = articulation_->state();
        if (joint_index_ >= state.velocities.size())
        {
            return std::numeric_limits<double>::quiet_NaN();
        }
        return applied_effort() * state.velocities[joint_index_];
    }

    bool FEMArticulationMotorComponent::saturated() const noexcept
    {
        return initialized() && motor_->saturated(channel_index_);
    }

    FEMJointLimitComponent::FEMJointLimitComponent()
        : CxxComponent("FEMJointLimitComponent")
    {
    }

    void FEMJointLimitComponent::register_type()
    {
        auto descriptor =
            ComponentTypeDescriptorBuilder::native<FEMJointLimitComponent>(
                "FEMJointLimitComponent", module_owner, "Component");
        descriptor.category("Physics");
        auto& inspect = descriptor.inspect();
        tc::stage_inspect_field(inspect,
                                &FEMJointLimitComponent::minimum_enabled,
                                "FEMJointLimitComponent",
                                "minimum_enabled",
                                "Minimum Enabled",
                                "bool");
        stage_double(inspect,
                     &FEMJointLimitComponent::minimum_coordinate,
                     "FEMJointLimitComponent",
                     "minimum_coordinate",
                     "Minimum Coordinate",
                     -1.0e9,
                     1.0e9,
                     0.1);
        tc::stage_inspect_field(inspect,
                                &FEMJointLimitComponent::maximum_enabled,
                                "FEMJointLimitComponent",
                                "maximum_enabled",
                                "Maximum Enabled",
                                "bool");
        stage_double(inspect,
                     &FEMJointLimitComponent::maximum_coordinate,
                     "FEMJointLimitComponent",
                     "maximum_coordinate",
                     "Maximum Coordinate",
                     -1.0e9,
                     1.0e9,
                     0.1);
        (void)descriptor.commit();
    }

    FEMJointServoComponent::FEMJointServoComponent()
        : CxxComponent("FEMJointServoComponent")
    {
    }

    void FEMJointServoComponent::register_type()
    {
        auto descriptor =
            ComponentTypeDescriptorBuilder::native<FEMJointServoComponent>(
                "FEMJointServoComponent", module_owner, "Component");
        descriptor.category("Control");
        auto& inspect = descriptor.inspect();
        tc::stage_inspect_field(
            inspect,
            &FEMJointServoComponent::position_control_enabled,
            "FEMJointServoComponent",
            "position_control_enabled",
            "Position Control",
            "bool");
        tc::stage_inspect_field(
            inspect,
            &FEMJointServoComponent::integral_control_enabled,
            "FEMJointServoComponent",
            "integral_control_enabled",
            "Integral Control",
            "bool");
        stage_double(inspect,
                     &FEMJointServoComponent::target_coordinate,
                     "FEMJointServoComponent",
                     "target_coordinate",
                     "Target Coordinate",
                     -1.0e9,
                     1.0e9,
                     0.1);
        stage_double(inspect,
                     &FEMJointServoComponent::target_velocity,
                     "FEMJointServoComponent",
                     "target_velocity",
                     "Target Velocity",
                     -1.0e9,
                     1.0e9,
                     0.1);
        stage_double(inspect,
                     &FEMJointServoComponent::position_gain,
                     "FEMJointServoComponent",
                     "position_gain",
                     "Position Gain",
                     0.0,
                     1.0e9,
                     0.1);
        stage_double(inspect,
                     &FEMJointServoComponent::integral_gain,
                     "FEMJointServoComponent",
                     "integral_gain",
                     "Integral Gain",
                     0.0,
                     1.0e9,
                     0.1);
        stage_double(inspect,
                     &FEMJointServoComponent::maximum_integral_effort,
                     "FEMJointServoComponent",
                     "maximum_integral_effort",
                     "Maximum Integral Effort",
                     0.0,
                     1.0e9,
                     0.1);
        stage_double(inspect,
                     &FEMJointServoComponent::velocity_gain,
                     "FEMJointServoComponent",
                     "velocity_gain",
                     "Velocity Gain",
                     0.0,
                     1.0e9,
                     0.1);
        stage_double(inspect,
                     &FEMJointServoComponent::feed_forward_effort,
                     "FEMJointServoComponent",
                     "feed_forward_effort",
                     "Feed-forward Effort",
                     -1.0e9,
                     1.0e9,
                     0.1);
        (void)descriptor.commit();
    }

    void FEMJointServoComponent::on_destroy()
    {
        if (world_ != nullptr)
        {
            world_->detach(*this);
        }
        CxxComponent::on_destroy();
    }

    bool FEMJointServoComponent::initialized() const noexcept
    {
        return world_ != nullptr && joint_ != nullptr &&
               motor_component_ != nullptr && articulation_ != nullptr;
    }

    double FEMJointServoComponent::position_error() const noexcept
    {
        return joint_ != nullptr ? target_coordinate - joint_->get_coordinate()
                                 : std::numeric_limits<double>::quiet_NaN();
    }

    double FEMJointServoComponent::commanded_effort() const noexcept
    {
        return initialized() ? commanded_effort_
                             : std::numeric_limits<double>::quiet_NaN();
    }

    double FEMJointServoComponent::position_effort() const noexcept
    {
        return initialized() ? position_effort_
                             : std::numeric_limits<double>::quiet_NaN();
    }

    double FEMJointServoComponent::velocity_effort() const noexcept
    {
        return initialized() ? velocity_effort_
                             : std::numeric_limits<double>::quiet_NaN();
    }

    double FEMJointServoComponent::integral_effort() const noexcept
    {
        return initialized() ? integral_effort_
                             : std::numeric_limits<double>::quiet_NaN();
    }

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

    void FEMRigidBodyComponent::on_destroy()
    {
        if (world_ != nullptr)
        {
            world_->detach(*this);
        }
        CxxComponent::on_destroy();
    }

    bool FEMRigidBodyComponent::initialized() const noexcept
    {
        return world_ != nullptr &&
               (body_ != nullptr || articulation_ != nullptr);
    }

    Screw3 FEMRigidBodyComponent::velocity_local() const noexcept
    {
        if (body_ != nullptr)
        {
            return body_->state().velocity_local;
        }
        if (articulation_ == nullptr)
        {
            return Screw3::zero();
        }
        if (articulation_base_)
        {
            const auto& base = articulation_->floating_base();
            return base.has_value() ? base->velocity_local : Screw3::zero();
        }
        const auto& velocities = articulation_->unit_velocities_local();
        return articulation_unit_index_ < velocities.size()
                   ? velocities[articulation_unit_index_]
                   : Screw3::zero();
    }

    bool FEMRigidBodyComponent::set_velocity_local(Screw3 velocity) noexcept
    {
        if (body_ != nullptr)
        {
            physics_qopt::RigidBody3DState state = body_->state();
            state.velocity_local = velocity;
            const physics_qopt::Multibody3DDiagnostic diagnostic =
                body_->set_state(state);
            if (diagnostic != physics_qopt::Multibody3DDiagnostic::None)
            {
                tc::Log::error(
                    "[FEMRigidBodyComponent] rejected local velocity: %s",
                    physics_qopt::multibody3d_diagnostic_name(diagnostic)
                        .data());
                return false;
            }
            return true;
        }
        if (articulation_ != nullptr && articulation_base_)
        {
            const auto& base = articulation_->floating_base();
            if (!base.has_value())
            {
                tc::Log::error(
                    "[FEMRigidBodyComponent] floating-base binding has no "
                    "base state");
                return false;
            }
            const robotics::Articulation3DDiagnostic diagnostic =
                articulation_->set_floating_base_state(base->pose_world,
                                                       velocity);
            if (diagnostic != robotics::Articulation3DDiagnostic::None)
            {
                tc::Log::error(
                    "[FEMRigidBodyComponent] rejected floating-base local "
                    "velocity: %s",
                    robotics::articulation3d_diagnostic_name(diagnostic)
                        .data());
                return false;
            }
            return true;
        }
        if (articulation_ != nullptr)
        {
            tc::Log::error(
                "[FEMRigidBodyComponent] articulation unit velocity is "
                "determined by reduced coordinates");
            return false;
        }
        else
        {
            tc::Log::error(
                "[FEMRigidBodyComponent] cannot set velocity before the body "
                "is initialized");
            return false;
        }
    }

    FEMFixedJointComponent::FEMFixedJointComponent()
        : CxxComponent("FEMFixedJointComponent")
    {
        install_render_lifecycle(&_c);
    }

    void FEMFixedJointComponent::register_type()
    {
        (void)fem_joint_debug_geometry_type();
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

    void FEMFixedJointComponent::on_destroy()
    {
        if (world_ != nullptr)
        {
            world_->detach(*this);
        }
        CxxComponent::on_destroy();
    }

    void FEMFixedJointComponent::prepare_render(
        const RenderPrepareContext& context)
    {
        DebugGeometryDrawer drawer = context.debug_geometry(
            fem_joint_debug_geometry_type().type_id());
        if (!drawer)
        {
            return;
        }

        const Vec3 anchor = entity().transform().global_position();
        Vec3 body_position;
        if (body_ != nullptr)
        {
            body_position = body_->state().pose.lin;
        }
        else
        {
            const Entity body_entity =
                entity().scene().find_entity_by_name(body_entity_name);
            if (!body_entity.valid())
            {
                return;
            }
            body_position = body_entity.transform().global_position();
        }
        drawer.line(anchor,
                    body_position,
                    Color4{0.8f, 0.8f, 0.2f, 1.0f},
                    false);
        drawer.wire_sphere(anchor,
                           0.05,
                           Color4{1.0f, 0.5f, 0.0f, 1.0f},
                           8,
                           false);
    }

    FEMRevoluteJointComponent::FEMRevoluteJointComponent()
        : CxxComponent("FEMRevoluteJointComponent")
    {
        install_render_lifecycle(&_c);
    }

    void FEMRevoluteJointComponent::register_type()
    {
        (void)fem_joint_debug_geometry_type();
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

    void FEMRevoluteJointComponent::on_destroy()
    {
        if (world_ != nullptr)
        {
            world_->detach(*this);
        }
        CxxComponent::on_destroy();
    }

    void FEMRevoluteJointComponent::prepare_render(
        const RenderPrepareContext& context)
    {
        DebugGeometryDrawer drawer = context.debug_geometry(
            fem_joint_debug_geometry_type().type_id());
        if (!drawer)
        {
            return;
        }

        Vec3 joint_position;
        Vec3 body_a_position;
        Vec3 body_b_position;
        if (body_a_ != nullptr && body_b_ != nullptr)
        {
            joint_position = body_a_->state().pose.transform_point(
                vec3(joint_offset_in_body_a));
            body_a_position = body_a_->state().pose.lin;
            body_b_position = body_b_->state().pose.lin;
        }
        else
        {
            const TcSceneRef scene = entity().scene();
            const Entity body_a_entity =
                scene.find_entity_by_name(body_a_entity_name);
            const Entity body_b_entity =
                scene.find_entity_by_name(body_b_entity_name);
            if (!body_a_entity.valid() || !body_b_entity.valid())
            {
                return;
            }
            joint_position = body_a_entity.transform().transform_point(
                vec3(joint_offset_in_body_a));
            body_a_position = body_a_entity.transform().global_position();
            body_b_position = body_b_entity.transform().global_position();
        }

        drawer.line(joint_position,
                    body_a_position,
                    Color4{0.2f, 0.8f, 0.8f, 1.0f},
                    false);
        drawer.line(joint_position,
                    body_b_position,
                    Color4{0.8f, 0.2f, 0.8f, 1.0f},
                    false);
        drawer.wire_sphere(joint_position,
                           0.05,
                           Color4{0.2f, 0.8f, 0.2f, 1.0f},
                           8,
                           false);
    }

    FEMPhysicsWorldComponent::FEMPhysicsWorldComponent()
        : CxxComponent("FEMPhysicsWorldComponent")
    {
        set_has_fixed_update(true);
        (void)set_fixed_update_priority(fixed_update_priority::physics);
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
                     &FEMPhysicsWorldComponent::contact_friction_coefficient,
                     "FEMPhysicsWorldComponent",
                     "contact_friction_coefficient",
                     "Contact Friction",
                     0.0,
                     10.0,
                     0.01);
        register_collision_layer_mask_field(inspect);
        tc::stage_inspect_field(
            inspect,
            &FEMPhysicsWorldComponent::adjacent_unit_collision_enabled,
            "FEMPhysicsWorldComponent",
            "adjacent_unit_collision_enabled",
            "Adjacent Link Collision",
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

    void FEMPhysicsWorldComponent::fixed_update(float dt)
    {
        if (!initialized_ || !enabled())
        {
            return;
        }
        if (!std::isfinite(dt) || dt <= 0.0f)
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] received invalid fixed dt=%g",
                static_cast<double>(dt));
            initialized_ = false;
            return;
        }
        for (const FEMArticulationComponent* articulation : articulations_)
        {
            if (articulation != nullptr &&
                articulation->articulation_owner_ != nullptr &&
                articulation->articulation_owner_->articulation() !=
                    articulation->articulation_)
            {
                tc::Log::error(
                    "[FEMPhysicsWorldComponent] ArticulationComponent on "
                    "'%s' was rebuilt while its FEM model was active; rebuild "
                    "the physics world before continuing",
                    articulation->entity().name());
                initialized_ = false;
                return;
            }
        }
        step_simulation(static_cast<double>(dt));
    }

    void FEMPhysicsWorldComponent::on_destroy()
    {
        initialized_ = false;
        system_ = physics_qopt::Multibody3DSystem();
        clear_runtime_links();
        simulated_time_ = 0.0;
        initial_total_energy_ = 0.0;
        successful_steps_ = 0;
        motor_work_ = 0.0;
        contacts_ = nullptr;
        warned_contact_colliders_.clear();
        CxxComponent::on_destroy();
    }

    bool FEMPhysicsWorldComponent::rebuild_simulation()
    {
        system_ = physics_qopt::Multibody3DSystem();
        clear_runtime_links();
        simulated_time_ = 0.0;
        initial_total_energy_ = 0.0;
        successful_steps_ = 0;
        motor_work_ = 0.0;

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
        if (!std::isfinite(contact_friction_coefficient) ||
            contact_friction_coefficient < 0.0)
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] invalid contact friction "
                "coefficient=%g",
                contact_friction_coefficient);
            return false;
        }

        std::vector<FEMRigidBodyComponent*> discovered_bodies;
        const std::vector<Entity> entities = scene.get_all_entities();
        for (Entity candidate : entities)
        {
            if (auto* body = candidate.get_component<FEMRigidBodyComponent>();
                body != nullptr && body->enabled())
            {
                discovered_bodies.push_back(body);
            }
            if (auto* articulation =
                    candidate.get_component<FEMArticulationComponent>();
                articulation != nullptr && articulation->enabled())
            {
                articulations_.push_back(articulation);
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
        if (discovered_bodies.empty() && articulations_.empty())
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] scene contains no FEM bodies or "
                "articulations");
            clear_runtime_links();
            return false;
        }
        for (FEMArticulationComponent* articulation : articulations_)
        {
            if (!register_articulation(*articulation))
            {
                clear_runtime_links();
                return false;
            }
        }
        for (FEMRigidBodyComponent* body : discovered_bodies)
        {
            if (body->world_ == nullptr && !register_body(*body))
            {
                clear_runtime_links();
                return false;
            }
            if (body->world_ != this)
            {
                tc::Log::error(
                    "[FEMPhysicsWorldComponent] body '%s' belongs to another "
                    "dynamics world",
                    body->entity().name());
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
        auto contacts =
            std::make_unique<physics_qopt::ContactSet3DContribution>(
                "scene_contacts");
        contacts_ = contacts.get();
        if (system_.add_contribution(std::move(contacts)) !=
            physics_qopt::DynamicsSystemDiagnostic::None)
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] failed to add scene contact "
                "contribution");
            contacts_ = nullptr;
            clear_runtime_links();
            return false;
        }
        const physics_qopt::DynamicsSystemDiagnostic finalized =
            system_.finalize();
        if (finalized != physics_qopt::DynamicsSystemDiagnostic::None)
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] native model finalize failed: %s",
                physics_qopt::dynamics_system_diagnostic_name(finalized)
                    .data());
            clear_runtime_links();
            return false;
        }
        initial_total_energy_ = total_energy();
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
        SpatialInertia3 inertia;
        inertia.mass = component.mass;
        inertia.principal_moments = vec3(component.inertia_diagonal);
        inertia.inertia_frame = Pose3::identity();
        physics_qopt::RigidBody3DState state;
        state.pose = *pose;
        auto body = std::make_unique<physics_qopt::RigidBody3DContribution>(
            inertia,
            state,
            vec3(gravity),
            body_entity.name() ? body_entity.name() : "body");
        if (body->diagnostic() != physics_qopt::Multibody3DDiagnostic::None)
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] body '%s' registration failed: %s",
                body_entity.name(),
                physics_qopt::multibody3d_diagnostic_name(body->diagnostic())
                    .data());
            return false;
        }
        component.body_ = body.get();
        if (system_.add_contribution(std::move(body)) !=
            physics_qopt::DynamicsSystemDiagnostic::None)
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] failed to add body contribution");
            component.body_ = nullptr;
            return false;
        }
        auto force = std::make_unique<physics_qopt::ForceOnBody3DContribution>(
            *component.body_);
        component.force_ = force.get();
        if (system_.add_contribution(std::move(force)) !=
            physics_qopt::DynamicsSystemDiagnostic::None)
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] failed to add force contribution");
            component.force_ = nullptr;
            return false;
        }
        component.world_ = this;
        bodies_.push_back(&component);
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
        auto joint =
            std::make_unique<physics_qopt::FixedRevoluteJoint3DContribution>(
                *body->body_,
                local_anchor,
                local_axis,
                world_anchor,
                world_axis,
                component.entity().name() ? component.entity().name()
                                          : "fixed_joint");
        if (joint->diagnostic() != physics_qopt::Multibody3DDiagnostic::None)
        {
            tc::Log::error(
                "[FEMFixedJointComponent] registration failed: %s",
                physics_qopt::multibody3d_diagnostic_name(joint->diagnostic())
                    .data());
            return false;
        }
        component.joint_ = joint.get();
        if (system_.add_contribution(std::move(joint)) !=
            physics_qopt::DynamicsSystemDiagnostic::None)
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
        auto joint =
            std::make_unique<physics_qopt::RevoluteJoint3DContribution>(
                *body_a->body_,
                local_anchor_a,
                local_axis_a,
                *body_b->body_,
                local_anchor_b,
                local_axis_b,
                component.entity().name() ? component.entity().name()
                                          : "revolute_joint");
        if (joint->diagnostic() != physics_qopt::Multibody3DDiagnostic::None)
        {
            tc::Log::error(
                "[FEMRevoluteJointComponent] registration failed: %s",
                physics_qopt::multibody3d_diagnostic_name(joint->diagnostic())
                    .data());
            return false;
        }
        component.joint_ = joint.get();
        if (system_.add_contribution(std::move(joint)) !=
            physics_qopt::DynamicsSystemDiagnostic::None)
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

    bool FEMPhysicsWorldComponent::register_articulation(
        FEMArticulationComponent& component)
    {
        FEMArticulationSceneCompilation compiled =
            compile_fem_articulation_scene(component.entity());
        if (!compiled.ok())
        {
            tc::Log::error(
                "[FEMArticulationComponent] compilation failed at '%s': %s",
                compiled.diagnostic_entity.c_str(),
                fem_articulation_scene_diagnostic_name(compiled.diagnostic)
                    .data());
            return false;
        }
        if (compiled.base_body != nullptr)
        {
            if (compiled.base_body->world_ != nullptr)
            {
                tc::Log::error(
                    "[FEMArticulationComponent] base body '%s' belongs to "
                    "more than one dynamics model",
                    compiled.base_entity.name());
                return false;
            }
            if (compiled.base_body->linear_damping != 0.0 ||
                compiled.base_body->angular_damping != 0.0)
            {
                tc::Log::error(
                    "[FEMArticulationComponent] base body '%s' uses damping, "
                    "which is not yet projected into reduced coordinates",
                    compiled.base_entity.name());
                return false;
            }
        }
        for (const FEMArticulationSceneBinding& binding : compiled.bindings)
        {
            if (binding.body != nullptr && binding.body->world_ != nullptr)
            {
                tc::Log::error(
                    "[FEMArticulationComponent] body '%s' belongs to more than "
                    "one dynamics model",
                    binding.body_entity.name());
                return false;
            }
            if (binding.body != nullptr &&
                (binding.body->linear_damping != 0.0 ||
                 binding.body->angular_damping != 0.0))
            {
                tc::Log::error(
                    "[FEMArticulationComponent] body '%s' uses damping, which "
                    "is not yet projected into reduced coordinates",
                    binding.body_entity.name());
                return false;
            }
        }

        std::unique_ptr<robotics::Articulation3D> legacy_articulation;
        std::shared_ptr<robotics::Articulation3D> shared_articulation =
            std::move(compiled.borrowed_articulation);
        robotics::Articulation3D* articulation = shared_articulation.get();
        if (articulation == nullptr && compiled.floating_base.has_value())
        {
            legacy_articulation = std::make_unique<robotics::Articulation3D>(
                std::move(*compiled.floating_base),
                std::move(compiled.units),
                std::move(compiled.state),
                component.entity().name() ? component.entity().name()
                                          : "articulation");
            articulation = legacy_articulation.get();
        }
        else if (articulation == nullptr)
        {
            legacy_articulation = std::make_unique<robotics::Articulation3D>(
                std::move(compiled.units),
                std::move(compiled.state),
                component.entity().name() ? component.entity().name()
                                          : "articulation");
            articulation = legacy_articulation.get();
        }
        if (articulation == nullptr || articulation->diagnostic() !=
            robotics::Articulation3DDiagnostic::None)
        {
            tc::Log::error(
                "[FEMArticulationComponent] reduced model is invalid: %s",
                robotics::articulation3d_diagnostic_name(
                    articulation != nullptr
                        ? articulation->diagnostic()
                        : robotics::Articulation3DDiagnostic::InvalidState)
                    .data());
            return false;
        }

        std::vector<physics_qopt::ArticulationMotorChannel> motor_channels;
        const std::size_t joint_dof_offset =
            articulation->has_floating_base() ? 6U : 0U;
        for (std::size_t joint_index = 0;
             joint_index < compiled.bindings.size();
             ++joint_index)
        {
            const FEMArticulationSceneBinding& binding =
                compiled.bindings[joint_index];
            FEMArticulationMotorComponent* motor = binding.motor;
            FEMJointServoComponent* servo = binding.servo;
            if (servo != nullptr && servo->enabled() &&
                (motor == nullptr || !motor->enabled()))
            {
                tc::Log::error(
                    "[FEMJointServoComponent] servo on '%s' requires an "
                    "enabled FEMArticulationMotorComponent",
                    binding.joint_entity.name());
                return false;
            }
            if (motor == nullptr || !motor->enabled())
            {
                continue;
            }
            if (!std::isfinite(motor->commanded_effort) ||
                !std::isfinite(motor->maximum_effort) ||
                motor->maximum_effort < 0.0)
            {
                tc::Log::error(
                    "[FEMArticulationMotorComponent] invalid settings on '%s'",
                    binding.joint_entity.name());
                return false;
            }
            if (motor->world_ != nullptr)
            {
                tc::Log::error(
                    "[FEMArticulationMotorComponent] motor on '%s' belongs to "
                    "another world",
                    binding.joint_entity.name());
                return false;
            }
            if (servo != nullptr && servo->enabled() &&
                (!std::isfinite(servo->target_coordinate) ||
                 !std::isfinite(servo->target_velocity) ||
                 !std::isfinite(servo->position_gain) ||
                 servo->position_gain < 0.0 ||
                 !std::isfinite(servo->integral_gain) ||
                 servo->integral_gain < 0.0 ||
                 !std::isfinite(servo->maximum_integral_effort) ||
                 servo->maximum_integral_effort < 0.0 ||
                 !std::isfinite(servo->velocity_gain) ||
                 servo->velocity_gain < 0.0 ||
                 !std::isfinite(servo->feed_forward_effort) ||
                 servo->world_ != nullptr))
            {
                tc::Log::error(
                    "[FEMJointServoComponent] invalid settings or ownership "
                    "on '%s'",
                    binding.joint_entity.name());
                return false;
            }
            motor_channels.push_back({
                .dof_index = joint_dof_offset + joint_index,
                .effort_limit = motor->maximum_effort,
                .diagnostic_name = binding.joint_entity.name(),
            });
        }

        auto dynamics =
            std::make_unique<physics_qopt::Articulation3DDynamicsContribution>(
                *articulation,
                vec3(gravity),
                component.entity().name() ? component.entity().name()
                                          : "articulation");
        if (dynamics->diagnostic() != robotics::Articulation3DDiagnostic::None)
        {
            tc::Log::error(
                "[FEMArticulationComponent] dynamics adapter is invalid: %s",
                robotics::articulation3d_diagnostic_name(dynamics->diagnostic())
                    .data());
            return false;
        }
        physics_qopt::Articulation3DDynamicsContribution* dynamics_ptr =
            dynamics.get();
        std::unique_ptr<physics_qopt::ArticulationMotorContribution> motor;
        physics_qopt::ArticulationMotorContribution* motor_ptr = nullptr;
        if (!motor_channels.empty())
        {
            motor =
                std::make_unique<physics_qopt::ArticulationMotorContribution>(
                    *dynamics_ptr,
                    std::move(motor_channels),
                    component.entity().name() ? component.entity().name()
                                              : "articulation-motors");
            if (motor->diagnostic() !=
                physics_qopt::ArticulationMotorDiagnostic::None)
            {
                tc::Log::error(
                    "[FEMArticulationComponent] motor model is invalid: %s",
                    physics_qopt::articulation_motor_diagnostic_name(
                        motor->diagnostic())
                        .data());
                return false;
            }
            motor_ptr = motor.get();
        }
        if (system_.add_contribution(std::move(dynamics)) !=
            physics_qopt::DynamicsSystemDiagnostic::None)
        {
            tc::Log::error(
                "[FEMArticulationComponent] failed to add contribution");
            return false;
        }
        if (motor != nullptr &&
            system_.add_contribution(std::move(motor)) !=
                physics_qopt::DynamicsSystemDiagnostic::None)
        {
            tc::Log::error("[FEMArticulationComponent] failed to add motor "
                           "contribution");
            return false;
        }
        component.articulation_owner_ = compiled.articulation_owner;
        component.shared_articulation_ = std::move(shared_articulation);
        component.legacy_articulation_ = std::move(legacy_articulation);
        component.articulation_ = articulation;
        component.dynamics_ = dynamics_ptr;
        component.motor_ = motor_ptr;
        component.world_ = this;
        component.base_body_ = compiled.base_body;
        if (component.base_body_ != nullptr)
        {
            component.base_body_->world_ = this;
            component.base_body_->articulation_ = component.dynamics_;
            component.base_body_->articulation_unit_index_ =
                robotics::articulation_root_frame;
            component.base_body_->articulation_base_ = true;
        }
        component.bodies_.reserve(compiled.bindings.size());
        component.joint_entities_.reserve(compiled.bindings.size());
        component.joint_coordinate_scales_.reserve(compiled.bindings.size());
        component.motors_.reserve(compiled.bindings.size());
        component.servos_.reserve(compiled.bindings.size());
        std::size_t motor_channel = 0;
        for (std::size_t joint_index = 0;
             joint_index < compiled.bindings.size();
             ++joint_index)
        {
            const FEMArticulationSceneBinding& binding =
                compiled.bindings[joint_index];
            component.bodies_.push_back(binding.body);
            component.joint_entities_.push_back(binding.joint_entity);
            component.joint_coordinate_scales_.push_back(
                binding.coordinate_scale);
            if (binding.body != nullptr)
            {
                binding.body->world_ = this;
                binding.body->articulation_ = component.dynamics_;
                binding.body->articulation_unit_index_ = joint_index;
                binding.body->articulation_base_ = false;
            }
            if (binding.motor != nullptr && binding.motor->enabled())
            {
                binding.motor->world_ = this;
                binding.motor->articulation_ = component.dynamics_;
                binding.motor->motor_ = component.motor_;
                binding.motor->dof_index_ = joint_dof_offset + joint_index;
                binding.motor->joint_index_ = joint_index;
                binding.motor->channel_index_ = motor_channel++;
                component.motors_.push_back(binding.motor);
            }
            if (binding.servo != nullptr && binding.servo->enabled())
            {
                binding.servo->world_ = this;
                binding.servo->joint_ = binding.joint;
                binding.servo->motor_component_ = binding.motor;
                binding.servo->articulation_ = component.dynamics_;
                binding.servo->dof_index_ = joint_index;
                binding.servo->coordinate_scale_ = binding.coordinate_scale;
                binding.servo->position_effort_ = 0.0;
                binding.servo->velocity_effort_ = 0.0;
                binding.servo->integral_effort_ = 0.0;
                binding.servo->commanded_effort_ = 0.0;
                component.servos_.push_back(binding.servo);
            }
        }
        return true;
    }

    void FEMPhysicsWorldComponent::synchronize_articulations()
    {
        for (FEMArticulationComponent* component : articulations_)
        {
            if (component == nullptr || component->articulation_ == nullptr)
            {
                continue;
            }
            const robotics::Articulation3DState& state =
                component->articulation_->state();
            if (component->base_body_ != nullptr)
            {
                const auto& base = component->articulation_->floating_base();
                if (!base.has_value())
                {
                    tc::Log::error(
                        "[FEMArticulationComponent] base body binding has no "
                        "floating-base state");
                    initialized_ = false;
                    return;
                }
                component->base_body_->entity().transform().set_global_pose(
                    base->pose_world);
            }
            if (state.coordinates.size() != component->joint_entities_.size())
            {
                tc::Log::error(
                    "[FEMArticulationComponent] runtime binding size mismatch");
                initialized_ = false;
                return;
            }
            if (component->joint_coordinate_scales_.size() !=
                component->joint_entities_.size())
            {
                tc::Log::error("[FEMArticulationComponent] coordinate scale "
                               "binding size mismatch");
                initialized_ = false;
                return;
            }
            for (std::size_t index = 0;
                 index < component->joint_entities_.size();
                 ++index)
            {
                Entity joint_entity = component->joint_entities_[index];
                KinematicUnitComponent* joint =
                    joint_entity.valid()
                        ? joint_entity.get_component<KinematicUnitComponent>()
                        : nullptr;
                if (joint == nullptr)
                {
                    tc::Log::error(
                        "[FEMArticulationComponent] joint binding was "
                        "destroyed during simulation");
                    initialized_ = false;
                    return;
                }
                const double coordinate_scale =
                    component->joint_coordinate_scales_[index];
                if (!std::isfinite(coordinate_scale) || coordinate_scale <= 0.0)
                {
                    tc::Log::error("[FEMArticulationComponent] invalid "
                                   "coordinate scale binding");
                    initialized_ = false;
                    return;
                }
                joint->set_coordinate(state.coordinates[index] /
                                      coordinate_scale);
            }
        }
    }

    bool FEMPhysicsWorldComponent::update_motor_commands(double dt)
    {
        for (FEMArticulationComponent* component : articulations_)
        {
            if (component == nullptr || component->articulation_ == nullptr)
            {
                continue;
            }
            const robotics::Articulation3DState& state =
                component->articulation_->state();
            for (FEMJointServoComponent* servo : component->servos_)
            {
                if (servo == nullptr || servo->motor_component_ == nullptr ||
                    servo->dof_index_ >= state.coordinates.size() ||
                    servo->dof_index_ >= state.velocities.size())
                {
                    tc::Log::error(
                        "[FEMJointServoComponent] invalid runtime binding");
                    return false;
                }
                if (!std::isfinite(servo->coordinate_scale_) ||
                    servo->coordinate_scale_ <= 0.0)
                {
                    tc::Log::error(
                        "[FEMJointServoComponent] invalid coordinate scale");
                    return false;
                }
                const double target_position =
                    servo->target_coordinate * servo->coordinate_scale_;
                const double target_velocity =
                    servo->target_velocity * servo->coordinate_scale_;
                const double position_error =
                    target_position - state.coordinates[servo->dof_index_];
                const double position_effort =
                    servo->position_control_enabled
                        ? servo->position_gain * position_error
                        : 0.0;
                const double velocity_effort =
                    servo->velocity_gain *
                    (target_velocity - state.velocities[servo->dof_index_]);
                const double non_integral_effort = position_effort +
                                                   velocity_effort +
                                                   servo->feed_forward_effort;

                if (!servo->enabled() || !servo->motor_component_->enabled() ||
                    !servo->position_control_enabled ||
                    !servo->integral_control_enabled ||
                    servo->integral_gain == 0.0)
                {
                    servo->integral_effort_ = 0.0;
                }
                else
                {
                    const double proposed_integral_effort = std::clamp(
                        servo->integral_effort_ +
                            servo->integral_gain * position_error * dt,
                        -servo->maximum_integral_effort,
                        servo->maximum_integral_effort);
                    const double proposed_command =
                        non_integral_effort + proposed_integral_effort;
                    const double integral_delta =
                        proposed_integral_effort - servo->integral_effort_;
                    const double motor_limit =
                        servo->motor_component_->maximum_effort;
                    const bool pushes_further_into_saturation =
                        (proposed_command > motor_limit &&
                         integral_delta > 0.0) ||
                        (proposed_command < -motor_limit &&
                         integral_delta < 0.0);
                    if (!pushes_further_into_saturation)
                    {
                        servo->integral_effort_ = proposed_integral_effort;
                    }
                }

                const double effort =
                    servo->enabled()
                        ? non_integral_effort + servo->integral_effort_
                        : 0.0;
                servo->position_effort_ =
                    servo->enabled() ? position_effort : 0.0;
                servo->velocity_effort_ =
                    servo->enabled() ? velocity_effort : 0.0;
                if (!std::isfinite(effort))
                {
                    tc::Log::error(
                        "[FEMJointServoComponent] produced a non-finite "
                        "effort command");
                    return false;
                }
                servo->commanded_effort_ = effort;
                servo->motor_component_->commanded_effort = effort;
            }
            for (FEMArticulationMotorComponent* motor : component->motors_)
            {
                if (motor == nullptr || motor->motor_ == nullptr ||
                    !std::isfinite(motor->commanded_effort) ||
                    !std::isfinite(motor->maximum_effort) ||
                    motor->maximum_effort < 0.0 ||
                    motor->motor_->set_effort_limit(motor->channel_index_,
                                                    motor->maximum_effort) !=
                        physics_qopt::ArticulationMotorDiagnostic::None ||
                    motor->motor_->set_command(
                        motor->channel_index_,
                        motor->enabled() ? motor->commanded_effort : 0.0) !=
                        physics_qopt::ArticulationMotorDiagnostic::None)
                {
                    tc::Log::error(
                        "[FEMArticulationMotorComponent] failed to update "
                        "motor command");
                    return false;
                }
            }
        }
        return true;
    }

    void FEMPhysicsWorldComponent::step_simulation(double dt)
    {
        std::vector<Screw3> wrenches_world(bodies_.size());
        const auto body_index =
            [this](physics_qopt::RigidBody3DContribution* contribution)
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
            const Screw3 velocity_world =
                body->body_->velocity_at_body_origin_world();
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
            const Screw3 velocity_world =
                joint->body_->velocity_at_body_origin_world();
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
                joint->body_a_->velocity_at_body_origin_world() -
                joint->body_b_->velocity_at_body_origin_world();
            const Screw3 damping_wrench{
                relative_velocity_world.ang * joint->damping,
                Vec3::zero(),
            };
            wrenches_world[index_a] -= damping_wrench;
            wrenches_world[index_b] += damping_wrench;
        }
        for (std::size_t index = 0; index < bodies_.size(); ++index)
        {
            bodies_[index]->force_->set_wrench_at_body_origin_world(
                wrenches_world[index]);
        }

        if (!update_motor_commands(dt))
        {
            initialized_ = false;
            return;
        }
        if (!refresh_contacts())
        {
            initialized_ = false;
            return;
        }

        physics_qopt::Multibody3DStepOptions options;
        options.time_step = dt;
        options.position_tolerance = 1.0e-8;
        options.velocity_tolerance = 1.0e-8;
        options.max_position_iterations = 8;
        const physics_qopt::Multibody3DStepResult result =
            system_.step(options);
        if (result.status != physics_qopt::QpStatus::Optimal ||
            result.diagnostic != physics_qopt::DynamicsSystemDiagnostic::None)
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] native step failed: status=%s "
                "diagnostic=%s position_error=%g position_iterations=%zu",
                physics_qopt::qp_status_name(result.status).data(),
                physics_qopt::dynamics_system_diagnostic_name(result.diagnostic)
                    .data(),
                result.position_constraint_linf,
                result.position_iterations);
            initialized_ = false;
            return;
        }

        for (FEMRigidBodyComponent* body : bodies_)
        {
            body->entity().transform().set_global_pose(
                body->body_->state().pose);
        }
        synchronize_articulations();
        if (!initialized_)
        {
            return;
        }
        const FEMPhysicsTelemetry current = telemetry();
        motor_work_ += current.motor_power * dt;
        simulated_time_ += dt;
        ++successful_steps_;
    }

} // namespace termin
