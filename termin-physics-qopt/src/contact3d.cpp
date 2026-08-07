#include <termin/physics_qopt/contact3d.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <exception>
#include <limits>
#include <numbers>
#include <string>
#include <unordered_set>
#include <utility>

#include <termin/physics_qopt/articulation3d_dynamics.hpp>
#include <termin/physics_qopt/multibody3d.hpp>

namespace termin::physics_qopt
{

    namespace
    {

        constexpr double kNormalTolerance = 1e-8;
        constexpr double kWarmImpulseTolerance = 1e-12;
        constexpr double kFrictionBoundaryTolerance = 1e-8;

        AssemblyDiagnostic
        assembly_failure(Contact3DDiagnostic diagnostic) noexcept
        {
            return diagnostic == Contact3DDiagnostic::InternalFailure
                       ? AssemblyDiagnostic::InternalFailure
                       : AssemblyDiagnostic::NonFiniteContribution;
        }

        double projected(const termin::Vec3& normal,
                         ConstDenseMatrixView jacobian,
                         std::size_t column) noexcept
        {
            return normal.x * jacobian(0, column) +
                   normal.y * jacobian(1, column) +
                   normal.z * jacobian(2, column);
        }

        std::array<termin::Vec3, 2>
        tangent_basis(const termin::Vec3& normal) noexcept
        {
            const double ax = std::abs(normal.x);
            const double ay = std::abs(normal.y);
            const double az = std::abs(normal.z);
            termin::Vec3 reference = termin::Vec3::unit_x();
            if (ay <= ax && ay <= az)
            {
                reference = termin::Vec3::unit_y();
            }
            else if (az <= ax && az <= ay)
            {
                reference = termin::Vec3::unit_z();
            }
            const termin::Vec3 first = normal.cross(reference).normalized();
            return {first, normal.cross(first)};
        }

    } // namespace

    std::string_view
    contact3d_diagnostic_name(Contact3DDiagnostic diagnostic) noexcept
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
        case Contact3DDiagnostic::InvalidFrictionCoefficient:
            return "invalid_friction_coefficient";
        case Contact3DDiagnostic::DuplicateKey:
            return "duplicate_key";
        case Contact3DDiagnostic::CacheCapacityExceeded:
            return "cache_capacity_exceeded";
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

    ContactEndpoint3D
    ContactEndpoint3D::rigid_body(RigidBody3DContribution& body,
                                  termin::Vec3 point_local) noexcept
    {
        ContactEndpoint3D endpoint;
        endpoint.kind_ = Kind::RigidBody;
        endpoint.body_ = &body;
        endpoint.point_ = point_local;
        return endpoint;
    }

    ContactEndpoint3D ContactEndpoint3D::articulation_unit(
        Articulation3DDynamicsContribution& articulation,
        std::size_t unit_index,
        termin::Vec3 point_local) noexcept
    {
        ContactEndpoint3D endpoint;
        endpoint.kind_ = Kind::ArticulationUnit;
        endpoint.articulation_ = &articulation;
        endpoint.unit_index_ = unit_index;
        endpoint.point_ = point_local;
        return endpoint;
    }

    ContactEndpoint3D ContactEndpoint3D::articulation_base(
        Articulation3DDynamicsContribution& articulation,
        termin::Vec3 point_local) noexcept
    {
        ContactEndpoint3D endpoint;
        endpoint.kind_ = Kind::ArticulationBase;
        endpoint.articulation_ = &articulation;
        endpoint.point_ = point_local;
        return endpoint;
    }

    bool ContactEndpoint3D::valid() const noexcept
    {
        return kind_ != Kind::Invalid && point_.is_finite() &&
               (kind_ == Kind::StaticWorld ||
                (kind_ == Kind::RigidBody && body_ != nullptr) ||
                (kind_ == Kind::ArticulationBase && articulation_ != nullptr) ||
                (kind_ == Kind::ArticulationUnit && articulation_ != nullptr));
    }

    bool ContactEndpoint3D::is_static() const noexcept
    {
        return kind_ == Kind::StaticWorld;
    }

