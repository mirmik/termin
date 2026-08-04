#include <termin/physics_qopt/contact3d.hpp>

#include <termin/physics_qopt/articulation3d_dynamics.hpp>
#include <termin/physics_qopt/multibody3d.hpp>

#include "test_check.hpp"

#include <array>
#include <cmath>
#include <limits>
#include <memory>
#include <utility>
#include <vector>

using namespace termin;
using namespace termin::physics_qopt;
using namespace termin::robotics;

namespace
{

    constexpr double kTolerance = 1e-10;

    void
    check_near(double actual, double expected, double tolerance = kTolerance)
    {
        if (std::abs(actual - expected) > tolerance)
        {
            std::fprintf(stderr,
                         "actual=%.17g expected=%.17g error=%.17g\n",
                         actual,
                         expected,
                         std::abs(actual - expected));
        }
        TERMIN_QOPT_CHECK(std::abs(actual - expected) <= tolerance);
    }

    SpatialInertia3 unit_inertia()
    {
        return {1.0, {1.0, 1.0, 1.0}, Pose3::identity()};
    }

    DynamicsSystemStepOptions step_options(double time_step = 0.01)
    {
        return {
            .time_step = time_step,
            .position_tolerance = 1e-10,
            .velocity_tolerance = 1e-10,
            .max_position_iterations = 10,
        };
    }

    template <typename Contribution>
    Contribution* add(DynamicsSystem& system,
                      std::unique_ptr<Contribution> contribution)
    {
        Contribution* result = contribution.get();
        TERMIN_QOPT_CHECK(system.add_contribution(std::move(contribution)) ==
                          DynamicsSystemDiagnostic::None);
        return result;
    }

    Contact3D ground_contact(std::uint64_t key,
                             RigidBody3DContribution& body,
                             double gap,
                             std::uint64_t group_key = 0)
    {
        return {
            .key = key,
            .group_key = group_key,
            .endpoint_a = ContactEndpoint3D::static_world(Vec3::zero()),
            .endpoint_b = ContactEndpoint3D::rigid_body(body, Vec3::zero()),
            .normal_from_a_to_b_world = Vec3::unit_y(),
            .signed_gap = gap,
        };
    }

    void test_body_static_assembly()
    {
        RigidBody3DContribution body(unit_inertia(),
                                     {Pose3::translation(0.0, 0.25, 0.0),
                                      {{0.3, -0.4, 0.5}, {0.6, -0.7, 0.8}}});
        ContactSet3DContribution contacts("assembly-contact");
        TERMIN_QOPT_CHECK(contacts.set_contacts({ground_contact(
                              17, body, 0.25)}) == Contact3DDiagnostic::None);

        DynamicsTopology topology;
        TERMIN_QOPT_CHECK(body.register_topology(topology) ==
                          AssemblyDiagnostic::None);
        TERMIN_QOPT_CHECK(contacts.register_topology(topology) ==
                          AssemblyDiagnostic::None);
        TERMIN_QOPT_CHECK(topology.finalize() == AssemblyDiagnostic::None);
        DynamicsUnilateralTopology unilateral_topology;
        TERMIN_QOPT_CHECK(contacts.register_unilateral_constraints(
                              unilateral_topology, 0.1) ==
                          AssemblyDiagnostic::None);
        TERMIN_QOPT_CHECK(unilateral_topology.finalize() ==
                          AssemblyDiagnostic::None);

        std::array<double, 36> mass{};
        std::array<double, 6> load{};
        std::array<double, 6> unilateral_jacobian{};
        std::array<double, 1> unilateral_limit{};
        DynamicsAssembly assembly(
            topology,
            unilateral_topology,
            {
                DenseMatrixView::row_major(mass.data(), 6, 6),
                {load.data(), load.size(), 1},
                DenseMatrixView::row_major(nullptr, 0, 6),
                {},
                DenseMatrixView::row_major(unilateral_jacobian.data(), 1, 6),
                {unilateral_limit.data(), unilateral_limit.size(), 1},
            });
        TERMIN_QOPT_CHECK(assembly.valid());
        TERMIN_QOPT_CHECK(assembly.clear() == AssemblyDiagnostic::None);
        TERMIN_QOPT_CHECK(
            contacts.assemble(assembly,
                              DynamicsAssemblyPhase::PositionProjection) ==
            AssemblyDiagnostic::None);
        const std::array<double, 6> expected{0.0, -1.0, 0.0, 0.0, 0.0, 0.0};
        for (std::size_t index = 0; index < expected.size(); ++index)
        {
            check_near(unilateral_jacobian[index], expected[index]);
        }
        check_near(unilateral_limit[0], 0.25);

        TERMIN_QOPT_CHECK(assembly.clear() == AssemblyDiagnostic::None);
        TERMIN_QOPT_CHECK(
            contacts.assemble(assembly,
                              DynamicsAssemblyPhase::VelocityProjection) ==
            AssemblyDiagnostic::None);
        check_near(unilateral_limit[0], 2.5);
        TERMIN_QOPT_CHECK(contacts.states().size() == 1);
        check_near(contacts.states()[0].normal_velocity, -0.7);
    }

