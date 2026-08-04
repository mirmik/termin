#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include <array>
#include <cmath>
#include <stdexcept>

#include <termin/robotics/robotics.hpp>

namespace nb = nanobind;
using namespace termin;
using namespace termin::robotics;

namespace
{
    Vec3 tuple_vec3(nb::tuple value)
    {
        if (nb::len(value) != 3)
        {
            throw nb::value_error("expected a three-element tuple");
        }
        return {nb::cast<double>(value[0]),
                nb::cast<double>(value[1]),
                nb::cast<double>(value[2])};
    }

    nb::tuple vec3_tuple(Vec3 value)
    {
        return nb::make_tuple(value.x, value.y, value.z);
    }

    class PythonVelocityHqpController3D
    {
    public:
        explicit PythonVelocityHqpController3D(Articulation3D& articulation)
            : articulation_(&articulation), controller_(articulation)
        {
        }

        VelocityControlResult3D solve_point_velocity(
            std::size_t unit_index,
            nb::tuple point_local,
            nb::tuple target_velocity_world,
            double time_step,
            double maximum_joint_velocity)
        {
            if (!std::isfinite(maximum_joint_velocity) ||
                maximum_joint_velocity <= 0.0)
            {
                throw nb::value_error(
                    "maximum_joint_velocity must be finite and positive");
            }
            PointVelocityTask3D point_task(
                unit_index,
                tuple_vec3(point_local),
                tuple_vec3(target_velocity_world),
                {.priority = 1, .diagnostic_name = "point tracking"});
            JointVelocityLimitConstraint3D velocity_limit(
                {},
                std::vector<double>(articulation_->unit_count(),
                                    -maximum_joint_velocity),
                std::vector<double>(articulation_->unit_count(),
                                    maximum_joint_velocity),
                {.priority = 0, .diagnostic_name = "joint velocity limit"});
            const std::array<const ArticulationTask3D*, 2> tasks{
                &velocity_limit, &point_task};
            return controller_.solve(tasks, {.time_step = time_step});
        }

        void reset_primal_warm_start() noexcept
        {
            controller_.reset_primal_warm_start();
        }

    private:
        Articulation3D* articulation_ = nullptr;
        VelocityHqpController3D controller_;
    };
} // namespace

NB_MODULE(_robotics_native, m)
{
    m.doc() = "Solver-neutral Termin robotics bindings";

    nb::class_<Articulation3D>(m, "Articulation3D")
        .def_prop_ro("unit_count", &Articulation3D::unit_count)
        .def_prop_ro("dof_count", &Articulation3D::dof_count)
        .def_prop_ro(
            "coordinates",
            [](const Articulation3D& articulation)
            { return articulation.state().coordinates; })
        .def_prop_ro(
            "velocities",
            [](const Articulation3D& articulation)
            { return articulation.state().velocities; })
        .def(
            "point_position",
            [](const Articulation3D& articulation,
               std::size_t unit_index,
               nb::tuple point_local)
            {
                const ArticulationPointKinematics3DResult result =
                    articulation.point_kinematics(unit_index,
                                                  tuple_vec3(point_local));
                if (!result.ok())
                {
                    throw std::runtime_error(
                        std::string("point kinematics failed: ") +
                        std::string(articulation3d_diagnostic_name(
                            result.diagnostic)));
                }
                return vec3_tuple(result.value.position_world);
            },
            nb::arg("unit_index"),
            nb::arg("point_local"));

    nb::class_<VelocityControlResult3D>(m, "VelocityControlResult3D")
        .def_prop_ro("ok", &VelocityControlResult3D::ok)
        .def_ro("generalized_velocity",
                &VelocityControlResult3D::generalized_velocity)
        .def_prop_ro(
            "diagnostic",
            [](const VelocityControlResult3D& result)
            {
                return std::string(
                    velocity_control_diagnostic_name(result.diagnostic));
            })
        .def_ro("failed_task_name", &VelocityControlResult3D::failed_task_name);

    nb::class_<PythonVelocityHqpController3D>(m, "VelocityHqpController3D")
        .def(nb::init<Articulation3D&>(), nb::keep_alive<1, 2>())
        .def("solve_point_velocity",
             &PythonVelocityHqpController3D::solve_point_velocity,
             nb::arg("unit_index"),
             nb::arg("point_local"),
             nb::arg("target_velocity_world"),
             nb::arg("time_step"),
             nb::arg("maximum_joint_velocity") = 2.0)
        .def("reset_primal_warm_start",
             &PythonVelocityHqpController3D::reset_primal_warm_start);
}
