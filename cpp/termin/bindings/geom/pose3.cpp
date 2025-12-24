#include "common.hpp"

namespace termin {

void bind_pose3(py::module_& m) {
    py::class_<Pose3>(m, "Pose3")
        .def(py::init<>())
        .def(py::init<const Quat&, const Vec3&>())
        // Convenience: Pose3(Vec3) - translation only
        .def(py::init([](const Vec3& lin) {
            return Pose3{Quat::identity(), lin};
        }))
        .def(py::init([](py::array_t<double> ang_arr, py::array_t<double> lin_arr) {
            return Pose3(numpy_to_quat(ang_arr), numpy_to_vec3(lin_arr));
        }))
        // Python-style constructor with keyword args
        .def(py::init([](py::object ang, py::object lin) {
            Quat q = Quat::identity();
            Vec3 t = Vec3::zero();

            if (!ang.is_none()) {
                if (py::isinstance<Quat>(ang)) {
                    q = ang.cast<Quat>();
                } else {
                    auto arr = ang.cast<py::array_t<double>>();
                    auto buf = arr.unchecked<1>();
                    q = Quat{buf(0), buf(1), buf(2), buf(3)};
                }
            }
            if (!lin.is_none()) {
                if (py::isinstance<Vec3>(lin)) {
                    t = lin.cast<Vec3>();
                } else {
                    auto arr = lin.cast<py::array_t<double>>();
                    auto buf = arr.unchecked<1>();
                    t = Vec3{buf(0), buf(1), buf(2)};
                }
            }
            return Pose3{q, t};
        }), py::arg("ang") = py::none(), py::arg("lin") = py::none())
        .def_property("ang",
            [](const Pose3& p) { return p.ang; },
            [](Pose3& p, py::object val) {
                if (py::isinstance<Quat>(val)) {
                    p.ang = val.cast<Quat>();
                } else {
                    auto arr = py::array_t<double>::ensure(val);
                    auto buf = arr.unchecked<1>();
                    p.ang = Quat{buf(0), buf(1), buf(2), buf(3)};
                }
            })
        .def_property("lin",
            [](const Pose3& p) { return p.lin; },
            [](Pose3& p, py::object val) {
                if (py::isinstance<Vec3>(val)) {
                    p.lin = val.cast<Vec3>();
                } else {
                    auto arr = py::array_t<double>::ensure(val);
                    auto buf = arr.unchecked<1>();
                    p.lin = Vec3{buf(0), buf(1), buf(2)};
                }
            })
        .def(py::self * py::self)
        .def("__matmul__", [](const Pose3& a, const Pose3& b) { return a * b; })
        .def("inverse", &Pose3::inverse)
        .def("transform_point", &Pose3::transform_point)
        .def("transform_point", [](const Pose3& p, py::object obj) {
            return p.transform_point(py_to_vec3(obj));
        })
        .def("transform_vector", &Pose3::transform_vector)
        .def("transform_vector", [](const Pose3& p, py::object obj) {
            return p.transform_vector(py_to_vec3(obj));
        })
        .def("rotate_point", &Pose3::rotate_point)
        .def("rotate_point", [](const Pose3& p, py::object obj) {
            return p.rotate_point(py_to_vec3(obj));
        })
        .def("inverse_transform_point", &Pose3::inverse_transform_point)
        .def("inverse_transform_point", [](const Pose3& p, py::object obj) {
            return p.inverse_transform_point(py_to_vec3(obj));
        })
        .def("inverse_transform_vector", &Pose3::inverse_transform_vector)
        .def("inverse_transform_vector", [](const Pose3& p, py::object obj) {
            return p.inverse_transform_vector(py_to_vec3(obj));
        })
        // rotate_vector is an alias for transform_vector (for Pose3 without scale, they are the same)
        .def("rotate_vector", &Pose3::transform_vector)
        .def("rotate_vector", [](const Pose3& p, py::object obj) {
            return p.transform_vector(py_to_vec3(obj));
        })
        .def("inverse_rotate_vector", &Pose3::inverse_transform_vector)
        .def("inverse_rotate_vector", [](const Pose3& p, py::object obj) {
            return p.inverse_transform_vector(py_to_vec3(obj));
        })
        .def("normalized", &Pose3::normalized)
        .def("with_translation", py::overload_cast<const Vec3&>(&Pose3::with_translation, py::const_))
        .def("with_rotation", &Pose3::with_rotation)
        .def("rotation_matrix", [](const Pose3& p) {
            auto result = py::array_t<double>({3, 3});
            auto buf = result.mutable_unchecked<2>();
            double m[9];
            p.rotation_matrix(m);
            for (int i = 0; i < 3; i++)
                for (int j = 0; j < 3; j++)
                    buf(i, j) = m[i * 3 + j];
            return result;
        })
        .def_static("identity", &Pose3::identity)
        .def_static("translation", py::overload_cast<double, double, double>(&Pose3::translation))
        .def_static("rotation", &Pose3::rotation)
        .def_static("rotation", [](py::array_t<double> axis_arr, double angle) {
            return Pose3::rotation(numpy_to_vec3(axis_arr), angle);
        })
        .def_static("rotate_x", &Pose3::rotate_x)
        .def_static("rotate_y", &Pose3::rotate_y)
        .def_static("rotate_z", &Pose3::rotate_z)
        // Python-style aliases (rotateX instead of rotate_x)
        .def_static("rotateX", &Pose3::rotate_x)
        .def_static("rotateY", &Pose3::rotate_y)
        .def_static("rotateZ", &Pose3::rotate_z)
        // moveX, moveY, moveZ for translation
        .def_static("moveX", [](double d) { return Pose3::translation(d, 0, 0); })
        .def_static("moveY", [](double d) { return Pose3::translation(0, d, 0); })
        .def_static("moveZ", [](double d) { return Pose3::translation(0, 0, d); })
        .def_static("looking_at", &Pose3::looking_at,
                    py::arg("eye"), py::arg("target"), py::arg("up") = Vec3::unit_z())
        .def_static("looking_at", [](py::array_t<double> eye, py::array_t<double> target, py::object up_obj) {
            Vec3 up = Vec3::unit_z();
            if (!up_obj.is_none()) {
                auto up_arr = py::array_t<double>::ensure(up_obj);
                if (up_arr) {
                    auto buf = up_arr.unchecked<1>();
                    up = Vec3{buf(0), buf(1), buf(2)};
                } else if (py::isinstance<Vec3>(up_obj)) {
                    up = up_obj.cast<Vec3>();
                }
            }
            auto eye_buf = eye.unchecked<1>();
            auto target_buf = target.unchecked<1>();
            return Pose3::looking_at(
                Vec3{eye_buf(0), eye_buf(1), eye_buf(2)},
                Vec3{target_buf(0), target_buf(1), target_buf(2)},
                up
            );
        }, py::arg("eye"), py::arg("target"), py::arg("up") = py::none())
        .def_static("from_euler", &Pose3::from_euler,
                    py::arg("roll"), py::arg("pitch"), py::arg("yaw"))
        .def("to_euler", &Pose3::to_euler)
        .def("to_axis_angle", [](const Pose3& p) {
            Vec3 axis;
            double angle;
            p.to_axis_angle(axis, angle);
            return py::make_tuple(axis, angle);
        })
        .def("distance", &Pose3::distance)
        .def("copy", &Pose3::copy)
        .def("as_matrix", [](const Pose3& p) {
            auto result = py::array_t<double>({4, 4});
            auto buf = result.mutable_unchecked<2>();
            double m[16];
            p.as_matrix(m);
            for (int i = 0; i < 4; i++)
                for (int j = 0; j < 4; j++)
                    buf(i, j) = m[j * 4 + i];  // column-major to row-major
            return result;
        })
        .def("as_matrix34", [](const Pose3& p) {
            auto result = py::array_t<double>({3, 4});
            auto buf = result.mutable_unchecked<2>();
            double rot[9];
            p.rotation_matrix(rot);
            for (int i = 0; i < 3; i++)
                for (int j = 0; j < 3; j++)
                    buf(i, j) = rot[i * 3 + j];
            buf(0, 3) = p.lin.x;
            buf(1, 3) = p.lin.y;
            buf(2, 3) = p.lin.z;
            return result;
        })
        .def("compose", [](const Pose3& a, const Pose3& b) { return a * b; })
        // x, y, z property shortcuts for translation
        .def_property("x",
            [](const Pose3& p) { return p.lin.x; },
            [](Pose3& p, double v) { p.lin.x = v; })
        .def_property("y",
            [](const Pose3& p) { return p.lin.y; },
            [](Pose3& p, double v) { p.lin.y = v; })
        .def_property("z",
            [](const Pose3& p) { return p.lin.z; },
            [](Pose3& p, double v) { p.lin.z = v; })
        // Static translation methods (aliases)
        .def_static("right", [](double d) { return Pose3::translation(d, 0, 0); })
        .def_static("forward", [](double d) { return Pose3::translation(0, d, 0); })
        .def_static("up", [](double d) { return Pose3::translation(0, 0, d); })
        // Static from_axis_angle
        .def_static("from_axis_angle", [](const Vec3& axis, double angle) {
            return Pose3::rotation(axis, angle);
        })
        .def_static("from_axis_angle", [](py::array_t<double> axis_arr, double angle) {
            return Pose3::rotation(numpy_to_vec3(axis_arr), angle);
        })
        // Static lerp
        .def_static("lerp", [](const Pose3& a, const Pose3& b, double t) {
            return lerp(a, b, t);
        })
        // to_euler with order string (only xyz supported for now, as in the original)
        .def("to_euler", [](const Pose3& p, const std::string& order) {
            if (order != "xyz") {
                throw std::runtime_error("Only 'xyz' order is supported");
            }
            Vec3 euler = p.to_euler();
            return py::make_tuple(euler.x, euler.y, euler.z);
        })
        .def("to_general_pose3", [](const Pose3& p, const Vec3& scale) {
            return GeneralPose3(p.ang, p.lin, scale);
        }, py::arg("scale") = Vec3{1.0, 1.0, 1.0})
        .def("__repr__", [](const Pose3& p) {
            return "Pose3(ang=Quat(" + std::to_string(p.ang.x) + ", " +
                   std::to_string(p.ang.y) + ", " + std::to_string(p.ang.z) + ", " +
                   std::to_string(p.ang.w) + "), lin=Vec3(" +
                   std::to_string(p.lin.x) + ", " + std::to_string(p.lin.y) + ", " +
                   std::to_string(p.lin.z) + "))";
        });

    m.def("lerp",
          static_cast<Pose3 (*)(const Pose3&, const Pose3&, double)>(&lerp),
          "Linear interpolation between poses");
}

} // namespace termin
