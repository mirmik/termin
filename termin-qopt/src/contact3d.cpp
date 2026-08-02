#include <termin/qopt/contact3d.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <exception>
#include <limits>
#include <string>
#include <unordered_set>
#include <utility>

#include <termin/qopt/articulation3d.hpp>
#include <termin/qopt/multibody3d.hpp>

namespace termin::qopt
{

    namespace
    {

        constexpr double kNormalTolerance = 1e-8;

        AssemblyDiagnostic assembly_failure(Contact3DDiagnostic diagnostic) noexcept
        {
            return diagnostic == Contact3DDiagnostic::InternalFailure
                       ? AssemblyDiagnostic::InternalFailure
                       : AssemblyDiagnostic::NonFiniteContribution;
        }

        double projected(const termin::Vec3& normal,
                         ConstDenseMatrixView jacobian,
                         std::size_t column) noexcept
        {
            return normal.x * jacobian(0, column) + normal.y * jacobian(1, column) +
                   normal.z * jacobian(2, column);
        }

    } // namespace

    std::string_view contact3d_diagnostic_name(Contact3DDiagnostic diagnostic) noexcept
    {
        switch (diagnostic)
        {
        case Contact3DDiagnostic::None:
            return "none";
        case Contact3DDiagnostic::InvalidEndpoint:
            return "invalid_endpoint";
        case Contact3DDiagnostic::InvalidEndpointPair:
            return "invalid_endpoint_pair";
        case Contact3DDiagnostic::InvalidNormal:
            return "invalid_normal";
        case Contact3DDiagnostic::NonFiniteGap:
            return "non_finite_gap";
        case Contact3DDiagnostic::DuplicateKey:
            return "duplicate_key";
        case Contact3DDiagnostic::InvalidState:
            return "invalid_state";
        case Contact3DDiagnostic::InternalFailure:
            return "internal_failure";
        }
        return "unknown";
    }

    ContactEndpoint3D
    ContactEndpoint3D::static_world(termin::Vec3 position_world) noexcept
    {
        ContactEndpoint3D endpoint;
        endpoint.kind_ = Kind::StaticWorld;
        endpoint.point_ = position_world;
        return endpoint;
    }

    ContactEndpoint3D ContactEndpoint3D::rigid_body(RigidBody3DContribution& body,
                                                    termin::Vec3 point_local) noexcept
    {
        ContactEndpoint3D endpoint;
        endpoint.kind_ = Kind::RigidBody;
        endpoint.body_ = &body;
        endpoint.point_ = point_local;
        return endpoint;
    }

    ContactEndpoint3D
    ContactEndpoint3D::articulation_link(Articulation3DContribution& articulation,
                                         std::size_t link_index,
                                         termin::Vec3 point_local) noexcept
    {
        ContactEndpoint3D endpoint;
        endpoint.kind_ = Kind::ArticulationLink;
        endpoint.articulation_ = &articulation;
        endpoint.link_index_ = link_index;
        endpoint.point_ = point_local;
        return endpoint;
    }

    bool ContactEndpoint3D::valid() const noexcept
    {
        return kind_ != Kind::Invalid && point_.is_finite() &&
               (kind_ == Kind::StaticWorld ||
                (kind_ == Kind::RigidBody && body_ != nullptr) ||
                (kind_ == Kind::ArticulationLink && articulation_ != nullptr));
    }

    bool ContactEndpoint3D::is_static() const noexcept
    {
        return kind_ == Kind::StaticWorld;
    }

    PointKinematics3DResult ContactEndpoint3D::point_kinematics() const noexcept
    {
        switch (kind_)
        {
        case Kind::StaticWorld:
            return static_point_kinematics(point_);
        case Kind::RigidBody:
            if (body_ != nullptr)
            {
                return body_->point_kinematics(point_);
            }
            break;
        case Kind::ArticulationLink:
            if (articulation_ != nullptr)
            {
                return articulation_->point_kinematics(link_index_, point_);
            }
            break;
        case Kind::Invalid:
            break;
        }
        std::fprintf(stderr, "[termin-qopt] contact references invalid endpoint\n");
        return {{}, PointKinematics3DDiagnostic::InvalidModel};
    }

    ContactSet3DContribution::ContactSet3DContribution(std::string_view diagnostic_name)
        : diagnostic_name_(diagnostic_name)
    {
    }

