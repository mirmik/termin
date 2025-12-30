#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/operators.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/pair.h>

#include "termin/geom/geom.hpp"

namespace nb = nanobind;
using namespace termin;

// Helper to create numpy array from Vec3
static nb::object vec3_to_numpy(const Vec3& v) {
    double* data = new double[3]{v.x, v.y, v.z};
    nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
    return nb::cast(nb::ndarray<nb::numpy, double, nb::shape<3>>(data, {3}, owner));
}

// Helper to create Vec3 from numpy array
static Vec3 numpy_to_vec3(nb::ndarray<double, nb::c_contig, nb::device::cpu> arr) {
    double* ptr = arr.data();
    return {ptr[0], ptr[1], ptr[2]};
}

// Helper to create numpy array from Quat
static nb::object quat_to_numpy(const Quat& q) {
    double* data = new double[4]{q.x, q.y, q.z, q.w};
    nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
    return nb::cast(nb::ndarray<nb::numpy, double, nb::shape<4>>(data, {4}, owner));
}

// Helper to create Quat from numpy array
static Quat numpy_to_quat(nb::ndarray<double, nb::c_contig, nb::device::cpu> arr) {
    double* ptr = arr.data();
    return {ptr[0], ptr[1], ptr[2], ptr[3]};
}

// Helper to convert any array-like Python object to Vec3
static Vec3 py_to_vec3(nb::object obj) {
    if (nb::isinstance<Vec3>(obj)) {
        return nb::cast<Vec3>(obj);
    }
    // Try ndarray
    try {
        auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(obj);
        double* ptr = arr.data();
        return Vec3{ptr[0], ptr[1], ptr[2]};
    } catch (...) {}
    // Try sequence protocol
    nb::sequence seq = nb::cast<nb::sequence>(obj);
    return Vec3{nb::cast<double>(seq[0]), nb::cast<double>(seq[1]), nb::cast<double>(seq[2])};
}

