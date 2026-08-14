#pragma once

#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include <termin/entity/entity.hpp>
#include <termin/physics_fem/components.hpp>
#include <termin/robotics/articulation3d.hpp>

namespace termin {
    class ArticulationComponent;
    class KinematicUnitComponent;

    enum class FEMArticulationSceneDiagnostic : std::uint8_t {
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
    fem_articulation_scene_diagnostic_name(FEMArticulationSceneDiagnostic diagnostic) noexcept;

    struct FEMArticulationSceneBinding {
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

    struct FEMArticulationSceneCompilation {
        FEMArticulationSceneDiagnostic diagnostic = FEMArticulationSceneDiagnostic::None;
        std::string diagnostic_entity;
        std::vector<robotics::ArticulationUnit3D> units;
        robotics::Articulation3DState state;
        std::optional<robotics::ArticulationFloatingBase3D> floating_base;
        // Target authoring path: FEM borrows the solver-neutral model owned by
        // the co-located ArticulationComponent. Empty for the transitional
        // joint/body grammar below.
        ArticulationComponent* articulation_owner = nullptr;
        std::shared_ptr<robotics::Articulation3D> borrowed_articulation;
        FEMRigidBodyComponent* base_body = nullptr;
        Entity base_entity;
        std::vector<FEMArticulationSceneBinding> bindings;

        [[nodiscard]] bool ok() const noexcept {
            return diagnostic == FEMArticulationSceneDiagnostic::None;
        }
    };

    // Compiles the target direct KinematicUnit hierarchy when the root owns an
    // ArticulationComponent. The older alternating joint -> rigid-body scene
    // grammar remains as a migration path, including its floating-base form.
    [[nodiscard]] ENTITY_API FEMArticulationSceneCompilation compile_fem_articulation_scene(Entity root);

} // namespace termin
