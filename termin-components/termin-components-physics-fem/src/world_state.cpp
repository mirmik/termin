#include <termin/physics_fem/components.hpp>

#include <algorithm>
#include <cmath>
#include <limits>

namespace termin {
    FEMPhysicsTelemetry FEMPhysicsWorldComponent::telemetry() const noexcept {
        return {
            .initialized = initialized_,
            .simulated_time = simulated_time_,
            .successful_steps = successful_steps_,
            .body_count =
                [this]() {
                    std::size_t result = bodies_.size();
                    for (const FEMArticulationComponent* articulation : articulations_) {
                        if (articulation != nullptr) {
                            result += articulation->unit_count();
                            result += articulation->base_body_ != nullptr ? 1U : 0U;
                        }
                    }
                    return result;
                }(),
            .joint_count = fixed_joints_.size() + revolute_joints_.size(),
            .articulation_count = articulations_.size(),
            .reduced_dof_count =
                [this]() {
                    std::size_t result = 0;
                    for (const FEMArticulationComponent* articulation : articulations_) {
                        result += articulation != nullptr && articulation->articulation_ != nullptr
                                      ? articulation->articulation_->dof_count()
                                      : 0;
                    }
                    return result;
                }(),
            .motor_count =
                [this]() {
                    std::size_t result = 0;
                    for (const FEMArticulationComponent* articulation : articulations_) {
                        result += articulation != nullptr ? articulation->motors_.size() : 0;
                    }
                    return result;
                }(),
            .saturated_motor_count =
                [this]() {
                    std::size_t result = 0;
                    for (const FEMArticulationComponent* articulation : articulations_) {
                        if (articulation == nullptr) {
                            continue;
                        }
                        for (const FEMArticulationMotorComponent* motor : articulation->motors_) {
                            result += motor != nullptr && motor->saturated() ? 1U : 0U;
                        }
                    }
                    return result;
                }(),
            .contact_count = contacts_ != nullptr ? contacts_->contacts().size() : 0,
            .active_contact_count =
                [this]() {
                    std::size_t result = 0;
                    if (contacts_ != nullptr) {
                        for (const physics_qopt::ContactState3D& state : contacts_->states()) {
                            result += state.active ? 1U : 0U;
                        }
                    }
                    return result;
                }(),
            .sliding_contact_count =
                [this]() {
                    std::size_t result = 0;
                    if (contacts_ != nullptr) {
                        for (const physics_qopt::ContactState3D& state : contacts_->states()) {
                            result += state.sliding ? 1U : 0U;
                        }
                    }
                    return result;
                }(),
            .cached_contact_count = contacts_ != nullptr ? contacts_->cached_contact_count() : 0,
            .warm_started_contact_count = contacts_ != nullptr ? contacts_->warm_started_contact_count() : 0,
            .minimum_contact_gap =
                [this]() {
                    if (contacts_ == nullptr || contacts_->states().empty()) {
                        return 0.0;
                    }
                    double result = std::numeric_limits<double>::infinity();
                    for (const physics_qopt::ContactState3D& state : contacts_->states()) {
                        result = std::min(result, state.signed_gap);
                    }
                    return result;
                }(),
            .normal_impulse_sum =
                [this]() {
                    double result = 0.0;
                    if (contacts_ != nullptr) {
                        for (const physics_qopt::ContactState3D& state : contacts_->states()) {
                            result += std::max(state.normal_impulse, 0.0);
                        }
                    }
                    return result;
                }(),
            .normal_reaction_sum =
                [this]() {
                    double result = 0.0;
                    if (contacts_ != nullptr) {
                        for (const physics_qopt::ContactState3D& state : contacts_->states()) {
                            result += std::max(state.normal_reaction, 0.0);
                        }
                    }
                    return result;
                }(),
            .normal_reaction_linf =
                [this]() {
                    double result = 0.0;
                    if (contacts_ != nullptr) {
                        for (const physics_qopt::ContactState3D& state : contacts_->states()) {
                            result = std::max(result, std::abs(state.normal_reaction));
                        }
                    }
                    return result;
                }(),
            .tangent_impulse_sum =
                [this]() {
                    double result = 0.0;
                    if (contacts_ != nullptr) {
                        for (const physics_qopt::ContactState3D& state : contacts_->states()) {
                            result += state.tangent_impulse_world.norm();
                        }
                    }
                    return result;
                }(),
            .tangent_speed_linf =
                [this]() {
                    double result = 0.0;
                    if (contacts_ != nullptr) {
                        for (const physics_qopt::ContactState3D& state : contacts_->states()) {
                            result = std::max(result, state.tangent_velocity_world.norm());
                        }
                    }
                    return result;
                }(),
            .friction_capacity_sum =
                [this]() {
                    double result = 0.0;
                    if (contacts_ != nullptr) {
                        const auto& contacts = contacts_->contacts();
                        const auto& states = contacts_->states();
                        const std::size_t count = std::min(contacts.size(), states.size());
                        for (std::size_t index = 0; index < count; ++index) {
                            result +=
                                contacts[index].friction_coefficient * std::max(states[index].normal_impulse, 0.0);
                        }
                    }
                    return result;
                }(),
            .friction_work =
                [this]() {
                    double result = 0.0;
                    if (contacts_ != nullptr) {
                        for (const physics_qopt::ContactState3D& state : contacts_->states()) {
                            result += state.friction_work;
                        }
                    }
                    return result;
                }(),
            .motor_effort_linf =
                [this]() {
                    double result = 0.0;
                    for (const FEMArticulationComponent* articulation : articulations_) {
                        if (articulation == nullptr) {
                            continue;
                        }
                        for (const FEMArticulationMotorComponent* motor : articulation->motors_) {
                            if (motor != nullptr) {
                                result = std::max(result, std::abs(motor->applied_effort()));
                            }
                        }
                    }
                    return result;
                }(),
            .motor_power =
                [this]() {
                    double result = 0.0;
                    for (const FEMArticulationComponent* articulation : articulations_) {
                        if (articulation == nullptr) {
                            continue;
                        }
                        for (const FEMArticulationMotorComponent* motor : articulation->motors_) {
                            if (motor != nullptr) {
                                const double power = motor->power();
                                if (std::isfinite(power)) {
                                    result += power;
                                }
                            }
                        }
                    }
                    return result;
                }(),
            .motor_work = motor_work_,
            .initial_total_energy = initial_total_energy_,
            .total_energy = total_energy(),
        };
    }
    double FEMPhysicsWorldComponent::total_energy() const noexcept {
        double result = 0.0;
        for (const FEMRigidBodyComponent* body : bodies_) {
            if (body != nullptr && body->body_ != nullptr) {
                result += body->body_->total_energy();
            }
        }
        for (const FEMArticulationComponent* articulation : articulations_) {
            if (articulation != nullptr && articulation->dynamics_ != nullptr) {
                result += articulation->dynamics_->total_energy();
            }
        }
        return result;
    }