    void test_two_dynamic_endpoints_accumulate()
    {
        RigidBody3DContribution body_a(unit_inertia());
        RigidBody3DContribution body_b(unit_inertia());
        ContactSet3DContribution contacts;
        TERMIN_QOPT_CHECK(contacts.set_contacts({{
                              .key = 3,
                              .endpoint_a = ContactEndpoint3D::rigid_body(
                                  body_a, Vec3::zero()),
                              .endpoint_b = ContactEndpoint3D::rigid_body(
                                  body_b, Vec3::zero()),
                              .normal_from_a_to_b_world = Vec3::unit_x(),
                              .signed_gap = 0.0,
                          }}) == Contact3DDiagnostic::None);

        DynamicsTopology topology;
        TERMIN_QOPT_CHECK(body_a.register_topology(topology) ==
                          AssemblyDiagnostic::None);
        TERMIN_QOPT_CHECK(body_b.register_topology(topology) ==
                          AssemblyDiagnostic::None);
        TERMIN_QOPT_CHECK(topology.finalize() == AssemblyDiagnostic::None);
        DynamicsUnilateralTopology unilateral_topology;
        TERMIN_QOPT_CHECK(contacts.register_unilateral_constraints(
                              unilateral_topology, 0.01) ==
                          AssemblyDiagnostic::None);
        TERMIN_QOPT_CHECK(unilateral_topology.finalize() ==
                          AssemblyDiagnostic::None);
        std::array<double, 144> mass{};
        std::array<double, 12> load{};
        std::array<double, 12> row{};
        std::array<double, 1> limit{};
        DynamicsAssembly assembly(
            topology,
            unilateral_topology,
            {
                DenseMatrixView::row_major(mass.data(), 12, 12),
                {load.data(), load.size(), 1},
                DenseMatrixView::row_major(nullptr, 0, 12),
                {},
                DenseMatrixView::row_major(row.data(), 1, 12),
                {limit.data(), limit.size(), 1},
            });
        TERMIN_QOPT_CHECK(assembly.clear() == AssemblyDiagnostic::None);
        TERMIN_QOPT_CHECK(
            contacts.assemble(assembly,
                              DynamicsAssemblyPhase::VelocityProjection) ==
            AssemblyDiagnostic::None);
        check_near(row[0], 1.0);
        check_near(row[6], -1.0);
        for (std::size_t index = 1; index < 6; ++index)
        {
            check_near(row[index], 0.0);
            check_near(row[index + 6], 0.0);
        }
    }

