// Benchmark-only access to the committed floating-base articulation state.
#include <nanobind/nanobind.h>
#include <nanobind/stl/vector.h>
#include <stdexcept>
#include <termin/robotics/articulation3d.hpp>

namespace nb = nanobind;

namespace {
    nb::tuple vector(termin::Vec3 v) {
        return nb::make_tuple(v.x, v.y, v.z);
    }
} // namespace

NB_MODULE(_spider_termin_snapshot, m) {
    m.def("read", [](const termin::robotics::Articulation3D& tree) {
        const auto& base = tree.floating_base().value();
        const auto& q = base.pose_world.ang;
        nb::dict state;
        state["base_position"] = vector(base.pose_world.lin);
        state["base_wxyz"] = nb::make_tuple(q.w, q.x, q.y, q.z);
        state["base_linear_world"] = vector(q.rotate(base.velocity_local.lin));
        state["base_angular_local"] = vector(base.velocity_local.ang);
        nb::dict links;
        for (std::size_t i = 0; i < tree.unit_count(); ++i) {
            const auto& pose = tree.unit_poses_world()[i];
            const auto& twist = tree.unit_velocities_local()[i];
            nb::dict link;
            link["dof"] = 6 + i;
            link["q"] = tree.state().coordinates[i];
            link["v"] = tree.state().velocities[i];
            link["origin"] = vector(pose.lin);
            link["linear"] = vector(pose.ang.rotate(twist.lin));
            link["angular"] = vector(pose.ang.rotate(twist.ang));
            links[tree.units()[i].diagnostic_name.c_str()] = link;
        }
        state["links"] = links;
        return state;
    });
    m.def("point_jacobian",
          [](const termin::robotics::Articulation3D& tree, std::size_t unit, double x, double y, double z) {
              const auto& pose = tree.unit_poses_world().at(unit);
              const auto point = tree.point_kinematics(unit, pose.inverse_transform_point({x, y, z}));
              if (!point.ok()) {
                  throw std::runtime_error("Failed to evaluate contact point kinematics");
              }
              return point.value.linear_jacobian_world_storage;
          });
}