    void FEMPhysicsWorldComponent::clear_runtime_links() {
        for (FEMRigidBodyComponent* body : bodies_) {
            if (body != nullptr && body->world_ == this) {
                body->world_ = nullptr;
                body->body_ = nullptr;
                body->force_ = nullptr;
                body->articulation_ = nullptr;
                body->articulation_unit_index_ = robotics::articulation_root_frame;
                body->articulation_base_ = false;
            }
        }
        for (FEMFixedJointComponent* joint : fixed_joints_) {
            if (joint != nullptr && joint->world_ == this) {
                joint->world_ = nullptr;
                joint->joint_ = nullptr;
                joint->body_ = nullptr;
            }
        }
        for (FEMRevoluteJointComponent* joint : revolute_joints_) {
            if (joint != nullptr && joint->world_ == this) {
                joint->world_ = nullptr;
                joint->joint_ = nullptr;
                joint->body_a_ = nullptr;
                joint->body_b_ = nullptr;
            }
        }
        for (FEMArticulationComponent* articulation : articulations_) {
            if (articulation == nullptr || articulation->world_ != this) {
                continue;
            }
            if (articulation->base_body_ != nullptr && articulation->base_body_->world_ == this) {
                articulation->base_body_->world_ = nullptr;
                articulation->base_body_->body_ = nullptr;
                articulation->base_body_->force_ = nullptr;
                articulation->base_body_->articulation_ = nullptr;
                articulation->base_body_->articulation_unit_index_ = robotics::articulation_root_frame;
                articulation->base_body_->articulation_base_ = false;
            }
            articulation->base_body_ = nullptr;
            for (FEMRigidBodyComponent* body : articulation->bodies_) {
                if (body != nullptr && body->world_ == this) {
                    body->world_ = nullptr;
                    body->body_ = nullptr;
                    body->force_ = nullptr;
                    body->articulation_ = nullptr;
                    body->articulation_unit_index_ = robotics::articulation_root_frame;
                    body->articulation_base_ = false;
                }
            }
            articulation->bodies_.clear();
            articulation->joint_entities_.clear();
            articulation->joint_coordinate_scales_.clear();
            for (FEMArticulationMotorComponent* motor : articulation->motors_) {
                if (motor != nullptr && motor->world_ == this) {
                    motor->world_ = nullptr;
                    motor->articulation_ = nullptr;
                    motor->motor_ = nullptr;
                }
            }
            articulation->motors_.clear();
            for (FEMJointServoComponent* servo : articulation->servos_) {
                if (servo != nullptr && servo->world_ == this) {
                    servo->world_ = nullptr;
                    servo->joint_ = nullptr;
                    servo->motor_component_ = nullptr;
                    servo->articulation_ = nullptr;
                    servo->position_effort_ = 0.0;
                    servo->velocity_effort_ = 0.0;
                    servo->integral_effort_ = 0.0;
                    servo->commanded_effort_ = 0.0;
                }
            }
            articulation->servos_.clear();
            articulation->motor_ = nullptr;
            articulation->dynamics_ = nullptr;
            articulation->articulation_ = nullptr;
            articulation->articulation_owner_ = nullptr;
            articulation->world_ = nullptr;
        }
        bodies_.clear();
        fixed_joints_.clear();
        revolute_joints_.clear();
        articulations_.clear();
        contacts_ = nullptr;
        warned_contact_colliders_.clear();
    }