    void test_split_position_correction()
    {
        DynamicsSystem system;
        auto* body =
            add(system,
                std::make_unique<RigidBody3DContribution>(
                    unit_inertia(),
                    RigidBody3DState{Pose3::translation(0.0, -0.1, 0.0),
                                     Screw3::zero()}));
        auto contacts = std::make_unique<ContactSet3DContribution>("ground");
        ContactSet3DContribution* contact_set = contacts.get();
        TERMIN_QOPT_CHECK(contacts->set_contacts({ground_contact(
                              1, *body, -0.1)}) == Contact3DDiagnostic::None);
        add(system, std::move(contacts));
        TERMIN_QOPT_CHECK(system.finalize() == DynamicsSystemDiagnostic::None);

        const DynamicsSystemStepResult result = system.step(step_options());
        TERMIN_QOPT_CHECK(result.ok());
        TERMIN_QOPT_CHECK(result.position_iterations >= 1);
        check_near(body->state().pose.lin.y, 0.0, 2e-10);
        check_near(body->state().velocity_local.lin.y, 0.0, 2e-10);
        TERMIN_QOPT_CHECK(contact_set->states().size() == 1);
        check_near(contact_set->states()[0].signed_gap, 0.0, 2e-10);
        check_near(contact_set->states()[0].normal_impulse, 0.0, 2e-10);
    }

    void test_impact_and_removal()
    {
        DynamicsSystem system;
        auto* body = add(system,
                         std::make_unique<RigidBody3DContribution>(
                             unit_inertia(),
                             RigidBody3DState{Pose3::translation(0.0, 0.0, 0.0),
                                              {{}, {0.0, -2.0, 0.0}}}));
        auto contacts = std::make_unique<ContactSet3DContribution>("impact");
        ContactSet3DContribution* contact_set = contacts.get();
        TERMIN_QOPT_CHECK(contacts->set_contacts({ground_contact(
                              5, *body, 0.0)}) == Contact3DDiagnostic::None);
        add(system, std::move(contacts));
        TERMIN_QOPT_CHECK(system.finalize() == DynamicsSystemDiagnostic::None);

        const double energy_before = body->total_energy();
        const DynamicsSystemStepResult impact = system.step(step_options());
        if (!impact.ok())
        {
            std::fprintf(
                stderr,
                "impact failed: status=%s diagnostic=%s qp=%s position=%.17g "
                "velocity=%.17g iterations=%zu\n",
                qp_status_name(impact.status).data(),
                dynamics_system_diagnostic_name(impact.diagnostic).data(),
                qp_diagnostic_name(impact.velocity_projection.diagnostic)
                    .data(),
                impact.position_constraint_linf,
                impact.velocity_constraint_linf,
                impact.position_iterations);
            std::fprintf(stderr,
                         "qp residuals: stationarity=%.17g equality=%.17g "
                         "inequality=%.17g dual=%.17g complementarity=%.17g "
                         "active=%zu iterations=%zu\n",
                         impact.velocity_projection.stationarity_linf,
                         impact.velocity_projection.equality_linf,
                         impact.velocity_projection.inequality_linf,
                         impact.velocity_projection.dual_linf,
                         impact.velocity_projection.complementarity_linf,
                         impact.velocity_projection.active_set_size,
                         impact.velocity_projection.iterations);
        }
        TERMIN_QOPT_CHECK(impact.ok());
        check_near(body->state().pose.lin.y, 0.0, 2e-10);
        check_near(body->state().velocity_local.lin.y, 0.0, 2e-10);
        TERMIN_QOPT_CHECK(contact_set->states()[0].normal_impulse > 0.0);
        check_near(contact_set->states()[0].normal_impulse, 2.0, 2e-9);
        TERMIN_QOPT_CHECK(contact_set->states()[0].active);
        TERMIN_QOPT_CHECK(body->total_energy() <= energy_before + 1e-10);

        TERMIN_QOPT_CHECK(contact_set->set_contacts({}) ==
                          Contact3DDiagnostic::None);
        TERMIN_QOPT_CHECK(system.step(step_options()).ok());
        TERMIN_QOPT_CHECK(contact_set->states().empty());
    }

