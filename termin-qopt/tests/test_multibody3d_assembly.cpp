#include <termin/qopt/multibody3d.hpp>

#include "test_check.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <initializer_list>
#include <vector>

using namespace termin;
using namespace termin::qopt;

namespace
{

    constexpr double kTolerance = 1e-12;

    struct AssembledSystem
    {
        DynamicsTopology topology;
        std::vector<double> mass;
        std::vector<double> load;
        std::vector<double> jacobian;
        std::vector<double> rhs;
    };

    void check_near(double actual, double expected, double tolerance = kTolerance)
    {
        TERMIN_QOPT_CHECK(std::abs(actual - expected) <= tolerance);
    }

    void check_values(const std::vector<double>& actual,
                      std::initializer_list<double> expected,
                      double tolerance = kTolerance)
    {
        TERMIN_QOPT_CHECK(actual.size() == expected.size());
        std::size_t index = 0;
        for (const double value : expected)
        {
            check_near(actual[index], value, tolerance);
            ++index;
        }
    }

    AssembledSystem assemble(std::initializer_list<DynamicsContribution*> contributions,
                             DynamicsAssemblyPhase phase)
    {
        AssembledSystem result;
        std::size_t contribution_index = 0;
        for (DynamicsContribution* contribution : contributions)
        {
            TERMIN_QOPT_CHECK(contribution != nullptr);
            const AssemblyDiagnostic diagnostic =
                contribution->register_topology(result.topology);
            if (diagnostic != AssemblyDiagnostic::None)
            {
                std::fprintf(stderr,
                             "contribution %zu topology registration failed: %s\n",
                             contribution_index,
                             assembly_diagnostic_name(diagnostic).data());
            }
            TERMIN_QOPT_CHECK(diagnostic == AssemblyDiagnostic::None);
            ++contribution_index;
        }
        TERMIN_QOPT_CHECK(result.topology.finalize() == AssemblyDiagnostic::None);

        const std::size_t dofs = result.topology.dof_count();
        const std::size_t constraints = result.topology.constraint_count();
        result.mass.assign(dofs * dofs, 91.0);
        result.load.assign(dofs, 92.0);
        result.jacobian.assign(constraints * dofs, 93.0);
        result.rhs.assign(constraints, 94.0);

        DynamicsAssembly assembly(
            result.topology,
            {
                DenseMatrixView::row_major(result.mass.data(), dofs, dofs),
                {result.load.data(), result.load.size(), 1},
                DenseMatrixView::row_major(result.jacobian.data(), constraints, dofs),
                {result.rhs.data(), result.rhs.size(), 1},
            });
        TERMIN_QOPT_CHECK(assembly.valid());
        TERMIN_QOPT_CHECK(assembly.clear() == AssemblyDiagnostic::None);
        for (DynamicsContribution* contribution : contributions)
        {
            TERMIN_QOPT_CHECK(contribution->assemble(assembly, phase) ==
                              AssemblyDiagnostic::None);
        }
        return result;
    }

    RigidBody3DContribution body(RigidBody3DState state = {},
                                 Vec3 gravity = Vec3::zero(),
                                 SpatialInertia3 inertia = {2.0, {3.0, 4.0, 5.0}, {}},
                                 std::string_view name = "body")
    {
        return RigidBody3DContribution(inertia, state, gravity, name);
    }

    void test_rigid_body_equations()
    {
        auto contribution = body({{Quat::identity(), {4.0, 5.0, 6.0}},
                                  Screw3{{1.0, 2.0, 3.0}, {7.0, 8.0, 9.0}}},
                                 {0.0, -10.0, 1.0});

        const AssembledSystem acceleration =
            assemble({&contribution}, DynamicsAssemblyPhase::Acceleration);
        check_values(acceleration.mass,
                     {
                         2, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0,
                         0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 5,
                     });
        // Body-fixed equations contain the full spatial bias ad*_V M V. Besides
        // the gyroscopic torque, its force part contains omega x (m v).
        check_values(acceleration.load, {12, -44, 14, -6, 6, -2});
        TERMIN_QOPT_CHECK(acceleration.jacobian.empty());
        TERMIN_QOPT_CHECK(acceleration.rhs.empty());

        // Velocity projection minimizes ||v_new-v_old||_M and therefore
        // assembles M v_old as its load. Position projection has a zero load.
        const AssembledSystem velocity =
            assemble({&contribution}, DynamicsAssemblyPhase::VelocityProjection);
        check_values(velocity.load, {14, 16, 18, 3, 8, 15});
        const AssembledSystem position =
            assemble({&contribution}, DynamicsAssemblyPhase::PositionProjection);
        check_values(position.load, {0, 0, 0, 0, 0, 0});
    }

