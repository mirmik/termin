#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/operators.h>
#include <pybind11/stl.h>

#include "termin/geom/geom.hpp"

namespace py = pybind11;
using namespace termin;
using namespace termin::geom;

// Helper to create numpy array from Vec3
static py::array_t<double> vec3_to_numpy(const Vec3& v) {
    auto result = py::array_t<double>(3);
    auto buf = result.mutable_unchecked<1>();
    buf(0) = v.x;
    buf(1) = v.y;
    buf(2) = v.z;
    return result;
}

// Helper to create Vec3 from numpy array
static Vec3 numpy_to_vec3(py::array_t<double> arr) {
    auto buf = arr.unchecked<1>();
    return {buf(0), buf(1), buf(2)};
}

// Helper to create numpy array from Quat
static py::array_t<double> quat_to_numpy(const Quat& q) {
    auto result = py::array_t<double>(4);
    auto buf = result.mutable_unchecked<1>();
    buf(0) = q.x;
    buf(1) = q.y;
    buf(2) = q.z;
    buf(3) = q.w;
    return result;
}

// Helper to create Quat from numpy array
static Quat numpy_to_quat(py::array_t<double> arr) {
    auto buf = arr.unchecked<1>();
    return {buf(0), buf(1), buf(2), buf(3)};
}

static py::array_t<double> make_mat(int rows, int cols) {
    return py::array_t<double>({rows, cols});
}

// Helper to convert any array-like Python object to Vec3
static Vec3 py_to_vec3(py::object obj) {
    if (py::isinstance<Vec3>(obj)) {
        return obj.cast<Vec3>();
    }
    // Try numpy array or sequence
    auto arr = py::array_t<double>::ensure(obj);
    if (arr) {
        auto buf = arr.unchecked<1>();
        return Vec3{buf(0), buf(1), buf(2)};
    }
    // Try sequence protocol
    auto seq = obj.cast<py::sequence>();
    return Vec3{seq[0].cast<double>(), seq[1].cast<double>(), seq[2].cast<double>()};
}

