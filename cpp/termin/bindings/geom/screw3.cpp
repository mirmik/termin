#include "common.hpp"

namespace termin {

void bind_screw3(py::module_& m) {
    py::class_<Screw3>(m, "Screw3")
        .def(py::init<>())
        .def(py::init<const Vec3&, const Vec3&>(), py::arg("ang"), py::arg("lin"))
        .def(py::init([](py::array_t<double> ang_arr, py::array_t<double> lin_arr) {
            return Screw3(numpy_to_vec3(ang_arr), numpy_to_vec3(lin_arr));
        }), py::arg("ang"), py::arg("lin"))
        .def_readwrite("ang", &Screw3::ang)
        .def_readwrite("lin", &Screw3::lin)
        .def(py::self + py::self)
        .def(py::self - py::self)
        .def(py::self * double())
        .def(double() * py::self)
        .def(-py::self)
        .def("dot", &Screw3::dot)
        .def("cross_motion", &Screw3::cross_motion)
        .def("cross_force", &Screw3::cross_force)
        .def("transform_by", &Screw3::transform_by)
        .def("inverse_transform_by", &Screw3::inverse_transform_by)
        .def("to_pose", &Screw3::to_pose)
        .def("as_pose3", &Screw3::to_pose)  // alias for compatibility
        .def("scaled", &Screw3::scaled)
        // Adjoint overloads
        .def("adjoint", py::overload_cast<const Pose3&>(&Screw3::adjoint, py::const_))
        .def("adjoint", py::overload_cast<const Vec3&>(&Screw3::adjoint, py::const_))
        .def("adjoint", [](const Screw3& s, py::array_t<double> arm_arr) {
            return s.adjoint(numpy_to_vec3(arm_arr));
        })
        .def("adjoint_inv", py::overload_cast<const Pose3&>(&Screw3::adjoint_inv, py::const_))
        .def("adjoint_inv", py::overload_cast<const Vec3&>(&Screw3::adjoint_inv, py::const_))
        .def("adjoint_inv", [](const Screw3& s, py::array_t<double> arm_arr) {
            return s.adjoint_inv(numpy_to_vec3(arm_arr));
        })
        .def("coadjoint", py::overload_cast<const Pose3&>(&Screw3::coadjoint, py::const_))
        .def("coadjoint", py::overload_cast<const Vec3&>(&Screw3::coadjoint, py::const_))
        .def("coadjoint", [](const Screw3& s, py::array_t<double> arm_arr) {
            return s.coadjoint(numpy_to_vec3(arm_arr));
        })
        .def("coadjoint_inv", py::overload_cast<const Pose3&>(&Screw3::coadjoint_inv, py::const_))
        .def("coadjoint_inv", py::overload_cast<const Vec3&>(&Screw3::coadjoint_inv, py::const_))
        .def("coadjoint_inv", [](const Screw3& s, py::array_t<double> arm_arr) {
            return s.coadjoint_inv(numpy_to_vec3(arm_arr));
        })
        // Aliases for compatibility
        .def("kinematic_carry", py::overload_cast<const Vec3&>(&Screw3::adjoint, py::const_))
        .def("kinematic_carry", [](const Screw3& s, py::array_t<double> arm_arr) {
            return s.adjoint(numpy_to_vec3(arm_arr));
        })
        .def("twist_carry", py::overload_cast<const Vec3&>(&Screw3::adjoint, py::const_))
        .def("force_carry", py::overload_cast<const Vec3&>(&Screw3::coadjoint, py::const_))
        .def("force_carry", [](const Screw3& s, py::array_t<double> arm_arr) {
            return s.coadjoint(numpy_to_vec3(arm_arr));
        })
        .def("wrench_carry", py::overload_cast<const Vec3&>(&Screw3::coadjoint, py::const_))
        .def_static("zero", &Screw3::zero)
        .def("__repr__", [](const Screw3& s) {
            return "Screw3(ang=Vec3(" + std::to_string(s.ang.x) + ", " +
                   std::to_string(s.ang.y) + ", " + std::to_string(s.ang.z) +
                   "), lin=Vec3(" + std::to_string(s.lin.x) + ", " +
                   std::to_string(s.lin.y) + ", " + std::to_string(s.lin.z) + "))";
        });
}

} // namespace termin