    void test_resting_support_and_separation()
    {
        DynamicsSystem system;
        auto* body =
            add(system,
                std::make_unique<RigidBody3DContribution>(
                    unit_inertia(), RigidBody3DState{}, Vec3{0.0, -9.81, 0.0}));
        auto contacts = std::make_unique<ContactSet3DContribution>("support");
        ContactSet3DContribution* contact_set = contacts.get();
        TERMIN_QOPT_CHECK(contacts->set_contacts({ground_contact(
                              9, *body, 0.0)}) == Contact3DDiagnostic::None);
        add(system, std::move(contacts));
        TERMIN_QOPT_CHECK(system.finalize() == DynamicsSystemDiagnostic::None);

        TERMIN_QOPT_CHECK(system.step(step_options()).ok());
        check_near(body->state().pose.lin.y, 0.0, 2e-10);
        check_near(body->state().velocity_local.lin.y, 0.0, 2e-10);
        check_near(contact_set->states()[0].normal_reaction, 9.81, 2e-8);

        TERMIN_QOPT_CHECK(body->set_gravity_world(Vec3::zero()) ==
                          Multibody3DDiagnostic::None);
        RigidBody3DState separating = body->state();
        separating.velocity_local.lin.y = 1.0;
        TERMIN_QOPT_CHECK(body->set_state(separating) ==
                          Multibody3DDiagnostic::None);
        TERMIN_QOPT_CHECK(system.step(step_options()).ok());
        check_near(body->state().velocity_local.lin.y, 1.0, 2e-10);
        check_near(contact_set->states()[0].normal_impulse, 0.0, 2e-10);
        TERMIN_QOPT_CHECK(!contact_set->states()[0].active);
    }

    void test_ground_coulomb_friction()
    {
        DynamicsSystem system;
        auto* body =
            add(system,
                std::make_unique<RigidBody3DContribution>(
                    unit_inertia(),
                    RigidBody3DState{Pose3::identity(), {{}, {1.0, 0.0, 0.0}}},
                    Vec3{0.0, -9.81, 0.0}));
        auto contacts = std::make_unique<ContactSet3DContribution>("friction");
        ContactSet3DContribution* contact_set = contacts.get();
        Contact3D contact = ground_contact(40, *body, 0.0);
        contact.friction_coefficient = 0.5;
        TERMIN_QOPT_CHECK(contacts->set_contacts({contact}) ==
                          Contact3DDiagnostic::None);
        add(system, std::move(contacts));
        TERMIN_QOPT_CHECK(system.finalize() == DynamicsSystemDiagnostic::None);

        TERMIN_QOPT_CHECK(system.step(step_options()).ok());
        const double normal_impulse = 9.81 * 0.01;
        check_near(
            contact_set->states()[0].normal_impulse, normal_impulse, 2e-8);
        check_near(body->state().velocity_local.lin.x,
                   1.0 - 0.5 * normal_impulse,
                   2e-8);
        check_near(contact_set->states()[0].tangent_impulse_world.x,
                   -0.5 * normal_impulse,
                   2e-8);
        TERMIN_QOPT_CHECK(contact_set->states()[0].friction_work < 0.0);
        TERMIN_QOPT_CHECK(contact_set->states()[0].sliding);

        RigidBody3DState slow = body->state();
        slow.velocity_local.lin = {0.01, 0.0, 0.0};
        TERMIN_QOPT_CHECK(body->set_state(slow) == Multibody3DDiagnostic::None);
        TERMIN_QOPT_CHECK(system.step(step_options()).ok());
        check_near(body->state().velocity_local.lin.x, 0.0, 2e-8);
        check_near(
            contact_set->states()[0].tangent_impulse_world.x, -0.01, 2e-8);
        TERMIN_QOPT_CHECK(!contact_set->states()[0].sliding);
    }