    Contact3DDiagnostic
    ContactSet3DContribution::set_contacts(std::vector<Contact3D> contacts) noexcept
    {
        try
        {
            contacts_ = std::move(contacts);
            states_.clear();
            states_snapshot_.clear();
            step_contacts_.clear();
            diagnostic_ = validate_contacts();
            if (diagnostic_ != Contact3DDiagnostic::None)
            {
                std::fprintf(stderr,
                             "[termin-qopt] rejected contact set '%s': %s\n",
                             diagnostic_name_.c_str(),
                             contact3d_diagnostic_name(diagnostic_).data());
            }
            return diagnostic_;
        }
        catch (const std::exception& error)
        {
            std::fprintf(
                stderr, "[termin-qopt] setting contact set failed: %s\n", error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-qopt] setting contact set failed with an unknown "
                         "exception\n");
        }
        diagnostic_ = Contact3DDiagnostic::InternalFailure;
        return diagnostic_;
    }

    const std::vector<Contact3D>& ContactSet3DContribution::contacts() const noexcept
    {
        return contacts_;
    }

    const std::vector<ContactState3D>& ContactSet3DContribution::states() const noexcept
    {
        return states_;
    }

    Contact3DDiagnostic ContactSet3DContribution::diagnostic() const noexcept
    {
        return diagnostic_;
    }

    Contact3DDiagnostic ContactSet3DContribution::validate_contacts() const noexcept
    {
        try
        {
            std::unordered_set<std::uint64_t> keys;
            for (const Contact3D& contact : contacts_)
            {
                if (!contact.endpoint_a.valid() || !contact.endpoint_b.valid())
                {
                    return Contact3DDiagnostic::InvalidEndpoint;
                }
                if (contact.endpoint_a.is_static() && contact.endpoint_b.is_static())
                {
                    return Contact3DDiagnostic::InvalidEndpointPair;
                }
                const double normal_norm = contact.normal_from_a_to_b_world.norm();
                if (!contact.normal_from_a_to_b_world.is_finite() ||
                    !std::isfinite(normal_norm) ||
                    std::abs(normal_norm - 1.0) > kNormalTolerance)
                {
                    return Contact3DDiagnostic::InvalidNormal;
                }
                if (!std::isfinite(contact.signed_gap))
                {
                    return Contact3DDiagnostic::NonFiniteGap;
                }
                if (!keys.insert(contact.key).second)
                {
                    return Contact3DDiagnostic::DuplicateKey;
                }
            }
            return Contact3DDiagnostic::None;
        }
        catch (...)
        {
            return Contact3DDiagnostic::InternalFailure;
        }
    }

    AssemblyDiagnostic
    ContactSet3DContribution::register_topology(DynamicsTopology&) noexcept
    {
        return AssemblyDiagnostic::None;
    }

    AssemblyDiagnostic ContactSet3DContribution::register_unilateral_constraints(
        DynamicsUnilateralTopology& topology, double time_step) noexcept
    {
        diagnostic_ = validate_contacts();
        if (diagnostic_ != Contact3DDiagnostic::None || !std::isfinite(time_step) ||
            time_step <= 0.0)
        {
            std::fprintf(stderr,
                         "[termin-qopt] contact set '%s' cannot register rows: %s\n",
                         diagnostic_name_.c_str(),
                         contact3d_diagnostic_name(diagnostic_).data());
            return assembly_failure(diagnostic_);
        }

        try
        {
            time_step_ = time_step;
            states_.assign(contacts_.size(), {});
            step_contacts_.assign(contacts_.size(), {});
            const std::string prefix =
                diagnostic_name_.empty() ? "contacts" : diagnostic_name_;
            for (std::size_t index = 0; index < contacts_.size(); ++index)
            {
                PointKinematics3DResult endpoint_a =
                    contacts_[index].endpoint_a.point_kinematics();
                PointKinematics3DResult endpoint_b =
                    contacts_[index].endpoint_b.point_kinematics();
                if (!endpoint_a.ok() || !endpoint_b.ok() ||
                    (!endpoint_a.value.is_static() && !endpoint_a.value.dofs.valid()) ||
                    (!endpoint_b.value.is_static() && !endpoint_b.value.dofs.valid()))
                {
                    diagnostic_ = Contact3DDiagnostic::InvalidEndpoint;
                    std::fprintf(stderr,
                                 "[termin-qopt] contact %llu has invalid endpoint "
                                 "kinematics\n",
                                 static_cast<unsigned long long>(contacts_[index].key));
                    return assembly_failure(diagnostic_);
                }
                const auto registration = topology.register_constraint(
                    1, prefix + ".normal." + std::to_string(contacts_[index].key));
                if (!registration.ok())
                {
                    return registration.diagnostic;
                }
                step_contacts_[index].row = registration.handle;
                step_contacts_[index].reference_separation =
                    contacts_[index].normal_from_a_to_b_world.dot(
                        endpoint_b.value.position_world -
                        endpoint_a.value.position_world);
                states_[index].key = contacts_[index].key;
                states_[index].signed_gap = contacts_[index].signed_gap;
                states_[index].normal_velocity =
                    contacts_[index].normal_from_a_to_b_world.dot(
                        endpoint_b.value.velocity_world -
                        endpoint_a.value.velocity_world);
            }
            return AssemblyDiagnostic::None;
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
                         "[termin-qopt] contact row registration failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-qopt] contact row registration failed with an "
                         "unknown exception\n");
        }
        diagnostic_ = Contact3DDiagnostic::InternalFailure;
        return AssemblyDiagnostic::InternalFailure;
    }

    bool ContactSet3DContribution::update_state(std::size_t index,
                                                PointKinematics3D& endpoint_a,
                                                PointKinematics3D& endpoint_b) noexcept
    {
        if (index >= contacts_.size() || index >= step_contacts_.size() ||
            index >= states_.size())
        {
            return false;
        }
        PointKinematics3DResult a = contacts_[index].endpoint_a.point_kinematics();
        PointKinematics3DResult b = contacts_[index].endpoint_b.point_kinematics();
        if (!a.ok() || !b.ok())
        {
            return false;
        }
        endpoint_a = std::move(a.value);
        endpoint_b = std::move(b.value);
        const termin::Vec3& normal = contacts_[index].normal_from_a_to_b_world;
        ContactState3D& state = states_[index];
        state.key = contacts_[index].key;
        state.signed_gap =
            contacts_[index].signed_gap +
            normal.dot(endpoint_b.position_world - endpoint_a.position_world) -
            step_contacts_[index].reference_separation;
        state.normal_velocity =
            normal.dot(endpoint_b.velocity_world - endpoint_a.velocity_world);
        return std::isfinite(state.signed_gap) && std::isfinite(state.normal_velocity);
    }

    AssemblyDiagnostic
    ContactSet3DContribution::assemble(DynamicsAssembly& assembly,
                                       DynamicsAssemblyPhase phase) noexcept
    {
        if (phase == DynamicsAssemblyPhase::Acceleration)
        {
            return AssemblyDiagnostic::None;
        }
        if (diagnostic_ != Contact3DDiagnostic::None || !std::isfinite(time_step_) ||
            time_step_ <= 0.0 || step_contacts_.size() != contacts_.size())
        {
            return AssemblyDiagnostic::NonFiniteContribution;
        }

        try
        {
            for (std::size_t index = 0; index < contacts_.size(); ++index)
            {
                PointKinematics3D endpoint_a;
                PointKinematics3D endpoint_b;
                if (!update_state(index, endpoint_a, endpoint_b))
                {
                    diagnostic_ = Contact3DDiagnostic::InvalidState;
                    std::fprintf(stderr,
                                 "[termin-qopt] contact %llu produced invalid "
                                 "kinematics\n",
                                 static_cast<unsigned long long>(contacts_[index].key));
                    return AssemblyDiagnostic::NonFiniteContribution;
                }
                const termin::Vec3& normal = contacts_[index].normal_from_a_to_b_world;
                const auto add_endpoint =
                    [&](const PointKinematics3D& endpoint, double sign) noexcept
                {
                    if (endpoint.is_static())
                    {
                        return AssemblyDiagnostic::None;
                    }
                    const ConstDenseMatrixView jacobian =
                        endpoint.linear_jacobian_world();
                    std::vector<double> row(endpoint.dof_count());
                    for (std::size_t column = 0; column < row.size(); ++column)
                    {
                        row[column] = sign * projected(normal, jacobian, column);
                    }
                    return assembly.add_unilateral_jacobian(
                        step_contacts_[index].row,
                        endpoint.dofs,
                        ConstDenseMatrixView::row_major(row.data(), 1, row.size()));
                };
                AssemblyDiagnostic result = add_endpoint(endpoint_a, 1.0);
                if (result == AssemblyDiagnostic::None)
                {
                    result = add_endpoint(endpoint_b, -1.0);
                }
                if (result != AssemblyDiagnostic::None)
                {
                    return result;
                }
                const std::array<double, 1> limit{
                    phase == DynamicsAssemblyPhase::PositionProjection
                        ? states_[index].signed_gap
                        : std::max(states_[index].signed_gap, 0.0) / time_step_,
                };
                result = assembly.add_unilateral_limit(step_contacts_[index].row,
                                                       {limit.data(), limit.size(), 1});
                if (result != AssemblyDiagnostic::None)
                {
                    return result;
                }
            }
            return AssemblyDiagnostic::None;
        }
        catch (const std::exception& error)
        {
            std::fprintf(
                stderr, "[termin-qopt] contact assembly failed: %s\n", error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-qopt] contact assembly failed with an unknown "
                         "exception\n");
        }
        diagnostic_ = Contact3DDiagnostic::InternalFailure;
        return AssemblyDiagnostic::InternalFailure;
    }

    AssemblyDiagnostic ContactSet3DContribution::begin_step() noexcept
    {
        try
        {
            states_snapshot_ = states_;
            snapshot_ready_ = true;
            return AssemblyDiagnostic::None;
        }
        catch (const std::exception& error)
        {
            std::fprintf(
                stderr, "[termin-qopt] contact snapshot failed: %s\n", error.what());
        }
        catch (...)
        {
            std::fprintf(stderr,
                         "[termin-qopt] contact snapshot failed with an unknown "
                         "exception\n");
        }
        return AssemblyDiagnostic::InternalFailure;
    }

    void ContactSet3DContribution::commit_step() noexcept
    {
        snapshot_ready_ = false;
    }

    void ContactSet3DContribution::rollback_step() noexcept
    {
        if (snapshot_ready_)
        {
            states_.swap(states_snapshot_);
            snapshot_ready_ = false;
        }
    }

    void ContactSet3DContribution::apply_unilateral_solution(
        const DynamicsTopology&,
        const DynamicsUnilateralTopology& unilateral_topology,
        ConstDenseVectorView reactions,
        ConstDenseVectorView tight_mask) noexcept
    {
        if (states_.size() != step_contacts_.size())
        {
            return;
        }
        for (std::size_t index = 0; index < states_.size(); ++index)
        {
            PointKinematics3D endpoint_a;
            PointKinematics3D endpoint_b;
            if (!update_state(index, endpoint_a, endpoint_b))
            {
                diagnostic_ = Contact3DDiagnostic::InvalidState;
                std::fprintf(stderr,
                             "[termin-qopt] cannot update solved contact state\n");
                continue;
            }
            const DenseBlockInfo info =
                unilateral_topology.constraint_topology().block_info(
                    step_contacts_[index].row.block);
            if (!info.ok() || info.size != 1 || info.offset >= reactions.size ||
                info.offset >= tight_mask.size)
            {
                std::fprintf(stderr, "[termin-qopt] invalid contact reaction output\n");
                continue;
            }
            states_[index].normal_impulse = reactions[info.offset];
            states_[index].normal_reaction = reactions[info.offset] / time_step_;
            states_[index].active = tight_mask[info.offset] == 1.0;
        }
    }

    double ContactSet3DContribution::position_error_linf() const noexcept
    {
        double result = 0.0;
        if (step_contacts_.size() != contacts_.size())
        {
            return contacts_.empty() ? 0.0 : std::numeric_limits<double>::infinity();
        }
        for (std::size_t index = 0; index < contacts_.size(); ++index)
        {
            const PointKinematics3DResult endpoint_a =
                contacts_[index].endpoint_a.point_kinematics();
            const PointKinematics3DResult endpoint_b =
                contacts_[index].endpoint_b.point_kinematics();
            if (!endpoint_a.ok() || !endpoint_b.ok())
            {
                return std::numeric_limits<double>::infinity();
            }
            const termin::Vec3& normal = contacts_[index].normal_from_a_to_b_world;
            const double gap = contacts_[index].signed_gap +
                               normal.dot(endpoint_b.value.position_world -
                                          endpoint_a.value.position_world) -
                               step_contacts_[index].reference_separation;
            result = std::max(result, std::max(-gap, 0.0));
        }
        return result;
    }

    double ContactSet3DContribution::velocity_error_linf() const noexcept
    {
        if (!std::isfinite(time_step_) || time_step_ <= 0.0)
        {
            return 0.0;
        }
        if (step_contacts_.size() != contacts_.size())
        {
            return contacts_.empty() ? 0.0 : std::numeric_limits<double>::infinity();
        }
        double result = 0.0;
        for (std::size_t index = 0; index < contacts_.size(); ++index)
        {
            const PointKinematics3DResult endpoint_a =
                contacts_[index].endpoint_a.point_kinematics();
            const PointKinematics3DResult endpoint_b =
                contacts_[index].endpoint_b.point_kinematics();
            if (!endpoint_a.ok() || !endpoint_b.ok())
            {
                return std::numeric_limits<double>::infinity();
            }
            const termin::Vec3& normal = contacts_[index].normal_from_a_to_b_world;
            const double gap = contacts_[index].signed_gap +
                               normal.dot(endpoint_b.value.position_world -
                                          endpoint_a.value.position_world) -
                               step_contacts_[index].reference_separation;
            const double normal_velocity = normal.dot(endpoint_b.value.velocity_world -
                                                      endpoint_a.value.velocity_world);
            const double target = -std::max(gap, 0.0) / time_step_;
            result = std::max(result, std::max(target - normal_velocity, 0.0));
        }
        return result;
    }

} // namespace termin::qopt