NB_MODULE(_geom_native, m) {
    m.doc() = "Native C++ geometry module for termin";

    // Vec3
    nb::class_<Vec3>(m, "Vec3")
        .def(nb::init<>())
        .def(nb::init<double, double, double>())
        .def("__init__", [](Vec3* self, nb::ndarray<double, nb::c_contig, nb::device::cpu> arr) {
            new (self) Vec3(numpy_to_vec3(arr));
        })
        .def_rw("x", &Vec3::x)
        .def_rw("y", &Vec3::y)
        .def_rw("z", &Vec3::z)
        .def("__getitem__", [](const Vec3& v, int i) { return v[i]; })
        .def("__setitem__", [](Vec3& v, int i, double val) { v[i] = val; })
        .def("__setitem__", [](Vec3& v, nb::ellipsis, nb::object val) {
            // Support vec[...] = (x, y, z) or vec[...] = other_vec
            if (nb::isinstance<Vec3>(val)) {
                Vec3 other = nb::cast<Vec3>(val);
                v.x = other.x;
                v.y = other.y;
                v.z = other.z;
            } else {
                nb::sequence seq = nb::cast<nb::sequence>(val);
                v.x = nb::cast<double>(seq[0]);
                v.y = nb::cast<double>(seq[1]);
                v.z = nb::cast<double>(seq[2]);
            }
        })
        .def("__len__", [](const Vec3&) { return 3; })
        .def("__iter__", [](const Vec3& v) {
            return nb::make_iterator(nb::type<Vec3>(), "vec3_iter", &v.x, &v.x + 3);
        }, nb::keep_alive<0, 1>())
        .def(nb::self + nb::self)
        .def(nb::self - nb::self)
        .def(nb::self * double())
        .def(double() * nb::self)
        .def(nb::self / double())
        .def(-nb::self)
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
        .def("tolist", [](const Vec3& v) {
            nb::list lst;
            lst.append(v.x);
            lst.append(v.y);
            lst.append(v.z);
            return lst;
        })
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
        }, nb::arg("other"), nb::arg("eps") = 1e-9)
        .def("__repr__", [](const Vec3& v) {
            return "Vec3(" + std::to_string(v.x) + ", " +
                   std::to_string(v.y) + ", " + std::to_string(v.z) + ")";
        });

    // Quat
    nb::class_<Quat>(m, "Quat")
        .def(nb::init<>())
        .def(nb::init<double, double, double, double>())
        .def("__init__", [](Quat* self, nb::ndarray<double, nb::c_contig, nb::device::cpu> arr) {
            new (self) Quat(numpy_to_quat(arr));
        })
        .def_rw("x", &Quat::x)
        .def_rw("y", &Quat::y)
        .def_rw("z", &Quat::z)
        .def_rw("w", &Quat::w)
        .def("__getitem__", [](const Quat& q, int i) {
            if (i == 0) return q.x;
            if (i == 1) return q.y;
            if (i == 2) return q.z;
            if (i == 3) return q.w;
            throw nb::index_error("Quat index out of range");
        })
        .def("__setitem__", [](Quat& q, int i, double val) {
            if (i == 0) q.x = val;
            else if (i == 1) q.y = val;
            else if (i == 2) q.z = val;
            else if (i == 3) q.w = val;
            else throw nb::index_error("Quat index out of range");
        })
        .def("__setitem__", [](Quat& q, nb::ellipsis, nb::object val) {
            // Support quat[...] = (x, y, z, w) or quat[...] = other_quat
            if (nb::isinstance<Quat>(val)) {
                Quat other = nb::cast<Quat>(val);
                q.x = other.x;
                q.y = other.y;
                q.z = other.z;
                q.w = other.w;
            } else {
                nb::sequence seq = nb::cast<nb::sequence>(val);
                q.x = nb::cast<double>(seq[0]);
                q.y = nb::cast<double>(seq[1]);
                q.z = nb::cast<double>(seq[2]);
                q.w = nb::cast<double>(seq[3]);
            }
        })
        .def("__len__", [](const Quat&) { return 4; })
        .def("__iter__", [](const Quat& q) {
            return nb::make_iterator(nb::type<Quat>(), "quat_iter", &q.x, &q.x + 4);
        }, nb::keep_alive<0, 1>())
        .def(nb::self * nb::self)
        .def("conjugate", &Quat::conjugate)
        .def("inverse", &Quat::inverse)
        .def("norm", &Quat::norm)
        .def("normalized", &Quat::normalized)
        .def("rotate", &Quat::rotate)
        .def("inverse_rotate", &Quat::inverse_rotate)
        .def_static("identity", &Quat::identity)
        .def_static("from_axis_angle", &Quat::from_axis_angle)
        .def("to_numpy", &quat_to_numpy)
        .def("tolist", [](const Quat& q) {
            nb::list lst;
            lst.append(q.x);
            lst.append(q.y);
            lst.append(q.z);
            lst.append(q.w);
            return lst;
        })
        .def("copy", [](const Quat& q) { return q; })
        .def("__repr__", [](const Quat& q) {
            return "Quat(" + std::to_string(q.x) + ", " +
                   std::to_string(q.y) + ", " + std::to_string(q.z) + ", " +
                   std::to_string(q.w) + ")";
        });

    m.def("slerp", &slerp, "Spherical linear interpolation between quaternions");

    // Mat44
    nb::class_<Mat44>(m, "Mat44")
        .def(nb::init<>())
        .def("__call__", [](const Mat44& mat, int col, int row) { return mat(col, row); })
        .def("__getitem__", [](const Mat44& mat, std::pair<int, int> idx) {
            return mat(idx.first, idx.second);
        })
        .def("__setitem__", [](Mat44& mat, std::pair<int, int> idx, double val) {
            mat(idx.first, idx.second) = val;
        })
        .def(nb::self * nb::self)
        .def("transform_point", &Mat44::transform_point)
        .def("transform_direction", &Mat44::transform_direction)
        .def("transposed", &Mat44::transposed)
        .def("inverse", &Mat44::inverse)
        .def("get_translation", &Mat44::get_translation)
        .def("get_scale", &Mat44::get_scale)
        .def_static("identity", &Mat44::identity)
        .def_static("zero", &Mat44::zero)
        .def_static("translation", nb::overload_cast<const Vec3&>(&Mat44::translation))
        .def_static("translation", nb::overload_cast<double, double, double>(&Mat44::translation))
        .def_static("scale", nb::overload_cast<const Vec3&>(&Mat44::scale))
        .def_static("scale", nb::overload_cast<double>(&Mat44::scale))
        .def_static("rotation", &Mat44::rotation)
        .def_static("rotation_axis_angle", &Mat44::rotation_axis_angle)
        .def_static("perspective", &Mat44::perspective,
            nb::arg("fov_y"), nb::arg("aspect"), nb::arg("near"), nb::arg("far"),
            "Perspective projection (Y-forward, Z-up)")
        .def_static("orthographic", &Mat44::orthographic,
            nb::arg("left"), nb::arg("right"), nb::arg("bottom"), nb::arg("top"),
            nb::arg("near"), nb::arg("far"),
            "Orthographic projection (Y-forward, Z-up)")
        .def_static("look_at", &Mat44::look_at,
            nb::arg("eye"), nb::arg("target"), nb::arg("up") = Vec3::unit_z(),
            "Look-at view matrix (Y-forward, Z-up)")
        .def_static("compose", &Mat44::compose,
            nb::arg("translation"), nb::arg("rotation"), nb::arg("scale"),
            "Compose TRS matrix")
        .def("to_numpy", [](const Mat44& mat) {
            double* data = new double[16];
            for (int col = 0; col < 4; ++col) {
                for (int row = 0; row < 4; ++row) {
                    data[row * 4 + col] = mat(col, row);
                }
            }
            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
            size_t shape[2] = {4, 4};
            return nb::ndarray<nb::numpy, double, nb::shape<4, 4>>(data, 2, shape, owner);
        })
        .def("to_numpy_f32", [](const Mat44& mat) {
            float* data = new float[16];
            for (int col = 0; col < 4; ++col) {
                for (int row = 0; row < 4; ++row) {
                    data[row * 4 + col] = static_cast<float>(mat(col, row));
                }
            }
            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<float*>(p); });
            size_t shape[2] = {4, 4};
            return nb::ndarray<nb::numpy, float, nb::shape<4, 4>>(data, 2, shape, owner);
        })
        .def("__repr__", [](const Mat44& mat) {
            return "<Mat44>";
        });

    // Pose3
    nb::class_<Pose3>(m, "Pose3")
        .def(nb::init<>())
        .def(nb::init<const Quat&, const Vec3&>())
        // Convenience: Pose3(Vec3) - translation only
        .def("__init__", [](Pose3* self, const Vec3& lin) {
            new (self) Pose3{Quat::identity(), lin};
        })
        .def("__init__", [](Pose3* self,
                           nb::ndarray<double, nb::c_contig, nb::device::cpu> ang_arr,
                           nb::ndarray<double, nb::c_contig, nb::device::cpu> lin_arr) {
            new (self) Pose3(numpy_to_quat(ang_arr), numpy_to_vec3(lin_arr));
        })
        // Python-style constructor with keyword args
        .def("__init__", [](Pose3* self, nb::object ang, nb::object lin) {
            Quat q = Quat::identity();
            Vec3 t = Vec3::zero();

            if (!ang.is_none()) {
                if (nb::isinstance<Quat>(ang)) {
                    q = nb::cast<Quat>(ang);
                } else {
                    auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(ang);
                    double* ptr = arr.data();
                    q = Quat{ptr[0], ptr[1], ptr[2], ptr[3]};
                }
            }
            if (!lin.is_none()) {
                if (nb::isinstance<Vec3>(lin)) {
                    t = nb::cast<Vec3>(lin);
                } else {
                    auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(lin);
                    double* ptr = arr.data();
                    t = Vec3{ptr[0], ptr[1], ptr[2]};
                }
            }
            new (self) Pose3{q, t};
        }, nb::arg("ang") = nb::none(), nb::arg("lin") = nb::none())
        .def_prop_rw("ang",
            [](const Pose3& p) { return p.ang; },
            [](Pose3& p, nb::object val) {
                if (nb::isinstance<Quat>(val)) {
                    p.ang = nb::cast<Quat>(val);
                } else {
                    auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(val);
                    double* ptr = arr.data();
                    p.ang = Quat{ptr[0], ptr[1], ptr[2], ptr[3]};
                }
            })
        .def_prop_rw("lin",
            [](const Pose3& p) { return p.lin; },
            [](Pose3& p, nb::object val) {
                if (nb::isinstance<Vec3>(val)) {
                    p.lin = nb::cast<Vec3>(val);
                } else {
                    auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(val);
                    double* ptr = arr.data();
                    p.lin = Vec3{ptr[0], ptr[1], ptr[2]};
                }
            })
        .def(nb::self * nb::self)
        .def("__matmul__", [](const Pose3& a, const Pose3& b) { return a * b; })
        .def("inverse", &Pose3::inverse)
        .def("transform_point", nb::overload_cast<const Vec3&>(&Pose3::transform_point, nb::const_))
        .def("transform_point", [](const Pose3& p, nb::object obj) {
            return p.transform_point(py_to_vec3(obj));
        })
        .def("transform_vector", nb::overload_cast<const Vec3&>(&Pose3::transform_vector, nb::const_))
        .def("transform_vector", [](const Pose3& p, nb::object obj) {
            return p.transform_vector(py_to_vec3(obj));
        })
        .def("rotate_point", &Pose3::rotate_point)
        .def("rotate_point", [](const Pose3& p, nb::object obj) {
            return p.rotate_point(py_to_vec3(obj));
        })
        .def("inverse_transform_point", nb::overload_cast<const Vec3&>(&Pose3::inverse_transform_point, nb::const_))
        .def("inverse_transform_point", [](const Pose3& p, nb::object obj) {
            return p.inverse_transform_point(py_to_vec3(obj));
        })
        .def("inverse_transform_vector", nb::overload_cast<const Vec3&>(&Pose3::inverse_transform_vector, nb::const_))
        .def("inverse_transform_vector", [](const Pose3& p, nb::object obj) {
            return p.inverse_transform_vector(py_to_vec3(obj));
        })
        // rotate_vector is an alias for transform_vector (for Pose3 without scale, they are the same)
        .def("rotate_vector", nb::overload_cast<const Vec3&>(&Pose3::transform_vector, nb::const_))
        .def("rotate_vector", [](const Pose3& p, nb::object obj) {
            return p.transform_vector(py_to_vec3(obj));
        })
        .def("inverse_rotate_vector", nb::overload_cast<const Vec3&>(&Pose3::inverse_transform_vector, nb::const_))
        .def("inverse_rotate_vector", [](const Pose3& p, nb::object obj) {
            return p.inverse_transform_vector(py_to_vec3(obj));
        })
        .def("normalized", &Pose3::normalized)
        .def("with_translation", nb::overload_cast<const Vec3&>(&Pose3::with_translation, nb::const_))
        .def("with_rotation", &Pose3::with_rotation)
        .def("rotation_matrix", [](const Pose3& p) {
            double* data = new double[9];
            p.rotation_matrix(data);
            nb::capsule owner(data, [](void* ptr) noexcept { delete[] static_cast<double*>(ptr); });
            size_t shape[2] = {3, 3};
            return nb::ndarray<nb::numpy, double, nb::shape<3, 3>>(data, 2, shape, owner);
        })
        .def_static("identity", &Pose3::identity)
        .def_static("translation", nb::overload_cast<double, double, double>(&Pose3::translation))
        .def_static("rotation", nb::overload_cast<const Vec3&, double>(&Pose3::rotation))
        .def_static("rotation", [](nb::ndarray<double, nb::c_contig, nb::device::cpu> axis_arr, double angle) {
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
        .def_static("looking_at", nb::overload_cast<const Vec3&, const Vec3&, const Vec3&>(&Pose3::looking_at),
                    nb::arg("eye"), nb::arg("target"), nb::arg("up") = Vec3::unit_z())
        .def_static("looking_at", [](nb::ndarray<double, nb::c_contig, nb::device::cpu> eye,
                                     nb::ndarray<double, nb::c_contig, nb::device::cpu> target,
                                     nb::object up_obj) {
            Vec3 up = Vec3::unit_z();
            if (!up_obj.is_none()) {
                if (nb::isinstance<Vec3>(up_obj)) {
                    up = nb::cast<Vec3>(up_obj);
                } else {
                    auto up_arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(up_obj);
                    double* ptr = up_arr.data();
                    up = Vec3{ptr[0], ptr[1], ptr[2]};
                }
            }
            double* eye_ptr = eye.data();
            double* target_ptr = target.data();
            return Pose3::looking_at(
                Vec3{eye_ptr[0], eye_ptr[1], eye_ptr[2]},
                Vec3{target_ptr[0], target_ptr[1], target_ptr[2]},
                up
            );
        }, nb::arg("eye"), nb::arg("target"), nb::arg("up") = nb::none())
        .def_static("from_euler", &Pose3::from_euler,
                    nb::arg("roll"), nb::arg("pitch"), nb::arg("yaw"))
        .def("to_euler", nb::overload_cast<>(&Pose3::to_euler, nb::const_))
        .def("to_axis_angle", [](const Pose3& p) {
            Vec3 axis;
            double angle;
            p.to_axis_angle(axis, angle);
            return nb::make_tuple(axis, angle);
        })
        .def("distance", &Pose3::distance)
        .def("copy", &Pose3::copy)
        .def("as_matrix", [](const Pose3& p) {
            double* data = new double[16];
            double m[16];
            p.as_matrix(m);
            for (int i = 0; i < 4; i++)
                for (int j = 0; j < 4; j++)
                    data[i * 4 + j] = m[j * 4 + i];  // column-major to row-major
            nb::capsule owner(data, [](void* ptr) noexcept { delete[] static_cast<double*>(ptr); });
            size_t shape[2] = {4, 4};
            return nb::ndarray<nb::numpy, double, nb::shape<4, 4>>(data, 2, shape, owner);
        })
        .def("as_matrix34", [](const Pose3& p) {
            double* data = new double[12];
            double rot[9];
            p.rotation_matrix(rot);
            for (int i = 0; i < 3; i++)
                for (int j = 0; j < 3; j++)
                    data[i * 4 + j] = rot[i * 3 + j];
            data[3] = p.lin.x;
            data[7] = p.lin.y;
            data[11] = p.lin.z;
            nb::capsule owner(data, [](void* ptr) noexcept { delete[] static_cast<double*>(ptr); });
            size_t shape[2] = {3, 4};
            return nb::ndarray<nb::numpy, double, nb::shape<3, 4>>(data, 2, shape, owner);
        })
        .def("compose", [](const Pose3& a, const Pose3& b) { return a * b; })
        // x, y, z property shortcuts for translation
        .def_prop_rw("x",
            [](const Pose3& p) { return p.lin.x; },
            [](Pose3& p, double v) { p.lin.x = v; })
        .def_prop_rw("y",
            [](const Pose3& p) { return p.lin.y; },
            [](Pose3& p, double v) { p.lin.y = v; })
        .def_prop_rw("z",
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
        .def_static("from_axis_angle", [](nb::ndarray<double, nb::c_contig, nb::device::cpu> axis_arr, double angle) {
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
            return nb::make_tuple(euler.x, euler.y, euler.z);
        })
        .def("to_general_pose3", [](const Pose3& p, const Vec3& scale) {
            return GeneralPose3(p.ang, p.lin, scale);
        }, nb::arg("scale") = Vec3{1.0, 1.0, 1.0})
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

    // GeneralPose3
    nb::class_<GeneralPose3>(m, "GeneralPose3")
        .def(nb::init<>())
        .def(nb::init<const Quat&, const Vec3&, const Vec3&>(),
             nb::arg("ang"), nb::arg("lin"), nb::arg("scale") = Vec3{1.0, 1.0, 1.0})
        .def("__init__", [](GeneralPose3* self,
                           nb::ndarray<double, nb::c_contig, nb::device::cpu> ang_arr,
                           nb::ndarray<double, nb::c_contig, nb::device::cpu> lin_arr,
                           nb::ndarray<double, nb::c_contig, nb::device::cpu> scale_arr) {
            new (self) GeneralPose3(numpy_to_quat(ang_arr), numpy_to_vec3(lin_arr), numpy_to_vec3(scale_arr));
        })
        // Python-style constructor with keyword args (matching Python GeneralPose3)
        .def("__init__", [](GeneralPose3* self, nb::object ang, nb::object lin, nb::object scale) {
            Quat q = Quat::identity();
            Vec3 t = Vec3::zero();
            Vec3 s{1.0, 1.0, 1.0};

            if (!ang.is_none()) {
                if (nb::isinstance<Quat>(ang)) {
                    q = nb::cast<Quat>(ang);
                } else {
                    auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(ang);
                    double* ptr = arr.data();
                    q = Quat{ptr[0], ptr[1], ptr[2], ptr[3]};
                }
            }
            if (!lin.is_none()) {
                if (nb::isinstance<Vec3>(lin)) {
                    t = nb::cast<Vec3>(lin);
                } else {
                    auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(lin);
                    double* ptr = arr.data();
                    t = Vec3{ptr[0], ptr[1], ptr[2]};
                }
            }
            if (!scale.is_none()) {
                if (nb::isinstance<Vec3>(scale)) {
                    s = nb::cast<Vec3>(scale);
                } else {
                    auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(scale);
                    double* ptr = arr.data();
                    s = Vec3{ptr[0], ptr[1], ptr[2]};
                }
            }
            new (self) GeneralPose3{q, t, s};
        }, nb::arg("ang") = nb::none(), nb::arg("lin") = nb::none(), nb::arg("scale") = nb::none())
        .def_prop_rw("ang",
            [](const GeneralPose3& p) { return p.ang; },
            [](GeneralPose3& p, nb::object val) {
                if (nb::isinstance<Quat>(val)) {
                    p.ang = nb::cast<Quat>(val);
                } else {
                    auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(val);
                    double* ptr = arr.data();
                    p.ang = Quat{ptr[0], ptr[1], ptr[2], ptr[3]};
                }
            })
        .def_prop_rw("lin",
            [](const GeneralPose3& p) { return p.lin; },
            [](GeneralPose3& p, nb::object val) {
                if (nb::isinstance<Vec3>(val)) {
                    p.lin = nb::cast<Vec3>(val);
                } else {
                    auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(val);
                    double* ptr = arr.data();
                    p.lin = Vec3{ptr[0], ptr[1], ptr[2]};
                }
            })
        .def_prop_rw("scale",
            [](const GeneralPose3& p) { return p.scale; },
            [](GeneralPose3& p, nb::object val) {
                if (nb::isinstance<Vec3>(val)) {
                    p.scale = nb::cast<Vec3>(val);
                } else {
                    auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(val);
                    double* ptr = arr.data();
                    p.scale = Vec3{ptr[0], ptr[1], ptr[2]};
                }
            })
        .def(nb::self * nb::self)
        .def("__matmul__", [](const GeneralPose3& a, const GeneralPose3& b) { return a * b; })
        .def("inverse", &GeneralPose3::inverse)
        .def("transform_point", nb::overload_cast<const Vec3&>(&GeneralPose3::transform_point, nb::const_))
        .def("transform_point", [](const GeneralPose3& p, nb::object obj) {
            return p.transform_point(py_to_vec3(obj));
        })
        .def("transform_vector", nb::overload_cast<const Vec3&>(&GeneralPose3::transform_vector, nb::const_))
        .def("transform_vector", [](const GeneralPose3& p, nb::object obj) {
            return p.transform_vector(py_to_vec3(obj));
        })
        .def("rotate_point", nb::overload_cast<const Vec3&>(&GeneralPose3::rotate_point, nb::const_))
        .def("rotate_point", [](const GeneralPose3& p, nb::object obj) {
            return p.rotate_point(py_to_vec3(obj));
        })
        .def("inverse_transform_point", nb::overload_cast<const Vec3&>(&GeneralPose3::inverse_transform_point, nb::const_))
        .def("inverse_transform_point", [](const GeneralPose3& p, nb::object obj) {
            return p.inverse_transform_point(py_to_vec3(obj));
        })
        .def("inverse_transform_vector", nb::overload_cast<const Vec3&>(&GeneralPose3::inverse_transform_vector, nb::const_))
        .def("inverse_transform_vector", [](const GeneralPose3& p, nb::object obj) {
            return p.inverse_transform_vector(py_to_vec3(obj));
        })
        .def("normalized", &GeneralPose3::normalized)
        .def("with_translation", nb::overload_cast<const Vec3&>(&GeneralPose3::with_translation, nb::const_))
        .def("with_rotation", &GeneralPose3::with_rotation)
        .def("with_scale", nb::overload_cast<const Vec3&>(&GeneralPose3::with_scale, nb::const_))
        .def("to_pose3", &GeneralPose3::to_pose3)
        .def("rotation_matrix", [](const GeneralPose3& p) {
            double* data = new double[9];
            p.rotation_matrix(data);
            nb::capsule owner(data, [](void* ptr) noexcept { delete[] static_cast<double*>(ptr); });
            size_t shape[2] = {3, 3};
            return nb::ndarray<nb::numpy, double, nb::shape<3, 3>>(data, 2, shape, owner);
        })
        .def("as_matrix", [](const GeneralPose3& p) {
            double* data = new double[16];
            double m_arr[16];
            p.matrix4(m_arr);
            for (int i = 0; i < 4; i++)
                for (int j = 0; j < 4; j++)
                    data[i * 4 + j] = m_arr[i * 4 + j];
            nb::capsule owner(data, [](void* ptr) noexcept { delete[] static_cast<double*>(ptr); });
            size_t shape[2] = {4, 4};
            return nb::ndarray<nb::numpy, double, nb::shape<4, 4>>(data, 2, shape, owner);
        })
        .def("as_matrix34", [](const GeneralPose3& p) {
            double* data = new double[12];
            double m_arr[12];
            p.matrix34(m_arr);
            for (int i = 0; i < 3; i++)
                for (int j = 0; j < 4; j++)
                    data[i * 4 + j] = m_arr[i * 4 + j];
            nb::capsule owner(data, [](void* ptr) noexcept { delete[] static_cast<double*>(ptr); });
            size_t shape[2] = {3, 4};
            return nb::ndarray<nb::numpy, double, nb::shape<3, 4>>(data, 2, shape, owner);
        })
        .def("inverse_matrix", [](const GeneralPose3& p) {
            double* data = new double[16];
            double m_arr[16];
            p.inverse_matrix4(m_arr);
            for (int i = 0; i < 4; i++)
                for (int j = 0; j < 4; j++)
                    data[i * 4 + j] = m_arr[i * 4 + j];
            nb::capsule owner(data, [](void* ptr) noexcept { delete[] static_cast<double*>(ptr); });
            size_t shape[2] = {4, 4};
            return nb::ndarray<nb::numpy, double, nb::shape<4, 4>>(data, 2, shape, owner);
        })
        .def_static("identity", &GeneralPose3::identity)
        .def_static("translation", nb::overload_cast<double, double, double>(&GeneralPose3::translation))
        .def_static("translation", nb::overload_cast<const Vec3&>(&GeneralPose3::translation))
        .def_static("rotation", &GeneralPose3::rotation)
        .def_static("scaling", nb::overload_cast<double>(&GeneralPose3::scaling))
        .def_static("scaling", nb::overload_cast<double, double, double>(&GeneralPose3::scaling))
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
        .def_static("looking_at", nb::overload_cast<const Vec3&, const Vec3&, const Vec3&>(&GeneralPose3::looking_at),
                    nb::arg("eye"), nb::arg("target"), nb::arg("up_vec") = Vec3{0.0, 0.0, 1.0})
        .def_static("looking_at", [](nb::ndarray<double, nb::c_contig, nb::device::cpu> eye,
                                     nb::ndarray<double, nb::c_contig, nb::device::cpu> target,
                                     nb::object up_obj) {
            Vec3 up{0.0, 0.0, 1.0};
            if (!up_obj.is_none()) {
                if (nb::isinstance<Vec3>(up_obj)) {
                    up = nb::cast<Vec3>(up_obj);
                } else {
                    auto up_arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(up_obj);
                    double* ptr = up_arr.data();
                    up = Vec3{ptr[0], ptr[1], ptr[2]};
                }
            }
            double* eye_ptr = eye.data();
            double* target_ptr = target.data();
            return GeneralPose3::looking_at(
                Vec3{eye_ptr[0], eye_ptr[1], eye_ptr[2]},
                Vec3{target_ptr[0], target_ptr[1], target_ptr[2]},
                up
            );
        }, nb::arg("eye"), nb::arg("target"), nb::arg("up_vec") = nb::none())
        .def_static("lerp",
                    static_cast<GeneralPose3 (*)(const GeneralPose3&, const GeneralPose3&, double)>(&lerp),
                    "Linear interpolation between GeneralPose3 (with scale)")
        .def_static("from_matrix", [](nb::ndarray<double, nb::c_contig, nb::device::cpu> mat) {
            double* buf = mat.data();
            // Assume row-major 4x4 layout
            // Extract translation from 4th column
            Vec3 lin{buf[0 * 4 + 3], buf[1 * 4 + 3], buf[2 * 4 + 3]};

            // Extract column vectors of upper-left 3x3 for scale
            Vec3 col0{buf[0 * 4 + 0], buf[1 * 4 + 0], buf[2 * 4 + 0]};
            Vec3 col1{buf[0 * 4 + 1], buf[1 * 4 + 1], buf[2 * 4 + 1]};
            Vec3 col2{buf[0 * 4 + 2], buf[1 * 4 + 2], buf[2 * 4 + 2]};

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

    // Screw3
    nb::class_<Screw3>(m, "Screw3")
        .def(nb::init<>())
        .def(nb::init<const Vec3&, const Vec3&>(), nb::arg("ang"), nb::arg("lin"))
        .def("__init__", [](Screw3* self,
                           nb::ndarray<double, nb::c_contig, nb::device::cpu> ang_arr,
                           nb::ndarray<double, nb::c_contig, nb::device::cpu> lin_arr) {
            new (self) Screw3(numpy_to_vec3(ang_arr), numpy_to_vec3(lin_arr));
        }, nb::arg("ang"), nb::arg("lin"))
        .def_rw("ang", &Screw3::ang)
        .def_rw("lin", &Screw3::lin)
        .def(nb::self + nb::self)
        .def(nb::self - nb::self)
        .def(nb::self * double())
        .def(double() * nb::self)
        .def(-nb::self)
        .def("dot", &Screw3::dot)
        .def("cross_motion", &Screw3::cross_motion)
        .def("cross_force", &Screw3::cross_force)
        .def("transform_by", &Screw3::transform_by)
        .def("inverse_transform_by", &Screw3::inverse_transform_by)
        .def("to_pose", &Screw3::to_pose)
        .def("as_pose3", &Screw3::to_pose)  // alias for compatibility
        .def("scaled", &Screw3::scaled)
        // Adjoint overloads
        .def("adjoint", nb::overload_cast<const Pose3&>(&Screw3::adjoint, nb::const_))
        .def("adjoint", nb::overload_cast<const Vec3&>(&Screw3::adjoint, nb::const_))
        .def("adjoint", [](const Screw3& s, nb::ndarray<double, nb::c_contig, nb::device::cpu> arm_arr) {
            return s.adjoint(numpy_to_vec3(arm_arr));
        })
        .def("adjoint_inv", nb::overload_cast<const Pose3&>(&Screw3::adjoint_inv, nb::const_))
        .def("adjoint_inv", nb::overload_cast<const Vec3&>(&Screw3::adjoint_inv, nb::const_))
        .def("adjoint_inv", [](const Screw3& s, nb::ndarray<double, nb::c_contig, nb::device::cpu> arm_arr) {
            return s.adjoint_inv(numpy_to_vec3(arm_arr));
        })
        .def("coadjoint", nb::overload_cast<const Pose3&>(&Screw3::coadjoint, nb::const_))
        .def("coadjoint", nb::overload_cast<const Vec3&>(&Screw3::coadjoint, nb::const_))
        .def("coadjoint", [](const Screw3& s, nb::ndarray<double, nb::c_contig, nb::device::cpu> arm_arr) {
            return s.coadjoint(numpy_to_vec3(arm_arr));
        })
        .def("coadjoint_inv", nb::overload_cast<const Pose3&>(&Screw3::coadjoint_inv, nb::const_))
        .def("coadjoint_inv", nb::overload_cast<const Vec3&>(&Screw3::coadjoint_inv, nb::const_))
        .def("coadjoint_inv", [](const Screw3& s, nb::ndarray<double, nb::c_contig, nb::device::cpu> arm_arr) {
            return s.coadjoint_inv(numpy_to_vec3(arm_arr));
        })
        // Aliases for compatibility
        .def("kinematic_carry", nb::overload_cast<const Vec3&>(&Screw3::adjoint, nb::const_))
        .def("kinematic_carry", [](const Screw3& s, nb::ndarray<double, nb::c_contig, nb::device::cpu> arm_arr) {
            return s.adjoint(numpy_to_vec3(arm_arr));
        })
        .def("twist_carry", nb::overload_cast<const Vec3&>(&Screw3::adjoint, nb::const_))
        .def("force_carry", nb::overload_cast<const Vec3&>(&Screw3::coadjoint, nb::const_))
        .def("force_carry", [](const Screw3& s, nb::ndarray<double, nb::c_contig, nb::device::cpu> arm_arr) {
            return s.coadjoint(numpy_to_vec3(arm_arr));
        })
        .def("wrench_carry", nb::overload_cast<const Vec3&>(&Screw3::coadjoint, nb::const_))
        .def_static("zero", &Screw3::zero)
        .def("__repr__", [](const Screw3& s) {
            return "Screw3(ang=Vec3(" + std::to_string(s.ang.x) + ", " +
                   std::to_string(s.ang.y) + ", " + std::to_string(s.ang.z) +
                   "), lin=Vec3(" + std::to_string(s.lin.x) + ", " +
                   std::to_string(s.lin.y) + ", " + std::to_string(s.lin.z) + "))";
        });

    // GeneralTransform3 bindings are now in termin/bindings/geom/transform.cpp

    // TransformHandle
    nb::class_<TransformHandle>(m, "TransformHandle")
        .def(nb::init<>())
        .def_ro("index", &TransformHandle::index)
        .def_ro("generation", &TransformHandle::generation)
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
    nb::class_<GeneralTransform3Pool>(m, "GeneralTransform3Pool")
        .def(nb::init<size_t>(), nb::arg("initial_capacity") = 256)

        .def("create", &GeneralTransform3Pool::create,
             nb::arg("local_pose") = GeneralPose3::identity(),
             nb::arg("name") = "")
        .def("destroy", &GeneralTransform3Pool::destroy)
        .def("destroy_by_ptr", &GeneralTransform3Pool::destroy_by_ptr)

        .def("get", nb::overload_cast<TransformHandle>(&GeneralTransform3Pool::get),
             nb::rv_policy::reference)
        .def("is_valid", &GeneralTransform3Pool::is_valid)
        .def("is_valid_ptr", &GeneralTransform3Pool::is_valid_ptr)
        .def("handle_from_ptr", &GeneralTransform3Pool::handle_from_ptr)

        .def("__len__", &GeneralTransform3Pool::size)
        .def_prop_ro("size", &GeneralTransform3Pool::size)
        .def_prop_ro("capacity", &GeneralTransform3Pool::capacity)

        .def("__repr__", [](const GeneralTransform3Pool& pool) {
            return "GeneralTransform3Pool(size=" + std::to_string(pool.size()) +
                   ", capacity=" + std::to_string(pool.capacity()) + ")";
        });

    // AABB
    nb::class_<AABB>(m, "AABB")
        .def(nb::init<>())
        .def(nb::init<const Vec3&, const Vec3&>())
        .def("__init__", [](AABB* self,
                           nb::ndarray<double, nb::c_contig, nb::device::cpu> min_arr,
                           nb::ndarray<double, nb::c_contig, nb::device::cpu> max_arr) {
            new (self) AABB(numpy_to_vec3(min_arr), numpy_to_vec3(max_arr));
        })
        .def_rw("min_point", &AABB::min_point)
        .def_rw("max_point", &AABB::max_point)
        .def("extend", &AABB::extend)
        .def("intersects", &AABB::intersects)
        .def("contains", &AABB::contains)
        .def("merge", &AABB::merge)
        .def("center", &AABB::center)
        .def("size", &AABB::size)
        .def("half_size", &AABB::half_size)
        .def("project_point", &AABB::project_point)
        .def("surface_area", &AABB::surface_area)
        .def("volume", &AABB::volume)
        .def("corners", [](const AABB& aabb) {
            auto corners = aabb.corners();
            double* data = new double[24];  // 8 corners * 3 coords
            for (size_t i = 0; i < 8; ++i) {
                data[i * 3 + 0] = corners[i].x;
                data[i * 3 + 1] = corners[i].y;
                data[i * 3 + 2] = corners[i].z;
            }
            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
            size_t shape[2] = {8, 3};
            return nb::ndarray<nb::numpy, double, nb::shape<8, 3>>(data, 2, shape, owner);
        })
        .def("get_corners_homogeneous", [](const AABB& aabb) {
            auto corners = aabb.corners();
            double* data = new double[32];  // 8 corners * 4 coords
            for (size_t i = 0; i < 8; ++i) {
                data[i * 4 + 0] = corners[i].x;
                data[i * 4 + 1] = corners[i].y;
                data[i * 4 + 2] = corners[i].z;
                data[i * 4 + 3] = 1.0;
            }
            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
            size_t shape[2] = {8, 4};
            return nb::ndarray<nb::numpy, double, nb::shape<8, 4>>(data, 2, shape, owner);
        })
        .def_static("from_points", [](nb::ndarray<double, nb::c_contig, nb::device::cpu> points) {
            size_t n = points.shape(0);
            if (n == 0) {
                return AABB();
            }
            double* ptr = points.data();
            size_t stride = points.shape(1);
            Vec3 min_pt{ptr[0], ptr[1], ptr[2]};
            Vec3 max_pt = min_pt;
            for (size_t i = 1; i < n; ++i) {
                Vec3 p{ptr[i * stride + 0], ptr[i * stride + 1], ptr[i * stride + 2]};
                min_pt.x = std::min(min_pt.x, p.x);
                min_pt.y = std::min(min_pt.y, p.y);
                min_pt.z = std::min(min_pt.z, p.z);
                max_pt.x = std::max(max_pt.x, p.x);
                max_pt.y = std::max(max_pt.y, p.y);
                max_pt.z = std::max(max_pt.z, p.z);
            }
            return AABB(min_pt, max_pt);
        })
        .def("transformed_by", nb::overload_cast<const Pose3&>(&AABB::transformed_by, nb::const_))
        .def("transformed_by", nb::overload_cast<const GeneralPose3&>(&AABB::transformed_by, nb::const_))
        .def("__repr__", [](const AABB& aabb) {
            return "AABB(min_point=Vec3(" + std::to_string(aabb.min_point.x) + ", " +
                   std::to_string(aabb.min_point.y) + ", " + std::to_string(aabb.min_point.z) +
                   "), max_point=Vec3(" + std::to_string(aabb.max_point.x) + ", " +
                   std::to_string(aabb.max_point.y) + ", " + std::to_string(aabb.max_point.z) + "))";
        });
}
