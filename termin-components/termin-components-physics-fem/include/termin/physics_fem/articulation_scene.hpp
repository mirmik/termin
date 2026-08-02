#pragma once

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

#include <termin/entity/entity.hpp>
#include <termin/physics_fem/components.hpp>
#include <termin/qopt/articulation3d.hpp>

namespace termin
{
    class KinematicUnitComponent;

    enum class FEMArticulationSceneDiagnostic : std::uint8_t
    {
        None,
        InvalidRoot,
        EmptyArticulation,
        NonRigidTransform,
        UnsupportedJoint,
        DegenerateJointAxis,
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
        std::vector<qopt::ArticulationLink3D> links;
        qopt::Articulation3DState state;
        std::vector<FEMArticulationSceneBinding> bindings;

        [[nodiscard]] bool ok() const noexcept
        {
            return diagnostic == FEMArticulationSceneDiagnostic::None;
        }
    };

    // Compiles the strict alternating hierarchy
    // articulation root -> kinematic joint entity -> rigid body entity.
    // Every body may contain more joint entities, which naturally forms a
    // topologically ordered reduced-coordinate tree.
    [[nodiscard]] ENTITY_API FEMArticulationSceneCompilation
    compile_fem_articulation_scene(Entity root);

} // namespace termin
