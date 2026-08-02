#include <termin/physics_fem/articulation_scene.hpp>

#include <cmath>
#include <functional>
#include <unordered_set>

#include <components/actuator_component.hpp>
#include <components/kinematic_unit_component.hpp>
#include <components/rotator_component.hpp>
#include <termin/geom/general_pose3.hpp>

namespace termin
{
    namespace
    {
        constexpr double rigid_tolerance = 1.0e-10;
        constexpr double axis_tolerance = 1.0e-10;

        std::string entity_name(Entity entity)
        {
            const char* name = entity.name();
            return name != nullptr ? name : "<unnamed>";
        }

        bool unit_scale(Vec3 scale)
        {
            return scale.is_finite() &&
                   std::abs(scale.x - 1.0) <= rigid_tolerance &&
                   std::abs(scale.y - 1.0) <= rigid_tolerance &&
                   std::abs(scale.z - 1.0) <= rigid_tolerance;
        }

        bool local_rigid_pose(Entity entity, Pose3& result)
        {
            const GeneralPose3 pose = entity.transform().local_pose();
            if (!unit_scale(pose.scale) || !pose.ang.is_finite() ||
                pose.ang.norm() <= rigid_tolerance || !pose.lin.is_finite())
            {
                return false;
            }
            result = Pose3{pose.ang.normalized(), pose.lin};
            return true;
        }

        bool joint_zero_pose(const KinematicUnitComponent& joint, Pose3& result)
        {
            const Vec3 scale{
                joint.base_scale.x, joint.base_scale.y, joint.base_scale.z};
            const Quat rotation{joint.base_rotation.x,
                                joint.base_rotation.y,
                                joint.base_rotation.z,
                                joint.base_rotation.w};
            const Vec3 position{joint.base_position.x,
                                joint.base_position.y,
                                joint.base_position.z};
            if (!unit_scale(scale) || !rotation.is_finite() ||
                rotation.norm() <= rigid_tolerance || !position.is_finite())
            {
                return false;
            }
            result = Pose3{rotation.normalized(), position};
            return true;
        }

        Screw3 joint_motion_twist(const KinematicUnitComponent& joint)
        {
            const Vec3 axis = joint.get_axis();
            if (dynamic_cast<const RotatorComponent*>(&joint) != nullptr)
            {
                return {axis, Vec3::zero()};
            }
            if (dynamic_cast<const ActuatorComponent*>(&joint) != nullptr)
            {
                return {Vec3::zero(), axis};
            }
            return Screw3::zero();
        }

    } // namespace

