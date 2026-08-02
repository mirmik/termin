#include <termin/qopt/articulation3d_motor.hpp>

#include "test_check.hpp"

#include <cmath>
#include <memory>
#include <vector>

using namespace termin;
using namespace termin::qopt;

namespace
{
    std::vector<ArticulationLink3D> links()
    {
        const SpatialInertia3 inertia{
            1.0,
            {0.1, 0.1, 0.1},
            Pose3::identity(),
        };
        return {
            {
                .parent_link = articulation_world_link,
                .parent_to_joint_zero = Pose3::identity(),
                .motion_twist_at_joint = {Vec3::unit_y(), Vec3::zero()},
                .joint_to_link = Pose3::identity(),
                .inertia = inertia,
                .diagnostic_name = "first",
            },
            {
                .parent_link = 0,
                .parent_to_joint_zero = Pose3::identity(),
                .motion_twist_at_joint = {Vec3::unit_y(), Vec3::zero()},
                .joint_to_link = Pose3::identity(),
                .inertia = inertia,
                .diagnostic_name = "second",
            },
        };
    }
} // namespace

int main()
{
    Articulation3DContribution articulation(
        links(), {{0.0, 0.0}, {0.0, 0.0}}, Vec3::zero(), "plant");
    ArticulationMotorContribution motor(
        articulation,
        {{.dof_index = 1, .effort_limit = 2.0, .diagnostic_name = "motor"}},
        "motor-bank");
    TERMIN_QOPT_CHECK(motor.diagnostic() == ArticulationMotorDiagnostic::None);
    TERMIN_QOPT_CHECK(motor.set_command(0, 5.0) == ArticulationMotorDiagnostic::None);

    DynamicsTopology topology;
    TERMIN_QOPT_CHECK(motor.register_topology(topology) == AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(articulation.register_topology(topology) ==
                      AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(topology.finalize() == AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(articulation.bind_topology(topology) == AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(motor.bind_topology(topology) == AssemblyDiagnostic::None);

    std::vector<double> mass(4, 0.0);
    std::vector<double> load(2, 0.0);
    DynamicsAssembly assembly(topology,
                              {
                                  DenseMatrixView::row_major(mass.data(), 2, 2),
                                  {load.data(), load.size(), 1},
                                  DenseMatrixView::row_major(nullptr, 0, 2),
                                  {nullptr, 0, 1},
                              });
    TERMIN_QOPT_CHECK(assembly.clear() == AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(
        articulation.assemble(assembly, DynamicsAssemblyPhase::Acceleration) ==
        AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(motor.assemble(assembly, DynamicsAssemblyPhase::Acceleration) ==
                      AssemblyDiagnostic::None);
    TERMIN_QOPT_CHECK(std::abs(load[0]) < 1.0e-12);
    TERMIN_QOPT_CHECK(std::abs(load[1] - 2.0) < 1.0e-12);
    TERMIN_QOPT_CHECK(std::abs(motor.applied_effort(0) - 2.0) < 1.0e-12);
    TERMIN_QOPT_CHECK(motor.saturated(0));

    // Dependency binding is a second pass: contribution insertion order does
    // not have to match ownership order.
    DynamicsSystem system;
    auto owned_articulation = std::make_unique<Articulation3DContribution>(
        links(), Articulation3DState{{0.0, 0.0}, {0.0, 0.0}}, Vec3::zero());
    Articulation3DContribution* articulation_ptr = owned_articulation.get();
    auto owned_motor = std::make_unique<ArticulationMotorContribution>(
        *articulation_ptr,
        std::vector<ArticulationMotorChannel>{{.dof_index = 0, .effort_limit = 1.0}});
    TERMIN_QOPT_CHECK(system.add_contribution(std::move(owned_motor)) ==
                      DynamicsSystemDiagnostic::None);
    TERMIN_QOPT_CHECK(system.add_contribution(std::move(owned_articulation)) ==
                      DynamicsSystemDiagnostic::None);
    TERMIN_QOPT_CHECK(system.finalize() == DynamicsSystemDiagnostic::None);

    return 0;
}