    void test_persistent_contact_cache_and_warm_start()
    {
        DynamicsSystem system;
        auto* body =
            add(system,
                std::make_unique<RigidBody3DContribution>(
                    unit_inertia(), RigidBody3DState{}, Vec3{0.0, -9.81, 0.0}));
        auto contacts =
            std::make_unique<ContactSet3DContribution>("persistent");
        ContactSet3DContribution* contact_set = contacts.get();
        TERMIN_QOPT_CHECK(
            contacts->set_contacts({ground_contact(9, *body, 0.0, 77)}, {77}) ==
            Contact3DDiagnostic::None);
        add(system, std::move(contacts));
        TERMIN_QOPT_CHECK(system.finalize() == DynamicsSystemDiagnostic::None);

        const DynamicsSystemStepResult first = system.step(step_options());
        TERMIN_QOPT_CHECK(first.ok());
        TERMIN_QOPT_CHECK(contact_set->cached_contact_count() == 1);
        TERMIN_QOPT_CHECK(contact_set->states()[0].active);

        // The geometric query missed the exactly touching pair, but the pair
        // itself remains live. The cached material points keep the row alive.
        TERMIN_QOPT_CHECK(contact_set->set_contacts({}, {77}) ==
                          Contact3DDiagnostic::None);
        TERMIN_QOPT_CHECK(contact_set->contacts().size() == 1);
        const DynamicsSystemStepResult second = system.step(step_options());
        TERMIN_QOPT_CHECK(second.ok());
        TERMIN_QOPT_CHECK(contact_set->warm_started_contact_count() == 1);
        TERMIN_QOPT_CHECK(second.velocity_projection.iterations <=
                          first.velocity_projection.iterations);
        check_near(contact_set->states()[0].normal_reaction, 9.81, 2e-8);

        // A fresh feature in the same live group replaces, rather than
        // accumulating with, the old feature.
        TERMIN_QOPT_CHECK(
            contact_set->set_contacts({ground_contact(10, *body, 0.0, 77)},
                                      {77}) == Contact3DDiagnostic::None);
        TERMIN_QOPT_CHECK(contact_set->contacts().size() == 1);
        TERMIN_QOPT_CHECK(contact_set->contacts()[0].key == 10);
        TERMIN_QOPT_CHECK(contact_set->cached_contact_count() == 0);

        TERMIN_QOPT_CHECK(system.step(step_options()).ok());
        TERMIN_QOPT_CHECK(contact_set->cached_contact_count() == 1);
        TERMIN_QOPT_CHECK(contact_set->set_contacts({}, {}) ==
                          Contact3DDiagnostic::None);
        TERMIN_QOPT_CHECK(contact_set->contacts().empty());
        TERMIN_QOPT_CHECK(contact_set->cached_contact_count() == 0);
    }

    void test_contact_cache_order_capacity_and_rollback()
    {
        RigidBody3DContribution body(unit_inertia());
        ContactSet3DContribution ordered;
        TERMIN_QOPT_CHECK(
            ordered.set_contacts({ground_contact(30, body, 0.0),
                                  ground_contact(10, body, 0.0),
                                  ground_contact(20, body, 0.0)}) ==
            Contact3DDiagnostic::None);
        TERMIN_QOPT_CHECK(ordered.contacts()[0].key == 10);
        TERMIN_QOPT_CHECK(ordered.contacts()[1].key == 20);
        TERMIN_QOPT_CHECK(ordered.contacts()[2].key == 30);
        TERMIN_QOPT_CHECK(ordered.set_maximum_cached_contacts(3));
        TERMIN_QOPT_CHECK(
            ordered.set_contacts({ground_contact(1, body, 0.0),
                                  ground_contact(2, body, 0.0),
                                  ground_contact(3, body, 0.0),
                                  ground_contact(4, body, 0.0)}) ==
            Contact3DDiagnostic::CacheCapacityExceeded);

        DynamicsSystem system;
        auto* dynamic_body =
            add(system,
                std::make_unique<RigidBody3DContribution>(
                    unit_inertia(), RigidBody3DState{}, Vec3{0.0, -9.81, 0.0}));
        auto contacts =
            std::make_unique<ContactSet3DContribution>("rollback-cache");
        ContactSet3DContribution* contact_set = contacts.get();
        TERMIN_QOPT_CHECK(
            contacts->set_contacts({ground_contact(1, *dynamic_body, 0.0, 99)},
                                   {99}) == Contact3DDiagnostic::None);
        add(system, std::move(contacts));
        TERMIN_QOPT_CHECK(system.finalize() == DynamicsSystemDiagnostic::None);
        TERMIN_QOPT_CHECK(system.step(step_options()).ok());
        TERMIN_QOPT_CHECK(contact_set->cached_contact_count() == 1);

        Contact3D invalid = ground_contact(1, *dynamic_body, 0.0, 99);
        invalid.normal_from_a_to_b_world = {0.0, 2.0, 0.0};
        TERMIN_QOPT_CHECK(contact_set->set_contacts({invalid}, {99}) ==
                          Contact3DDiagnostic::InvalidNormal);
        TERMIN_QOPT_CHECK(!system.step(step_options()).ok());
        TERMIN_QOPT_CHECK(contact_set->cached_contact_count() == 0);
    }

