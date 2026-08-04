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
    TaskSettings3D task_settings(int priority,
                                 std::vector<double> diagonal_weight,
                                 std::string diagnostic_name)
    {
        return {
            .priority = priority,
            .diagonal_weight = std::move(diagonal_weight),
            .diagnostic_name = std::move(diagnostic_name),
        };
    }

    std::vector<const ArticulationTask3D*> task_pointers(nb::list tasks)
    {
        std::vector<const ArticulationTask3D*> result;
        result.reserve(nb::len(tasks));
        for (std::size_t index = 0; index < nb::len(tasks); ++index)
        {
            result.push_back(nb::cast<const ArticulationTask3D*>(tasks[index]));
        }
        return result;
    }

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

        VelocityControlResult3D solve(nb::list tasks, double time_step)
        {
            const std::vector<const ArticulationTask3D*> pointers =
                task_pointers(std::move(tasks));
            return controller_.solve(pointers, {.time_step = time_step});
        }

        VelocityControlResult3D
        solve_point_velocity(std::size_t unit_index,
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

    std::vector<InverseDynamicsActuator3D>
    make_actuators(const std::vector<std::size_t>& dof_indices,
                   const std::vector<double>& effort_limits)
    {
        if (dof_indices.size() != effort_limits.size())
        {
            throw nb::value_error(
                "dof_indices and effort_limits must have equal length");
        }
        std::vector<InverseDynamicsActuator3D> result;
        result.reserve(dof_indices.size());
        for (std::size_t index = 0; index < dof_indices.size(); ++index)
        {
            const double limit = effort_limits[index];
            if (!std::isfinite(limit) || limit < 0.0)
            {
                throw nb::value_error(
                    "effort limits must be finite and non-negative");
            }
            result.push_back({
                .dof_index = dof_indices[index],
                .minimum_effort = -limit,
                .maximum_effort = limit,
            });
        }
        return result;
    }

    class PythonInverseDynamicsHqpController3D
    {
    public:
        PythonInverseDynamicsHqpController3D(
            Articulation3D& articulation,
            const std::vector<std::size_t>& dof_indices,
            const std::vector<double>& effort_limits,
            nb::tuple gravity_world)
            : articulation_(&articulation),
              controller_(articulation,
                          make_actuators(dof_indices, effort_limits),
                          tuple_vec3(gravity_world))
        {
        }

        InverseDynamicsControlResult3D solve(nb::list tasks, double time_step)
        {
            const std::vector<const ArticulationTask3D*> pointers =
                task_pointers(std::move(tasks));
            return controller_.solve(pointers, {.time_step = time_step});
        }

        InverseDynamicsControlResult3D
        solve_point_acceleration(std::size_t unit_index,
                                 nb::tuple point_local,
                                 nb::tuple target_position_world,
                                 nb::tuple target_velocity_world,
                                 nb::tuple feedforward_acceleration_world,
                                 double position_gain,
                                 double velocity_gain,
                                 double time_step,
                                 double maximum_joint_velocity)
        {
            if (!std::isfinite(maximum_joint_velocity) ||
                maximum_joint_velocity <= 0.0)
            {
                throw nb::value_error(
                    "maximum_joint_velocity must be finite and positive");
            }
            PointAccelerationTask3D point_task(
                unit_index,
                tuple_vec3(point_local),
                tuple_vec3(target_position_world),
                tuple_vec3(target_velocity_world),
                tuple_vec3(feedforward_acceleration_world),
                position_gain,
                velocity_gain,
                {.priority = 1, .diagnostic_name = "point tracking"});
            JointLimitConstraint3D position_limit(
                {.priority = 0, .diagnostic_name = "joint position limit"});
            JointVelocityLimitConstraint3D velocity_limit(
                {},
                std::vector<double>(articulation_->unit_count(),
                                    -maximum_joint_velocity),
                std::vector<double>(articulation_->unit_count(),
                                    maximum_joint_velocity),
                {.priority = 0, .diagnostic_name = "joint velocity limit"});
            const std::array<const ArticulationTask3D*, 3> tasks{
                &position_limit, &velocity_limit, &point_task};
            return controller_.solve(tasks, {.time_step = time_step});
        }

        void reset_primal_warm_start() noexcept
        {
            controller_.reset_primal_warm_start();
        }

    private:
        Articulation3D* articulation_ = nullptr;
        InverseDynamicsHqpController3D controller_;
    };
} // namespace