    void test_offset_center_of_mass_equations()
    {
        const SpatialInertia3 inertia{
            2.0,
            {3.0, 4.0, 5.0},
            {Quat::identity(), {1.0, 0.0, 0.0}},
        };
        auto contribution = body(
            {{Quat::identity(), Vec3::zero()}, Screw3{{0.0, 0.0, 2.0}, Vec3::zero()}},
            {0.0, 0.0, -10.0},
            inertia);
        const AssembledSystem system =
            assemble({&contribution}, DynamicsAssemblyPhase::Acceleration);
        check_values(system.mass,
                     {
                         2, 0, 0, 0, 0, 0, 0, 2, 0,  0, 0, 2, 0, 0, 2, 0, -2, 0,
                         0, 0, 0, 3, 0, 0, 0, 0, -2, 0, 6, 0, 0, 2, 0, 0, 0,  7,
                     });
        // The origin is one metre from the center of mass. The first three rows
        // include the centrifugal acceleration of that center; gravity also
        // contributes its moment about the body origin.
        check_values(system.load, {8, 0, -20, 0, 20, 0});
    }

    void test_rotated_body_uses_local_dofs()
    {
        const Quat orientation =
            Quat::from_axis_angle(Vec3::unit_z(), 0.5 * 3.14159265358979323846);
        auto rigid_body =
            body({{orientation, Vec3::zero()}, Screw3::zero()}, {1.0, 2.0, 3.0});
        FixedPointJoint3DContribution joint(
            rigid_body, Vec3::unit_x(), Vec3::unit_y(), "rotated-fixed-point");
        const AssembledSystem system =
            assemble({&rigid_body, &joint}, DynamicsAssemblyPhase::Acceleration);

        // The body rotation does not rotate its local mass block. Gravity and
        // the joint columns are instead transformed at their contribution
        // boundaries.
        check_values(system.mass,
                     {
                         2, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0,
                         0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 5,
                     });
        check_values(system.load, {4, -2, 6, 0, 0, 0});
        check_values(system.jacobian,
                     {
                         0,
                         -1,
                         0,
                         0,
                         0,
                         -1,
                         1,
                         0,
                         0,
                         0,
                         0,
                         0,
                         0,
                         0,
                         1,
                         0,
                         -1,
                         0,
                     },
                     1e-11);
    }

    void test_force_adds_to_body_load()
    {
        auto rigid_body = body();
        ForceOnBody3DContribution force(rigid_body,
                                        {{14.0, 15.0, 16.0}, {11.0, 12.0, 13.0}});
        const AssembledSystem system =
            assemble({&rigid_body, &force}, DynamicsAssemblyPhase::Acceleration);
        check_values(system.load, {11, 12, 13, 14, 15, 16});
    }

    void test_fixed_point_equations()
    {
        auto rigid_body = body({{Quat::identity(), {4.0, 5.0, 6.0}},
                                Screw3{{2.0, -1.0, 3.0}, Vec3::zero()}});
        FixedPointJoint3DContribution joint(
            rigid_body, {1.0, 2.0, 3.0}, {1.0, 1.0, 1.0}, "fixed-point");

        const AssembledSystem acceleration =
            assemble({&rigid_body, &joint}, DynamicsAssemblyPhase::Acceleration);
        check_values(acceleration.jacobian,
                     {
                         1,
                         0,
                         0,
                         0,
                         3,
                         -2,
                         0,
                         1,
                         0,
                         -3,
                         0,
                         1,
                         0,
                         0,
                         1,
                         2,
                         -1,
                         0,
                     });
        // omega x (omega x r) = (4, -37, -15).
        check_values(acceleration.rhs, {-4, 37, 15});

        const AssembledSystem position =
            assemble({&rigid_body, &joint}, DynamicsAssemblyPhase::PositionProjection);
        check_values(position.rhs, {-4, -6, -8});
        const AssembledSystem velocity =
            assemble({&rigid_body, &joint}, DynamicsAssemblyPhase::VelocityProjection);
        check_values(velocity.rhs, {0, 0, 0});
    }

