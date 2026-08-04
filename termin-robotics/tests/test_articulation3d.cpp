#include <termin/robotics/articulation3d.hpp>

#include "test_check.hpp"

#include <cmath>
#include <vector>

using namespace termin;
using namespace termin::robotics;

namespace
{
    SpatialInertia3 link_inertia()
    {
        return {1.0, {0.2, 0.3, 0.4}, Pose3::identity()};
    }

    std::vector<ArticulationLink3D> links()
    {
        return {
            {
                .parent_link = articulation_root_frame,
                .parent_to_joint_zero = Pose3::identity(),
                .motion_twist_at_joint = {Vec3::unit_z(), Vec3::zero()},
                .joint_to_link = Pose3::translation(1.0, 0.0, 0.0),
                .inertia = link_inertia(),
                .diagnostic_name = "root",
            },
            {
                .parent_link = 0,
                .parent_to_joint_zero = Pose3::translation(0.5, 0.0, 0.0),
                .motion_twist_at_joint = {Vec3::unit_y(), Vec3::zero()},
                .joint_to_link = Pose3::translation(0.5, 0.0, 0.0),
                .inertia = link_inertia(),
                .diagnostic_name = "child",
            },
        };
    }

    void test_validation()
    {
        Articulation3D empty({}, {}, "empty");
        TERMIN_QOPT_CHECK(empty.diagnostic() ==
                          Articulation3DDiagnostic::EmptyModel);

        auto invalid_links = links();
        invalid_links[0].parent_link = 0;
        Articulation3D invalid(std::move(invalid_links),
                               {{0.0, 0.0}, {0.0, 0.0}});
        TERMIN_QOPT_CHECK(invalid.diagnostic() ==
                          Articulation3DDiagnostic::InvalidParent);
    }

    void test_kinematics_and_inertial_model()
    {
        const Articulation3DState state{{0.3, -0.4}, {0.7, -0.2}};
        Articulation3D model(links(), state, "two-link");
        TERMIN_QOPT_CHECK(model.diagnostic() == Articulation3DDiagnostic::None);
        TERMIN_QOPT_CHECK(model.link_poses_world().size() == 2);

        const auto point = model.point_kinematics(1, {0.2, -0.1, 0.3});
        TERMIN_QOPT_CHECK(point.ok());
        const auto jacobian = point.value.linear_jacobian_world();
        TERMIN_QOPT_CHECK(jacobian.rows == 3);
        TERMIN_QOPT_CHECK(jacobian.columns == 2);

        Vec3 jacobian_velocity = Vec3::zero();
        for (std::size_t column = 0; column < state.velocities.size(); ++column)
        {
            jacobian_velocity.x +=
                jacobian(0, column) * state.velocities[column];
            jacobian_velocity.y +=
                jacobian(1, column) * state.velocities[column];
            jacobian_velocity.z +=
                jacobian(2, column) * state.velocities[column];
        }
        TERMIN_QOPT_CHECK(
            (jacobian_velocity - point.value.velocity_world).norm() < 1e-12);

        std::vector<double> mass;
        TERMIN_QOPT_CHECK(model.mass_matrix(mass));
        TERMIN_QOPT_CHECK(mass.size() == 4);
        TERMIN_QOPT_CHECK(std::abs(mass[1] - mass[2]) < 1e-12);
        TERMIN_QOPT_CHECK(std::isfinite(model.total_energy({0.0, 0.0, -9.81})));
    }
}

int main()
{
    test_validation();
    test_kinematics_and_inertial_model();
    return 0;
}