    bool ContactEndpoint3D::belongs_to(
        const Articulation3DDynamicsContribution& articulation) const noexcept
    {
        return articulation_ == &articulation &&
               (kind_ == Kind::ArticulationBase ||
                kind_ == Kind::ArticulationUnit);
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
        case Kind::ArticulationBase:
            if (articulation_ != nullptr)
            {
                return articulation_->floating_base_point_kinematics(point_);
            }
            break;
        case Kind::ArticulationUnit:
            if (articulation_ != nullptr)
            {
                return articulation_->point_kinematics(unit_index_, point_);
            }
            break;
        case Kind::Invalid:
            break;
        }
        std::fprintf(stderr,
                     "[termin-qopt] contact references invalid endpoint\n");
        return {{}, PointKinematics3DDiagnostic::InvalidModel};
    }

    ContactSet3DContribution::ContactSet3DContribution(
        std::string_view diagnostic_name)
        : diagnostic_name_(diagnostic_name)
    {
    }

    Contact3DDiagnostic ContactSet3DContribution::set_contacts(
        std::vector<Contact3D> contacts) noexcept
    {
        return set_contacts(std::move(contacts), {});
    }

    Contact3DDiagnostic ContactSet3DContribution::set_contacts(
        std::vector<Contact3D> contacts,
        std::vector<std::uint64_t> live_groups) noexcept
    {
        try
        {
            const auto contact_less = [](const Contact3D& a, const Contact3D& b)
            { return a.key < b.key; };
            const auto state_less =
                [](const ContactState3D& state, std::uint64_t key)
            { return state.key < key; };
            std::sort(contacts.begin(), contacts.end(), contact_less);
            std::sort(live_groups.begin(), live_groups.end());
            live_groups.erase(
                std::unique(live_groups.begin(), live_groups.end()),
                live_groups.end());
            if (contacts.size() > maximum_cached_contacts_)
            {
                diagnostic_ = Contact3DDiagnostic::CacheCapacityExceeded;
                std::fprintf(stderr,
                             "[termin-qopt] contact set '%s' exceeds cache "
                             "capacity (%zu > %zu)\n",
                             diagnostic_name_.c_str(),
                             contacts.size(),
                             maximum_cached_contacts_);
                return diagnostic_;
            }

            std::vector<Contact3D> merged = contacts;
            for (const Contact3D& previous : contacts_)
            {
                const bool key_present = std::binary_search(
                    contacts.begin(), contacts.end(), previous, contact_less);
                if (key_present || previous.group_key == 0 ||
                    !std::binary_search(live_groups.begin(),
                                        live_groups.end(),
                                        previous.group_key))
                {
                    continue;
                }
                const bool group_has_fresh_contacts = std::any_of(
                    contacts.begin(),
                    contacts.end(),
                    [&](const Contact3D& candidate)
                    { return candidate.group_key == previous.group_key; });
                if (group_has_fresh_contacts)
                {
                    continue;
                }
                const auto cached = std::lower_bound(state_cache_.begin(),
                                                     state_cache_.end(),
                                                     previous.key,
                                                     state_less);
                if (cached == state_cache_.end() ||
                    cached->key != previous.key || !cached->active ||
                    cached->normal_impulse <= kWarmImpulseTolerance)
                {
                    continue;
                }
                const PointKinematics3DResult endpoint_a =
                    previous.endpoint_a.point_kinematics();
                const PointKinematics3DResult endpoint_b =
                    previous.endpoint_b.point_kinematics();
                if (!endpoint_a.ok() || !endpoint_b.ok())
                {
                    continue;
                }
                const double current_gap =
                    previous.normal_from_a_to_b_world.dot(
                        endpoint_b.value.position_world -
                        endpoint_a.value.position_world);
                if (!std::isfinite(current_gap) ||
                    current_gap > persistence_distance_)
                {
                    continue;
                }
                Contact3D retained = previous;
                retained.signed_gap = current_gap;
                merged.push_back(std::move(retained));
                if (merged.size() > maximum_cached_contacts_)
                {
                    diagnostic_ = Contact3DDiagnostic::CacheCapacityExceeded;
                    return diagnostic_;
                }
            }
            std::sort(merged.begin(), merged.end(), contact_less);
            contacts_ = std::move(merged);
            states_.clear();
            states_snapshot_.clear();
            step_contacts_.clear();
            warm_started_contact_count_ = 0;
            diagnostic_ = validate_contacts();
            if (diagnostic_ != Contact3DDiagnostic::None)
            {
                std::fprintf(stderr,
                             "[termin-qopt] rejected contact set '%s': %s\n",
                             diagnostic_name_.c_str(),
                             contact3d_diagnostic_name(diagnostic_).data());
                return diagnostic_;
            }
            state_cache_.erase(
                std::remove_if(state_cache_.begin(),
                               state_cache_.end(),
                               [&](const ContactState3D& state)
                               {
                                   return !std::binary_search(
                                       contacts_.begin(),
                                       contacts_.end(),
                                       Contact3D{.key = state.key},
                                       contact_less);
                               }),
                state_cache_.end());
            return diagnostic_;
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
                         "[termin-qopt] setting contact set failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            std::fprintf(
                stderr,
                "[termin-qopt] setting contact set failed with an unknown "
                "exception\n");
        }
        diagnostic_ = Contact3DDiagnostic::InternalFailure;
        return diagnostic_;
    }

    std::size_t ContactSet3DContribution::cached_contact_count() const noexcept
    {
        return state_cache_.size();
    }

    std::size_t
    ContactSet3DContribution::warm_started_contact_count() const noexcept
    {
        return warm_started_contact_count_;
    }

    double ContactSet3DContribution::persistence_distance() const noexcept
    {
        return persistence_distance_;
    }

    std::size_t
    ContactSet3DContribution::maximum_cached_contacts() const noexcept
    {
        return maximum_cached_contacts_;
    }

    bool
    ContactSet3DContribution::set_persistence_distance(double distance) noexcept
    {
        if (!std::isfinite(distance) || distance < 0.0)
        {
            std::fprintf(
                stderr, "[termin-qopt] invalid contact persistence distance\n");
            return false;
        }
        persistence_distance_ = distance;
        return true;
    }

    bool ContactSet3DContribution::set_maximum_cached_contacts(
        std::size_t maximum) noexcept
    {
        if (maximum == 0 || maximum < contacts_.size() ||
            maximum < state_cache_.size())
        {
            std::fprintf(stderr,
                         "[termin-qopt] invalid contact cache capacity\n");
            return false;
        }
        maximum_cached_contacts_ = maximum;
        return true;
    }

    void ContactSet3DContribution::clear_cache() noexcept
    {
        contacts_.clear();
        states_.clear();
        state_cache_.clear();
        states_snapshot_.clear();
        step_contacts_.clear();
        warm_started_contact_count_ = 0;
        diagnostic_ = Contact3DDiagnostic::None;
    }

    const std::vector<Contact3D>&
    ContactSet3DContribution::contacts() const noexcept
    {
        return contacts_;
    }

    const std::vector<ContactState3D>&
    ContactSet3DContribution::states() const noexcept
    {
        return states_;
    }

    Contact3DDiagnostic ContactSet3DContribution::diagnostic() const noexcept
    {
        return diagnostic_;
    }

    Contact3DDiagnostic
    ContactSet3DContribution::validate_contacts() const noexcept
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
                if (contact.endpoint_a.is_static() &&
                    contact.endpoint_b.is_static())
                {
                    return Contact3DDiagnostic::InvalidEndpointPair;
                }
                const double normal_norm =
                    contact.normal_from_a_to_b_world.norm();
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
                if (!std::isfinite(contact.friction_coefficient) ||
                    contact.friction_coefficient < 0.0)
                {
                    return Contact3DDiagnostic::InvalidFrictionCoefficient;
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

    AssemblyDiagnostic
    ContactSet3DContribution::register_unilateral_constraints(
        DynamicsUnilateralTopology& topology, double time_step) noexcept
    {
        diagnostic_ = validate_contacts();
        if (diagnostic_ != Contact3DDiagnostic::None ||
            !std::isfinite(time_step) || time_step <= 0.0)
        {
            std::fprintf(
                stderr,
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
            warm_started_contact_count_ = 0;
            const std::string prefix =
                diagnostic_name_.empty() ? "contacts" : diagnostic_name_;
            for (std::size_t index = 0; index < contacts_.size(); ++index)
            {
                const auto cached = std::lower_bound(
                    state_cache_.begin(),
                    state_cache_.end(),
                    contacts_[index].key,
                    [](const ContactState3D& state, std::uint64_t key)
                    { return state.key < key; });
                if (cached != state_cache_.end() &&
                    cached->key == contacts_[index].key)
                {
                    states_[index] = *cached;
                    warm_started_contact_count_ +=
                        cached->active &&
                                cached->normal_impulse > kWarmImpulseTolerance
                            ? 1U
                            : 0U;
                }
                PointKinematics3DResult endpoint_a =
                    contacts_[index].endpoint_a.point_kinematics();
                PointKinematics3DResult endpoint_b =
                    contacts_[index].endpoint_b.point_kinematics();
                if (!endpoint_a.ok() || !endpoint_b.ok() ||
                    (!endpoint_a.value.is_static() &&
                     !endpoint_a.value.dofs.valid()) ||
                    (!endpoint_b.value.is_static() &&
                     !endpoint_b.value.dofs.valid()))
                {
                    diagnostic_ = Contact3DDiagnostic::InvalidEndpoint;
                    std::fprintf(
                        stderr,
                        "[termin-qopt] contact %llu has invalid endpoint "
                        "kinematics\n",
                        static_cast<unsigned long long>(contacts_[index].key));
                    return assembly_failure(diagnostic_);
                }
                const auto registration = topology.register_constraint(
                    1,
                    prefix + ".normal." + std::to_string(contacts_[index].key));
                if (!registration.ok())
                {
                    return registration.diagnostic;
                }
                step_contacts_[index].row = registration.handle;
                const auto tangents =
                    tangent_basis(contacts_[index].normal_from_a_to_b_world);
                step_contacts_[index].tangent_1_world = tangents[0];
                step_contacts_[index].tangent_2_world = tangents[1];
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
            state_cache_ = states_;
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
            std::fprintf(
                stderr,
                "[termin-qopt] contact row registration failed with an "
                "unknown exception\n");
        }
        diagnostic_ = Contact3DDiagnostic::InternalFailure;
        return AssemblyDiagnostic::InternalFailure;
    }

    AssemblyDiagnostic ContactSet3DContribution::register_friction_contacts(
        DynamicsFrictionTopology& topology, double time_step) noexcept
    {
        if (diagnostic_ != Contact3DDiagnostic::None ||
            !std::isfinite(time_step) || time_step <= 0.0 ||
            step_contacts_.size() != contacts_.size())
        {
            std::fprintf(stderr,
                         "[termin-qopt] contact set '%s' cannot register "
                         "friction rows\n",
                         diagnostic_name_.c_str());
            return AssemblyDiagnostic::NonFiniteContribution;
        }

        try
        {
            const std::string prefix =
                diagnostic_name_.empty() ? "contacts" : diagnostic_name_;
            for (std::size_t index = 0; index < contacts_.size(); ++index)
            {
                if (contacts_[index].friction_coefficient == 0.0)
                {
                    continue;
                }
                const auto registration = topology.register_contact(
                    step_contacts_[index].row,
                    prefix + ".friction." +
                    std::to_string(contacts_[index].key));
                if (!registration.ok())
                {
                    return registration.diagnostic;
                }
                step_contacts_[index].friction = registration.handle;
            }
            return AssemblyDiagnostic::None;
        }
        catch (const std::exception& error)
        {
            std::fprintf(
                stderr,
                "[termin-qopt] contact friction registration failed: %s\n",
                error.what());
        }
        catch (...)
        {
            std::fprintf(
                stderr,
                "[termin-qopt] contact friction registration failed with "
                "an unknown exception\n");
        }
        diagnostic_ = Contact3DDiagnostic::InternalFailure;
        return AssemblyDiagnostic::InternalFailure;
    }

    bool ContactSet3DContribution::update_state(
        std::size_t index,
        PointKinematics3D& endpoint_a,
        PointKinematics3D& endpoint_b) noexcept
    {
        if (index >= contacts_.size() || index >= step_contacts_.size() ||
            index >= states_.size())
        {
            return false;
        }
        PointKinematics3DResult a =
            contacts_[index].endpoint_a.point_kinematics();
        PointKinematics3DResult b =
            contacts_[index].endpoint_b.point_kinematics();
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
        return std::isfinite(state.signed_gap) &&
               std::isfinite(state.normal_velocity);
    }

    AssemblyDiagnostic
    ContactSet3DContribution::assemble(DynamicsAssembly& assembly,
                                       DynamicsAssemblyPhase phase) noexcept
    {
        if (phase == DynamicsAssemblyPhase::Acceleration)
        {
            return AssemblyDiagnostic::None;
        }
        if (diagnostic_ != Contact3DDiagnostic::None ||
            !std::isfinite(time_step_) || time_step_ <= 0.0 ||
            step_contacts_.size() != contacts_.size())
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
                    std::fprintf(
                        stderr,
                        "[termin-qopt] contact %llu produced invalid "
                        "kinematics\n",
                        static_cast<unsigned long long>(contacts_[index].key));
                    return AssemblyDiagnostic::NonFiniteContribution;
                }
                const termin::Vec3& normal =
                    contacts_[index].normal_from_a_to_b_world;
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
                        row[column] =
                            sign * projected(normal, jacobian, column);
                    }
                    return assembly.add_unilateral_jacobian(
                        step_contacts_[index].row,
                        endpoint.dofs,
                        ConstDenseMatrixView::row_major(
                            row.data(), 1, row.size()));
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
                result = assembly.add_unilateral_limit(
                    step_contacts_[index].row, {limit.data(), limit.size(), 1});
                if (result != AssemblyDiagnostic::None)
                {
                    return result;
                }
            }
            return AssemblyDiagnostic::None;
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
                         "[termin-qopt] contact assembly failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            std::fprintf(
                stderr,
                "[termin-qopt] contact assembly failed with an unknown "
                "exception\n");
        }
        diagnostic_ = Contact3DDiagnostic::InternalFailure;
        return AssemblyDiagnostic::InternalFailure;
    }

    AssemblyDiagnostic ContactSet3DContribution::assemble_friction(
        DynamicsFrictionAssembly& assembly) noexcept
    {
        if (diagnostic_ != Contact3DDiagnostic::None ||
            step_contacts_.size() != contacts_.size() ||
            states_.size() != contacts_.size())
        {
            return AssemblyDiagnostic::NonFiniteContribution;
        }

        try
        {
            for (std::size_t index = 0; index < contacts_.size(); ++index)
            {
                const DynamicsFrictionContactHandle handle =
                    step_contacts_[index].friction;
                if (!handle.valid())
                {
                    continue;
                }
                PointKinematics3D endpoint_a;
                PointKinematics3D endpoint_b;
                if (!update_state(index, endpoint_a, endpoint_b))
                {
                    diagnostic_ = Contact3DDiagnostic::InvalidState;
                    std::fprintf(
                        stderr,
                        "[termin-qopt] contact %llu produced invalid "
                        "friction kinematics\n",
                        static_cast<unsigned long long>(contacts_[index].key));
                    return AssemblyDiagnostic::NonFiniteContribution;
                }

                const auto add_endpoint =
                    [&](const PointKinematics3D& endpoint, double sign) noexcept
                {
                    if (endpoint.is_static())
                    {
                        return AssemblyDiagnostic::None;
                    }
                    const ConstDenseMatrixView jacobian =
                        endpoint.linear_jacobian_world();
                    std::vector<double> normal_row(endpoint.dof_count());
                    std::vector<double> rows(2 * endpoint.dof_count());
                    for (std::size_t column = 0; column < endpoint.dof_count();
                         ++column)
                    {
                        normal_row[column] =
                            sign *
                            projected(contacts_[index].normal_from_a_to_b_world,
                                      jacobian,
                                      column);
                        rows[column] =
                            sign *
                            projected(step_contacts_[index].tangent_1_world,
                                      jacobian,
                                      column);
                        rows[endpoint.dof_count() + column] =
                            sign *
                            projected(step_contacts_[index].tangent_2_world,
                                      jacobian,
                                      column);
                    }
                    AssemblyDiagnostic result =
                        assembly.add_contact_normal_jacobian(
                            handle,
                            endpoint.dofs,
                            ConstDenseMatrixView::row_major(
                                normal_row.data(), 1, endpoint.dof_count()));
                    if (result != AssemblyDiagnostic::None)
                    {
                        return result;
                    }
                    return assembly.add_tangent_jacobian(
                        handle,
                        endpoint.dofs,
                        ConstDenseMatrixView::row_major(
                            rows.data(), 2, endpoint.dof_count()));
                };

                AssemblyDiagnostic result = add_endpoint(endpoint_a, -1.0);
                if (result == AssemblyDiagnostic::None)
                {
                    result = add_endpoint(endpoint_b, 1.0);
                }
                if (result == AssemblyDiagnostic::None)
                {
                    result = assembly.add_normal_impulse(
                        handle, states_[index].normal_impulse);
                }
                if (result == AssemblyDiagnostic::None)
                {
                    result = assembly.add_friction_coefficient(
                        handle, contacts_[index].friction_coefficient);
                }
                if (result != AssemblyDiagnostic::None)
                {
                    return result;
                }
            }
            return AssemblyDiagnostic::None;
        }
        catch (const std::exception& error)
        {
            std::fprintf(stderr,
                         "[termin-qopt] contact friction assembly failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            std::fprintf(
                stderr,
                "[termin-qopt] contact friction assembly failed with an "
                "unknown exception\n");
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
            std::fprintf(stderr,
                         "[termin-qopt] contact snapshot failed: %s\n",
                         error.what());
        }
        catch (...)
        {
            std::fprintf(
                stderr,
                "[termin-qopt] contact snapshot failed with an unknown "
                "exception\n");
        }
        return AssemblyDiagnostic::InternalFailure;
    }

    void ContactSet3DContribution::commit_step() noexcept
    {
        snapshot_ready_ = false;
        states_snapshot_.clear();
    }

    void ContactSet3DContribution::rollback_step() noexcept
    {
        if (snapshot_ready_)
        {
            states_.swap(states_snapshot_);
            state_cache_.clear();
            warm_started_contact_count_ = 0;
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
                std::fprintf(
                    stderr,
                    "[termin-qopt] cannot update solved contact state\n");
                continue;
            }
            const DenseBlockInfo info =
                unilateral_topology.constraint_topology().block_info(
                    step_contacts_[index].row.block);
            if (!info.ok() || info.size != 1 || info.offset >= reactions.size ||
                info.offset >= tight_mask.size)
            {
                std::fprintf(stderr,
                             "[termin-qopt] invalid contact reaction output\n");
                continue;
            }
            states_[index].normal_impulse = reactions[info.offset];
            states_[index].normal_reaction =
                reactions[info.offset] / time_step_;
            states_[index].active = tight_mask[info.offset] == 1.0;
            state_cache_[index] = states_[index];
        }
    }

    bool ContactSet3DContribution::write_unilateral_warm_start(
        const DynamicsUnilateralTopology& topology,
        DenseVectorView active_mask) const noexcept
    {
        if (states_.size() != step_contacts_.size())
        {
            return false;
        }
        bool wrote_hint = false;
        for (std::size_t index = 0; index < states_.size(); ++index)
        {
            if (!states_[index].active ||
                states_[index].normal_impulse <= kWarmImpulseTolerance)
            {
                continue;
            }
            const DenseBlockInfo info =
                topology.constraint_topology().block_info(
                    step_contacts_[index].row.block);
            if (!info.ok() || info.size != 1 || info.offset >= active_mask.size)
            {
                std::fprintf(stderr,
                             "[termin-qopt] invalid contact warm-start row\n");
                return false;
            }
            active_mask[info.offset] = 1.0;
            wrote_hint = true;
        }
        return wrote_hint;
    }

    void ContactSet3DContribution::apply_friction_solution(
        const DynamicsFrictionTopology& topology,
        ConstDenseVectorView normal_impulses,
        ConstDenseVectorView tangent_impulses,
        ConstDenseVectorView friction_work) noexcept
    {
        if (states_.size() != step_contacts_.size())
        {
            return;
        }
        for (std::size_t index = 0; index < states_.size(); ++index)
        {
            const DynamicsFrictionContactHandle handle =
                step_contacts_[index].friction;
            if (!handle.valid())
            {
                states_[index].tangent_impulse_world = termin::Vec3::zero();
                states_[index].friction_work = 0.0;
                states_[index].sliding = false;
                state_cache_[index] = states_[index];
                continue;
            }
            const DenseBlockInfo contact_info =
                topology.contact_topology().block_info(handle.contact_block);
            const DenseBlockInfo tangent_info =
                topology.tangent_topology().block_info(handle.tangent_block);
            if (!contact_info.ok() || contact_info.size != 1 ||
                contact_info.offset >= friction_work.size ||
                !tangent_info.ok() ||
                contact_info.offset >= normal_impulses.size ||
                tangent_info.size != 2 ||
                tangent_info.offset + 1 >= tangent_impulses.size)
            {
                diagnostic_ = Contact3DDiagnostic::InvalidState;
                std::fprintf(stderr,
                             "[termin-qopt] invalid contact friction output\n");
                continue;
            }
            const double first = tangent_impulses[tangent_info.offset];
            const double second = tangent_impulses[tangent_info.offset + 1];
            states_[index].tangent_impulse_world =
                step_contacts_[index].tangent_1_world * first +
                step_contacts_[index].tangent_2_world * second;
            states_[index].normal_impulse =
                normal_impulses[contact_info.offset];
            states_[index].normal_reaction =
                states_[index].normal_impulse / time_step_;
            const PointKinematics3DResult endpoint_a =
                contacts_[index].endpoint_a.point_kinematics();
            const PointKinematics3DResult endpoint_b =
                contacts_[index].endpoint_b.point_kinematics();
            if (endpoint_a.ok() && endpoint_b.ok())
            {
                const termin::Vec3 relative_velocity =
                    endpoint_b.value.velocity_world -
                    endpoint_a.value.velocity_world;
                const termin::Vec3& normal =
                    contacts_[index].normal_from_a_to_b_world;
                states_[index].tangent_velocity_world =
                    relative_velocity - normal * normal.dot(relative_velocity);
            }
            states_[index].friction_work = friction_work[contact_info.offset];
            const double capacity = contacts_[index].friction_coefficient *
                                    states_[index].normal_impulse;
            states_[index].sliding =
                capacity > 0.0 && states_[index].tangent_impulse_world.norm() >=
                                      capacity *
                                          std::cos(std::numbers::pi / 32.0) *
                                          (1.0 - kFrictionBoundaryTolerance);
            state_cache_[index] = states_[index];
        }
    }

    double ContactSet3DContribution::position_error_linf() const noexcept
    {
        double result = 0.0;
        if (step_contacts_.size() != contacts_.size())
        {
            return contacts_.empty() ? 0.0
                                     : std::numeric_limits<double>::infinity();
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
            const termin::Vec3& normal =
                contacts_[index].normal_from_a_to_b_world;
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
            return contacts_.empty() ? 0.0
                                     : std::numeric_limits<double>::infinity();
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
            const termin::Vec3& normal =
                contacts_[index].normal_from_a_to_b_world;
            const double gap = contacts_[index].signed_gap +
                               normal.dot(endpoint_b.value.position_world -
                                          endpoint_a.value.position_world) -
                               step_contacts_[index].reference_separation;
            const double normal_velocity =
                normal.dot(endpoint_b.value.velocity_world -
                           endpoint_a.value.velocity_world);
            const double target = -std::max(gap, 0.0) / time_step_;
            result = std::max(result, std::max(target - normal_velocity, 0.0));
        }
        return result;
    }

} // namespace termin::physics_qopt