PYBIND11_MODULE(_geom_native, m) {
    m.doc() = "Native C++ geometry module for termin";

    // Vec3
    py::class_<Vec3>(m, "Vec3")
        .def(py::init<>())
        .def(py::init<double, double, double>())
        .def(py::init([](py::array_t<double> arr) {
            return numpy_to_vec3(arr);
        }))
        .def_readwrite("x", &Vec3::x)
        .def_readwrite("y", &Vec3::y)
        .def_readwrite("z", &Vec3::z)
        .def("__getitem__", [](const Vec3& v, int i) { return v[i]; })
        .def("__setitem__", [](Vec3& v, int i, double val) { v[i] = val; })
        .def("__setitem__", [](Vec3& v, py::ellipsis, py::object val) {
            // Support vec[...] = (x, y, z) or vec[...] = other_vec
            if (py::isinstance<Vec3>(val)) {
                Vec3 other = val.cast<Vec3>();
                v.x = other.x;
                v.y = other.y;
                v.z = other.z;
            } else {
                auto seq = val.cast<py::sequence>();
                v.x = seq[0].cast<double>();
                v.y = seq[1].cast<double>();
                v.z = seq[2].cast<double>();
            }
        })
        .def("__len__", [](const Vec3&) { return 3; })
        .def("__iter__", [](const Vec3& v) {
            return py::make_iterator(&v.x, &v.x + 3);
        }, py::keep_alive<0, 1>())
        .def(py::self + py::self)
        .def(py::self - py::self)
        .def(py::self * double())
        .def(double() * py::self)
        .def(py::self / double())
        .def(-py::self)
        .def("dot", &Vec3::dot)
        .def("cross", &Vec3::cross)
        .def("norm", &Vec3::norm)
        .def("norm_squared", &Vec3::norm_squared)
        .def("normalized", &Vec3::normalized)
        .def_static("zero", &Vec3::zero)
        .def_static("unit_x", &Vec3::unit_x)
        .def_static("unit_y", &Vec3::unit_y)
        .def_static("unit_z", &Vec3::unit_z)
        .def("to_numpy", &vec3_to_numpy)
        .def("copy", [](const Vec3& v) { return v; })
        .def("__eq__", [](const Vec3& a, const Vec3& b) {
            return a.x == b.x && a.y == b.y && a.z == b.z;
        })
        .def("__ne__", [](const Vec3& a, const Vec3& b) {
            return a.x != b.x || a.y != b.y || a.z != b.z;
        })
        .def("approx_eq", [](const Vec3& a, const Vec3& b, double eps) {
            return std::abs(a.x - b.x) < eps &&
                   std::abs(a.y - b.y) < eps &&
                   std::abs(a.z - b.z) < eps;
        }, py::arg("other"), py::arg("eps") = 1e-9)
        .def("__repr__", [](const Vec3& v) {
            return "Vec3(" + std::to_string(v.x) + ", " +
                   std::to_string(v.y) + ", " + std::to_string(v.z) + ")";
        });

    // Quat
    py::class_<Quat>(m, "Quat")
        .def(py::init<>())
        .def(py::init<double, double, double, double>())
        .def(py::init([](py::array_t<double> arr) {
            return numpy_to_quat(arr);
        }))
        .def_readwrite("x", &Quat::x)
        .def_readwrite("y", &Quat::y)
        .def_readwrite("z", &Quat::z)
        .def_readwrite("w", &Quat::w)
        .def("__getitem__", [](const Quat& q, int i) {
            if (i == 0) return q.x;
            if (i == 1) return q.y;
            if (i == 2) return q.z;
            if (i == 3) return q.w;
            throw py::index_error("Quat index out of range");
        })
        .def("__setitem__", [](Quat& q, int i, double val) {
            if (i == 0) q.x = val;
            else if (i == 1) q.y = val;
            else if (i == 2) q.z = val;
            else if (i == 3) q.w = val;
            else throw py::index_error("Quat index out of range");
        })
        .def("__setitem__", [](Quat& q, py::ellipsis, py::object val) {
            // Support quat[...] = (x, y, z, w) or quat[...] = other_quat
            if (py::isinstance<Quat>(val)) {
                Quat other = val.cast<Quat>();
                q.x = other.x;
                q.y = other.y;
                q.z = other.z;
                q.w = other.w;
            } else {
                auto seq = val.cast<py::sequence>();
                q.x = seq[0].cast<double>();
                q.y = seq[1].cast<double>();
                q.z = seq[2].cast<double>();
                q.w = seq[3].cast<double>();
            }
        })
        .def("__len__", [](const Quat&) { return 4; })
        .def("__iter__", [](const Quat& q) {
            return py::make_iterator(&q.x, &q.x + 4);
        }, py::keep_alive<0, 1>())
        .def(py::self * py::self)
        .def("conjugate", &Quat::conjugate)
        .def("inverse", &Quat::inverse)
        .def("norm", &Quat::norm)
        .def("normalized", &Quat::normalized)
        .def("rotate", &Quat::rotate)
        .def("inverse_rotate", &Quat::inverse_rotate)
        .def_static("identity", &Quat::identity)
        .def_static("from_axis_angle", &Quat::from_axis_angle)
        .def("to_numpy", &quat_to_numpy)
        .def("copy", [](const Quat& q) { return q; })
        .def("__repr__", [](const Quat& q) {
            return "Quat(" + std::to_string(q.x) + ", " +
                   std::to_string(q.y) + ", " + std::to_string(q.z) + ", " +
                   std::to_string(q.w) + ")";
        });

    m.def("slerp", &slerp, "Spherical linear interpolation between quaternions");

    // Pose3
    py::class_<Pose3>(m, "Pose3")
        .def(py::init<>())
        .def(py::init<const Quat&, const Vec3&>())
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
        .def_readwrite("ang", &Pose3::ang)
        .def_readwrite("lin", &Pose3::lin)
        .def(py::self * py::self)
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
        .def_static("rotate_x", &Pose3::rotate_x)
        .def_static("rotate_y", &Pose3::rotate_y)
        .def_static("rotate_z", &Pose3::rotate_z)
        // Python-style aliases (rotateX instead of rotate_x)
        .def_static("rotateX", &Pose3::rotate_x)
        .def_static("rotateY", &Pose3::rotate_y)
        .def_static("rotateZ", &Pose3::rotate_z)
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

    m.def("lerp", py::overload_cast<const Pose3&, const Pose3&, double>(&lerp),
          "Linear interpolation between poses");

    // GeneralPose3
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
        .def_readwrite("ang", &GeneralPose3::ang)
        .def_readwrite("lin", &GeneralPose3::lin)
        .def_readwrite("scale", &GeneralPose3::scale)
        .def(py::self * py::self)
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
        .def_static("lerp", py::overload_cast<const GeneralPose3&, const GeneralPose3&, double>(&lerp),
                    "Linear interpolation between GeneralPose3 (with scale)")
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
          py::overload_cast<const GeneralPose3&, const GeneralPose3&, double>(&lerp),
          "Linear interpolation between GeneralPose3 (with scale)");

    // Screw3
    py::class_<Screw3>(m, "Screw3")
        .def(py::init<>())
        .def(py::init<const Vec3&, const Vec3&>())
        .def(py::init([](py::array_t<double> ang_arr, py::array_t<double> lin_arr) {
            return Screw3(numpy_to_vec3(ang_arr), numpy_to_vec3(lin_arr));
        }))
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
        .def("scaled", &Screw3::scaled)
        .def_static("zero", &Screw3::zero)
        .def("__repr__", [](const Screw3& s) {
            return "Screw3(ang=Vec3(" + std::to_string(s.ang.x) + ", " +
                   std::to_string(s.ang.y) + ", " + std::to_string(s.ang.z) +
                   "), lin=Vec3(" + std::to_string(s.lin.x) + ", " +
                   std::to_string(s.lin.y) + ", " + std::to_string(s.lin.z) + "))";
        });

    // Helper to convert Python GeneralPose3 (with numpy arrays) to C++ GeneralPose3
    auto py_pose_to_cpp = [](py::object py_pose) -> GeneralPose3 {
        if (py_pose.is_none()) {
            return GeneralPose3::identity();
        }
        // Check if it's already a C++ GeneralPose3
        if (py::isinstance<GeneralPose3>(py_pose)) {
            return py_pose.cast<GeneralPose3>();
        }
        // Otherwise, extract ang, lin, scale from Python object
        Quat ang = Quat::identity();
        Vec3 lin = Vec3::zero();
        Vec3 scale{1.0, 1.0, 1.0};

        if (py::hasattr(py_pose, "ang")) {
            py::object ang_obj = py_pose.attr("ang");
            if (py::isinstance<Quat>(ang_obj)) {
                ang = ang_obj.cast<Quat>();
            } else {
                auto arr = ang_obj.cast<py::array_t<double>>();
                auto buf = arr.unchecked<1>();
                ang = Quat{buf(0), buf(1), buf(2), buf(3)};
            }
        }
        if (py::hasattr(py_pose, "lin")) {
            py::object lin_obj = py_pose.attr("lin");
            if (py::isinstance<Vec3>(lin_obj)) {
                lin = lin_obj.cast<Vec3>();
            } else {
                auto arr = lin_obj.cast<py::array_t<double>>();
                auto buf = arr.unchecked<1>();
                lin = Vec3{buf(0), buf(1), buf(2)};
            }
        }
        if (py::hasattr(py_pose, "scale")) {
            py::object scale_obj = py_pose.attr("scale");
            if (py::isinstance<Vec3>(scale_obj)) {
                scale = scale_obj.cast<Vec3>();
            } else {
                auto arr = scale_obj.cast<py::array_t<double>>();
                auto buf = arr.unchecked<1>();
                scale = Vec3{buf(0), buf(1), buf(2)};
            }
        }
        return GeneralPose3{ang, lin, scale};
    };

    // GeneralTransform3
    py::class_<GeneralTransform3>(m, "GeneralTransform3", py::dynamic_attr())
        .def(py::init<>())
        .def(py::init<const GeneralPose3&, const std::string&>(),
             py::arg("local_pose") = GeneralPose3::identity(),
             py::arg("name") = "")
        // Constructor accepting any Python object with ang/lin/scale (including Python GeneralPose3)
        .def(py::init([py_pose_to_cpp](py::object local_pose, GeneralTransform3* parent, const std::string& name) {
            GeneralPose3 pose = py_pose_to_cpp(local_pose);
            auto* t = new GeneralTransform3(pose, name);
            if (parent) {
                parent->add_child(t);
            }
            return t;
        }), py::arg("local_pose") = py::none(), py::arg("parent") = nullptr, py::arg("name") = "",
            py::return_value_policy::take_ownership)

        // Attributes
        .def_readwrite("name", &GeneralTransform3::name)
        .def_property_readonly("parent",
            [](GeneralTransform3& self) { return self.parent; },
            py::return_value_policy::reference)
        .def_property_readonly("children",
            [](GeneralTransform3& self) -> std::vector<GeneralTransform3*>& { return self.children; },
            py::return_value_policy::reference)

        // entity attribute (stored as Python object)
        .def_property("entity",
            [](GeneralTransform3& self) -> py::object {
                // Store entity as a Python attribute on the object
                py::object py_self = py::cast(&self, py::return_value_policy::reference);
                if (py::hasattr(py_self, "_entity")) {
                    return py_self.attr("_entity");
                }
                return py::none();
            },
            [](GeneralTransform3& self, py::object entity) {
                py::object py_self = py::cast(&self, py::return_value_policy::reference);
                py_self.attr("_entity") = entity;
            })

        // Pose access
        .def("local_pose", &GeneralTransform3::local_pose, py::return_value_policy::reference)
        .def("global_pose", &GeneralTransform3::global_pose, py::return_value_policy::reference)
        .def("set_local_pose", [py_pose_to_cpp](GeneralTransform3& self, py::object pose) {
            self.set_local_pose(py_pose_to_cpp(pose));
        })
        .def("set_global_pose", [py_pose_to_cpp](GeneralTransform3& self, py::object pose) {
            self.set_global_pose(py_pose_to_cpp(pose));
        })

        // Relocate (accepts Python GeneralPose3, C++ GeneralPose3, Python Pose3, or C++ Pose3)
        .def("relocate", [py_pose_to_cpp](GeneralTransform3& self, py::object pose) {
            // Check if it's a C++ Pose3
            if (py::isinstance<Pose3>(pose)) {
                self.relocate(pose.cast<Pose3>());
            }
            // Check if it's a Python Pose3 (has ang and lin but no scale)
            else if (py::hasattr(pose, "ang") && py::hasattr(pose, "lin") && !py::hasattr(pose, "scale")) {
                py::object ang_obj = pose.attr("ang");
                py::object lin_obj = pose.attr("lin");
                Quat ang = Quat::identity();
                Vec3 lin = Vec3::zero();
                if (py::isinstance<Quat>(ang_obj)) {
                    ang = ang_obj.cast<Quat>();
                } else {
                    auto arr = ang_obj.cast<py::array_t<double>>();
                    auto buf = arr.unchecked<1>();
                    ang = Quat{buf(0), buf(1), buf(2), buf(3)};
                }
                if (py::isinstance<Vec3>(lin_obj)) {
                    lin = lin_obj.cast<Vec3>();
                } else {
                    auto arr = lin_obj.cast<py::array_t<double>>();
                    auto buf = arr.unchecked<1>();
                    lin = Vec3{buf(0), buf(1), buf(2)};
                }
                self.relocate(Pose3{ang, lin});
            } else {
                self.relocate(py_pose_to_cpp(pose));
            }
        })
        .def("relocate_global", [py_pose_to_cpp](GeneralTransform3& self, py::object pose) {
            // Check if it's a C++ Pose3
            if (py::isinstance<Pose3>(pose)) {
                self.relocate_global(pose.cast<Pose3>());
            }
            // Check if it's a Python Pose3 (has ang and lin but no scale)
            else if (py::hasattr(pose, "ang") && py::hasattr(pose, "lin") && !py::hasattr(pose, "scale")) {
                py::object ang_obj = pose.attr("ang");
                py::object lin_obj = pose.attr("lin");
                Quat ang = Quat::identity();
                Vec3 lin = Vec3::zero();
                if (py::isinstance<Quat>(ang_obj)) {
                    ang = ang_obj.cast<Quat>();
                } else {
                    auto arr = ang_obj.cast<py::array_t<double>>();
                    auto buf = arr.unchecked<1>();
                    ang = Quat{buf(0), buf(1), buf(2), buf(3)};
                }
                if (py::isinstance<Vec3>(lin_obj)) {
                    lin = lin_obj.cast<Vec3>();
                } else {
                    auto arr = lin_obj.cast<py::array_t<double>>();
                    auto buf = arr.unchecked<1>();
                    lin = Vec3{buf(0), buf(1), buf(2)};
                }
                self.relocate_global(Pose3{ang, lin});
            } else {
                self.relocate_global(py_pose_to_cpp(pose));
            }
        })

        // Hierarchy
        .def("add_child", &GeneralTransform3::add_child, py::keep_alive<1, 2>())
        .def("set_parent", &GeneralTransform3::set_parent, py::keep_alive<2, 1>())
        .def("_unparent", &GeneralTransform3::unparent)
        .def("unparent", &GeneralTransform3::unparent)
        .def("link", &GeneralTransform3::add_child, py::keep_alive<1, 2>())  // alias

        // Dirty tracking
        .def("is_dirty", &GeneralTransform3::is_dirty)
        .def("_mark_dirty", &GeneralTransform3::_mark_dirty)
        .def("increment_version", [](GeneralTransform3&, uint32_t v) {
            return GeneralTransform3::increment_version(v);
        })

        // Version attributes
        .def_readwrite("_version_for_walking_to_proximal", &GeneralTransform3::_version_for_walking_to_proximal)
        .def_readwrite("_version_for_walking_to_distal", &GeneralTransform3::_version_for_walking_to_distal)
        .def_readwrite("_version_only_my", &GeneralTransform3::_version_only_my)

        // Transformations - return numpy arrays
        .def("transform_point", [](const GeneralTransform3& self, py::array_t<double> point) {
            Vec3 p = numpy_to_vec3(point);
            Vec3 result = self.transform_point(p);
            return vec3_to_numpy(result);
        })
        .def("transform_point_inverse", [](const GeneralTransform3& self, py::array_t<double> point) {
            Vec3 p = numpy_to_vec3(point);
            Vec3 result = self.transform_point_inverse(p);
            return vec3_to_numpy(result);
        })
        .def("transform_vector", [](const GeneralTransform3& self, py::array_t<double> vec) {
            Vec3 v = numpy_to_vec3(vec);
            Vec3 result = self.transform_vector(v);
            return vec3_to_numpy(result);
        })
        .def("transform_vector_inverse", [](const GeneralTransform3& self, py::array_t<double> vec) {
            Vec3 v = numpy_to_vec3(vec);
            Vec3 result = self.transform_vector_inverse(v);
            return vec3_to_numpy(result);
        })

        // Direction helpers - return numpy arrays
        .def("forward", [](const GeneralTransform3& self, double distance) {
            return vec3_to_numpy(self.forward(distance));
        }, py::arg("distance") = 1.0)
        .def("backward", [](const GeneralTransform3& self, double distance) {
            return vec3_to_numpy(self.backward(distance));
        }, py::arg("distance") = 1.0)
        .def("up", [](const GeneralTransform3& self, double distance) {
            return vec3_to_numpy(self.up(distance));
        }, py::arg("distance") = 1.0)
        .def("down", [](const GeneralTransform3& self, double distance) {
            return vec3_to_numpy(self.down(distance));
        }, py::arg("distance") = 1.0)
        .def("right", [](const GeneralTransform3& self, double distance) {
            return vec3_to_numpy(self.right(distance));
        }, py::arg("distance") = 1.0)
        .def("left", [](const GeneralTransform3& self, double distance) {
            return vec3_to_numpy(self.left(distance));
        }, py::arg("distance") = 1.0)

        // World matrix - return 4x4 numpy array
        .def("world_matrix", [](const GeneralTransform3& self) {
            auto result = make_mat(4, 4);
            auto buf = result.mutable_unchecked<2>();
            double m[16];
            self.world_matrix(m);
            for (int i = 0; i < 4; i++)
                for (int j = 0; j < 4; j++)
                    buf(i, j) = m[i * 4 + j];
            return result;
        })

        .def("__repr__", [](const GeneralTransform3& self) {
            const auto& p = self._local_pose;
            return "GeneralTransform3(" + self.name + ", local_pose=GeneralPose3(...))";
        });

    // TransformHandle
    py::class_<TransformHandle>(m, "TransformHandle")
        .def(py::init<>())
        .def_readonly("index", &TransformHandle::index)
        .def_readonly("generation", &TransformHandle::generation)
        .def("is_null", &TransformHandle::is_null)
        .def("__bool__", &TransformHandle::operator bool)
        .def("__eq__", &TransformHandle::operator==)
        .def("__ne__", &TransformHandle::operator!=)
        .def("__repr__", [](const TransformHandle& h) {
            if (h.is_null()) return std::string("TransformHandle(null)");
            return "TransformHandle(index=" + std::to_string(h.index) +
                   ", generation=" + std::to_string(h.generation) + ")";
        });

    // GeneralTransform3Pool
    py::class_<GeneralTransform3Pool>(m, "GeneralTransform3Pool")
        .def(py::init<size_t>(), py::arg("initial_capacity") = 256)

        .def("create", &GeneralTransform3Pool::create,
             py::arg("local_pose") = GeneralPose3::identity(),
             py::arg("name") = "")
        .def("destroy", &GeneralTransform3Pool::destroy)
        .def("destroy_by_ptr", &GeneralTransform3Pool::destroy_by_ptr)

        .def("get", py::overload_cast<TransformHandle>(&GeneralTransform3Pool::get),
             py::return_value_policy::reference)
        .def("is_valid", &GeneralTransform3Pool::is_valid)
        .def("is_valid_ptr", &GeneralTransform3Pool::is_valid_ptr)
        .def("handle_from_ptr", &GeneralTransform3Pool::handle_from_ptr)

        .def("__len__", &GeneralTransform3Pool::size)
        .def_property_readonly("size", &GeneralTransform3Pool::size)
        .def_property_readonly("capacity", &GeneralTransform3Pool::capacity)

        .def("__repr__", [](const GeneralTransform3Pool& pool) {
            return "GeneralTransform3Pool(size=" + std::to_string(pool.size()) +
                   ", capacity=" + std::to_string(pool.capacity()) + ")";
        });

}
