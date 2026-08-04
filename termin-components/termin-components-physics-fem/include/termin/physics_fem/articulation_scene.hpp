#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include <termin/entity/entity.hpp>
#include <termin/physics_fem/components.hpp>
#include <termin/robotics/articulation3d.hpp>

namespace termin
{
    class KinematicUnitComponent;

    enum class FEMArticulationSceneDiagnostic : std::uint8_t
    {
        None,
        InvalidRoot,
        InvalidBaseMode,
        MissingRootBody,
        UnexpectedRootBody,
        EmptyArticulation,
        NonRigidTransform,
        UnsupportedJoint,
        DegenerateJointAxis,
        InvalidJointLimits,
        MissingBody,
        MultipleBodies,
        DuplicateBody,
        NestedArticulation,
    };

    [[nodiscard]] ENTITY_API std::string_view
    fem_articulation_scene_diagnostic_name(
        FEMArticulationSceneDiagnostic diagnostic) noexcept;

    struct FEMArticulationSceneBinding
    {
        KinematicUnitComponent* joint = nullptr;
        FEMRigidBodyComponent* body = nullptr;
        FEMArticulationMotorComponent* motor = nullptr;
        FEMJointServoComponent* servo = nullptr;
        Entity joint_entity;
        Entity body_entity;
        // Authored coordinate units per SI generalized coordinate. The qopt
        // articulation always stores radians or metres.
        double coordinate_scale = 1.0;
    };

    struct FEMArticulationSceneCompilation
    {
        FEMArticulationSceneDiagnostic diagnostic =
            FEMArticulationSceneDiagnostic::None;
        std::string diagnostic_entity;
        std::vector<robotics::ArticulationUnit3D> units;
        robotics::Articulation3DState state;
        std::optional<robotics::ArticulationFloatingBase3D> floating_base;
        FEMRigidBodyComponent* base_body = nullptr;
        Entity base_entity;
        std::vector<FEMArticulationSceneBinding> bindings;

        [[nodiscard]] bool ok() const noexcept
        {
            return diagnostic == FEMArticulationSceneDiagnostic::None;
        }
    };

    // Compiles the strict alternating hierarchy rooted at an articulation
    // frame. A fixed root is only a frame. A floating root also owns its
    // FEMRigidBodyComponent, which becomes the physical base body. Below it,
    // kinematic joint entity -> rigid body entity alternation forms a
    // topologically ordered reduced-coordinate tree.
    [[nodiscard]] ENTITY_API FEMArticulationSceneCompilation
    compile_fem_articulation_scene(Entity root);

} // namespace termin