    std::string_view fem_articulation_scene_diagnostic_name(
        FEMArticulationSceneDiagnostic diagnostic) noexcept
    {
        switch (diagnostic)
        {
        case FEMArticulationSceneDiagnostic::None:
            return "none";
        case FEMArticulationSceneDiagnostic::InvalidRoot:
            return "invalid-root";
        case FEMArticulationSceneDiagnostic::EmptyArticulation:
            return "empty-articulation";
        case FEMArticulationSceneDiagnostic::NonRigidTransform:
            return "non-rigid-transform";
        case FEMArticulationSceneDiagnostic::UnsupportedJoint:
            return "unsupported-joint";
        case FEMArticulationSceneDiagnostic::DegenerateJointAxis:
            return "degenerate-joint-axis";
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

    FEMArticulationSceneCompilation compile_fem_articulation_scene(Entity root)
    {
        FEMArticulationSceneCompilation result;
        if (!root.valid() ||
            root.get_component<FEMArticulationComponent>() == nullptr)
        {
            result.diagnostic = FEMArticulationSceneDiagnostic::InvalidRoot;
            return result;
        }

        const std::optional<Pose3> root_pose =
            root.transform().try_rigid_pose();
        if (!root_pose.has_value())
        {
            result.diagnostic =
                FEMArticulationSceneDiagnostic::NonRigidTransform;
            result.diagnostic_entity = entity_name(root);
            return result;
        }

        std::unordered_set<FEMRigidBodyComponent*> compiled_bodies;
        const auto fail =
            [&result](FEMArticulationSceneDiagnostic diagnostic, Entity entity)
        {
            if (result.diagnostic == FEMArticulationSceneDiagnostic::None)
            {
                result.diagnostic = diagnostic;
                result.diagnostic_entity = entity_name(entity);
            }
        };

        std::function<void(Entity, std::size_t)> compile_children;
        compile_children = [&](Entity parent_entity, std::size_t parent_link)
        {
            for (Entity joint_entity : parent_entity.children())
            {
                if (result.diagnostic != FEMArticulationSceneDiagnostic::None)
                {
                    return;
                }
                KinematicUnitComponent* joint =
                    joint_entity.get_component<KinematicUnitComponent>();
                if (joint == nullptr || !joint->enabled())
                {
                    continue;
                }
                if (dynamic_cast<RotatorComponent*>(joint) == nullptr &&
                    dynamic_cast<ActuatorComponent*>(joint) == nullptr)
                {
                    fail(FEMArticulationSceneDiagnostic::UnsupportedJoint,
                         joint_entity);
                    return;
                }

                Pose3 parent_to_joint_zero;
                if (!joint_zero_pose(*joint, parent_to_joint_zero))
                {
                    fail(FEMArticulationSceneDiagnostic::NonRigidTransform,
                         joint_entity);
                    return;
                }
                if (parent_link == qopt::articulation_world_link)
                {
                    parent_to_joint_zero =
                        (*root_pose * parent_to_joint_zero).normalized();
                }

                const Screw3 motion_twist = joint_motion_twist(*joint);
                if (!motion_twist.is_finite() ||
                    joint->get_axis().norm() <= axis_tolerance ||
                    !std::isfinite(joint->coordinate))
                {
                    fail(FEMArticulationSceneDiagnostic::DegenerateJointAxis,
                         joint_entity);
                    return;
                }

                FEMRigidBodyComponent* body = nullptr;
                Entity body_entity;
                for (Entity child : joint_entity.children())
                {
                    FEMRigidBodyComponent* candidate =
                        child.get_component<FEMRigidBodyComponent>();
                    if (candidate == nullptr || !candidate->enabled())
                    {
                        continue;
                    }
                    if (body != nullptr)
                    {
                        fail(FEMArticulationSceneDiagnostic::MultipleBodies,
                             joint_entity);
                        return;
                    }
                    body = candidate;
                    body_entity = child;
                }
                if (body == nullptr)
                {
                    fail(FEMArticulationSceneDiagnostic::MissingBody,
                         joint_entity);
                    return;
                }
                if (body_entity.get_component<FEMArticulationComponent>() !=
                    nullptr)
                {
                    fail(FEMArticulationSceneDiagnostic::NestedArticulation,
                         body_entity);
                    return;
                }
                if (!compiled_bodies.insert(body).second)
                {
                    fail(FEMArticulationSceneDiagnostic::DuplicateBody,
                         body_entity);
                    return;
                }

                Pose3 joint_to_link;
                if (!local_rigid_pose(body_entity, joint_to_link))
                {
                    fail(FEMArticulationSceneDiagnostic::NonRigidTransform,
                         body_entity);
                    return;
                }

                SpatialInertia3 inertia;
                inertia.mass = body->mass;
                inertia.principal_moments = {
                    body->inertia_diagonal.x,
                    body->inertia_diagonal.y,
                    body->inertia_diagonal.z,
                };
                inertia.inertia_frame = Pose3::identity();

                const std::size_t link_index = result.links.size();
                result.links.push_back({
                    .parent_link = parent_link,
                    .parent_to_joint_zero = parent_to_joint_zero,
                    .motion_twist_at_joint = motion_twist,
                    .joint_to_link = joint_to_link,
                    .inertia = inertia,
                    .diagnostic_name = entity_name(body_entity),
                });
                result.state.coordinates.push_back(joint->coordinate);
                result.state.velocities.push_back(0.0);
                result.bindings.push_back({
                    .joint = joint,
                    .body = body,
                    .joint_entity = joint_entity,
                    .body_entity = body_entity,
                });
                compile_children(body_entity, link_index);
            }
        };

        compile_children(root, qopt::articulation_world_link);
        if (result.diagnostic == FEMArticulationSceneDiagnostic::None &&
            result.links.empty())
        {
            result.diagnostic =
                FEMArticulationSceneDiagnostic::EmptyArticulation;
            result.diagnostic_entity = entity_name(root);
        }
        return result;
    }

} // namespace termin