    void test_articulation_endpoint()
    {
        std::vector<ArticulationUnit3D> units{
            {
                .parent_unit = articulation_root_frame,
                .parent_to_unit_zero = Pose3::identity(),
                .motion_twist_at_unit = {Vec3::zero(), Vec3::unit_y()},
                .inertia = unit_inertia(),
            },
        };
        Articulation3D model(std::move(units), {{0.2}, {-0.3}});
        Articulation3DDynamicsContribution articulation(model);
        DynamicsTopology topology;
        TERMIN_QOPT_CHECK(articulation.register_topology(topology) ==
                          AssemblyDiagnostic::None);
        TERMIN_QOPT_CHECK(topology.finalize() == AssemblyDiagnostic::None);
        const ContactEndpoint3D endpoint =
            ContactEndpoint3D::articulation_unit(articulation, 0, Vec3::zero());
        const PointKinematics3DResult result = endpoint.point_kinematics();
        TERMIN_QOPT_CHECK(result.ok());
        TERMIN_QOPT_CHECK(result.value.dof_count() == 1);
        check_near(result.value.position_world.y, 0.2);
        check_near(result.value.velocity_world.y, -0.3);
    }

    void test_articulation_contact_rows()
    {
        RigidBody3DContribution body(unit_inertia());
        std::vector<ArticulationUnit3D> units{
            {
                .parent_unit = articulation_root_frame,
                .parent_to_unit_zero = Pose3::identity(),
                .motion_twist_at_unit = {Vec3::zero(), Vec3::unit_y()},
                .inertia = unit_inertia(),
            },
        };
        Articulation3D model(std::move(units), {{0.0}, {0.0}});
        Articulation3DDynamicsContribution articulation(model);
        ContactSet3DContribution contacts("mixed-rows");
        TERMIN_QOPT_CHECK(
            contacts.set_contacts({
                {
                    .key = 20,
                    .endpoint_a = ContactEndpoint3D::static_world(Vec3::zero()),
                    .endpoint_b = ContactEndpoint3D::articulation_unit(
                        articulation, 0, Vec3::zero()),
                    .normal_from_a_to_b_world = Vec3::unit_y(),
                    .signed_gap = 0.0,
                },
                {
                    .key = 21,
                    .endpoint_a =
                        ContactEndpoint3D::rigid_body(body, Vec3::zero()),
                    .endpoint_b = ContactEndpoint3D::articulation_unit(
                        articulation, 0, Vec3::zero()),
                    .normal_from_a_to_b_world = Vec3::unit_y(),
                    .signed_gap = 0.0,
                },
            }) == Contact3DDiagnostic::None);

        DynamicsTopology topology;
        TERMIN_QOPT_CHECK(body.register_topology(topology) ==
                          AssemblyDiagnostic::None);
        TERMIN_QOPT_CHECK(articulation.register_topology(topology) ==
                          AssemblyDiagnostic::None);
        TERMIN_QOPT_CHECK(topology.finalize() == AssemblyDiagnostic::None);
        DynamicsUnilateralTopology unilateral_topology;
        TERMIN_QOPT_CHECK(contacts.register_unilateral_constraints(
                              unilateral_topology, 0.01) ==
                          AssemblyDiagnostic::None);
        TERMIN_QOPT_CHECK(unilateral_topology.finalize() ==
                          AssemblyDiagnostic::None);

        std::array<double, 49> mass{};
        std::array<double, 7> load{};
        std::array<double, 14> rows{};
        std::array<double, 2> limits{};
        DynamicsAssembly assembly(
            topology,
            unilateral_topology,
            {
                DenseMatrixView::row_major(mass.data(), 7, 7),
                {load.data(), load.size(), 1},
                DenseMatrixView::row_major(nullptr, 0, 7),
                {},
                DenseMatrixView::row_major(rows.data(), 2, 7),
                {limits.data(), limits.size(), 1},
            });
        TERMIN_QOPT_CHECK(assembly.clear() == AssemblyDiagnostic::None);
        TERMIN_QOPT_CHECK(
            contacts.assemble(assembly,
                              DynamicsAssemblyPhase::VelocityProjection) ==
            AssemblyDiagnostic::None);
        for (std::size_t column = 0; column < 6; ++column)
        {
            check_near(rows[column], 0.0);
        }
        check_near(rows[6], -1.0);
        check_near(rows[7], 0.0);
        check_near(rows[8], 1.0);
        for (std::size_t column = 9; column < 13; ++column)
        {
            check_near(rows[column], 0.0);
        }
        check_near(rows[13], -1.0);
    }

