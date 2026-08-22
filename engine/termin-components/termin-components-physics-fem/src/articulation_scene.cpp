#include <termin/physics_fem/articulation_scene.hpp>

#include <cmath>
#include <functional>
#include <unordered_set>

#include <components/actuator_component.hpp>
#include <components/articulation_component.hpp>
#include <components/kinematic_unit_component.hpp>
#include <components/rotator_component.hpp>
#include <termin/geom/general_pose3.hpp>

namespace termin {
    namespace {
        constexpr double rigid_tolerance = 1.0e-10;
        constexpr double axis_tolerance = 1.0e-10;

        std::string entity_name(Entity entity) {
            const char* name = entity.name();
            return name != nullptr ? name : "<unnamed>";
        }

        bool unit_scale(Vec3 scale) {
            return scale.is_finite() && std::abs(scale.x - 1.0) <= rigid_tolerance &&
                   std::abs(scale.y - 1.0) <= rigid_tolerance && std::abs(scale.z - 1.0) <= rigid_tolerance;
        }

        bool local_rigid_pose(Entity entity, Pose3& result) {
            const GeneralPose3 pose = entity.transform().local_pose();
            if (!unit_scale(pose.scale) || !pose.ang.is_finite() || pose.ang.norm() <= rigid_tolerance ||
                !pose.lin.is_finite()) {
                return false;
            }
            result = Pose3{pose.ang.normalized(), pose.lin};
            return true;
        }

        bool joint_zero_pose(const KinematicUnitComponent& joint, Pose3& result) {
            const Quat rotation = joint.origin_rotation;
            const Vec3 position = joint.origin_position;
            if (!rotation.is_finite() || rotation.norm() <= rigid_tolerance || !position.is_finite()) {
                return false;
            }
            result = Pose3{rotation.normalized(), position};
            return true;
        }

        Screw3 joint_motion_twist(const KinematicUnitComponent& joint) {
            const Vec3 axis = joint.get_axis();
            if (dynamic_cast<const RotatorComponent*>(&joint) != nullptr) {
                return {axis, Vec3::zero()};
            }
            if (dynamic_cast<const ActuatorComponent*>(&joint) != nullptr) {
                return {Vec3::zero(), axis};
            }
            return Screw3::zero();
        }

        SpatialInertia3 body_inertia(const FEMRigidBodyComponent& body) {
            SpatialInertia3 inertia;
            inertia.mass = body.mass;
            inertia.principal_moments = {
                body.inertia_diagonal.x,
                body.inertia_diagonal.y,
                body.inertia_diagonal.z,
            };
            inertia.inertia_frame = Pose3::identity();
            return inertia;
        }

        std::vector<FEMRigidBodyComponent*> enabled_bodies(Entity entity) {
            std::vector<FEMRigidBodyComponent*> result;
            for (std::size_t index = 0; index < entity.component_count(); ++index) {
                tc_component* component = entity.component_at(index);
                if (component == nullptr || component->kind != TC_CXX_COMPONENT) {
                    continue;
                }
                auto* body = dynamic_cast<FEMRigidBodyComponent*>(CxxComponent::from_tc(component));
                if (body != nullptr && body->enabled()) {
                    result.push_back(body);
                }
            }
            return result;
        }

    } // namespace

