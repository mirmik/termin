#include <termin/physics_qopt/dynamics.hpp>

#include <cstdio>

namespace termin::physics_qopt {

    DynamicsRegistrationResult<DynamicsDofHandle>
    DynamicsTopology::register_dofs(std::size_t size, std::string_view diagnostic_name) noexcept {
        if (finalized_) {
            return {{}, AssemblyDiagnostic::TopologyFinalized};
        }
        const DenseBlockRegistrationResult result = dofs_.register_block(size, diagnostic_name);
        return {{result.handle}, result.diagnostic};
    }

    DynamicsRegistrationResult<DynamicsConstraintHandle>
    DynamicsTopology::register_constraint(std::size_t size, std::string_view diagnostic_name) noexcept {
        if (finalized_) {
            return {{}, AssemblyDiagnostic::TopologyFinalized};
        }
        const DenseBlockRegistrationResult result = constraints_.register_block(size, diagnostic_name);
        return {{result.handle}, result.diagnostic};
    }

    AssemblyDiagnostic DynamicsTopology::finalize() noexcept {
        if (finalized_) {
            return AssemblyDiagnostic::TopologyFinalized;
        }
        const AssemblyDiagnostic dof_result = dofs_.finalize();
        if (dof_result != AssemblyDiagnostic::None) {
            return dof_result;
        }
        const AssemblyDiagnostic constraint_result = constraints_.finalize();
        if (constraint_result != AssemblyDiagnostic::None) {
            return constraint_result;
        }
        finalized_ = true;
        return AssemblyDiagnostic::None;
    }

    bool DynamicsTopology::finalized() const noexcept {
        return finalized_;
    }

    std::size_t DynamicsTopology::dof_count() const noexcept {
        return dofs_.total_size();
    }

    std::size_t DynamicsTopology::constraint_count() const noexcept {
        return constraints_.total_size();
    }

    const DenseBlockTopology& DynamicsTopology::dof_topology() const noexcept {
        return dofs_;
    }

    const DenseBlockTopology& DynamicsTopology::constraint_topology() const noexcept {
        return constraints_;
    }

    DynamicsRegistrationResult<DynamicsUnilateralConstraintHandle>
    DynamicsUnilateralTopology::register_constraint(std::size_t size, std::string_view diagnostic_name) noexcept {
        if (finalized_) {
            return {{}, AssemblyDiagnostic::TopologyFinalized};
        }
        const DenseBlockRegistrationResult result = constraints_.register_block(size, diagnostic_name);
        return {{result.handle}, result.diagnostic};
    }

    AssemblyDiagnostic DynamicsUnilateralTopology::finalize() noexcept {
        if (finalized_) {
            return AssemblyDiagnostic::TopologyFinalized;
        }
        const AssemblyDiagnostic result = constraints_.finalize();
        if (result != AssemblyDiagnostic::None) {
            return result;
        }
        finalized_ = true;
        return AssemblyDiagnostic::None;
    }

    bool DynamicsUnilateralTopology::finalized() const noexcept {
        return finalized_;
    }

    std::size_t DynamicsUnilateralTopology::constraint_count() const noexcept {
        return constraints_.total_size();
    }

    const DenseBlockTopology& DynamicsUnilateralTopology::constraint_topology() const noexcept {
        return constraints_;
    }

    DynamicsRegistrationResult<DynamicsFrictionContactHandle>
    DynamicsFrictionTopology::register_contact(DynamicsUnilateralConstraintHandle normal_constraint,
                                               std::string_view diagnostic_name) noexcept {
        if (finalized_) {
            return {{}, AssemblyDiagnostic::TopologyFinalized};
        }
        if (!normal_constraint.valid()) {
            return {{}, AssemblyDiagnostic::InvalidBlock};
        }
        const DenseBlockRegistrationResult contact = contacts_.register_block(1, diagnostic_name);
        if (!contact.ok()) {
            return {{}, contact.diagnostic};
        }
        const DenseBlockRegistrationResult tangent = tangents_.register_block(2, diagnostic_name);
        if (!tangent.ok()) {
            std::fprintf(stderr,
                         "[termin-qopt] friction tangent topology registration "
                         "failed after contact registration\n");
            return {{}, tangent.diagnostic};
        }
        try {
            normal_constraints_.push_back(normal_constraint);
        } catch (...) {
            std::fprintf(stderr,
                         "[termin-qopt] friction normal-row mapping "
                         "registration failed\n");
            return {{}, AssemblyDiagnostic::InternalFailure};
        }
        return {{contact.handle, tangent.handle}, AssemblyDiagnostic::None};
    }

    AssemblyDiagnostic DynamicsFrictionTopology::finalize() noexcept {
        if (finalized_) {
            return AssemblyDiagnostic::TopologyFinalized;
        }
        const AssemblyDiagnostic contact = contacts_.finalize();
        if (contact != AssemblyDiagnostic::None) {
            return contact;
        }
        const AssemblyDiagnostic tangent = tangents_.finalize();
        if (tangent != AssemblyDiagnostic::None) {
            return tangent;
        }
        finalized_ = true;
        return AssemblyDiagnostic::None;
    }

    bool DynamicsFrictionTopology::finalized() const noexcept {
        return finalized_;
    }

    std::size_t DynamicsFrictionTopology::contact_count() const noexcept {
        return contacts_.total_size();
    }

    std::size_t DynamicsFrictionTopology::tangent_count() const noexcept {
        return tangents_.total_size();
    }

    const DenseBlockTopology& DynamicsFrictionTopology::contact_topology() const noexcept {
        return contacts_;
    }

    const DenseBlockTopology& DynamicsFrictionTopology::tangent_topology() const noexcept {
        return tangents_;
    }

    DynamicsUnilateralConstraintHandle
    DynamicsFrictionTopology::normal_constraint(std::size_t contact_index) const noexcept {
        if (contact_index >= normal_constraints_.size()) {
            return {};
        }
        return normal_constraints_[contact_index];
    }
} // namespace termin::physics_qopt
