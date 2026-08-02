#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

#include <termin/qopt/articulation3d.hpp>
#include <termin/qopt/dynamics.hpp>
#include <termin/qopt/termin_qopt_api.hpp>

namespace termin::qopt
{
    enum class ArticulationMotorDiagnostic : std::uint8_t
    {
        None,
        NullArticulation,
        InvalidChannel,
        DuplicateDof,
        NonFiniteInput,
        TopologyMismatch,
    };

    [[nodiscard]] TERMIN_QOPT_API std::string_view
    articulation_motor_diagnostic_name(ArticulationMotorDiagnostic diagnostic) noexcept;

    struct ArticulationMotorChannel
    {
        std::size_t dof_index = 0;
        double effort_limit = 0.0;
        std::string diagnostic_name;
    };

    // Adds bounded physical efforts to an existing reduced articulation DOF
    // block. It owns no generalized coordinates and registers no topology.
    class TERMIN_QOPT_API ArticulationMotorContribution final
        : public DynamicsContribution
    {
      public:
        ArticulationMotorContribution(Articulation3DContribution& articulation,
                                      std::vector<ArticulationMotorChannel> channels,
                                      std::string_view diagnostic_name = {});

        [[nodiscard]] ArticulationMotorDiagnostic diagnostic() const noexcept;
        [[nodiscard]] std::size_t channel_count() const noexcept;
        [[nodiscard]] const std::vector<ArticulationMotorChannel>&
        channels() const noexcept;

        [[nodiscard]] ArticulationMotorDiagnostic set_command(std::size_t channel_index,
                                                              double effort) noexcept;
        [[nodiscard]] ArticulationMotorDiagnostic
        set_effort_limit(std::size_t channel_index, double effort_limit) noexcept;
        [[nodiscard]] double command(std::size_t channel_index) const noexcept;
        [[nodiscard]] double applied_effort(std::size_t channel_index) const noexcept;
        [[nodiscard]] bool saturated(std::size_t channel_index) const noexcept;

        AssemblyDiagnostic
        register_topology(DynamicsTopology& topology) noexcept override;
        AssemblyDiagnostic
        bind_topology(const DynamicsTopology& topology) noexcept override;
        AssemblyDiagnostic assemble(DynamicsAssembly& assembly,
                                    DynamicsAssemblyPhase phase) noexcept override;

      private:
        Articulation3DContribution* articulation_ = nullptr;
        std::vector<ArticulationMotorChannel> channels_;
        std::vector<double> commands_;
        std::vector<double> applied_efforts_;
        std::string diagnostic_name_;
        ArticulationMotorDiagnostic diagnostic_ = ArticulationMotorDiagnostic::None;

        [[nodiscard]] ArticulationMotorDiagnostic validate() const noexcept;
    };

} // namespace termin::qopt