NB_MODULE(_robotics_native, m)
{
    m.doc() = "Solver-neutral Termin robotics bindings";

    nb::class_<Articulation3D>(m, "Articulation3D")
        .def_prop_ro("unit_count", &Articulation3D::unit_count)
        .def_prop_ro("dof_count", &Articulation3D::dof_count)
        .def_prop_ro("coordinates",
                     [](const Articulation3D& articulation)
                     { return articulation.state().coordinates; })
        .def_prop_ro("velocities",
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
                        std::string(
                            articulation3d_diagnostic_name(result.diagnostic)));
                }
                return vec3_tuple(result.value.position_world);
            },
            nb::arg("unit_index"),
            nb::arg("point_local"));

    nb::class_<ArticulationTask3D>(m, "ArticulationTask3D");

    nb::class_<PointVelocityTask3D, ArticulationTask3D>(m,
                                                        "PointVelocityTask3D")
        .def(
            "__init__",
            [](PointVelocityTask3D* self,
               std::size_t unit_index,
               nb::tuple point_local,
               nb::tuple target_velocity_world,
               int priority,
               std::vector<double> diagonal_weight,
               std::string diagnostic_name)
            {
                new (self) PointVelocityTask3D(
                    unit_index,
                    tuple_vec3(point_local),
                    tuple_vec3(target_velocity_world),
                    task_settings(priority,
                                  std::move(diagonal_weight),
                                  std::move(diagnostic_name)));
            },
            nb::arg("unit_index"),
            nb::arg("point_local"),
            nb::arg("target_velocity_world"),
            nb::kw_only(),
            nb::arg("priority") = 0,
            nb::arg("diagonal_weight") = std::vector<double>{},
            nb::arg("diagnostic_name") = "point velocity");

    nb::class_<PointAccelerationTask3D, ArticulationTask3D>(
        m, "PointAccelerationTask3D")
        .def(
            "__init__",
            [](PointAccelerationTask3D* self,
               std::size_t unit_index,
               nb::tuple point_local,
               nb::tuple target_position_world,
               nb::tuple target_velocity_world,
               nb::tuple feedforward_acceleration_world,
               double position_gain,
               double velocity_gain,
               int priority,
               std::vector<double> diagonal_weight,
               std::string diagnostic_name)
            {
                new (self) PointAccelerationTask3D(
                    unit_index,
                    tuple_vec3(point_local),
                    tuple_vec3(target_position_world),
                    tuple_vec3(target_velocity_world),
                    tuple_vec3(feedforward_acceleration_world),
                    position_gain,
                    velocity_gain,
                    task_settings(priority,
                                  std::move(diagonal_weight),
                                  std::move(diagnostic_name)));
            },
            nb::arg("unit_index"),
            nb::arg("point_local"),
            nb::arg("target_position_world"),
            nb::arg("target_velocity_world") = nb::make_tuple(0.0, 0.0, 0.0),
            nb::arg("feedforward_acceleration_world") =
                nb::make_tuple(0.0, 0.0, 0.0),
            nb::arg("position_gain") = 25.0,
            nb::arg("velocity_gain") = 10.0,
            nb::kw_only(),
            nb::arg("priority") = 0,
            nb::arg("diagonal_weight") = std::vector<double>{},
            nb::arg("diagnostic_name") = "point acceleration");

    nb::class_<JointLimitConstraint3D, ArticulationTask3D>(
        m, "JointLimitConstraint3D")
        .def(
            "__init__",
            [](JointLimitConstraint3D* self,
               int priority,
               std::string diagnostic_name)
            {
                new (self) JointLimitConstraint3D(
                    task_settings(priority, {}, std::move(diagnostic_name)));
            },
            nb::kw_only(),
            nb::arg("priority") = 0,
            nb::arg("diagnostic_name") = "joint position limit");

    nb::class_<JointVelocityLimitConstraint3D, ArticulationTask3D>(
        m, "JointVelocityLimitConstraint3D")
        .def(
            "__init__",
            [](JointVelocityLimitConstraint3D* self,
               std::vector<std::size_t> joint_indices,
               std::vector<double> minimum_velocities,
               std::vector<double> maximum_velocities,
               int priority,
               std::string diagnostic_name)
            {
                new (self) JointVelocityLimitConstraint3D(
                    std::move(joint_indices),
                    std::move(minimum_velocities),
                    std::move(maximum_velocities),
                    task_settings(priority, {}, std::move(diagnostic_name)));
            },
            nb::arg("joint_indices"),
            nb::arg("minimum_velocities"),
            nb::arg("maximum_velocities"),
            nb::kw_only(),
            nb::arg("priority") = 0,
            nb::arg("diagnostic_name") = "joint velocity limit");

    nb::class_<VelocityControlResult3D>(m, "VelocityControlResult3D")
        .def_prop_ro("ok", &VelocityControlResult3D::ok)
        .def_ro("generalized_velocity",
                &VelocityControlResult3D::generalized_velocity)
        .def_ro("level_priorities", &VelocityControlResult3D::level_priorities)
        .def_ro("level_task_residual_l2",
                &VelocityControlResult3D::level_task_residual_l2)
        .def_prop_ro("diagnostic",
                     [](const VelocityControlResult3D& result) {
                         return std::string(velocity_control_diagnostic_name(
                             result.diagnostic));
                     })
        .def_ro("failed_task_name", &VelocityControlResult3D::failed_task_name);

    nb::class_<PythonVelocityHqpController3D>(m, "VelocityHqpController3D")
        .def(nb::init<Articulation3D&>(), nb::keep_alive<1, 2>())
        .def("solve",
             &PythonVelocityHqpController3D::solve,
             nb::arg("tasks"),
             nb::arg("time_step"))
        .def("solve_point_velocity",
             &PythonVelocityHqpController3D::solve_point_velocity,
             nb::arg("unit_index"),
             nb::arg("point_local"),
             nb::arg("target_velocity_world"),
             nb::arg("time_step"),
             nb::arg("maximum_joint_velocity") = 2.0)
        .def("reset_primal_warm_start",
             &PythonVelocityHqpController3D::reset_primal_warm_start);

    nb::class_<InverseDynamicsControlResult3D>(m,
                                               "InverseDynamicsControlResult3D")
        .def_prop_ro("ok", &InverseDynamicsControlResult3D::ok)
        .def_ro("generalized_acceleration",
                &InverseDynamicsControlResult3D::generalized_acceleration)
        .def_ro("required_generalized_effort",
                &InverseDynamicsControlResult3D::required_generalized_effort)
        .def_ro("actuator_dof_indices",
                &InverseDynamicsControlResult3D::actuator_dofs)
        .def_ro("actuator_effort",
                &InverseDynamicsControlResult3D::actuator_effort)
        .def_ro("level_priorities",
                &InverseDynamicsControlResult3D::level_priorities)
        .def_ro("level_task_residual_l2",
                &InverseDynamicsControlResult3D::level_task_residual_l2)
        .def_prop_ro("diagnostic",
                     [](const InverseDynamicsControlResult3D& result)
                     {
                         return std::string(
                             inverse_dynamics_control_diagnostic_name(
                                 result.diagnostic));
                     })
        .def_ro("failed_task_name",
                &InverseDynamicsControlResult3D::failed_task_name);

    nb::class_<PythonInverseDynamicsHqpController3D>(
        m, "InverseDynamicsHqpController3D")
        .def(nb::init<Articulation3D&,
                      const std::vector<std::size_t>&,
                      const std::vector<double>&,
                      nb::tuple>(),
             nb::arg("articulation"),
             nb::arg("dof_indices"),
             nb::arg("effort_limits"),
             nb::arg("gravity_world") = nb::make_tuple(0.0, 0.0, 0.0),
             nb::keep_alive<1, 2>())
        .def("solve",
             &PythonInverseDynamicsHqpController3D::solve,
             nb::arg("tasks"),
             nb::arg("time_step"))
        .def("solve_point_acceleration",
             &PythonInverseDynamicsHqpController3D::solve_point_acceleration,
             nb::arg("unit_index"),
             nb::arg("point_local"),
             nb::arg("target_position_world"),
             nb::arg("target_velocity_world") = nb::make_tuple(0.0, 0.0, 0.0),
             nb::arg("feedforward_acceleration_world") =
                 nb::make_tuple(0.0, 0.0, 0.0),
             nb::arg("position_gain") = 25.0,
             nb::arg("velocity_gain") = 10.0,
             nb::arg("time_step"),
             nb::arg("maximum_joint_velocity") = 4.0)
        .def("reset_primal_warm_start",
             &PythonInverseDynamicsHqpController3D::reset_primal_warm_start);
}