    void test_validation()
    {
        RigidBody3DContribution body(unit_inertia());
        ContactSet3DContribution contacts;
        Contact3D contact = ground_contact(1, body, 0.0);
        contact.normal_from_a_to_b_world = {0.0, 2.0, 0.0};
        TERMIN_QOPT_CHECK(contacts.set_contacts({contact}) ==
                          Contact3DDiagnostic::InvalidNormal);

        contact = ground_contact(1, body, 0.0);
        contact.signed_gap = std::numeric_limits<double>::quiet_NaN();
        TERMIN_QOPT_CHECK(contacts.set_contacts({contact}) ==
                          Contact3DDiagnostic::NonFiniteGap);

        contact = ground_contact(1, body, 0.0);
        TERMIN_QOPT_CHECK(contacts.set_contacts({contact, contact}) ==
                          Contact3DDiagnostic::DuplicateKey);

        contact.endpoint_b = ContactEndpoint3D::static_world(Vec3::unit_y());
        TERMIN_QOPT_CHECK(contacts.set_contacts({contact}) ==
                          Contact3DDiagnostic::InvalidEndpointPair);

        contact = ground_contact(1, body, 0.0);
        contact.friction_coefficient = -0.1;
        TERMIN_QOPT_CHECK(contacts.set_contacts({contact}) ==
                          Contact3DDiagnostic::InvalidFrictionCoefficient);
    }

    void test_invalid_contact_step_is_transactional()
    {
        DynamicsSystem system;
        auto* body = add(
            system, std::make_unique<RigidBody3DContribution>(unit_inertia()));
        auto contacts =
            std::make_unique<ContactSet3DContribution>("invalid-step");
        Contact3D invalid = ground_contact(1, *body, 0.0);
        invalid.normal_from_a_to_b_world = Vec3{0.0, 3.0, 0.0};
        TERMIN_QOPT_CHECK(contacts->set_contacts({invalid}) ==
                          Contact3DDiagnostic::InvalidNormal);
        add(system, std::move(contacts));
        TERMIN_QOPT_CHECK(system.finalize() == DynamicsSystemDiagnostic::None);
        const RigidBody3DState before = body->state();
        const DynamicsSystemStepResult result = system.step(step_options());
        TERMIN_QOPT_CHECK(!result.ok());
        check_near(body->state().pose.lin.y, before.pose.lin.y);
        check_near(body->state().velocity_local.lin.y,
                   before.velocity_local.lin.y);
    }

} // namespace

int main()
{
    test_body_static_assembly();
    test_two_dynamic_endpoints_accumulate();
    test_split_position_correction();
    test_impact_and_removal();
    test_resting_support_and_separation();
    test_ground_coulomb_friction();
    test_persistent_contact_cache_and_warm_start();
    test_contact_cache_order_capacity_and_rollback();
    test_articulation_endpoint();
    test_articulation_contact_rows();
    test_validation();
    test_invalid_contact_step_is_transactional();
    return 0;
}
