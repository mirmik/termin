#include <termin/qopt/articulation3d_motor.hpp>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <limits>
#include <unordered_set>

namespace termin::qopt
{
    std::string_view
    articulation_motor_diagnostic_name(ArticulationMotorDiagnostic value) noexcept
    {
        switch (value)
        {
        case ArticulationMotorDiagnostic::None:
            return "none";
        case ArticulationMotorDiagnostic::NullArticulation:
            return "null-articulation";
        case ArticulationMotorDiagnostic::InvalidChannel:
            return "invalid-channel";
        case ArticulationMotorDiagnostic::DuplicateDof:
            return "duplicate-dof";
        case ArticulationMotorDiagnostic::NonFiniteInput:
            return "non-finite-input";
        case ArticulationMotorDiagnostic::TopologyMismatch:
            return "topology-mismatch";
        }
        return "unknown";
    }

    ArticulationMotorContribution::ArticulationMotorContribution(
        Articulation3DContribution& articulation,
        std::vector<ArticulationMotorChannel> channels,
        std::string_view diagnostic_name)
        : articulation_(&articulation), channels_(std::move(channels)),
          diagnostic_name_(diagnostic_name)
    {
        diagnostic_ = validate();
        commands_.assign(channels_.size(), 0.0);
        applied_efforts_.assign(channels_.size(), 0.0);
    }

    ArticulationMotorDiagnostic ArticulationMotorContribution::validate() const noexcept
    {
        if (articulation_ == nullptr)
        {
            return ArticulationMotorDiagnostic::NullArticulation;
        }
        std::unordered_set<std::size_t> dofs;
        for (const ArticulationMotorChannel& channel : channels_)
        {
            if (channel.dof_index >= articulation_->dof_count() ||
                !std::isfinite(channel.effort_limit) || channel.effort_limit < 0.0)
            {
                return ArticulationMotorDiagnostic::InvalidChannel;
            }
            if (!dofs.insert(channel.dof_index).second)
            {
                return ArticulationMotorDiagnostic::DuplicateDof;
            }
        }
        return ArticulationMotorDiagnostic::None;
    }

    ArticulationMotorDiagnostic
    ArticulationMotorContribution::diagnostic() const noexcept
    {
        return diagnostic_;
    }

    std::size_t ArticulationMotorContribution::channel_count() const noexcept
    {
        return channels_.size();
    }

    const std::vector<ArticulationMotorChannel>&
    ArticulationMotorContribution::channels() const noexcept
    {
        return channels_;
    }

    ArticulationMotorDiagnostic
    ArticulationMotorContribution::set_command(std::size_t channel_index,
                                               double effort) noexcept
    {
        if (channel_index >= commands_.size())
        {
            std::fprintf(stderr,
                         "[termin-qopt] motor command channel is out of range\n");
            return ArticulationMotorDiagnostic::InvalidChannel;
        }
        if (!std::isfinite(effort))
        {
            std::fprintf(stderr, "[termin-qopt] rejected non-finite motor command\n");
            return ArticulationMotorDiagnostic::NonFiniteInput;
        }
        commands_[channel_index] = effort;
        return ArticulationMotorDiagnostic::None;
    }

    double
    ArticulationMotorContribution::command(std::size_t channel_index) const noexcept
    {
        return channel_index < commands_.size()
                   ? commands_[channel_index]
                   : std::numeric_limits<double>::quiet_NaN();
    }

    ArticulationMotorDiagnostic
    ArticulationMotorContribution::set_effort_limit(std::size_t channel_index,
                                                    double effort_limit) noexcept
    {
        if (channel_index >= channels_.size())
        {
            std::fprintf(stderr, "[termin-qopt] motor limit channel is out of range\n");
            return ArticulationMotorDiagnostic::InvalidChannel;
        }
        if (!std::isfinite(effort_limit) || effort_limit < 0.0)
        {
            std::fprintf(stderr, "[termin-qopt] rejected invalid motor effort limit\n");
            return ArticulationMotorDiagnostic::NonFiniteInput;
        }
        channels_[channel_index].effort_limit = effort_limit;
        return ArticulationMotorDiagnostic::None;
    }

    double ArticulationMotorContribution::applied_effort(
        std::size_t channel_index) const noexcept
    {
        return channel_index < applied_efforts_.size()
                   ? applied_efforts_[channel_index]
                   : std::numeric_limits<double>::quiet_NaN();
    }

    bool
    ArticulationMotorContribution::saturated(std::size_t channel_index) const noexcept
    {
        return channel_index < commands_.size() &&
               std::abs(commands_[channel_index]) >
                   channels_[channel_index].effort_limit;
    }

    AssemblyDiagnostic ArticulationMotorContribution::register_topology(
        DynamicsTopology& topology) noexcept
    {
        (void)topology;
        if (diagnostic_ != ArticulationMotorDiagnostic::None)
        {
            std::fprintf(stderr,
                         "[termin-qopt] invalid articulation motor '%s': %s\n",
                         diagnostic_name_.c_str(),
                         articulation_motor_diagnostic_name(diagnostic_).data());
            return AssemblyDiagnostic::NonFiniteContribution;
        }
        return AssemblyDiagnostic::None;
    }

    AssemblyDiagnostic ArticulationMotorContribution::bind_topology(
        const DynamicsTopology& topology) noexcept
    {
        if (!topology.finalized() || articulation_ == nullptr ||
            !articulation_->dofs().valid())
        {
            diagnostic_ = ArticulationMotorDiagnostic::TopologyMismatch;
            return AssemblyDiagnostic::InvalidBlock;
        }
        const DenseBlockInfo info =
            topology.dof_topology().block_info(articulation_->dofs().block);
        if (!info.ok() || info.size != articulation_->dof_count())
        {
            diagnostic_ = ArticulationMotorDiagnostic::TopologyMismatch;
            return AssemblyDiagnostic::DimensionMismatch;
        }
        return AssemblyDiagnostic::None;
    }

    AssemblyDiagnostic
    ArticulationMotorContribution::assemble(DynamicsAssembly& assembly,
                                            DynamicsAssemblyPhase phase) noexcept
    {
        if (diagnostic_ != ArticulationMotorDiagnostic::None)
        {
            return AssemblyDiagnostic::NonFiniteContribution;
        }
        if (phase != DynamicsAssemblyPhase::Acceleration)
        {
            return AssemblyDiagnostic::None;
        }

        std::vector<double> load(articulation_->dof_count(), 0.0);
        for (std::size_t index = 0; index < channels_.size(); ++index)
        {
            const double limit = channels_[index].effort_limit;
            const double effort = std::clamp(commands_[index], -limit, limit);
            applied_efforts_[index] = effort;
            load[channels_[index].dof_index] += effort;
        }
        return assembly.add_load(articulation_->dofs(), {load.data(), load.size(), 1});
    }

} // namespace termin::qopt