    std::string_view fem_articulation_scene_diagnostic_name(FEMArticulationSceneDiagnostic diagnostic) noexcept {
        switch (diagnostic) {
        case FEMArticulationSceneDiagnostic::None:
            return "none";
        case FEMArticulationSceneDiagnostic::InvalidRoot:
            return "invalid-root";
        case FEMArticulationSceneDiagnostic::InvalidBaseMode:
            return "invalid-base-mode";
        case FEMArticulationSceneDiagnostic::MissingRootBody:
            return "missing-root-body";
        case FEMArticulationSceneDiagnostic::UnexpectedRootBody:
            return "unexpected-root-body";
        case FEMArticulationSceneDiagnostic::EmptyArticulation:
            return "empty-articulation";
        case FEMArticulationSceneDiagnostic::NonRigidTransform:
            return "non-rigid-transform";
        case FEMArticulationSceneDiagnostic::UnsupportedJoint:
            return "unsupported-joint";
        case FEMArticulationSceneDiagnostic::DegenerateJointAxis:
            return "degenerate-joint-axis";
        case FEMArticulationSceneDiagnostic::InvalidJointLimits:
            return "invalid-joint-limits";
        case FEMArticulationSceneDiagnostic::MissingBody:
            return "missing-body";
        case FEMArticulationSceneDiagnostic::MultipleBodies:
            return "multiple-bodies";
        case FEMArticulationSceneDiagnostic::DuplicateBody:
            return "duplicate-body";
        case FEMArticulationSceneDiagnostic::NestedArticulation:
            return "nested-articulation";
        }
        return "unknown";
    }