    void test_point_joint_equations()
    {
        auto body_a = body({{Quat::identity(), {-1.0, 0.0, 0.0}},
                            Screw3{{0.0, 0.0, 2.0}, Vec3::zero()}},
                           Vec3::zero(),
                           {2.0, {3.0, 4.0, 5.0}, {}},
                           "body-a");
        auto body_b = body({{Quat::identity(), {1.0, 0.0, 0.0}},
                            Screw3{{0.0, 0.0, 3.0}, Vec3::zero()}},
                           Vec3::zero(),
                           {2.0, {3.0, 4.0, 5.0}, {}},
                           "body-b");
        PointJoint3DContribution joint(
            body_a, {1.0, 0.0, 0.0}, body_b, {0.0, 2.0, 0.0}, "point");
        const AssembledSystem acceleration =
            assemble({&body_a, &body_b, &joint}, DynamicsAssemblyPhase::Acceleration);
        check_values(acceleration.jacobian,
                     {
                         1, 0,  0, 0, 0, 0, -1, 0, 0, 0, 0,  2, 0, 1, 0,  0,  0, 1,
                         0, -1, 0, 0, 0, 0, 0,  0, 1, 0, -1, 0, 0, 0, -1, -2, 0, 0,
                     });
        check_values(acceleration.rhs, {4, -18, 0});

        const AssembledSystem position = assemble(
            {&body_a, &body_b, &joint}, DynamicsAssemblyPhase::PositionProjection);
        // pA+rA=(0,0,0), pB+rB=(1,2,0).
        check_values(position.rhs, {1, 2, 0});
    }

    void test_fixed_revolute_equations()
    {
        auto rigid_body = body({{Quat::identity(), {0.0, 0.0, 0.0}},
                                Screw3{{1.0, 2.0, 3.0}, Vec3::zero()}});
        FixedRevoluteJoint3DContribution joint(rigid_body,
                                               {1.0, 0.0, 0.0},
                                               Vec3::unit_y(),
                                               Vec3::zero(),
                                               Vec3::unit_y(),
                                               "fixed-revolute");
        const AssembledSystem acceleration =
            assemble({&rigid_body, &joint}, DynamicsAssemblyPhase::Acceleration);
        check_values(acceleration.jacobian,
                     {
                         1, 0,  0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1,
                         0, -1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0,
                     });
        check_values(acceleration.rhs, {13, -2, -3, 2, -6});
    }

    void test_revolute_equations()
    {
        auto body_a = body({}, Vec3::zero(), {2.0, {3.0, 4.0, 5.0}, {}}, "body-a");
        auto body_b = body({}, Vec3::zero(), {2.0, {3.0, 4.0, 5.0}, {}}, "body-b");
        RevoluteJoint3DContribution joint(body_a,
                                          {1.0, 0.0, 0.0},
                                          Vec3::unit_y(),
                                          body_b,
                                          {0.0, 2.0, 0.0},
                                          Vec3::unit_y(),
                                          "revolute");
        const AssembledSystem system =
            assemble({&body_a, &body_b, &joint}, DynamicsAssemblyPhase::Acceleration);
        check_values(system.jacobian,
                     {
                         1, 0, 0,  0,  0,  0, -1, 0, 0, 0, 0, 2, 0,  1,  0,
                         0, 0, 1,  0,  -1, 0, 0,  0, 0, 0, 0, 1, 0,  -1, 0,
                         0, 0, -1, -2, 0,  0, 0,  0, 0, 0, 0, 1, 0,  0,  0,
                         0, 0, -1, 0,  0,  0, 1,  0, 0, 0, 0, 0, -1, 0,  0,
                     });
        check_values(system.rhs, {0, 0, 0, 0, 0});
    }

} // namespace

int main()
{
    test_rigid_body_equations();
    test_offset_center_of_mass_equations();
    test_rotated_body_uses_local_dofs();
    test_force_adds_to_body_load();
    test_fixed_point_equations();
    test_point_joint_equations();
    test_fixed_revolute_equations();
    test_revolute_equations();
    return 0;
}
