#include "common.hpp"

namespace termin {

void bind_general_pose3(py::module_& m) {
    py::class_<GeneralPose3>(m, "GeneralPose3")
        .def(py::init<>())
        .def(py::init<const Quat&, const Vec3&, const Vec3&>(),
             py::arg("ang"), py::arg("lin"), py::arg("scale") = Vec3{1.0, 1.0, 1.0})
        .def(py::init([](py::array_t<double> ang_arr, py::array_t<double> lin_arr, py::array_t<double> scale_arr) {
            return GeneralPose3(numpy_to_quat(ang_arr), numpy_to_vec3(lin_arr), numpy_to_vec3(scale_arr));
        }))
        // Python-style constructor with keyword args (matching Python GeneralPose3)
        .def(py::init([](py::object ang, py::object lin, py::object scale) {
            Quat q = Quat::identity();
            Vec3 t = Vec3::zero();
            Vec3 s{1.0, 1.0, 1.0};

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
            if (!scale.is_none()) {
                if (py::isinstance<Vec3>(scale)) {
                    s = scale.cast<Vec3>();
                } else {
                    auto arr = scale.cast<py::array_t<double>>();
                    auto buf = arr.unchecked<1>();
                    s = Vec3{buf(0), buf(1), buf(2)};
                }
            }
            return GeneralPose3{q, t, s};
        }), py::arg("ang") = py::none(), py::arg("lin") = py::none(), py::arg("scale") = py::none())
        .def_property("ang",
            [](const GeneralPose3& p) { return p.ang; },
            [](GeneralPose3& p, py::object val) {
                if (py::isinstance<Quat>(val)) {
                    p.ang = val.cast<Quat>();
                } else {
                    auto arr = py::array_t<double>::ensure(val);
                    auto buf = arr.unchecked<1>();
                    p.ang = Quat{buf(0), buf(1), buf(2), buf(3)};
                }
            })
        .def_property("lin",
            [](const GeneralPose3& p) { return p.lin; },
            [](GeneralPose3& p, py::object val) {
                if (py::isinstance<Vec3>(val)) {
                    p.lin = val.cast<Vec3>();
                } else {
                    auto arr = py::array_t<double>::ensure(val);
                    auto buf = arr.unchecked<1>();
                    p.lin = Vec3{buf(0), buf(1), buf(2)};
                }
            })
        .def_property("scale",
            [](const GeneralPose3& p) { return p.scale; },
            [](GeneralPose3& p, py::object val) {
                if (py::isinstance<Vec3>(val)) {
                    p.scale = val.cast<Vec3>();
                } else {
                    auto arr = py::array_t<double>::ensure(val);
                    auto buf = arr.unchecked<1>();
                    p.scale = Vec3{buf(0), buf(1), buf(2)};
                }
            })
        .def(py::self * py::self)
        .def("__matmul__", [](const GeneralPose3& a, const GeneralPose3& b) { return a * b; })
        .def("inverse", &GeneralPose3::inverse)
        .def("transform_point", &GeneralPose3::transform_point)
        .def("transform_point", [](const GeneralPose3& p, py::object obj) {
            return p.transform_point(py_to_vec3(obj));
        })
        .def("transform_vector", &GeneralPose3::transform_vector)
        .def("transform_vector", [](const GeneralPose3& p, py::object obj) {
            return p.transform_vector(py_to_vec3(obj));
        })
        .def("rotate_point", &GeneralPose3::rotate_point)
        .def("rotate_point", [](const GeneralPose3& p, py::object obj) {
            return p.rotate_point(py_to_vec3(obj));
        })
        .def("inverse_transform_point", &GeneralPose3::inverse_transform_point)
        .def("inverse_transform_point", [](const GeneralPose3& p, py::object obj) {
            return p.inverse_transform_point(py_to_vec3(obj));
        })
        .def("inverse_transform_vector", &GeneralPose3::inverse_transform_vector)
        .def("inverse_transform_vector", [](const GeneralPose3& p, py::object obj) {
            return p.inverse_transform_vector(py_to_vec3(obj));
        })
        .def("normalized", &GeneralPose3::normalized)
        .def("with_translation", &GeneralPose3::with_translation)
        .def("with_rotation", &GeneralPose3::with_rotation)
        .def("with_scale", &GeneralPose3::with_scale)
        .def("to_pose3", &GeneralPose3::to_pose3)
        .def("rotation_matrix", [](const GeneralPose3& p) {
            auto result = make_mat(3, 3);
            auto buf = result.mutable_unchecked<2>();
            double m_arr[9];
            p.rotation_matrix(m_arr);
            for (int i = 0; i < 3; i++)
                for (int j = 0; j < 3; j++)
                    buf(i, j) = m_arr[i * 3 + j];
            return result;
        })
        .def("as_matrix", [](const GeneralPose3& p) {
            auto result = make_mat(4, 4);
            auto buf = result.mutable_unchecked<2>();
            double m_arr[16];
            p.matrix4(m_arr);
            for (int i = 0; i < 4; i++)
                for (int j = 0; j < 4; j++)
                    buf(i, j) = m_arr[i * 4 + j];
            return result;
        })
        .def("as_matrix34", [](const GeneralPose3& p) {
            auto result = make_mat(3, 4);
            auto buf = result.mutable_unchecked<2>();
            double m_arr[12];
            p.matrix34(m_arr);
            for (int i = 0; i < 3; i++)
                for (int j = 0; j < 4; j++)
                    buf(i, j) = m_arr[i * 4 + j];
            return result;
        })
        .def("inverse_matrix", [](const GeneralPose3& p) {
            auto result = make_mat(4, 4);
            auto buf = result.mutable_unchecked<2>();
            double m_arr[16];
            p.inverse_matrix4(m_arr);
            for (int i = 0; i < 4; i++)
                for (int j = 0; j < 4; j++)
                    buf(i, j) = m_arr[i * 4 + j];
            return result;
        })
        .def_static("identity", &GeneralPose3::identity)
        .def_static("translation", py::overload_cast<double, double, double>(&GeneralPose3::translation))
        .def_static("translation", py::overload_cast<const Vec3&>(&GeneralPose3::translation))
        .def_static("rotation", &GeneralPose3::rotation)
        .def_static("scaling", py::overload_cast<double>(&GeneralPose3::scaling))
        .def_static("scaling", py::overload_cast<double, double, double>(&GeneralPose3::scaling))
        .def_static("rotate_x", &GeneralPose3::rotate_x)
        .def_static("rotate_y", &GeneralPose3::rotate_y)
        .def_static("rotate_z", &GeneralPose3::rotate_z)
        // Python-style aliases (rotateX instead of rotate_x)
        .def_static("rotateX", &GeneralPose3::rotate_x)
        .def_static("rotateY", &GeneralPose3::rotate_y)
        .def_static("rotateZ", &GeneralPose3::rotate_z)
        .def("copy", [](const GeneralPose3& p) { return p; })
        .def_static("move", &GeneralPose3::move)
        .def_static("move_x", &GeneralPose3::move_x)
        .def_static("move_y", &GeneralPose3::move_y)
        .def_static("move_z", &GeneralPose3::move_z)
        .def_static("right", &GeneralPose3::right)
        .def_static("forward", &GeneralPose3::forward)
        .def_static("up", &GeneralPose3::up)
        .def_static("looking_at", &GeneralPose3::looking_at,
                    py::arg("eye"), py::arg("target"), py::arg("up_vec") = Vec3{0.0, 0.0, 1.0})
        .def_static("looking_at", [](py::array_t<double> eye, py::array_t<double> target, py::object up_obj) {
            Vec3 up{0.0, 0.0, 1.0};
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
            return GeneralPose3::looking_at(
                Vec3{eye_buf(0), eye_buf(1), eye_buf(2)},
                Vec3{target_buf(0), target_buf(1), target_buf(2)},
                up
            );
        }, py::arg("eye"), py::arg("target"), py::arg("up_vec") = py::none())
        .def_static("lerp",
                    static_cast<GeneralPose3 (*)(const GeneralPose3&, const GeneralPose3&, double)>(&lerp),
                    "Linear interpolation between GeneralPose3 (with scale)")
        .def_static("from_matrix", [](py::array_t<double> mat) {
            auto buf = mat.unchecked<2>();
            // Extract translation from 4th column
            Vec3 lin{buf(0, 3), buf(1, 3), buf(2, 3)};

            // Extract column vectors of upper-left 3x3 for scale
            Vec3 col0{buf(0, 0), buf(1, 0), buf(2, 0)};
            Vec3 col1{buf(0, 1), buf(1, 1), buf(2, 1)};
            Vec3 col2{buf(0, 2), buf(1, 2), buf(2, 2)};

            // Scale is the length of each column
            Vec3 scale{col0.norm(), col1.norm(), col2.norm()};

            // Build rotation matrix by dividing out scale
            double rot[9];
            if (scale.x > 1e-10) {
                rot[0] = col0.x / scale.x; rot[3] = col0.y / scale.x; rot[6] = col0.z / scale.x;
            } else {
                rot[0] = 1; rot[3] = 0; rot[6] = 0;
            }
            if (scale.y > 1e-10) {
                rot[1] = col1.x / scale.y; rot[4] = col1.y / scale.y; rot[7] = col1.z / scale.y;
            } else {
                rot[1] = 0; rot[4] = 1; rot[7] = 0;
            }
            if (scale.z > 1e-10) {
                rot[2] = col2.x / scale.z; rot[5] = col2.y / scale.z; rot[8] = col2.z / scale.z;
            } else {
                rot[2] = 0; rot[5] = 0; rot[8] = 1;
            }

            // Convert rotation matrix to quaternion
            Quat q = Quat::from_rotation_matrix(rot);

            return GeneralPose3(q, lin, scale);
        })
        .def("__repr__", [](const GeneralPose3& p) {
            return "GeneralPose3(ang=Quat(" + std::to_string(p.ang.x) + ", " +
                   std::to_string(p.ang.y) + ", " + std::to_string(p.ang.z) + ", " +
                   std::to_string(p.ang.w) + "), lin=Vec3(" +
                   std::to_string(p.lin.x) + ", " + std::to_string(p.lin.y) + ", " +
                   std::to_string(p.lin.z) + "), scale=Vec3(" +
                   std::to_string(p.scale.x) + ", " + std::to_string(p.scale.y) + ", " +
                   std::to_string(p.scale.z) + "))";
        });

    m.def("lerp_general_pose3",
          static_cast<GeneralPose3 (*)(const GeneralPose3&, const GeneralPose3&, double)>(&lerp),
          "Linear interpolation between GeneralPose3 (with scale)");
}

} // namespace termin