    FEMArticulationSceneCompilation compile_fem_articulation_scene(Entity root) {
        FEMArticulationSceneCompilation result;
        if (!root.valid() || root.get_component<FEMArticulationComponent>() == nullptr) {
            result.diagnostic = FEMArticulationSceneDiagnostic::InvalidRoot;
            return result;
        }

        FEMArticulationComponent* articulation = root.get_component<FEMArticulationComponent>();
        const bool floating = articulation->base_mode == static_cast<int>(FEMArticulationBaseMode::Floating);
        if (!floating && articulation->base_mode != static_cast<int>(FEMArticulationBaseMode::Fixed)) {
            result.diagnostic = FEMArticulationSceneDiagnostic::InvalidBaseMode;
            result.diagnostic_entity = entity_name(root);
            return result;
        }

        // The native authoring path shares the exact Articulation3D compiled
        // by ArticulationComponent. FEM contributes dynamics and actuation but
        // does not compile or own a parallel kinematic model.
        ArticulationComponent* owner = root.get_component<ArticulationComponent>();
        if (owner != nullptr && owner->enabled()) {
            if (floating) {
                result.diagnostic = FEMArticulationSceneDiagnostic::InvalidBaseMode;
                result.diagnostic_entity = entity_name(root);
                return result;
            }
            if (!owner->initialized() && !owner->rebuild()) {
                result.diagnostic = FEMArticulationSceneDiagnostic::EmptyArticulation;
                result.diagnostic_entity = entity_name(root);
                return result;
            }
            std::shared_ptr<robotics::Articulation3D> model = owner->articulation_shared();
            if (model == nullptr || model->unit_count() == 0) {
                result.diagnostic = FEMArticulationSceneDiagnostic::EmptyArticulation;
                result.diagnostic_entity = entity_name(root);
                return result;
            }

            result.articulation_owner = owner;
            result.borrowed_articulation = model;
            result.bindings.reserve(model->unit_count());
            for (std::size_t index = 0; index < model->unit_count(); ++index) {
                KinematicUnitComponent* unit = owner->unit_component(index);
                const double coordinate_scale = owner->unit_coordinate_scale(index);
                if (unit == nullptr || !std::isfinite(coordinate_scale) || coordinate_scale <= 0.0) {
                    result.diagnostic = FEMArticulationSceneDiagnostic::DegenerateJointAxis;
                    result.diagnostic_entity = entity_name(root);
                    return result;
                }
                Entity unit_entity = unit->entity();
                FEMRigidBodyComponent* body = nullptr;
                Entity body_entity;
                for (Entity child : unit_entity.children()) {
                    // A direct KinematicUnit child is another articulation
                    // unit, not a legacy body anchor for this one.
                    if (child.get_component<KinematicUnitComponent>() != nullptr) {
                        continue;
                    }
                    const std::vector<FEMRigidBodyComponent*> candidates = enabled_bodies(child);
                    if (candidates.empty()) {
                        continue;
                    }
                    if (body != nullptr || candidates.size() > 1) {
                        result.diagnostic = FEMArticulationSceneDiagnostic::MultipleBodies;
                        result.diagnostic_entity = entity_name(unit_entity);
                        return result;
                    }
                    body = candidates.front();
                    body_entity = child;
                }
                result.bindings.push_back({
                    .joint = unit,
                    .body = body,
                    .motor = unit_entity.get_component<FEMArticulationMotorComponent>(),
                    .servo = unit_entity.get_component<FEMJointServoComponent>(),
                    .joint_entity = unit_entity,
                    .body_entity = body_entity,
                    .coordinate_scale = coordinate_scale,
                });
            }
            return result;
        }

        const std::optional<Pose3> root_pose = root.transform().try_rigid_pose();
        if (!root_pose.has_value()) {
            result.diagnostic = FEMArticulationSceneDiagnostic::NonRigidTransform;
            result.diagnostic_entity = entity_name(root);
            return result;
        }

        const std::vector<FEMRigidBodyComponent*> root_bodies = enabled_bodies(root);
        if (root_bodies.size() > 1) {
            result.diagnostic = FEMArticulationSceneDiagnostic::MultipleBodies;
            result.diagnostic_entity = entity_name(root);
            return result;
        }
        FEMRigidBodyComponent* root_body = root_bodies.empty() ? nullptr : root_bodies.front();
        if (floating && root_body == nullptr) {
            result.diagnostic = FEMArticulationSceneDiagnostic::MissingRootBody;
            result.diagnostic_entity = entity_name(root);
            return result;
        }
        if (!floating && root_body != nullptr) {
            result.diagnostic = FEMArticulationSceneDiagnostic::UnexpectedRootBody;
            result.diagnostic_entity = entity_name(root);
            return result;
        }
        if (floating) {
            result.base_body = root_body;
            result.base_entity = root;
            result.floating_base = robotics::ArticulationFloatingBase3D{
                .inertia = body_inertia(*root_body),
                .pose_world = *root_pose,
                .velocity_local = Screw3::zero(),
                .diagnostic_name = entity_name(root),
            };
        }

        std::unordered_set<FEMRigidBodyComponent*> compiled_bodies;
        const auto fail = [&result](FEMArticulationSceneDiagnostic diagnostic, Entity entity) {
            if (result.diagnostic == FEMArticulationSceneDiagnostic::None) {
                result.diagnostic = diagnostic;
                result.diagnostic_entity = entity_name(entity);
            }
        };

        std::function<void(Entity, std::size_t)> compile_children;
        compile_children = [&](Entity parent_entity, std::size_t parent_unit) {
            for (Entity joint_entity : parent_entity.children()) {
                if (result.diagnostic != FEMArticulationSceneDiagnostic::None) {
                    return;
                }
                KinematicUnitComponent* joint = joint_entity.get_component<KinematicUnitComponent>();
                if (joint == nullptr || !joint->enabled()) {
                    continue;
                }
                if (dynamic_cast<RotatorComponent*>(joint) == nullptr &&
                    dynamic_cast<ActuatorComponent*>(joint) == nullptr) {
                    fail(FEMArticulationSceneDiagnostic::UnsupportedJoint, joint_entity);
                    return;
                }

                Pose3 parent_to_unit_zero;
                Pose3 current_joint_pose;
                if (!local_rigid_pose(joint_entity, current_joint_pose) ||
                    !joint_zero_pose(*joint, parent_to_unit_zero)) {
                    fail(FEMArticulationSceneDiagnostic::NonRigidTransform, joint_entity);
                    return;
                }
                if (!floating && parent_unit == robotics::articulation_root_frame) {
                    parent_to_unit_zero = (*root_pose * parent_to_unit_zero).normalized();
                }

                const Screw3 motion_twist = joint_motion_twist(*joint);
                if (!motion_twist.is_finite() || joint->get_axis().norm() <= axis_tolerance ||
                    !std::isfinite(joint->coordinate)) {
                    fail(FEMArticulationSceneDiagnostic::DegenerateJointAxis, joint_entity);
                    return;
                }

                FEMRigidBodyComponent* body = nullptr;
                Entity body_entity;
                for (Entity child : joint_entity.children()) {
                    const std::vector<FEMRigidBodyComponent*> candidates = enabled_bodies(child);
                    if (candidates.empty()) {
                        continue;
                    }
                    if (body != nullptr || candidates.size() > 1) {
                        fail(FEMArticulationSceneDiagnostic::MultipleBodies, joint_entity);
                        return;
                    }
                    body = candidates.front();
                    body_entity = child;
                }
                if (body == nullptr) {
                    fail(FEMArticulationSceneDiagnostic::MissingBody, joint_entity);
                    return;
                }
                if (body_entity.get_component<FEMArticulationComponent>() != nullptr) {
                    fail(FEMArticulationSceneDiagnostic::NestedArticulation, body_entity);
                    return;
                }
                if (!compiled_bodies.insert(body).second) {
                    fail(FEMArticulationSceneDiagnostic::DuplicateBody, body_entity);
                    return;
                }

                Pose3 joint_to_unit;
                if (!local_rigid_pose(body_entity, joint_to_unit)) {
                    fail(FEMArticulationSceneDiagnostic::NonRigidTransform, body_entity);
                    return;
                }

                const double coordinate_scale = joint->get_coordinate_scale();
                if (!std::isfinite(coordinate_scale) || coordinate_scale <= 0.0) {
                    fail(FEMArticulationSceneDiagnostic::DegenerateJointAxis, joint_entity);
                    return;
                }
                robotics::ArticulationUnitLimits3D limits;
                FEMJointLimitComponent* authored_limits = joint_entity.get_component<FEMJointLimitComponent>();
                if (authored_limits != nullptr && authored_limits->enabled()) {
                    if ((authored_limits->minimum_enabled && !std::isfinite(authored_limits->minimum_coordinate)) ||
                        (authored_limits->maximum_enabled && !std::isfinite(authored_limits->maximum_coordinate)) ||
                        (authored_limits->minimum_enabled && authored_limits->maximum_enabled &&
                         authored_limits->minimum_coordinate > authored_limits->maximum_coordinate)) {
                        fail(FEMArticulationSceneDiagnostic::InvalidJointLimits, joint_entity);
                        return;
                    }
                    if (authored_limits->minimum_enabled) {
                        limits.minimum = authored_limits->minimum_coordinate * coordinate_scale;
                    }
                    if (authored_limits->maximum_enabled) {
                        limits.maximum = authored_limits->maximum_coordinate * coordinate_scale;
                    }
                }

                const std::size_t unit_index = result.units.size();
                result.units.push_back({
                    .parent_unit = parent_unit,
                    .parent_to_unit_zero = (parent_to_unit_zero * joint_to_unit).normalized(),
                    .motion_twist_at_unit = motion_twist.adjoint_inv(joint_to_unit),
                    .inertia = body_inertia(*body),
                    .limits = limits,
                    .diagnostic_name = entity_name(body_entity),
                });
                result.state.coordinates.push_back(joint->coordinate * coordinate_scale);
                result.state.velocities.push_back(0.0);
                result.bindings.push_back({
                    .joint = joint,
                    .body = body,
                    .motor = joint_entity.get_component<FEMArticulationMotorComponent>(),
                    .servo = joint_entity.get_component<FEMJointServoComponent>(),
                    .joint_entity = joint_entity,
                    .body_entity = body_entity,
                    .coordinate_scale = coordinate_scale,
                });
                compile_children(body_entity, unit_index);
            }
        };

        compile_children(root, robotics::articulation_root_frame);
        if (result.diagnostic == FEMArticulationSceneDiagnostic::None && result.units.empty()) {
            result.diagnostic = FEMArticulationSceneDiagnostic::EmptyArticulation;
            result.diagnostic_entity = entity_name(root);
        }
        return result;
    }

} // namespace termin
