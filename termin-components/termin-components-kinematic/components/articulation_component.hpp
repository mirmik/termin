#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <span>
#include <string>
#include <string_view>
#include <vector>

#include <termin/entity/component.hpp>
#include <termin/robotics/articulation3d.hpp>

namespace termin {
    class KinematicUnitComponent;

    enum class ArticulationComponentDiagnostic : std::uint8_t {
        None,
        InvalidRoot,
        EmptyArticulation,
        MultipleUnitsOnEntity,
        UnsupportedUnit,
        IndirectUnit,
        NestedArticulation,
        NonRigidTransform,
        InvalidCoordinateScale,
        InvalidCoordinateLimits,
        InvalidInertia,
        InvalidModel,
        IntegrationFailure,
        SynchronizationFailure,
    };

    [[nodiscard]] ENTITY_API std::string_view
    articulation_component_diagnostic_name(ArticulationComponentDiagnostic diagnostic) noexcept;

    // Solver-neutral owner of a direct KinematicUnit -> KinematicUnit scene
    // tree. It compiles and synchronizes Articulation3D, but never calculates
    // controller policy or advances time automatically.
    class ENTITY_API ArticulationComponent final : public CxxComponent {
    public:
        ArticulationComponent();
        ~ArticulationComponent() override = default;

        static void register_type();
        void start() override;
        void on_destroy() override;

        [[nodiscard]] bool rebuild();
        [[nodiscard]] bool synchronize();
        [[nodiscard]] bool integrate_velocity(std::span<const double> generalized_velocity, double time_step);

        [[nodiscard]] bool initialized() const noexcept;
        [[nodiscard]] std::size_t unit_count() const noexcept;
        [[nodiscard]] KinematicUnitComponent* unit_component(std::size_t unit_index) noexcept;
        [[nodiscard]] const KinematicUnitComponent* unit_component(std::size_t unit_index) const noexcept;
        [[nodiscard]] double unit_coordinate_scale(std::size_t unit_index) const noexcept;
        [[nodiscard]] ArticulationComponentDiagnostic diagnostic() const noexcept;
        [[nodiscard]] std::string_view diagnostic_entity() const noexcept;
        [[nodiscard]] robotics::Articulation3D* articulation() noexcept;
        [[nodiscard]] const robotics::Articulation3D* articulation() const noexcept;
        [[nodiscard]] std::shared_ptr<robotics::Articulation3D> articulation_shared() const noexcept;

    private:
        std::shared_ptr<robotics::Articulation3D> articulation_;
        std::vector<KinematicUnitComponent*> bindings_;
        std::vector<double> coordinate_scales_;
        ArticulationComponentDiagnostic diagnostic_ = ArticulationComponentDiagnostic::None;
        std::string diagnostic_entity_;
    };
} // namespace termin