    void FEMPhysicsWorldComponent::detach(FEMArticulationComponent&) noexcept {
        // Dynamics contributions borrow their Articulation3D from the scene
        // component. Destroy the complete solver before that component can
        // release its model; a partially detached finalized system is not a
        // valid runtime state.
        initialized_ = false;
        system_ = physics_qopt::Multibody3DSystem();
        clear_runtime_links();
    }

    void FEMPhysicsWorldComponent::detach(FEMArticulationMotorComponent& component) noexcept {
        initialized_ = false;
        for (FEMArticulationComponent* articulation : articulations_) {
            if (articulation == nullptr) {
                continue;
            }
            for (FEMArticulationMotorComponent*& motor : articulation->motors_) {
                if (motor == &component) {
                    motor = nullptr;
                }
            }
            for (FEMJointServoComponent* servo : articulation->servos_) {
                if (servo != nullptr && servo->motor_component_ == &component) {
                    servo->world_ = nullptr;
                    servo->joint_ = nullptr;
                    servo->motor_component_ = nullptr;
                    servo->articulation_ = nullptr;
                    servo->position_effort_ = 0.0;
                    servo->velocity_effort_ = 0.0;
                    servo->integral_effort_ = 0.0;
                    servo->commanded_effort_ = 0.0;
                }
            }
        }
        component.world_ = nullptr;
        component.articulation_ = nullptr;
        component.motor_ = nullptr;
    }

    void FEMPhysicsWorldComponent::detach(FEMJointServoComponent& component) noexcept {
        initialized_ = false;
        for (FEMArticulationComponent* articulation : articulations_) {
            if (articulation == nullptr) {
                continue;
            }
            for (FEMJointServoComponent*& servo : articulation->servos_) {
                if (servo == &component) {
                    servo = nullptr;
                }
            }
        }
        component.world_ = nullptr;
        component.joint_ = nullptr;
        component.motor_component_ = nullptr;
        component.articulation_ = nullptr;
        component.position_effort_ = 0.0;
        component.velocity_effort_ = 0.0;
        component.integral_effort_ = 0.0;
        component.commanded_effort_ = 0.0;
    }

    void FEMPhysicsWorldComponent::detach(FEMRigidBodyComponent& component) noexcept {
        initialized_ = false;
        for (FEMRigidBodyComponent*& candidate : bodies_) {
            if (candidate == &component) {
                candidate = nullptr;
            }
        }
        for (FEMArticulationComponent* articulation : articulations_) {
            if (articulation == nullptr) {
                continue;
            }
            if (articulation->base_body_ == &component) {
                articulation->base_body_ = nullptr;
            }
            for (FEMRigidBodyComponent*& candidate : articulation->bodies_) {
                if (candidate == &component) {
                    candidate = nullptr;
                }
            }
        }
        component.body_ = nullptr;
        component.force_ = nullptr;
        component.articulation_ = nullptr;
        component.articulation_unit_index_ = robotics::articulation_root_frame;
        component.articulation_base_ = false;
        component.world_ = nullptr;
    }

    void FEMPhysicsWorldComponent::detach(FEMFixedJointComponent& component) noexcept {
        initialized_ = false;
        for (FEMFixedJointComponent*& candidate : fixed_joints_) {
            if (candidate == &component) {
                candidate = nullptr;
            }
        }
        component.joint_ = nullptr;
        component.body_ = nullptr;
        component.world_ = nullptr;
    }

    void FEMPhysicsWorldComponent::detach(FEMRevoluteJointComponent& component) noexcept {
        initialized_ = false;
        for (FEMRevoluteJointComponent*& candidate : revolute_joints_) {
            if (candidate == &component) {
                candidate = nullptr;
            }
        }
        component.joint_ = nullptr;
        component.body_a_ = nullptr;
        component.body_b_ = nullptr;
        component.world_ = nullptr;
    }

} // namespace termin
